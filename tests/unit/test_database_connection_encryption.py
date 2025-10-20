import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from data.database.connection import DatabaseConnection


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
