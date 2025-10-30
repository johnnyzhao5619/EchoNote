#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2025 EchoNote Contributors

"""
Enhanced PySide6 migration verification script.

This script comprehensively verifies that the PyQt6 to PySide6 migration
was completed successfully, with detailed reporting and JSON output support.
"""

import argparse
import json
import logging
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Set

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

class VerificationIssue:
    """Represents a verification issue found during migration check."""

    def __init__(
        self,
        filepath: str,
        line_number: int,
        line_content: str,
        issue_type: str,
        description: str,
        severity: str = "error",
    ):
        self.filepath = filepath
        self.line_number = line_number
        self.line_content = line_content.strip()
        self.issue_type = issue_type
        self.description = description
        self.severity = severity  # error, warning, info

    def to_dict(self) -> Dict:
        """Convert issue to dictionary for JSON serialization."""
        return {
            "filepath": self.filepath,
            "line_number": self.line_number,
            "line_content": self.line_content,
            "issue_type": self.issue_type,
            "description": self.description,
            "severity": self.severity,
        }

    def __str__(self) -> str:
        """String representation for console output."""
        return (
            f"{self.severity.upper()}: {self.filepath}:{self.line_number} "
            f"[{self.issue_type}] {self.description}"
        )

class VerificationStats:
    """Track verification statistics."""

    def __init__(self):
        self.files_checked = 0
        self.files_with_issues = 0
        self.total_issues = 0
        self.issues_by_type: Dict[str, int] = {}
        self.issues_by_severity: Dict[str, int] = {}
        self.clean_files: List[str] = []
        self.problematic_files: Set[str] = set()

    def add_issue(self, issue: VerificationIssue):
        """Add an issue to the statistics."""
        self.total_issues += 1
        self.issues_by_type[issue.issue_type] = self.issues_by_type.get(issue.issue_type, 0) + 1
        self.issues_by_severity[issue.severity] = self.issues_by_severity.get(issue.severity, 0) + 1
        self.problematic_files.add(issue.filepath)

    def add_clean_file(self, filepath: str):
        """Add a file that passed all checks."""
        self.clean_files.append(filepath)

    def finalize(self):
        """Finalize statistics calculation."""
        self.files_with_issues = len(self.problematic_files)

