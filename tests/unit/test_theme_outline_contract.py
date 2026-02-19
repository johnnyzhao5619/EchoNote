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
"""Theme outline contract tests.

These tests enforce a single style contract across all QSS themes and prevent
light/dark divergence when new semantic roles are introduced.
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from typing import Any

from ui.common.theme import ThemeManager
from ui.constants import APP_TOP_BAR_CONTROL_HEIGHT, CONTROL_BUTTON_MIN_HEIGHT, REALTIME_BUTTON_MIN_WIDTH


PROJECT_ROOT = Path(__file__).resolve().parents[2]
UI_DIR = PROJECT_ROOT / "ui"
THEMES_DIR = PROJECT_ROOT / "resources" / "themes"
THEME_OUTLINE_PATH = THEMES_DIR / "theme_outline.json"

ROLE_SELECTOR_PATTERN = re.compile(r'\[role="([^"]+)"\]')
ROLE_KEYWORDS = {"role", "role_name"}


def _load_theme_outline() -> dict[str, Any]:
    return json.loads(THEME_OUTLINE_PATH.read_text(encoding="utf-8"))


def _collect_module_str_constants(module: ast.Module) -> dict[str, str]:
    constants: dict[str, str] = {}
    for node in module.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name) and isinstance(node.value, ast.Constant):
                if isinstance(node.value.value, str):
                    constants[target.id] = node.value.value
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and isinstance(node.value, ast.Constant):
                if isinstance(node.value.value, str):
                    constants[node.target.id] = node.value.value
    return constants


def _resolve_role_value(node: ast.AST, constants: dict[str, str]) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name):
        return constants.get(node.id)
    return None


def _collect_ui_roles_from_code() -> set[str]:
    roles: set[str] = set()
    for py_file in UI_DIR.rglob("*.py"):
        source = py_file.read_text(encoding="utf-8")
        module = ast.parse(source)
        constants = _collect_module_str_constants(module)

        for node in ast.walk(module):
            if not isinstance(node, ast.Call):
                continue

            if isinstance(node.func, ast.Attribute) and node.func.attr == "setProperty":
                if len(node.args) >= 2:
                    first = node.args[0]
                    if isinstance(first, ast.Constant) and first.value == "role":
                        role = _resolve_role_value(node.args[1], constants)
                        if role:
                            roles.add(role)

            for keyword in node.keywords:
                if keyword.arg in ROLE_KEYWORDS:
                    role = _resolve_role_value(keyword.value, constants)
                    if role:
                        roles.add(role)

    return roles


def _theme_names_from_outline(outline: dict[str, Any]) -> tuple[str, ...]:
    names = tuple(outline.get("themes", ()))
    assert names, "Theme outline must declare at least one theme."
    return names


def _read_theme_text(theme_name: str) -> str:
    path = THEMES_DIR / f"{theme_name}.qss"
    assert path.exists(), f"Theme QSS file is missing: {path}"
    return path.read_text(encoding="utf-8")


def _extract_selector_block(theme_text: str, selector: str) -> str:
    pattern = re.compile(rf"(?m)^{re.escape(selector)}\s*\{{(.*?)^\}}", re.S)
    match = pattern.search(theme_text)
    assert match, f"Selector block not found: {selector}"
    return match.group(1)


def _get_css_property(block: str, property_name: str) -> str:
    pattern = re.compile(rf"(?m)^\s*{re.escape(property_name)}\s*:\s*([^;]+);")
    match = pattern.search(block)
    assert match, f"CSS property '{property_name}' not found in selector block."
    return match.group(1).strip()


def _count_selector_blocks(theme_text: str, selector: str) -> int:
    pattern = re.compile(rf"(?m)^{re.escape(selector)}\s*\{{")
    return len(pattern.findall(theme_text))


def _collect_duplicate_selectors(theme_text: str) -> dict[str, int]:
    pattern = re.compile(r"(?m)^([^\n{}][^\n{}]*?)\s*\{")
    counts: dict[str, int] = {}
    for match in pattern.finditer(theme_text):
        selector = match.group(1).strip()
        counts[selector] = counts.get(selector, 0) + 1
    return {selector: count for selector, count in counts.items() if count > 1}


def test_theme_outline_selectors_exist_for_all_themes():
    outline = _load_theme_outline()
    theme_names = _theme_names_from_outline(outline)
    sections = outline.get("sections", [])
    assert sections, "Theme outline must include sections."

    for theme_name in theme_names:
        theme_text = _read_theme_text(theme_name)
        for section in sections:
            section_id = section["id"]
            for selector in section.get("selectors", []):
                assert selector in theme_text, (
                    f"Theme '{theme_name}' is missing outline selector "
                    f"'{selector}' in section '{section_id}'."
                )


def test_ui_roles_are_covered_by_each_theme_qss():
    outline = _load_theme_outline()
    theme_names = _theme_names_from_outline(outline)
    ui_roles = _collect_ui_roles_from_code()
    assert ui_roles, "Expected at least one semantic UI role in code."

    for theme_name in theme_names:
        qss_roles = set(ROLE_SELECTOR_PATTERN.findall(_read_theme_text(theme_name)))
        missing_roles = sorted(ui_roles - qss_roles)
        assert not missing_roles, (
            f"Theme '{theme_name}' is missing semantic role selectors: {missing_roles}"
        )


def test_all_themes_share_identical_role_sets():
    outline = _load_theme_outline()
    theme_names = _theme_names_from_outline(outline)
    role_sets = {
        name: set(ROLE_SELECTOR_PATTERN.findall(_read_theme_text(name))) for name in theme_names
    }
    first_name = theme_names[0]
    baseline = role_sets[first_name]
    for name in theme_names[1:]:
        assert role_sets[name] == baseline, (
            f"Role set drift detected between '{first_name}' and '{name}'."
        )


def test_theme_manager_and_qss_outline_are_consistent():
    outline = _load_theme_outline()
    qss_themes = set(_theme_names_from_outline(outline))
    manager_themes = {name for name in ThemeManager.THEMES if name != "system"}
    palette_themes = set(ThemeManager.PALETTES.keys())

    assert qss_themes == manager_themes, (
        "ThemeManager.THEMES (excluding system) must match theme_outline themes."
    )
    assert qss_themes <= palette_themes, "Every QSS theme must have a ThemeManager palette."

    first_theme = next(iter(sorted(qss_themes)))
    baseline_keys = set(ThemeManager.PALETTES[first_theme].keys())
    for theme_name in sorted(qss_themes):
        assert set(ThemeManager.PALETTES[theme_name].keys()) == baseline_keys, (
            f"Palette token mismatch in theme '{theme_name}'."
        )


def test_core_selector_has_single_definition_per_theme():
    outline = _load_theme_outline()
    theme_names = _theme_names_from_outline(outline)

    for theme_name in theme_names:
        text = _read_theme_text(theme_name)
        assert len(re.findall(r"(?m)^QPushButton\s*\{", text)) == 1, (
            f"Theme '{theme_name}' must keep a single global QPushButton definition."
        )
        assert "QLineEdit, QTextEdit, QPlainTextEdit {" not in text, (
            f"Theme '{theme_name}' should avoid legacy duplicate text-input baseline block."
        )


def test_density_contract_for_core_controls():
    outline = _load_theme_outline()
    theme_names = _theme_names_from_outline(outline)

    for theme_name in theme_names:
        text = _read_theme_text(theme_name)

        push_button_block = _extract_selector_block(text, "QPushButton")
        assert _get_css_property(push_button_block, "min-height") == "28px"

        marker_block = _extract_selector_block(text, 'QPushButton[role="realtime-marker-action"]')
        assert _get_css_property(marker_block, "min-width") == f"{REALTIME_BUTTON_MIN_WIDTH}px"

        duration_block = _extract_selector_block(text, 'QLabel[role="realtime-duration"]')
        assert _get_css_property(duration_block, "min-height") == f"{CONTROL_BUTTON_MIN_HEIGHT}px"

        top_search_block = _extract_selector_block(text, "QLineEdit#top_bar_search")
        assert _get_css_property(top_search_block, "min-height") == f"{APP_TOP_BAR_CONTROL_HEIGHT}px"
        assert _get_css_property(top_search_block, "max-height") == f"{APP_TOP_BAR_CONTROL_HEIGHT}px"

        hint_block = _extract_selector_block(text, "QLabel#top_bar_hint")
        assert _get_css_property(hint_block, "min-height") == f"{APP_TOP_BAR_CONTROL_HEIGHT}px"
        assert _get_css_property(hint_block, "max-height") == f"{APP_TOP_BAR_CONTROL_HEIGHT}px"


def test_duplicated_semantic_blocks_are_deduplicated():
    outline = _load_theme_outline()
    theme_names = _theme_names_from_outline(outline)
    single_source_selectors = (
        'QFrame[role="batch-viewer-toolbar"] QPushButton[role="batch-viewer-edit-action"][state="active"]',
        'QFrame[role="batch-viewer-toolbar"] QPushButton[role="batch-viewer-copy-action"]',
        'QFrame[role="batch-viewer-toolbar"] QPushButton[role="batch-viewer-export-action"]',
        'QPushButton[role="model-delete"]',
        'QPushButton#clear_markers_button',
        'QLabel[role="time-display"]',
        'QWidget[role="task-item"]',
        'QPushButton[role="settings-cancel-action"]',
        "QCheckBox::indicator",
        "QRadioButton::indicator",
        'QSlider[role="audio-player-progress"]::groove:horizontal',
        'QSlider[role="audio-player-volume"]::groove:horizontal',
    )

    for theme_name in theme_names:
        text = _read_theme_text(theme_name)
        for selector in single_source_selectors:
            assert _count_selector_blocks(text, selector) <= 1, (
                f"Theme '{theme_name}' should not define '{selector}' more than once."
            )


def test_theme_qss_has_no_duplicate_selectors():
    outline = _load_theme_outline()
    theme_names = _theme_names_from_outline(outline)

    for theme_name in theme_names:
        text = _read_theme_text(theme_name)
        duplicates = _collect_duplicate_selectors(text)
        assert not duplicates, (
            f"Theme '{theme_name}' has duplicate selector blocks: "
            f"{sorted(duplicates.items())[:10]}"
        )
