# SPDX-License-Identifier: Apache-2.0
"""
Unit tests for RealtimeRecorder.

Tests real-time recording lifecycle, audio processing, transcription,
translation, and marker functionality.
"""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

import numpy as np
import pytest

from core.realtime.recorder import RealtimeRecorder


class MockAudioCapture:
    """Mock audio capture for testing."""

    def __init__(self, sample_rate=16000):
        self.sample_rate = sample_rate
        self.is_capturing = False
        self.callback = None
        self.device_index = None

    def start_capture(self, device_index=None, callback=None):
        """Start audio capture."""
        self.is_capturing = True
        self.device_index = device_index
        self.callback = callback

    def stop_capture(self):
        """Stop audio capture."""
        self.is_capturing = False
        self.callback = None

    def get_input_devices(self):
        """Return mock input devices."""
        return []

    def simulate_audio_chunk(self, size=1600):
        """Simulate receiving an audio chunk."""
        if self.callback and self.is_capturing:
            audio_chunk = np.random.rand(size).astype(np.float32)
            self.callback(audio_chunk)


class MockSpeechEngine:
    """Mock speech engine for testing."""

    def __init__(self):
        self.transcribe_stream_calls = []
        self.transcribe_file_calls = []
        self.runtime_model_selection_calls = []
        self.model_manager = Mock()
        self.model_size = "base"

    async def transcribe_stream(self, audio_data, language=None, sample_rate=16000):
        """Mock stream transcription."""
        self.transcribe_stream_calls.append(
            {"audio_size": len(audio_data), "language": language, "sample_rate": sample_rate}
        )
        # Simulate transcription result
        return {"text": "Test transcription", "language": "en"}

    async def transcribe_file(self, file_path, language=None, progress_callback=None):
        """Mock file transcription."""
        self.transcribe_file_calls.append({"file_path": file_path, "language": language})
        return {"segments": [{"text": "Test", "start": 0.0, "end": 1.0}]}

    def is_model_available(self):
        """Check if model is available."""
        return True

    def _apply_runtime_model_selection(self, model_name, model_path=None):
        """Mock runtime model selection."""
        self.runtime_model_selection_calls.append(
            {"model_name": model_name, "model_path": model_path}
        )
        if model_name:
            self.model_size = model_name


class MockTranslationEngine:
    """Mock translation engine for testing."""

    def __init__(self):
        self.translate_calls = []

    async def translate(self, text, source_lang="auto", target_lang="en"):
        """Mock translation."""
        self.translate_calls.append(
            {"text": text, "source_lang": source_lang, "target_lang": target_lang}
        )
        return f"Translated: {text}"


@pytest.fixture
def mock_audio_capture():
    return MockAudioCapture()


@pytest.fixture
def mock_speech_engine():
    return MockSpeechEngine()


@pytest.fixture
def mock_translation_engine():
    return MockTranslationEngine()


@pytest.fixture
def mock_db():
    return Mock()


@pytest.fixture
def mock_file_manager():
    return Mock()


@pytest.fixture
def mock_session_archiver():
    with patch("core.realtime.recorder.SessionArchiver") as mock_cls:
        mock_instance = Mock()
        mock_instance.save_recording = AsyncMock(return_value="/path/to/recording.wav")
        mock_instance.save_text = AsyncMock(return_value="/path/to/transcript.txt")
        mock_instance.save_markers = AsyncMock(return_value="/path/to/markers.json")
        mock_cls.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_calendar_integration():
    with patch("core.realtime.recorder.CalendarIntegration") as mock_cls:
        mock_instance = Mock()
        mock_instance.create_event = AsyncMock(return_value="event_123")
        mock_cls.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def recorder(
    mock_audio_capture,
    mock_speech_engine,
    mock_translation_engine,
    mock_db,
    mock_file_manager,
    mock_session_archiver,
    mock_calendar_integration,
):
    return RealtimeRecorder(
        audio_capture=mock_audio_capture,
        speech_engine=mock_speech_engine,
        translation_engine=mock_translation_engine,
        db_connection=mock_db,
        file_manager=mock_file_manager,
    )


