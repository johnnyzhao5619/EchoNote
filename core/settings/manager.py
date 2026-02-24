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
Settings management for EchoNote application.

Provides a unified interface for managing application settings with validation,
change notifications, and persistence.
"""

import copy
import logging
from collections.abc import Mapping
from typing import Any, Dict, Optional

from core.qt_imports import QObject, Signal

from utils.i18n import get_translation_codes

logger = logging.getLogger(__name__)


class SettingsManager(QObject):
    """
    Manages application settings with validation and change notifications.

    Provides a high-level interface over ConfigManager with:
    - Setting validation
    - Change notifications via Qt signals
    - Default value management
    - Type checking
    """

    # Signal emitted when any setting changes
    setting_changed = Signal(str, object)  # (key, new_value)

    # Signal emitted when API keys are updated (for engine reloading)
    api_keys_updated = Signal()

    def __init__(self, config_manager):
        """
        Initialize the settings manager.

        Args:
            config_manager: ConfigManager instance for persistence
        """
        super().__init__()
        self.config_manager = config_manager
        self._default_config = self._load_defaults()
        logger.info("SettingsManager initialized")

    def _load_defaults(self) -> Dict[str, Any]:
        """
        Load default configuration values.

        Returns:
            Dictionary of default configuration values
        """
        defaults = self.config_manager.get_defaults()
        return self._clone_defaults(defaults)

    @staticmethod
    def _clone_defaults(value: Any) -> Any:
        """Return a deep, mutable copy of default configuration structures."""
        if isinstance(value, Mapping):
            return {
                key: SettingsManager._clone_defaults(sub_value) for key, sub_value in value.items()
            }
        if isinstance(value, tuple):
            return [SettingsManager._clone_defaults(item) for item in value]
        if isinstance(value, list):
            return [SettingsManager._clone_defaults(item) for item in value]
        return copy.deepcopy(value)

    def get_setting(self, key: str) -> Any:
        """
        Get a setting value by key.

        Supports nested keys using dot notation
        (e.g., "transcription.default_engine").

        Args:
            key: Setting key (supports dot notation)

        Returns:
            Setting value or None if not found
        """
        value = self.config_manager.get(key)
        logger.debug(f"Retrieved setting '{key}': {value}")
        return value

    def get_realtime_preferences(self) -> Dict[str, Any]:
        """Return realtime recording preferences with defaults applied."""
        # Get defaults from configuration schema
        realtime_defaults = self._default_config.get("realtime", {})

        from config.constants import (
            DEFAULT_TRANSLATION_TARGET_LANGUAGE,
            RECORDING_FORMAT_WAV,
            TRANSLATION_ENGINE_NONE,
            TRANSLATION_LANGUAGE_AUTO,
        )

        # Start with defaults
        preferences = {
            "recording_format": realtime_defaults.get("recording_format", RECORDING_FORMAT_WAV),
            "auto_save": realtime_defaults.get("auto_save", True),
            "default_input_source": realtime_defaults.get("default_input_source", "default"),
            "default_gain": realtime_defaults.get("default_gain", 1.0),
            "translation_engine": realtime_defaults.get(
                "translation_engine", TRANSLATION_ENGINE_NONE
            ),
            "translation_source_lang": realtime_defaults.get(
                "translation_source_lang", TRANSLATION_LANGUAGE_AUTO
            ),
            "translation_target_lang": realtime_defaults.get(
                "translation_target_lang", DEFAULT_TRANSLATION_TARGET_LANGUAGE
            ),
            "vad_threshold": realtime_defaults.get("vad_threshold", 0.5),
            "silence_duration_ms": realtime_defaults.get("silence_duration_ms", 2000),
            "min_audio_duration": realtime_defaults.get("min_audio_duration", 3.0),
            "save_transcript": realtime_defaults.get("save_transcript", True),
            "create_calendar_event": realtime_defaults.get("create_calendar_event", True),
            "floating_window_enabled": bool(
                realtime_defaults.get("floating_window_enabled", False)
            ),
            "hide_main_window_when_floating": bool(
                realtime_defaults.get("hide_main_window_when_floating", False)
            ),
            "floating_window_always_on_top": bool(
                realtime_defaults.get("floating_window_always_on_top", True)
            ),
        }

        # Override with current settings
        current_settings = self.config_manager.get("realtime", {})
        if current_settings:
            preferences.update(current_settings)

        return preferences

    def get_realtime_translation_preferences(self) -> Dict[str, Any]:
        """Return realtime translation preferences with defaults applied."""
        from config.constants import (
            DEFAULT_TRANSLATION_TARGET_LANGUAGE,
            TRANSLATION_ENGINE_NONE,
            TRANSLATION_LANGUAGE_AUTO,
        )

        preferences = self.get_realtime_preferences()
        return {
            "translation_engine": preferences.get("translation_engine", TRANSLATION_ENGINE_NONE),
            "translation_source_lang": preferences.get(
                "translation_source_lang", TRANSLATION_LANGUAGE_AUTO
            )
            or TRANSLATION_LANGUAGE_AUTO,
            "translation_target_lang": preferences.get(
                "translation_target_lang", DEFAULT_TRANSLATION_TARGET_LANGUAGE
            )
            or DEFAULT_TRANSLATION_TARGET_LANGUAGE,
            "floating_window_enabled": bool(preferences.get("floating_window_enabled", False)),
            "hide_main_window_when_floating": bool(
                preferences.get("hide_main_window_when_floating", False)
            ),
            "floating_window_always_on_top": bool(
                preferences.get("floating_window_always_on_top", True)
            ),
        }

    def set_setting(self, key: str, value: Any) -> bool:
        """
        Set a setting value with validation.

        Args:
            key: Setting key (supports dot notation)
            value: Value to set

        Returns:
            True if setting was successfully set, False otherwise
        """
        try:
            # Delegate validation to ConfigManager
            if not self.config_manager.validate_setting(key, value):
                logger.error(f"Validation failed for setting '{key}' with value: {value}")
                return False

            # Get old value for comparison
            old_value = self.get_setting(key)

            # Set the value (ConfigManager checks validation again, but that's safe)
            self.config_manager.set(key, value)
            logger.info(f"Setting '{key}' changed from {old_value} to {value}")

            # Emit change signal if value actually changed
            if old_value != value:
                self.setting_changed.emit(key, value)

            return True

        except Exception as e:
            logger.error(f"Error setting '{key}': {e}")
            return False

    def validate_setting(self, key: str, value: Any) -> bool:
        """
        Validate a setting value.

        Args:
            key: Setting key
            value: Value to validate

        Returns:
            True if value is valid, False otherwise
        """
        return self.config_manager.validate_setting(key, value)

    def reset_to_default(self, key: Optional[str] = None) -> bool:
        """
        Reset setting(s) to default values.

        Args:
            key: Setting key to reset, or None to reset all settings

        Returns:
            True if reset was successful, False otherwise
        """
        try:
            if key is None:
                # Reset all settings
                logger.info("Resetting all settings to defaults")
                for k, v in self._default_config.items():
                    self.config_manager.set(k, copy.deepcopy(v))
                # Signal all settings changed
                self.setting_changed.emit("*", None)
            else:
                # Reset specific setting
                default_value = self._get_default_value(key)
                if default_value is not None:
                    logger.info(f"Resetting setting '{key}' to " f"default: {default_value}")
                    self.config_manager.set(key, copy.deepcopy(default_value))
                    self.setting_changed.emit(key, default_value)
                else:
                    logger.warning(f"No default value found for setting: {key}")
                    return False

            return True

        except Exception as e:
            logger.error(f"Error resetting settings: {e}")
            return False

    def _get_default_value(self, key: str) -> Any:
        """
        Get the default value for a setting key.

        Args:
            key: Setting key (supports dot notation)

        Returns:
            Default value or None if not found
        """
        keys = key.split(".")
        value = self._default_config

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return None

        return copy.deepcopy(value)

    # Convenience methods for common settings

    def get_transcription_settings(self) -> Dict[str, Any]:
        """Get all transcription settings."""
        return self.config_manager.get("transcription", {})

    def get_realtime_settings(self) -> Dict[str, Any]:
        """Get all realtime recording settings."""
        return self.config_manager.get("realtime", {})

    def get_calendar_settings(self) -> Dict[str, Any]:
        """Get all calendar settings."""
        return self.config_manager.get("calendar", {})

    def get_timeline_settings(self) -> Dict[str, Any]:
        """Get all timeline settings."""
        return self.config_manager.get("timeline", {})

    def get_ui_settings(self) -> Dict[str, Any]:
        """Get all UI settings."""
        return self.config_manager.get("ui", {})

    def get_theme(self) -> str:
        """Get current theme."""
        return self.get_setting("ui.theme")

    def set_theme(self, theme: str) -> bool:
        """Set theme with validation."""
        return self.set_setting("ui.theme", theme)

    def get_language(self) -> str:
        """Get current language."""
        return self.get_setting("ui.language")

    def set_language(self, language: str) -> bool:
        """Set language with validation."""
        return self.set_setting("ui.language", language)
