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

    def create_unique_filename(
        self,
        base_name: str,
        extension: str,
        subdirectory: Optional[str] = None
    ) -> str:
        if not extension.startswith('.'):
            extension = '.' + extension

        target_dir = self.base_dir / subdirectory if subdirectory else self.base_dir
        target_dir.mkdir(parents=True, exist_ok=True)

        candidate = f"{base_name}{extension}"
        counter = 1
        while (target_dir / candidate).exists():
            candidate = f"{base_name}_{counter}{extension}"
            counter += 1
        return candidate

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


class FailingAudioCapture(DummyAudioCapture):
    """Audio capture stub that raises when starting capture."""

    def start_capture(self, device_index=None, callback=None):  # noqa: ARG002
        raise RuntimeError("boom")


class AlwaysSpeechVAD:
    """VAD stub that treats every buffered chunk as valid speech."""

    def __init__(self, *args, **kwargs):  # noqa: D401, ARG002
        """无状态初始化，兼容真实 VAD 接口。"""

    def detect_speech(self, audio, sample_rate):  # noqa: ARG002
        if len(audio) == 0:
            return []
        return [{'start': 0.0, 'end': len(audio) / sample_rate}]

    def extract_speech(self, audio, timestamps, sample_rate=16000):  # noqa: ARG002
        return audio


class DummyTranslationEngine:
    """Translation engine stub that records translation calls."""

    def __init__(self):
        self.calls = 0
        self.arguments = []

    async def translate(self, text, source_lang='auto', target_lang='en'):
        self.calls += 1
        self.arguments.append((text, source_lang, target_lang))
        return f"{text}-to-{target_lang}"


class StubNotificationManager:
    def __init__(self):
        self.success_messages = []
        self.error_messages = []
        self.warning_messages = []

    def send_success(self, title, message):
        self.success_messages.append((title, message))

    def send_error(self, title, message):
        self.error_messages.append((title, message))

    def send_warning(self, title, message):
        self.warning_messages.append((title, message))


class DummyBackgroundScheduler:
    def __init__(self):
        self.jobs = []
        self.started = False

    def add_job(self, func, trigger, **kwargs):  # noqa: ARG002
        self.jobs.append((func, trigger, kwargs))

    def start(self):
        self.started = True

    def shutdown(self, wait=True):  # noqa: ARG002
        self.started = False


def _configure_scheduler_stubs(monkeypatch, notification_stub):
    background_module = types.ModuleType("apscheduler.schedulers.background")
    background_module.BackgroundScheduler = DummyBackgroundScheduler
    schedulers_module = types.ModuleType("apscheduler.schedulers")
    schedulers_module.background = background_module
    apscheduler_module = types.ModuleType("apscheduler")
    apscheduler_module.schedulers = schedulers_module

    monkeypatch.setitem(sys.modules, "apscheduler", apscheduler_module)
    monkeypatch.setitem(sys.modules, "apscheduler.schedulers", schedulers_module)
    monkeypatch.setitem(
        sys.modules,
        "apscheduler.schedulers.background",
        background_module,
    )

    ui_module = types.ModuleType("ui")
    common_module = types.ModuleType("ui.common")
    notification_module = types.ModuleType("ui.common.notification")

    notification_module.get_notification_manager = lambda: notification_stub
    notification_module.NotificationManager = object

    common_module.notification = notification_module
    ui_module.common = common_module

    monkeypatch.setitem(sys.modules, "ui", ui_module)
    monkeypatch.setitem(sys.modules, "ui.common", common_module)
    monkeypatch.setitem(
        sys.modules,
        "ui.common.notification",
        notification_module,
    )

    from core.timeline import auto_task_scheduler as scheduler_module

    monkeypatch.setattr(
        scheduler_module,
        "get_notification_manager",
        lambda: notification_stub,
    )

    return scheduler_module


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


