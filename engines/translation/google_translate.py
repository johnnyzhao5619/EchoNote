# SPDX-License-Identifier: Apache-2.0
#
# Copyright (c) 2024-2025 EchoNote Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Google Translate engine implementation using Google Cloud Translation API."""

import logging
from typing import List, Optional
import httpx

from engines.speech.base import (
    BASE_LANGUAGE_CODES,
    CHINESE_LANGUAGE_VARIANTS,
    combine_languages,
)
from engines.translation.base import TranslationEngine

logger = logging.getLogger(__name__)


class GoogleTranslateEngine(TranslationEngine):
    """Google Translate engine implementation."""

    # Primary languages supported by Google Translate.
    SUPPORTED_LANGUAGES = combine_languages(
        ("zh",),
        CHINESE_LANGUAGE_VARIANTS,
        BASE_LANGUAGE_CODES,
    )

    def __init__(self, api_key: str, max_retries: int = 3):
        """Initialize the Google Translate engine.

        Args:
            api_key: Google Cloud API key.
            max_retries: Maximum number of retry attempts.
        """
        self.api_key = api_key
        self.max_retries = max_retries
        base = "https://translation.googleapis.com"
        self.base_url = f"{base}/language/translate/v2"

        # Create the underlying HTTP client.
        self.client: Optional[httpx.AsyncClient] = httpx.AsyncClient(
            timeout=30.0, headers={"Content-Type": "application/json"}
        )

        logger.info("Google Translate engine initialized")

    def get_name(self) -> str:
        """Return the engine identifier."""
        return "google-translate"

    def get_supported_languages(self) -> List[str]:
        """Return the supported language codes."""
        return self.SUPPORTED_LANGUAGES.copy()

    async def translate(self, text: str, source_lang: str = "auto", target_lang: str = "en") -> str:
        """Translate text using the Google Cloud Translation API.

        Args:
            text: Input text to translate.
            source_lang: Source language code. ``"auto"`` enables detection.
            target_lang: Target language code.

        Returns:
            str: Translated text.
        """
        if not text or not text.strip():
            return ""

        # Validate the target language.
        if not self.validate_language(target_lang):
            msg = f"Unsupported target language: {target_lang}"
            logger.error(msg)
            raise ValueError(msg)

        # Prepare request parameters.
        params = {"key": self.api_key, "q": text, "target": target_lang}

        # Include the explicit source language when provided.
        if source_lang != "auto":
            if not self.validate_language(source_lang):
                msg = f"Unsupported source language: {source_lang}"
                logger.error(msg)
                raise ValueError(msg)
            params["source"] = source_lang

        # Retry loop.
        last_error = None
        for attempt in range(self.max_retries):
            try:
                logger.debug(f"Translation attempt {attempt + 1}/" f"{self.max_retries}")

                # Send the HTTP request.
                response = await self.client.post(self.base_url, params=params)

                # Inspect the response status code.
                if response.status_code == 200:
                    data = response.json()

                    # Extract translation payload.
                    if "data" in data and "translations" in data["data"]:
                        translations = data["data"]["translations"]
                        if translations:
                            translated = translations[0]["translatedText"]
                            logger.debug(
                                f"Translation successful: "
                                f"{text[:50]}... -> {translated[:50]}..."
                            )
                            return translated

                    logger.error(f"Unexpected response format: {data}")
                    msg = "Unexpected response format from API"
                    raise ValueError(msg)

                elif response.status_code == 400:
                    # Client error: do not retry.
                    error_data = response.json()
                    error_msg = error_data.get("error", {}).get("message", "Unknown error")
                    logger.error(f"Google Translate API error (400): {error_msg}")
                    raise ValueError(f"Translation failed: {error_msg}")

                elif response.status_code == 403:
                    # Authentication error: do not retry.
                    logger.error("Google Translate API authentication failed (403)")
                    msg = "Invalid API key or insufficient permissions"
                    raise ValueError(msg)

                elif response.status_code == 429:
                    # Rate limit exceeded: apply exponential backoff.
                    logger.warning("Google Translate API rate limit exceeded (429)")
                    if attempt < self.max_retries - 1:
                        import asyncio

                        await asyncio.sleep(2**attempt)  # Exponential backoff.
                        continue
                    msg = "Translation failed: Rate limit exceeded"
                    raise ValueError(msg)

                else:
                    # Other error: retry when attempts remain.
                    logger.warning(f"Google Translate API error " f"({response.status_code})")
                    if attempt < self.max_retries - 1:
                        import asyncio

                        await asyncio.sleep(1)
                        continue
                    msg = f"Translation failed with status code: " f"{response.status_code}"
                    raise ValueError(msg)

            except httpx.RequestError as e:
                # Network error: retry.
                logger.warning(f"Network error during translation: {e}")
                last_error = e
                if attempt < self.max_retries - 1:
                    import asyncio

                    await asyncio.sleep(1)
                    continue

            except Exception as e:
                # Propagate unexpected errors.
                logger.error(f"Translation error: {e}")
                raise

        # All retries exhausted.
        if last_error:
            msg = f"Translation failed after {self.max_retries} " f"attempts: {last_error}"
            raise ValueError(msg)

        msg = f"Translation failed after {self.max_retries} attempts"
        raise ValueError(msg)

    def close(self):
        """Synchronously close the underlying HTTP client."""
        return self.aclose()

    async def aclose(self) -> None:
        """Asynchronously close the underlying HTTP client."""
        if self.client is None:
            return

        client = self.client
        self.client = None

        try:
            await client.aclose()
        except Exception:
            # Restore the client so callers can retry closing if needed.
            self.client = client
            raise
        else:
            logger.debug("Google Translate AsyncClient closed")

    async def detect_language(self, text: str) -> str:
        """Detect the language of the supplied text.

        Args:
            text: Text whose language should be detected.

        Returns:
            str: Detected language code or ``"unknown"``.
        """
        if not text or not text.strip():
            return "unknown"

        try:
            # Use the Google Translate API detection endpoint.
            params = {"key": self.api_key, "q": text}

            response = await self.client.post(f"{self.base_url}/detect", params=params)

            if response.status_code == 200:
                data = response.json()
                if "data" in data and "detections" in data["data"]:
                    detections = data["data"]["detections"]
                    if detections and detections[0]:
                        language = detections[0][0]["language"]
                        confidence = detections[0][0].get("confidence", 0)
                        logger.debug(
                            f"Detected language: {language} " f"(confidence: {confidence})"
                        )
                        return language

            logger.warning("Language detection failed")
            return "unknown"

        except Exception as e:
            logger.error(f"Language detection error: {e}")
            return "unknown"

    def get_config_schema(self) -> dict:
        """Return the JSON schema describing configuration options."""
        return {
            "type": "object",
            "properties": {
                "api_key": {"type": "string", "description": "Google Cloud API Key"},
                "max_retries": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 10,
                    "default": 3,
                    "description": "Maximum number of retry attempts",
                },
            },
            "required": ["api_key"],
        }

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.aclose()
