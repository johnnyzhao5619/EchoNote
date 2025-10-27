#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""
Detect hardcoded UI strings that should be internationalized.

Scans UI files for hardcoded text in setText(), setWindowTitle(),
setToolTip(), and QMessageBox calls.
"""

import re
import sys
from pathlib import Path
from typing import Dict, List


def find_hardcoded_ui_strings(file_path: Path) -> List[Dict]:
    """Find hardcoded UI strings in a Python file."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except (UnicodeDecodeError, FileNotFoundError):
        return []

    issues = []
    lines = content.split("\n")

    # Patterns for UI method calls with hardcoded strings
    ui_patterns = [
        (r'\.setText\s*\(\s*["\']([^"\']+)["\']\s*\)', "setText"),
        (r'\.setWindowTitle\s*\(\s*["\']([^"\']+)["\']\s*\)', "setWindowTitle"),
        (r'\.setToolTip\s*\(\s*["\']([^"\']+)["\']\s*\)', "setToolTip"),
        (r'\.setPlaceholderText\s*\(\s*["\']([^"\']+)["\']\s*\)', "setPlaceholderText"),
        (r'QMessageBox\.[^(]*\([^,]*["\']([^"\']+)["\']', "QMessageBox"),
    ]

    for line_num, line in enumerate(lines, 1):
        # Skip comments and docstrings
        stripped = line.strip()
        if stripped.startswith("#") or stripped.startswith('"""') or stripped.startswith("'''"):
            continue

        for pattern, method in ui_patterns:
            matches = re.finditer(pattern, line)
            for match in matches:
                text = match.group(1)
                if _is_user_facing_text(text):
                    issues.append(
                        {
                            "line": line_num,
                            "method": method,
                            "text": text,
                            "full_line": line.strip(),
                        }
                    )

    return issues


def _is_user_facing_text(text: str) -> bool:
    """Check if text is likely user-facing and should be internationalized."""
    # Skip very short strings or technical patterns
    if len(text) < 3 or re.match(r"^[a-z_]+$|^\d+%?$|^#[0-9A-Fa-f]{6}$", text):
        return False

    # Skip common technical terms
    if text.lower() in {"debug", "info", "warning", "error", "get", "post", "json", "utf-8"}:
        return False

    # Check for user-facing patterns
    return bool(
        re.match(
            r"^[A-Z].*[.!?]$|^[A-Z].*\s.*$|.*(button|dialog|window|menu|failed|success|error).*",
            text,
            re.IGNORECASE,
        )
    )


def main():
    """Main function."""
    ui_dir = Path("ui")
    if not ui_dir.exists():
        print("UI directory not found!")
        return

    results = {}
    for py_file in ui_dir.rglob("*.py"):
        issues = find_hardcoded_ui_strings(py_file)
        if issues:
            results[str(py_file.relative_to(Path(".")))] = issues

    total_issues = sum(len(issues) for issues in results.values())

    if total_issues == 0:
        print("✅ No hardcoded UI strings found!")
        sys.exit(0)

    print(f"❌ Found {total_issues} hardcoded UI strings in {len(results)} files:")
    print()

    for filepath, issues in sorted(results.items()):
        print(f"  {filepath}: {len(issues)} issues")
        for issue in issues:
            text_preview = issue["text"][:50] + ("..." if len(issue["text"]) > 50 else "")
            print(f"    Line {issue['line']}: {issue['method']} - \"{text_preview}\"")

    print()
    print("Fix: Replace with self.i18n.t('translation.key') calls")
    sys.exit(1)


if __name__ == "__main__":
    main()