def test_auto_scheduler_reports_start_failure(monkeypatch):
    from core.realtime.recorder import RealtimeRecorder

    notification_stub = StubNotificationManager()

    scheduler_module = _configure_scheduler_stubs(monkeypatch, notification_stub)

    recorder = RealtimeRecorder(
        audio_capture=FailingAudioCapture(),
        speech_engine=DummySpeechEngine(),
        translation_engine=None,
        db_connection=None,
        file_manager=DummyFileManager(),
    )

    scheduler = scheduler_module.AutoTaskScheduler(
        timeline_manager=object(),
        realtime_recorder=recorder,
        db_connection=None,
        file_manager=DummyFileManager(),
        reminder_minutes=5,
        settings_manager=None,
    )

    event = types.SimpleNamespace(id='evt-fail', title='Broken capture')
    auto_tasks = {'enable_recording': True, 'enable_transcription': True}

    started = scheduler._start_auto_tasks(event, auto_tasks)

    assert started is False
    assert recorder.is_recording is False
    assert event.id not in scheduler.active_recordings
    assert event.id not in scheduler.started_events
    assert notification_stub.success_messages == []
    assert notification_stub.error_messages, "Error notification should be sent"

    error_title, error_message = notification_stub.error_messages[-1]
    app_name = scheduler.i18n.t('app.name')
    expected_title = scheduler.i18n.t(
        'auto_task.notifications.start_error.title',
        app_name=app_name
    )
    assert error_title == expected_title

    expected_message = scheduler.i18n.t(
        'auto_task.notifications.start_error.message',
        event_title=event.title,
        error_message="自动录制启动失败：boom"
    )
    assert error_message == expected_message

    scheduler.scheduler.shutdown(wait=False)


def test_recorder_reinitializes_queues_between_event_loops(monkeypatch):
    from core.realtime.recorder import RealtimeRecorder

    monkeypatch.setattr("engines.audio.vad.VADDetector", AlwaysSpeechVAD)

    audio_capture = DummyAudioCapture()
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
        'enable_translation': False,
    }

    first_session_queues: dict[str, asyncio.Queue] = {}

    async def _widget_session():
        loop = asyncio.get_running_loop()
        await recorder.start_recording(options=options, event_loop=loop)
        first_session_queues['transcription'] = recorder.transcription_queue
        first_session_queues['translation'] = recorder.translation_queue
        first_session_queues['transcription_stream'] = recorder._transcription_stream_queue
        first_session_queues['translation_stream'] = recorder._translation_stream_queue
        await recorder.stop_recording()

    asyncio.run(_widget_session())

    for queue in first_session_queues.values():
        assert queue is not None

    notification_stub = StubNotificationManager()
    scheduler_module = _configure_scheduler_stubs(monkeypatch, notification_stub)

    scheduler = scheduler_module.AutoTaskScheduler(
        timeline_manager=object(),
        realtime_recorder=recorder,
        db_connection=None,
        file_manager=DummyFileManager(),
        reminder_minutes=5,
        settings_manager=None,
    )

    event = types.SimpleNamespace(id='evt-loop', title='Multi-loop test')
    auto_tasks = {
        'enable_recording': True,
        'enable_transcription': True,
        'enable_translation': False,
    }

    second_session_queues: dict[str, asyncio.Queue] = {}
    started = False
    try:
        started = scheduler._start_auto_tasks(event, auto_tasks)
        assert started is True
        assert recorder.is_recording is True

        second_session_queues['transcription'] = recorder.transcription_queue
        second_session_queues['translation'] = recorder.translation_queue
        second_session_queues['transcription_stream'] = recorder._transcription_stream_queue
        second_session_queues['translation_stream'] = recorder._translation_stream_queue

        for key, queue in second_session_queues.items():
            assert queue is not None
            assert queue is not first_session_queues[key]
    finally:
        if started and event.id in scheduler.active_recordings:
            scheduler._stop_auto_tasks(event)
        scheduler.scheduler.shutdown(wait=False)

    assert notification_stub.error_messages == []
    assert notification_stub.success_messages, "Success notifications should be sent"

    app_name = scheduler.i18n.t('app.name')

    start_title, start_message = notification_stub.success_messages[0]
    expected_start_title = scheduler.i18n.t(
        'auto_task.notifications.start_success.title',
        app_name=app_name
    )
    expected_start_message = scheduler.i18n.t(
        'auto_task.notifications.start_success.message',
        event_title=event.title
    )
    assert start_title == expected_start_title
    assert start_message == expected_start_message

    stop_title, stop_message = notification_stub.success_messages[-1]
    expected_stop_title = scheduler.i18n.t(
        'auto_task.notifications.stop_success.title',
        app_name=app_name
    )
    expected_stop_message = scheduler.i18n.t(
        'auto_task.notifications.stop_success.message',
        event_title=event.title,
        duration_seconds="0.0"
    )
    assert stop_title == expected_stop_title
    assert stop_message == expected_stop_message