class TestRealtimeRecorderInitialization:
    def test_init_with_all_dependencies(self, recorder):
        assert recorder.audio_capture is not None
        assert recorder.speech_engine is not None
        assert recorder.translation_engine is not None
        assert recorder.db is not None
        assert recorder.session_archiver is not None
        assert recorder.calendar_integration is not None
        assert recorder.sample_rate == 16000
        assert not recorder.is_recording

    def test_init_sample_rate_from_capture(
        self, mock_speech_engine, mock_translation_engine, mock_db, mock_file_manager
    ):
        audio_capture = MockAudioCapture(sample_rate=44100)
        with (
            patch("core.realtime.recorder.SessionArchiver"),
            patch("core.realtime.recorder.CalendarIntegration"),
        ):
            recorder = RealtimeRecorder(
                audio_capture=audio_capture,
                speech_engine=mock_speech_engine,
                translation_engine=mock_translation_engine,
                db_connection=mock_db,
                file_manager=mock_file_manager,
            )
        assert recorder.sample_rate == 44100

    def test_set_callbacks(self, recorder):
        transcription_cb = Mock()
        translation_cb = Mock()
        error_cb = Mock()
        audio_cb = Mock()
        marker_cb = Mock()

        recorder.set_callbacks(
            on_transcription=transcription_cb,
            on_translation=translation_cb,
            on_error=error_cb,
            on_audio_data=audio_cb,
            on_marker=marker_cb,
        )

        assert recorder.on_transcription_update == transcription_cb
        assert recorder.on_translation_update == translation_cb
        assert recorder.on_error == error_cb
        assert recorder.on_audio_data == audio_cb
        assert recorder.on_marker_added == marker_cb


class TestRealtimeRecorderLifecycle:
    @pytest.mark.asyncio
    async def test_start_recording_basic(self, recorder, event_loop):
        await recorder.start_recording(event_loop=event_loop)
        assert recorder.is_recording
        assert recorder.recording_start_time is not None
        assert recorder.audio_capture.is_capturing
        assert recorder.processing_task is not None

    @pytest.mark.asyncio
    async def test_stop_recording_basic(self, recorder, event_loop):
        await recorder.start_recording(event_loop=event_loop)

        # Simulate some data
        recorder.accumulated_transcription.append("Test")
        recorder.recording_audio_buffer.append(np.zeros(10))

        result = await recorder.stop_recording()

        assert not recorder.is_recording
        assert not recorder.audio_capture.is_capturing
        assert "duration" in result

        recorder.session_archiver.save_recording.assert_called()
        recorder.session_archiver.save_text.assert_called()
        recorder.calendar_integration.create_event.assert_called()

    @pytest.mark.asyncio
    async def test_stop_recording_saves_files(self, recorder, event_loop):
        options = {"save_recording": True, "save_transcript": True, "create_calendar_event": True}
        await recorder.start_recording(options=options, event_loop=event_loop)

        recorder.recording_audio_buffer.append(np.zeros(10))
        recorder.accumulated_transcription.append("Test")

        result = await recorder.stop_recording()

        assert result["recording_path"] == "/path/to/recording.wav"
        assert result["transcript_path"] == "/path/to/transcript.txt"
        assert result["event_id"] == "event_123"

    @pytest.mark.asyncio
    async def test_stop_recording_respects_processing_timeout_config(self, recorder, event_loop):
        await recorder.start_recording(
            options={"enable_transcription": False, "save_recording": False},
            event_loop=event_loop,
        )
        recorder.config.processing_task_timeout = 0.01
        blocking_task = asyncio.create_task(asyncio.sleep(60))
        recorder.processing_task = blocking_task

        start = asyncio.get_running_loop().time()
        await recorder.stop_recording()
        elapsed = asyncio.get_running_loop().time() - start

        assert elapsed < 1.0
        assert blocking_task.cancelled()

    @pytest.mark.asyncio
    async def test_stop_recording_always_cleans_streaming_capture(self, recorder, event_loop):
        await recorder.start_recording(event_loop=event_loop)
        recorder.session_archiver.abort_recording_capture = Mock()
        recorder.recording_audio_buffer.append(np.zeros(10))

        await recorder.stop_recording()

        recorder.session_archiver.abort_recording_capture.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_recording_without_audio_capture(
        self, mock_speech_engine, mock_translation_engine, mock_db, mock_file_manager, event_loop
    ):
        """Test starting recording without audio capture raises error."""
        with (
            patch("core.realtime.recorder.SessionArchiver"),
            patch("core.realtime.recorder.CalendarIntegration"),
        ):
            recorder = RealtimeRecorder(
                audio_capture=None,
                speech_engine=mock_speech_engine,
                translation_engine=mock_translation_engine,
                db_connection=mock_db,
                file_manager=mock_file_manager,
            )

        with pytest.raises(RuntimeError, match="Audio capture is not available"):
            await recorder.start_recording(event_loop=event_loop)

    @pytest.mark.asyncio
    async def test_start_recording_applies_selected_model(
        self, recorder, mock_speech_engine, event_loop
    ):
        model_info = Mock()
        model_info.is_downloaded = True
        mock_speech_engine.model_manager.get_model = Mock(return_value=model_info)
        mock_speech_engine.model_size = "tiny"

        await recorder.start_recording(
            options={"model_name": "base", "model_path": "/tmp/models/base"},
            event_loop=event_loop,
        )

        assert mock_speech_engine.model_size == "base"
        assert mock_speech_engine.runtime_model_selection_calls[-1] == {
            "model_name": "base",
            "model_path": "/tmp/models/base",
        }
        await recorder.stop_recording()

    @pytest.mark.asyncio
    async def test_start_recording_with_transcription_disabled(self, recorder, event_loop):
        await recorder.start_recording(
            options={"enable_transcription": False, "enable_translation": True},
            event_loop=event_loop,
        )

        assert recorder.processing_task is None
        assert recorder.translation_task is None
        assert recorder.current_options["enable_translation"] is False

        await recorder.stop_recording()

    @pytest.mark.asyncio
    async def test_start_recording_tracks_loopback_input_metadata(self, recorder, event_loop):
        recorder.audio_capture.get_input_devices = Mock(
            return_value=[{"index": 4, "name": "BlackHole 2ch", "default_sample_rate": 48000}]
        )

        await recorder.start_recording(input_source=4, event_loop=event_loop)

        status = recorder.get_recording_status()
        assert status["input_source"] == 4
        assert status["input_device_name"] == "BlackHole 2ch"
        assert status["input_device_is_loopback"] is True
        assert status["input_device_is_system_audio"] is True
        assert status["input_device_scoped_app"] == ""

        await recorder.stop_recording()

    @pytest.mark.asyncio
    async def test_start_recording_tracks_meeting_audio_input_metadata(self, recorder, event_loop):
        recorder.audio_capture.get_input_devices = Mock(
            return_value=[
                {"index": 6, "name": "Microsoft Teams Audio", "default_sample_rate": 48000}
            ]
        )

        await recorder.start_recording(input_source=6, event_loop=event_loop)

        status = recorder.get_recording_status()
        assert status["input_source"] == 6
        assert status["input_device_name"] == "Microsoft Teams Audio"
        assert status["input_device_is_loopback"] is False
        assert status["input_device_is_system_audio"] is True
        assert status["input_device_scoped_app"] == "Microsoft Teams"

        await recorder.stop_recording()


