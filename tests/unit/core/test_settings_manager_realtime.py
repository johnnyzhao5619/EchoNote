# SPDX-License-Identifier: Apache-2.0
"""Tests for realtime settings behavior in SettingsManager."""

from typing import Any
from core.settings.manager import SettingsManager


class _FakeConfigManager:
    def __init__(self):
        self._defaults = {
            "realtime": {
                "recording_format": "wav",
                "auto_save": True,
                "default_input_source": "default",
                "default_gain": 1.0,
                "translation_engine": "google",
                "vad_threshold": 0.5,
                "silence_duration_ms": 2000,
                "min_audio_duration": 3.0,
                "save_transcript": True,
                "create_calendar_event": True,
            }
        }
        self._settings = {
            "realtime": {
                "translation_engine": "none",
                "default_gain": 1.5,
            }
        }

    def get_defaults(self):
        return self._defaults

    def get(self, key, default=None):
        # Support dot notation for deep access if necessary,
        # but primarily support top-level keys like "realtime"
        if "." in key:
            parts = key.split(".")
            current = self._settings
            for part in parts:
                if isinstance(current, dict) and part in current:
                    current = current[part]
                else:
                    return default
            return current
        return self._settings.get(key, default)

    def set(self, key, value):
        if "." in key:
            parts = key.split(".")
            current = self._settings
            for part in parts[:-1]:
                if part not in current:
                    current[part] = {}
                current = current[part]
            current[parts[-1]] = value
        else:
            self._settings[key] = value

    def validate_setting(self, key: str, value: Any) -> bool:
        # Simple mock validation logic
        if key == "realtime.translation_engine":
            return value in ["none", "google"]
        if key == "realtime.default_input_source":
            return value == "default"
        if key == "timeline.auto_start_enabled":
            return isinstance(value, bool)
        return True

    def get_all(self):
        return dict(self._settings)

    def save(self):
        return None

    def replace_all(self, snapshot):
        self._settings = snapshot


def test_get_realtime_preferences_includes_translation_engine():
    manager = SettingsManager(_FakeConfigManager())
    preferences = manager.get_realtime_preferences()

    assert preferences["translation_engine"] == "none"
    assert preferences["default_gain"] == 1.5


def test_validate_realtime_translation_engine_setting():
    manager = SettingsManager(_FakeConfigManager())

    assert manager.validate_setting("realtime.translation_engine", "none")
    assert manager.validate_setting("realtime.translation_engine", "google")
    assert not manager.validate_setting("realtime.translation_engine", "azure")


def test_validate_realtime_default_input_source_setting():
    manager = SettingsManager(_FakeConfigManager())

    assert manager.validate_setting("realtime.default_input_source", "default")
    assert not manager.validate_setting("realtime.default_input_source", "system")


def test_validate_timeline_auto_start_enabled_setting():
    manager = SettingsManager(_FakeConfigManager())

    assert manager.validate_setting("timeline.auto_start_enabled", True)
    assert not manager.validate_setting("timeline.auto_start_enabled", "true")
