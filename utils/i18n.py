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
Internationalization (i18n) support for EchoNote application.

Provides translation management and language switching capabilities with
enhanced support for complex dynamic strings, conditional text, and
performance optimization.
"""

import json
import logging
import re
from pathlib import Path
from string import Template
from typing import Any, Dict, List, Union

try:
    from PySide6.QtCore import QObject, Signal

    QT_AVAILABLE = True
except ImportError:
    QT_AVAILABLE = False

logger = logging.getLogger(__name__)

# Constants for i18n system
NESTED_VALUE_CACHE_SIZE = 128
PARAMETER_PATTERN = r"\{(\w+)\}"
CONDITIONAL_PATTERN = r"\{(\w+)\|([^|}]*)\|([^}]*)\}"
SPECIAL_PARAMETERS = {"condition", "fallback"}

# Shared language options used by translation-aware widgets across the UI.
# Each tuple contains the language code and the translation key for the
# human-readable label. This keeps language pickers consistent and avoids
# duplicating the option list in multiple widgets.
LANGUAGE_OPTION_KEYS = [
    ("zh", "realtime_record.available_languages.zh"),
    ("en", "realtime_record.available_languages.en"),
    ("fr", "realtime_record.available_languages.fr"),
    ("ja", "realtime_record.available_languages.ja"),
    ("ko", "realtime_record.available_languages.ko"),
]


class I18nManager:
    """Basic translation manager without Qt dependencies with enhanced dynamic string support."""

    def __init__(self, translations_dir: str = None, default_language: str = "en_US"):
        """
        Initialize the translation manager.

        Args:
            translations_dir: Directory containing translation files
            default_language: Default language code (en_US)
        """
        if translations_dir is None:
            translations_dir = Path(__file__).parent.parent / "resources" / "translations"
        else:
            translations_dir = Path(translations_dir)

        self.translations_dir = translations_dir
        self.current_language = default_language
        self.translations: Dict[str, Any] = {}
        self._template_cache: Dict[str, Template] = {}
        self._parameter_cache: Dict[str, List[str]] = {}
        self._load_translations(default_language)

    def _load_translations(self, language: str) -> None:
        """
        Load translations for the specified language.

        Args:
            language: Language code (en_US)
        """
        translation_file = self.translations_dir / f"{language}.json"

        try:
            with open(translation_file, "r", encoding="utf-8") as f:
                self.translations = json.load(f)
            logger.info(f"Loaded translations for language: {language}")
        except FileNotFoundError:
            logger.error(f"Translation file not found: {translation_file}")
            self.translations = {}
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in translation file {translation_file}: {e}")
            self.translations = {}

    def t(self, key: str, **kwargs) -> str:
        """
        Get translated string for the given key with enhanced dynamic string support.

        Supports nested keys using dot notation, parameter substitution, conditional text,
        and performance optimization through caching.

        Args:
            key: Translation key (supports dot notation, e.g., "ui.button")
            **kwargs: Parameters for string formatting, including special parameters:
                     - count: For plural forms (if supported)
                     - condition: For conditional text display
                     - fallback: Fallback text if key not found

        Returns:
            Translated string with parameters substituted
        """
        # Handle fallback parameter
        fallback = kwargs.pop("fallback", None)

        # Navigate nested keys
        keys = key.split(".")
        value = self.translations

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                logger.warning(
                    f"Translation key not found: {key} (language: {self.current_language})"
                )
                return fallback if fallback is not None else key

        # Ensure we have a string
        if not isinstance(value, str):
            logger.warning(f"Translation value is not a string: {key}")
            return fallback if fallback is not None else key

        # Handle conditional text
        if "condition" in kwargs:
            condition = kwargs.pop("condition")
            value = self._handle_conditional_text(value, condition, kwargs)

        # Handle plural forms (basic implementation)
        if "count" in kwargs:
            value = self._handle_plural_forms(key, value, kwargs["count"])

        # Cache parameter info if not already cached
        if key not in self._parameter_cache and "{" in value:
            parameters = self._extract_parameters(value)
            self._parameter_cache[key] = parameters

        # Substitute parameters with enhanced error handling
        try:
            return self._substitute_parameters(key, value, kwargs)
        except Exception as e:
            logger.warning(f"Error substituting parameters for key {key}: {e}")
            return fallback if fallback is not None else value

    def _substitute_parameters(self, key: str, value: str, params: Dict[str, Any]) -> str:
        """
        Substitute parameters in translation string with performance optimization.

        Args:
            key: Translation key for caching
            value: Translation string
            params: Parameters to substitute

        Returns:
            String with parameters substituted
        """
        # Check if string contains parameters
        if "{" not in value:
            return value

        # Use cached template if available
        if key in self._template_cache:
            template = self._template_cache[key]
            try:
                return template.safe_substitute(**params)
            except Exception as e:
                logger.warning(f"Template substitution error for key {key}: {e}")
                return value

        # Create and cache template for complex strings
        if self._has_complex_parameters(value):
            # Convert {param} to ${param} for Template class
            template_str = value.replace("{", "${").replace("}", "}")
            template = Template(template_str)
            self._template_cache[key] = template
            try:
                return template.safe_substitute(**params)
            except Exception as e:
                logger.warning(f"Template substitution error for key {key}: {e}")
                return value
        else:
            # Use simple format for basic parameters
            try:
                return value.format(**params)
            except KeyError as e:
                logger.warning(f"Missing parameter in translation: {e} for key {key}")
                return value
            except Exception as e:
                logger.warning(f"Format error for key {key}: {e}")
                return value

    def _extract_parameters(self, value: str) -> List[str]:
        """
        Extract parameter names from translation string.

        Args:
            value: Translation string

        Returns:
            List of parameter names
        """
        return re.findall(PARAMETER_PATTERN, value)

    def _has_complex_parameters(self, value: str) -> bool:
        """
        Check if string has complex parameter patterns that need template processing.

        Args:
            value: Translation string to check

        Returns:
            True if string has complex parameters
        """
        # Check for conditional patterns (most common complex case)
        if "|" in value and "{" in value:
            return True

        # Check for nested braces or format specifiers
        complex_patterns = [
            r"\{[^}]*\{[^}]*\}[^}]*\}",  # Nested braces
            r"\{[^}]*:[^}]*\}",  # Format specifiers
        ]

        return any(re.search(pattern, value) for pattern in complex_patterns)

    def _handle_conditional_text(self, value: str, condition: bool, params: Dict[str, Any]) -> str:
        """
        Handle conditional text display based on condition parameter.

        Args:
            value: Translation string that may contain conditional patterns
            condition: Boolean condition to evaluate
            params: Additional parameters

        Returns:
            String with conditional text resolved
        """
        # Pattern: {param_name|text_if_true|text_if_false}

        def replace_conditional(match):
            param_name = match.group(1)
            true_text = match.group(2)
            false_text = match.group(3)

            # Check if the parameter exists and is truthy
            param_value = params.get(param_name, False)
            if isinstance(param_value, bool):
                return true_text if param_value else false_text
            else:
                # For non-boolean values, check truthiness
                return true_text if param_value else false_text

        return re.sub(CONDITIONAL_PATTERN, replace_conditional, value)

    def _handle_plural_forms(self, key: str, value: str, count: Union[int, float]) -> str:
        """
        Handle basic plural forms based on count parameter.

        Args:
            key: Translation key
            value: Translation string
            count: Count for plural determination

        Returns:
            String with appropriate plural form
        """
        # For languages that need plural forms, check for plural variants
        plural_key = f"{key}_plural"
        if count != 1:
            # Try to find plural form in translations
            plural_keys = plural_key.split(".")
            plural_value = self.translations

            for k in plural_keys:
                if isinstance(plural_value, dict) and k in plural_value:
                    plural_value = plural_value[k]
                else:
                    plural_value = None
                    break

            if plural_value and isinstance(plural_value, str):
                return plural_value

        return value

    def validate_parameters(self, key: str, **kwargs) -> Dict[str, Any]:
        """
        Validate parameters for a translation key.

        Args:
            key: Translation key
            **kwargs: Parameters to validate

        Returns:
            Dictionary with validation results
        """
        # Get the translation value
        keys = key.split(".")
        value = self.translations

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return {"valid": False, "error": f"Key not found: {key}"}

        if not isinstance(value, str):
            return {"valid": False, "error": f"Value is not a string: {key}"}

        # Extract expected parameters from the translation string
        expected_params = set(self._extract_parameters(value))
        provided_params = set(kwargs.keys())

        # Special parameters that are handled by the i18n system
        special_params = SPECIAL_PARAMETERS.copy()

        # Count is a special parameter but it's also a valid translation parameter
        # Don't remove it from validation unless it's not in the expected params
        if "count" in provided_params and "count" not in expected_params:
            provided_params.remove("count")

        # Remove other special parameters from validation
        provided_params -= special_params

        missing_params = expected_params - provided_params
        extra_params = provided_params - expected_params

        result = {
            "valid": len(missing_params) == 0,
            "expected_parameters": list(expected_params),
            "provided_parameters": list(provided_params),
            "missing_parameters": list(missing_params),
            "extra_parameters": list(extra_params),
        }

        return result

    def get_parameter_info(self, key: str) -> Dict[str, Any]:
        """
        Get information about parameters expected by a translation key.

        Args:
            key: Translation key

        Returns:
            Dictionary with parameter information
        """
        if key in self._parameter_cache:
            return {"parameters": self._parameter_cache[key]}

        # Get the translation value
        keys = key.split(".")
        value = self.translations

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return {"parameters": [], "error": f"Key not found: {key}"}

        if not isinstance(value, str):
            return {"parameters": [], "error": f"Value is not a string: {key}"}

        # Extract parameters and cache them
        parameters = self._extract_parameters(value)
        self._parameter_cache[key] = parameters

        return {"parameters": parameters}

    def change_language(self, language: str) -> None:
        """
        Change the current language and clear caches.

        Args:
            language: New language code (en_US)
        """
        if language == self.current_language:
            return

        self._load_translations(language)
        self.current_language = language

        # Clear caches when language changes
        self._template_cache.clear()
        self._parameter_cache.clear()

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

    def precompile_templates(self) -> None:
        """
        Precompile templates for all parameterized strings to improve performance.

        This method should be called during application initialization for better
        runtime performance.
        """

        def _process_dict(data: Dict[str, Any], prefix: str = "") -> None:
            for key, value in data.items():
                full_key = f"{prefix}.{key}" if prefix else key

                if isinstance(value, dict):
                    _process_dict(value, full_key)
                elif isinstance(value, str) and "{" in value:
                    if self._has_complex_parameters(value):
                        template = Template(value.replace("{", "${").replace("}", "}"))
                        self._template_cache[full_key] = template

                    # Cache parameter info
                    parameters = self._extract_parameters(value)
                    if parameters:
                        self._parameter_cache[full_key] = parameters

        _process_dict(self.translations)
        logger.info(
            f"Precompiled {len(self._template_cache)} templates and "
            f"cached {len(self._parameter_cache)} parameter lists"
        )

    def clear_caches(self) -> None:
        """Clear all internal caches."""
        self._template_cache.clear()
        self._parameter_cache.clear()
        logger.debug("Cleared i18n caches")

    def get_cache_stats(self) -> Dict[str, int]:
        """
        Get statistics about cache usage.

        Returns:
            Dictionary with cache statistics
        """
        return {
            "template_cache_size": len(self._template_cache),
            "parameter_cache_size": len(self._parameter_cache),
        }


if QT_AVAILABLE:

    class I18nQtManager(QObject, I18nManager):
        """Translation manager with Qt Signal support."""

        language_changed = Signal(str)

        def __init__(self, translations_dir: str = None, default_language: str = "en_US"):
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
            Change the current language, clear caches, and emit signal.

            Args:
                language: New language code (en_US)
            """
            if language == self.current_language:
                return

            I18nManager.change_language(self, language)
            self.language_changed.emit(language)

else:
    # If Qt is not available, use the basic manager
    I18nQtManager = I18nManager  # type: ignore
