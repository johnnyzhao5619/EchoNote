import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from tests.unit.test_transcription_manager_failure import _ensure_cryptography_stubs
from tests.unit.test_calendar_manager import _ensure_apscheduler_stub


_ensure_cryptography_stubs()
_ensure_apscheduler_stub()


from data.database.connection import DatabaseConnection
from data.database.encryption_helper import initialize_encryption_helper, encrypt_sensitive_field
from core.calendar.manager import CalendarManager
from data.database.models import (
    CalendarEvent,
    CalendarEventLink,
    CalendarSyncStatus,
    EventAttachment,
)
from data.security.encryption import SecurityManager


class _StubCalendarAdapter:
    """Minimal calendar adapter stub for integration tests."""

    def __init__(
        self,
        events: List[Dict[str, Any]],
        deleted: Optional[List[str]] = None,
        sync_token: str = "sync-token-next",
    ) -> None:
        self._events = events
        self._deleted = deleted or []
        self._sync_token = sync_token

    def fetch_events(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        last_sync_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        return {
            'events': list(self._events),
            'deleted': list(self._deleted),
            'sync_token': self._sync_token,
        }

    # The manager only calls fetch_events in this test suite. Define placeholders
    # for the remaining adapter methods to satisfy the interface expectations if
    # they are ever used elsewhere.
    def authenticate(self, credentials: dict) -> dict:  # pragma: no cover - unused in tests
        raise NotImplementedError

    def push_event(self, event):  # pragma: no cover - unused in tests
        raise NotImplementedError

    def update_event(self, event, external_id):  # pragma: no cover - unused in tests
        raise NotImplementedError

    def delete_event(self, event, external_id):  # pragma: no cover - unused in tests
        raise NotImplementedError

    def revoke_access(self):  # pragma: no cover - unused in tests
        raise NotImplementedError


def test_calendar_reauthorization_keeps_single_active_status(tmp_path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()

    security_manager = SecurityManager(str(config_dir))
    initialize_encryption_helper(security_manager)

    db_path = tmp_path / "calendar.db"
    db = DatabaseConnection(str(db_path))
    db.initialize_schema()

    def active_count() -> int:
        rows = db.execute(
            "SELECT COUNT(*) as count FROM calendar_sync_status WHERE provider = ? AND is_active = 1",
            ("google",),
        )
        return rows[0]["count"] if rows else 0

    # First authorization persists an active status with a sync token.
    status = CalendarSyncStatus(
        provider="google",
        user_email="user@example.com",
        sync_token="sync-token-v1",
        last_sync_time="2024-01-01T00:00:00",
    )
    status.save(db)

    assert active_count() == 1

    # Re-authorization should reuse the same record, clear stale sync data, and stay active.
    existing = CalendarSyncStatus.get_by_provider(db, "google")
    assert existing is not None
    assert existing.id == status.id

    existing.user_email = "new@example.com"
    existing.sync_token = None
    existing.last_sync_time = None
    existing.is_active = True
    existing.save(db)

    assert active_count() == 1

    refreshed = CalendarSyncStatus.get_by_provider(db, "google")
    assert refreshed is not None
    assert refreshed.user_email == "new@example.com"
    assert refreshed.sync_token is None

    # After the initial post-authorization sync, a new sync token is stored.
    refreshed.sync_token = "sync-token-v2"
    refreshed.last_sync_time = "2024-01-02T00:00:00"
    refreshed.save(db)

    latest = CalendarSyncStatus.get_by_provider(db, "google")
    assert latest is not None
    assert latest.sync_token == "sync-token-v2"
    assert latest.last_sync_time == "2024-01-02T00:00:00"

    # Inject a legacy duplicate to emulate older builds that allowed multiple active rows.
    db.execute(
        """
        INSERT INTO calendar_sync_status (
            id, provider, user_email, last_sync_time, sync_token,
            is_active, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """,
        (
            "legacy-google-row",
            "google",
            "legacy@example.com",
            None,
            encrypt_sensitive_field("legacy-token"),
        ),
        commit=True,
    )

    assert active_count() == 2

    # Saving the legitimate record again should deactivate the legacy row and clear its sync token.
    latest.is_active = True
    latest.sync_token = "sync-token-v3"
    latest.save(db)

    assert active_count() == 1

    newest = CalendarSyncStatus.get_by_provider(db, "google")
    assert newest is not None
    assert newest.id == latest.id
    assert newest.sync_token == "sync-token-v3"

    legacy_rows = db.execute(
        "SELECT is_active, sync_token FROM calendar_sync_status WHERE id = ?",
        ("legacy-google-row",),
    )
    assert legacy_rows
    assert legacy_rows[0]["is_active"] == 0
    assert legacy_rows[0]["sync_token"] is None

    db.close_all()


def test_sync_removes_cancelled_and_missing_remote_events(tmp_path):
    config_dir = tmp_path / "sync-config"
    config_dir.mkdir()

    security_manager = SecurityManager(str(config_dir))
    initialize_encryption_helper(security_manager)

    db_path = tmp_path / "calendar.db"
    db = DatabaseConnection(str(db_path))
    db.initialize_schema()

    keep_event = CalendarEvent(
        title="Keep",
        start_time="2024-03-01T09:00:00+00:00",
        end_time="2024-03-01T10:00:00+00:00",
        source="google",
        external_id="remote-keep",
        is_readonly=True,
    )
    keep_event.save(db)
    CalendarEventLink(
        event_id=keep_event.id,
        provider="google",
        external_id="remote-keep",
    ).save(db)

    cancelled_event = CalendarEvent(
        title="Cancelled",
        start_time="2024-03-02T09:00:00+00:00",
        end_time="2024-03-02T10:00:00+00:00",
        source="google",
        external_id="remote-cancelled",
        is_readonly=True,
    )
    cancelled_event.save(db)
    CalendarEventLink(
        event_id=cancelled_event.id,
        provider="google",
        external_id="remote-cancelled",
    ).save(db)

    EventAttachment(
        event_id=cancelled_event.id,
        attachment_type="recording",
        file_path="recording.wav",
    ).save(db)

    missing_event = CalendarEvent(
        title="Missing",
        start_time="2024-03-03T09:00:00+00:00",
        end_time="2024-03-03T10:00:00+00:00",
        source="google",
        external_id="remote-missing",
        is_readonly=True,
    )
    missing_event.save(db)
    CalendarEventLink(
        event_id=missing_event.id,
        provider="google",
        external_id="remote-missing",
    ).save(db)

    CalendarSyncStatus(
        provider="google",
        user_email="user@example.com",
        sync_token="sync-token-old",
    ).save(db)

    adapter = _StubCalendarAdapter(
        events=[
            {
                'id': 'remote-keep',
                'title': 'Keep Updated',
                'event_type': 'Event',
                'start_time': '2024-03-01T09:00:00+00:00',
                'end_time': '2024-03-01T10:00:00+00:00',
                'location': 'Remote Room',
                'attendees': ['a@example.com'],
                'description': 'Refreshed details',
            },
            {'id': 'remote-cancelled', 'deleted': True},
        ],
        deleted=['remote-missing'],
        sync_token='sync-token-new',
    )

    manager = CalendarManager(
        db_connection=db,
        sync_adapters={'google': adapter},
    )
    manager.sync_external_calendar('google')

    refreshed_status = CalendarSyncStatus.get_by_provider(db, 'google')
    assert refreshed_status is not None
    assert refreshed_status.sync_token == 'sync-token-new'

    updated_event = CalendarEvent.get_by_id(db, keep_event.id)
    assert updated_event is not None
    assert updated_event.title == 'Keep Updated'

    keep_link = CalendarEventLink.get_by_provider_and_external_id(
        db,
        'google',
        'remote-keep',
    )
    assert keep_link is not None

    assert CalendarEvent.get_by_id(db, cancelled_event.id) is None
    assert (
        CalendarEventLink.get_by_provider_and_external_id(
            db,
            'google',
            'remote-cancelled',
        )
        is None
    )
    assert not EventAttachment.get_by_event_id(db, cancelled_event.id)

    assert CalendarEvent.get_by_id(db, missing_event.id) is None
    assert (
        CalendarEventLink.get_by_provider_and_external_id(
            db,
            'google',
            'remote-missing',
        )
        is None
    )

    db.close_all()
