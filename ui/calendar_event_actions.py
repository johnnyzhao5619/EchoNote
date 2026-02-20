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
from data.database.models import EventAttachment
from core.qt_imports import QFileDialog, QMessageBox

logger = logging.getLogger("echonote.ui.calendar_event_actions")

_ACTION_CANCEL = "cancel"
_ACTION_DELETE = "delete"
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

    db = getattr(calendar_manager, "db", None)
    if db and event_id:
        try:
            attachments = EventAttachment.get_by_event_id(db, event_id)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Failed to load attachments for event %s: %s", event_id, exc)
        else:
            for attachment in attachments:
                attachments_payload.append(
                    {
                        "id": getattr(attachment, "id", ""),
                        "attachment_type": getattr(attachment, "attachment_type", ""),
                        "file_path": getattr(attachment, "file_path", ""),
                        "file_size": getattr(attachment, "file_size", None),
                        "created_at": _as_iso(getattr(attachment, "created_at", "")),
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


def _choose_delete_action(parent: Any, i18n: Any, event: Any) -> str:
    dialog = QMessageBox(parent)
    dialog.setIcon(QMessageBox.Icon.Warning)
    dialog.setWindowTitle(i18n.t("calendar.delete.confirm_title"))
    dialog.setText(i18n.t("calendar.delete.confirm_message", title=getattr(event, "title", "")))
    dialog.setInformativeText(i18n.t("calendar.delete.confirm_hint"))

    export_btn = dialog.addButton(
        i18n.t("calendar.delete.export_then_delete"),
        QMessageBox.ButtonRole.ActionRole,
    )
    delete_btn = dialog.addButton(
        i18n.t("calendar.delete.delete_now"),
        QMessageBox.ButtonRole.DestructiveRole,
    )
    cancel_btn = dialog.addButton(i18n.t("common.cancel"), QMessageBox.ButtonRole.RejectRole)
    dialog.setDefaultButton(cancel_btn)

    dialog.exec()
    clicked = dialog.clickedButton()
    if clicked is export_btn:
        return _ACTION_EXPORT_AND_DELETE
    if clicked is delete_btn:
        return _ACTION_DELETE
    return _ACTION_CANCEL


def _confirm_delete_second_step(parent: Any, i18n: Any, event: Any) -> bool:
    reply = QMessageBox.question(
        parent,
        i18n.t("calendar.delete.second_confirm_title"),
        i18n.t("calendar.delete.second_confirm_message", title=getattr(event, "title", "")),
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

    action = _choose_delete_action(parent, i18n, event)
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

    if not _confirm_delete_second_step(parent, i18n, event):
        return False

    try:
        calendar_manager.delete_event(event_id)
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
