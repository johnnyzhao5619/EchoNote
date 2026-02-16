# SPDX-License-Identifier: Apache-2.0
"""Tests for realtime settings behavior in SettingsManager."""

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
            "realtime.translation_engine": "none",
            "realtime.default_gain": 1.5,
        }

    def get_defaults(self):
        return self._defaults

    def get(self, key, default=None):
        return self._settings.get(key, default)

    def set(self, key, value):
        self._settings[key] = value

    def get_all(self):
        return dict(self._settings)

    def save(self):
        return None


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
