# SPDX-License-Identifier: Apache-2.0
"""
Tests for realtime record widget.
"""

from unittest.mock import MagicMock, Mock, patch

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
        # Cleanup: Stop the async loop
        try:
            if widget._async_loop and widget._async_loop.is_running():
                widget._async_loop.call_soon_threadsafe(widget._async_loop.stop)
                if widget._async_thread and widget._async_thread.is_alive():
                    widget._async_thread.join(timeout=1)
        except:
            pass

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
        # Cleanup
        try:
            if widget._async_loop and widget._async_loop.is_running():
                widget._async_loop.call_soon_threadsafe(widget._async_loop.stop)
                if widget._async_thread and widget._async_thread.is_alive():
                    widget._async_thread.join(timeout=1)
        except:
            pass

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
        # Cleanup
        try:
            if widget._async_loop and widget._async_loop.is_running():
                widget._async_loop.call_soon_threadsafe(widget._async_loop.stop)
                if widget._async_thread and widget._async_thread.is_alive():
                    widget._async_thread.join(timeout=1)
        except:
            pass

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
