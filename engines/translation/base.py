"""
翻译引擎抽象基类

定义所有翻译引擎必须实现的统一接口
"""

from abc import ABC, abstractmethod
from typing import List, Dict


class TranslationEngine(ABC):
    """翻译引擎抽象基类"""

    @abstractmethod
    def get_name(self) -> str:
        """
        获取引擎名称

        Returns:
            str: 引擎名称（如 'google-translate', 'deepl'）
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
    async def translate(
        self, text: str, source_lang: str, target_lang: str
    ) -> str:
        """
        翻译文本

        Args:
            text: 待翻译文本
            source_lang: 源语言代码（'auto' 表示自动检测）
            target_lang: 目标语言代码

        Returns:
            str: 翻译后的文本
        """
        pass

    def validate_language(self, lang_code: str) -> bool:
        """
        验证语言代码是否支持

        Args:
            lang_code: 语言代码

        Returns:
            bool: 是否支持
        """
        if lang_code == 'auto':
            return True

        supported = self.get_supported_languages()
        return lang_code in supported

    def get_config_schema(self) -> Dict:
        """
        获取引擎配置的 JSON Schema

        Returns:
            Dict: JSON Schema 定义
        """
        return {
            'type': 'object',
            'properties': {},
            'required': []
        }
