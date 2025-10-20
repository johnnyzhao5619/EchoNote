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
from data.database.connection import DatabaseConnection
from data.database.models import CalendarEvent, CalendarEventLink, EventAttachment
from unittest.mock import Mock


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
