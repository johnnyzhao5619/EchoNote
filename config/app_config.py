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
Configuration management for EchoNote application.

Handles loading, validation, and saving of application configuration.
"""

import copy
import json
import logging
from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType
from typing import Any, Dict

from utils.i18n import get_translation_codes

from .__version__ import get_version

APP_DIR_NAME = ".echonote"


def get_app_dir() -> Path:
    """Return the root directory for EchoNote user data."""
    return Path.home() / APP_DIR_NAME


logger = logging.getLogger(__name__)


class ConfigManager:
    """Manages application configuration with validation and persistence."""

    def __init__(self, i18n_manager=None):
        """Initialize the configuration manager."""
        self.default_config_path = Path(__file__).parent / "default_config.json"
        self.user_config_dir = get_app_dir()
        self.user_config_path = self.user_config_dir / "app_config.json"
        self._config: Dict[str, Any] = {}
        self._default_config: Dict[str, Any] = {}
        self._i18n_manager = i18n_manager
        self._load_config()

    def _load_config(self) -> None:
        """Load configuration from user config or default config."""
        try:
            logger.info(f"Loading default configuration from {self.default_config_path}")
            with open(self.default_config_path, "r", encoding="utf-8") as f:
                self._default_config = json.load(f)

            user_config: Dict[str, Any] = {}
            if self.user_config_path.exists():
                logger.info(f"Loading user configuration from {self.user_config_path}")
                with open(self.user_config_path, "r", encoding="utf-8") as f:
                    user_config = json.load(f)

            self._config = self._deep_merge(self._default_config, user_config)

            # Ensure version is always current from code, not config file
            self._config["version"] = get_version()

            # Validate the loaded configuration
            self._validate_config()
            logger.info("Configuration loaded and validated successfully")

        except FileNotFoundError as e:
            logger.error(f"Configuration file not found: {e}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in configuration file: {e}")
            raise
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            raise

    def _validate_config(self) -> None:
        """Validate required configuration fields and types."""
        required_fields = {
            "version": str,
            "database": dict,
            "transcription": dict,
            "realtime": dict,
            "calendar": dict,
            "timeline": dict,
            "resource_monitor": dict,
            "ui": dict,
            "security": dict,
        }

        for field, expected_type in required_fields.items():
            if field not in self._config:
                raise ValueError(f"Missing required configuration field: {field}")
            if not isinstance(self._config[field], expected_type):
                raise TypeError(
                    f"Configuration field '{field}' must be of type "
                    f"{expected_type.__name__}, got "
                    f"{type(self._config[field]).__name__}"
                )

        # Validate nested required fields
        self._validate_database_config()
        self._validate_transcription_config()
        self._validate_resource_monitor_config()
        self._validate_ui_config()

    def _validate_database_config(self) -> None:
        """Validate database configuration."""
        db_config = self._config["database"]
        if "path" not in db_config:
            raise ValueError("Missing required field: database.path")
        if "encryption_enabled" not in db_config:
            raise ValueError("Missing required field: database.encryption_enabled")

    def _validate_transcription_config(self) -> None:
        """Validate transcription configuration."""
        trans_config = self._config["transcription"]
        required = ["default_engine", "default_output_format", "max_concurrent_tasks"]
        for field in required:
            if field not in trans_config:
                raise ValueError(f"Missing required field: transcription.{field}")

        # Validate max_concurrent_tasks range
        max_concurrent = trans_config["max_concurrent_tasks"]
        if not isinstance(max_concurrent, int) or not (1 <= max_concurrent <= 5):
            raise ValueError(
                "transcription.max_concurrent_tasks must be an " "integer between 1 and 5"
            )

        if "max_retries" in trans_config:
            max_retries = trans_config["max_retries"]
            if not isinstance(max_retries, int) or max_retries < 0:
                raise ValueError("transcription.max_retries must be a non-negative integer")

        if "retry_delay" in trans_config:
            retry_delay = trans_config["retry_delay"]
            if not isinstance(retry_delay, (int, float)) or retry_delay < 0:
                raise ValueError("transcription.retry_delay must be a non-negative number")

        if "task_queue" in trans_config:
            task_queue_config = trans_config["task_queue"]
            if not isinstance(task_queue_config, dict):
                raise TypeError("transcription.task_queue must be a dictionary")

            if "max_concurrent_tasks" in task_queue_config:
                tq_concurrent = task_queue_config["max_concurrent_tasks"]
                if not isinstance(tq_concurrent, int) or not (1 <= tq_concurrent <= 5):
                    raise ValueError(
                        "transcription.task_queue.max_concurrent_tasks must be "
                        "an integer between 1 and 5"
                    )

            if "max_retries" in task_queue_config:
                tq_retries = task_queue_config["max_retries"]
                if not isinstance(tq_retries, int) or tq_retries < 0:
                    raise ValueError(
                        "transcription.task_queue.max_retries must be a " "non-negative integer"
                    )

            if "retry_delay" in task_queue_config:
                tq_retry_delay = task_queue_config["retry_delay"]
                if not isinstance(tq_retry_delay, (int, float)) or tq_retry_delay < 0:
                    raise ValueError(
                        "transcription.task_queue.retry_delay must be a " "non-negative number"
                    )

        # Validate faster_whisper configuration
        if "faster_whisper" in trans_config:
            fw_config = trans_config["faster_whisper"]

            # Validate model_size
            if "model_size" in fw_config:
                if not isinstance(fw_config["model_size"], str):
                    raise TypeError("transcription.faster_whisper.model_size must be a string")

                from core.models.registry import get_default_model_names

                valid_models = list(get_default_model_names())
                if fw_config["model_size"] not in valid_models:
                    raise ValueError(
                        f"transcription.faster_whisper.model_size must be one of {valid_models}"
                    )

            # Validate model_dir
            if "model_dir" in fw_config:
                if not isinstance(fw_config["model_dir"], str):
                    raise TypeError("transcription.faster_whisper.model_dir must be a string")

    def _validate_resource_monitor_config(self) -> None:
        """Validate resource monitor configuration."""
        monitor_config = self._config["resource_monitor"]

        for field in ("low_memory_mb", "high_cpu_percent"):
            if field not in monitor_config:
                raise ValueError(f"Missing required field: resource_monitor.{field}")

        low_memory_mb = monitor_config["low_memory_mb"]
        if isinstance(low_memory_mb, bool) or not isinstance(low_memory_mb, (int, float)):
            raise TypeError("resource_monitor.low_memory_mb must be a number")

        if not (64 <= float(low_memory_mb) <= 1048576):
            raise ValueError("resource_monitor.low_memory_mb must be between 64 and 1048576 MB")

        high_cpu_percent = monitor_config["high_cpu_percent"]
        if isinstance(high_cpu_percent, bool) or not isinstance(high_cpu_percent, (int, float)):
            raise TypeError("resource_monitor.high_cpu_percent must be a number")

        if not (1 <= float(high_cpu_percent) <= 100):
            raise ValueError("resource_monitor.high_cpu_percent must be between 1 and 100")

    def _validate_ui_config(self) -> None:
        """Validate UI configuration."""
        ui_config = self._config["ui"]
        if "theme" not in ui_config:
            raise ValueError("Missing required field: ui.theme")
        if "language" not in ui_config:
            raise ValueError("Missing required field: ui.language")

        # Validate theme value
        valid_themes = ["light", "dark", "system"]
        if ui_config["theme"] not in valid_themes:
            raise ValueError(f"ui.theme must be one of {valid_themes}")

        # Validate language value
        valid_languages = get_translation_codes()
        if not valid_languages:
            valid_languages = ["en_US"]
        if ui_config["language"] not in valid_languages:
            raise ValueError(f"ui.language must be one of {valid_languages}")

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value by key.

        Supports nested keys using dot notation (e.g., "database.path").

        Args:
            key: Configuration key (supports dot notation)
            default: Default value if key is not found

        Returns:
            Configuration value or default
        """
        keys = key.split(".")
        value = self._config

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    def set(self, key: str, value: Any) -> None:
        """
        Set a configuration value by key.

        Supports nested keys using dot notation (e.g., "database.path").

        Args:
            key: Configuration key (supports dot notation)
            value: Value to set
        """
        # Validate before setting
        if not self.validate_setting(key, value):
            raise ValueError(f"Invalid value for configuration key '{key}': {value}")

        keys = key.split(".")
        config = self._config

        # Navigate to the parent of the target key
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]

        # Set the value
        config[keys[-1]] = value

    def validate_setting(self, key: str, value: Any) -> bool:
        """
        Validate a specific configuration setting.

        Args:
            key: Setting key (dot notation)
            value: Value to validate

        Returns:
            True if valid, False otherwise
        """
        parts = key.split(".")
        if len(parts) < 2:
            # Top-level keys like 'version' are read-only or handled separately
            return True

        category = parts[0]
        setting = ".".join(parts[1:])

        try:
            if category == "transcription":
                return self._validate_transcription_setting(setting, value)
            elif category == "realtime":
                return self._validate_realtime_setting(setting, value)
            elif category == "calendar":
                return self._validate_calendar_setting(setting, value)
            elif category == "timeline":
                return self._validate_timeline_setting(setting, value)
            elif category == "resource_monitor":
                return self._validate_resource_monitor_setting(setting, value)
            elif category == "ui":
                return self._validate_ui_setting(setting, value)

            return True
        except Exception as e:
            logger.error(f"Validation error for {key}: {e}")
            return False

    def _validate_transcription_setting(self, setting: str, value: Any) -> bool:
        from config.constants import (
            SUPPORTED_TRANSCRIPTION_ENGINES,
            SUPPORTED_TRANSCRIPTION_FORMATS,
        )

        if setting == "default_output_format":
            return value in SUPPORTED_TRANSCRIPTION_FORMATS
        elif setting == "max_concurrent_tasks":
            return isinstance(value, int) and 1 <= value <= 5
        elif setting == "default_engine":
            return value in SUPPORTED_TRANSCRIPTION_ENGINES
        elif setting == "default_save_path":
            return isinstance(value, str) and len(value.strip()) > 0
        elif setting == "faster_whisper.model_size":
            from core.models.registry import get_default_model_names

            return isinstance(value, str) and value in get_default_model_names()
        elif setting == "faster_whisper.model_dir":
            return isinstance(value, str)
        # Task queue settings
        elif setting.startswith("task_queue."):
            sub = setting.split(".", 1)[1]
            if sub == "max_concurrent_tasks":
                return isinstance(value, int) and 1 <= value <= 5
            elif sub == "max_retries":
                return isinstance(value, int) and value >= 0
            elif sub == "retry_delay":
                return isinstance(value, (int, float)) and value >= 0
        return True

    def _validate_realtime_setting(self, setting: str, value: Any) -> bool:
        from config.constants import (
            SUPPORTED_REALTIME_TRANSLATION_ENGINES,
            SUPPORTED_RECORDING_FORMATS,
        )

        if setting == "recording_format":
            return value in SUPPORTED_RECORDING_FORMATS
        elif setting == "auto_save":
            return isinstance(value, bool)
        elif setting == "default_input_source":
            # 'default' or valid device ID (string)
            return isinstance(value, str)
        elif setting == "default_gain":
            # 0.1 to 10.0
            return isinstance(value, (int, float)) and 0.0 <= value <= 10.0
        elif setting == "translation_engine":
            return value in SUPPORTED_REALTIME_TRANSLATION_ENGINES
        elif setting in ("translation_source_lang", "translation_target_lang"):
            # "auto" or ISO 639-1/639-2 language code (non-empty string)
            return isinstance(value, str) and len(value.strip()) >= 2
        elif setting == "vad_threshold":
            return isinstance(value, (int, float)) and 0.0 <= value <= 1.0
        elif setting == "silence_duration_ms":
            return isinstance(value, int) and value >= 0
        elif setting == "min_audio_duration":
            return isinstance(value, (int, float)) and value >= 0
        elif setting == "save_transcript" or setting == "create_calendar_event":
            return isinstance(value, bool)
        elif setting in (
            "floating_window_enabled",
            "hide_main_window_when_floating",
            "floating_window_always_on_top",
        ):
            return isinstance(value, bool)
        elif setting == "recording_save_path":
            return isinstance(value, str)
        return True

    def _validate_calendar_setting(self, setting: str, value: Any) -> bool:
        if setting == "default_view":
            return value in ["month", "week", "day"]
        elif setting == "sync_interval_minutes":
            return isinstance(value, int) and value >= 1
        elif setting.startswith("colors."):
            return isinstance(value, str) and value.startswith("#") and len(value) == 7
        return True

    def _validate_timeline_setting(self, setting: str, value: Any) -> bool:
        from config.constants import (
            TIMELINE_REMINDER_MINUTES_OPTIONS,
            TIMELINE_STOP_CONFIRMATION_DELAY_MAX_MINUTES,
        )

        if setting in ["past_days", "future_days"]:
            return isinstance(value, int) and value >= 1
        elif setting == "reminder_minutes":
            return value in TIMELINE_REMINDER_MINUTES_OPTIONS
        elif setting == "page_size":
            return isinstance(value, int) and value >= 1
        elif setting == "auto_start_enabled":
            return isinstance(value, bool)
        elif setting == "auto_stop_grace_minutes":
            return isinstance(value, int) and value >= 0
        elif setting == "stop_confirmation_delay_minutes":
            return (
                isinstance(value, int)
                and 1 <= value <= TIMELINE_STOP_CONFIRMATION_DELAY_MAX_MINUTES
            )
        return True

    def _validate_resource_monitor_setting(self, setting: str, value: Any) -> bool:
        if setting == "low_memory_mb":
            return isinstance(value, (int, float)) and 64 <= float(value) <= 1048576
        elif setting == "high_cpu_percent":
            return isinstance(value, (int, float)) and 1 <= float(value) <= 100
        return True

    def _validate_ui_setting(self, setting: str, value: Any) -> bool:
        if setting == "theme":
            return value in ["light", "dark", "system"]
        elif setting == "language":
            valid = get_translation_codes() or ["en_US"]
            return value in valid
        return True

    def save(self) -> None:
        """Save the current configuration to the user config file."""
        try:
            # Ensure the user config directory exists
            self.user_config_dir.mkdir(parents=True, exist_ok=True)

            # Validate before saving
            self._validate_config()

            # Write configuration to file
            with open(self.user_config_path, "w", encoding="utf-8") as f:
                json.dump(self._config, f, indent=2, ensure_ascii=False)

            # Set secure file permissions (owner read/write only)
            import os

            try:
                os.chmod(self.user_config_path, 0o600)
                logger.debug("Set secure permissions for config file")
            except Exception as e:
                logger.warning(f"Could not set file permissions: {e}")

            logger.info(f"Configuration saved to {self.user_config_path}")

        except Exception as e:
            logger.error(f"Error saving configuration: {e}")
            raise

    def get_all(self) -> Dict[str, Any]:
        """
        Get the entire configuration dictionary.

        Returns:
            Complete configuration dictionary
        """
        return self._clone_value(self._config)

    def replace_all(self, config: Dict[str, Any]) -> None:
        """
        Replace in-memory configuration with a validated snapshot.

        Args:
            config: Full configuration snapshot
        """
        if not isinstance(config, dict):
            raise TypeError("config must be a dictionary")

        candidate = self._clone_value(config)
        candidate["version"] = get_version()

        previous = self._config
        self._config = candidate
        try:
            self._validate_config()
        except Exception:
            self._config = previous
            raise

    def reload(self) -> None:
        """Reload configuration from disk."""
        self._load_config()

    def get_defaults(self) -> Mapping[str, Any]:
        """Return an immutable view of the default configuration."""
        return self._deep_freeze(self._default_config)

    @classmethod
    def _deep_merge(cls, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively merge two dictionaries without mutating inputs."""
        result: Dict[str, Any] = {}

        for key, base_value in base.items():
            if key in override:
                override_value = override[key]
                if isinstance(base_value, dict) and isinstance(override_value, dict):
                    result[key] = cls._deep_merge(base_value, override_value)
                else:
                    result[key] = cls._clone_value(override_value)
            else:
                result[key] = cls._clone_value(base_value)

        for key, override_value in override.items():
            if key not in base:
                result[key] = cls._clone_value(override_value)

        return result

    @classmethod
    def _clone_value(cls, value: Any) -> Any:
        """Return a deep copy of supported container types."""
        if isinstance(value, dict):
            return {k: cls._clone_value(v) for k, v in value.items()}
        if isinstance(value, list):
            return [cls._clone_value(v) for v in value]
        return copy.deepcopy(value)

    @classmethod
    def _deep_freeze(cls, value: Any) -> Any:
        """Create an immutable representation of nested configuration data."""
        if isinstance(value, dict):
            frozen = {k: cls._deep_freeze(v) for k, v in value.items()}
            return MappingProxyType(frozen)
        if isinstance(value, list):
            return tuple(cls._deep_freeze(v) for v in value)
        return value

    def get_i18n_default_paths(self) -> Dict[str, str]:
        """
        Get internationalized default paths for user directories.

        Returns:
            Dict with localized default paths
        """
        if self._i18n_manager is None:
            # Fallback to English paths
            return {
                "transcripts": str(Path.home() / "Documents" / "EchoNote" / "Transcripts"),
                "recordings": str(Path.home() / "Documents" / "EchoNote" / "Recordings"),
            }

        # Get localized folder names
        documents_folder = self._i18n_manager.t("constants.folders.documents")
        transcripts_folder = self._i18n_manager.t(
            "constants.folders.transcripts", fallback="Transcripts"
        )
        recordings_folder = self._i18n_manager.t("constants.folders.recordings")

        base_path = Path.home() / documents_folder / "EchoNote"
        return {
            "transcripts": str(base_path / transcripts_folder),
            "recordings": str(base_path / recordings_folder),
        }

    def update_i18n_manager(self, i18n_manager) -> None:
        """
        Update the i18n manager reference.

        Args:
            i18n_manager: New i18n manager instance
        """
        self._i18n_manager = i18n_manager
