# SPDX-License-Identifier: Apache-2.0
"""Tests for realtime settings page behavior."""

from unittest.mock import Mock, patch

import pytest

from ui.settings.realtime_page import RealtimeSettingsPage

pytestmark = pytest.mark.ui


class _FakeSettingsManager:
    def __init__(self):
        self._settings = {
            "realtime.default_input_source": "default",
            "realtime.default_gain": 1.0,
            "realtime.recording_format": "wav",
            "realtime.recording_save_path": "~/Documents/EchoNote/Recordings",
            "realtime.auto_save": True,
            "realtime.floating_window_enabled": True,
            "realtime.hide_main_window_when_floating": False,
            "realtime.floating_window_always_on_top": True,
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


def test_load_settings_populates_realtime_controls(qapp, mock_i18n):
    settings_manager = _FakeSettingsManager()
    page = RealtimeSettingsPage(settings_manager, mock_i18n)
    page.load_settings()

    assert page.floating_window_check.isChecked() is True
    assert page.hide_main_window_check.isChecked() is False
    assert page.floating_window_always_on_top_check.isChecked() is True
    assert page.save_transcript_check.isChecked() is True
    assert page.create_calendar_event_check.isChecked() is False
    assert page.vad_threshold_spin.value() == 0.45
    assert page.silence_duration_spin.value() == 1800
    assert page.min_audio_duration_spin.value() == 2.5


def test_save_settings_persists_realtime_preferences(qapp, mock_i18n):
    settings_manager = _FakeSettingsManager()
    page = RealtimeSettingsPage(settings_manager, mock_i18n)

    page.floating_window_check.setChecked(True)
    page.hide_main_window_check.setChecked(True)
    page.floating_window_always_on_top_check.setChecked(False)
    page.save_transcript_check.setChecked(False)
    page.create_calendar_event_check.setChecked(True)
    page.vad_threshold_spin.setValue(0.6)
    page.silence_duration_spin.setValue(2500)
    page.min_audio_duration_spin.setValue(4.2)

    page.save_settings()

    assert settings_manager.get_setting("realtime.floating_window_enabled") is True
    assert settings_manager.get_setting("realtime.hide_main_window_when_floating") is True
    assert settings_manager.get_setting("realtime.floating_window_always_on_top") is False
    assert settings_manager.get_setting("realtime.save_transcript") is False
    assert settings_manager.get_setting("realtime.create_calendar_event") is True
    assert settings_manager.get_setting("realtime.vad_threshold") == 0.6
    assert settings_manager.get_setting("realtime.silence_duration_ms") == 2500
    assert settings_manager.get_setting("realtime.min_audio_duration") == 4.2



def test_loopback_status_updates_from_checker(qapp, mock_i18n):
    settings_manager = _FakeSettingsManager()
    page = RealtimeSettingsPage(settings_manager, mock_i18n)
    checker = Mock()
    checker.get_loopback_devices.return_value = [{"name": "BlackHole 2ch"}]

    with patch.object(page, "_get_loopback_checker", return_value=checker):
        page._refresh_loopback_status()

    assert page.loopback_status_text.text() == "settings.realtime.loopback_installed"
    assert page.loopback_status_text.property("state") == "available"
    assert page.loopback_info_label.text() == "settings.realtime.loopback_detected_devices"


def test_floating_toggle_disables_hide_main_option(qapp, mock_i18n):
    settings_manager = _FakeSettingsManager()
    page = RealtimeSettingsPage(settings_manager, mock_i18n)

    page.floating_window_check.setChecked(False)

    assert page.hide_main_window_check.isEnabled() is False
    assert page.hide_main_window_check.isChecked() is False


def test_loopback_guide_opens_dialog_and_refreshes_status(qapp, mock_i18n):
    settings_manager = _FakeSettingsManager()
    page = RealtimeSettingsPage(settings_manager, mock_i18n)
    checker = Mock()
    checker.get_installation_instructions.return_value = ("title", "instructions")
    checker.get_loopback_devices.return_value = []
    checker.is_loopback_available.return_value = False

    dialog = Mock()
    with (
        patch.object(page, "_get_loopback_checker", return_value=checker),
        patch(
            "ui.dialogs.loopback_install_dialog.LoopbackInstallDialog",
            return_value=dialog,
        ) as dialog_cls,
    ):
        page._on_show_loopback_guide()

    dialog_cls.assert_called_once()
    dialog.exec.assert_called_once()
    assert page.loopback_status_text.text() == "settings.realtime.loopback_not_installed"


def test_loopback_status_marks_driver_without_endpoint_as_not_ready(qapp, mock_i18n):
    settings_manager = _FakeSettingsManager()
    page = RealtimeSettingsPage(settings_manager, mock_i18n)
    checker = Mock()
    checker.get_loopback_devices.return_value = []
    checker.is_loopback_available.return_value = True

    with patch.object(page, "_get_loopback_checker", return_value=checker):
        page._refresh_loopback_status()

    assert page.loopback_status_text.text() == "settings.realtime.loopback_not_ready"
    assert page.loopback_status_text.property("state") == "missing"
    assert page.loopback_info_label.text() == "settings.realtime.loopback_restart_required_hint"
