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

from PySide6.QtCore import QObject, Signal

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
        realtime_defaults = self._default_config.get("realtime", {})
        preferences = {
            "recording_format": realtime_defaults.get("recording_format", "wav"),
            "auto_save": realtime_defaults.get("auto_save", True),
        }

        try:
            recording_format = self.get_setting("realtime.recording_format")
            if recording_format in ("wav", "mp3"):
                preferences["recording_format"] = recording_format
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to read realtime.recording_format: %s", exc, exc_info=True)

        try:
            auto_save = self.get_setting("realtime.auto_save")
            if auto_save is not None:
                preferences["auto_save"] = bool(auto_save)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to read realtime.auto_save: %s", exc, exc_info=True)

        return preferences

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
            # Validate the setting
            if not self.validate_setting(key, value):
                logger.error(f"Validation failed for setting '{key}' " f"with value: {value}")
                return False

            # Get old value for comparison
            old_value = self.get_setting(key)

            # Set the value
            self.config_manager.set(key, value)
            logger.info(f"Setting '{key}' changed from {old_value} to {value}")

            # Emit change signal if value actually changed
            if old_value != value:
                self.setting_changed.emit(key, value)

            return True

        except Exception as e:
            logger.error(f"Error setting '{key}': {e}")
            return False

    def get_all_settings(self) -> Dict[str, Any]:
        """
        Get all settings.

        Returns:
            Dictionary containing all settings
        """
        return self.config_manager.get_all()

    def save_settings(self) -> bool:
        """
        Save current settings to disk.

        Returns:
            True if settings were successfully saved, False otherwise
        """
        try:
            self.config_manager.save()
            logger.info("Settings saved successfully")
            return True
        except Exception as e:
            logger.error(f"Error saving settings: {e}")
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
        try:
            # Split key to get category and setting name
            parts = key.split(".")

            if len(parts) < 2:
                logger.warning(f"Invalid setting key format: {key}")
                return False

            category = parts[0]
            setting_name = ".".join(parts[1:])

            # Validate based on category
            if category == "transcription":
                return self._validate_transcription_setting(setting_name, value)
            elif category == "realtime":
                return self._validate_realtime_setting(setting_name, value)
            elif category == "calendar":
                return self._validate_calendar_setting(setting_name, value)
            elif category == "timeline":
                return self._validate_timeline_setting(setting_name, value)
            elif category == "ui":
                return self._validate_ui_setting(setting_name, value)
            else:
                # For unknown categories, perform basic type checking
                logger.warning(f"No specific validation for category: {category}")
                return True

        except Exception as e:
            logger.error(f"Error validating setting '{key}': {e}")
            return False

    def _validate_transcription_setting(self, setting_name: str, value: Any) -> bool:
        """Validate transcription settings."""
        if setting_name == "default_output_format":
            valid_formats = ["txt", "srt", "md"]
            if value not in valid_formats:
                logger.error(f"Invalid output format: {value}. " f"Must be one of {valid_formats}")
                return False

        elif setting_name == "max_concurrent_tasks":
            if not isinstance(value, int) or not (1 <= value <= 5):
                logger.error(
                    "max_concurrent_tasks must be an integer " f"between 1 and 5, got: {value}"
                )
                return False

        elif setting_name == "default_engine":
            valid_engines = ["faster-whisper", "openai", "google", "azure"]
            if value not in valid_engines:
                logger.error(f"Invalid engine: {value}. " f"Must be one of {valid_engines}")
                return False

        elif setting_name == "default_save_path":
            if not isinstance(value, str) or not value.strip():
                logger.error("default_save_path must be a non-empty string")
                return False

        return True

    def _validate_realtime_setting(self, setting_name: str, value: Any) -> bool:
        """Validate realtime recording settings."""
        if setting_name == "default_gain":
            if not isinstance(value, (int, float)) or not (0.1 <= value <= 2.0):
                logger.error("default_gain must be a number between 0.1 and 2.0, " f"got: {value}")
                return False

        elif setting_name == "recording_format":
            valid_formats = ["wav", "mp3"]
            if value not in valid_formats:
                logger.error(
                    f"Invalid recording format: {value}. " f"Must be one of {valid_formats}"
                )
                return False

        elif setting_name == "recording_save_path":
            if not isinstance(value, str) or not value.strip():
                logger.error("recording_save_path must be a non-empty string")
                return False

        elif setting_name == "vad_threshold":
            if not isinstance(value, (int, float)) or not (0.0 <= value <= 1.0):
                logger.error("vad_threshold must be a number between 0.0 and 1.0, " f"got: {value}")
                return False

        elif setting_name == "silence_duration_ms":
            if not isinstance(value, int) or value < 0:
                logger.error("silence_duration_ms must be a non-negative integer, " f"got: {value}")
                return False

        return True

    def _validate_calendar_setting(self, setting_name: str, value: Any) -> bool:
        """Validate calendar settings."""
        if setting_name == "default_view":
            valid_views = ["month", "week", "day"]
            if value not in valid_views:
                logger.error(f"Invalid calendar view: {value}. " f"Must be one of {valid_views}")
                return False

        elif setting_name == "sync_interval_minutes":
            if not isinstance(value, int) or value < 1:
                logger.error("sync_interval_minutes must be a positive integer, " f"got: {value}")
                return False

        elif setting_name.startswith("colors."):
            # Validate color hex code
            if not isinstance(value, str) or not value.startswith("#") or len(value) != 7:
                logger.error("Color must be a hex code (e.g., #2196F3), " f"got: {value}")
                return False

        return True

    def _validate_timeline_setting(self, setting_name: str, value: Any) -> bool:
        """Validate timeline settings."""
        if setting_name in ["past_days", "future_days"]:
            if not isinstance(value, int) or value < 1:
                logger.error(f"{setting_name} must be a positive integer, " f"got: {value}")
                return False

        elif setting_name == "reminder_minutes":
            valid_values = [5, 10, 15, 30]
            if value not in valid_values:
                logger.error(f"reminder_minutes must be one of {valid_values}, " f"got: {value}")
                return False

        elif setting_name == "page_size":
            if not isinstance(value, int) or value < 1:
                logger.error(f"page_size must be a positive integer, got: {value}")
                return False

        return True

    def _validate_ui_setting(self, setting_name: str, value: Any) -> bool:
        """Validate UI settings."""
        if setting_name == "theme":
            valid_themes = ["light", "dark", "system"]
            if value not in valid_themes:
                logger.error(f"Invalid theme: {value}. " f"Must be one of {valid_themes}")
                return False

        elif setting_name == "language":
            valid_languages = ["en_US"]
            if value not in valid_languages:
                logger.error(f"Invalid language: {value}. " f"Must be one of {valid_languages}")
                return False

        return True

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
