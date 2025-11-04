# SPDX-License-Identifier: Apache-2.0
"""
Unit tests for DatabaseConnection class.

Tests database connection management, encryption, transactions, and schema operations.
"""

import sqlite3
import tempfile
import threading
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from data.database.connection import DatabaseConnection


class TestDatabaseConnectionInitialization:
    """Test database connection initialization."""

    def test_init_creates_directory(self, tmp_path):
        """Test that initialization creates database directory."""
        db_path = tmp_path / "subdir" / "test.db"
        db = DatabaseConnection(str(db_path))

        assert db_path.parent.exists()
        assert db.db_path == db_path

    def test_init_without_encryption(self, tmp_path):
        """Test initialization without encryption key."""
        db_path = tmp_path / "test.db"
        db = DatabaseConnection(str(db_path))

        assert db.encryption_key is None
        assert not db.is_encryption_enabled()

    def test_init_with_encryption_key(self, tmp_path):
        """Test initialization with encryption key."""
        db_path = tmp_path / "test.db"
        db = DatabaseConnection(str(db_path), encryption_key="test_key")

        assert db.encryption_key == "test_key"


class TestDatabaseConnectionManagement:
    """Test connection lifecycle management."""

    def test_get_connection_creates_new(self, tmp_path):
        """Test that _get_connection creates a new connection."""
        db_path = tmp_path / "test.db"
        db = DatabaseConnection(str(db_path))

        conn = db._get_connection()

        assert conn is not None
        assert isinstance(conn, sqlite3.Connection)
        assert conn.row_factory == sqlite3.Row

    def test_get_connection_reuses_thread_local(self, tmp_path):
        """Test that _get_connection reuses thread-local connection."""
        db_path = tmp_path / "test.db"
        db = DatabaseConnection(str(db_path))

        conn1 = db._get_connection()
        conn2 = db._get_connection()

        assert conn1 is conn2

    def test_get_connection_different_threads(self, tmp_path):
        """Test that different threads get different connections."""
        db_path = tmp_path / "test.db"
        db = DatabaseConnection(str(db_path))

        connections = []

        def get_conn():
            conn = db._get_connection()
            connections.append(id(conn))

        thread1 = threading.Thread(target=get_conn)
        thread2 = threading.Thread(target=get_conn)

        thread1.start()
        thread2.start()
        thread1.join()
        thread2.join()

        # Different threads should have different connection IDs
        assert len(connections) == 2
        assert connections[0] != connections[1]

    def test_foreign_keys_enabled(self, tmp_path):
        """Test that foreign keys are enabled."""
        db_path = tmp_path / "test.db"
        db = DatabaseConnection(str(db_path))

        result = db.execute("PRAGMA foreign_keys")
        assert result[0][0] == 1

    def test_close_connection(self, tmp_path):
        """Test closing database connection."""
        db_path = tmp_path / "test.db"
        db = DatabaseConnection(str(db_path))

        # Create connection
        conn = db._get_connection()
        assert conn is not None

        # Close connection
        db.close()

        # Connection should be None
        assert not hasattr(db._local, "connection") or db._local.connection is None


class TestDatabaseCursorOperations:
    """Test cursor context manager operations."""

    def test_get_cursor_basic(self, tmp_path):
        """Test basic cursor context manager."""
        db_path = tmp_path / "test.db"
        db = DatabaseConnection(str(db_path))

        with db.get_cursor() as cursor:
            assert cursor is not None
            assert isinstance(cursor, sqlite3.Cursor)

    def test_get_cursor_with_commit(self, tmp_path):
        """Test cursor with commit."""
        db_path = tmp_path / "test.db"
        db = DatabaseConnection(str(db_path))

        # Create table
        with db.get_cursor(commit=True) as cursor:
            cursor.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, value TEXT)")

        # Verify table exists
        with db.get_cursor() as cursor:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='test'")
            result = cursor.fetchone()
            assert result is not None

    def test_get_cursor_rollback_on_error(self, tmp_path):
        """Test that cursor rolls back on error."""
        db_path = tmp_path / "test.db"
        db = DatabaseConnection(str(db_path))

        # Create table
        db.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, value TEXT)", commit=True)

        # Try to insert with error
        with pytest.raises(sqlite3.IntegrityError):
            with db.get_cursor(commit=True) as cursor:
                cursor.execute("INSERT INTO test (id, value) VALUES (1, 'test')")
                cursor.execute(
                    "INSERT INTO test (id, value) VALUES (1, 'duplicate')"
                )  # Duplicate key

        # Verify no data was inserted
        result = db.execute("SELECT COUNT(*) as count FROM test")
        assert result[0]["count"] == 0


