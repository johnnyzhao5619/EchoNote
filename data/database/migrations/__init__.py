"""
Database migration system for EchoNote.

Handles schema versioning and incremental database updates.
"""

import logging
from pathlib import Path
from typing import List, Tuple


logger = logging.getLogger('echonote.database.migrations')


class MigrationManager:
    """Manages database schema migrations."""

    def __init__(self, db_connection):
        """
        Initialize migration manager.

        Args:
            db_connection: DatabaseConnection instance
        """
        self.db = db_connection
        self.migrations_dir = Path(__file__).parent
    
    def get_available_migrations(self) -> List[Tuple[int, Path]]:
        """
        Get list of available migration files.

        Returns:
            List of (version, file_path) tuples, sorted by version
        """
        migrations = []
        
        for file_path in self.migrations_dir.glob("*.sql"):
            # Migration files should be named like: 001_initial.sql, 002_add_field.sql
            filename = file_path.stem
            
            # Skip __init__.py and other non-migration files
            if not filename[0].isdigit():
                continue
            
            try:
                # Extract version number from filename
                version = int(filename.split('_')[0])
                migrations.append((version, file_path))
            except (ValueError, IndexError):
                logger.warning(f"Skipping invalid migration file: {file_path}")
                continue
        
        # Sort by version number
        migrations.sort(key=lambda x: x[0])
        return migrations
    
    def get_pending_migrations(self) -> List[Tuple[int, Path]]:
        """
        Get list of migrations that need to be applied.

        Returns:
            List of (version, file_path) tuples for pending migrations
        """
        current_version = self.db.get_version()
        all_migrations = self.get_available_migrations()
        
        # Filter migrations with version greater than current
        pending = [
            (version, path) for version, path in all_migrations
            if version > current_version
        ]
        
        logger.info(
            f"Current schema version: {current_version}, "
            f"Pending migrations: {len(pending)}"
        )
        
        return pending
    
    def apply_migration(self, version: int, migration_path: Path):
        """
        Apply a single migration.

        Args:
            version: Migration version number
            migration_path: Path to migration SQL file
        """
        logger.info(f"Applying migration {version}: {migration_path.name}")
        
        try:
            # Read migration SQL
            with open(migration_path, 'r', encoding='utf-8') as f:
                migration_sql = f.read()
            
            # Execute migration
            self.db.execute_script(migration_sql, commit=True)
            
            # Update schema version
            self.db.set_version(version)
            
            logger.info(f"Migration {version} applied successfully")
            
        except Exception as e:
            logger.error(f"Failed to apply migration {version}: {e}")
            raise
    
    def migrate(self):
        """
        Apply all pending migrations.

        Raises:
            Exception: If any migration fails
        """
        pending = self.get_pending_migrations()
        
        if not pending:
            logger.info("No pending migrations")
            return
        
        logger.info(f"Applying {len(pending)} pending migration(s)")
        
        for version, migration_path in pending:
            self.apply_migration(version, migration_path)
        
        logger.info("All migrations applied successfully")
    
    def create_migration(self, name: str) -> Path:
        """
        Create a new migration file template.

        Args:
            name: Descriptive name for the migration (e.g., "add_user_table")

        Returns:
            Path to the created migration file
        """
        # Get next version number
        migrations = self.get_available_migrations()
        next_version = 1 if not migrations else migrations[-1][0] + 1
        
        # Create filename
        filename = f"{next_version:03d}_{name}.sql"
        migration_path = self.migrations_dir / filename
        
        # Create template
        template = f"""-- Migration: {name}
-- Version: {next_version}
-- Created: {self._get_timestamp()}

-- Add your migration SQL here

"""
        
        with open(migration_path, 'w', encoding='utf-8') as f:
            f.write(template)
        
        logger.info(f"Created migration file: {migration_path}")
        return migration_path
    
    def _get_timestamp(self) -> str:
        """Get current timestamp as string."""
        from datetime import datetime
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')
