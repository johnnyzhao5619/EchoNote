#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2025 EchoNote Contributors

"""Common build configuration for PyInstaller packaging with PySide6."""

import os
import platform
from pathlib import Path
from typing import Any, Dict, List

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
MAIN_SCRIPT = PROJECT_ROOT / "main.py"
DIST_DIR = PROJECT_ROOT / "dist"
BUILD_DIR = PROJECT_ROOT / "build"

# App metadata
APP_NAME = "EchoNote"
APP_VERSION = "1.4.0"

# PySide6 hidden imports
HIDDEN_IMPORTS = [
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    "PySide6.QtMultimedia",
    "PySide6.QtNetwork",
    "PySide6.QtSvg",
    "faster_whisper",
    "torch",
    "torchaudio",
    "librosa",
    "soundfile",
    "PyAudio",
    "httpx",
    "requests",
    "authlib",
    "cryptography",
    "APScheduler",
    "psutil",
    "core",
    "engines",
    "data",
    "ui",
    "utils",
    "config",
]

# Data files to include
DATA_FILES = [
    ("config/default_config.json", "config/"),
    ("data/database/schema.sql", "data/database/"),
    ("resources/themes/", "resources/themes/"),
    ("resources/translations/", "resources/translations/"),
    ("resources/icons/", "resources/icons/"),
    ("LICENSE", "."),
    ("README.md", "."),
]

# Modules to exclude
EXCLUDE_MODULES = ["PyQt6", "pytest", "black", "isort", "flake8", "mypy", "tkinter"]


def get_platform_config() -> Dict[str, Any]:
    """Get platform-specific configuration."""
    system = platform.system().lower()

    if system == "darwin":  # macOS
        return {"icon": str(PROJECT_ROOT / "resources" / "icons" / "echonote.icns")}
    elif system == "windows":  # Windows
        return {"icon": str(PROJECT_ROOT / "resources" / "icons" / "echonote.ico")}
    else:  # Linux
        return {"icon": str(PROJECT_ROOT / "resources" / "icons" / "echonote.png")}


def get_pyside6_binaries() -> List[tuple]:
    """Get PySide6 binaries to include."""
    try:
        import PySide6

        pyside6_path = Path(PySide6.__file__).parent

        binaries = []
        plugins_dir = pyside6_path / "Qt" / "plugins"
        if plugins_dir.exists():
            for plugin_type in ["platforms", "styles", "imageformats"]:
                plugin_path = plugins_dir / plugin_type
                if plugin_path.exists():
                    binaries.append((str(plugin_path), f"PySide6/Qt/plugins/{plugin_type}"))

        translations_dir = pyside6_path / "Qt" / "translations"
        if translations_dir.exists():
            binaries.append((str(translations_dir), "PySide6/Qt/translations"))

        return binaries
    except ImportError:
        return []


def clean_build_dirs():
    """Clean previous build directories."""
    import shutil

    for path in [BUILD_DIR, DIST_DIR]:
        if path.exists():
            shutil.rmtree(path)


def get_pyinstaller_args(console: bool = False) -> List[str]:
    """Get PyInstaller command line arguments."""
    platform_config = get_platform_config()

    args = [
        str(MAIN_SCRIPT),
        "--name",
        APP_NAME,
        "--distpath",
        str(DIST_DIR),
        "--workpath",
        str(BUILD_DIR),
        "--clean",
        "--noconfirm",
    ]

    args.append("--console" if console else "--windowed")

    # Icon
    if "icon" in platform_config and Path(platform_config["icon"]).exists():
        args.extend(["--icon", platform_config["icon"]])

    # Hidden imports
    for module in HIDDEN_IMPORTS:
        args.extend(["--hidden-import", module])

    # Data files
    for src, dst in DATA_FILES:
        src_path = PROJECT_ROOT / src
        if src_path.exists():
            args.extend(["--add-data", f"{src_path}{os.pathsep}{dst}"])

    # PySide6 binaries
    for src, dst in get_pyside6_binaries():
        args.extend(["--add-binary", f"{src}{os.pathsep}{dst}"])

    # Exclude modules
    for module in EXCLUDE_MODULES:
        args.extend(["--exclude-module", module])

    return args


if __name__ == "__main__":
    print(f"Project root: {PROJECT_ROOT}")
    print(f"Platform: {platform.system()}")
    print(f"PySide6 binaries: {len(get_pyside6_binaries())} items")
