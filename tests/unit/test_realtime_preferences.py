import asyncio
import threading
import types

import pytest

PyQt6 = pytest.importorskip("PyQt6")
from PyQt6.QtWidgets import QApplication

from core.timeline.auto_task_scheduler import AutoTaskScheduler
from ui.realtime_record.widget import RealtimeRecordWidget


class DummySignal:
    def __init__(self):
        self._callbacks = []

    def connect(self, callback):
        self._callbacks.append(callback)

    def disconnect(self, callback):
        try:
            self._callbacks.remove(callback)
        except ValueError:
            pass

    def emit(self, *args, **kwargs):
        for callback in list(self._callbacks):
            callback(*args, **kwargs)


class FakeSettingsManager:
    def __init__(self, preferences):
        self._preferences = dict(preferences)
        self.setting_changed = DummySignal()

    def get_realtime_preferences(self):
        return dict(self._preferences)

    def update(self, **kwargs):
        self._preferences.update(kwargs)
        for key, value in kwargs.items():
            self.setting_changed.emit(f"realtime.{key}", value)


class FakeI18n:
    def __init__(self):
        self.language_changed = DummySignal()

    def t(self, key, **kwargs):
        if not kwargs:
            return key
        replacements = ", ".join(f"{name}={value}" for name, value in kwargs.items())
        return f"{key} ({replacements})"


class FakeRecorder:
    def __init__(self, stop_result=None):
        self.is_recording = False
        self.audio_capture = None
        self.translation_engine = None
        self.start_kwargs = None
        self._stop_result = dict(stop_result or {})

    def set_callbacks(
        self,
        on_transcription=None,
        on_translation=None,
        on_error=None,
        on_audio_data=None,
        on_marker=None
    ):
        # Callbacks are ignored for this fake; method kept for compatibility.
        self._callbacks = {
            'on_transcription': on_transcription,
            'on_translation': on_translation,
            'on_error': on_error,
            'on_audio_data': on_audio_data,
            'on_marker': on_marker,
        }

    def audio_input_available(self):
        return False

    async def start_recording(self, input_source=None, options=None, event_loop=None):
        self.is_recording = True
        self.start_kwargs = {
            'input_source': input_source,
            'options': options,
            'event_loop': event_loop,
        }

    async def stop_recording(self):
        self.is_recording = False
        return dict(self._stop_result)

    def get_recording_status(self):
        return {'is_recording': self.is_recording, 'duration': 0.0}

    def get_accumulated_transcription(self):
        return ''

    def get_accumulated_translation(self):
        return ''

    def add_marker(self):
        return {'offset': 0.0, 'label': None}


class StubNotificationManager:
    def __init__(self):
        self.success_messages = []
        self.error_messages = []

    def send_success(self, title, message):
        self.success_messages.append((title, message))

    def send_error(self, title, message):
        self.error_messages.append((title, message))


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


def test_realtime_widget_uses_settings_preferences(qapp):
    settings = FakeSettingsManager({'recording_format': 'mp3', 'auto_save': False})
    recorder = FakeRecorder()
    widget = RealtimeRecordWidget(
        recorder=recorder,
        audio_capture=None,
        i18n_manager=FakeI18n(),
        settings_manager=settings
    )

    widget.enable_translation_checkbox.setChecked(False)
    widget.source_lang_combo.setCurrentIndex(0)
    widget.target_lang_combo.setCurrentIndex(0)

    asyncio.run(widget._start_recording())

    assert recorder.start_kwargs is not None
    options = recorder.start_kwargs['options']
    assert options['recording_format'] == 'mp3'
    assert options['save_recording'] is False

    widget.deleteLater()
    qapp.processEvents()


def test_widget_show_error_updates_feedback_and_notifies(qapp, monkeypatch):
    notification_stub = StubNotificationManager()
    monkeypatch.setattr(
        'ui.realtime_record.widget.get_notification_manager',
        lambda: notification_stub
    )

    settings = FakeSettingsManager({'recording_format': 'wav', 'auto_save': True})
    recorder = FakeRecorder()
    widget = RealtimeRecordWidget(
        recorder=recorder,
        audio_capture=None,
        i18n_manager=FakeI18n(),
        settings_manager=settings
    )

    try:
        widget._show_error('Microphone missing')
        qapp.processEvents()

        assert widget.feedback_label.isVisible()
        assert 'Microphone missing' in widget.feedback_label.text()
        assert notification_stub.error_messages
        assert 'Microphone missing' in notification_stub.error_messages[-1][1]
    finally:
        widget.deleteLater()
        qapp.processEvents()


def test_widget_show_error_from_worker_thread(qapp, monkeypatch):
    notification_stub = StubNotificationManager()
    monkeypatch.setattr(
        'ui.realtime_record.widget.get_notification_manager',
        lambda: notification_stub
    )

    recorder = FakeRecorder()
    widget = RealtimeRecordWidget(
        recorder=recorder,
        audio_capture=None,
        i18n_manager=FakeI18n(),
        settings_manager=None
    )

    try:
        thread = threading.Thread(
            target=widget._show_error,
            args=('Background failure',),
            daemon=True
        )
        thread.start()
        thread.join()

        qapp.processEvents()

        assert notification_stub.error_messages
        assert any('Background failure' in msg for _, msg in notification_stub.error_messages)
    finally:
        widget.deleteLater()
        qapp.processEvents()


def test_widget_stop_recording_emits_success_feedback(qapp, monkeypatch):
    notification_stub = StubNotificationManager()
    monkeypatch.setattr(
        'ui.realtime_record.widget.get_notification_manager',
        lambda: notification_stub
    )

    stop_result = {
        'duration': 12.0,
        'recording_path': '/tmp/test-session.wav'
    }
    recorder = FakeRecorder(stop_result=stop_result)
    recorder.is_recording = True

    widget = RealtimeRecordWidget(
        recorder=recorder,
        audio_capture=None,
        i18n_manager=FakeI18n(),
        settings_manager=None
    )

    try:
        asyncio.run(widget._stop_recording())
        qapp.processEvents()

        assert notification_stub.success_messages
        title, message = notification_stub.success_messages[-1]
        assert 'recording_saved' in title
        assert '/tmp/test-session.wav' in message

        assert widget.feedback_label.isVisible()
        assert '/tmp/test-session.wav' in widget.feedback_label.text()
    finally:
        widget.deleteLater()
        qapp.processEvents()


def test_auto_task_scheduler_inherits_global_preferences():
    settings = FakeSettingsManager({'recording_format': 'mp3', 'auto_save': False})
    scheduler = AutoTaskScheduler(
        timeline_manager=object(),
        realtime_recorder=FakeRecorder(),
        db_connection=object(),
        file_manager=object(),
        reminder_minutes=5,
        settings_manager=settings
    )

    event = types.SimpleNamespace(id='evt-1', title='Weekly Sync')
    auto_tasks = {'enable_transcription': True}

    options = scheduler._build_recording_options(event, auto_tasks)
    assert options['recording_format'] == 'mp3'
    assert options['save_recording'] is False
    assert options['save_transcript'] is True

    auto_tasks_explicit = {'enable_recording': True}
    override_options = scheduler._build_recording_options(event, auto_tasks_explicit)
    assert override_options['save_recording'] is True

    scheduler.scheduler.shutdown(wait=False)
