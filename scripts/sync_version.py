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
with the version defined in config/__version__.py.
"""

import json
import re
import sys
from pathlib import Path
from typing import List, Tuple

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config import get_version, get_display_version


def update_pyproject_toml(version: str) -> bool:
    """Update version in pyproject.toml."""
    file_path = project_root / "pyproject.toml"
    if not file_path.exists():
        print(f"Warning: {file_path} not found")
        return False

    content = file_path.read_text(encoding="utf-8")

    # Update version line
    pattern = r'^version\s*=\s*"[^"]*"'
    replacement = f'version = "{version}"'

    new_content = re.sub(pattern, replacement, content, flags=re.MULTILINE)

    if new_content != content:
        file_path.write_text(new_content, encoding="utf-8")
        print(f"Updated version in {file_path}")
        return True

    print(f"Version already up to date in {file_path}")
    return False


def update_default_config_json(version: str) -> bool:
    """Update version in config/default_config.json."""
    file_path = project_root / "config" / "default_config.json"
    if not file_path.exists():
        print(f"Warning: {file_path} not found")
        return False

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            config = json.load(f)

        old_version = config.get("version")
        if old_version != version:
            config["version"] = version

            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2, ensure_ascii=False)

            print(f"Updated version in {file_path}: {old_version} -> {version}")
            return True

        print(f"Version already up to date in {file_path}")
        return False

    except (json.JSONDecodeError, KeyError) as e:
        print(f"Error updating {file_path}: {e}")
        return False


def update_readme_md(version: str, display_version: str) -> bool:
    """Update version references in README.md."""
    file_path = project_root / "README.md"
    if not file_path.exists():
        print(f"Warning: {file_path} not found")
        return False

    content = file_path.read_text(encoding="utf-8")
    original_content = content

    # Update version patterns
    patterns = [
        # Version in project status
        (r"- \*\*Version\*\*: v[\d.]+", f"- **Version**: {display_version}"),
        # Version in announcement
        (r"> 📢 v[\d.]+ 维护版本发布", f"> 📢 {display_version} 维护版本发布"),
        # Version in status lines
        (r"\(v[\d.]+\)", f"({display_version})"),
    ]

    for pattern, replacement in patterns:
        content = re.sub(pattern, replacement, content)

    if content != original_content:
        file_path.write_text(content, encoding="utf-8")
        print(f"Updated version references in {file_path}")
        return True

    print(f"Version references already up to date in {file_path}")
    return False


def update_third_party_licenses(version: str) -> bool:
    """Update EchoNote version in THIRD_PARTY_LICENSES.md."""
    file_path = project_root / "THIRD_PARTY_LICENSES.md"
    if not file_path.exists():
        print(f"Warning: {file_path} not found")
        return False

    content = file_path.read_text(encoding="utf-8")

    # Update EchoNote version at the end of the file
    pattern = r"\*\*EchoNote Version\*\*: [\d.]+"
    replacement = f"**EchoNote Version**: {version}"

    new_content = re.sub(pattern, replacement, content)

    if new_content != content:
        file_path.write_text(new_content, encoding="utf-8")
        print(f"Updated EchoNote version in {file_path}")
        return True

    print(f"EchoNote version already up to date in {file_path}")
    return False


def check_version_consistency() -> List[Tuple[str, str, str]]:
    """Check version consistency across files."""
    inconsistencies = []
    canonical_version = get_version()

    # Check pyproject.toml
    pyproject_path = project_root / "pyproject.toml"
    if pyproject_path.exists():
        content = pyproject_path.read_text(encoding="utf-8")
        match = re.search(r'^version\s*=\s*"([^"]*)"', content, re.MULTILINE)
        if match:
            found_version = match.group(1)
            if found_version != canonical_version:
                inconsistencies.append(("pyproject.toml", found_version, canonical_version))

    # Check default_config.json
    config_path = project_root / "config" / "default_config.json"
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            found_version = config.get("version", "")
            if found_version != canonical_version:
                inconsistencies.append(
                    ("config/default_config.json", found_version, canonical_version)
                )
        except (json.JSONDecodeError, KeyError):
            pass

    return inconsistencies


def main():
    """Main function to synchronize versions."""
    print("EchoNote Version Synchronization")
    print("=" * 40)

    # Get canonical version
    version = get_version()
    display_version = get_display_version()

    print(f"Canonical version: {version}")
    print(f"Display version: {display_version}")
    print()

    # Check for inconsistencies first
    inconsistencies = check_version_consistency()
    if inconsistencies:
        print("Found version inconsistencies:")
        for file_path, found, expected in inconsistencies:
            print(f"  {file_path}: {found} (expected: {expected})")
        print()

    # Update all files
    updated_files = []

    if update_pyproject_toml(version):
        updated_files.append("pyproject.toml")

    if update_default_config_json(version):
        updated_files.append("config/default_config.json")

    if update_readme_md(version, display_version):
        updated_files.append("README.md")

    if update_third_party_licenses(version):
        updated_files.append("THIRD_PARTY_LICENSES.md")

    print()
    if updated_files:
        print(f"Updated {len(updated_files)} files:")
        for file_path in updated_files:
            print(f"  ✓ {file_path}")
        print("\nVersion synchronization completed successfully!")
    else:
        print("All files are already up to date.")

    # Final consistency check
    final_inconsistencies = check_version_consistency()
    if final_inconsistencies:
        print("\nWarning: Some inconsistencies remain:")
        for file_path, found, expected in final_inconsistencies:
            print(f"  {file_path}: {found} (expected: {expected})")
        sys.exit(1)
    else:
        print("\n✓ All version references are now consistent.")


if __name__ == "__main__":
    main()
