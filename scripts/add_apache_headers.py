#!/usr/bin/env python3
"""
Script to add Apache 2.0 license headers to all Python files in the EchoNote project.
"""

import os
import sys
from pathlib import Path
from typing import List

# Apache 2.0 header template
APACHE_HEADER = """# SPDX-License-Identifier: Apache-2.0
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

def has_apache_header(content: str) -> bool:
    """Check if the file already has an Apache 2.0 header."""
    return "SPDX-License-Identifier: Apache-2.0" in content

def has_shebang(content: str) -> bool:
    """Check if the file starts with a shebang."""
    return content.startswith("#!")

def add_header_to_file(file_path: Path) -> bool:
    """Add Apache 2.0 header to a Python file. Returns True if modified."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Skip if already has Apache header
        if has_apache_header(content):
            print(f"SKIP: {file_path} (already has Apache header)")
            return False

        # Handle different file structures
        lines = content.split("\n")
        insert_index = 0

        # Skip shebang if present
        if lines and has_shebang(content):
            insert_index = 1

        # Skip encoding declarations
        while insert_index < len(lines):
            line = lines[insert_index].strip()
            if (
                line.startswith("# -*- coding:")
                or line.startswith("# coding:")
                or line.startswith("# coding=")
            ):
                insert_index += 1
            else:
                break

        # Insert header
        header_lines = APACHE_HEADER.rstrip().split("\n")
        for i, header_line in enumerate(header_lines):
            lines.insert(insert_index + i, header_line)

        # Write back to file
        new_content = "\n".join(lines)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(new_content)

        print(f"ADDED: {file_path}")
        return True

    except Exception as e:
        print(f"ERROR: {file_path} - {e}")
        return False

def find_python_files(root_dir: Path) -> List[Path]:
    """Find all Python files in the project, excluding certain directories."""
    exclude_dirs = {
        ".git",
        ".venv",
        "__pycache__",
        ".pytest_cache",
        "node_modules",
        ".mypy_cache",
        "build",
        "dist",
        ".kiro",  # Exclude Kiro configuration
    }

    python_files = []

    for root, dirs, files in os.walk(root_dir):
        # Remove excluded directories from dirs list to prevent traversal
        dirs[:] = [d for d in dirs if d not in exclude_dirs]

        for file in files:
            if file.endswith(".py"):
                file_path = Path(root) / file
                python_files.append(file_path)

    return sorted(python_files)

def main():
    """Main function to add Apache headers to all Python files."""
    # Get project root directory
    script_dir = Path(__file__).parent
    project_root = script_dir.parent

    print(f"Adding Apache 2.0 headers to Python files in: {project_root}")
    print("=" * 60)

    # Find all Python files
    python_files = find_python_files(project_root)

    if not python_files:
        print("No Python files found!")
        return 1

    print(f"Found {len(python_files)} Python files")
    print()

    # Process each file
    modified_count = 0
    for file_path in python_files:
        if add_header_to_file(file_path):
            modified_count += 1

    print()
    print("=" * 60)
    print(f"Summary: Modified {modified_count} out of {len(python_files)} files")

    return 0

if __name__ == "__main__":
    sys.exit(main())
