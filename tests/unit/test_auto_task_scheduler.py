from __future__ import annotations

import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

try:  # pragma: no cover - test utility setup
    from apscheduler.schedulers.background import BackgroundScheduler  # type: ignore  # noqa: F401
except ModuleNotFoundError:  # pragma: no cover - executed when dependency missing
    import types

    apscheduler_module = types.ModuleType('apscheduler')
    schedulers_module = types.ModuleType('apscheduler.schedulers')
    background_module = types.ModuleType('apscheduler.schedulers.background')

    class BackgroundScheduler:  # type: ignore[override]
        """Minimal stub to satisfy AutoTaskScheduler in unit tests."""

        def __init__(self, *_, **__):
            self.jobs = []

        def add_job(self, *args, **kwargs):
            self.jobs.append((args, kwargs))

        def start(self):  # noqa: D401
            return None

        def shutdown(self, *_, **__):  # noqa: D401
            return None

    background_module.BackgroundScheduler = BackgroundScheduler
    schedulers_module.background = background_module
    apscheduler_module.schedulers = schedulers_module

    sys.modules.setdefault('apscheduler', apscheduler_module)
    sys.modules.setdefault('apscheduler.schedulers', schedulers_module)
    sys.modules.setdefault('apscheduler.schedulers.background', background_module)

try:  # pragma: no cover - test utility setup
    import PyQt6  # type: ignore  # noqa: F401
except ModuleNotFoundError:  # pragma: no cover - executed when dependency missing
    import types

    pyqt_module = types.ModuleType('PyQt6')
    qtwidgets_module = types.ModuleType('PyQt6.QtWidgets')
    qtcore_module = types.ModuleType('PyQt6.QtCore')
    qtgui_module = types.ModuleType('PyQt6.QtGui')

    class _DummySignal:
        def connect(self, *_, **__):
            return None

        def emit(self, *_, **__):
            return None

    def pyqtSignal(*_, **__):  # noqa: D401
        return _DummySignal()

    class QObject:  # type: ignore[override]
        def __init__(self, *_, **__):
            pass

    class _BaseWidget:
        def __init__(self, *_, **__):
            pass

    class QWidget(_BaseWidget):
        pass

    class QDialog(_BaseWidget):
        pass

    class QLabel(_BaseWidget):
        def setWordWrap(self, *_, **__):
            return None

        def setObjectName(self, *_, **__):
            return None

        def setAlignment(self, *_, **__):
            return None

        def setText(self, *_, **__):
            return None

    class QPushButton(_BaseWidget):
        clicked = _DummySignal()

    class QTextEdit(_BaseWidget):
        def setReadOnly(self, *_, **__):
            return None

        def setPlainText(self, *_, **__):
            return None

        def toPlainText(self):
            return ""

        def setFixedHeight(self, *_, **__):
            return None

    class QProgressBar(_BaseWidget):
        def setRange(self, *_, **__):
            return None

        def setValue(self, *_, **__):
            return None

        def setTextVisible(self, *_, **__):
            return None

    class QVBoxLayout:
        def __init__(self, *_, **__):
            pass

        def setContentsMargins(self, *_, **__):
            return None

        def setSpacing(self, *_, **__):
            return None

        def addLayout(self, *_, **__):
            return None

        def addWidget(self, *_, **__):
            return None

        def addStretch(self, *_, **__):
            return None

    class QHBoxLayout(QVBoxLayout):
        pass

    class QIcon:
        def __init__(self, *_, **__):
            pass

    class QClipboard:
        def setText(self, *_, **__):
            return None

    class QApplication:
        @staticmethod
        def clipboard():
            return QClipboard()

    class _AlignmentFlag:
        AlignRight = 0
        AlignVCenter = 1

    class Qt:
        AlignmentFlag = _AlignmentFlag()

    qtwidgets_module.QWidget = QWidget
    qtwidgets_module.QDialog = QDialog
    qtwidgets_module.QLabel = QLabel
    qtwidgets_module.QPushButton = QPushButton
    qtwidgets_module.QTextEdit = QTextEdit
    qtwidgets_module.QVBoxLayout = QVBoxLayout
    qtwidgets_module.QHBoxLayout = QHBoxLayout
    qtwidgets_module.QProgressBar = QProgressBar
    qtwidgets_module.QApplication = QApplication

    qtcore_module.Qt = Qt
    qtcore_module.QObject = QObject
    qtcore_module.pyqtSignal = pyqtSignal

    qtgui_module.QIcon = QIcon
    qtgui_module.QClipboard = QClipboard

    pyqt_module.QtWidgets = qtwidgets_module
    pyqt_module.QtCore = qtcore_module
    pyqt_module.QtGui = qtgui_module

    sys.modules.setdefault('PyQt6', pyqt_module)
    sys.modules.setdefault('PyQt6.QtWidgets', qtwidgets_module)
    sys.modules.setdefault('PyQt6.QtCore', qtcore_module)
    sys.modules.setdefault('PyQt6.QtGui', qtgui_module)

