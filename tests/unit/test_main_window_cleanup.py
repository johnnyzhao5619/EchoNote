# SPDX-License-Identifier: Apache-2.0
"""Tests for main window cleanup behavior."""

from unittest.mock import Mock

from ui.main_window import MainWindow


def test_cleanup_uses_realtime_widget_cleanup_when_recording():
    """Main window cleanup should delegate recorder shutdown to realtime widget."""
    realtime_recorder = Mock()
    realtime_recorder.is_recording = True
    realtime_recorder.audio_capture = Mock()

    realtime_widget = Mock()
    realtime_widget._cleanup_resources = Mock()

    fake_window = Mock()
    fake_window.i18n = Mock()
    fake_window.i18n.t = Mock(side_effect=lambda key, **kwargs: key)
    fake_window.i18n.language_changed = Mock()
    fake_window.pages = {"realtime_record": realtime_widget}
    fake_window.managers = {"realtime_recorder": realtime_recorder}

    MainWindow._cleanup(fake_window)

    realtime_widget._cleanup_resources.assert_called_once()
    realtime_recorder.audio_capture.stop_capture.assert_not_called()


def test_on_api_keys_updated_reload_and_refresh_realtime_widget():
    """API key update should reload engines and refresh realtime widget availability."""
    realtime_recorder = Mock()
    realtime_recorder.reload_engine = Mock()

    realtime_widget = Mock()
    realtime_widget.refresh_engine_availability = Mock()

    fake_window = Mock()
    fake_window.i18n = Mock()
    fake_window.i18n.t = Mock(side_effect=lambda key, **kwargs: key)
    fake_window.managers = {
        "realtime_recorder": realtime_recorder,
    }
    fake_window.pages = {"realtime_record": realtime_widget}

    MainWindow._on_api_keys_updated(fake_window)

    realtime_recorder.reload_engine.assert_called_once()
    realtime_widget.refresh_engine_availability.assert_called_once()