def test_stop_recording_without_database_skips_calendar_event(monkeypatch):
    from core.realtime.recorder import RealtimeRecorder

    monkeypatch.setattr("engines.audio.vad.VADDetector", AlwaysSpeechVAD)

    audio_capture = DummyAudioCapture()
    recorder = RealtimeRecorder(
        audio_capture=audio_capture,
        speech_engine=DummySpeechEngine(),
        translation_engine=None,
        db_connection=None,
        file_manager=DummyFileManager(),
    )

    errors: list[str] = []
    recorder.set_callbacks(on_error=errors.append)

    options = {
        'save_recording': False,
        'save_transcript': False,
        'create_calendar_event': True,
        'enable_translation': False,
    }

    async def _run():
        loop = asyncio.get_running_loop()
        await recorder.start_recording(options=options, event_loop=loop)
        return await recorder.stop_recording()

    result = asyncio.run(_run())

    assert 'event_id' not in result
    assert errors == []


def test_create_calendar_event_requires_database_connection():
    from core.realtime.recorder import RealtimeRecorder

    recorder = RealtimeRecorder(
        audio_capture=None,
        speech_engine=DummySpeechEngine(),
        translation_engine=None,
        db_connection=None,
        file_manager=DummyFileManager(),
    )

    warnings: list[str] = []
    recorder.set_callbacks(on_error=warnings.append)

    now = datetime.now()
    recorder.recording_start_time = now

    result = asyncio.run(recorder._create_calendar_event({
        'start_time': now.isoformat(),
        'end_time': (now + timedelta(seconds=1)).isoformat(),
        'duration': 1.0,
    }))

    assert result == ""
    assert warnings
    assert "database" in warnings[-1].lower()


def test_start_recording_failure_rolls_back_state():
    from core.realtime.recorder import RealtimeRecorder

    audio_capture = FailingAudioCapture()
    recorder = RealtimeRecorder(
        audio_capture=audio_capture,
        speech_engine=DummySpeechEngine(),
        translation_engine=None,
        db_connection=None,
        file_manager=DummyFileManager(),
    )

    errors = []

    def _on_error(message):
        errors.append(message)

    recorder.set_callbacks(on_error=_on_error)

    async def _start():
        await recorder.start_recording()

    with pytest.raises(RuntimeError, match="boom"):
        asyncio.run(_start())

    assert recorder.is_recording is False
    assert recorder.recording_start_time is None
    assert recorder.recording_audio_buffer == []
    assert recorder.audio_buffer is None
    assert recorder.processing_task is None
    assert recorder.translation_task is None
    assert recorder.transcription_queue is None
    assert recorder.translation_queue is None
    assert recorder._transcription_stream_queue is None
    assert recorder._translation_stream_queue is None
    assert errors, "Expected on_error to be triggered"
    assert "Failed to start recording" in errors[-1]


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


def test_transcription_stream_emits_segments(monkeypatch):
    if not HAS_NUMPY:
        pytest.skip("numpy is required for streaming tests")

    from core.realtime.recorder import RealtimeRecorder

    monkeypatch.setattr("engines.audio.vad.VADDetector", AlwaysSpeechVAD)

    audio_capture = DummyAudioCapture(sample_rate=16000)
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
        'enable_translation': False,
    }

    results: list[str] = []

    async def _run():
        loop = asyncio.get_running_loop()
        await recorder.start_recording(options=options, event_loop=loop)
        assert audio_capture.callback is not None

        ready = asyncio.Event()

        async def _consume_stream():
            async for text in recorder.get_transcription_stream():
                results.append(text)
                if len(results) >= 1:
                    ready.set()

        consumer_task = asyncio.create_task(_consume_stream())

        chunk = np.full(recorder.sample_rate, 0.05, dtype=np.float32)
        for _ in range(3):
            audio_capture.callback(chunk.copy())
            await asyncio.sleep(0.01)

        await asyncio.wait_for(ready.wait(), timeout=2.0)

        await recorder.stop_recording()
        await consumer_task

    asyncio.run(_run())

    assert results == ["transcription-1"]


def test_translation_stream_emits_segments(monkeypatch):
    if not HAS_NUMPY:
        pytest.skip("numpy is required for streaming tests")

    from core.realtime.recorder import RealtimeRecorder

    monkeypatch.setattr("engines.audio.vad.VADDetector", AlwaysSpeechVAD)

    audio_capture = DummyAudioCapture(sample_rate=16000)
    speech_engine = DummyStreamingSpeechEngine()
    translation_engine = DummyTranslationEngine()
    recorder = RealtimeRecorder(
        audio_capture=audio_capture,
        speech_engine=speech_engine,
        translation_engine=translation_engine,
        db_connection=None,
        file_manager=DummyFileManager(),
    )

    options = {
        'save_recording': False,
        'save_transcript': False,
        'create_calendar_event': False,
        'enable_translation': True,
        'target_language': 'en',
    }

    translations: list[str] = []

    async def _run():
        loop = asyncio.get_running_loop()
        await recorder.start_recording(options=options, event_loop=loop)
        assert audio_capture.callback is not None

        ready = asyncio.Event()

        async def _consume_translation():
            async for text in recorder.get_translation_stream():
                translations.append(text)
                if len(translations) >= 1:
                    ready.set()

        translation_task = asyncio.create_task(_consume_translation())

        chunk = np.full(recorder.sample_rate, 0.05, dtype=np.float32)
        for _ in range(3):
            audio_capture.callback(chunk.copy())
            await asyncio.sleep(0.01)

        await asyncio.wait_for(ready.wait(), timeout=2.0)

        await recorder.stop_recording()
        await translation_task

    asyncio.run(_run())

    assert translations == ["transcription-1-to-en"]
    assert translation_engine.calls == 1
    assert translation_engine.arguments[-1][1] == options.get('language', 'auto')
    assert translation_engine.arguments[-1][2] == 'en'


