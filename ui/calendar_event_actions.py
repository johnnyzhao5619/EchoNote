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
"""Shared calendar event actions used by multiple UI pages."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from core.calendar.exceptions import SyncError
from core.qt_imports import QFileDialog, QMessageBox
from ui.constants import (
    CALENDAR_DELETE_ACTION_BUTTON_MIN_WIDTH,
    CALENDAR_DELETE_DIALOG_MIN_WIDTH,
    ROLE_DANGER,
    ROLE_DIALOG_SECONDARY_ACTION,
)

logger = logging.getLogger("echonote.ui.calendar_event_actions")

_ACTION_CANCEL = "cancel"
_ACTION_DELETE_EVENT_ONLY = "delete_event_only"
_ACTION_DELETE_WITH_ARTIFACTS = "delete_with_artifacts"
_ACTION_EXPORT_AND_DELETE = "export_and_delete"


def _show_info(parent: Any, title: str, message: str) -> None:
    if hasattr(parent, "show_info"):
        parent.show_info(title, message)
        return
    QMessageBox.information(parent, title, message)


def _show_warning(parent: Any, title: str, message: str) -> None:
    if hasattr(parent, "show_warning"):
        parent.show_warning(title, message)
        return
    QMessageBox.warning(parent, title, message, QMessageBox.StandardButton.Ok)


def _show_error(parent: Any, title: str, message: str) -> None:
    if hasattr(parent, "show_error"):
        parent.show_error(title, message)
        return
    QMessageBox.critical(parent, title, message, QMessageBox.StandardButton.Ok)


def _as_iso(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    if value is None:
        return ""
    return str(value)


def _safe_file_component(text: str) -> str:
    cleaned = re.sub(r"[^\w.-]+", "_", text.strip())
    cleaned = cleaned.strip("._")
    return cleaned or "event"


def _build_export_payload(event: Any, calendar_manager: Any) -> dict:
    event_id = str(getattr(event, "id", ""))
    attachments_payload = []

    workspace_manager = getattr(calendar_manager, "workspace_manager", None)
    if workspace_manager and event_id:
        try:
            artifacts = workspace_manager.get_event_artifacts(event_id)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Failed to load workspace artifacts for event %s: %s", event_id, exc)
        else:
            for asset in artifacts.get("attachments", []):
                attachments_payload.append(
                    {
                        "id": asset.get("id", ""),
                        "asset_role": asset.get("type", ""),
                        "file_path": asset.get("path", ""),
                        "file_size": asset.get("size"),
                        "created_at": _as_iso(asset.get("created_at", "")),
                        "text_content": asset.get("text_content"),
                    }
                )

    return {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "event": {
            "id": event_id,
            "title": getattr(event, "title", ""),
            "event_type": getattr(event, "event_type", ""),
            "start_time": _as_iso(getattr(event, "start_time", "")),
            "end_time": _as_iso(getattr(event, "end_time", "")),
            "location": getattr(event, "location", None),
            "attendees": getattr(event, "attendees", None),
            "description": getattr(event, "description", None),
            "reminder_minutes": getattr(event, "reminder_minutes", None),
            "source": getattr(event, "source", ""),
            "is_readonly": bool(getattr(event, "is_readonly", False)),
        },
        "attachments": attachments_payload,
    }


def _export_event_snapshot(
    parent: Any, i18n: Any, calendar_manager: Any, event: Any
) -> Optional[str]:
    title = str(getattr(event, "title", "") or "")
    event_id = str(getattr(event, "id", "") or "")
    file_component = _safe_file_component(title) if title else "event"
    suffix = event_id[:8] if event_id else datetime.now().strftime("%Y%m%d%H%M%S")
    default_name = f"{file_component}_{suffix}.json"

    file_filter = i18n.t("calendar.delete.export_file_filter")
    file_path, _ = QFileDialog.getSaveFileName(
        parent,
        i18n.t("calendar.delete.export_dialog_title"),
        default_name,
        file_filter,
    )
    if not file_path:
        return None

    target_path = Path(file_path)
    if target_path.suffix.lower() != ".json":
        target_path = target_path.with_suffix(".json")

    payload = _build_export_payload(event, calendar_manager)
    target_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(target_path)


def _get_cleanup_summary(calendar_manager: Any, event_id: str) -> dict:
    workspace_manager = getattr(calendar_manager, "workspace_manager", None)
    if workspace_manager is None or not event_id:
        return {
            "event_id": event_id,
            "has_workspace_assets": False,
            "linked_item_count": 0,
            "linked_asset_count": 0,
            "asset_roles": [],
        }

    try:
        return workspace_manager.get_event_cleanup_summary(event_id)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Failed to summarize workspace cleanup for event %s: %s", event_id, exc)
        return {
            "event_id": event_id,
            "has_workspace_assets": False,
            "linked_item_count": 0,
            "linked_asset_count": 0,
            "asset_roles": [],
        }


def _build_delete_copy(i18n: Any, event: Any, cleanup_summary: dict) -> dict[str, str]:
    asset_roles = cleanup_summary.get("asset_roles") or []
    asset_roles_label = ", ".join(asset_roles) if asset_roles else i18n.t("common.none")
    has_workspace_assets = bool(cleanup_summary.get("has_workspace_assets"))
    hint_key = (
        "calendar.delete.confirm_hint_with_workspace"
        if has_workspace_assets
        else "calendar.delete.confirm_hint_without_workspace"
    )
    return {
        "message": i18n.t("calendar.delete.confirm_message", title=getattr(event, "title", "")),
        "hint": i18n.t(
            hint_key,
            item_count=cleanup_summary.get("linked_item_count", 0),
            asset_count=cleanup_summary.get("linked_asset_count", 0),
            asset_roles=asset_roles_label,
        ),
    }


def _choose_delete_action(parent: Any, i18n: Any, event: Any, cleanup_summary: dict) -> str:
    dialog = QMessageBox(parent)
    dialog.setIcon(QMessageBox.Icon.Warning)
    dialog.setOption(QMessageBox.Option.DontUseNativeDialog, True)
    dialog.setMinimumWidth(CALENDAR_DELETE_DIALOG_MIN_WIDTH)
    dialog.setWindowTitle(i18n.t("calendar.delete.confirm_title"))
    copy = _build_delete_copy(i18n, event, cleanup_summary)
    dialog.setText(copy["message"])
    dialog.setInformativeText(copy["hint"])

    export_btn = dialog.addButton(
        i18n.t("calendar.delete.export_then_delete"),
        QMessageBox.ButtonRole.ActionRole,
    )
    delete_event_only_btn = dialog.addButton(
        i18n.t("calendar.delete.delete_event_only"),
        QMessageBox.ButtonRole.ActionRole,
    )
    delete_with_artifacts_btn = dialog.addButton(
        i18n.t("calendar.delete.delete_with_artifacts"),
        QMessageBox.ButtonRole.DestructiveRole,
    )
    cancel_btn = dialog.addButton(i18n.t("common.cancel"), QMessageBox.ButtonRole.RejectRole)
    button_role_map = {
        export_btn: ROLE_DIALOG_SECONDARY_ACTION,
        delete_event_only_btn: ROLE_DIALOG_SECONDARY_ACTION,
        delete_with_artifacts_btn: ROLE_DANGER,
        cancel_btn: ROLE_DIALOG_SECONDARY_ACTION,
    }
    for button, role in button_role_map.items():
        button.setProperty("role", role)
        text_width = button.fontMetrics().horizontalAdvance(button.text())
        button.setMinimumWidth(max(CALENDAR_DELETE_ACTION_BUTTON_MIN_WIDTH, text_width + 36))
    dialog.setDefaultButton(cancel_btn)
    dialog.setEscapeButton(cancel_btn)

    dialog.exec()
    clicked = dialog.clickedButton()
    if clicked is export_btn:
        return _ACTION_EXPORT_AND_DELETE
    if clicked is delete_event_only_btn:
        return _ACTION_DELETE_EVENT_ONLY
    if clicked is delete_with_artifacts_btn:
        return _ACTION_DELETE_WITH_ARTIFACTS
    return _ACTION_CANCEL


def _confirm_delete_second_step(parent: Any, i18n: Any, event: Any, action: str) -> bool:
    message_key = (
        "calendar.delete.second_confirm_keep_workspace"
        if action == _ACTION_DELETE_EVENT_ONLY
        else "calendar.delete.second_confirm_delete_workspace"
    )
    reply = QMessageBox.question(
        parent,
        i18n.t("calendar.delete.second_confirm_title"),
        i18n.t(message_key, title=getattr(event, "title", "")),
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.No,
    )
    return reply == QMessageBox.StandardButton.Yes


def confirm_and_delete_event(
    *,
    parent: Any,
    i18n: Any,
    calendar_manager: Any,
    event: Any,
    on_deleted: Optional[Callable[[], None]] = None,
) -> bool:
    """Delete event with export option + double confirmation."""
    if not event:
        _show_warning(parent, i18n.t("common.warning"), i18n.t("calendar.error.event_not_found"))
        return False

    if bool(getattr(event, "is_readonly", False)):
        _show_warning(
            parent,
            i18n.t("common.warning"),
            i18n.t("calendar.error.delete_readonly_external"),
        )
        return False

    event_id = str(getattr(event, "id", "") or "")
    if not event_id:
        _show_warning(parent, i18n.t("common.warning"), i18n.t("calendar.error.event_not_found"))
        return False

    cleanup_summary = _get_cleanup_summary(calendar_manager, event_id)
    action = _choose_delete_action(parent, i18n, event, cleanup_summary)
    if action == _ACTION_CANCEL:
        return False

    if action == _ACTION_EXPORT_AND_DELETE:
        try:
            export_path = _export_event_snapshot(parent, i18n, calendar_manager, event)
        except Exception as exc:
            logger.error("Failed to export event %s: %s", event_id, exc)
            _show_error(
                parent,
                i18n.t("common.error"),
                i18n.t("calendar.error.export_failed", error=str(exc)),
            )
            return False

        if not export_path:
            return False

        _show_info(
            parent,
            i18n.t("common.success"),
            i18n.t("calendar.success.event_exported", path=export_path),
        )

    if not _confirm_delete_second_step(parent, i18n, event, action):
        return False

    try:
        if action == _ACTION_DELETE_EVENT_ONLY:
            calendar_manager.delete_event(event_id, delete_artifacts=False)
        else:
            calendar_manager.delete_event(event_id, delete_artifacts=True)
    except ValueError as exc:
        error_text = str(exc)
        if "Cannot delete readonly event" in error_text:
            _show_warning(
                parent,
                i18n.t("common.warning"),
                i18n.t("calendar.error.delete_readonly_external"),
            )
            return False

        _show_error(
            parent,
            i18n.t("common.error"),
            i18n.t("calendar.error.delete_failed", error=error_text),
        )
        return False
    except SyncError as exc:
        _show_error(
            parent,
            i18n.t("common.error"),
            i18n.t("calendar.error.delete_failed", error=str(exc)),
        )
        return False
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("Unexpected error deleting event %s: %s", event_id, exc, exc_info=True)
        _show_error(
            parent,
            i18n.t("common.error"),
            i18n.t("calendar.error.delete_failed", error=str(exc)),
        )
        return False

    if on_deleted is not None:
        try:
            on_deleted()
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("Post-delete callback failed for %s: %s", event_id, exc, exc_info=True)

    _show_info(parent, i18n.t("common.success"), i18n.t("calendar.success.event_deleted"))
    return True