class TestRealtimeRecorderAudioProcessing:
    def test_audio_callback(self, recorder):
        recorder.is_recording = True
        recorder._event_loop = asyncio.new_event_loop()
        recorder.transcription_queue = asyncio.Queue()

        audio_chunk = np.random.rand(1600).astype(np.float32)
        recorder._audio_callback(audio_chunk)

        assert len(recorder.recording_audio_buffer) == 1
        assert np.array_equal(recorder.recording_audio_buffer[0], audio_chunk)

    def test_audio_callback_skips_buffer_when_save_disabled(self, recorder):
        recorder.is_recording = True
        recorder._event_loop = asyncio.new_event_loop()
        recorder.transcription_queue = asyncio.Queue()
        recorder.current_options = {"save_recording": False}

        audio_chunk = np.random.rand(1600).astype(np.float32)
        recorder._audio_callback(audio_chunk)

        assert len(recorder.recording_audio_buffer) == 0

    def test_audio_callback_skips_transcription_queue_when_disabled(self, recorder):
        recorder.is_recording = True
        recorder._transcription_enabled = False
        recorder._event_loop = Mock()
        recorder.transcription_queue = asyncio.Queue()

        audio_chunk = np.random.rand(1600).astype(np.float32)
        recorder._audio_callback(audio_chunk)

        recorder._event_loop.call_soon_threadsafe.assert_not_called()

    def test_audio_callback_failover_stream_capture_on_append_failure(self, recorder):
        recorder.is_recording = True
        recorder._transcription_enabled = False
        recorder.current_options = {"save_recording": True}
        recorder._stream_recording_active = True
        recorder.session_archiver.append_recording_chunk = Mock(return_value=False)
        recorder.session_archiver.failover_recording_capture = Mock(return_value=True)
        recorder.session_archiver.abort_recording_capture = Mock()

        audio_chunk = np.random.rand(1600).astype(np.float32)
        recorder._audio_callback(audio_chunk)

        recorder.session_archiver.failover_recording_capture.assert_called_once()
        recorder.session_archiver.abort_recording_capture.assert_not_called()
        assert recorder._stream_recording_active is False
        assert len(recorder.recording_audio_buffer) == 1

    def test_audio_callback_abort_when_stream_failover_unavailable(self, recorder):
        recorder.is_recording = True
        recorder._transcription_enabled = False
        recorder.current_options = {"save_recording": True}
        recorder._stream_recording_active = True
        recorder.session_archiver.append_recording_chunk = Mock(return_value=False)
        recorder.session_archiver.failover_recording_capture = Mock(return_value=False)
        recorder.session_archiver.abort_recording_capture = Mock()

        audio_chunk = np.random.rand(1600).astype(np.float32)
        recorder._audio_callback(audio_chunk)

        recorder.session_archiver.failover_recording_capture.assert_called_once()
        recorder.session_archiver.abort_recording_capture.assert_called_once()
        assert recorder._stream_recording_active is False
        assert len(recorder.recording_audio_buffer) == 1


