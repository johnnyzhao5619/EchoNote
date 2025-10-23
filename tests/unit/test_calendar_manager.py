import sys
import types
import pytest
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _ensure_soundfile_stub():
    if "soundfile" in sys.modules:
        return

    soundfile_module = types.ModuleType("soundfile")

    def _write_stub(*args, **kwargs):  # noqa: ARG002
        return None

    soundfile_module.write = _write_stub  # type: ignore[attr-defined]
    sys.modules["soundfile"] = soundfile_module


_ensure_soundfile_stub()


def _ensure_psutil_stub():
    if "psutil" in sys.modules:
        return

    psutil_module = types.ModuleType("psutil")

    class _Process:
        def __init__(self, *args, **kwargs):
            pass

        def cpu_percent(self, *args, **kwargs):  # noqa: D401 - stub method
            return 0.0

        def memory_percent(self, *args, **kwargs):  # noqa: D401 - stub method
            return 0.0

    class _VirtualMemory:
        percent = 0.0

    def _virtual_memory():  # noqa: D401 - stub function
        return _VirtualMemory()

    psutil_module.Process = _Process
    psutil_module.cpu_count = lambda *args, **kwargs: 1  # noqa: E731 - simple stub
    psutil_module.virtual_memory = _virtual_memory

    sys.modules["psutil"] = psutil_module


def _ensure_pyqt6_stub():
    if "PyQt6" in sys.modules:
        return

    pyqt6_module = types.ModuleType("PyQt6")
    qtcore_module = types.ModuleType("PyQt6.QtCore")
    qtwidgets_module = types.ModuleType("PyQt6.QtWidgets")

    class QObject:  # noqa: D401 - stub class
        pass

    class QCoreApplication:  # noqa: D401 - stub class
        def __init__(self, *args, **kwargs):
            pass

        @staticmethod
        def instance():  # noqa: D401 - stub method
            return None

    class QTimer:  # noqa: D401 - stub class
        def __init__(self, *args, **kwargs):
            pass

        def start(self, *args, **kwargs):  # noqa: D401 - stub method
            return None

        def stop(self):  # noqa: D401 - stub method
            return None

    class _Signal:  # noqa: D401 - stub helper
        def __init__(self, *args, **kwargs):
            self._subscribers = []

        def connect(self, callback):  # noqa: D401 - stub method
            self._subscribers.append(callback)

        def emit(self, *args, **kwargs):  # noqa: D401 - stub method
            for subscriber in list(self._subscribers):
                subscriber(*args, **kwargs)

    def pyqtSignal(*args, **kwargs):  # noqa: D401 - stub factory
        return _Signal()

    class _Qt:  # noqa: D401 - stub namespace
        AlignCenter = 0

    qtcore_module.Qt = _Qt
    qtcore_module.QObject = QObject
    qtcore_module.QCoreApplication = QCoreApplication
    qtcore_module.QTimer = QTimer
    qtcore_module.pyqtSignal = pyqtSignal

    class QWidget:  # noqa: D401 - stub class
        def __init__(self, *args, **kwargs):
            pass

    class QLayout:  # noqa: D401 - shared stub base
        def __init__(self, *args, **kwargs):
            pass

        def addWidget(self, *args, **kwargs):  # noqa: N802,D401 - stub method
            return None

    class QVBoxLayout(QLayout):
        pass

    class QHBoxLayout(QLayout):
        pass

    class QLabel(QWidget):
        def setText(self, *args, **kwargs):  # noqa: D401 - stub method
            return None

    class QProgressBar(QWidget):
        def setValue(self, *args, **kwargs):  # noqa: D401 - stub method
            return None

    qtwidgets_module.QWidget = QWidget
    qtwidgets_module.QVBoxLayout = QVBoxLayout
    qtwidgets_module.QHBoxLayout = QHBoxLayout
    qtwidgets_module.QLabel = QLabel
    qtwidgets_module.QProgressBar = QProgressBar

    pyqt6_module.QtCore = qtcore_module
    pyqt6_module.QtWidgets = qtwidgets_module

    sys.modules["PyQt6"] = pyqt6_module
    sys.modules["PyQt6.QtCore"] = qtcore_module
    sys.modules["PyQt6.QtWidgets"] = qtwidgets_module


_ensure_psutil_stub()
_ensure_pyqt6_stub()


try:  # pragma: no cover - import guard for optional test helpers
    from tests.unit.test_transcription_manager_failure import (  # type: ignore
        _ensure_cryptography_stubs,
    )
