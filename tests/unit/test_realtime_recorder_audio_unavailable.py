import asyncio
import sys
import types
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from tests.unit.test_transcription_manager_failure import _ensure_numpy_stub  # type: ignore


_ensure_numpy_stub()


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
    """Placeholder used to satisfy recorder constructor."""


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
