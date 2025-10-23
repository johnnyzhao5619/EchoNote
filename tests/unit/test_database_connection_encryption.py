import logging
import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from data.database.connection import DatabaseConnection
try:
    from data.security.encryption import SecurityManager
except ModuleNotFoundError:  # pragma: no cover - optional dependency for tests
    SecurityManager = None


def test_database_connection_handles_quoted_encryption_key(tmp_path):
    db_path = tmp_path / "quoted_key.db"
    encryption_key = "pa'ss\"word;--"

    db = DatabaseConnection(str(db_path), encryption_key=encryption_key)

    db.execute(
        "CREATE TABLE test_table (id INTEGER PRIMARY KEY, value TEXT)",
        commit=True,
    )
    db.execute(
        "INSERT INTO test_table (value) VALUES (?)",
        ("secure",),
        commit=True,
    )

    rows = db.execute("SELECT value FROM test_table")

    assert rows[0]["value"] == "secure"


def test_first_run_initialization_preserves_encryption_intent(tmp_path, caplog):
    config_dir = tmp_path / "config"
    config_dir.mkdir()

    if SecurityManager is None:
        pytest.skip("cryptography dependency is required for SecurityManager")

    pytest.importorskip("psutil")

    from utils.first_run_setup import FirstRunSetup  # Local import to avoid importing heavy dependencies when unused

    security_manager = SecurityManager(str(config_dir))

    caplog.set_level(logging.WARNING)

    FirstRunSetup._initialize_database(config_dir, security_manager=security_manager)

    db_path = config_dir / "data.db"
    assert db_path.exists()

    encryption_key = security_manager.encryption_key[:32].hex()

    first_connection = DatabaseConnection(str(db_path), encryption_key=encryption_key)
    second_connection = DatabaseConnection(str(db_path), encryption_key=encryption_key)

    first_status = first_connection.is_encryption_enabled()
    second_status = second_connection.is_encryption_enabled()

    assert second_status == first_status

    if not first_status:
        warning_messages = [record.message.lower() for record in caplog.records]
        assert any("remains unencrypted" in message for message in warning_messages)
    else:
        assert not caplog.records
