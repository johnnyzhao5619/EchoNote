import asyncio
import json
import sys
import tempfile
import types
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


try:
    import numpy as np  # type: ignore
    HAS_NUMPY = True
except ImportError:  # pragma: no cover - fallback when numpy is unavailable
    from tests.unit.test_transcription_manager_failure import _ensure_numpy_stub  # type: ignore

    _ensure_numpy_stub()
    import numpy as np  # type: ignore
    HAS_NUMPY = hasattr(np, "array")


def _ensure_soundfile_stub():
    if "soundfile" in sys.modules:
        return

    soundfile_module = types.ModuleType("soundfile")

    def _write_stub(path, data, samplerate):  # noqa: ARG001
        return None

    soundfile_module.write = _write_stub  # type: ignore[attr-defined]
    sys.modules["soundfile"] = soundfile_module


_ensure_soundfile_stub()


class DummySpeechEngine:
    """Minimal speech engine stub used for availability tests."""

    def get_name(self) -> str:
        return "dummy"


class DummyFileManager:
    """File manager stub that stores data inside a temporary directory."""

    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = Path(base_dir or tempfile.gettempdir()) / "echonote-tests"
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.saved_files = {}
        self.saved_texts = {}

    def get_temp_path(self, filename: str) -> str:
        temp_dir = self.base_dir / "tmp"
        temp_dir.mkdir(parents=True, exist_ok=True)
        return str(temp_dir / filename)

    def save_file(self, data: bytes, filename: str, subdirectory: Optional[str] = None) -> str:
        target_dir = self.base_dir / (subdirectory or "misc")
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / filename
        with open(target_path, 'wb') as file:
            file.write(data)
        self.saved_files[filename] = str(target_path)
        return str(target_path)

    def save_text_file(self, content: str, filename: str, subdirectory: Optional[str] = None) -> str:
        target_dir = self.base_dir / (subdirectory or "text")
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / filename
        with open(target_path, 'w', encoding='utf-8') as file:
            file.write(content)
        self.saved_texts[filename] = str(target_path)
        return str(target_path)


class DummyStreamingSpeechEngine(DummySpeechEngine):
    """Speech engine stub that records streaming transcription inputs."""

    def __init__(self):
        self.calls = 0
        self.captured_audio = []
        self.received_sample_rates = []

    async def transcribe_stream(self, audio, language=None, sample_rate=None):  # noqa: ARG002
        self.calls += 1
        self.captured_audio.append(audio.copy())
        self.received_sample_rates.append(sample_rate)
        return f"transcription-{self.calls}"


class DummyAudioCapture:
    """Audio capture stub that directly exposes the recorder callback."""

    def __init__(self, sample_rate: int = 16000):
        self.sample_rate = sample_rate
        self.callback = None
        self.started = False

    def start_capture(self, device_index=None, callback=None):  # noqa: ARG002
        self.started = True
        self.callback = callback

    def stop_capture(self):
        self.started = False


def test_start_recording_without_audio_capture():
    from core.realtime.recorder import RealtimeRecorder

    recorder = RealtimeRecorder(
        audio_capture=None,
        speech_engine=DummySpeechEngine(),
        translation_engine=None,
        db_connection=None,
        file_manager=DummyFileManager(),
    )

    assert not recorder.audio_input_available()

    async def _start():
        await recorder.start_recording()

    with pytest.raises(RuntimeError) as excinfo:
        asyncio.run(_start())

    assert "Install PyAudio" in str(excinfo.value)
    assert recorder.is_recording is False


def test_stop_recording_without_start():
    from core.realtime.recorder import RealtimeRecorder

    recorder = RealtimeRecorder(
        audio_capture=None,
        speech_engine=DummySpeechEngine(),
        translation_engine=None,
        db_connection=None,
        file_manager=DummyFileManager(),
    )

    result = asyncio.run(recorder.stop_recording())
    assert result == {}


