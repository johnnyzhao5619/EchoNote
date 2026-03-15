# SPDX-License-Identifier: Apache-2.0
"""Workspace item list widget."""

from __future__ import annotations

from datetime import datetime

from core.qt_imports import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
    Signal,
)
from ui.base_widgets import BaseWidget
from ui.constants import (
    ROLE_WORKSPACE_ITEM_BADGES,
    ROLE_WORKSPACE_ITEM_LIST,
    ROLE_WORKSPACE_ITEM_META,
    ROLE_WORKSPACE_ITEM_TITLE,
    ROLE_WORKSPACE_PLACEHOLDER,
)
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


class WorkspaceItemRowWidget(QWidget):
    """Structured row widget used inside the workspace item list."""

    def __init__(self, title: str, meta_text: str, badge_texts: list[str], parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        self.title_label = QLabel(title, self)
        self.title_label.setProperty("role", ROLE_WORKSPACE_ITEM_TITLE)
        layout.addWidget(self.title_label)

        self.meta_label = QLabel(meta_text, self)
        self.meta_label.setProperty("role", ROLE_WORKSPACE_ITEM_META)
        self.meta_label.setVisible(bool(meta_text))
        layout.addWidget(self.meta_label)

        self.badges_widget = QWidget(self)
        self.badges_widget.setProperty("role", ROLE_WORKSPACE_ITEM_BADGES)
        self.status_badges_layout = QHBoxLayout(self.badges_widget)
        self.status_badges_layout.setContentsMargins(0, 0, 0, 0)
        self.status_badges_layout.setSpacing(4)
        for badge_text in badge_texts:
            self.status_badges_layout.addWidget(QLabel(badge_text, self.badges_widget))
        self.status_badges_layout.addStretch()
        self.badges_widget.setVisible(bool(badge_texts))
        layout.addWidget(self.badges_widget)


class WorkspaceItemList(BaseWidget):
    """Display workspace items and emit the selected item identifier."""

    item_selected = Signal(str)

    def __init__(self, i18n: I18nQtManager, parent=None):
        super().__init__(i18n, parent)
        self.items = []
        self._view_mode = "structure"
        self._init_ui()

    def _init_ui(self) -> None:
        self.setProperty("role", ROLE_WORKSPACE_ITEM_LIST)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.empty_label = QLabel(self.i18n.t("workspace.no_items"))
        self.empty_label.setProperty("role", ROLE_WORKSPACE_PLACEHOLDER)
        self.empty_label.hide()
        layout.addWidget(self.empty_label)

        self.list_widget = QListWidget()
        self.list_widget.setProperty("role", ROLE_WORKSPACE_ITEM_LIST)
        self.list_widget.setSpacing(4)
        self.list_widget.setWordWrap(True)
        self.list_widget.currentRowChanged.connect(self._on_row_changed)
        layout.addWidget(self.list_widget)

    def set_view_mode(self, view_mode: str) -> None:
        """Track the active library view mode for label formatting."""
        self._view_mode = view_mode or "structure"

    def set_items(self, items, metadata_by_item=None) -> None:
        self.items = list(items)
        metadata_by_item = metadata_by_item or {}
        self.list_widget.blockSignals(True)
        self.list_widget.clear()
        for item in self.items:
            metadata = metadata_by_item.get(item.id, {})
            row_widget = WorkspaceItemRowWidget(
                item.title or item.id,
                self._format_meta_text(metadata),
                self._badge_texts(metadata),
                self.list_widget,
            )
            list_item = QListWidgetItem()
            list_item.setData(0x0100, item.id)
            list_item.setSizeHint(row_widget.sizeHint())
            self.list_widget.addItem(list_item)
            self.list_widget.setItemWidget(list_item, row_widget)
        if self.items:
            self.list_widget.setCurrentRow(0)
        self.list_widget.blockSignals(False)
        self.empty_label.setVisible(not bool(self.items))
        self.list_widget.setVisible(bool(self.items))

    def select_item(self, item_id: str) -> None:
        for row in range(self.list_widget.count()):
            item = self.list_widget.item(row)
            if item.data(0x0100) == item_id:
                self.list_widget.setCurrentRow(row)
                return

    def current_item_id(self) -> str:
        current_item = self.list_widget.currentItem()
        if current_item is None:
            return ""
        return current_item.data(0x0100) or ""

    def _format_meta_text(self, metadata: dict) -> str:
        details = []
        if self._view_mode == "event" and metadata.get("event_id"):
            details.append(
                self.i18n.t("workspace.item_meta_event", value=str(metadata["event_id"]))
            )
        elif self._view_mode == "structure" and metadata.get("folder_name"):
            details.append(str(metadata["folder_name"]))

        source = metadata.get("source")
        if source:
            details.append(self._format_source_label(str(source)))
        updated_at = metadata.get("updated_at")
        if updated_at:
            details.append(
                self.i18n.t(
                    "workspace.item_meta_updated",
                    value=self._format_updated_at(str(updated_at)),
                )
            )
        return " / ".join(details)

    def _badge_texts(self, metadata: dict) -> list[str]:
        badges: list[str] = []
        if metadata.get("is_orphaned"):
            badges.append(self.i18n.t("workspace.item_badge_orphaned"))
        if metadata.get("has_audio"):
            badges.append(self.i18n.t("workspace.item_badge_audio"))
        if metadata.get("has_text"):
            badges.append(self.i18n.t("workspace.item_badge_text"))
        return badges

    def _format_source_label(self, source: str) -> str:
        return format_workspace_source_label(self.i18n, source)

    def _format_updated_at(self, updated_at: str) -> str:
        return format_workspace_updated_at(updated_at)

    def _on_row_changed(self, row: int) -> None:
        if row < 0 or row >= len(self.items):
            return
        self.item_selected.emit(self.items[row].id)
