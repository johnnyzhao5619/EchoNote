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

from config.api_constants import GOOGLE_TRANSLATE_BASE_URL
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
        self.base_url = f"{GOOGLE_TRANSLATE_BASE_URL}/language/translate/v2"

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

        For long texts exceeding ``_MAX_CHARS_PER_REQUEST``, the input is split
        into sentence-boundary chunks and each chunk is translated separately,
        then the results are joined.

        Args:
            text: Input text to translate.
            source_lang: Source language code. ``"auto"`` enables detection.
            target_lang: Target language code.

        Returns:
            str: Translated text.
        """
        if not text or not text.strip():
            return ""

        # Validate languages up-front.
        if not self.validate_language(target_lang):
            msg = f"Unsupported target language: {target_lang}"
            logger.error(msg)
            raise ValueError(msg)

        if source_lang != "auto" and not self.validate_language(source_lang):
            msg = f"Unsupported source language: {source_lang}"
            logger.error(msg)
            raise ValueError(msg)

        # Split long texts into chunks to stay within per-request limits.
        chunks = self._split_text(text)
        if len(chunks) == 1:
            return await self._translate_chunk(text, source_lang=source_lang, target_lang=target_lang)

        parts = []
        for chunk in chunks:
            part = await self._translate_chunk(chunk, source_lang=source_lang, target_lang=target_lang)
            parts.append(part)
        return " ".join(parts)

    async def _translate_chunk(
        self, text: str, *, source_lang: str, target_lang: str
    ) -> str:
        """Send a single translation request as a POST JSON body.

        The API key is passed as a URL query parameter; the payload (``q``,
        ``target``, ``source``) is sent in the JSON request body.  This avoids
        URL-length limits that arise when long texts are encoded as query
        parameters.
        """
        # API key stays in the URL; content goes in the POST body.
        url_params = {"key": self.api_key}
        body: dict = {"q": text, "target": target_lang, "format": "text"}
        if source_lang != "auto":
            body["source"] = source_lang

        last_error = None
        for attempt in range(self.max_retries):
            try:
                logger.debug("Translation attempt %d/%d", attempt + 1, self.max_retries)

                response = await self.client.post(
                    self.base_url, params=url_params, json=body
                )

                if response.status_code == 200:
                    data = response.json()

                    if "data" in data and "translations" in data["data"]:
                        translations = data["data"]["translations"]
                        if translations:
                            translated = translations[0]["translatedText"]
                            logger.debug(
                                "Translation successful: %s... -> %s...",
                                text[:50],
                                translated[:50],
                            )
                            return translated

                    logger.error("Unexpected response format: %s", data)
                    raise ValueError("Unexpected response format from API")

                elif response.status_code == 400:
                    # Client error: do not retry.
                    error_data = response.json()
                    error_msg = error_data.get("error", {}).get("message", "Unknown error")
                    logger.error("Google Translate API error (400): %s", error_msg)
                    raise ValueError(f"Translation failed: {error_msg}")

                elif response.status_code == 403:
                    # Authentication error: do not retry.
                    logger.error("Google Translate API authentication failed (403)")
                    raise ValueError("Invalid API key or insufficient permissions")

                elif response.status_code == 429:
                    # Rate limit exceeded: exponential backoff.
                    logger.warning("Google Translate API rate limit exceeded (429)")
                    if attempt < self.max_retries - 1:
                        import asyncio

                        await asyncio.sleep(2**attempt)
                        continue
                    raise ValueError("Translation failed: Rate limit exceeded")

                else:
                    logger.warning("Google Translate API error (%d)", response.status_code)
                    if attempt < self.max_retries - 1:
                        import asyncio

                        await asyncio.sleep(1)
                        continue
                    raise ValueError(
                        f"Translation failed with status code: {response.status_code}"
                    )

            except httpx.RequestError as e:
                logger.warning("Network error during translation: %s", e)
                last_error = e
                if attempt < self.max_retries - 1:
                    import asyncio

                    await asyncio.sleep(1)
                    continue

            except Exception as e:
                logger.error("Translation error: %s", e)
                raise

        if last_error:
            raise ValueError(
                f"Translation failed after {self.max_retries} attempts: {last_error}"
            )
        raise ValueError(f"Translation failed after {self.max_retries} attempts")

    # Maximum characters sent to the API in a single request.  Long texts are
    # split at sentence boundaries before each chunk is translated individually.
    _MAX_CHARS_PER_REQUEST: int = 5000

    @classmethod
    def _split_text(cls, text: str) -> List[str]:
        """Split text into chunks not exceeding ``_MAX_CHARS_PER_REQUEST``."""
        import re

        if len(text) <= cls._MAX_CHARS_PER_REQUEST:
            return [text]

        sentences = re.split(r"(?<=[.!?。！？\n])\s*", text)
        chunks: List[str] = []
        current = ""
        for sentence in sentences:
            if not sentence:
                continue
            addition = len(sentence) + (1 if current else 0)
            if current and len(current) + addition > cls._MAX_CHARS_PER_REQUEST:
                chunks.append(current.strip())
                current = sentence
            else:
                current = (current + " " + sentence).strip() if current else sentence
        if current:
            chunks.append(current.strip())

        if not chunks:
            # Fallback: hard split with no sentence boundary detection.
            return [
                text[i : i + cls._MAX_CHARS_PER_REQUEST]
                for i in range(0, len(text), cls._MAX_CHARS_PER_REQUEST)
            ]
        return chunks

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

    async def __aexit__(self, _exc_type, _exc_val, _exc_tb):
        """Async context manager exit."""
        await self.aclose()
