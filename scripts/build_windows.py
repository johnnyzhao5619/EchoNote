#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2025 EchoNote Contributors

"""Windows build script for EchoNote using PyInstaller with PySide6."""

import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from build_config import (
    APP_NAME,
    APP_VERSION,
    DIST_DIR,
    PROJECT_ROOT,
    clean_build_dirs,
    get_pyinstaller_args,
)


def create_version_info():
    """Create version info file for Windows executable."""
    version_content = f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers=(1, 0, 0, 0), prodvers=(1, 0, 0, 0), mask=0x3f, flags=0x0, OS=0x4, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable(u'040904B0', [
      StringStruct(u'CompanyName', u'EchoNote Contributors'),
      StringStruct(u'FileDescription', u'Voice transcription and calendar management'),
      StringStruct(u'FileVersion', u'{APP_VERSION}'),
      StringStruct(u'ProductName', u'{APP_NAME}'),
      StringStruct(u'ProductVersion', u'{APP_VERSION}')
    ])]),
    VarFileInfo([VarStruct(u'Translation', [1033, 1200])])
  ]
)"""

    version_file = PROJECT_ROOT / "scripts" / "version_info.txt"
    with open(version_file, "w") as f:
        f.write(version_content)
    return version_file


def build_executable():
    """Build the executable using PyInstaller."""
    create_version_info()
    args = ["pyinstaller"] + get_pyinstaller_args()
    args.extend(["--version-file", str(PROJECT_ROOT / "scripts" / "version_info.txt")])

    result = subprocess.run(args, cwd=PROJECT_ROOT)
    if result.returncode != 0:
        sys.exit(1)


def create_zip():
    """Create ZIP distribution."""
    app_dir = DIST_DIR / APP_NAME
    if not app_dir.exists():
        return

    zip_path = DIST_DIR / "echonote-windows-x64"
    shutil.make_archive(str(zip_path), "zip", str(DIST_DIR), APP_NAME)


def main():
    """Main build function."""
    if "--clean" in sys.argv:
        clean_build_dirs()

    build_executable()
    create_zip()

    print(f"✅ Windows build completed: {DIST_DIR}")


if __name__ == "__main__":
    main()
