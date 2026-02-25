# SPDX-License-Identifier: Apache-2.0
"""Tests for realtime settings behavior in SettingsManager."""

from typing import Any

from core.settings.manager import (
    SettingsManager,
    resolve_translation_languages_from_settings,
)


class _FakeConfigManager:
    def __init__(self):
        self._defaults = {
            "realtime": {
                "recording_format": "wav",
                "auto_save": True,
                "default_input_source": "default",
                "default_gain": 1.0,
                "floating_window_enabled": False,
                "hide_main_window_when_floating": False,
                "floating_window_always_on_top": True,
                "vad_threshold": 0.5,
                "silence_duration_ms": 2000,
                "min_audio_duration": 3.0,
                "save_transcript": True,
                "create_calendar_event": True,
            },
            "translation": {
                "translation_engine": "google",
                "translation_source_lang": "auto",
                "translation_target_lang": "en",
            },
        }
        self._settings = {
            "realtime": {
                "default_gain": 1.5,
                "floating_window_enabled": True,
            },
            "translation": {
                "translation_engine": "none",
            },
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
        if key == "translation.translation_engine":
            return value in ["none", "google"]
        if key == "realtime.default_input_source":
            return value == "default"
        if key == "timeline.auto_start_enabled":
            return isinstance(value, bool)
        if key == "timeline.auto_stop_grace_minutes":
            return isinstance(value, int) and value >= 0
        if key == "timeline.stop_confirmation_delay_minutes":
            return isinstance(value, int) and value >= 1
        return True

    def get_all(self):
        return dict(self._settings)

    def save(self):
        return None

    def replace_all(self, snapshot):
        self._settings = snapshot


def test_get_realtime_preferences_uses_realtime_defaults_only():
    manager = SettingsManager(_FakeConfigManager())
    preferences = manager.get_realtime_preferences()

    assert "translation_engine" not in preferences
    assert preferences["default_gain"] == 1.5
    assert preferences["floating_window_enabled"] is True
    assert preferences["floating_window_always_on_top"] is True


def test_get_translation_preferences_uses_unified_defaults():
    manager = SettingsManager(_FakeConfigManager())
    preferences = manager.get_translation_preferences()

    assert preferences["translation_engine"] == "none"
    assert preferences["translation_source_lang"] == "auto"
    assert preferences["translation_target_lang"] == "en"


def test_resolve_realtime_translation_languages_uses_runtime_overrides():
    manager = SettingsManager(_FakeConfigManager())

    resolved = manager.resolve_realtime_translation_languages(source_lang="zh", target_lang="fr")

    assert resolved["translation_source_lang"] == "zh"
    assert resolved["translation_target_lang"] == "fr"


def test_resolve_realtime_translation_languages_falls_back_to_settings_defaults():
    config = _FakeConfigManager()
    config.set("translation.translation_source_lang", "ja")
    config.set("translation.translation_target_lang", "ko")
    manager = SettingsManager(config)

    resolved = manager.resolve_realtime_translation_languages(source_lang="", target_lang=None)

    assert resolved["translation_source_lang"] == "ja"
    assert resolved["translation_target_lang"] == "ko"


def test_resolve_translation_languages_from_settings_handles_missing_manager():
    resolved = resolve_translation_languages_from_settings(None, target_lang="fr")

    assert resolved["translation_source_lang"] == "auto"
    assert resolved["translation_target_lang"] == "fr"


def test_validate_realtime_translation_engine_setting():
    manager = SettingsManager(_FakeConfigManager())

    assert manager.validate_setting("translation.translation_engine", "none")
    assert manager.validate_setting("translation.translation_engine", "google")
    assert not manager.validate_setting("translation.translation_engine", "azure")


def test_validate_realtime_default_input_source_setting():
    manager = SettingsManager(_FakeConfigManager())

    assert manager.validate_setting("realtime.default_input_source", "default")
    assert not manager.validate_setting("realtime.default_input_source", "system")


def test_validate_timeline_auto_start_enabled_setting():
    manager = SettingsManager(_FakeConfigManager())

    assert manager.validate_setting("timeline.auto_start_enabled", True)
    assert not manager.validate_setting("timeline.auto_start_enabled", "true")


def test_validate_timeline_auto_stop_grace_setting():
    manager = SettingsManager(_FakeConfigManager())

    assert manager.validate_setting("timeline.auto_stop_grace_minutes", 0)
    assert manager.validate_setting("timeline.auto_stop_grace_minutes", 15)
    assert not manager.validate_setting("timeline.auto_stop_grace_minutes", -1)
    assert not manager.validate_setting("timeline.auto_stop_grace_minutes", "15")


def test_validate_timeline_stop_confirmation_delay_setting():
    manager = SettingsManager(_FakeConfigManager())

    assert manager.validate_setting("timeline.stop_confirmation_delay_minutes", 1)
    assert manager.validate_setting("timeline.stop_confirmation_delay_minutes", 10)
    assert not manager.validate_setting("timeline.stop_confirmation_delay_minutes", 0)
    assert not manager.validate_setting("timeline.stop_confirmation_delay_minutes", "10")
