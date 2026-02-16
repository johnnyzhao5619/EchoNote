#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""
Audit and optionally fill missing i18n keys from a base translation file.

Usage:
  python scripts/audit_i18n.py
  python scripts/audit_i18n.py --write
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


BASE_LOCALE = "en_US"
TARGET_LOCALES = ("zh_CN", "fr_FR")


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise TypeError(f"Expected object at top level in {path}")
    return data


def merge_missing(base: Any, target: Any) -> Any:
    if isinstance(base, dict):
        target_dict = target if isinstance(target, dict) else {}
        merged: dict[str, Any] = {}
        for key, base_value in base.items():
            merged[key] = merge_missing(base_value, target_dict.get(key))
        return merged
    if target is None:
        return base
    return target


def list_missing_keys(base: Any, target: Any, prefix: str = "") -> list[str]:
    missing: list[str] = []
    if not isinstance(base, dict):
        return missing

    target_dict = target if isinstance(target, dict) else {}
    for key, base_value in base.items():
        current = f"{prefix}.{key}" if prefix else key
        if key not in target_dict:
            missing.append(current)
            continue
        missing.extend(list_missing_keys(base_value, target_dict[key], current))
    return missing


def audit_locale(translations_dir: Path, locale: str, write: bool) -> tuple[int, Path]:
    base_path = translations_dir / f"{BASE_LOCALE}.json"
    target_path = translations_dir / f"{locale}.json"

    base_data = load_json(base_path)
    target_data = load_json(target_path) if target_path.exists() else {}

    missing_before = list_missing_keys(base_data, target_data)
    merged_data = merge_missing(base_data, target_data)
    missing_after = list_missing_keys(base_data, merged_data)

    if write:
        with target_path.open("w", encoding="utf-8") as f:
            json.dump(merged_data, f, ensure_ascii=False, indent=2)
            f.write("\n")

    if missing_after:
        raise RuntimeError(f"Locale {locale} still has missing keys after merge")

    return len(missing_before), target_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit and fill i18n translation keys.")
    parser.add_argument("--write", action="store_true", help="Write merged locale files.")
    parser.add_argument(
        "--translations-dir",
        default="resources/translations",
        help="Path to translation directory",
    )
    args = parser.parse_args()

    translations_dir = Path(args.translations_dir)
    if not translations_dir.exists():
        raise FileNotFoundError(f"Translations directory not found: {translations_dir}")

    print(f"Base locale: {BASE_LOCALE}")
    print(f"Target locales: {', '.join(TARGET_LOCALES)}")
    print(f"Mode: {'write' if args.write else 'audit-only'}")

    total_missing = 0
    for locale in TARGET_LOCALES:
        missing_count, path = audit_locale(translations_dir, locale, args.write)
        total_missing += missing_count
        print(f"[{locale}] missing keys: {missing_count} -> {path}")

    print(f"Total missing keys: {total_missing}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