def test_audio_buffer_accumulates_and_clears(monkeypatch):
    if not HAS_NUMPY:
        pytest.skip("numpy is required for audio buffer tests")

    from core.realtime.recorder import RealtimeRecorder

    class _DummyVAD:
        def __init__(self, *args, **kwargs):  # noqa: D401, ARG002
            """Lightweight stub that always treats input as speech."""

        def detect_speech(self, audio, sample_rate):  # noqa: ARG002
            if len(audio) == 0:
                return []
            return [{'start': 0.0, 'end': len(audio) / sample_rate}]

        def extract_speech(self, audio, timestamps, sample_rate=16000):  # noqa: ARG002
            return audio

    monkeypatch.setattr("engines.audio.vad.VADDetector", _DummyVAD)

    async def _run_test():
        sample_rate = 16000
        audio_capture = DummyAudioCapture(sample_rate=sample_rate)
        speech_engine = DummyStreamingSpeechEngine()

        recorder = RealtimeRecorder(
            audio_capture=audio_capture,
            speech_engine=speech_engine,
            translation_engine=None,
            db_connection=None,
            file_manager=DummyFileManager(),
        )

        options = {
            'save_recording': False,
            'save_transcript': False,
            'create_calendar_event': False,
        }

        loop = asyncio.get_running_loop()
        await recorder.start_recording(options=options, event_loop=loop)

        assert recorder.audio_buffer is not None
        assert recorder.audio_buffer.sample_rate == sample_rate
        assert audio_capture.started
        assert audio_capture.callback is not None
        callback = audio_capture.callback

        chunk_samples = sample_rate  # 1 秒音频块
        chunk = np.full(chunk_samples, 0.01, dtype=np.float32)

        async def wait_for_transcriptions(expected_calls: int):
            async def _poll():
                while speech_engine.calls < expected_calls:
                    await asyncio.sleep(0.01)

            await asyncio.wait_for(_poll(), timeout=2.0)

        for _ in range(3):
            callback(chunk.copy())
            await asyncio.sleep(0.01)

        await wait_for_transcriptions(1)

        assert speech_engine.calls == 1
        assert recorder.audio_buffer.get_size() == 0

        expected_window = np.concatenate([chunk, chunk, chunk])
        first_audio = speech_engine.captured_audio[0]
        assert len(first_audio) == chunk_samples * 3
        np.testing.assert_allclose(first_audio, expected_window)

        for _ in range(3):
            callback(chunk.copy())
            await asyncio.sleep(0.01)

        await wait_for_transcriptions(2)

        assert speech_engine.calls == 2
        second_audio = speech_engine.captured_audio[1]
        assert len(second_audio) == chunk_samples * 3
        np.testing.assert_allclose(second_audio, expected_window)

        assert speech_engine.received_sample_rates == [sample_rate, sample_rate]

        await recorder.stop_recording()

        assert recorder.audio_buffer is None
        assert not audio_capture.started

    asyncio.run(_run_test())


def test_custom_sample_rate_propagates(monkeypatch, tmp_path):
    if not HAS_NUMPY:
        pytest.skip("numpy is required for audio buffer tests")

    from core.realtime.recorder import RealtimeRecorder

    recorded_rates: list[int] = []

    def _fake_write(path, data, samplerate):  # noqa: ANN001
        recorded_rates.append(samplerate)
        tmp_path_local = Path(path)
        tmp_path_local.parent.mkdir(parents=True, exist_ok=True)
        tmp_path_local.write_bytes(b"\x00\x00")

    monkeypatch.setattr("soundfile.write", _fake_write)

    sample_rate = 22050
    audio_capture = DummyAudioCapture(sample_rate=16000)
    speech_engine = DummyStreamingSpeechEngine()
    file_manager = DummyFileManager(base_dir=tmp_path)

    recorder = RealtimeRecorder(
        audio_capture=audio_capture,
        speech_engine=speech_engine,
        translation_engine=None,
        db_connection=None,
        file_manager=file_manager,
    )

    options = {
        'sample_rate': sample_rate,
        'save_recording': True,
        'save_transcript': False,
        'create_calendar_event': False,
        'enable_translation': False,
    }

    async def _run_custom_test():
        loop = asyncio.get_running_loop()
        await recorder.start_recording(options=options, event_loop=loop)

        assert recorder.sample_rate == sample_rate
        assert audio_capture.sample_rate == sample_rate
        assert recorder.audio_buffer is not None
        assert recorder.audio_buffer.sample_rate == sample_rate
        assert audio_capture.callback is not None

        callback = audio_capture.callback
        chunk = np.full(sample_rate, 0.02, dtype=np.float32)

        async def _wait_for(expected_calls: int):
            async def _poll():
                while speech_engine.calls < expected_calls:
                    await asyncio.sleep(0.01)

            await asyncio.wait_for(_poll(), timeout=2.0)

        for _ in range(3):
            callback(chunk.copy())
            await asyncio.sleep(0.01)

        await _wait_for(1)

        assert speech_engine.received_sample_rates == [sample_rate]

        await recorder.stop_recording()

    asyncio.run(_run_custom_test())

    assert recorded_rates
    assert recorded_rates[-1] == sample_rate


