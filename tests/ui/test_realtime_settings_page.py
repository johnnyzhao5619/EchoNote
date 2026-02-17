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
            "realtime.save_transcript": True,
            "realtime.create_calendar_event": False,
            "realtime.vad_threshold": 0.45,
            "realtime.silence_duration_ms": 1800,
            "realtime.min_audio_duration": 2.5,
        }

    def get_setting(self, key):
        return self._settings.get(key)

    def set_setting(self, key, value):
        self._settings[key] = value
        return True


def test_load_settings_populates_translation_engine(qapp, mock_i18n):
    settings_manager = _FakeSettingsManager()
    page = RealtimeSettingsPage(settings_manager, mock_i18n)
    page.load_settings()

    assert page.translation_combo.currentData() == "none"
    assert page.save_transcript_check.isChecked() is True
    assert page.create_calendar_event_check.isChecked() is False
    assert page.vad_threshold_spin.value() == 0.45
    assert page.silence_duration_spin.value() == 1800
    assert page.min_audio_duration_spin.value() == 2.5


def test_save_settings_persists_translation_engine(qapp, mock_i18n):
    settings_manager = _FakeSettingsManager()
    page = RealtimeSettingsPage(settings_manager, mock_i18n)

    index = page.translation_combo.findData("google")
    assert index >= 0
    page.translation_combo.setCurrentIndex(index)
    page.save_transcript_check.setChecked(False)
    page.create_calendar_event_check.setChecked(True)
    page.vad_threshold_spin.setValue(0.6)
    page.silence_duration_spin.setValue(2500)
    page.min_audio_duration_spin.setValue(4.2)

    page.save_settings()

    assert settings_manager.get_setting("realtime.translation_engine") == "google"
    assert settings_manager.get_setting("realtime.save_transcript") is False
    assert settings_manager.get_setting("realtime.create_calendar_event") is True
    assert settings_manager.get_setting("realtime.vad_threshold") == 0.6
    assert settings_manager.get_setting("realtime.silence_duration_ms") == 2500
    assert settings_manager.get_setting("realtime.min_audio_duration") == 4.2
