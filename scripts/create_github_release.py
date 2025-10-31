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
GitHub release creation script for EchoNote.

This script creates a GitHub release using the GitHub CLI or provides
instructions for manual release creation.
"""

import argparse
import subprocess
import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config.__version__ import __version__


class GitHubReleaseCreator:
    """Creates GitHub releases for EchoNote."""

    def __init__(self, project_root: Path):
        """
        Initialize the GitHub release creator.

        Args:
            project_root: Path to the project root directory
        """
        self.project_root = project_root
        self.version = __version__
        self.tag_name = f"v{self.version}"

    def create_release(self, draft: bool = False, prerelease: bool = False) -> bool:
        """
        Create a GitHub release.

        Args:
            draft: Create as draft release
            prerelease: Mark as prerelease

        Returns:
            True if release was created successfully, False otherwise
        """
        print(f"🚀 Creating GitHub release for {self.tag_name}")
        print("=" * 50)

        # Check if GitHub CLI is available
        if not self._check_gh_cli():
            print("❌ GitHub CLI not found. Please install it or create release manually.")
            self._print_manual_instructions()
            return False

        # Check if we're in a git repository with remote
        if not self._check_git_remote():
            print("❌ Git remote not configured properly.")
            return False

        # Load release notes
        release_notes = self._load_release_notes()
        if not release_notes:
            print("❌ Could not load release notes.")
            return False

        # Create the release
        return self._create_gh_release(release_notes, draft, prerelease)

    def _check_gh_cli(self) -> bool:
        """Check if GitHub CLI is available."""
        try:
            result = subprocess.run(["gh", "--version"], capture_output=True, text=True)
            return result.returncode == 0
        except FileNotFoundError:
            return False

    def _check_git_remote(self) -> bool:
        """Check if git remote is configured."""
        try:
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
            )

            if result.returncode != 0:
                return False

            remote_url = result.stdout.strip()
            print(f"📍 Repository: {remote_url}")
            return True

        except Exception as e:
            print(f"Error checking git remote: {e}")
            return False

    def _load_release_notes(self) -> str:
        """Load release notes from file."""
        release_notes_file = self.project_root / f"RELEASE_NOTES_v{self.version}.md"

        if not release_notes_file.exists():
            print(f"❌ Release notes file not found: {release_notes_file}")
            return ""

        try:
            content = release_notes_file.read_text(encoding="utf-8")
            # Remove the title line as GitHub will add its own
            lines = content.split("\n")
            if lines and lines[0].startswith("# EchoNote"):
                content = "\n".join(lines[2:])  # Skip title and empty line
            return content.strip()
        except Exception as e:
            print(f"Error reading release notes: {e}")
            return ""

    def _create_gh_release(self, release_notes: str, draft: bool, prerelease: bool) -> bool:
        """Create GitHub release using GitHub CLI."""
        try:
            cmd = [
                "gh",
                "release",
                "create",
                self.tag_name,
                "--title",
                f"EchoNote {self.version}",
                "--notes",
                release_notes,
            ]

            if draft:
                cmd.append("--draft")
            if prerelease:
                cmd.append("--prerelease")

            print(f"📝 Creating release with command: {' '.join(cmd[:4])}...")

            result = subprocess.run(cmd, cwd=self.project_root, capture_output=True, text=True)

            if result.returncode == 0:
                print("✅ GitHub release created successfully!")
                print(f"🔗 Release URL: {result.stdout.strip()}")
                return True
            else:
                print(f"❌ Failed to create GitHub release:")
                print(f"Error: {result.stderr}")
                return False

        except Exception as e:
            print(f"❌ Error creating GitHub release: {e}")
            return False

    def _print_manual_instructions(self):
        """Print instructions for manual release creation."""
        print("\n📋 Manual Release Creation Instructions:")
        print("=" * 50)
        print("1. Go to your GitHub repository")
        print("2. Click on 'Releases' in the right sidebar")
        print("3. Click 'Create a new release'")
        print(f"4. Choose tag: {self.tag_name}")
        print(f"5. Release title: EchoNote {self.version}")
        print("6. Copy the following release notes:")
        print()

        release_notes_file = self.project_root / f"RELEASE_NOTES_v{self.version}.md"
        if release_notes_file.exists():
            content = release_notes_file.read_text(encoding="utf-8")
            print("```")
            print(content)
            print("```")
        else:
            print("❌ Release notes file not found")

        print("\n7. Click 'Publish release'")

    def check_release_exists(self) -> bool:
        """Check if release already exists."""
        try:
            result = subprocess.run(
                ["gh", "release", "view", self.tag_name],
                cwd=self.project_root,
                capture_output=True,
                text=True,
            )
            return result.returncode == 0
        except Exception:
            return False


def main():
    """Main entry point for the GitHub release creation script."""
    parser = argparse.ArgumentParser(description="Create GitHub release for EchoNote")
    parser.add_argument("--draft", action="store_true", help="Create as draft release")
    parser.add_argument("--prerelease", action="store_true", help="Mark as prerelease")
    parser.add_argument(
        "--force", action="store_true", help="Force creation even if release exists"
    )

    args = parser.parse_args()

    # Initialize creator
    creator = GitHubReleaseCreator(project_root)

    # Check if release already exists
    if not args.force and creator.check_release_exists():
        print(f"⚠️  Release {creator.tag_name} already exists!")
        print("Use --force to recreate it or check the existing release.")
        return 1

    # Create release
    success = creator.create_release(draft=args.draft, prerelease=args.prerelease)

    if success:
        print(f"\n🎉 EchoNote {creator.version} release created successfully!")
        print("\n📦 Next steps:")
        print("1. Review the release on GitHub")
        print("2. Add any additional release assets if needed")
        print("3. Announce the release to users")
        return 0
    else:
        print(f"\n❌ Failed to create release {creator.tag_name}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
