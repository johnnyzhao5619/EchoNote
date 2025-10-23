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


from tests.unit.test_transcription_manager_failure import _ensure_cryptography_stubs


_ensure_cryptography_stubs()


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