class TestRealtimeRecorderTranscription:
    @pytest.mark.asyncio
    async def test_transcription_callback(self, recorder, event_loop):
        results = []
        recorder.set_callbacks(on_transcription=lambda t: results.append(t))

        await recorder.start_recording(event_loop=event_loop)

        if recorder.on_transcription_update:
            recorder.on_transcription_update("Test")

        await recorder.stop_recording()
        assert results == ["Test"]

    @pytest.mark.asyncio
    async def test_accumulated_transcription(self, recorder, event_loop):
        """Test accumulated transcription storage."""
        await recorder.start_recording(event_loop=event_loop)

        # Manually add transcriptions
        recorder.accumulated_transcription.append("First line")
        recorder.accumulated_transcription.append("Second line")

        result = recorder.get_accumulated_transcription()

        assert result == "First line\nSecond line"
        await recorder.stop_recording()


class TestRealtimeRecorderTranslation:
    @pytest.mark.asyncio
    async def test_translation_flow(self, recorder, event_loop):
        options = {"enable_translation": True, "target_language": "fr"}
        await recorder.start_recording(options=options, event_loop=event_loop)

        assert recorder.translation_task is not None

        await recorder.stop_recording()


class TestRealtimeRecorderMarkers:
    @pytest.mark.asyncio
    async def test_add_marker(self, recorder, event_loop):
        await recorder.start_recording(event_loop=event_loop)

        marker = recorder.add_marker("Test Marker")
        assert marker["label"] == "Test Marker"
        assert marker["index"] == 1

        await recorder.stop_recording()

        recorder.session_archiver.save_markers.assert_called()


class TestRealtimeRecorderStatus:
    @pytest.mark.asyncio
    async def test_get_status(self, recorder, event_loop):
        await recorder.start_recording(event_loop=event_loop)
        status = recorder.get_recording_status()
        assert status["is_recording"]
        await recorder.stop_recording()


class TestRealtimeRecorderUtilities:
    """Test utility methods."""

    def test_is_duplicate_transcription_exact(self, recorder):
        """Test duplicate detection with exact match."""
        assert recorder._is_duplicate_transcription("Hello", "Hello")

    def test_is_duplicate_transcription_similar(self, recorder):
        """Test duplicate detection with similar text."""
        assert recorder._is_duplicate_transcription("Hello world", "Hello world!")

    def test_is_duplicate_transcription_different(self, recorder):
        """Test duplicate detection with different text."""
        assert not recorder._is_duplicate_transcription("Hello", "Goodbye")

    def test_is_duplicate_transcription_empty_last(self, recorder):
        """Test duplicate detection with empty last text."""
        assert not recorder._is_duplicate_transcription("Hello", "")

    def test_drain_queue(self, recorder):
        """Test queue draining."""
        queue = asyncio.Queue()
        queue.put_nowait("item1")
        queue.put_nowait("item2")

        # Mock event loop to use run_nowait or process simple tasks
        # But _drain_queue is sync? No, check implementation.
        # It's likely using `queue.get_nowait()` in a loop.

        # Wait, usually _drain_queue is a helper to empty a queue.
        # Check if it needs async loop running?
        # queue.put_nowait works without loop running if queue created.

        recorder._drain_queue(queue)

        assert queue.empty()

    def test_signal_stream_completion(self, recorder):
        """Test stream completion signaling."""
        queue = asyncio.Queue()

        recorder._signal_stream_completion(queue)

        assert not queue.empty()
        # Should contain sentinel which is usually None
        assert queue.get_nowait() is None
