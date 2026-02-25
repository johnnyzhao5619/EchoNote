# SPDX-License-Identifier: Apache-2.0
"""Contract tests for dynamic UI property updates."""

from __future__ import annotations

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
UI_DIR = PROJECT_ROOT / "ui"
STYLE_UTILS_PATH = UI_DIR / "common" / "style_utils.py"

DYNAMIC_PROPERTY_PATTERN = re.compile(r'setProperty\(\s*"(state|active|recording)"')


def test_dynamic_style_properties_use_style_utils_helpers():
    """UI modules should avoid direct dynamic style-property writes."""
    offenders: list[str] = []
    for py_file in UI_DIR.rglob("*.py"):
        if py_file == STYLE_UTILS_PATH:
            continue
        content = py_file.read_text(encoding="utf-8")
        if DYNAMIC_PROPERTY_PATTERN.search(content):
            offenders.append(str(py_file.relative_to(PROJECT_ROOT)))

    assert not offenders, (
        "Direct dynamic setProperty calls found; use set_widget_state/"
        f"set_widget_dynamic_property instead: {offenders}"
    )
