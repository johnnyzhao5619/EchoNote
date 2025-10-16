"""
语音引擎抽象基类

定义所有语音识别引擎必须实现的统一接口
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, AsyncIterator
import numpy as np


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
    async def transcribe_stream(self, audio_chunk: np.ndarray, language: Optional[str] = None, **kwargs) -> str:
        """
        转录音频流（实时转录）
        
        Args:
            audio_chunk: 音频数据块（numpy array，采样率 16kHz）
            language: 源语言代码（可选）
            **kwargs: 引擎特定的额外参数
            
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
