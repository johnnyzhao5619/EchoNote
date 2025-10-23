"""Abstract base class for translation engines.

Defines the unified interface and lifecycle hooks shared by all translation
engine implementations.
"""

import inspect
from abc import ABC, abstractmethod
from typing import List, Dict, Optional


class TranslationEngine(ABC):
    """Abstract base class for translation engines."""

    @abstractmethod
    def get_name(self) -> str:
        """Return the engine identifier (e.g., ``"google-translate"``)."""
        pass

    @abstractmethod
    def get_supported_languages(self) -> List[str]:
        """Return language codes supported by the engine."""
        pass

    @abstractmethod
    async def translate(
        self, text: str, source_lang: str, target_lang: str
    ) -> str:
        """Translate text from ``source_lang`` into ``target_lang``.

        Args:
            text: Input text to translate.
            source_lang: Source language code (``"auto"`` triggers detection).
            target_lang: Target language code.

        Returns:
            str: Translated text.
        """
        pass

    def validate_language(self, lang_code: str) -> bool:
        """Return ``True`` when the language code is supported."""
        if lang_code == 'auto':
            return True

        supported = self.get_supported_languages()
        return lang_code in supported

    def get_config_schema(self) -> Dict:
        """Return the JSON schema that describes engine configuration."""
        return {
            'type': 'object',
            'properties': {},
            'required': []
        }

    def close(self) -> Optional[object]:
        """Release engine resources synchronously (optional).

        Subclasses may override this method to perform cleanup or return an
        awaitable for asynchronous finalization.
        Returns:
            Optional[object]: Awaitable cleanup task or ``None``.
        """
        return None

    async def aclose(self) -> None:
        """Asynchronously release engine resources (optional).

        The default implementation delegates to :meth:`close` and awaits the
        result when necessary.
        """
        result = self.close()
        if inspect.isawaitable(result):
            await result