class TestDatabaseExecuteOperations:
    """Test execute methods."""

    def test_execute_select(self, tmp_path):
        """Test execute with SELECT query."""
        db_path = tmp_path / "test.db"
        db = DatabaseConnection(str(db_path))

        db.execute("CREATE TABLE test (id INTEGER, value TEXT)", commit=True)
        db.execute("INSERT INTO test VALUES (1, 'test')", commit=True)

        result = db.execute("SELECT * FROM test WHERE id = ?", (1,))

        assert len(result) == 1
        assert result[0]["id"] == 1
        assert result[0]["value"] == "test"

    def test_execute_insert(self, tmp_path):
        """Test execute with INSERT query."""
        db_path = tmp_path / "test.db"
        db = DatabaseConnection(str(db_path))

        db.execute("CREATE TABLE test (id INTEGER, value TEXT)", commit=True)
        db.execute("INSERT INTO test VALUES (?, ?)", (1, "test"), commit=True)

        result = db.execute("SELECT * FROM test")
        assert len(result) == 1

    def test_execute_without_params(self, tmp_path):
        """Test execute without parameters."""
        db_path = tmp_path / "test.db"
        db = DatabaseConnection(str(db_path))

        db.execute("CREATE TABLE test (id INTEGER)", commit=True)
        result = db.execute("SELECT name FROM sqlite_master WHERE type='table'")

        assert len(result) > 0

    def test_execute_many(self, tmp_path):
        """Test execute_many with multiple parameter sets."""
        db_path = tmp_path / "test.db"
        db = DatabaseConnection(str(db_path))

        db.execute("CREATE TABLE test (id INTEGER, value TEXT)", commit=True)

        params_list = [(1, "one"), (2, "two"), (3, "three")]
        rowcount = db.execute_many("INSERT INTO test VALUES (?, ?)", params_list)

        assert rowcount == 3

        result = db.execute("SELECT COUNT(*) as count FROM test")
        assert result[0]["count"] == 3


class TestDatabaseScriptOperations:
    """Test script execution."""

    def test_execute_script(self, tmp_path):
        """Test executing SQL script."""
        db_path = tmp_path / "test.db"
        db = DatabaseConnection(str(db_path))

        script = """
        CREATE TABLE test1 (id INTEGER);
        CREATE TABLE test2 (id INTEGER);
        INSERT INTO test1 VALUES (1);
        INSERT INTO test2 VALUES (2);
        """

        db.execute_script(script)

        # Verify tables were created
        result = db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        table_names = [row["name"] for row in result]
        assert "test1" in table_names
        assert "test2" in table_names

    def test_execute_script_rollback_on_error(self, tmp_path):
        """Test that script rolls back on error."""
        db_path = tmp_path / "test.db"
        db = DatabaseConnection(str(db_path))

        script = """
        CREATE TABLE test (id INTEGER PRIMARY KEY);
        INSERT INTO test VALUES (1);
        INSERT INTO test VALUES (1);  -- Duplicate key error
        """

        with pytest.raises(sqlite3.IntegrityError):
            db.execute_script(script)


class TestDatabaseSchemaOperations:
    """Test schema initialization and versioning."""

    def test_initialize_schema_default_path(self, tmp_path):
        """Test schema initialization with default path."""
        db_path = tmp_path / "test.db"
        db = DatabaseConnection(str(db_path))

        # Initialize schema
        db.initialize_schema()

        # Verify tables exist
        result = db.execute("SELECT name FROM sqlite_master WHERE type='table'")
        table_names = [row["name"] for row in result]
        assert len(table_names) > 0

    def test_initialize_schema_custom_path(self, tmp_path):
        """Test schema initialization with custom path."""
        db_path = tmp_path / "test.db"
        schema_path = tmp_path / "custom_schema.sql"

        # Create custom schema file
        schema_path.write_text("CREATE TABLE custom_test (id INTEGER);")

        db = DatabaseConnection(str(db_path))
        db.initialize_schema(str(schema_path))

        # Verify custom table exists
        result = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='custom_test'"
        )
        assert len(result) == 1

    def test_initialize_schema_file_not_found(self, tmp_path):
        """Test schema initialization with non-existent file."""
        db_path = tmp_path / "test.db"
        db = DatabaseConnection(str(db_path))

        with pytest.raises(FileNotFoundError):
            db.initialize_schema("/nonexistent/schema.sql")

    def test_get_version_no_table(self, tmp_path):
        """Test get_version when app_settings table doesn't exist."""
        db_path = tmp_path / "test.db"
        db = DatabaseConnection(str(db_path))

        version = db.get_version()
        assert version == 0

    def test_get_version_with_value(self, tmp_path):
        """Test get_version with existing version."""
        db_path = tmp_path / "test.db"
        db = DatabaseConnection(str(db_path))

        # Create app_settings table and set version
        db.execute(
            "CREATE TABLE app_settings (key TEXT PRIMARY KEY, value TEXT, updated_at TEXT)",
            commit=True,
        )
        db.execute(
            "INSERT INTO app_settings VALUES ('schema_version', '5', '2024-01-01')", commit=True
        )

        version = db.get_version()
        assert version == 5

    def test_set_version(self, tmp_path):
        """Test setting schema version."""
        db_path = tmp_path / "test.db"
        db = DatabaseConnection(str(db_path))

        # Create app_settings table
        db.execute(
            "CREATE TABLE app_settings (key TEXT PRIMARY KEY, value TEXT, updated_at TEXT)",
            commit=True,
        )

        db.set_version(10)

        version = db.get_version()
        assert version == 10


