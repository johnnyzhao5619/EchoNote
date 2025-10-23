"""
OpenAI Whisper API 语音识别引擎

使用 OpenAI 的 Whisper API 进行云端语音识别
"""

import logging
from typing import Dict, List, Optional
import numpy as np
import os
from pathlib import Path

from engines.speech.base import (
    BASE_LANGUAGE_CODES,
    CLOUD_SPEECH_ADDITIONAL_LANGUAGES,
    SpeechEngine,
    combine_languages,
)
from utils.http_client import AsyncRetryableHttpClient
from data.database.models import APIUsage

logger = logging.getLogger(__name__)


class OpenAIEngine(SpeechEngine):
    """OpenAI Whisper API 引擎"""

    API_BASE_URL = "https://api.openai.com/v1"
    MAX_FILE_SIZE = 25 * 1024 * 1024  # 25 MB
    SUPPORTED_FORMATS = [
        'mp3', 'mp4', 'mpeg', 'mpga', 'm4a',
        'wav', 'webm', 'flac', 'ogg'
    ]

    def __init__(
        self,
        api_key: str,
        db_connection=None,
        timeout: int = 60,
        max_retries: int = 3,
        base_url: Optional[str] = None
    ):
        """
        初始化 OpenAI 引擎

        Args:
            api_key: OpenAI API Key
            db_connection: 数据库连接（用于记录使用量）
            timeout: 请求超时时间（秒）
            max_retries: 最大重试次数
            base_url: API 基础 URL（可选，用于测试或自定义端点）
        """
        if not api_key or not api_key.strip():
            raise ValueError("API key is required for OpenAI engine")

        self.api_key = api_key
        self.db_connection = db_connection
        self.timeout = timeout
        self.max_retries = max_retries
        self.base_url = base_url or self.API_BASE_URL

        # 使用可重试的 HTTP 客户端
        self.client = AsyncRetryableHttpClient(
            max_retries=max_retries,
            timeout=timeout,
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {api_key}"
            }
        )

        logger.info(
            f"OpenAI engine initialized: "
            f"timeout={timeout}s, max_retries={max_retries}"
        )

    def get_name(self) -> str:
        """获取引擎名称"""
        return "openai-whisper"

    def get_supported_languages(self) -> List[str]:
        """获取支持的语言列表"""
        # OpenAI Whisper 支持的基础语言及扩展语言
        return combine_languages(
            BASE_LANGUAGE_CODES,
            CLOUD_SPEECH_ADDITIONAL_LANGUAGES,
        )

    async def transcribe_file(
        self,
        audio_path: str,
        language: Optional[str] = None,
        **kwargs
    ) -> Dict:
        """
        转录音频文件

        Args:
            audio_path: 音频文件路径
            language: 源语言代码（ISO-639-1）
            **kwargs: 额外参数
                - prompt: 可选的提示文本
                - temperature: 采样温度（0-1）
                - progress_callback: 进度回调 (progress: float) -> None

        Returns:
            Dict: 转录结果，格式为：
            {
                "segments": [
                    {"start": float, "end": float, "text": str}, ...
                ],
                "language": str,
                "duration": float
            }

        Raises:
            ValueError: 文件大小超限或格式不支持
            httpx.HTTPError: API 请求失败
        """
        # 检查文件是否存在
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Audio file not found: {audio_path}")
        
        # 检查文件大小
        file_size = Path(audio_path).stat().st_size
        if file_size > self.MAX_FILE_SIZE:
            max_mb = self.MAX_FILE_SIZE / 1024 / 1024
            raise ValueError(
                f"File size ({file_size / 1024 / 1024:.2f} MB) exceeds "
                f"OpenAI's maximum ({max_mb} MB). "
                f"Please use a smaller file or faster-whisper."
            )

        # 检查文件格式
        file_ext = Path(audio_path).suffix.lower().lstrip('.')
        if file_ext not in self.SUPPORTED_FORMATS:
            formats = ', '.join(self.SUPPORTED_FORMATS)
            raise ValueError(
                f"Unsupported file format: .{file_ext}. "
                f"Supported formats: {formats}"
            )

        prompt = kwargs.get('prompt', '')
        temperature = kwargs.get('temperature', 0)
        progress_callback = kwargs.get('progress_callback')

        logger.info(
            f"Transcribing file with OpenAI: {audio_path}, "
            f"language={language}, size={file_size / 1024 / 1024:.2f}MB"
        )

        # 调用进度回调（开始）
        if progress_callback:
            try:
                progress_callback(10.0)  # 10% - 开始上传
            except Exception as e:
                logger.error(f"Error in progress callback: {e}")

        # 准备请求数据
        data = {
            "model": "whisper-1",
            "response_format": "verbose_json",
            "timestamp_granularities": ["segment"]
        }

        if language:
            data["language"] = language
        if prompt:
            data["prompt"] = prompt
        if temperature:
            data["temperature"] = temperature

        try:
            # 发送请求（AsyncRetryableHttpClient 会自动处理重试）
            with open(audio_path, 'rb') as f:
                file_name = Path(audio_path).name
                mime_type = f"audio/{file_ext}"
                files = {"file": (file_name, f, mime_type)}

                # 调用进度回调（上传中）
                if progress_callback:
                    try:
                        # 30% - 上传完成，等待处理
                        progress_callback(30.0)
                    except Exception as e:
                        logger.error(f"Error in progress callback: {e}")

                response = await self.client.post(
                    "/audio/transcriptions",
                    files=files,
                    data=data
                )

            # 调用进度回调（处理中）
            if progress_callback:
                try:
                    # 70% - 处理完成，解析结果
                    progress_callback(70.0)
                except Exception as e:
                    logger.error(f"Error in progress callback: {e}")

            # 解析响应
            result_data = response.json()

            # 转换为标准格式
            segments = []
            if "segments" in result_data:
                for seg in result_data["segments"]:
                    segments.append({
                        "start": seg["start"],
                        "end": seg["end"],
                        "text": seg["text"].strip()
                    })
            else:
                # 如果没有段落信息，创建单个段落
                segments.append({
                    "start": 0.0,
                    "end": result_data.get("duration", 0.0),
                    "text": result_data.get("text", "").strip()
                })

            duration = result_data.get("duration", 0.0)
            detected_language = result_data.get(
                "language", language or "unknown"
            )

            result = {
                "segments": segments,
                "language": detected_language,
                "duration": duration
            }

            # 记录使用量到数据库
            if self.db_connection and duration > 0:
                try:
                    usage = APIUsage(
                        engine="openai",
                        duration_seconds=duration,
                        cost=self._calculate_cost(duration)
                    )
                    usage.save(self.db_connection)
                    logger.debug(
                        f"Recorded API usage: duration={duration:.2f}s, "
                        f"cost=${usage.cost:.4f}"
                    )
                except Exception as e:
                    logger.error(f"Failed to record API usage: {e}")

            # 调用进度回调（完成）
            if progress_callback:
                try:
                    progress_callback(100.0)  # 100% - 完成
                except Exception as e:
                    logger.error(f"Error in progress callback: {e}")

            logger.info(
                f"Transcription completed: {len(segments)} segments, "
                f"language={detected_language}, duration={duration:.2f}s"
            )
            return result

        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            # 提供更友好的错误信息
            if "401" in str(e):
                raise ValueError(
                    "Invalid API key. "
                    "Please check your OpenAI API key in Settings."
                )
            elif "429" in str(e):
                raise ValueError(
                    "Rate limit exceeded. "
                    "Please try again later or upgrade your OpenAI plan."
                )
            elif "500" in str(e) or "502" in str(e) or "503" in str(e):
                raise ValueError(
                    "OpenAI service is temporarily unavailable. "
                    "Please try again later."
                )
            else:
                raise

    def _calculate_cost(self, duration_seconds: float) -> float:
        """
        计算转录费用

        Args:
            duration_seconds: 音频时长（秒）

        Returns:
            float: 费用（美元）
        """
        # OpenAI Whisper API 定价：$0.006 per minute
        duration_minutes = duration_seconds / 60.0
        cost = duration_minutes * 0.006
        return round(cost, 4)

    async def transcribe_stream(
        self,
        audio_chunk: np.ndarray,
        language: Optional[str] = None,
        sample_rate: Optional[int] = None,
        **kwargs
    ) -> str:
        """
        实时转录音频流

        注意：OpenAI API 不支持真正的流式转录，这里将音频块缓冲后转录。
        建议使用 faster-whisper 引擎进行实时转录以获得更好的性能。

        Args:
            audio_chunk: 音频数据块（numpy array）
            language: 源语言代码（可选）
            sample_rate: 音频采样率（Hz）
            **kwargs: 引擎特定的额外参数

        Returns:
            str: 转录文本片段
        """
        import tempfile
        import soundfile as sf

        # 检查音频长度（至少需要 1 秒的音频）
        effective_rate = sample_rate if sample_rate and sample_rate > 0 else 16000

        if len(audio_chunk) < effective_rate:
            logger.debug(
                f"Audio chunk too short ({len(audio_chunk)} samples), "
                "skipping transcription"
            )
            return ""

        chunk_duration = len(audio_chunk) / float(effective_rate)
        logger.debug(
            f"Transcribing audio stream with OpenAI: "
            f"length={len(audio_chunk)} samples ({chunk_duration:.2f}s)"
        )

        # 保存为临时文件
        with tempfile.NamedTemporaryFile(
            suffix='.wav', delete=False
        ) as tmp_file:
            tmp_path = tmp_file.name

        try:
            # 写入音频文件
            sf.write(tmp_path, audio_chunk, effective_rate)

            # 转录临时文件
            stream_kwargs = {**kwargs, 'sample_rate': effective_rate}
            result = await self.transcribe_file(tmp_path, language, **stream_kwargs)

            # 合并所有段落的文本
            text = " ".join([seg["text"] for seg in result["segments"]])

            logger.debug(f"Stream transcription result: '{text}'")
            return text

        except Exception as e:
            logger.error(f"Stream transcription failed: {e}")
            return ""

        finally:
            # 清理临时文件
            try:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
            except Exception as e:
                logger.warning(
                    f"Failed to delete temp file {tmp_path}: {e}"
                )

    def get_config_schema(self) -> Dict:
        """获取配置 Schema"""
        return {
            "type": "object",
            "properties": {
                "api_key": {
                    "type": "string",
                    "description": "OpenAI API Key",
                    "minLength": 1
                },
                "timeout": {
                    "type": "integer",
                    "default": 60,
                    "description": "请求超时时间（秒）"
                },
                "max_retries": {
                    "type": "integer",
                    "default": 3,
                    "minimum": 1,
                    "maximum": 10,
                    "description": "最大重试次数"
                }
            },
            "required": ["api_key"]
        }

    async def close(self):
        """关闭客户端连接"""
        await self.client.close()
        logger.info("OpenAI engine client closed")
