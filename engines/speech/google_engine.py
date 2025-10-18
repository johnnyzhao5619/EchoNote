"""
Google Speech-to-Text API 语音识别引擎

使用 Google Cloud Speech-to-Text API 进行云端语音识别
"""

import logging
from typing import Dict, List, Optional
import numpy as np
import httpx
from pathlib import Path
import base64

from engines.speech.base import SpeechEngine

logger = logging.getLogger(__name__)


class GoogleEngine(SpeechEngine):
    """Google Speech-to-Text 引擎"""

    API_BASE_URL = "https://speech.googleapis.com/v1"
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB (同步识别限制)

    def __init__(self, api_key: str, timeout: int = 60, max_retries: int = 3):
        """
        初始化 Google 引擎
        
        Args:
            api_key: Google Cloud API Key
            timeout: 请求超时时间（秒）
            max_retries: 最大重试次数
        """
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries
        
        self.client = httpx.AsyncClient(
            base_url=self.API_BASE_URL,
            timeout=timeout
        )
        
        logger.info("Google Speech-to-Text engine initialized")

    def get_name(self) -> str:
        """获取引擎名称"""
        return "google-speech"

    def get_supported_languages(self) -> List[str]:
        """获取支持的语言列表"""
        # Google Speech-to-Text 支持的主要语言
        return [
            'zh', 'en', 'fr', 'de', 'es', 'it', 'ja', 'ko', 'pt', 'ru',
            'ar', 'hi', 'nl', 'pl', 'tr', 'vi', 'id', 'th', 'uk', 'sv',
            'da', 'no', 'fi', 'cs', 'ro', 'bg', 'el', 'he', 'fa', 'ur'
        ]

    def _convert_language_code(self, language: Optional[str]) -> str:
        """
        转换语言代码为 Google 格式
        
        Args:
            language: ISO-639-1 语言代码
            
        Returns:
            str: Google 语言代码（如 'zh-CN', 'en-US'）
        """
        if not language:
            return "en-US"
        
        # 语言代码映射
        mapping = {
            'zh': 'zh-CN',
            'en': 'en-US',
            'fr': 'fr-FR',
            'de': 'de-DE',
            'es': 'es-ES',
            'it': 'it-IT',
            'ja': 'ja-JP',
            'ko': 'ko-KR',
            'pt': 'pt-BR',
            'ru': 'ru-RU',
            'ar': 'ar-SA',
            'hi': 'hi-IN',
            'nl': 'nl-NL',
            'pl': 'pl-PL',
            'tr': 'tr-TR',
            'vi': 'vi-VN',
            'id': 'id-ID',
            'th': 'th-TH',
            'uk': 'uk-UA',
            'sv': 'sv-SE'
        }
        
        return mapping.get(language, f"{language}-{language.upper()}")

    async def transcribe_file(self, audio_path: str, language: Optional[str] = None, **kwargs) -> Dict:
        """
        转录音频文件
        
        Args:
            audio_path: 音频文件路径
            language: 源语言代码
            **kwargs: 额外参数
                - enable_automatic_punctuation: 启用自动标点（默认 True）
                - enable_word_time_offsets: 启用词级时间戳（默认 False）
        """
        # 检查文件大小
        file_size = Path(audio_path).stat().st_size
        if file_size > self.MAX_FILE_SIZE:
            raise ValueError(
                f"File size ({file_size} bytes) exceeds maximum ({self.MAX_FILE_SIZE} bytes). "
                "Consider using Google Cloud Storage for larger files."
            )
        
        enable_punctuation = kwargs.get('enable_automatic_punctuation', True)
        enable_word_offsets = kwargs.get('enable_word_time_offsets', False)
        sample_rate = kwargs.get('sample_rate')
        
        logger.info(f"Transcribing file with Google: {audio_path}, language={language}")
        
        # 读取音频文件并编码为 base64
        with open(audio_path, 'rb') as f:
            audio_content = base64.b64encode(f.read()).decode('utf-8')
        
        # 准备请求数据
        request_data = {
            "config": {
                "encoding": "LINEAR16",  # 假设 WAV 格式
                "sampleRateHertz": sample_rate or 16000,
                "languageCode": self._convert_language_code(language),
                "enableAutomaticPunctuation": enable_punctuation,
                "enableWordTimeOffsets": enable_word_offsets
            },
            "audio": {
                "content": audio_content
            }
        }
        
        # 发送请求（带重试）
        for attempt in range(self.max_retries):
            try:
                response = await self.client.post(
                    f"/speech:recognize?key={self.api_key}",
                    json=request_data
                )
                response.raise_for_status()
                
                # 解析响应
                result_data = response.json()
                
                # 转换为标准格式
                segments = []
                if "results" in result_data:
                    current_time = 0.0
                    
                    for result in result_data["results"]:
                        if "alternatives" in result and result["alternatives"]:
                            alternative = result["alternatives"][0]
                            text = alternative.get("transcript", "").strip()
                            
                            # 如果有词级时间戳，使用它们
                            if "words" in alternative and alternative["words"]:
                                words = alternative["words"]
                                start_time = float(words[0].get("startTime", "0s").rstrip('s'))
                                end_time = float(words[-1].get("endTime", "0s").rstrip('s'))
                            else:
                                # 否则估算时间
                                duration = len(text.split()) * 0.5  # 假设每个词 0.5 秒
                                start_time = current_time
                                end_time = current_time + duration
                                current_time = end_time
                            
                            segments.append({
                                "start": start_time,
                                "end": end_time,
                                "text": text
                            })
                
                result = {
                    "segments": segments,
                    "language": language or "unknown",
                    "duration": segments[-1]["end"] if segments else 0.0
                }
                
                logger.info(f"Transcription completed: {len(segments)} segments")
                return result
                
            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP error (attempt {attempt + 1}/{self.max_retries}): {e}")
                
                if e.response.status_code == 429:
                    # 速率限制
                    if attempt < self.max_retries - 1:
                        import asyncio
                        wait_time = 2 ** attempt
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
        **kwargs
    ) -> str:
        """
        实时转录音频流

        注意：这里使用同步识别 API，真正的流式识别需要使用 gRPC

        Args:
            audio_chunk: 音频数据块
            language: 源语言代码
            sample_rate: 输入音频的采样率
        """
        import tempfile
        import soundfile as sf
        
        logger.debug("Transcribing audio stream with Google")

        effective_rate = sample_rate if sample_rate and sample_rate > 0 else 16000

        # 保存为临时文件
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
            tmp_path = tmp_file.name
            sf.write(tmp_path, audio_chunk, effective_rate)

        try:
            # 转录临时文件
            stream_kwargs = {**kwargs, 'sample_rate': effective_rate}
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
                "api_key": {
                    "type": "string",
                    "description": "Google Cloud API Key",
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
        await self.client.aclose()