except Exception:  # pragma: no cover - fallback to local stubs
    def _ensure_cryptography_stubs():
        if "cryptography" in sys.modules:
            return

        cryptography_module = types.ModuleType("cryptography")
        hazmat_module = types.ModuleType("cryptography.hazmat")
        primitives_module = types.ModuleType("cryptography.hazmat.primitives")
        ciphers_module = types.ModuleType(
            "cryptography.hazmat.primitives.ciphers"
        )
        aead_module = types.ModuleType(
            "cryptography.hazmat.primitives.ciphers.aead"
        )
        hashes_module = types.ModuleType("cryptography.hazmat.primitives.hashes")
        kdf_module = types.ModuleType("cryptography.hazmat.primitives.kdf")
        pbkdf2_module = types.ModuleType(
            "cryptography.hazmat.primitives.kdf.pbkdf2"
        )

        class _DummyAESGCM:
            def __init__(self, key):  # noqa: D401 - stub init
                self._key = key

            def encrypt(self, nonce, data, associated_data=None):  # noqa: D401
                return data

            def decrypt(self, nonce, data, associated_data=None):  # noqa: D401
                return data

        class _DummySHA256:
            name = "sha256"

        class _DummyPBKDF2HMAC:
            def __init__(self, algorithm, length, salt, iterations):
                self._length = length

            def derive(self, data):  # noqa: D401 - stub method
                if not data:
                    return b"\x00" * self._length
                repeated = (data * ((self._length // len(data)) + 1))[: self._length]
                return repeated

        aead_module.AESGCM = _DummyAESGCM
        hashes_module.SHA256 = _DummySHA256
        pbkdf2_module.PBKDF2HMAC = _DummyPBKDF2HMAC

        cryptography_module.hazmat = hazmat_module
        hazmat_module.primitives = primitives_module
        primitives_module.ciphers = ciphers_module
        primitives_module.hashes = hashes_module
        primitives_module.kdf = kdf_module
        ciphers_module.aead = aead_module
        kdf_module.pbkdf2 = pbkdf2_module

        sys.modules["cryptography"] = cryptography_module
        sys.modules["cryptography.hazmat"] = hazmat_module
        sys.modules["cryptography.hazmat.primitives"] = primitives_module
        sys.modules[
            "cryptography.hazmat.primitives.ciphers"
        ] = ciphers_module
        sys.modules[
            "cryptography.hazmat.primitives.ciphers.aead"
        ] = aead_module
        sys.modules["cryptography.hazmat.primitives.hashes"] = hashes_module
        sys.modules["cryptography.hazmat.primitives.kdf"] = kdf_module
        sys.modules[
            "cryptography.hazmat.primitives.kdf.pbkdf2"
        ] = pbkdf2_module

    app_config_module = types.ModuleType("config.app_config")

    class _ConfigManager:
        def __init__(self, *args, **kwargs):  # noqa: D401, ARG002
            self._config = {}

    def _get_app_dir():  # noqa: D401
        return Path.cwd()

    app_config_module.ConfigManager = _ConfigManager  # type: ignore[attr-defined]
    app_config_module.get_app_dir = _get_app_dir  # type: ignore[attr-defined]

    config_package = sys.modules.setdefault("config", types.ModuleType("config"))
    setattr(config_package, "app_config", app_config_module)
    sys.modules["config.app_config"] = app_config_module


_ensure_app_config_stub()


from tests.unit.test_transcription_manager_failure import (
    _ensure_cryptography_stubs,
    _ensure_pyqt_stub,
)


_ensure_pyqt_stub()
_ensure_cryptography_stubs()


def _ensure_ui_common_stubs():
    common_module = sys.modules.get("ui.common")
    if common_module is None:
        common_module = types.ModuleType("ui.common")
        sys.modules["ui.common"] = common_module

    notification_module = types.ModuleType("ui.common.notification")

    class _NotificationManager:
        def send_info(self, *args, **kwargs):  # noqa: D401 - stub method
            return None

        def send_warning(self, *args, **kwargs):  # noqa: D401 - stub method
            return None

        def send_success(self, *args, **kwargs):  # noqa: D401 - stub method
            return None

        def send_error(self, *args, **kwargs):  # noqa: D401 - stub method
            return None

    _notification_instance = _NotificationManager()

    def _get_notification_manager():  # noqa: D401 - stub factory
        return _notification_instance

    notification_module.NotificationManager = _NotificationManager
    notification_module.get_notification_manager = _get_notification_manager

    progress_module = types.ModuleType("ui.common.progress_bar")

    class _ProgressBar:  # noqa: D401 - stub class
        def show(self, *args, **kwargs):  # noqa: D401 - stub method
            return None

        def set_progress(self, *args, **kwargs):  # noqa: D401 - stub method
            return None

    progress_module.ProgressBar = _ProgressBar

    error_dialog_module = types.ModuleType("ui.common.error_dialog")

    class _ErrorDialog:  # noqa: D401 - stub class
        def __init__(self, *args, **kwargs):
            pass

        def show(self):  # noqa: D401 - stub method
            return None

    def _show_error_dialog(*args, **kwargs):  # noqa: D401 - stub function
        return None

    error_dialog_module.ErrorDialog = _ErrorDialog
    error_dialog_module.show_error_dialog = _show_error_dialog

    common_module.notification = notification_module
    common_module.progress_bar = progress_module
    common_module.error_dialog = error_dialog_module

    sys.modules["ui.common.notification"] = notification_module
    sys.modules["ui.common.progress_bar"] = progress_module
    sys.modules["ui.common.error_dialog"] = error_dialog_module


_ensure_ui_common_stubs()


def _ensure_httpx_stub():
    if "httpx" in sys.modules:
        return

    httpx_module = types.ModuleType("httpx")

    class _HTTPError(Exception):
        pass

    class _HTTPStatusError(_HTTPError):
        def __init__(self, message: str = "", request=None, response=None):
            super().__init__(message)
            self.response = response

    class _TimeoutException(_HTTPError):
        pass

    class _ConnectError(_HTTPError):
        pass

    class _NetworkError(_HTTPError):
        pass

    class _StubResponse:
        def __init__(self, status_code: int = 200, json_data=None, headers=None):
            self.status_code = status_code
            self._json_data = json_data or {}
            self.headers = headers or {}

        def json(self):  # pragma: no cover - simple stub
            return self._json_data

        def raise_for_status(self):  # pragma: no cover - simple stub
            if self.status_code >= 400:
                raise _HTTPStatusError("stub error", response=self)

    class _StubClient:  # pragma: no cover - simple stub
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def request(self, method, url, **kwargs):
            return _StubResponse()

        def post(self, url, **kwargs):
            return _StubResponse()

        def close(self):
            return None

    httpx_module.Client = _StubClient
    httpx_module.Response = _StubResponse
    httpx_module.HTTPError = _HTTPError
    httpx_module.HTTPStatusError = _HTTPStatusError
    httpx_module.TimeoutException = _TimeoutException
    httpx_module.ConnectError = _ConnectError
    httpx_module.NetworkError = _NetworkError

    sys.modules["httpx"] = httpx_module


_ensure_httpx_stub()


def _ensure_apscheduler_stub():
    if "apscheduler" in sys.modules:
        return

    apscheduler_module = types.ModuleType("apscheduler")
    schedulers_module = types.ModuleType("apscheduler.schedulers")
    background_module = types.ModuleType("apscheduler.schedulers.background")
    triggers_module = types.ModuleType("apscheduler.triggers")
    interval_module = types.ModuleType("apscheduler.triggers.interval")

    class _BackgroundScheduler:  # pragma: no cover - simple stub
        def __init__(self, *args, **kwargs):
            pass

        def start(self):  # pragma: no cover - simple stub
            pass

        def shutdown(self, *args, **kwargs):  # pragma: no cover - simple stub
            pass

    class _IntervalTrigger:  # pragma: no cover - simple stub
        def __init__(self, *args, **kwargs):
            pass

    background_module.BackgroundScheduler = _BackgroundScheduler
    schedulers_module.background = background_module
    interval_module.IntervalTrigger = _IntervalTrigger
    triggers_module.interval = interval_module
    apscheduler_module.schedulers = schedulers_module
    apscheduler_module.triggers = triggers_module

    sys.modules["apscheduler"] = apscheduler_module
    sys.modules["apscheduler.schedulers"] = schedulers_module
    sys.modules["apscheduler.schedulers.background"] = background_module
    sys.modules["apscheduler.triggers"] = triggers_module
    sys.modules["apscheduler.triggers.interval"] = interval_module


_ensure_apscheduler_stub()


from core.calendar.manager import CalendarManager
from core.timeline.manager import TimelineManager
from core.timeline.auto_task_scheduler import AutoTaskScheduler
from data.database.connection import DatabaseConnection
from data.database.models import CalendarEvent, CalendarEventLink, EventAttachment
from data.storage.file_manager import FileManager
from unittest.mock import Mock

from engines.calendar_sync.google_calendar import GoogleCalendarAdapter


def _create_db(tmp_path: Path) -> DatabaseConnection:
    db_path = tmp_path / "calendar.db"
    db = DatabaseConnection(str(db_path))
    db.initialize_schema()
    return db


class DummySyncAdapter:
    def __init__(self, provider: str):
        self.provider = provider

    def push_event(self, event: CalendarEvent) -> str:  # pragma: no cover - simple stub
        return f"{self.provider}-{event.id}"


class RecordingAdapter:
    def __init__(self):
        self.google_adapter = GoogleCalendarAdapter(
            client_id="id",
            client_secret="secret",
            redirect_uri="http://localhost/callback",
        )
        self.last_payload = None
        self.last_external_id = None

    def update_event(self, event: CalendarEvent, external_id: str):
        self.last_payload = self.google_adapter._convert_to_google_event(event)
        self.last_external_id = external_id


def test_create_event_accepts_datetime_objects(tmp_path):
    db = _create_db(tmp_path)
    manager = CalendarManager(db)

    start_dt = datetime(2024, 5, 1, 9, 0, tzinfo=timezone.utc)
    end_dt = start_dt + timedelta(hours=1)

    event_data = {
        "title": "Team Sync",
        "event_type": "Event",
        "start_time": start_dt,
        "end_time": end_dt,
    }

    event_id = manager.create_event(event_data)

    assert isinstance(event_data["start_time"], str)
    assert isinstance(event_data["end_time"], str)

    rows = db.execute(
        "SELECT start_time, end_time FROM calendar_events WHERE id = ?",
        (event_id,),
    )
    assert rows
    row = rows[0]
    assert row["start_time"] == event_data["start_time"]
    assert row["end_time"] == event_data["end_time"]

    db.close_all()


def test_create_event_accepts_z_timezone_strings(tmp_path):
    db = _create_db(tmp_path)
    manager = CalendarManager(db)

    event_data = {
        "title": "Team Sync",
        "event_type": "Event",
        "start_time": "2024-05-01T09:00:00Z",
        "end_time": "2024-05-01T10:00:00Z",
    }

    event_id = manager.create_event(event_data)

    assert event_data["start_time"].endswith("+00:00")
    assert event_data["end_time"].endswith("+00:00")

    rows = db.execute(
        "SELECT start_time, end_time FROM calendar_events WHERE id = ?",
        (event_id,),
    )
    assert rows
    row = rows[0]
    assert row["start_time"] == event_data["start_time"]
    assert row["end_time"] == event_data["end_time"]

    db.close_all()


def test_create_event_normalizes_mixed_timezone_inputs(tmp_path):
    db = _create_db(tmp_path)
    manager = CalendarManager(db)

    event_data = {
        "title": "Hybrid Timezone Meeting",
        "event_type": "Event",
        "start_time": "2024-05-01T09:00:00+02:00",
        "end_time": "2024-05-01T10:30:00",
    }

    event_id = manager.create_event(event_data)

    rows = db.execute(
        "SELECT start_time, end_time FROM calendar_events WHERE id = ?",
        (event_id,),
    )
    assert rows
    stored_start = rows[0]["start_time"]
    stored_end = rows[0]["end_time"]

    start_dt = datetime.fromisoformat(stored_start)
    end_dt = datetime.fromisoformat(stored_end)

    assert start_dt.tzinfo == timezone.utc
    assert end_dt.tzinfo == timezone.utc

    source_tz = timezone(timedelta(hours=2))
    expected_start = datetime(2024, 5, 1, 9, 0, tzinfo=source_tz)
    expected_end = datetime(2024, 5, 1, 10, 30, tzinfo=source_tz)

    assert start_dt.astimezone(source_tz) == expected_start
    assert end_dt.astimezone(source_tz) == expected_end

    db.close_all()


def test_multi_provider_links_are_persisted_and_retrievable(tmp_path):
    db = _create_db(tmp_path)

    adapters = {
        "google": DummySyncAdapter("google"),
        "outlook": DummySyncAdapter("outlook"),
    }

    manager = CalendarManager(db, sync_adapters=adapters)

    event_data = {
        "title": "Team Sync",
        "event_type": "Event",
        "start_time": datetime(2024, 5, 1, 9, 0, tzinfo=timezone.utc),
        "end_time": datetime(2024, 5, 1, 10, 0, tzinfo=timezone.utc),
    }

    event_id = manager.create_event(event_data, sync_to=["google", "outlook"])

    link_rows = db.execute(
        "SELECT provider, external_id, last_synced_at "
        "FROM calendar_event_links WHERE event_id = ?",
        (event_id,),
    )
    assert len(link_rows) == 2
    providers = {row["provider"] for row in link_rows}
    assert providers == {"google", "outlook"}
    assert all(row["last_synced_at"] for row in link_rows)

    event_rows = db.execute(
        "SELECT external_id FROM calendar_events WHERE id = ?",
        (event_id,),
    )
    assert event_rows
    assert event_rows[0]["external_id"] is None

    google_update = {
        "id": f"google-{event_id}",
        "title": "Team Sync (Google)",
        "start_time": event_data["start_time"],
        "end_time": event_data["end_time"],
        "attendees": ["alice@example.com"],
    }
    manager._save_external_event(google_update, "google")

    refreshed_event = CalendarEvent.get_by_id(db, event_id)
    assert refreshed_event is not None
    assert refreshed_event.title == "Team Sync (Google)"
    assert refreshed_event.attendees == ["alice@example.com"]

    outlook_update = {
        "id": f"outlook-{event_id}",
        "description": "Imported from Outlook",
        "start_time": event_data["start_time"],
        "end_time": event_data["end_time"],
    }
    manager._save_external_event(outlook_update, "outlook")

    refreshed_event = CalendarEvent.get_by_id(db, event_id)
    assert refreshed_event is not None
    assert refreshed_event.description == "Imported from Outlook"

    post_update_links = db.execute(
        "SELECT provider, event_id FROM calendar_event_links WHERE event_id = ?",
        (event_id,),
    )
    assert len(post_update_links) == 2
    assert {row["provider"] for row in post_update_links} == {"google", "outlook"}

    db.close_all()


def test_save_external_event_accepts_z_timezone_strings(tmp_path):
    db = _create_db(tmp_path)
    manager = CalendarManager(db)

    ext_event = {
        "id": "google-z-time",
        "title": "External Z Event",
        "start_time": "2024-07-01T09:00:00Z",
        "end_time": "2024-07-01T10:00:00Z",
        "attendees": ["alice@example.com"],
    }

    manager._save_external_event(ext_event, "google")

    link = CalendarEventLink.get_by_provider_and_external_id(
        db,
        "google",
        "google-z-time",
    )
    assert link is not None

    event = CalendarEvent.get_by_id(db, link.event_id)
    assert event is not None
    assert event.start_time.endswith("+00:00")
    assert event.end_time.endswith("+00:00")

    start_dt = datetime.fromisoformat(event.start_time)
    end_dt = datetime.fromisoformat(event.end_time)
    assert start_dt.tzinfo == timezone.utc
    assert end_dt.tzinfo == timezone.utc

    db.close_all()


def test_save_external_event_normalizes_mixed_timezone_inputs(tmp_path):
    db = _create_db(tmp_path)
    manager = CalendarManager(db)

    ext_event = {
        "id": "google-mixed-time",
        "title": "External Mixed Time",
        "start_time": "2024-07-02T09:00:00+02:00",
        "end_time": "2024-07-02T10:45:00",
    }

    manager._save_external_event(ext_event, "google")

    link = CalendarEventLink.get_by_provider_and_external_id(
        db,
        "google",
        "google-mixed-time",
    )
    assert link is not None

    event = CalendarEvent.get_by_id(db, link.event_id)
    assert event is not None

    start_dt = datetime.fromisoformat(event.start_time)
    end_dt = datetime.fromisoformat(event.end_time)

    assert start_dt.tzinfo == timezone.utc
    assert end_dt.tzinfo == timezone.utc

    source_tz = timezone(timedelta(hours=2))
    expected_start = datetime(2024, 7, 2, 9, 0, tzinfo=source_tz)
    expected_end = datetime(2024, 7, 2, 10, 45, tzinfo=source_tz)

    assert start_dt.astimezone(source_tz) == expected_start
    assert end_dt.astimezone(source_tz) == expected_end

    db.close_all()


def test_external_event_without_end_time_is_normalized(tmp_path, monkeypatch):
    db = _create_db(tmp_path)
    manager = CalendarManager(db)

    start_dt = datetime(2024, 6, 1, 9, 0, tzinfo=timezone.utc)
    ext_event = {
        "id": "google-missing-end",
        "title": "External Without End",
        "start_time": start_dt.isoformat(),
        # end_time intentionally omitted
        "attendees": {"alice@example.com"},
    }

    manager._save_external_event(ext_event, "google")

    link = CalendarEventLink.get_by_provider_and_external_id(
        db,
        "google",
        "google-missing-end",
    )
    assert link is not None

    event = CalendarEvent.get_by_id(db, link.event_id)
    assert event is not None
    assert event.end_time

    start_value = datetime.fromisoformat(event.start_time)
    end_value = datetime.fromisoformat(event.end_time)
    assert end_value >= start_value

    timeline_manager = TimelineManager(manager, db)
    timeline_data = timeline_manager.get_timeline_events(
        center_time=start_dt - timedelta(hours=1),
        past_days=1,
        future_days=1,
    )
    future_ids = [item['event'].id for item in timeline_data['future_events']]
    assert event.id in future_ids

    class DummyNotificationManager:
        def send_info(self, *args, **kwargs):  # noqa: D401
            return None

        def send_warning(self, *args, **kwargs):  # noqa: D401
            return None

        def send_success(self, *args, **kwargs):  # noqa: D401
            return None

        def send_error(self, *args, **kwargs):  # noqa: D401
            return None

    monkeypatch.setattr(
        'core.timeline.auto_task_scheduler.get_notification_manager',
        lambda: DummyNotificationManager(),
    )

    class DummyRecorder:
        async def start_recording(self, *args, **kwargs):  # noqa: D401
            return None

        async def stop_recording(self):  # noqa: D401
            return {}

    scheduler = AutoTaskScheduler(
        timeline_manager=timeline_manager,
        realtime_recorder=DummyRecorder(),
        db_connection=db,
        file_manager=None,
        reminder_minutes=5,
    )

    from datetime import datetime as real_datetime

    current_time = {
        'value': (start_dt - timedelta(minutes=10)).astimezone(timezone.utc)
    }

    class FlexibleDateTime(real_datetime):
        @classmethod
        def now(cls, tz=None):  # noqa: D401
            current = current_time['value']
            if tz is None:
                return current
            return current.astimezone(tz)

        @classmethod
        def fromisoformat(cls, date_string):  # noqa: D401
            return real_datetime.fromisoformat(date_string)

    monkeypatch.setattr(
        'core.timeline.auto_task_scheduler.datetime',
        FlexibleDateTime,
    )

    scheduler._check_upcoming_events()

    scheduler.active_recordings[event.id] = {}
    current_time['value'] = (start_dt + timedelta(minutes=2)).astimezone(timezone.utc)

    scheduler._check_upcoming_events()

    db.close_all()


def test_update_event_accepts_datetime_objects(tmp_path):
    db = _create_db(tmp_path)

    existing = CalendarEvent(
        title="Team Sync",
        start_time="2024-05-01T09:00:00",
        end_time="2024-05-01T10:00:00",
    )
    existing.save(db)

    manager = CalendarManager(db)

    new_start = datetime(2024, 5, 1, 10, 0, 0)
    new_end = new_start + timedelta(hours=1)

    update_data = {
        "start_time": new_start,
        "end_time": new_end,
    }

    manager.update_event(existing.id, update_data)

    assert isinstance(update_data["start_time"], str)
    assert isinstance(update_data["end_time"], str)

    rows = db.execute(
        "SELECT start_time, end_time FROM calendar_events WHERE id = ?",
        (existing.id,),
    )
    assert rows
    row = rows[0]
    assert row["start_time"] == update_data["start_time"]
    assert row["end_time"] == update_data["end_time"]

    db.close_all()


def test_update_event_triggers_external_sync(tmp_path):
    db = _create_db(tmp_path)

    existing = CalendarEvent(
        title="Team Sync",
        start_time="2024-05-01T09:00:00",
        end_time="2024-05-01T10:00:00",
    )
    existing.save(db)

    link = CalendarEventLink(
        event_id=existing.id,
        provider="google",
        external_id="google-123",
    )
    link.save(db)

    adapter = Mock()
    manager = CalendarManager(db, sync_adapters={"google": adapter})

    manager.update_event(existing.id, {"title": "Updated"})

    assert adapter.update_event.call_count == 1
    args, kwargs = adapter.update_event.call_args
    assert not kwargs
    synced_event, synced_external_id = args
    assert synced_event.id == existing.id
    assert synced_external_id == "google-123"

    refreshed_link = CalendarEventLink.get_by_event_and_provider(
        db,
        existing.id,
        "google",
    )
    assert refreshed_link is not None
    assert refreshed_link.last_synced_at is not None

    db.close_all()


def test_delete_event_requires_external_cleanup(tmp_path):
    db = _create_db(tmp_path)

    existing = CalendarEvent(
        title="Team Sync",
        start_time="2024-05-01T09:00:00",
        end_time="2024-05-01T10:00:00",
    )
    existing.save(db)

    link = CalendarEventLink(
        event_id=existing.id,
        provider="google",
        external_id="google-123",
    )
    link.save(db)

    adapter = Mock()
    manager = CalendarManager(db, sync_adapters={"google": adapter})

    manager.delete_event(existing.id)

    adapter.delete_event.assert_called_once()
    args, kwargs = adapter.delete_event.call_args
    assert not kwargs
    deleted_event, external_id = args
    assert deleted_event.id == existing.id
    assert external_id == "google-123"

    rows = db.execute(
        "SELECT * FROM calendar_events WHERE id = ?",
        (existing.id,),
    )
    assert not rows

    link_rows = db.execute(
        "SELECT * FROM calendar_event_links WHERE event_id = ?",
        (existing.id,),
    )
    assert not link_rows

    db.close_all()


def test_delete_event_stops_when_external_deletion_fails(tmp_path):
    db = _create_db(tmp_path)

    existing = CalendarEvent(
        title="Team Sync",
        start_time="2024-05-01T09:00:00",
        end_time="2024-05-01T10:00:00",
    )
    existing.save(db)

    CalendarEventLink(
        event_id=existing.id,
        provider="google",
        external_id="google-123",
    ).save(db)

    failing_adapter = Mock()
    failing_adapter.delete_event.side_effect = RuntimeError("api down")

    manager = CalendarManager(db, sync_adapters={"google": failing_adapter})

    with pytest.raises(RuntimeError):
        manager.delete_event(existing.id)

    # Event should still exist locally
    remaining = CalendarEvent.get_by_id(db, existing.id)
    assert remaining is not None

    db.close_all()


def test_delete_event_cleans_attachments_and_files(tmp_path):
    db = _create_db(tmp_path)
    storage_root = tmp_path / "storage"
    file_manager = FileManager(base_dir=str(storage_root))

    existing = CalendarEvent(
        title="All Hands",
        start_time="2024-06-01T09:00:00",
        end_time="2024-06-01T10:00:00",
    )
    existing.save(db)

    file_path = file_manager.save_text_file("hello", "notes.txt")
    EventAttachment(
        event_id=existing.id,
        attachment_type="transcript",
        file_path=file_path,
    ).save(db)

    manager = CalendarManager(db, file_manager=file_manager)

    manager.delete_event(existing.id)

    assert CalendarEvent.get_by_id(db, existing.id) is None
    assert not EventAttachment.get_by_event_id(db, existing.id)
    assert not Path(file_path).exists()

    db.close_all()


def test_delete_event_without_attachments(tmp_path):
    db = _create_db(tmp_path)
    manager = CalendarManager(db, file_manager=FileManager(base_dir=str(tmp_path / "storage")))

    existing = CalendarEvent(
        title="Planning",
        start_time="2024-06-02T09:00:00",
        end_time="2024-06-02T10:00:00",
    )
    existing.save(db)

    manager.delete_event(existing.id)

    assert CalendarEvent.get_by_id(db, existing.id) is None
    assert not EventAttachment.get_by_event_id(db, existing.id)

    db.close_all()


def test_remove_external_event_retains_shared_event(tmp_path):
    db = _create_db(tmp_path)
    manager = CalendarManager(db)

    shared_event = CalendarEvent(
        title="Cross Provider Sync",
        start_time="2024-05-01T09:00:00",
        end_time="2024-05-01T10:00:00",
        source="google",
        is_readonly=True,
    )
    shared_event.save(db)

    attachment = EventAttachment(
        event_id=shared_event.id,
        attachment_type="recording",
        file_path="/tmp/shared.wav",
    )
    attachment.save(db)

    CalendarEventLink(
        event_id=shared_event.id,
        provider="google",
        external_id="google-evt-1",
    ).save(db)
    CalendarEventLink(
        event_id=shared_event.id,
        provider="outlook",
        external_id="outlook-evt-1",
    ).save(db)

    manager._remove_external_event(shared_event.id, "google", "google-evt-1")

    # Event should still exist because another provider references it
    persisted_event = CalendarEvent.get_by_id(db, shared_event.id)
    assert persisted_event is not None

    google_link = CalendarEventLink.get_by_event_and_provider(
        db,
        shared_event.id,
        "google",
    )
    assert google_link is None

    remaining_links = CalendarEventLink.list_for_event(db, shared_event.id)
    assert len(remaining_links) == 1
    assert remaining_links[0].provider == "outlook"

    attachments = EventAttachment.get_by_event_id(db, shared_event.id)
    assert len(attachments) == 1
    assert attachments[0].id == attachment.id

    db.close_all()


def test_remove_external_event_cleans_single_provider_event(tmp_path):
    db = _create_db(tmp_path)
    manager = CalendarManager(db)

    single_event = CalendarEvent(
        title="Google Only",
        start_time="2024-05-02T09:00:00",
        end_time="2024-05-02T10:00:00",
        source="google",
        is_readonly=True,
    )
    single_event.save(db)

    attachment = EventAttachment(
        event_id=single_event.id,
        attachment_type="transcript",
        file_path="/tmp/single.txt",
    )
    attachment.save(db)

    CalendarEventLink(
        event_id=single_event.id,
        provider="google",
        external_id="google-evt-2",
    ).save(db)

    manager._remove_external_event(single_event.id, "google", "google-evt-2")

    assert CalendarEvent.get_by_id(db, single_event.id) is None
    assert not CalendarEventLink.list_for_event(db, single_event.id)
    assert not EventAttachment.get_by_event_id(db, single_event.id)

    db.close_all()


def test_calendar_event_all_day_detection_variants():
    date_only = CalendarEvent(
        title="全天",
        start_time="2024-05-01",
        end_time="2024-05-02",
    )
    assert date_only.is_all_day_event()

    iso_midnight = CalendarEvent(
        title="全天",
        start_time="2024-05-01T00:00:00",
        end_time="2024-05-03T00:00:00",
    )
    assert iso_midnight.is_all_day_event()

    timed = CalendarEvent(
        title="定时",
        start_time="2024-05-01T09:00:00",
        end_time="2024-05-01T10:00:00",
    )
    assert not timed.is_all_day_event()


def test_google_adapter_converts_all_day_event():
    adapter = GoogleCalendarAdapter(
        client_id="id",
        client_secret="secret",
        redirect_uri="http://localhost/callback",
    )
    event = CalendarEvent(
        title="全天会议",
        start_time="2024-05-01",
        end_time="2024-05-02",
    )

    google_event = adapter._convert_to_google_event(event)

    assert google_event['start'] == {'date': '2024-05-01'}
    assert google_event['end'] == {'date': '2024-05-02'}


def test_google_adapter_converts_timed_event(monkeypatch):
    monkeypatch.setenv('ECHONOTE_LOCAL_TIMEZONE', 'Asia/Shanghai')

    adapter = GoogleCalendarAdapter(
        client_id="id",
        client_secret="secret",
        redirect_uri="http://localhost/callback",
    )
    event = CalendarEvent(
        title="定时会议",
        start_time="2024-05-01T09:00:00",
        end_time="2024-05-01T10:30:00",
    )

    google_event = adapter._convert_to_google_event(event)

    assert google_event['start'] == {
        'dateTime': '2024-05-01T09:00:00+08:00',
        'timeZone': 'Asia/Shanghai',
    }
    assert google_event['end'] == {
        'dateTime': '2024-05-01T10:30:00+08:00',
        'timeZone': 'Asia/Shanghai',
    }


def test_all_day_event_round_trip_sync(tmp_path):
    db = _create_db(tmp_path)
    recorder = RecordingAdapter()
    manager = CalendarManager(db, sync_adapters={"google": recorder})

    event = CalendarEvent(
        title="全天会议",
        start_time="2024-05-10",
        end_time="2024-05-11",
        source="google",
        external_id="evt-1",
    )
    event.save(db)

    CalendarEventLink(
        event_id=event.id,
        provider="google",
        external_id="evt-1",
    ).save(db)

    manager.update_event(event.id, {"title": "调整后的会议"})

    assert recorder.last_external_id == "evt-1"
    assert recorder.last_payload is not None
    assert recorder.last_payload['start'] == {'date': '2024-05-10'}
    assert recorder.last_payload['end'] == {'date': '2024-05-11'}

    db.close_all()