def test_stop_recording_persists_translation_file(monkeypatch, tmp_path):
    from core.realtime.recorder import RealtimeRecorder

    monkeypatch.setattr("engines.audio.vad.VADDetector", AlwaysSpeechVAD)

    audio_capture = DummyAudioCapture(sample_rate=16000)
    speech_engine = DummyStreamingSpeechEngine()
    translation_engine = DummyTranslationEngine()
    file_manager = DummyFileManager(base_dir=tmp_path)

    recorder = RealtimeRecorder(
        audio_capture=audio_capture,
        speech_engine=speech_engine,
        translation_engine=translation_engine,
        db_connection=None,
        file_manager=file_manager,
    )

    options = {
        'save_recording': False,
        'save_transcript': False,
        'create_calendar_event': False,
        'enable_translation': True,
        'target_language': 'en',
    }

    async def _run():
        loop = asyncio.get_running_loop()
        await recorder.start_recording(options=options, event_loop=loop)
        assert audio_capture.callback is not None

        translated_text = await translation_engine.translate(
            "transcription-1",
            source_lang=options.get('language', 'auto'),
            target_lang=options['target_language'],
        )
        recorder.accumulated_translation.append(translated_text)

        return await recorder.stop_recording()

    result = asyncio.run(_run())

    translation_path = result.get('translation_path')
    assert translation_path, "Expected translation_path in stop_recording result"

    saved_path = Path(translation_path)
    assert saved_path.exists()
    content = saved_path.read_text(encoding='utf-8').strip()
    assert "transcription-1-to-en" in content


def test_save_recording_mp3_with_ffmpeg(monkeypatch, tmp_path):
    from core.realtime.recorder import RealtimeRecorder

    audio_capture = DummyAudioCapture()
    file_manager = DummyFileManager(base_dir=tmp_path)
    recorder = RealtimeRecorder(
        audio_capture=audio_capture,
        speech_engine=DummySpeechEngine(),
        translation_engine=None,
        db_connection=None,
        file_manager=file_manager,
    )

    if HAS_NUMPY:
        recorder.recording_audio_buffer = [
            np.zeros(160, dtype=np.float32)
        ]
    else:
        class _NPStub:
            @staticmethod
            def concatenate(buffers):
                return b''.join(buffers)

        monkeypatch.setattr('core.realtime.recorder.np', _NPStub())
        recorder.recording_audio_buffer = [b'DUMMY']
    recorder.recording_start_time = datetime.now()
    recorder.sample_rate = 16000
    recorder.current_options = {'recording_format': 'mp3'}

    monkeypatch.setattr(
        recorder,
        '_is_mp3_conversion_available',
        lambda: True
    )

    def _fake_convert(_, wav_path: str, mp3_path: str):  # type: ignore[override]
        Path(mp3_path).parent.mkdir(parents=True, exist_ok=True)
        with open(mp3_path, 'wb') as mp3_file:
            mp3_file.write(b'MP3DATA')

    monkeypatch.setattr(
        recorder,
        '_convert_wav_to_mp3',
        _fake_convert.__get__(recorder, recorder.__class__)  # type: ignore[arg-type]
    )

    def _fake_write(path, data, samplerate):  # noqa: ARG001
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'wb') as wav_file:
            wav_file.write(b'WAVDATA')

    monkeypatch.setattr('soundfile.write', _fake_write)

    path = asyncio.run(recorder._save_recording())

    assert path.endswith('.mp3')
    assert any(name.endswith('.mp3') for name in file_manager.saved_files)


