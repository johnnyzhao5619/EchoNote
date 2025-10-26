#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2025 EchoNote Contributors

"""
Enhanced PyQt6 to PySide6 migration script.

This script automatically converts PyQt6 imports and syntax to PySide6 equivalents
with comprehensive error handling, backup functionality, and transaction support.
"""

import argparse
import json
import logging
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("migration.log", mode="w", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


class MigrationError(Exception):
    """Custom exception for migration errors."""

    pass


class MigrationStats:
    """Track migration statistics."""

    def __init__(self):
        self.files_processed = 0
        self.files_modified = 0
        self.files_skipped = 0
        self.files_failed = 0
        self.total_replacements = 0
        self.replacements_by_type: Dict[str, int] = {}
        self.failed_files: List[Tuple[str, str]] = []
        self.modified_files: List[str] = []

    def add_replacement(self, replacement_type: str, count: int = 1):
        """Add replacement count for a specific type."""
        self.total_replacements += count
        self.replacements_by_type[replacement_type] = (
            self.replacements_by_type.get(replacement_type, 0) + count
        )

    def add_failed_file(self, filepath: str, error: str):
        """Add a failed file with error message."""
        self.files_failed += 1
        self.failed_files.append((filepath, error))

    def add_modified_file(self, filepath: str):
        """Add a successfully modified file."""
        self.files_modified += 1
        self.modified_files.append(filepath)


class PyQt6ToPySide6Migrator:
    """Enhanced PyQt6 to PySide6 migration tool."""

    # Comprehensive conversion patterns
    IMPORT_PATTERNS = [
        # Pattern 1: from PySide6.Module import ...
        (
            re.compile(r"^(\s*)from\s+PyQt6\.([A-Za-z]+)\s+import\s+(.+)$", re.MULTILINE),
            r"\1from PySide6.\2 import \3",
            "module_imports",
        ),
        # Pattern 2: import PySide6.Module
        (
            re.compile(r"^(\s*)import\s+PyQt6\.([A-Za-z]+)(\s+as\s+\w+)?$", re.MULTILINE),
            r"\1import PySide6.\2\3",
            "direct_imports",
        ),
        # Pattern 3: import PyQt6
        (
            re.compile(r"^(\s*)import\s+PyQt6(\s+as\s+\w+)?$", re.MULTILINE),
            r"\1import PySide6\2",
            "base_imports",
        ),
        # Pattern 4: PyQt6 in code (not imports)
        (re.compile(r"\bPyQt6\.([A-Za-z]+)"), r"PySide6.\1", "code_references"),
    ]

    SIGNAL_SLOT_PATTERNS = [
        # Signal -> Signal
        (re.compile(r"\bpyqtSignal\b"), "Signal", "signal_definitions"),
        # Slot -> Slot
        (re.compile(r"\bpyqtSlot\b"), "Slot", "slot_decorators"),
        # Property -> Property
        (re.compile(r"\bpyqtProperty\b"), "Property", "property_definitions"),
    ]

    # Special cases that need manual attention
    SPECIAL_CASES = {
        "QAction": {
            "from": "from PySide6.QtGui import QAction",
            "to": "from PySide6.QtGui import QAction",
            "note": "QAction moved from QtWidgets to QtGui in PySide6",
        }
    }

    def __init__(self, dry_run: bool = False, backup: bool = True, rollback_on_error: bool = True):
        """Initialize the migrator.

        Args:
            dry_run: If True, only show what would be changed
            backup: If True, create backup files before modification
            rollback_on_error: If True, rollback changes on any error
        """
        self.dry_run = dry_run
        self.backup = backup
        self.rollback_on_error = rollback_on_error
        self.stats = MigrationStats()
        self.backup_dir: Optional[Path] = None
        self.processed_files: Set[str] = set()

        # Compile all patterns for better performance
        self.compiled_patterns = []
        for pattern, replacement, pattern_type in self.IMPORT_PATTERNS + self.SIGNAL_SLOT_PATTERNS:
            self.compiled_patterns.append((pattern, replacement, pattern_type))

    def setup_backup_directory(self) -> Path:
        """Create backup directory with timestamp."""
        if not self.backup:
            return None

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = Path(f"migration_backup_{timestamp}")
        backup_dir.mkdir(exist_ok=True)
        logger.info(f"Created backup directory: {backup_dir}")
        return backup_dir

    def backup_file(self, filepath: Path) -> Optional[Path]:
        """Create backup of a file before modification.

        Args:
            filepath: Path to the file to backup

        Returns:
            Path to backup file or None if backup disabled
        """
        if not self.backup or not self.backup_dir:
            return None

        try:
            # Preserve directory structure in backup
            # Handle both absolute and relative paths
            if filepath.is_absolute():
                relative_path = filepath.relative_to(Path.cwd())
            else:
                relative_path = filepath

            backup_path = self.backup_dir / relative_path
            backup_path.parent.mkdir(parents=True, exist_ok=True)

            shutil.copy2(filepath, backup_path)
            logger.debug(f"Backed up {filepath} to {backup_path}")
            return backup_path

        except Exception as e:
            logger.error(f"Failed to backup {filepath}: {e}")
            raise MigrationError(f"Backup failed for {filepath}: {e}")

    def restore_from_backup(self, filepath: Path) -> bool:
        """Restore file from backup.

        Args:
            filepath: Original file path to restore

        Returns:
            True if restored successfully, False otherwise
        """
        if not self.backup_dir:
            return False

        try:
            # Handle both absolute and relative paths
            if filepath.is_absolute():
                relative_path = filepath.relative_to(Path.cwd())
            else:
                relative_path = filepath

            backup_path = self.backup_dir / relative_path

            if backup_path.exists():
                shutil.copy2(backup_path, filepath)
                logger.info(f"Restored {filepath} from backup")
                return True
            else:
                logger.warning(f"No backup found for {filepath}")
                return False

        except Exception as e:
            logger.error(f"Failed to restore {filepath}: {e}")
            return False

    def process_file_content(self, content: str, filepath: str) -> Tuple[str, bool]:
        """Process file content and apply all conversion patterns.

        Args:
            content: File content to process
            filepath: File path for logging

        Returns:
            Tuple of (modified_content, was_modified)
        """
        modified_content = content
        was_modified = False
        file_stats = {}

        # Apply all conversion patterns
        for pattern, replacement, pattern_type in self.compiled_patterns:
            matches = pattern.findall(modified_content)
            if matches:
                count = len(matches)
                modified_content = pattern.sub(replacement, modified_content)
                was_modified = True
                file_stats[pattern_type] = count
                self.stats.add_replacement(pattern_type, count)
                logger.debug(f"{filepath}: Applied {count} {pattern_type} replacements")

        # Handle special cases
        for case_name, case_info in self.SPECIAL_CASES.items():
            if case_info["from"] in modified_content:
                modified_content = modified_content.replace(case_info["from"], case_info["to"])
                was_modified = True
                self.stats.add_replacement("special_cases", 1)
                logger.info(f"{filepath}: Applied special case for {case_name}")

        if file_stats:
            logger.info(f"{filepath}: Replacements - {file_stats}")

        return modified_content, was_modified

    def process_file(self, filepath: Path) -> bool:
        """Process a single Python file.

        Args:
            filepath: Path to the Python file

        Returns:
            True if file was processed successfully, False otherwise
        """
        try:
            self.stats.files_processed += 1

            # Read file content
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    original_content = f.read()
            except UnicodeDecodeError:
                # Try with different encoding
                with open(filepath, "r", encoding="latin-1") as f:
                    original_content = f.read()
                logger.warning(f"{filepath}: Used latin-1 encoding")

            # Check if file contains PyQt6 references
            if "PyQt6" not in original_content:
                self.stats.files_skipped += 1
                logger.debug(f"{filepath}: No PyQt6 references found, skipping")
                return True

            # Process content
            modified_content, was_modified = self.process_file_content(
                original_content, str(filepath)
            )

            if not was_modified:
                self.stats.files_skipped += 1
                logger.debug(f"{filepath}: No changes needed")
                return True

            if self.dry_run:
                logger.info(f"{filepath}: Would be modified (dry run)")
                self.stats.add_modified_file(str(filepath))
                return True

            # Create backup before modification
            self.backup_file(filepath)

            # Write modified content
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(modified_content)

            self.stats.add_modified_file(str(filepath))
            self.processed_files.add(str(filepath))
            logger.info(f"{filepath}: Successfully migrated")
            return True

        except Exception as e:
            error_msg = f"Failed to process {filepath}: {e}"
            logger.error(error_msg)
            self.stats.add_failed_file(str(filepath), str(e))

            # Attempt to restore from backup if rollback is enabled
            if self.rollback_on_error and not self.dry_run:
                self.restore_from_backup(filepath)

            return False

    def find_python_files(self, paths: List[str]) -> List[Path]:
        """Find all Python files in the given paths.

        Args:
            paths: List of file or directory paths

        Returns:
            List of Python file paths
        """
        python_files = []

        for path_str in paths:
            path = Path(path_str)

            if not path.exists():
                logger.warning(f"Path does not exist: {path}")
                continue

            if path.is_file():
                if path.suffix == ".py":
                    python_files.append(path)
                else:
                    logger.warning(f"Not a Python file: {path}")
            elif path.is_dir():
                # Recursively find Python files
                for py_file in path.rglob("*.py"):
                    # Skip certain directories
                    if any(part.startswith(".") for part in py_file.parts):
                        continue
                    if "venv" in py_file.parts or "__pycache__" in py_file.parts:
                        continue
                    python_files.append(py_file)

        return sorted(python_files)

    def rollback_all_changes(self):
        """Rollback all changes made during migration."""
        if not self.backup_dir or self.dry_run:
            logger.info("No rollback needed (dry run or no backup)")
            return

        logger.info("Rolling back all changes...")
        rollback_count = 0

        for filepath_str in self.processed_files:
            filepath = Path(filepath_str)
            if self.restore_from_backup(filepath):
                rollback_count += 1

        logger.info(f"Rolled back {rollback_count} files")

    def generate_report(self) -> Dict:
        """Generate migration report.

        Returns:
            Dictionary containing migration statistics and details
        """
        report = {
            "timestamp": datetime.now().isoformat(),
            "dry_run": self.dry_run,
            "backup_enabled": self.backup,
            "backup_directory": str(self.backup_dir) if self.backup_dir else None,
            "statistics": {
                "files_processed": self.stats.files_processed,
                "files_modified": self.stats.files_modified,
                "files_skipped": self.stats.files_skipped,
                "files_failed": self.stats.files_failed,
                "total_replacements": self.stats.total_replacements,
                "replacements_by_type": self.stats.replacements_by_type,
            },
            "modified_files": self.stats.modified_files,
            "failed_files": [
                {"file": filepath, "error": error} for filepath, error in self.stats.failed_files
            ],
            "special_cases_applied": self.stats.replacements_by_type.get("special_cases", 0),
        }

        return report

    def migrate(self, paths: List[str]) -> bool:
        """Run the migration process.

        Args:
            paths: List of file or directory paths to migrate

        Returns:
            True if migration completed successfully, False otherwise
        """
        try:
            logger.info("Starting PyQt6 to PySide6 migration")
            logger.info(f"Dry run: {self.dry_run}")
            logger.info(f"Backup enabled: {self.backup}")
            logger.info(f"Rollback on error: {self.rollback_on_error}")

            # Setup backup directory
            if self.backup and not self.dry_run:
                self.backup_dir = self.setup_backup_directory()

            # Find Python files
            python_files = self.find_python_files(paths)
            logger.info(f"Found {len(python_files)} Python files to process")

            if not python_files:
                logger.warning("No Python files found to process")
                return True

            # Process files
            success_count = 0
            for filepath in python_files:
                if self.process_file(filepath):
                    success_count += 1
                else:
                    if self.rollback_on_error and not self.dry_run:
                        logger.error("Error occurred, rolling back all changes")
                        self.rollback_all_changes()
                        return False

            # Generate and display report
            report = self.generate_report()
            self.display_report(report)

            # Save report to file
            report_file = f"migration_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(report_file, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            logger.info(f"Migration report saved to: {report_file}")

            success = self.stats.files_failed == 0
            if success:
                logger.info("Migration completed successfully!")
            else:
                logger.error(f"Migration completed with {self.stats.files_failed} failures")

            return success

        except Exception as e:
            logger.error(f"Migration failed: {e}")
            if self.rollback_on_error and not self.dry_run:
                self.rollback_all_changes()
            return False

    def display_report(self, report: Dict):
        """Display migration report in a readable format.

        Args:
            report: Migration report dictionary
        """
        print("\n" + "=" * 60)
        print("MIGRATION REPORT")
        print("=" * 60)

        stats = report["statistics"]
        print(f"Files processed: {stats['files_processed']}")
        print(f"Files modified: {stats['files_modified']}")
        print(f"Files skipped: {stats['files_skipped']}")
        print(f"Files failed: {stats['files_failed']}")
        print(f"Total replacements: {stats['total_replacements']}")

        if stats["replacements_by_type"]:
            print("\nReplacements by type:")
            for replacement_type, count in stats["replacements_by_type"].items():
                print(f"  {replacement_type}: {count}")

        if report["modified_files"]:
            print(f"\nModified files ({len(report['modified_files'])}):")
            for filepath in report["modified_files"][:10]:  # Show first 10
                print(f"  {filepath}")
            if len(report["modified_files"]) > 10:
                print(f"  ... and {len(report['modified_files']) - 10} more")

        if report["failed_files"]:
            print(f"\nFailed files ({len(report['failed_files'])}):")
            for failed in report["failed_files"]:
                print(f"  {failed['file']}: {failed['error']}")

        if report["backup_directory"]:
            print(f"\nBackup directory: {report['backup_directory']}")

        print("=" * 60)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Enhanced PyQt6 to PySide6 migration script",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python migrate_to_pyside6.py --dry-run .
  python migrate_to_pyside6.py ui/ core/ main.py
  python migrate_to_pyside6.py --no-backup --no-rollback .
        """,
    )

    parser.add_argument("paths", nargs="+", help="Files or directories to migrate")

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be changed without making modifications",
    )

    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Disable file backup before modification",
    )

    parser.add_argument(
        "--no-rollback",
        action="store_true",
        help="Disable automatic rollback on errors",
    )

    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")

    args = parser.parse_args()

    # Configure logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Create migrator
    migrator = PyQt6ToPySide6Migrator(
        dry_run=args.dry_run,
        backup=not args.no_backup,
        rollback_on_error=not args.no_rollback,
    )

    # Run migration
    success = migrator.migrate(args.paths)

    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
