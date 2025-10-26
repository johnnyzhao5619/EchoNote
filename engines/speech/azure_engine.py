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
Azure Speech API 语音识别引擎

使用 Microsoft Azure Cognitive Services Speech API 进行云端语音识别
"""

import logging
from typing import Dict, List, Optional

import httpx
import numpy as np

from engines.speech.base import (
    BASE_LANGUAGE_CODES,
    CLOUD_SPEECH_ADDITIONAL_LANGUAGES,
    CLOUD_SPEECH_LANGUAGE_LOCALE_MAPPING,
    SpeechEngine,
    combine_languages,
    convert_audio_to_wav_bytes,
)

logger = logging.getLogger(__name__)


class AzureEngine(SpeechEngine):
    """Azure Speech API 引擎"""

    def __init__(self, subscription_key: str, region: str, timeout: int = 60, max_retries: int = 3):
        """
        初始化 Azure 引擎

        Args:
            subscription_key: Azure 订阅密钥
            region: Azure 区域（如 'eastus', 'westeurope'）
            timeout: 请求超时时间（秒）
            max_retries: 最大重试次数
        """
        self.subscription_key = subscription_key
        self.region = region
        self.timeout = timeout
        self.max_retries = max_retries

        self.api_base_url = f"https://{region}.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1"

        self.client = httpx.AsyncClient(
            headers={"Ocp-Apim-Subscription-Key": subscription_key, "Content-Type": "audio/wav"},
            timeout=timeout,
        )

        logger.info(f"Azure Speech engine initialized (region: {region})")

    def get_name(self) -> str:
        """获取引擎名称"""
        return "azure-speech"

    def get_supported_languages(self) -> List[str]:
        """获取支持的语言列表"""
        # Azure Speech 支持的基础语言及扩展语言
        return combine_languages(
            BASE_LANGUAGE_CODES,
            CLOUD_SPEECH_ADDITIONAL_LANGUAGES,
        )

    def _convert_language_code(self, language: Optional[str]) -> str:
        """
        转换语言代码为 Azure 格式

        Args:
            language: ISO-639-1 语言代码

        Returns:
            str: Azure 语言代码（如 'zh-CN', 'en-US'）
        """
        if not language:
            return "en-US"

        return CLOUD_SPEECH_LANGUAGE_LOCALE_MAPPING.get(language, language)

    async def transcribe_file(
        self, audio_path: str, language: Optional[str] = None, **kwargs
    ) -> Dict:
        """
        转录音频文件

        Args:
            audio_path: 音频文件路径
            language: 源语言代码
            **kwargs: 额外参数
                - profanity: 脏话过滤模式 ('masked', 'removed', 'raw')
        """
        profanity = kwargs.get("profanity", "masked")
        sample_rate = kwargs.get("sample_rate")
        language_code = self._convert_language_code(language)

        logger.info(f"Transcribing file with Azure: {audio_path}, language={language_code}")
        if sample_rate:
            logger.debug(f"Azure transcription input sample rate: {sample_rate} Hz")

        # 准备 URL 参数
        params = {"language": language_code, "format": "detailed", "profanity": profanity}

        target_rate = sample_rate or 16000
        audio_data, effective_rate, original_rate, detected_format = convert_audio_to_wav_bytes(
            audio_path, target_rate
        )

        logger.debug(
            "Azure audio prepared: format=%s, original_rate=%s, effective_rate=%s",
            detected_format,
            original_rate,
            effective_rate,
        )

        # 发送请求（带重试）
        for attempt in range(self.max_retries):
            try:
                headers = dict(self.client.headers)
                headers["Content-Type"] = (
                    f"audio/wav; codecs=audio/pcm; samplerate={effective_rate}"
                )
                response = await self.client.post(
                    self.api_base_url, params=params, content=audio_data, headers=headers
                )
                response.raise_for_status()

                # 解析响应
                result_data = response.json()

                # 转换为标准格式
                segments = []

                if result_data.get("RecognitionStatus") == "Success":
                    # Azure 返回的是完整文本，需要分段
                    if "NBest" in result_data and result_data["NBest"]:
                        best_result = result_data["NBest"][0]

                        # 如果有词级信息，使用它们创建段落
                        if "Words" in best_result:
                            words = best_result["Words"]

                            # 将词组合成句子段落（简单实现：每 10 个词一个段落）
                            segment_size = 10
                            for i in range(0, len(words), segment_size):
                                segment_words = words[i : i + segment_size]

                                if segment_words:
                                    start_time = segment_words[0]["Offset"] / 10000000  # 转换为秒
                                    end_time = (
                                        segment_words[-1]["Offset"] + segment_words[-1]["Duration"]
                                    ) / 10000000
                                    text = " ".join([w["Word"] for w in segment_words])

                                    segments.append(
                                        {"start": start_time, "end": end_time, "text": text}
                                    )
                        else:
                            # 没有词级信息，创建单个段落
                            duration = result_data.get("Duration", 0) / 10000000
                            segments.append(
                                {
                                    "start": 0.0,
                                    "end": duration,
                                    "text": best_result.get("Display", "").strip(),
                                }
                            )

                result = {
                    "segments": segments,
                    "language": language or "unknown",
                    "duration": segments[-1]["end"] if segments else 0.0,
                }

                logger.info(f"Transcription completed: {len(segments)} segments")
                return result

            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP error (attempt {attempt + 1}/{self.max_retries}): {e}")

                if e.response.status_code == 429:
                    # 速率限制
                    if attempt < self.max_retries - 1:
                        import asyncio

                        wait_time = 2**attempt
                        logger.info(f"Rate limited, waiting {wait_time}s before retry...")
                        await asyncio.sleep(wait_time)
                        continue

                if attempt == self.max_retries - 1:
                    raise

            except Exception as e:
                logger.error(f"Request failed (attempt {attempt + 1}/{self.max_retries}): {e}")
                if attempt == self.max_retries - 1:
                    raise

    async def transcribe_stream(
        self,
        audio_chunk: np.ndarray,
        language: Optional[str] = None,
        sample_rate: Optional[int] = None,
        **kwargs,
    ) -> str:
        """
        实时转录音频流

        注意：这里使用 REST API，真正的流式识别需要使用 WebSocket

        Args:
            audio_chunk: 音频数据块
            language: 源语言代码
            sample_rate: 输入音频的采样率
        """
        import tempfile

        import soundfile as sf

        logger.debug("Transcribing audio stream with Azure")

        effective_rate = sample_rate if sample_rate and sample_rate > 0 else 16000

        # 保存为临时文件
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
            tmp_path = tmp_file.name
            sf.write(tmp_path, audio_chunk, effective_rate)

        try:
            # 转录临时文件
            stream_kwargs = {**kwargs, "sample_rate": effective_rate}
            result = await self.transcribe_file(tmp_path, language, **stream_kwargs)

            # 合并所有段落的文本
            text = " ".join([seg["text"] for seg in result["segments"]])
            return text

        finally:
            # 清理临时文件
            import os

            os.unlink(tmp_path)

    def get_config_schema(self) -> Dict:
        """获取配置 Schema"""
        return {
            "type": "object",
            "properties": {
                "subscription_key": {
                    "type": "string",
                    "description": "Azure 订阅密钥",
                    "minLength": 1,
                },
                "region": {
                    "type": "string",
                    "description": "Azure 区域（如 'eastus', 'westeurope'）",
                    "minLength": 1,
                },
                "timeout": {"type": "integer", "default": 60, "description": "请求超时时间（秒）"},
                "max_retries": {
                    "type": "integer",
                    "default": 3,
                    "minimum": 1,
                    "maximum": 10,
                    "description": "最大重试次数",
                },
            },
            "required": ["subscription_key", "region"],
        }

    async def close(self):
        """关闭客户端连接"""
        await self.client.aclose()