def test_save_recording_mp3_without_ffmpeg(monkeypatch, tmp_path):
    from core.realtime.recorder import RealtimeRecorder

    audio_capture = DummyAudioCapture()
    file_manager = DummyFileManager(base_dir=tmp_path)
    recorder = RealtimeRecorder(
        audio_capture=audio_capture,
        speech_engine=DummySpeechEngine(),
        translation_engine=None,
        db_connection=None,
        file_manager=file_manager,
    )

    messages = []
    recorder.on_error = messages.append

    if HAS_NUMPY:
        recorder.recording_audio_buffer = [
            np.zeros(160, dtype=np.float32)
        ]
    else:
        class _NPStub:
            @staticmethod
            def concatenate(buffers):
                return b''.join(buffers)

        monkeypatch.setattr('core.realtime.recorder.np', _NPStub())
        recorder.recording_audio_buffer = [b'DUMMY']
    recorder.recording_start_time = datetime.now()
    recorder.sample_rate = 16000
    recorder.current_options = {'recording_format': 'mp3'}

    monkeypatch.setattr(
        recorder,
        '_is_mp3_conversion_available',
        lambda: False
    )

    def _fake_write(path, data, samplerate):  # noqa: ARG001
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'wb') as wav_file:
            wav_file.write(b'WAVDATA')

    monkeypatch.setattr('soundfile.write', _fake_write)

    path = asyncio.run(recorder._save_recording())

    assert path.endswith('.wav')
    assert any(name.endswith('.wav') for name in file_manager.saved_files)
    assert messages
    assert any('MP3' in message for message in messages)


def test_exports_use_unique_filenames(monkeypatch, tmp_path):
    from core.realtime.recorder import RealtimeRecorder

    audio_capture = DummyAudioCapture()
    file_manager = DummyFileManager(base_dir=tmp_path)
    recorder = RealtimeRecorder(
        audio_capture=audio_capture,
        speech_engine=DummySpeechEngine(),
        translation_engine=None,
        db_connection=None,
        file_manager=file_manager,
    )

    base_time = datetime(2024, 1, 1, 12, 0, 0)
    recorder.sample_rate = 16000
    recorder.current_options = {
        'recording_format': 'wav',
        'target_language': 'en',
    }

    if HAS_NUMPY:
        sample_chunk = np.zeros(160, dtype=np.float32)

        def _prepare_audio_buffer():
            recorder.recording_audio_buffer = [sample_chunk.copy()]
    else:
        class _NPStub:
            @staticmethod
            def concatenate(buffers):
                return b''.join(buffers)

        monkeypatch.setattr('core.realtime.recorder.np', _NPStub())
        sample_chunk = b'DUMMY'

        def _prepare_audio_buffer():
            recorder.recording_audio_buffer = [sample_chunk]

    def _fake_write(path, data, samplerate):  # noqa: ARG001
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'wb') as wav_file:
            wav_file.write(b'WAVDATA')

    monkeypatch.setattr('soundfile.write', _fake_write)

    recorder.recording_start_time = base_time
    _prepare_audio_buffer()
    first_recording = asyncio.run(recorder._save_recording())

    recorder.recording_start_time = base_time
    _prepare_audio_buffer()
    second_recording = asyncio.run(recorder._save_recording())

    assert first_recording
    assert second_recording
    assert Path(first_recording).name != Path(second_recording).name
    assert Path(first_recording).parent == Path(second_recording).parent

    recorder.recording_start_time = base_time
    recorder.accumulated_transcription = ['first transcript']
    first_transcript = asyncio.run(recorder._save_transcript())

    recorder.recording_start_time = base_time
    recorder.accumulated_transcription = ['second transcript']
    second_transcript = asyncio.run(recorder._save_transcript())

    assert first_transcript
    assert second_transcript
    assert Path(first_transcript).name != Path(second_transcript).name

    recorder.recording_start_time = base_time
    recorder.accumulated_translation = ['hola']
    first_translation = asyncio.run(recorder._save_translation())

    recorder.recording_start_time = base_time
    recorder.accumulated_translation = ['adios']
    second_translation = asyncio.run(recorder._save_translation())

    assert first_translation
    assert second_translation
    assert Path(first_translation).name != Path(second_translation).name

    recorder.recording_start_time = base_time
    recorder.markers = [{
        'index': 1,
        'offset': 0.0,
        'absolute_time': base_time.isoformat(),
        'label': 'first'
    }]
    first_markers = recorder._save_markers()

    recorder.recording_start_time = base_time
    recorder.markers = [{
        'index': 1,
        'offset': 1.0,
        'absolute_time': base_time.isoformat(),
        'label': 'second'
    }]
    second_markers = recorder._save_markers()

    assert first_markers
    assert second_markers
    assert Path(first_markers).name != Path(second_markers).name