try:  # pragma: no cover - test utility setup
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM  # type: ignore  # noqa: F401
except ModuleNotFoundError:  # pragma: no cover - executed when dependency missing
    import types

    cryptography_module = types.ModuleType('cryptography')
    hazmat_module = types.ModuleType('cryptography.hazmat')
    primitives_module = types.ModuleType('cryptography.hazmat.primitives')
    ciphers_module = types.ModuleType('cryptography.hazmat.primitives.ciphers')
    aead_module = types.ModuleType('cryptography.hazmat.primitives.ciphers.aead')
    hashes_module = types.ModuleType('cryptography.hazmat.primitives.hashes')
    kdf_module = types.ModuleType('cryptography.hazmat.primitives.kdf')
    pbkdf2_module = types.ModuleType('cryptography.hazmat.primitives.kdf.pbkdf2')

    class AESGCM:  # type: ignore[override]
        def __init__(self, *_, **__):
            pass

    aead_module.AESGCM = AESGCM

    class HashAlgorithm:  # type: ignore[override]
        pass

    class SHA256(HashAlgorithm):  # type: ignore[override]
        digest_size = 32

        def __init__(self, *_, **__):
            pass

    hashes_module.HashAlgorithm = HashAlgorithm
    hashes_module.SHA256 = SHA256

    class PBKDF2HMAC:  # type: ignore[override]
        def __init__(self, *_, **__):
            pass

        def derive(self, data):
            return b"".join([data])[:32].ljust(32, b"\0")

    pbkdf2_module.PBKDF2HMAC = PBKDF2HMAC

    ciphers_module.aead = aead_module
    primitives_module.ciphers = ciphers_module
    primitives_module.hashes = hashes_module
    kdf_module.pbkdf2 = pbkdf2_module
    primitives_module.kdf = kdf_module
    hazmat_module.primitives = primitives_module
    cryptography_module.hazmat = hazmat_module

    sys.modules.setdefault('cryptography', cryptography_module)
    sys.modules.setdefault('cryptography.hazmat', hazmat_module)
    sys.modules.setdefault('cryptography.hazmat.primitives', primitives_module)
    sys.modules.setdefault('cryptography.hazmat.primitives.ciphers', ciphers_module)
    sys.modules.setdefault('cryptography.hazmat.primitives.ciphers.aead', aead_module)
    sys.modules.setdefault('cryptography.hazmat.primitives.hashes', hashes_module)
    sys.modules.setdefault('cryptography.hazmat.primitives.kdf', kdf_module)
    sys.modules.setdefault('cryptography.hazmat.primitives.kdf.pbkdf2', pbkdf2_module)

from core.timeline.auto_task_scheduler import AutoTaskScheduler
from data.database.models import CalendarEvent
from utils.i18n import I18nQtManager


