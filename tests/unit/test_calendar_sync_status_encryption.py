import os
import stat
import sys
import uuid
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from tests.unit.test_transcription_manager_failure import _ensure_cryptography_stubs


_ensure_cryptography_stubs()


from data.database.connection import DatabaseConnection
from data.database.encryption_helper import initialize_encryption_helper
from data.database.models import CalendarSyncStatus
from data.security import encryption as encryption_module
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


def test_security_manager_password_hashing_migration(tmp_path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()

    security_manager = SecurityManager(str(config_dir))

    password = "StrongPass!123"
    new_hash = security_manager.hash_password(password)

    assert "$" in new_hash
    assert security_manager.verify_password(password, new_hash)
    is_valid, migrated = security_manager.verify_password(
        password,
        new_hash,
        return_new_hash=True,
    )
    assert is_valid and migrated is None

    legacy_hash = security_manager._legacy_hash_password(password)

    is_valid, migrated = security_manager.verify_password(
        password,
        legacy_hash,
        return_new_hash=True,
    )
    assert is_valid
    assert migrated is not None and "$" in migrated
    assert not security_manager.verify_password("wrong", legacy_hash)


def test_security_manager_persists_fallback_uuid(tmp_path, monkeypatch):
    config_dir = tmp_path / "config"
    config_dir.mkdir()

    fallback_file = config_dir / ".machine-uuid"

    original_exists = encryption_module.os.path.exists

    def fake_exists(path):
        if path in {"/etc/machine-id", "/var/lib/dbus/machine-id"}:
            return False
        return original_exists(path)

    def raise_getnode():
        raise RuntimeError("no mac address available")

    generated_values: list[str] = []

    def fake_uuid4():
        if not generated_values:
            value = uuid.UUID("11111111-1111-1111-1111-111111111111")
        else:
            value = uuid.UUID("22222222-2222-2222-2222-222222222222")
        generated_values.append(str(value))
        return value

    monkeypatch.setattr(encryption_module.os.path, "exists", fake_exists)
    monkeypatch.setattr(encryption_module.uuid, "getnode", raise_getnode)
    monkeypatch.setattr(encryption_module.uuid, "uuid4", fake_uuid4)

    security_manager_first = SecurityManager(str(config_dir))

    secret = "top secret"
    encrypted = security_manager_first.encrypt(secret)

    assert fallback_file.exists()
    assert fallback_file.read_text().strip() == generated_values[0]
    assert stat.S_IMODE(os.stat(fallback_file).st_mode) == 0o600

    security_manager_second = SecurityManager(str(config_dir))

    assert security_manager_second.decrypt(encrypted) == secret
    assert len(generated_values) == 1
