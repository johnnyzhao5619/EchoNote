#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2025 EchoNote Contributors

"""macOS build script for EchoNote using PyInstaller with PySide6."""

import sys
import subprocess
import shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from build_config import PROJECT_ROOT, DIST_DIR, APP_NAME, get_pyinstaller_args, clean_build_dirs


def build_executable():
    """Build the executable using PyInstaller."""
    args = ["pyinstaller"] + get_pyinstaller_args()
    result = subprocess.run(args, cwd=PROJECT_ROOT)
    if result.returncode != 0:
        sys.exit(1)


def create_dmg():
    """Create DMG installer if requested."""
    if "--dmg" not in sys.argv:
        return

    app_bundle = DIST_DIR / f"{APP_NAME}.app"
    if not app_bundle.exists():
        return

    dmg_path = DIST_DIR / "echonote-macos-x64.dmg"
    dmg_dir = DIST_DIR / "dmg_temp"

    if dmg_dir.exists():
        shutil.rmtree(dmg_dir)
    dmg_dir.mkdir()

    shutil.copytree(app_bundle, dmg_dir / f"{APP_NAME}.app")
    (dmg_dir / "Applications").symlink_to("/Applications")

    cmd = [
        "hdiutil",
        "create",
        "-volname",
        APP_NAME,
        "-srcfolder",
        str(dmg_dir),
        "-ov",
        "-format",
        "UDZO",
        str(dmg_path),
    ]
    subprocess.run(cmd)

    shutil.rmtree(dmg_dir)


def create_tarball():
    """Create tarball distribution."""
    app_bundle = DIST_DIR / f"{APP_NAME}.app"
    if not app_bundle.exists():
        return

    tarball_path = DIST_DIR / "echonote-macos-x64.tar.gz"
    cmd = ["tar", "-czf", str(tarball_path), "-C", str(DIST_DIR), f"{APP_NAME}.app"]
    subprocess.run(cmd)


def main():
    """Main build function."""
    if "--clean" in sys.argv:
        clean_build_dirs()

    build_executable()
    create_dmg()
    create_tarball()

    print(f"✅ macOS build completed: {DIST_DIR}")


if __name__ == "__main__":
    main()
