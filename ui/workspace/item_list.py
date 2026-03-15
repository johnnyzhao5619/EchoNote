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
        self._init_ui()

    def _init_ui(self) -> None:
        self.setProperty("role", ROLE_WORKSPACE_ITEM_LIST)
        layout = QVBoxLayout(self)
        self.list_widget = QListWidget()
        self.list_widget.setProperty("role", ROLE_WORKSPACE_ITEM_LIST)
        self.list_widget.currentRowChanged.connect(self._on_row_changed)
        layout.addWidget(self.list_widget)

    def set_items(self, items) -> None:
        self.items = list(items)
        self.list_widget.blockSignals(True)
        self.list_widget.clear()
        for item in self.items:
            list_item = QListWidgetItem(item.title or item.id)
            list_item.setData(0x0100, item.id)
            self.list_widget.addItem(list_item)
        self.list_widget.blockSignals(False)
        if self.items:
            self.list_widget.setCurrentRow(0)

    def select_item(self, item_id: str) -> None:
        for row in range(self.list_widget.count()):
            item = self.list_widget.item(row)
            if item.data(0x0100) == item_id:
                self.list_widget.setCurrentRow(row)
                return

    def _on_row_changed(self, row: int) -> None:
        if row < 0 or row >= len(self.items):
            return
        self.item_selected.emit(self.items[row].id)
