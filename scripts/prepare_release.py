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
Release preparation script for EchoNote.

This script prepares a new release by:
1. Verifying version consistency
2. Running tests
3. Checking code quality
4. Creating git tag
5. Preparing release notes
"""

import argparse
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config.__version__ import __version__


class ReleasePreparator:
    """Prepares EchoNote releases."""

    def __init__(self, project_root: Path):
        """
        Initialize the release preparator.

        Args:
            project_root: Path to the project root directory
        """
        self.project_root = project_root
        self.version = __version__

    def prepare_release(self, skip_tests: bool = False, dry_run: bool = False) -> bool:
        """
        Prepare a new release.

        Args:
            skip_tests: Skip running tests
            dry_run: Show what would be done without making changes

        Returns:
            True if preparation was successful, False otherwise
        """
        print(f"🚀 Preparing release {self.version}")
        print("=" * 50)

        steps = [
            ("Verifying version consistency", self._verify_versions),
            ("Checking git status", self._check_git_status),
            ("Running code quality checks", self._run_quality_checks),
        ]

        if not skip_tests:
            steps.append(("Running tests", self._run_tests))

        steps.extend(
            [
                ("Preparing release notes", self._prepare_release_notes),
                ("Creating git tag", lambda: self._create_git_tag(dry_run)),
            ]
        )

        for step_name, step_func in steps:
            print(f"\n📋 {step_name}...")
            success, message = step_func()

            if success:
                print(f"✅ {step_name} completed successfully")
                if message:
                    print(f"   {message}")
            else:
                print(f"❌ {step_name} failed: {message}")
                return False

        print(f"\n🎉 Release {self.version} prepared successfully!")

        if dry_run:
            print("\n📝 This was a dry run. No changes were made.")
        else:
            print(f"\n📦 Next steps:")
            print(f"   1. Push the tag: git push origin v{self.version}")
            print(f"   2. Create GitHub release from tag v{self.version}")
            print(f"   3. Upload release artifacts if needed")

        return True

    def _verify_versions(self) -> Tuple[bool, str]:
        """Verify version consistency across all files."""
        try:
            result = subprocess.run(
                [sys.executable, "scripts/sync_version.py", "--verify"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                return True, "All version references are consistent"
            else:
                return False, f"Version inconsistencies found:\n{result.stdout}"

        except Exception as e:
            return False, f"Error verifying versions: {e}"

    def _check_git_status(self) -> Tuple[bool, str]:
        """Check git repository status."""
        try:
            # Check if we're in a git repository
            result = subprocess.run(
                ["git", "rev-parse", "--git-dir"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
            )

            if result.returncode != 0:
                return False, "Not in a git repository"

            # Check for uncommitted changes
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
            )

            if result.stdout.strip():
                return (
                    False,
                    "Uncommitted changes found. Please commit or stash changes before release.",
                )

            # Check current branch
            result = subprocess.run(
                ["git", "branch", "--show-current"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
            )

            current_branch = result.stdout.strip()
            if current_branch != "main" and current_branch != "master":
                return False, f"Not on main/master branch (current: {current_branch})"

            return True, f"Git status clean on branch {current_branch}"

        except Exception as e:
            return False, f"Error checking git status: {e}"

    def _run_quality_checks(self) -> Tuple[bool, str]:
        """Run code quality checks."""
        checks = [
            (
                ["python", "-m", "flake8", "--select=E9,F63,F7,F82", "core/", "ui/", "utils/"],
                "Critical linting",
            ),
            (["python", "-m", "black", "--check", "."], "Code formatting"),
            (["python", "-m", "isort", "--check-only", "."], "Import sorting"),
        ]

        for cmd, check_name in checks:
            try:
                result = subprocess.run(cmd, cwd=self.project_root, capture_output=True, text=True)

                if result.returncode != 0:
                    return False, f"{check_name} failed:\n{result.stdout}\n{result.stderr}"

            except Exception as e:
                return False, f"Error running {check_name}: {e}"

        return True, "All quality checks passed"

    def _run_tests(self) -> Tuple[bool, str]:
        """Run the test suite."""
        try:
            result = subprocess.run(
                ["python", "-m", "pytest", "-v", "--tb=short"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                # Extract test summary from output
                lines = result.stdout.split("\n")
                summary_line = next(
                    (line for line in lines if "passed" in line and "failed" in line), ""
                )
                if not summary_line:
                    summary_line = next(
                        (line for line in lines if "passed" in line), "Tests passed"
                    )
                return True, summary_line
            else:
                return False, f"Tests failed:\n{result.stdout}\n{result.stderr}"

        except Exception as e:
            return False, f"Error running tests: {e}"

    def _prepare_release_notes(self) -> Tuple[bool, str]:
        """Prepare release notes from CHANGELOG."""
        try:
            changelog_path = self.project_root / "CHANGELOG.md"

            if not changelog_path.exists():
                return False, "CHANGELOG.md not found"

            content = changelog_path.read_text(encoding="utf-8")

            # Extract release notes for current version
            lines = content.split("\n")
            release_notes = []
            in_current_version = False

            for line in lines:
                if line.startswith(f"## [{self.version}]") or line.startswith(f"## {self.version}"):
                    in_current_version = True
                    continue
                elif line.startswith("## [") or line.startswith("## v"):
                    if in_current_version:
                        break
                elif in_current_version:
                    release_notes.append(line)

            if not release_notes:
                return False, f"No release notes found for version {self.version}"

            # Write release notes to file
            release_notes_path = self.project_root / f"RELEASE_NOTES_v{self.version}.md"
            release_notes_content = (
                f"# EchoNote {self.version} Release Notes\n\n" + "\n".join(release_notes).strip()
            )

            release_notes_path.write_text(release_notes_content, encoding="utf-8")

            return True, f"Release notes written to {release_notes_path.name}"

        except Exception as e:
            return False, f"Error preparing release notes: {e}"

    def _create_git_tag(self, dry_run: bool) -> Tuple[bool, str]:
        """Create git tag for the release."""
        try:
            tag_name = f"v{self.version}"

            # Check if tag already exists
            result = subprocess.run(
                ["git", "tag", "-l", tag_name],
                cwd=self.project_root,
                capture_output=True,
                text=True,
            )

            if result.stdout.strip():
                return False, f"Tag {tag_name} already exists"

            if dry_run:
                return True, f"Would create tag {tag_name}"

            # Create annotated tag
            result = subprocess.run(
                ["git", "tag", "-a", tag_name, "-m", f"Release {self.version}"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                return True, f"Created tag {tag_name}"
            else:
                return False, f"Failed to create tag: {result.stderr}"

        except Exception as e:
            return False, f"Error creating git tag: {e}"


def main():
    """Main entry point for the release preparation script."""
    parser = argparse.ArgumentParser(description="Prepare EchoNote release")
    parser.add_argument("--skip-tests", action="store_true", help="Skip running tests")
    parser.add_argument(
        "--dry-run", action="store_true", help="Show what would be done without making changes"
    )

    args = parser.parse_args()

    # Initialize preparator
    preparator = ReleasePreparator(project_root)

    # Prepare release
    success = preparator.prepare_release(skip_tests=args.skip_tests, dry_run=args.dry_run)

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
