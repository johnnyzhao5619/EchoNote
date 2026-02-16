# SPDX-License-Identifier: Apache-2.0
"""Tests for realtime settings page behavior."""

from ui.settings.realtime_page import RealtimeSettingsPage


class _FakeSettingsManager:
    def __init__(self):
        self._settings = {
            "realtime.default_input_source": "default",
            "realtime.default_gain": 1.0,
            "realtime.recording_format": "wav",
            "realtime.recording_save_path": "~/Documents/EchoNote/Recordings",
            "realtime.auto_save": True,
            "realtime.translation_engine": "none",
        }

    def get_setting(self, key):
        return self._settings.get(key)

    def set_setting(self, key, value):
        self._settings[key] = value


def test_load_settings_populates_translation_engine(qapp, mock_i18n):
    settings_manager = _FakeSettingsManager()
    page = RealtimeSettingsPage(settings_manager, mock_i18n)
    page.load_settings()

    assert page.translation_combo.currentData() == "none"


def test_save_settings_persists_translation_engine(qapp, mock_i18n):
    settings_manager = _FakeSettingsManager()
    page = RealtimeSettingsPage(settings_manager, mock_i18n)

    index = page.translation_combo.findData("google")
    assert index >= 0
    page.translation_combo.setCurrentIndex(index)

    page.save_settings()

    assert settings_manager.get_setting("realtime.translation_engine") == "google"