def iso_z(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')


class DummyTimelineManager:
    def __init__(self, future_events):
        self._future_events = list(future_events)
        self.calls = []

    def get_timeline_events(
        self,
        center_time,
        past_days,
        future_days,
        page=0,
        page_size=50,
    ):
        self.calls.append((center_time, past_days, future_days))
        if future_days == 0:
            return {
                'current_time': center_time.isoformat(),
                'future_events': [],
                'past_events': list(self._future_events),
                'has_more': False,
            }
        return {
            'current_time': center_time.isoformat(),
            'future_events': list(self._future_events),
            'past_events': [],
            'has_more': False,
        }


class DummyRecorder:
    def __init__(self):
        self.is_recording = False

    async def start_recording(self, *args, **kwargs):  # noqa: D401
        self.is_recording = True

    async def stop_recording(self):  # noqa: D401
        self.is_recording = False
        return {}


class DummyNotificationManager:
    def __init__(self):
        self.messages = []

    def send_info(self, title, message):
        self.messages.append(('info', title, message))

    def send_warning(self, title, message):  # noqa: D401
        self.messages.append(('warning', title, message))

    def send_success(self, title, message):  # noqa: D401
        self.messages.append(('success', title, message))

    def send_error(self, title, message):  # noqa: D401
        self.messages.append(('error', title, message))


class _CollectingSignal:
    def __init__(self):
        self.connections = []

    def connect(self, callback):
        self.connections.append(callback)

    def emit(self, *args, **kwargs):
        for callback in list(self.connections):
            callback(*args, **kwargs)


class DummySettingsManager:
    def __init__(self):
        self.setting_changed = _CollectingSignal()


def test_scheduler_updates_windows_after_setting_change(monkeypatch):
    timeline_manager = DummyTimelineManager([])
    recorder = DummyRecorder()
    notifications = DummyNotificationManager()
    settings_manager = DummySettingsManager()

    monkeypatch.setattr(
        'core.timeline.auto_task_scheduler.get_notification_manager',
        lambda: notifications,
    )

    scheduler = AutoTaskScheduler(
        timeline_manager=timeline_manager,
        realtime_recorder=recorder,
        db_connection=None,
        file_manager=None,
        reminder_minutes=5,
        settings_manager=settings_manager,
    )

    assert settings_manager.setting_changed.connections

    scheduler.notified_events.update({'event-1', 'event-2'})

    settings_manager.setting_changed.emit('timeline.reminder_minutes', '25')

    assert scheduler.reminder_minutes == 25
    assert scheduler._past_window_minutes == 25
    assert scheduler._future_window_minutes == 35
    assert scheduler.notified_events == set()

    scheduler._check_upcoming_events()

    assert timeline_manager.calls
    main_call = next(
        (call for call in timeline_manager.calls if call[2] > 0),
        timeline_manager.calls[0]
    )
    _, past_days, future_days = main_call
    expected_past_days = scheduler._past_window_minutes / (24 * 60)
    expected_future_days = scheduler._future_window_minutes / (24 * 60)
    assert past_days == pytest.approx(expected_past_days)
    assert future_days == pytest.approx(expected_future_days)


def test_scheduler_triggers_reminder_with_timezone(monkeypatch):
    base_now = datetime.now().astimezone()
    future_event = CalendarEvent(
        id='future-event',
        title='Reminder Test',
        start_time=iso_z(base_now + timedelta(minutes=65)),
        end_time=iso_z(base_now + timedelta(minutes=125)),
    )

    future_events = [{
        'event': future_event,
        'auto_tasks': {'enable_transcription': True},
    }]

    timeline_manager = DummyTimelineManager(future_events)
    recorder = DummyRecorder()
    notifications = DummyNotificationManager()

    monkeypatch.setattr(
        'core.timeline.auto_task_scheduler.get_notification_manager',
        lambda: notifications,
    )

    called = []

    original_send = AutoTaskScheduler._send_reminder_notification

    def wrapped_send(self, event, auto_tasks):
        called.append(event.id)
        return original_send(self, event, auto_tasks)

    monkeypatch.setattr(
        AutoTaskScheduler,
        '_send_reminder_notification',
        wrapped_send
    )

    from datetime import datetime as real_datetime

    fixed_now = real_datetime.now().astimezone()

    class FixedDateTime(real_datetime):
        @classmethod
        def now(cls, tz=None):
            if tz is None:
                return fixed_now
            return fixed_now.astimezone(tz)

        @classmethod
        def fromisoformat(cls, date_string):
            return real_datetime.fromisoformat(date_string)

    monkeypatch.setattr(
        'core.timeline.auto_task_scheduler.datetime',
        FixedDateTime
    )

    scheduler = AutoTaskScheduler(
        timeline_manager=timeline_manager,
        realtime_recorder=recorder,
        db_connection=None,
        file_manager=None,
        reminder_minutes=5,
    )

    future_event.start_time = iso_z(
        fixed_now + timedelta(minutes=5, seconds=10)
    )
    assert timeline_manager._future_events[0]['event'].start_time == future_event.start_time

    from core.timeline.manager import to_local_naive

    now_local = to_local_naive(FixedDateTime.now())
    event_start_local = to_local_naive(future_event.start_time)
    diff_seconds = (event_start_local - now_local).total_seconds()
    assert scheduler.reminder_minutes * 60 <= diff_seconds <= scheduler.reminder_minutes * 60 + 60

    scheduler._check_upcoming_events()

    assert called, "Reminder notification was not triggered"
    assert scheduler.notified_events, f"notified_events={scheduler.notified_events}"
    assert future_event.id in scheduler.notified_events
    assert notifications.messages
    kind, title, message = notifications.messages[0]
    assert kind == 'info'
    expected_title = scheduler.i18n.t(
        'auto_task.reminder.title',
        app_name=scheduler.i18n.t('app.name')
    )
    assert title == expected_title

    try:
        start_dt = to_local_naive(future_event.start_time)
    except Exception:  # noqa: BLE001
        expected_start_time = future_event.start_time
    else:
        expected_start_time = start_dt.strftime('%H:%M')

    tasks = [scheduler.i18n.t('auto_task.tasks.transcription')]
    separator = scheduler.i18n.t('auto_task.tasks.separator')
    if not isinstance(separator, str) or not separator:
        separator = ', '
    tasks_str = separator.join(tasks)
    expected_message = scheduler.i18n.t(
        'auto_task.reminder.message',
        event_title=future_event.title,
        start_time_label=scheduler.i18n.t('auto_task.reminder.start_time_label'),
        start_time=expected_start_time,
        task_list_label=scheduler.i18n.t('auto_task.reminder.task_list_label'),
        task_list=tasks_str
    )
    assert message == expected_message
    assert not recorder.is_recording
    assert timeline_manager.calls  # ensure call recorded
    for center_time, _, _ in timeline_manager.calls:
        assert center_time.tzinfo is None


def test_scheduler_reminder_localized_en(monkeypatch):
    base_now = datetime.now().astimezone()
    future_event = CalendarEvent(
        id='future-event-en',
        title='Planning Meeting',
        start_time=iso_z(base_now + timedelta(minutes=65)),
        end_time=iso_z(base_now + timedelta(minutes=125)),
    )

    future_events = [{
        'event': future_event,
        'auto_tasks': {
            'enable_transcription': True,
            'enable_recording': True
        },
    }]

    timeline_manager = DummyTimelineManager(future_events)
    recorder = DummyRecorder()
    notifications = DummyNotificationManager()

    monkeypatch.setattr(
        'core.timeline.auto_task_scheduler.get_notification_manager',
        lambda: notifications,
    )

    i18n = I18nQtManager(default_language='en_US')

    called = []
    original_send = AutoTaskScheduler._send_reminder_notification

    def wrapped_send(self, event, auto_tasks):
        called.append(event.id)
        return original_send(self, event, auto_tasks)

    monkeypatch.setattr(
        AutoTaskScheduler,
        '_send_reminder_notification',
        wrapped_send
    )

    from datetime import datetime as real_datetime

    fixed_now = real_datetime.now().astimezone()

    class FixedDateTime(real_datetime):
        @classmethod
        def now(cls, tz=None):
            if tz is None:
                return fixed_now
            return fixed_now.astimezone(tz)

        @classmethod
        def fromisoformat(cls, date_string):
            return real_datetime.fromisoformat(date_string)

    monkeypatch.setattr(
        'core.timeline.auto_task_scheduler.datetime',
        FixedDateTime
    )

    scheduler = AutoTaskScheduler(
        timeline_manager=timeline_manager,
        realtime_recorder=recorder,
        db_connection=None,
        file_manager=None,
        reminder_minutes=5,
        i18n_manager=i18n
    )

    future_event.start_time = iso_z(
        fixed_now + timedelta(minutes=5, seconds=10)
    )
    assert timeline_manager._future_events[0]['event'].start_time == future_event.start_time

    from core.timeline.manager import to_local_naive

    now_local = to_local_naive(FixedDateTime.now())
    event_start_local = to_local_naive(future_event.start_time)
    diff_seconds = (event_start_local - now_local).total_seconds()
    assert scheduler.reminder_minutes * 60 <= diff_seconds <= scheduler.reminder_minutes * 60 + 60

    scheduler._check_upcoming_events()

    assert called, "Reminder notification was not triggered"
    assert scheduler.notified_events, f"notified_events={scheduler.notified_events}"
    assert future_event.id in scheduler.notified_events
    assert notifications.messages
    kind, title, message = notifications.messages[0]
    assert kind == 'info'
    expected_title = i18n.t(
        'auto_task.reminder.title',
        app_name=i18n.t('app.name')
    )
    assert title == expected_title

    try:
        start_dt = to_local_naive(future_event.start_time)
    except Exception:  # noqa: BLE001
        expected_start_time = future_event.start_time
    else:
        expected_start_time = start_dt.strftime('%H:%M')

    tasks = [
        i18n.t('auto_task.tasks.transcription'),
        i18n.t('auto_task.tasks.recording')
    ]
    separator = i18n.t('auto_task.tasks.separator')
    if not isinstance(separator, str) or not separator:
        separator = ', '
    tasks_str = separator.join(tasks)
    expected_message = i18n.t(
        'auto_task.reminder.message',
        event_title=future_event.title,
        start_time_label=i18n.t('auto_task.reminder.start_time_label'),
        start_time=expected_start_time,
        task_list_label=i18n.t('auto_task.reminder.task_list_label'),
        task_list=tasks_str
    )
    assert message == expected_message


def test_scheduler_handles_naive_local_event_windows(monkeypatch):
    reminder_minutes = 5

    from datetime import datetime as real_datetime

    fixed_now = real_datetime.now().astimezone().replace(microsecond=0)

    class FixedDateTime(real_datetime):
        @classmethod
        def now(cls, tz=None):
            if tz is None:
                return fixed_now
            return fixed_now.astimezone(tz)

        @classmethod
        def fromisoformat(cls, date_string):
            return real_datetime.fromisoformat(date_string)

    monkeypatch.setattr(
        'core.timeline.auto_task_scheduler.datetime',
        FixedDateTime
    )

    reminder_start = fixed_now + timedelta(minutes=reminder_minutes, seconds=10)
    reminder_start_naive = reminder_start.replace(tzinfo=None).isoformat()

    future_event = CalendarEvent(
        id='naive-event',
        title='Local Only Planning',
        start_time=reminder_start_naive,
        end_time=(reminder_start + timedelta(hours=1)).replace(tzinfo=None).isoformat(),
    )

    future_events = [{
        'event': future_event,
        'auto_tasks': {
            'enable_transcription': True,
            'enable_recording': True,
        },
    }]

    timeline_manager = DummyTimelineManager(future_events)
    recorder = DummyRecorder()
    notifications = DummyNotificationManager()

    monkeypatch.setattr(
        'core.timeline.auto_task_scheduler.get_notification_manager',
        lambda: notifications,
    )

    reminder_calls = []
    start_calls = []

    def _capture_reminder(self, event, auto_tasks):
        reminder_calls.append((event.id, auto_tasks))

    def _capture_start(self, event, auto_tasks):
        start_calls.append((event.id, auto_tasks))
        return True

    monkeypatch.setattr(
        AutoTaskScheduler,
        '_send_reminder_notification',
        _capture_reminder
    )
    monkeypatch.setattr(
        AutoTaskScheduler,
        '_start_auto_tasks',
        _capture_start
    )

    i18n = I18nQtManager(default_language='en_US')

    scheduler = AutoTaskScheduler(
        timeline_manager=timeline_manager,
        realtime_recorder=recorder,
        db_connection=None,
        file_manager=None,
        reminder_minutes=reminder_minutes,
        i18n_manager=i18n,
    )

    scheduler._check_upcoming_events()

    assert reminder_calls == [(future_event.id, future_events[0]['auto_tasks'])]
    assert future_event.id in scheduler.notified_events
    assert not start_calls

    from core.timeline.manager import to_local_naive

    now_local = to_local_naive(FixedDateTime.now())
    event_start_local = to_local_naive(future_event.start_time)
    diff_seconds = (event_start_local - now_local).total_seconds()
    assert reminder_minutes * 60 <= diff_seconds <= reminder_minutes * 60 + 60

    near_start = fixed_now + timedelta(seconds=30)
    future_event.start_time = near_start.replace(tzinfo=None).isoformat()

    scheduler._check_upcoming_events()

    assert start_calls
    assert start_calls[0][0] == future_event.id
    assert future_event.id in scheduler.started_events

    now_local = to_local_naive(FixedDateTime.now())
    event_start_local = to_local_naive(future_event.start_time)
    diff_seconds = (event_start_local - now_local).total_seconds()
    assert -60 <= diff_seconds <= 60
