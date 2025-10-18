"""
语音引擎抽象基类

定义所有语音识别引擎必须实现的统一接口
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple
import numpy as np


def ensure_audio_sample_rate(
    audio_chunk: np.ndarray,
    source_rate: Optional[int],
    target_rate: Optional[int]
) -> Tuple[np.ndarray, Optional[int]]:
    """确保音频数据与目标采样率一致。

    Args:
        audio_chunk: 原始音频数据。
        source_rate: 音频的实际采样率。
        target_rate: 需要输出的目标采样率；如果为 None 则保持原始采样率。

    Returns:
        Tuple[np.ndarray, Optional[int]]: 处理后的音频数据及其采样率。
    """
    if audio_chunk.size == 0:
        return audio_chunk, target_rate or source_rate

    if source_rate is None or source_rate <= 0:
        source_rate = target_rate

    if target_rate is None or target_rate <= 0 or source_rate == target_rate:
        return audio_chunk, source_rate

    duration = audio_chunk.shape[0] / float(source_rate)
    if duration == 0:
        return audio_chunk, target_rate

    target_length = max(1, int(round(duration * target_rate)))
    if target_length == audio_chunk.shape[0]:
        return audio_chunk, target_rate

    source_positions = np.linspace(0.0, duration, num=audio_chunk.shape[0], endpoint=False)
    target_positions = np.linspace(0.0, duration, num=target_length, endpoint=False)
    resampled = np.interp(target_positions, source_positions, audio_chunk).astype(np.float32)
    return resampled, target_rate


class SpeechEngine(ABC):
    """语音识别引擎抽象基类"""

    @abstractmethod
    def get_name(self) -> str:
        """
        获取引擎名称
        
        Returns:
            str: 引擎名称（如 'faster-whisper', 'openai', 'google'）
        """
        pass

    @abstractmethod
    def get_supported_languages(self) -> List[str]:
        """
        获取引擎支持的语言列表
        
        Returns:
            List[str]: 语言代码列表（如 ['zh', 'en', 'fr']）
        """
        pass

    @abstractmethod
    async def transcribe_file(self, audio_path: str, language: Optional[str] = None, **kwargs) -> Dict:
        """
        转录音频文件（批量转录）
        
        Args:
            audio_path: 音频文件路径
            language: 源语言代码（可选，None 表示自动检测）
            **kwargs: 引擎特定的额外参数
            
        Returns:
            Dict: 转录结果，格式为：
            {
                "segments": [
                    {
                        "start": float,  # 开始时间（秒）
                        "end": float,    # 结束时间（秒）
                        "text": str      # 转录文本
                    },
                    ...
                ],
                "language": str,  # 检测到的语言代码
                "duration": float  # 音频总时长（秒）
            }
        """
        pass

    @abstractmethod
    async def transcribe_stream(
        self,
        audio_chunk: np.ndarray,
        language: Optional[str] = None,
        **kwargs
    ) -> str:
        """
        转录音频流（实时转录）

        Args:
            audio_chunk: 音频数据块（numpy array）
            language: 源语言代码（可选）
            **kwargs: 引擎特定的额外参数（如 sample_rate）

        Returns:
            str: 转录文本片段
        """
        pass

    @abstractmethod
    def get_config_schema(self) -> Dict:
        """
        获取引擎配置的 JSON Schema
        
        Returns:
            Dict: JSON Schema 定义，描述引擎所需的配置参数
        """
        pass

    def validate_config(self, config: Dict) -> bool:
        """
        验证配置是否有效
        
        Args:
            config: 配置字典
            
        Returns:
            bool: 配置是否有效
        """
        # 默认实现：基本验证
        schema = self.get_config_schema()
        required_fields = schema.get('required', [])
        
        for field in required_fields:
            if field not in config:
                return False
        
        return True
