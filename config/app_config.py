"""
Configuration management for EchoNote application.

Handles loading, validation, and saving of application configuration.
"""

import copy
import json
import logging
from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import Any, Dict


APP_DIR_NAME = ".echonote"


def get_app_dir() -> Path:
    """Return the root directory for EchoNote user data."""
    return Path.home() / APP_DIR_NAME


logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_default_config_version() -> str:
    """Return the application version defined in the default config."""
    default_config_path = Path(__file__).parent / "default_config.json"

    try:
        with open(default_config_path, "r", encoding="utf-8") as config_file:
            data = json.load(config_file)
    except FileNotFoundError:
        logger.error("Default configuration file not found: %s", default_config_path)
        return "0.0.0"
    except json.JSONDecodeError as exc:
        logger.error(
            "Invalid JSON in default configuration file %s: %s",
            default_config_path,
            exc
        )
        return "0.0.0"

    version = data.get("version")
    if isinstance(version, str) and version.strip():
        return version.strip()

    logger.warning(
        "Default configuration missing valid 'version'; falling back to 0.0.0"
    )
    return "0.0.0"


class ConfigManager:
    """Manages application configuration with validation and persistence."""

    def __init__(self):
        """Initialize the configuration manager."""
        self.default_config_path = (
            Path(__file__).parent / "default_config.json"
        )
        self.user_config_dir = get_app_dir()
        self.user_config_path = self.user_config_dir / "app_config.json"
        self._config: Dict[str, Any] = {}
        self._default_config: Dict[str, Any] = {}
        self._load_config()

    def _load_config(self) -> None:
        """Load configuration from user config or default config."""
        try:
            logger.info(
                f"Loading default configuration from "
                f"{self.default_config_path}"
            )
            with open(self.default_config_path, 'r', encoding='utf-8') as f:
                self._default_config = json.load(f)

            user_config: Dict[str, Any] = {}
            if self.user_config_path.exists():
                logger.info(
                    f"Loading user configuration from "
                    f"{self.user_config_path}"
                )
                with open(self.user_config_path, 'r', encoding='utf-8') as f:
                    user_config = json.load(f)

            self._config = self._deep_merge(self._default_config, user_config)

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
            "ui": dict,
            "security": dict
        }

        for field, expected_type in required_fields.items():
            if field not in self._config:
                raise ValueError(
                    f"Missing required configuration field: {field}"
                )
            if not isinstance(self._config[field], expected_type):
                raise TypeError(
                    f"Configuration field '{field}' must be of type "
                    f"{expected_type.__name__}, got "
                    f"{type(self._config[field]).__name__}"
                )

        # Validate nested required fields
        self._validate_database_config()
        self._validate_transcription_config()
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
        required = [
            "default_engine",
            "default_output_format",
            "max_concurrent_tasks"
        ]
        for field in required:
            if field not in trans_config:
                raise ValueError(
                    f"Missing required field: transcription.{field}"
                )

        # Validate max_concurrent_tasks range
        max_concurrent = trans_config["max_concurrent_tasks"]
        if (not isinstance(max_concurrent, int) or
                not (1 <= max_concurrent <= 5)):
            raise ValueError(
                "transcription.max_concurrent_tasks must be an "
                "integer between 1 and 5"
            )

        if "max_retries" in trans_config:
            max_retries = trans_config["max_retries"]
            if not isinstance(max_retries, int) or max_retries < 0:
                raise ValueError(
                    "transcription.max_retries must be a non-negative integer"
                )

        if "retry_delay" in trans_config:
            retry_delay = trans_config["retry_delay"]
            if not isinstance(retry_delay, (int, float)) or retry_delay < 0:
                raise ValueError(
                    "transcription.retry_delay must be a non-negative number"
                )

        if "task_queue" in trans_config:
            task_queue_config = trans_config["task_queue"]
            if not isinstance(task_queue_config, dict):
                raise TypeError("transcription.task_queue must be a dictionary")

            if "max_concurrent_tasks" in task_queue_config:
                tq_concurrent = task_queue_config["max_concurrent_tasks"]
                if (not isinstance(tq_concurrent, int) or
                        not (1 <= tq_concurrent <= 5)):
                    raise ValueError(
                        "transcription.task_queue.max_concurrent_tasks must be "
                        "an integer between 1 and 5"
                    )

            if "max_retries" in task_queue_config:
                tq_retries = task_queue_config["max_retries"]
                if not isinstance(tq_retries, int) or tq_retries < 0:
                    raise ValueError(
                        "transcription.task_queue.max_retries must be a "
                        "non-negative integer"
                    )

            if "retry_delay" in task_queue_config:
                tq_retry_delay = task_queue_config["retry_delay"]
                if (not isinstance(tq_retry_delay, (int, float)) or
                        tq_retry_delay < 0):
                    raise ValueError(
                        "transcription.task_queue.retry_delay must be a "
                        "non-negative number"
                    )
        
        # Validate faster_whisper configuration
        if "faster_whisper" in trans_config:
            fw_config = trans_config["faster_whisper"]
            
            # Validate model_dir
            if "model_dir" in fw_config:
                if not isinstance(fw_config["model_dir"], str):
                    raise TypeError(
                        "transcription.faster_whisper.model_dir must be a string"
                    )
            
            # Validate auto_download_recommended
            if "auto_download_recommended" in fw_config:
                if not isinstance(fw_config["auto_download_recommended"], bool):
                    raise TypeError(
                        "transcription.faster_whisper.auto_download_recommended "
                        "must be a boolean"
                    )
            
            # Validate default_model
            if "default_model" in fw_config:
                if not isinstance(fw_config["default_model"], str):
                    raise TypeError(
                        "transcription.faster_whisper.default_model must be a string"
                    )
                
                # Validate model name is in supported list
                valid_models = [
                    "tiny", "tiny.en", "base", "base.en",
                    "small", "small.en", "medium", "medium.en",
                    "large-v1", "large-v2", "large-v3"
                ]
                if fw_config["default_model"] not in valid_models:
                    raise ValueError(
                        f"transcription.faster_whisper.default_model must be "
                        f"one of {valid_models}"
                    )
    
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
        valid_languages = ["zh_CN", "en_US", "fr_FR"]
        if ui_config["language"] not in valid_languages:
            raise ValueError(
                f"ui.language must be one of {valid_languages}"
            )
    
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
        keys = key.split('.')
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
        keys = key.split('.')
        config = self._config

        # Navigate to the parent of the target key
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]

        # Set the value
        config[keys[-1]] = value
    
    def save(self) -> None:
        """Save the current configuration to the user config file."""
        try:
            # Ensure the user config directory exists
            self.user_config_dir.mkdir(parents=True, exist_ok=True)

            # Validate before saving
            self._validate_config()

            # Write configuration to file
            with open(self.user_config_path, 'w', encoding='utf-8') as f:
                json.dump(self._config, f, indent=2, ensure_ascii=False)
            
            # Set secure file permissions (owner read/write only)
            import os
            try:
                os.chmod(self.user_config_path, 0o600)
                logger.debug(f"Set secure permissions for config file")
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