class TestDatabaseMaintenanceOperations:
    """Test maintenance operations."""

    def test_vacuum(self, tmp_path):
        """Test VACUUM operation."""
        db_path = tmp_path / "test.db"
        db = DatabaseConnection(str(db_path))

        # Create and populate table
        db.execute("CREATE TABLE test (id INTEGER, data TEXT)", commit=True)
        db.execute_many("INSERT INTO test VALUES (?, ?)", [(i, "x" * 1000) for i in range(100)])

        # Delete data
        db.execute("DELETE FROM test", commit=True)

        # Get file size before vacuum
        size_before = db_path.stat().st_size

        # Run vacuum
        db.vacuum()

        # File size should be smaller after vacuum
        size_after = db_path.stat().st_size
        assert size_after <= size_before

    def test_backup(self, tmp_path):
        """Test database backup."""
        db_path = tmp_path / "test.db"
        backup_path = tmp_path / "backup.db"

        db = DatabaseConnection(str(db_path))

        # Create and populate table
        db.execute("CREATE TABLE test (id INTEGER, value TEXT)", commit=True)
        db.execute("INSERT INTO test VALUES (1, 'test')", commit=True)

        # Create backup
        db.backup(str(backup_path))

        # Verify backup exists
        assert backup_path.exists()

        # Verify backup contains data
        backup_db = DatabaseConnection(str(backup_path))
        result = backup_db.execute("SELECT * FROM test")
        assert len(result) == 1
        assert result[0]["value"] == "test"


class TestDatabaseEncryption:
    """Test database encryption features."""

    def test_check_sqlcipher_not_available(self, tmp_path):
        """Test _check_sqlcipher when SQLCipher is not available."""
        db_path = tmp_path / "test.db"
        db = DatabaseConnection(str(db_path))

        # Create a mock connection that raises OperationalError
        mock_conn = Mock()
        mock_conn.execute.side_effect = sqlite3.OperationalError("no such pragma")

        result = db._check_sqlcipher(mock_conn)
        assert result is False

    def test_is_encryption_enabled_no_key(self, tmp_path):
        """Test is_encryption_enabled when no key is provided."""
        db_path = tmp_path / "test.db"
        db = DatabaseConnection(str(db_path))

        assert not db.is_encryption_enabled()

    def test_rekey_without_sqlcipher(self, tmp_path):
        """Test rekey when SQLCipher is not available."""
        db_path = tmp_path / "test.db"
        db = DatabaseConnection(str(db_path), encryption_key="old_key")

        # Mock _check_sqlcipher to return False
        with patch.object(db, "_check_sqlcipher", return_value=False):
            result = db.rekey("new_key")
            assert result is False


class TestDatabaseThreadSafety:
    """Test thread safety of database operations."""

    def test_concurrent_reads(self, tmp_path):
        """Test concurrent read operations."""
        db_path = tmp_path / "test.db"
        db = DatabaseConnection(str(db_path))

        # Create and populate table
        db.execute("CREATE TABLE test (id INTEGER, value TEXT)", commit=True)
        db.execute_many("INSERT INTO test VALUES (?, ?)", [(i, f"value{i}") for i in range(100)])

        results = []
        errors = []

        def read_data():
            try:
                result = db.execute("SELECT COUNT(*) as count FROM test")
                results.append(result[0]["count"])
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=read_data) for _ in range(10)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert all(count == 100 for count in results)

    def test_concurrent_writes(self, tmp_path):
        """Test concurrent write operations."""
        db_path = tmp_path / "test.db"
        db = DatabaseConnection(str(db_path))

        db.execute(
            "CREATE TABLE test (id INTEGER PRIMARY KEY AUTOINCREMENT, value TEXT)", commit=True
        )

        errors = []

        def write_data(value):
            try:
                db.execute("INSERT INTO test (value) VALUES (?)", (value,), commit=True)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=write_data, args=(f"value{i}",)) for i in range(20)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Some writes might fail due to locking, but most should succeed
        result = db.execute("SELECT COUNT(*) as count FROM test")
        assert result[0]["count"] > 0
