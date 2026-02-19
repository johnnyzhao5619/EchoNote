# SPDX-License-Identifier: Apache-2.0
"""
Tests for realtime record widget.
"""

from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from PySide6.QtCore import Qt

from ui.realtime_record.widget import RealtimeRecorderSignals, RealtimeRecordWidget


class TestRealtimeRecorderSignals:
    """Tests for RealtimeRecorderSignals."""

    def test_signals_creation(self, qapp):
        """Test signals can be created."""
        signals = RealtimeRecorderSignals()

        assert signals is not None
        assert hasattr(signals, "transcription_updated")
        assert hasattr(signals, "translation_updated")
        assert hasattr(signals, "error_occurred")
        assert hasattr(signals, "status_changed")
        assert hasattr(signals, "audio_data_available")
        assert hasattr(signals, "recording_started")
        assert hasattr(signals, "recording_stopped")
        assert hasattr(signals, "recording_succeeded")
        assert hasattr(signals, "marker_added")


class TestRealtimeRecordWidget:
    """Tests for RealtimeRecordWidget."""

    @pytest.fixture
    def widget(
        self, qapp, mock_realtime_recorder, mock_audio_capture, mock_i18n, mock_settings_manager
    ):
        """Create a realtime record widget for testing."""
        with patch("ui.realtime_record.widget.get_notification_manager"):
            widget = RealtimeRecordWidget(
                recorder=mock_realtime_recorder,
                audio_capture=mock_audio_capture,
                i18n_manager=mock_i18n,
                settings_manager=mock_settings_manager,
            )
        yield widget
        widget._cleanup_resources()

    def test_widget_creation(self, widget):
        """Test widget can be created."""
        assert widget is not None
        assert widget.recorder is not None
        assert widget.audio_capture is not None
        assert widget.i18n is not None

    def test_widget_has_signals(self, widget):
        """Test widget has signal wrapper."""
        assert hasattr(widget, "signals")
        assert isinstance(widget.signals, RealtimeRecorderSignals)

    def test_widget_has_markers_list(self, widget):
        """Test widget has markers list."""
        assert hasattr(widget, "_markers")
        assert isinstance(widget._markers, list)
        assert len(widget._markers) == 0

    def test_widget_has_pending_futures(self, widget):
        """Test widget has pending futures set."""
        assert hasattr(widget, "_pending_futures")
        assert isinstance(widget._pending_futures, set)

    def test_widget_has_text_buffers(self, widget):
        """Test widget has text buffers."""
        assert hasattr(widget, "_transcription_buffer")
        assert hasattr(widget, "_translation_buffer")
        assert isinstance(widget._transcription_buffer, list)
        assert isinstance(widget._translation_buffer, list)

    def test_widget_has_buffer_lock(self, widget):
        """Test widget has buffer lock for thread safety."""
        assert hasattr(widget, "_buffer_lock")

    def test_widget_has_recording_preferences(self, widget):
        """Test widget has recording preferences."""
        assert hasattr(widget, "_recording_format")
        assert hasattr(widget, "_auto_save_enabled")
        assert widget._recording_format in ["wav", "mp3", "flac"]
        assert isinstance(widget._auto_save_enabled, bool)

    def test_widget_has_status_timer(self, widget):
        """Test widget has status timer."""
        assert hasattr(widget, "status_timer")
        assert widget.status_timer is not None

    def test_header_buttons_expose_semantic_roles(self, widget):
        """Header action buttons should expose semantic style roles."""
        assert widget.add_marker_button.property("role") == "realtime-marker-action"
        assert widget.record_button.property("role") == "realtime-record-action"
        assert widget.record_button.property("recording") is False
        assert widget.duration_value_label.property("role") == "realtime-duration"
        assert widget.input_combo.property("role") == "realtime-field-control"
        assert widget.source_lang_combo.property("role") == "realtime-field-control"
        assert widget.target_lang_combo.property("role") == "realtime-field-control"

    def test_widget_has_async_loop(self, widget):
        """Test widget has async event loop."""
        assert hasattr(widget, "_async_loop")
        assert hasattr(widget, "_async_thread")

    def test_recorder_callbacks_set(self, widget, mock_realtime_recorder):
        """Test recorder callbacks are set."""
        mock_realtime_recorder.set_callbacks.assert_called_once()

    def test_language_change_connected(self, widget, mock_i18n):
        """Test language change signal is connected."""
        mock_i18n.language_changed.connect.assert_called()

    def test_audio_available_flag(self, widget):
        """Test audio available flag is set correctly."""
        assert widget._audio_available is True

    def test_cleanup_flags(self, widget):
        """Test cleanup flags are initialized."""
        assert widget._cleanup_in_progress is False
        assert widget._cleanup_done is False


class TestRealtimeRecordWidgetWithoutAudio:
    """Tests for RealtimeRecordWidget without audio capture."""

    @pytest.fixture
    def widget_no_audio(self, qapp, mock_realtime_recorder, mock_i18n):
        """Create a realtime record widget without audio capture."""
        with patch("ui.realtime_record.widget.get_notification_manager"):
            widget = RealtimeRecordWidget(
                recorder=mock_realtime_recorder, audio_capture=None, i18n_manager=mock_i18n
            )
        yield widget
        widget._cleanup_resources()

    def test_widget_without_audio_capture(self, widget_no_audio):
        """Test widget can be created without audio capture."""
        assert widget_no_audio is not None
        # Widget can be created without audio capture
        # The _audio_available flag is set based on audio_capture parameter


