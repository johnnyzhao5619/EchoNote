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
"""
API Key Validation Tool

Used to validate the validity of cloud service API keys
"""

import logging
from typing import Tuple

import httpx

logger = logging.getLogger(__name__)


class APIKeyValidator:
    """API Key Validator"""

    @staticmethod
    async def validate_openai_key(api_key: str, timeout: int = 10) -> Tuple[bool, str]:
        """
        Validate OpenAI API key

        Args:
            api_key: OpenAI API key
            timeout: Timeout in seconds

        Returns:
            Tuple[bool, str]: (is_valid, error_message)
        """
        if not api_key or not api_key.strip():
            return False, "API key cannot be empty"

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(
                    "https://api.openai.com/v1/models",
                    headers={"Authorization": f"Bearer {api_key}"},
                )

                if response.status_code == 200:
                    logger.info("OpenAI API key validation successful")
                    return True, "API key is valid"
                elif response.status_code == 401:
                    logger.warning("OpenAI API key validation failed: Unauthorized")
                    return False, "Invalid API key"
                elif response.status_code == 429:
                    logger.warning("OpenAI API key validation failed: Rate limited")
                    return False, "Rate limit exceeded, but key appears valid"
                else:
                    logger.error(f"OpenAI API key validation failed: {response.status_code}")
                    return False, f"Validation failed with status {response.status_code}"

        except httpx.ConnectError:
            logger.error("OpenAI API key validation failed: Connection error")
            return False, "Connection error. Please check your network"
        except httpx.TimeoutException:
            logger.error("OpenAI API key validation failed: Timeout")
            return False, "Request timeout. Please try again"
        except Exception as e:
            logger.error(f"OpenAI API key validation failed: {e}")
            return False, f"Validation error: {str(e)}"

    @staticmethod
    async def validate_google_key(api_key: str, timeout: int = 10) -> Tuple[bool, str]:
        """
        Validate Google Cloud Speech-to-Text API key

        Args:
            api_key: Google API key
            timeout: Timeout in seconds

        Returns:
            Tuple[bool, str]: (is_valid, error_message)
        """
        if not api_key or not api_key.strip():
            return False, "API key cannot be empty"

        try:
            # Use simple API call to test key
            # Note: This requires valid audio data, using minimal test request here
            async with httpx.AsyncClient(timeout=timeout) as client:
                # Test API endpoint accessibility
                test_url = f"https://speech.googleapis.com/v1/speech:recognize?key={api_key}"

                # Send a minimal test request
                test_data = {
                    "config": {
                        "encoding": "LINEAR16",
                        "sampleRateHertz": 16000,
                        "languageCode": "en-US",
                    },
                    "audio": {"content": ""},  # Empty content returns error but validates key
                }

                response = await client.post(test_url, json=test_data)

                # Even if request fails, if not auth error, key is valid
                if response.status_code == 200:
                    logger.info("Google API key validation successful")
                    return True, "API key is valid"
                elif response.status_code == 400:
                    # 400 error usually indicates request format issue, but key is valid
                    logger.info("Google API key appears valid (400 response)")
                    return True, "API key is valid"
                elif response.status_code == 401 or response.status_code == 403:
                    logger.warning("Google API key validation failed: Unauthorized")
                    return False, "Invalid API key or insufficient permissions"
                elif response.status_code == 429:
                    logger.warning("Google API key validation failed: Rate limited")
                    return False, "Rate limit exceeded, but key appears valid"
                else:
                    logger.error(f"Google API key validation failed: {response.status_code}")
                    return False, f"Validation failed with status {response.status_code}"

        except httpx.ConnectError:
            logger.error("Google API key validation failed: Connection error")
            return False, "Connection error. Please check your network"
        except httpx.TimeoutException:
            logger.error("Google API key validation failed: Timeout")
            return False, "Request timeout. Please try again"
        except Exception as e:
            logger.error(f"Google API key validation failed: {e}")
            return False, f"Validation error: {str(e)}"

    @staticmethod
    async def validate_azure_key(api_key: str, region: str, timeout: int = 10) -> Tuple[bool, str]:
        """
        Validate Azure Speech Service API key

        Args:
            api_key: Azure API key
            region: Azure region (e.g., eastus)
            timeout: Timeout in seconds

        Returns:
            Tuple[bool, str]: (is_valid, error_message)
        """
        if not api_key or not api_key.strip():
            return False, "API key cannot be empty"

        if not region or not region.strip():
            return False, "Region cannot be empty"

        try:
            # Use token endpoint to validate key
            async with httpx.AsyncClient(timeout=timeout) as client:
                token_url = f"https://{region}.api.cognitive.microsoft.com/sts/v1.0/issueToken"

                response = await client.post(
                    token_url, headers={"Ocp-Apim-Subscription-Key": api_key}
                )

                if response.status_code == 200:
                    logger.info("Azure API key validation successful")
                    return True, "API key is valid"
                elif response.status_code == 401 or response.status_code == 403:
                    logger.warning("Azure API key validation failed: Unauthorized")
                    return False, "Invalid API key"
                elif response.status_code == 429:
                    logger.warning("Azure API key validation failed: Rate limited")
                    return False, "Rate limit exceeded, but key appears valid"
                else:
                    logger.error(f"Azure API key validation failed: {response.status_code}")
                    return False, f"Validation failed with status {response.status_code}"

        except httpx.ConnectError:
            logger.error("Azure API key validation failed: Connection error")
            return False, "Connection error. Please check your network"
        except httpx.TimeoutException:
            logger.error("Azure API key validation failed: Timeout")
            return False, "Request timeout. Please try again"
        except Exception as e:
            logger.error(f"Azure API key validation failed: {e}")
            return False, f"Validation error: {str(e)}"
