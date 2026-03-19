# SPDX-License-Identifier: Apache-2.0
"""Shared workspace drag payload helpers."""

from __future__ import annotations

import json
from typing import Optional


WORKSPACE_TEXT_DRAG_MIME = "application/x-echonote-workspace-text-item"
WORKSPACE_DRAG_SOURCE_EVENT = "event"
WORKSPACE_DRAG_SOURCE_BATCH_TASK = "batch_task"


def build_workspace_text_drag_payload(item_id: str, source_domain: str) -> dict[str, str]:
    """Return the normalized payload used for external workspace text drags."""
    return {
        "workspace_item_id": str(item_id or "").strip(),
        "source_domain": str(source_domain or "").strip(),
    }


def serialize_workspace_text_drag_payload(payload: dict[str, str]) -> bytes:
    """Serialize workspace drag payload into bytes for QMimeData."""
    return json.dumps(payload, ensure_ascii=False).encode("utf-8")


def parse_workspace_text_drag_payload(raw_payload: bytes | bytearray | memoryview) -> Optional[dict[str, str]]:
    """Parse a workspace text drag payload from mime bytes."""
    try:
        decoded = json.loads(bytes(raw_payload).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
        return None
    if not isinstance(decoded, dict):
        return None
    item_id = str(decoded.get("workspace_item_id") or "").strip()
    source_domain = str(decoded.get("source_domain") or "").strip()
    if not item_id or source_domain not in {
        WORKSPACE_DRAG_SOURCE_EVENT,
        WORKSPACE_DRAG_SOURCE_BATCH_TASK,
    }:
        return None
    return {
        "workspace_item_id": item_id,
        "source_domain": source_domain,
    }
