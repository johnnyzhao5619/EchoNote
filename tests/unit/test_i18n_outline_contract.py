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
