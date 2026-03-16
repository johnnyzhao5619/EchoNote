# SPDX-License-Identifier: Apache-2.0
"""Workspace item formatting helpers."""

from __future__ import annotations

from datetime import datetime

from utils.i18n import I18nQtManager


_WORKSPACE_SOURCE_KEY_MAP = {
    "workspace_note": "workspace.item_source_workspace_note",
    "batch_transcription": "workspace.item_source_batch_transcription",
    "realtime_recording": "workspace.item_source_realtime_recording",
    "ai_generated": "workspace.item_source_ai_generated",
}


def format_workspace_source_label(i18n: I18nQtManager, source: str) -> str:
    """Render workspace source metadata with localized labels when available."""
    translation_key = _WORKSPACE_SOURCE_KEY_MAP.get(source)
    if translation_key:
        return i18n.t(translation_key)
    if not source:
        return i18n.t("workspace.item_source_unknown")
    return source.replace("_", " ").title()


def format_workspace_updated_at(updated_at: str) -> str:
    """Render workspace timestamps in a compact user-facing format."""
    normalized = updated_at.strip()
    if not normalized:
        return ""
    try:
        parsed = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
        return parsed.strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return normalized.replace("T", " ")[:16]


def build_workspace_item_meta_text(
    i18n: I18nQtManager,
    metadata: dict,
    *,
    view_mode: str,
) -> str:
    """Build compact item metadata text for tooltips and secondary labels."""
    details: list[str] = []
    event_label = str(metadata.get("event_title") or metadata.get("event_id") or "").strip()
    if view_mode == "event" and event_label:
        details.append(i18n.t("workspace.item_meta_event", value=event_label))
    elif view_mode == "structure" and metadata.get("folder_name"):
        details.append(str(metadata["folder_name"]))

    source = metadata.get("source")
    if source:
        details.append(format_workspace_source_label(i18n, str(source)))
    task_id = str(metadata.get("task_id") or "").strip()
    if task_id:
        details.append(i18n.t("workspace.item_meta_task", value=task_id))
    original_file_name = str(metadata.get("original_file_name") or "").strip()
    if original_file_name:
        details.append(i18n.t("workspace.item_meta_original_file", value=original_file_name))
    updated_at = metadata.get("updated_at")
    if updated_at:
        details.append(
            i18n.t(
                "workspace.item_meta_updated",
                value=format_workspace_updated_at(str(updated_at)),
            )
        )
    return " / ".join(details)


def build_workspace_item_tooltip(
    i18n: I18nQtManager,
    title: str,
    metadata: dict,
    *,
    view_mode: str,
) -> str:
    """Build a multiline tooltip for a workspace tree item."""
    lines = [title]
    meta_text = build_workspace_item_meta_text(i18n, metadata, view_mode=view_mode)
    if meta_text:
        lines.append(meta_text)

    badge_texts: list[str] = []
    if metadata.get("is_orphaned"):
        badge_texts.append(i18n.t("workspace.item_badge_orphaned"))
    if metadata.get("event_id"):
        badge_texts.append(i18n.t("workspace.item_badge_event_linked"))
    if metadata.get("task_id"):
        badge_texts.append(i18n.t("workspace.item_badge_task_linked"))
    if metadata.get("has_audio"):
        badge_texts.append(i18n.t("workspace.item_badge_audio"))
    if badge_texts:
        lines.append(" · ".join(badge_texts))
    return "\n".join(line for line in lines if line)