class TestRealtimeRecordWidgetCallbacks:
    """Tests for RealtimeRecordWidget callback methods."""

    @pytest.fixture
    def widget(self, qapp, mock_realtime_recorder, mock_audio_capture, mock_i18n):
        """Create a realtime record widget for testing."""
        with patch("ui.realtime_record.widget.get_notification_manager"):
            widget = RealtimeRecordWidget(
                recorder=mock_realtime_recorder,
                audio_capture=mock_audio_capture,
                i18n_manager=mock_i18n,
            )
        yield widget
        widget._cleanup_resources()

    def test_on_transcription_callback(self, widget):
        """Test transcription callback."""
        # Should not raise exception
        widget._on_transcription("Test transcription")

    def test_on_translation_callback(self, widget):
        """Test translation callback."""
        # Should not raise exception
        widget._on_translation("Test translation")

    def test_on_error_callback(self, widget):
        """Test error callback."""
        # Should not raise exception
        widget._on_error("Test error")

    def test_on_audio_data_callback(self, widget):
        """Test audio data callback."""
        import numpy as np

        audio_data = np.array([0.1, 0.2, 0.3])
        # Should not raise exception
        widget._on_audio_data(audio_data)

    def test_on_marker_callback(self, widget):
        """Test marker callback."""
        marker = {"timestamp": 1.0, "text": "Test marker"}
        # Should not raise exception
        widget._on_marker(marker)

    def test_reset_markers_ui_clears_recorder_markers(self, widget, mock_realtime_recorder):
        """Resetting markers should clear both UI and recorder state."""
        widget._markers = [{"index": 1, "offset": 1.2}]
        widget.markers_list.addItem("marker")

        widget._reset_markers_ui()

        assert widget._markers == []
        assert widget.markers_list.count() == 0
        mock_realtime_recorder.clear_markers.assert_called_once()

    def test_populate_input_devices_marks_loopback_candidates(self, widget):
        """Loopback devices should be tagged and tracked for routing hints."""
        widget.audio_capture.get_input_devices.return_value = [
            {"index": 1, "name": "MacBook Pro Microphone"},
            {"index": 2, "name": "BlackHole 2ch"},
        ]

        widget._populate_input_devices()

        assert widget.input_combo.count() == 2
        assert widget.input_combo.itemText(1).endswith("(Loopback)")
        assert 2 in widget._loopback_input_indices

    def test_populate_input_devices_marks_meeting_audio_candidates(self, widget):
        """Meeting virtual inputs should be tagged as system-audio routes."""
        widget.audio_capture.get_input_devices.return_value = [
            {"index": 1, "name": "MacBook Pro Microphone"},
            {"index": 3, "name": "Microsoft Teams Audio"},
        ]

        widget._populate_input_devices()

        assert widget.input_combo.count() == 2
        assert widget.input_combo.itemText(1).endswith("(System Audio)")
        assert 3 in widget._system_audio_input_indices

    def test_capture_plan_message_without_loopback(self, widget):
        """When no loopback device exists, guidance should include setup planning."""
        widget._loopback_input_indices = set()
        widget._input_devices_by_index = {
            1: {"index": 1, "name": "MacBook Pro Microphone"},
        }
        widget.input_combo.clear()
        widget.input_combo.addItem("MacBook Pro Microphone", 1)
        widget.input_combo.setCurrentIndex(0)

        widget._update_capture_plan_message()

        assert widget.capture_plan_label.text()
        assert "No loopback input detected" in widget.capture_plan_label.text()

    def test_capture_plan_message_for_scoped_system_audio(self, widget):
        """App-scoped system audio should explain capture scope clearly."""
        widget._loopback_input_indices = set()
        widget._system_audio_input_indices = {3}
        widget._input_devices_by_index = {
            3: {"index": 3, "name": "Microsoft Teams Audio"},
        }
        widget.input_combo.clear()
        widget.input_combo.addItem("Microsoft Teams Audio (System Audio)", 3)
        widget.input_combo.setCurrentIndex(0)

        widget._update_capture_plan_message()

        text = widget.capture_plan_label.text()
        assert text
        assert "Microsoft Teams" in text
        assert "playback only" in text

    @pytest.mark.asyncio
    async def test_start_recording_uses_selected_input_device(self, widget, mock_realtime_recorder):
        """Start recording should use the currently selected device index."""
        mock_realtime_recorder.start_recording = AsyncMock(return_value=None)

        widget.input_combo.clear()
        widget.input_combo.addItem("Mic A", 7)
        widget.input_combo.setCurrentIndex(0)

        start_request = widget._prepare_start_request()
        assert start_request is not None
        await widget._start_recording(start_request)

        mock_realtime_recorder.start_recording.assert_awaited_once()
        _, kwargs = mock_realtime_recorder.start_recording.call_args
        assert kwargs["input_source"] == 7
