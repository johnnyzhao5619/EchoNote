"""
Database connection management for EchoNote application.

Provides SQLite connection with optional SQLCipher encryption support.
"""

import logging
import sqlite3
from pathlib import Path
from typing import Optional
from contextlib import contextmanager
import threading


logger = logging.getLogger('echonote.database')


class DatabaseConnection:
    """
    Manages SQLite database connections with encryption support.
    
    Provides connection pooling, encryption via SQLCipher, and
    thread-safe database access.
    """

    def __init__(self, db_path: str, encryption_key: Optional[str] = None):
        """
        Initialize database connection manager.

        Args:
            db_path: Path to the SQLite database file
            encryption_key: Optional encryption key for SQLCipher
        """
        self.db_path = Path(db_path).expanduser()
        self.encryption_key = encryption_key
        self._local = threading.local()
        
        # Ensure database directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Database connection manager initialized: {self.db_path}")
    
    def _get_connection(self) -> sqlite3.Connection:
        """
        Get or create a thread-local database connection.

        Returns:
            SQLite connection for the current thread
        """
        if not hasattr(self._local, 'connection') or self._local.connection is None:
            logger.debug(f"Creating new database connection for thread {threading.current_thread().name}")
            
            # Create connection
            conn = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False,
                timeout=30.0
            )
            
            # Enable foreign keys
            conn.execute("PRAGMA foreign_keys = ON")
            
            # Set row factory for dict-like access
            conn.row_factory = sqlite3.Row
            
            # Apply encryption if key is provided
            if self.encryption_key:
                try:
                    # Try to use SQLCipher with parameter binding to avoid injection
                    conn.execute("PRAGMA key = ?", (self.encryption_key,))
                    # Test if encryption is working
                    conn.execute("SELECT count(*) FROM sqlite_master")
                    logger.info("Database encryption enabled (SQLCipher)")
                except sqlite3.OperationalError as e:
                    logger.debug(
                        "PRAGMA key parameter binding failed, attempting quoted fallback: %s",
                        e,
                    )
                    try:
                        quoted_key = conn.execute(
                            "SELECT quote(?)", (self.encryption_key,)
                        ).fetchone()[0]
                        conn.execute(f"PRAGMA key = {quoted_key}")
                        conn.execute("SELECT count(*) FROM sqlite_master")
                        logger.info(
                            "Database encryption enabled (SQLCipher, quoted key fallback)"
                        )
                    except sqlite3.OperationalError as enc_error:
                        logger.warning(
                            "SQLCipher not available, falling back to unencrypted: %s",
                            enc_error,
                        )
                        # Reconnect without encryption
                        conn.close()
                        conn = sqlite3.connect(
                            str(self.db_path),
                            check_same_thread=False,
                            timeout=30.0
                        )
                        conn.execute("PRAGMA foreign_keys = ON")
                        conn.row_factory = sqlite3.Row
            
            self._local.connection = conn
        
        return self._local.connection
    
    @contextmanager
    def get_cursor(self, commit: bool = False):
        """
        Context manager for database cursor operations.

        Args:
            commit: Whether to commit the transaction on success

        Yields:
            Database cursor

        Example:
            with db.get_cursor(commit=True) as cursor:
                cursor.execute("INSERT INTO ...")
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            yield cursor
            if commit:
                conn.commit()
                logger.debug("Transaction committed")
        except Exception as e:
            conn.rollback()
            logger.error(f"Transaction rolled back due to error: {e}")
            raise
        finally:
            cursor.close()
    
    def execute(self, query: str, params: tuple = None, commit: bool = False):
        """
        Execute a single SQL query.

        Args:
            query: SQL query string
            params: Query parameters (optional)
            commit: Whether to commit after execution

        Returns:
            Cursor with query results
        """
        with self.get_cursor(commit=commit) as cursor:
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            return cursor.fetchall()
    
    def execute_many(self, query: str, params_list: list, commit: bool = True):
        """
        Execute a query with multiple parameter sets.

        Args:
            query: SQL query string
            params_list: List of parameter tuples
            commit: Whether to commit after execution

        Returns:
            Number of affected rows
        """
        with self.get_cursor(commit=commit) as cursor:
            cursor.executemany(query, params_list)
            return cursor.rowcount
    
    def execute_script(self, script: str, commit: bool = True):
        """
        Execute a SQL script (multiple statements).

        Args:
            script: SQL script string
            commit: Whether to commit after execution
        """
        conn = self._get_connection()
        try:
            conn.executescript(script)
            if commit:
                conn.commit()
                logger.debug("Script executed and committed")
        except Exception as e:
            conn.rollback()
            logger.error(f"Script execution failed: {e}")
            raise
    
    def initialize_schema(self, schema_path: Optional[str] = None):
        """
        Initialize database schema from SQL file.

        Args:
            schema_path: Path to schema.sql file. If None, uses default location.
        """
        if schema_path is None:
            schema_path = Path(__file__).parent / "schema.sql"
        else:
            schema_path = Path(schema_path)
        
        if not schema_path.exists():
            logger.error(f"Schema file not found: {schema_path}")
            raise FileNotFoundError(f"Schema file not found: {schema_path}")
        
        logger.info(f"Initializing database schema from {schema_path}")
        
        with open(schema_path, 'r', encoding='utf-8') as f:
            schema_sql = f.read()
        
        self.execute_script(schema_sql, commit=True)
        logger.info("Database schema initialized successfully")
    
    def get_version(self) -> int:
        """
        Get the current database schema version.

        Returns:
            Schema version number, or 0 if not set
        """
        try:
            result = self.execute(
                "SELECT value FROM app_settings WHERE key = 'schema_version'"
            )
            if result:
                return int(result[0]['value'])
            return 0
        except sqlite3.OperationalError:
            # Table doesn't exist yet
            return 0
    
    def set_version(self, version: int):
        """
        Set the database schema version.

        Args:
            version: Schema version number
        """
        self.execute(
            """
            INSERT OR REPLACE INTO app_settings (key, value, updated_at)
            VALUES ('schema_version', ?, CURRENT_TIMESTAMP)
            """,
            (str(version),),
            commit=True
        )
        logger.info(f"Database schema version set to {version}")
    
    def close(self):
        """Close the database connection for the current thread."""
        if hasattr(self._local, 'connection') and self._local.connection:
            self._local.connection.close()
            self._local.connection = None
            logger.debug("Database connection closed")
    
    def close_all(self):
        """
        Close all database connections.
        
        Note: This only closes the connection for the current thread.
        Other threads will close their connections when they exit.
        """
        self.close()
    
    def vacuum(self):
        """
        Optimize database by reclaiming unused space.
        
        Should be called periodically for maintenance.
        """
        logger.info("Running VACUUM on database")
        conn = self._get_connection()
        conn.execute("VACUUM")
        logger.info("VACUUM completed")
    
    def backup(self, backup_path: str):
        """
        Create a backup of the database.

        Args:
            backup_path: Path for the backup file
        """
        backup_path = Path(backup_path).expanduser()
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Creating database backup: {backup_path}")
        
        # Create backup connection
        backup_conn = sqlite3.connect(str(backup_path))
        
        # Copy database
        conn = self._get_connection()
        conn.backup(backup_conn)
        
        backup_conn.close()
        logger.info("Database backup completed successfully")