class PySide6MigrationVerifier:
    """Enhanced PySide6 migration verification tool."""

    # Patterns to detect PyQt6 remnants
    PYQT6_PATTERNS = [
        # Import statements
        (
            re.compile(r"^\s*from\s+PyQt6\b", re.MULTILINE),
            "pyqt6_import",
            "PyQt6 import statement found",
        ),
        (
            re.compile(r"^\s*import\s+PyQt6\b", re.MULTILINE),
            "pyqt6_import",
            "PyQt6 import statement found",
        ),
        # Code references
        (re.compile(r"\bPyQt6\."), "pyqt6_reference", "PyQt6 reference in code"),
        # Signal/slot remnants
        (
            re.compile(r"\bpyqtSignal\b"),
            "pyqt6_signal",
            "Signal found (should be Signal)",
        ),
        (re.compile(r"\bpyqtSlot\b"), "pyqt6_slot", "Slot found (should be Slot)"),
        (
            re.compile(r"\bpyqtProperty\b"),
            "pyqt6_property",
            "Property found (should be Property)",
        ),
    ]

    # Patterns to verify PySide6 usage
    PYSIDE6_PATTERNS = [
        (
            re.compile(r"^\s*from\s+PySide6\b", re.MULTILINE),
            "pyside6_import",
            "PySide6 import found",
        ),
        (
            re.compile(r"^\s*import\s+PySide6\b", re.MULTILINE),
            "pyside6_import",
            "PySide6 import found",
        ),
        (re.compile(r"\bSignal\s*\("), "pyside6_signal", "PySide6 Signal usage found"),
        (re.compile(r"@Slot\s*\("), "pyside6_slot", "PySide6 Slot decorator found"),
    ]

    # Common migration issues to check
    MIGRATION_ISSUES = [
        # QAction location change
        (
            re.compile(r"from\s+PySide6\.QtWidgets\s+import\s+.*\bQAction\b"),
            "qaction_location",
            "QAction should be imported from PySide6.QtGui, not QtWidgets",
            "warning",
        ),
        # Signal type annotation issues
        (
            re.compile(r"Signal\s*\[\s*\w+\s*\]"),
            "signal_annotation",
            "Signal type annotation should use parentheses: Signal(type) not Signal(type)",
            "warning",
        ),
        # Mixed imports
        (
            re.compile(r"from\s+(?:PyQt6|PySide6).*import.*(?:PyQt6|PySide6)"),
            "mixed_imports",
            "Mixed PyQt6/PySide6 imports detected",
            "error",
        ),
    ]

    # File patterns to check
    PYTHON_FILE_PATTERNS = ["*.py"]
    DOC_FILE_PATTERNS = ["*.md", "*.rst", "*.txt"]
    CONFIG_FILE_PATTERNS = ["*.yaml", "*.yml", "*.json", "*.toml", "*.cfg", "*.ini"]

    def __init__(
        self,
        include_docs: bool = True,
        include_configs: bool = True,
        strict_mode: bool = False,
    ):
        """Initialize the verifier.

        Args:
            include_docs: Check documentation files for PyQt6 references
            include_configs: Check configuration files for PyQt6 references
            strict_mode: Enable strict checking with additional warnings
        """
        self.include_docs = include_docs
        self.include_configs = include_configs
        self.strict_mode = strict_mode
        self.stats = VerificationStats()
        self.issues: List[VerificationIssue] = []

    def find_files_to_check(self, paths: List[str]) -> Dict[str, List[Path]]:
        """Find all files to check based on the given paths.

        Args:
            paths: List of file or directory paths

        Returns:
            Dictionary mapping file types to lists of file paths
        """
        files_by_type = {"python": [], "docs": [], "configs": []}

        for path_str in paths:
            path = Path(path_str)

            if not path.exists():
                logger.warning(f"Path does not exist: {path}")
                continue

            if path.is_file():
                self._categorize_file(path, files_by_type)
            elif path.is_dir():
                self._scan_directory(path, files_by_type)

        return files_by_type

    def _categorize_file(self, filepath: Path, files_by_type: Dict[str, List[Path]]):
        """Categorize a single file by type."""
        suffix = filepath.suffix.lower()

        if suffix == ".py":
            files_by_type["python"].append(filepath)
        elif self.include_docs and suffix in [".md", ".rst", ".txt"]:
            files_by_type["docs"].append(filepath)
        elif self.include_configs and suffix in [
            ".yaml",
            ".yml",
            ".json",
            ".toml",
            ".cfg",
            ".ini",
        ]:
            files_by_type["configs"].append(filepath)

    def _scan_directory(self, directory: Path, files_by_type: Dict[str, List[Path]]):
        """Recursively scan directory for files to check."""
        for pattern in self.PYTHON_FILE_PATTERNS:
            for filepath in directory.rglob(pattern):
                if self._should_skip_file(filepath):
                    continue
                files_by_type["python"].append(filepath)

        if self.include_docs:
            for pattern in self.DOC_FILE_PATTERNS:
                for filepath in directory.rglob(pattern):
                    if self._should_skip_file(filepath):
                        continue
                    files_by_type["docs"].append(filepath)

        if self.include_configs:
            for pattern in self.CONFIG_FILE_PATTERNS:
                for filepath in directory.rglob(pattern):
                    if self._should_skip_file(filepath):
                        continue
                    files_by_type["configs"].append(filepath)

    def _should_skip_file(self, filepath: Path) -> bool:
        """Check if a file should be skipped during verification."""
        # Skip hidden files and directories
        if any(part.startswith(".") for part in filepath.parts):
            return True

        # Skip common directories
        skip_dirs = {"venv", "__pycache__", "node_modules", ".git", "build", "dist"}
        if any(part in skip_dirs for part in filepath.parts):
            return True

        # Skip backup files
        if filepath.name.endswith(".backup") or filepath.name.endswith("~"):
            return True

        return False

    def check_python_file(self, filepath: Path) -> List[VerificationIssue]:
        """Check a Python file for migration issues.

        Args:
            filepath: Path to the Python file

        Returns:
            List of verification issues found
        """
        issues = []

        try:
            # Try UTF-8 first, fallback to latin-1
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()
            except UnicodeDecodeError:
                with open(filepath, "r", encoding="latin-1") as f:
                    content = f.read()
                logger.debug(f"Used latin-1 encoding for {filepath}")

            lines = content.splitlines()

            # Check for PyQt6 remnants
            for pattern, issue_type, description in self.PYQT6_PATTERNS:
                for match in pattern.finditer(content):
                    line_num = content[: match.start()].count("\n") + 1
                    line_content = lines[line_num - 1] if line_num <= len(lines) else ""

                    issue = VerificationIssue(
                        filepath=str(filepath),
                        line_number=line_num,
                        line_content=line_content,
                        issue_type=issue_type,
                        description=description,
                        severity="error",
                    )
                    issues.append(issue)

            # Check for migration-specific issues
            for pattern, issue_type, description, severity in self.MIGRATION_ISSUES:
                for match in pattern.finditer(content):
                    line_num = content[: match.start()].count("\n") + 1
                    line_content = lines[line_num - 1] if line_num <= len(lines) else ""

                    issue = VerificationIssue(
                        filepath=str(filepath),
                        line_number=line_num,
                        line_content=line_content,
                        issue_type=issue_type,
                        description=description,
                        severity=severity,
                    )
                    issues.append(issue)

            # In strict mode, verify PySide6 usage
            if self.strict_mode and "Qt" in content:
                has_pyside6 = any(
                    pattern.search(content) for pattern, _, _ in self.PYSIDE6_PATTERNS
                )

                if not has_pyside6:
                    issue = VerificationIssue(
                        filepath=str(filepath),
                        line_number=1,
                        line_content="",
                        issue_type="missing_pyside6",
                        description="File contains Qt references but no PySide6 imports",
                        severity="warning",
                    )
                    issues.append(issue)

        except Exception as e:
            logger.error(f"Error checking {filepath}: {e}")
            issue = VerificationIssue(
                filepath=str(filepath),
                line_number=0,
                line_content="",
                issue_type="check_error",
                description=f"Error during verification: {e}",
                severity="error",
            )
            issues.append(issue)

        return issues

    def check_text_file(self, filepath: Path, file_type: str) -> List[VerificationIssue]:
        """Check a text file (docs/configs) for PyQt6 references.

        Args:
            filepath: Path to the text file
            file_type: Type of file ('docs' or 'configs')

        Returns:
            List of verification issues found
        """
        issues = []

        try:
            # Try UTF-8 first, fallback to latin-1
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()
            except UnicodeDecodeError:
                with open(filepath, "r", encoding="latin-1") as f:
                    content = f.read()
                logger.debug(f"Used latin-1 encoding for {filepath}")

            lines = content.splitlines()

            # Simple PyQt6 reference check
            pyqt6_pattern = re.compile(r"\bPyQt6\b", re.IGNORECASE)

            for match in pyqt6_pattern.finditer(content):
                line_num = content[: match.start()].count("\n") + 1
                line_content = lines[line_num - 1] if line_num <= len(lines) else ""

                issue = VerificationIssue(
                    filepath=str(filepath),
                    line_number=line_num,
                    line_content=line_content,
                    issue_type=f"pyqt6_reference_{file_type}",
                    description=f"PyQt6 reference found in {file_type} file",
                    severity="warning",
                )
                issues.append(issue)

        except Exception as e:
            logger.error(f"Error checking {filepath}: {e}")
            issue = VerificationIssue(
                filepath=str(filepath),
                line_number=0,
                line_content="",
                issue_type="check_error",
                description=f"Error during verification: {e}",
                severity="error",
            )
            issues.append(issue)

        return issues

    def verify_migration(self, paths: List[str]) -> bool:
        """Run the verification process.

        Args:
            paths: List of file or directory paths to verify

        Returns:
            True if verification passed (no errors), False otherwise
        """
        logger.info("Starting PySide6 migration verification")
        logger.info(f"Include docs: {self.include_docs}")
        logger.info(f"Include configs: {self.include_configs}")
        logger.info(f"Strict mode: {self.strict_mode}")

        # Find files to check
        files_by_type = self.find_files_to_check(paths)

        total_files = sum(len(files) for files in files_by_type.values())
        logger.info(f"Found {total_files} files to check:")
        logger.info(f"  Python files: {len(files_by_type['python'])}")
        logger.info(f"  Documentation files: {len(files_by_type['docs'])}")
        logger.info(f"  Configuration files: {len(files_by_type['configs'])}")

        if total_files == 0:
            logger.warning("No files found to verify")
            return True

        # Check Python files
        for filepath in files_by_type["python"]:
            self.stats.files_checked += 1
            issues = self.check_python_file(filepath)

            if issues:
                for issue in issues:
                    self.issues.append(issue)
                    self.stats.add_issue(issue)
            else:
                self.stats.add_clean_file(str(filepath))

        # Check documentation files
        for filepath in files_by_type["docs"]:
            self.stats.files_checked += 1
            issues = self.check_text_file(filepath, "docs")

            if issues:
                for issue in issues:
                    self.issues.append(issue)
                    self.stats.add_issue(issue)
            else:
                self.stats.add_clean_file(str(filepath))

        # Check configuration files
        for filepath in files_by_type["configs"]:
            self.stats.files_checked += 1
            issues = self.check_text_file(filepath, "configs")

            if issues:
                for issue in issues:
                    self.issues.append(issue)
                    self.stats.add_issue(issue)
            else:
                self.stats.add_clean_file(str(filepath))

        # Finalize statistics
        self.stats.finalize()

        # Determine success
        error_count = self.stats.issues_by_severity.get("error", 0)
        success = error_count == 0

        if success:
            logger.info("Verification completed successfully!")
        else:
            logger.error(f"Verification failed with {error_count} errors")

        return success

    def generate_report(self) -> Dict:
        """Generate verification report.

        Returns:
            Dictionary containing verification results and statistics
        """
        report = {
            "timestamp": datetime.now().isoformat(),
            "verification_passed": self.stats.issues_by_severity.get("error", 0) == 0,
            "settings": {
                "include_docs": self.include_docs,
                "include_configs": self.include_configs,
                "strict_mode": self.strict_mode,
            },
            "statistics": {
                "files_checked": self.stats.files_checked,
                "files_with_issues": self.stats.files_with_issues,
                "clean_files_count": len(self.stats.clean_files),
                "total_issues": self.stats.total_issues,
                "issues_by_type": self.stats.issues_by_type,
                "issues_by_severity": self.stats.issues_by_severity,
            },
            "issues": [issue.to_dict() for issue in self.issues],
            "clean_files": self.stats.clean_files,
        }

        return report

    def display_report(self, report: Dict, show_clean_files: bool = False):
        """Display verification report in a readable format.

        Args:
            report: Verification report dictionary
            show_clean_files: Whether to show list of clean files
        """
        print("\n" + "=" * 60)
        print("PYSIDE6 MIGRATION VERIFICATION REPORT")
        print("=" * 60)

        # Overall status
        status = "PASSED" if report["verification_passed"] else "FAILED"
        print(f"Verification Status: {status}")
        print()

        # Statistics
        stats = report["statistics"]
        print(f"Files checked: {stats['files_checked']}")
        print(f"Files with issues: {stats['files_with_issues']}")
        print(f"Clean files: {stats['clean_files_count']}")
        print(f"Total issues: {stats['total_issues']}")

        if stats["issues_by_severity"]:
            print("\nIssues by severity:")
            for severity, count in stats["issues_by_severity"].items():
                print(f"  {severity}: {count}")

        if stats["issues_by_type"]:
            print("\nIssues by type:")
            for issue_type, count in stats["issues_by_type"].items():
                print(f"  {issue_type}: {count}")

        # Issues details
        if report["issues"]:
            print("\nIssue Details:")
            print("-" * 40)

            # Group issues by file
            issues_by_file = {}
            for issue in report["issues"]:
                filepath = issue["filepath"]
                if filepath not in issues_by_file:
                    issues_by_file[filepath] = []
                issues_by_file[filepath].append(issue)

            for filepath, file_issues in issues_by_file.items():
                print(f"\n{filepath}:")
                for issue in file_issues:
                    severity_marker = {"error": "❌", "warning": "⚠️", "info": "ℹ️"}.get(
                        issue["severity"], "•"
                    )

                    print(
                        f"  {severity_marker} Line {issue['line_number']}: "
                        f"{issue['description']}"
                    )
                    if issue["line_content"]:
                        print(f"    > {issue['line_content']}")

        # Clean files (if requested)
        if show_clean_files and report["clean_files"]:
            print(f"\nClean files ({len(report['clean_files'])}):")
            for filepath in report["clean_files"][:10]:  # Show first 10
                print(f"  ✅ {filepath}")
            if len(report["clean_files"]) > 10:
                print(f"  ... and {len(report['clean_files']) - 10} more")

        print("\n" + "=" * 60)

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Enhanced PySide6 migration verification script",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python verify_pyside6_migration.py .
  python verify_pyside6_migration.py --strict ui/ core/
  python verify_pyside6_migration.py --json-output report.json .
  python verify_pyside6_migration.py --no-docs --no-configs src/
        """,
    )

    parser.add_argument("paths", nargs="+", help="Files or directories to verify")

    parser.add_argument("--no-docs", action="store_true", help="Skip checking documentation files")

    parser.add_argument(
        "--no-configs", action="store_true", help="Skip checking configuration files"
    )

    parser.add_argument(
        "--strict",
        action="store_true",
        help="Enable strict mode with additional warnings",
    )

    parser.add_argument(
        "--json-output", metavar="FILE", help="Save report as JSON to specified file"
    )

    parser.add_argument(
        "--show-clean-files",
        action="store_true",
        help="Show list of clean files in report",
    )

    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")

    args = parser.parse_args()

    # Configure logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Create verifier
    verifier = PySide6MigrationVerifier(
        include_docs=not args.no_docs,
        include_configs=not args.no_configs,
        strict_mode=args.strict,
    )

    # Run verification
    success = verifier.verify_migration(args.paths)

    # Generate and display report
    report = verifier.generate_report()
    verifier.display_report(report, show_clean_files=args.show_clean_files)

    # Save JSON report if requested
    if args.json_output:
        try:
            with open(args.json_output, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            logger.info(f"JSON report saved to: {args.json_output}")
        except Exception as e:
            logger.error(f"Failed to save JSON report: {e}")

    # Exit with appropriate code
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
