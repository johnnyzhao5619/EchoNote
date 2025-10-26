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
API 密钥验证工具

用于验证云服务 API 密钥的有效性
"""

import logging
from typing import Optional, Tuple

import httpx

logger = logging.getLogger(__name__)


class APIKeyValidator:
    """API 密钥验证器"""

    @staticmethod
    async def validate_openai_key(api_key: str, timeout: int = 10) -> Tuple[bool, str]:
        """
        验证 OpenAI API 密钥

        Args:
            api_key: OpenAI API 密钥
            timeout: 超时时间（秒）

        Returns:
            Tuple[bool, str]: (是否有效, 错误消息)
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
        验证 Google Cloud Speech-to-Text API 密钥

        Args:
            api_key: Google API 密钥
            timeout: 超时时间（秒）

        Returns:
            Tuple[bool, str]: (是否有效, 错误消息)
        """
        if not api_key or not api_key.strip():
            return False, "API key cannot be empty"

        try:
            # 使用简单的 API 调用测试密钥
            # 注意：这需要一个有效的音频数据，这里使用最小的测试请求
            async with httpx.AsyncClient(timeout=timeout) as client:
                # 测试 API 端点可访问性
                test_url = f"https://speech.googleapis.com/v1/speech:recognize?key={api_key}"

                # 发送一个最小的测试请求
                test_data = {
                    "config": {
                        "encoding": "LINEAR16",
                        "sampleRateHertz": 16000,
                        "languageCode": "en-US",
                    },
                    "audio": {"content": ""},  # 空内容会返回错误，但可以验证密钥
                }

                response = await client.post(test_url, json=test_data)

                # 即使请求失败，如果不是认证错误，说明密钥有效
                if response.status_code == 200:
                    logger.info("Google API key validation successful")
                    return True, "API key is valid"
                elif response.status_code == 400:
                    # 400 错误通常表示请求格式问题，但密钥有效
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
        验证 Azure Speech Service API 密钥

        Args:
            api_key: Azure API 密钥
            region: Azure 区域（如 eastus）
            timeout: 超时时间（秒）

        Returns:
            Tuple[bool, str]: (是否有效, 错误消息)
        """
        if not api_key or not api_key.strip():
            return False, "API key cannot be empty"

        if not region or not region.strip():
            return False, "Region cannot be empty"

        try:
            # 使用 token 端点验证密钥
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
