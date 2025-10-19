import sys
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


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
from data.database.models import CalendarEvent


def _create_db(tmp_path: Path) -> DatabaseConnection:
    db_path = tmp_path / "calendar.db"
    db = DatabaseConnection(str(db_path))
    db.initialize_schema()
    return db


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
