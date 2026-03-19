# SPDX-License-Identifier: Apache-2.0
"""I18n outline contract tests.

These tests enforce structural parity across translation locales and prevent
missing/extra keys when i18n files evolve.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TRANSLATIONS_DIR = PROJECT_ROOT / "resources" / "translations"
I18N_OUTLINE_PATH = TRANSLATIONS_DIR / "i18n_outline.json"


def _load_outline() -> dict[str, Any]:
    return json.loads(I18N_OUTLINE_PATH.read_text(encoding="utf-8"))


def _load_locale(locale: str) -> dict[str, Any]:
    path = TRANSLATIONS_DIR / f"{locale}.json"
    assert path.exists(), f"Locale file is missing: {path}"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict), f"Locale root must be an object: {path}"
    return data


def _flatten_dict_key_paths(data: dict[str, Any], prefix: str = "") -> set[str]:
    key_paths: set[str] = set()
    for key, value in data.items():
        current = f"{prefix}.{key}" if prefix else key
        key_paths.add(current)
        if isinstance(value, dict):
            key_paths.update(_flatten_dict_key_paths(value, current))
    return key_paths


def _has_nested_key(data: dict[str, Any], dotted_key: str) -> bool:
    current: Any = data
    for part in dotted_key.split("."):
        if not isinstance(current, dict) or part not in current:
            return False
        current = current[part]
    return True


def test_outline_declares_valid_locale_list_and_sections():
    outline = _load_outline()
    locales = outline.get("locales", [])
    sections = outline.get("sections", [])

    assert locales, "i18n outline must declare locales"
    assert sections, "i18n outline must declare top-level sections"
    assert len(locales) == len(set(locales)), "locale list must not contain duplicates"
    assert len(sections) == len(set(sections)), "section list must not contain duplicates"


def test_all_locales_match_outline_top_level_sections():
    outline = _load_outline()
    locales = outline["locales"]
    sections = set(outline["sections"])

    for locale in locales:
        data = _load_locale(locale)
        keys = set(data.keys())
        missing = sorted(sections - keys)
        extra = sorted(keys - sections)
        assert not missing, f"Locale '{locale}' missing top-level sections: {missing}"
        assert not extra, f"Locale '{locale}' has undeclared top-level sections: {extra}"


def test_all_locales_have_identical_nested_key_paths():
    outline = _load_outline()
    locales = outline["locales"]
    base_locale = outline.get("base_locale") or locales[0]

    base_data = _load_locale(base_locale)
    base_keys = _flatten_dict_key_paths(base_data)

    for locale in locales:
        data = _load_locale(locale)
        keys = _flatten_dict_key_paths(data)
        missing = sorted(base_keys - keys)
        extra = sorted(keys - base_keys)
        assert not missing, f"Locale '{locale}' missing nested keys vs '{base_locale}': {missing[:20]}"
        assert not extra, f"Locale '{locale}' has extra nested keys vs '{base_locale}': {extra[:20]}"


def test_all_locales_have_dual_view_and_detached_window_keys():
    outline = _load_outline()
    locales = outline["locales"]
    required_keys = outline.get("required_nested_keys", {}).get("workspace", [])

    assert required_keys, "i18n outline must declare required workspace rearchitecture keys"

    for locale in locales:
        workspace = _load_locale(locale)["workspace"]
        missing = sorted(key for key in required_keys if not _has_nested_key(workspace, key))
        assert not missing, f"Locale '{locale}' missing required workspace keys: {missing}"


def test_i18n_outline_covers_workspace_task_window_and_recording_console_copy():
    outline = _load_outline()
    workspace_keys = set(outline.get("required_nested_keys", {}).get("workspace", []))

    assert "task_window_title" in workspace_keys
    assert "task_summary_total" in workspace_keys
    assert "task_summary_active" in workspace_keys
    assert "task_summary_failed" in workspace_keys
    assert "recording_console.session_options_title" in workspace_keys
    assert "recording_console.default_input_source" in workspace_keys


def test_i18n_outline_covers_workspace_item_meta_copy():
    outline = _load_outline()
    workspace_keys = set(outline.get("required_nested_keys", {}).get("workspace", []))

    assert "item_meta_event" in workspace_keys
    assert "item_meta_task" in workspace_keys
    assert "item_meta_original_file" in workspace_keys
    assert "item_meta_updated" in workspace_keys
    assert "item_source_workspace_note" in workspace_keys
    assert "item_source_batch_transcription" in workspace_keys
    assert "item_source_realtime_recording" in workspace_keys
    assert "item_source_ai_generated" in workspace_keys
    assert "item_source_unknown" in workspace_keys


def test_i18n_outline_covers_workspace_inspector_section_titles():
    outline = _load_outline()
    workspace_keys = set(outline.get("required_nested_keys", {}).get("workspace", []))

    assert "inspector_section_ai" in workspace_keys
    assert "inspector_section_media" in workspace_keys
    assert "inspector_section_metadata" in workspace_keys
    assert "ai_panel_subtitle" in workspace_keys
    assert "inspector_label_source" in workspace_keys
    assert "inspector_label_event" in workspace_keys
    assert "inspector_label_task" in workspace_keys
    assert "inspector_label_original_file" in workspace_keys
    assert "inspector_label_updated" in workspace_keys
    assert "inspector_event" in workspace_keys
    assert "inspector_task" in workspace_keys
    assert "inspector_original_file" in workspace_keys


def test_i18n_outline_covers_workspace_recording_dock_compact_copy():
    outline = _load_outline()
    workspace_keys = set(outline.get("required_nested_keys", {}).get("workspace", []))

    assert "recording_console.settings_tooltip" in workspace_keys
    assert "recording_console.enable_transcription_tooltip" in workspace_keys
    assert "recording_console.enable_translation_tooltip" in workspace_keys
    assert "recording_console.show_overlay_tooltip" in workspace_keys
    assert "recording_console.open_latest_document_tooltip" in workspace_keys


def test_visual_polish_contracts_are_documented_in_project_guides():
    agents_text = (PROJECT_ROOT / "AGENTS.md").read_text(encoding="utf-8")
    docs_readme_text = (PROJECT_ROOT / "docs" / "README.md").read_text(encoding="utf-8")
    release_skill_text = (
        PROJECT_ROOT / "skills" / "release-process" / "SKILL.md"
    ).read_text(encoding="utf-8")
    changelog_text = (PROJECT_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")

    assert "2026-03-15-workspace-redbox-closure-plan.md" in agents_text
    assert "2026-03-15-workspace-redbox-closure-plan.md" in docs_readme_text
    assert "pytest tests/unit/test_main_window_shell.py -v" in release_skill_text
    assert "theme/i18n/tests/docs" in changelog_text
