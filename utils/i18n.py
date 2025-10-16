"""
Internationalization (i18n) support for EchoNote application.

Provides translation management and language switching capabilities.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict

try:
    from PyQt6.QtCore import QObject, pyqtSignal
    QT_AVAILABLE = True
except ImportError:
    QT_AVAILABLE = False


logger = logging.getLogger(__name__)


class I18nManager:
    """Basic translation manager without Qt dependencies."""

    def __init__(self, translations_dir: str = None,
                 default_language: str = "zh_CN"):
        """
        Initialize the translation manager.

        Args:
            translations_dir: Directory containing translation files
            default_language: Default language code (zh_CN, en_US, fr_FR)
        """
        if translations_dir is None:
            translations_dir = (
                Path(__file__).parent.parent / "resources" / "translations"
            )
        else:
            translations_dir = Path(translations_dir)

        self.translations_dir = translations_dir
        self.current_language = default_language
        self.translations: Dict[str, Any] = {}
        self._load_translations(default_language)

    def _load_translations(self, language: str) -> None:
        """
        Load translations for the specified language.

        Args:
            language: Language code (zh_CN, en_US, fr_FR)
        """
        translation_file = self.translations_dir / f"{language}.json"

        try:
            with open(translation_file, 'r', encoding='utf-8') as f:
                self.translations = json.load(f)
            logger.info(f"Loaded translations for language: {language}")
        except FileNotFoundError:
            logger.error(
                f"Translation file not found: {translation_file}"
            )
            self.translations = {}
        except json.JSONDecodeError as e:
            logger.error(
                f"Invalid JSON in translation file {translation_file}: {e}"
            )
            self.translations = {}

    def t(self, key: str, **kwargs) -> str:
        """
        Get translated string for the given key.

        Supports nested keys using dot notation and parameter substitution.

        Args:
            key: Translation key (supports dot notation, e.g., "ui.button")
            **kwargs: Parameters for string formatting

        Returns:
            Translated string with parameters substituted
        """
        # Navigate nested keys
        keys = key.split('.')
        value = self.translations

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                logger.warning(
                    f"Translation key not found: {key} "
                    f"(language: {self.current_language})"
                )
                return key

        # Ensure we have a string
        if not isinstance(value, str):
            logger.warning(
                f"Translation value is not a string: {key}"
            )
            return key

        # Substitute parameters
        try:
            return value.format(**kwargs)
        except KeyError as e:
            logger.warning(
                f"Missing parameter in translation: {e} for key {key}"
            )
            return value

    def change_language(self, language: str) -> None:
        """
        Change the current language.

        Args:
            language: New language code (zh_CN, en_US, fr_FR)
        """
        if language == self.current_language:
            return

        self._load_translations(language)
        self.current_language = language
        logger.info(f"Language changed to: {language}")

    def get_available_languages(self) -> list:
        """
        Get list of available languages.

        Returns:
            List of language codes
        """
        languages = []
        for file in self.translations_dir.glob("*.json"):
            languages.append(file.stem)
        return sorted(languages)


if QT_AVAILABLE:
    class I18nQtManager(QObject, I18nManager):
        """Translation manager with Qt Signal support."""

        language_changed = pyqtSignal(str)

        def __init__(self, translations_dir: str = None,
                     default_language: str = "zh_CN"):
            """
            Initialize the Qt-enabled translation manager.

            Args:
                translations_dir: Directory containing translation files
                default_language: Default language code
            """
            QObject.__init__(self)
            I18nManager.__init__(self, translations_dir, default_language)

        def change_language(self, language: str) -> None:
            """
            Change the current language and emit signal.

            Args:
                language: New language code (zh_CN, en_US, fr_FR)
            """
            if language == self.current_language:
                return

            I18nManager.change_language(self, language)
            self.language_changed.emit(language)
else:
    # If Qt is not available, use the basic manager
    I18nQtManager = I18nManager  # type: ignore
