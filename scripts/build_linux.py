#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2025 EchoNote Contributors

"""Linux build script for EchoNote using PyInstaller with PySide6."""

import sys
import subprocess
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from build_config import PROJECT_ROOT, DIST_DIR, APP_NAME, get_pyinstaller_args, clean_build_dirs


def build_executable():
    """Build the executable using PyInstaller."""
    args = ["pyinstaller"] + get_pyinstaller_args()
    result = subprocess.run(args, cwd=PROJECT_ROOT)
    if result.returncode != 0:
        sys.exit(1)


def create_tarball():
    """Create distribution tarball."""
    app_dir = DIST_DIR / APP_NAME
    if not app_dir.exists():
        return

    tarball_path = DIST_DIR / "echonote-linux-x64.tar.gz"
    cmd = ["tar", "-czf", str(tarball_path), "-C", str(DIST_DIR), APP_NAME]
    subprocess.run(cmd)


def main():
    """Main build function."""
    if "--clean" in sys.argv:
        clean_build_dirs()

    build_executable()
    create_tarball()

    print(f"✅ Linux build completed: {DIST_DIR}")


if __name__ == "__main__":
    main()
