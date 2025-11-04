#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
#
# Copyright (c) 2024-2025 EchoNote Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
Version synchronization script for EchoNote.

This script ensures all version references across the project are consistent
with the canonical version defined in config/__version__.py.
"""

import argparse
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config.__version__ import VERSION_INFO, __version__


class VersionSyncer:
    """Synchronizes version numbers across all project files."""

    def __init__(self, project_root: Path):
        """
        Initialize the version syncer.

        Args:
            project_root: Path to the project root directory
        """
        self.project_root = project_root
        self.version = __version__
        self.version_info = VERSION_INFO

        # Files that need version synchronization
        self.version_files = {
            "pyproject.toml": self._update_pyproject_toml,
            "EchoNote.spec": self._update_spec_file,
            "README.md": self._update_readme,
            "docs/INSTALLATION.md": self._update_docs,
            "docs/DEVELOPER_GUIDE.md": self._update_docs,
        }

    def sync_all_versions(self, dry_run: bool = False) -> bool:
        """
        Synchronize version across all project files.

        Args:
            dry_run: If True, only show what would be changed without making changes

        Returns:
            True if all synchronizations were successful, False otherwise
        """
        print(f"Synchronizing version to {self.version}")
        print(f"Version info: {self.version_info}")
        print()

        success = True
        changes_made = []

        for file_path, update_func in self.version_files.items():
            full_path = self.project_root / file_path

            if not full_path.exists():
                print(f"⚠️  File not found: {file_path}")
                continue

            try:
                changed = update_func(full_path, dry_run)
                if changed:
                    changes_made.append(file_path)
                    status = "📝 Would update" if dry_run else "✅ Updated"
                    print(f"{status}: {file_path}")
                else:
                    print(f"✓ Already up to date: {file_path}")

            except Exception as e:
                print(f"❌ Error updating {file_path}: {e}")
                success = False

        print()
        if dry_run:
            print(f"Dry run complete. {len(changes_made)} files would be updated.")
        else:
            print(f"Version sync complete. {len(changes_made)} files updated.")

        return success

    def _update_pyproject_toml(self, file_path: Path, dry_run: bool) -> bool:
        """Update version in pyproject.toml."""
        content = file_path.read_text(encoding="utf-8")

        # Update version line
        pattern = r'^version\s*=\s*"[^"]*"'
        replacement = f'version = "{self.version}"'

        new_content, count = re.subn(pattern, replacement, content, flags=re.MULTILINE)

        if count > 0 and not dry_run:
            file_path.write_text(new_content, encoding="utf-8")

        return count > 0

    def _update_spec_file(self, file_path: Path, dry_run: bool) -> bool:
        """Update version references in PyInstaller spec file."""
        content = file_path.read_text(encoding="utf-8")
        original_content = content

        # Update any version references in the spec file
        # This is more complex as spec files can have various formats
        # For now, we'll look for common patterns

        # Look for version strings in comments or metadata
        patterns = [
            (r"# Version: [^\n]*", f"# Version: {self.version}"),
            (r'version=[\'"][^\'"]*[\'"]', f'version="{self.version}"'),
        ]

        for pattern, replacement in patterns:
            content = re.sub(pattern, replacement, content)

        changed = content != original_content

        if changed and not dry_run:
            file_path.write_text(content, encoding="utf-8")

        return changed

    def _update_readme(self, file_path: Path, dry_run: bool) -> bool:
        """Update version references in README files."""
        content = file_path.read_text(encoding="utf-8")
        original_content = content

        # Update version badges and references
        patterns = [
            # Version badges
            (r"version-v[0-9]+\.[0-9]+\.[0-9]+", f"version-v{self.version}"),
            (r"Version [0-9]+\.[0-9]+\.[0-9]+", f"Version {self.version}"),
            (r"v[0-9]+\.[0-9]+\.[0-9]+", f"v{self.version}"),
            # Download links
            (r"releases/tag/v[0-9]+\.[0-9]+\.[0-9]+", f"releases/tag/v{self.version}"),
        ]

        for pattern, replacement in patterns:
            content = re.sub(pattern, replacement, content)

        changed = content != original_content

        if changed and not dry_run:
            file_path.write_text(content, encoding="utf-8")

        return changed

    def _update_docs(self, file_path: Path, dry_run: bool) -> bool:
        """Update version references in documentation files."""
        content = file_path.read_text(encoding="utf-8")
        original_content = content

        # Update version references in documentation
        patterns = [
            (r"Version [0-9]+\.[0-9]+\.[0-9]+", f"Version {self.version}"),
            (r"v[0-9]+\.[0-9]+\.[0-9]+", f"v{self.version}"),
            (r"EchoNote [0-9]+\.[0-9]+\.[0-9]+", f"EchoNote {self.version}"),
        ]

        for pattern, replacement in patterns:
            content = re.sub(pattern, replacement, content)

        changed = content != original_content

        if changed and not dry_run:
            file_path.write_text(content, encoding="utf-8")

        return changed

    def verify_version_consistency(self) -> Tuple[bool, List[str]]:
        """
        Verify that all version references are consistent.

        Returns:
            Tuple of (is_consistent, list_of_inconsistencies)
        """
        inconsistencies = []

        for file_path, _ in self.version_files.items():
            full_path = self.project_root / file_path

            if not full_path.exists():
                continue

            try:
                content = full_path.read_text(encoding="utf-8")

                # Look for version patterns that don't match current version
                # Be more specific to avoid matching Python versions, etc.
                if file_path == "pyproject.toml":
                    version_patterns = [r'^version\s*=\s*"([^"]*)"']
                else:
                    version_patterns = [
                        r"Version ([0-9]+\.[0-9]+\.[0-9]+)",
                        r"v([0-9]+\.[0-9]+\.[0-9]+)",
                        r"EchoNote ([0-9]+\.[0-9]+\.[0-9]+)",
                    ]

                for pattern in version_patterns:
                    if file_path == "pyproject.toml":
                        matches = re.findall(pattern, content, re.MULTILINE)
                    else:
                        matches = re.findall(pattern, content, re.IGNORECASE)
                    for match in matches:
                        if match != self.version:
                            inconsistencies.append(
                                f"{file_path}: found version {match}, expected {self.version}"
                            )

            except Exception as e:
                inconsistencies.append(f"{file_path}: error reading file - {e}")

        return len(inconsistencies) == 0, inconsistencies


def main():
    """Main entry point for the version sync script."""
    parser = argparse.ArgumentParser(
        description="Synchronize version numbers across all EchoNote project files"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Show what would be changed without making changes"
    )
    parser.add_argument(
        "--verify", action="store_true", help="Verify version consistency without making changes"
    )
    parser.add_argument("--verbose", action="store_true", help="Show detailed output")

    args = parser.parse_args()

    # Initialize syncer
    syncer = VersionSyncer(project_root)

    if args.verify:
        print("Verifying version consistency...")
        is_consistent, inconsistencies = syncer.verify_version_consistency()

        if is_consistent:
            print("✅ All version references are consistent!")
            return 0
        else:
            print("❌ Version inconsistencies found:")
            for inconsistency in inconsistencies:
                print(f"  - {inconsistency}")
            return 1
    else:
        # Sync versions
        success = syncer.sync_all_versions(dry_run=args.dry_run)

        if success:
            if not args.dry_run:
                print("\n🎉 Version synchronization completed successfully!")
                print(f"All files now reference version {syncer.version}")
            return 0
        else:
            print("\n❌ Version synchronization failed!")
            return 1


if __name__ == "__main__":
    sys.exit(main())
