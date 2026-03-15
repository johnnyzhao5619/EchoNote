# SPDX-License-Identifier: Apache-2.0
"""Workspace item list widget."""

from __future__ import annotations

from core.qt_imports import QListWidget, QListWidgetItem, QVBoxLayout, Signal
from ui.base_widgets import BaseWidget
from ui.constants import ROLE_WORKSPACE_ITEM_LIST
from utils.i18n import I18nQtManager


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

        self.list_widget = QListWidget()
        self.list_widget.setProperty("role", ROLE_WORKSPACE_ITEM_LIST)
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
            list_item = QListWidgetItem(self._format_item_label(item, metadata))
            list_item.setData(0x0100, item.id)
            self.list_widget.addItem(list_item)
        if self.items:
            self.list_widget.setCurrentRow(0)
        self.list_widget.blockSignals(False)

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

    def _format_item_label(self, item, metadata: dict) -> str:
        details = []
        if self._view_mode == "event" and metadata.get("event_id"):
            details.append(f"event:{metadata['event_id']}")
        elif self._view_mode == "structure" and metadata.get("folder_name"):
            details.append(str(metadata["folder_name"]))

        source = metadata.get("source")
        if source:
            details.append(str(source))
        updated_at = metadata.get("updated_at")
        if updated_at:
            details.append(str(updated_at).replace("T", " ")[:16])
        if metadata.get("is_orphaned"):
            details.append("orphaned")
        if metadata.get("has_audio"):
            details.append("audio")
        if metadata.get("has_text"):
            details.append("text")
        if details:
            return f"{item.title or item.id}\n" + " | ".join(details)
        return item.title or item.id

    def _on_row_changed(self, row: int) -> None:
        if row < 0 or row >= len(self.items):
            return
        self.item_selected.emit(self.items[row].id)
