import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from tests.unit.test_transcription_manager_failure import _ensure_cryptography_stubs


_ensure_cryptography_stubs()


from data.database.connection import DatabaseConnection
from data.database.encryption_helper import initialize_encryption_helper
from data.database.models import CalendarSyncStatus
from data.security.encryption import SecurityManager


def test_calendar_sync_status_persists_encrypted_sync_token(tmp_path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()

    security_manager = SecurityManager(str(config_dir))
    initialize_encryption_helper(security_manager)

    db_path = tmp_path / "calendar.db"
    db = DatabaseConnection(str(db_path))
    db.initialize_schema()

    sync_token = "ya29.a0AfH6SMDummyToken"
    status = CalendarSyncStatus(
        provider="google",
        user_email="user@example.com",
        sync_token=sync_token,
    )
    status.save(db)

    stored_rows = db.execute(
        "SELECT sync_token FROM calendar_sync_status WHERE id = ?",
        (status.id,),
    )
    assert stored_rows, "calendar_sync_status row should exist"

    stored_value = stored_rows[0]["sync_token"]
    assert stored_value
    assert stored_value != sync_token
    assert security_manager.decrypt(stored_value) == sync_token

    retrieved = CalendarSyncStatus.get_by_provider(db, "google")
    assert retrieved is not None
    assert retrieved.sync_token == sync_token

    db.close_all()
