import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from tests.unit.test_transcription_manager_failure import _ensure_cryptography_stubs


_ensure_cryptography_stubs()


from data.database.connection import DatabaseConnection
from data.database.encryption_helper import initialize_encryption_helper, encrypt_sensitive_field
from data.database.models import CalendarSyncStatus
from data.security.encryption import SecurityManager


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
