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
Version bumping script for EchoNote.

This script automates the process of updating version numbers following
semantic versioning conventions.
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path
from typing import Tuple

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config import get_version


def parse_version(version_str: str) -> Tuple[int, int, int, str, str]:
    """
    Parse a semantic version string.

    Args:
        version_str: Version string to parse

    Returns:
        Tuple of (major, minor, patch, pre_release, build)
    """
    # Pattern for semantic versioning with optional pre-release and build
    pattern = r"^(\d+)\.(\d+)\.(\d+)(?:-([a-zA-Z0-9\-\.]+))?(?:\+([a-zA-Z0-9\-\.]+))?$"
    match = re.match(pattern, version_str)

    if not match:
        raise ValueError(f"Invalid version format: {version_str}")

    major, minor, patch = map(int, match.groups()[:3])
    pre_release = match.group(4) or ""
    build = match.group(5) or ""

    return major, minor, patch, pre_release, build


def format_version(
    major: int, minor: int, patch: int, pre_release: str = "", build: str = ""
) -> str:
    """
    Format version components into a version string.

    Args:
        major: Major version number
        minor: Minor version number
        patch: Patch version number
        pre_release: Pre-release identifier (optional)
        build: Build metadata (optional)

    Returns:
        Formatted version string
    """
    version = f"{major}.{minor}.{patch}"

    if pre_release:
        version += f"-{pre_release}"

    if build:
        version += f"+{build}"

    return version


def bump_version(bump_type: str, current_version: str, pre_release: str = "") -> str:
    """
    Bump version according to semantic versioning rules.

    Args:
        bump_type: Type of bump ('major', 'minor', 'patch', 'pre')
        current_version: Current version string
        pre_release: Pre-release identifier for 'pre' bump type

    Returns:
        New version string
    """
    major, minor, patch, current_pre, build = parse_version(current_version)

    if bump_type == "major":
        major += 1
        minor = 0
        patch = 0
        pre_release = ""
        build = ""
    elif bump_type == "minor":
        minor += 1
        patch = 0
        pre_release = ""
        build = ""
    elif bump_type == "patch":
        patch += 1
        pre_release = ""
        build = ""
    elif bump_type == "pre":
        if not pre_release:
            raise ValueError("Pre-release identifier required for 'pre' bump type")
        # If already a pre-release, increment it; otherwise add pre-release
        if current_pre:
            # Try to increment numeric suffix
            match = re.match(r"^(.+?)(\d+)$", current_pre)
            if match and match.group(1) == pre_release.rstrip("0123456789"):
                pre_release = f"{match.group(1)}{int(match.group(2)) + 1}"
            else:
                pre_release = f"{pre_release}1"
        else:
            pre_release = f"{pre_release}1"
        build = ""
    else:
        raise ValueError(f"Invalid bump type: {bump_type}")

    return format_version(major, minor, patch, pre_release, build)


def update_version_file(new_version: str) -> None:
    """
    Update the version in config/__version__.py.

    Args:
        new_version: New version string
    """
    version_file = project_root / "config" / "__version__.py"
    content = version_file.read_text(encoding="utf-8")

    # Parse new version
    major, minor, patch, pre_release, build = parse_version(new_version)

    # Update __version__
    content = re.sub(
        r'^__version__\s*=\s*"[^"]*"', f'__version__ = "{new_version}"', content, flags=re.MULTILINE
    )

    # Update VERSION_INFO
    version_info_pattern = r"VERSION_INFO\s*=\s*\{[^}]*\}"
    version_info_replacement = f"""VERSION_INFO = {{
    "major": {major},
    "minor": {minor},
    "patch": {patch},
    "pre_release": {f'"{pre_release}"' if pre_release else 'None'},
    "build": {f'"{build}"' if build else 'None'},
}}"""

    content = re.sub(version_info_pattern, version_info_replacement, content, flags=re.DOTALL)

    version_file.write_text(content, encoding="utf-8")
    print(f"Updated {version_file}")


def run_sync_script() -> bool:
    """
    Run the version synchronization script.

    Returns:
        True if successful, False otherwise
    """
    try:
        subprocess.run(
            [sys.executable, "scripts/sync_version.py"],
            cwd=project_root,
            capture_output=True,
            text=True,
            check=True,
        )
        print("Version synchronization completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Version synchronization failed: {e}")
        print(f"stdout: {e.stdout}")
        print(f"stderr: {e.stderr}")
        return False


def main():
    """Main function for version bumping."""
    parser = argparse.ArgumentParser(
        description="Bump EchoNote version following semantic versioning"
    )
    parser.add_argument(
        "bump_type", choices=["major", "minor", "patch", "pre"], help="Type of version bump"
    )
    parser.add_argument(
        "--pre-release", help="Pre-release identifier (required for 'pre' bump type)"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Show what would be done without making changes"
    )

    args = parser.parse_args()

    # Validate pre-release argument
    if args.bump_type == "pre" and not args.pre_release:
        parser.error("--pre-release is required for 'pre' bump type")

    # Get current version
    current_version = get_version()
    print(f"Current version: {current_version}")

    try:
        # Calculate new version
        new_version = bump_version(args.bump_type, current_version, args.pre_release or "")
        print(f"New version: {new_version}")

        if args.dry_run:
            print("\nDry run - no changes made")
            return

        # Confirm with user
        response = input(f"\nUpdate version from {current_version} to {new_version}? (y/N): ")
        if response.lower() != "y":
            print("Version update cancelled")
            return

        # Update version file
        update_version_file(new_version)

        # Run synchronization
        if not run_sync_script():
            print("Warning: Version synchronization failed")
            sys.exit(1)

        print(f"\n✓ Version successfully updated to {new_version}")
        print("\nNext steps:")
        print("1. Review the changes: git diff")
        print(f"2. Commit the changes: git add -A && git commit -m 'Bump version to {new_version}'")
        print(f"3. Tag the release: git tag v{new_version}")

    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