def test_add_marker_requires_active_recording():
    from core.realtime.recorder import RealtimeRecorder

    recorder = RealtimeRecorder(
        audio_capture=None,
        speech_engine=DummySpeechEngine(),
        translation_engine=None,
        db_connection=None,
        file_manager=DummyFileManager(),
    )

    assert recorder.add_marker() is None
    assert recorder.get_markers() == []


def test_markers_persist_and_save(monkeypatch, tmp_path):
    if not HAS_NUMPY:
        pytest.skip("numpy is required for marker persistence tests")

    from core.realtime.recorder import RealtimeRecorder

    class _DummyVAD:
        def __init__(self, *args, **kwargs):  # noqa: D401, ARG002
            """Stub VAD that treats all audio as speech."""

        def detect_speech(self, audio, sample_rate):  # noqa: ARG002
            if len(audio) == 0:
                return []
            return [{'start': 0.0, 'end': len(audio) / sample_rate}]

        def extract_speech(self, audio, timestamps, sample_rate=16000):  # noqa: ARG002
            return audio

    monkeypatch.setattr("engines.audio.vad.VADDetector", _DummyVAD)

    audio_capture = DummyAudioCapture(sample_rate=16000)
    speech_engine = DummyStreamingSpeechEngine()
    file_manager = DummyFileManager(base_dir=tmp_path)

    recorded_callbacks = []

    recorder = RealtimeRecorder(
        audio_capture=audio_capture,
        speech_engine=speech_engine,
        translation_engine=None,
        db_connection=None,
        file_manager=file_manager,
    )

    recorder.set_callbacks(on_marker=recorded_callbacks.append)

    options = {
        'save_recording': False,
        'save_transcript': False,
        'create_calendar_event': False,
        'enable_translation': False,
    }

    async def _run_marker_flow():
        loop = asyncio.get_running_loop()
        await recorder.start_recording(options=options, event_loop=loop)

        recorder.recording_start_time -= timedelta(seconds=5)

        marker = recorder.add_marker()
        assert marker is not None
        assert marker['index'] == 1
        assert marker['offset'] == pytest.approx(5, abs=0.2)

        await asyncio.sleep(0.02)
        second_marker = recorder.add_marker()
        assert second_marker is not None
        assert second_marker['index'] == 2
        assert second_marker['offset'] >= marker['offset']

        result = await recorder.stop_recording()
        return marker, second_marker, result

    marker, second_marker, result = asyncio.run(_run_marker_flow())

    assert recorded_callbacks
    assert len(recorded_callbacks) == 2

    assert 'markers' in result
    assert len(result['markers']) == 2
    assert result['markers'][0]['index'] == 1
    assert result['markers'][1]['index'] == 2

    assert 'markers_path' in result
    saved_path = Path(result['markers_path'])
    assert saved_path.exists()

    with saved_path.open('r', encoding='utf-8') as handle:
        payload = json.load(handle)

    assert payload['markers'][0]['index'] == 1
    assert payload['markers'][1]['index'] == 2
    assert payload['markers'][0]['offset'] == pytest.approx(marker['offset'], abs=0.2)
    assert payload['markers'][1]['offset'] == pytest.approx(second_marker['offset'], abs=0.2)
