import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from tests.unit.test_transcription_manager_failure import _ensure_cryptography_stubs


_ensure_cryptography_stubs()


from data.database.connection import DatabaseConnection
from data.database.models import CalendarEvent


def _create_db(tmp_path: Path) -> DatabaseConnection:
    db_path = tmp_path / "calendar.db"
    db = DatabaseConnection(str(db_path))
    db.initialize_schema()
    return db


def test_get_by_time_range_includes_overlapping_events(tmp_path):
    db = _create_db(tmp_path)

    overlapping_event = CalendarEvent(
        title="Overlap", start_time="2024-01-01T09:00:00", end_time="2024-01-01T11:00:00"
    )
    overlapping_event.save(db)

    before_event = CalendarEvent(
        title="Before", start_time="2023-12-31T08:00:00", end_time="2023-12-31T09:00:00"
    )
    before_event.save(db)

    after_event = CalendarEvent(
        title="After", start_time="2024-01-01T12:00:00", end_time="2024-01-01T13:00:00"
    )
    after_event.save(db)

    events = CalendarEvent.get_by_time_range(
        db,
        start_time="2024-01-01T10:00:00",
        end_time="2024-01-01T12:00:00",
    )

    returned_ids = {event.id for event in events}
    assert overlapping_event.id in returned_ids
    assert before_event.id not in returned_ids
    assert after_event.id not in returned_ids

    db.close_all()


def test_get_by_time_range_respects_source_filter(tmp_path):
    db = _create_db(tmp_path)

    local_event = CalendarEvent(
        title="Local",
        start_time="2024-01-02T09:00:00",
        end_time="2024-01-02T11:00:00",
        source="local",
    )
    local_event.save(db)

    external_event = CalendarEvent(
        title="External",
        start_time="2024-01-02T09:30:00",
        end_time="2024-01-02T11:30:00",
        source="google",
    )
    external_event.save(db)

    events = CalendarEvent.get_by_time_range(
        db,
        start_time="2024-01-02T10:00:00",
        end_time="2024-01-02T12:00:00",
        source="local",
    )

    returned_ids = {event.id for event in events}
    assert returned_ids == {local_event.id}

    db.close_all()
