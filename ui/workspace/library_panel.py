# SPDX-License-Identifier: Apache-2.0
"""Workspace library shell panel."""

from __future__ import annotations

from core.qt_imports import QVBoxLayout, Signal
from ui.base_widgets import BaseWidget
from ui.constants import ROLE_WORKSPACE_LIBRARY_PANEL
from ui.workspace.item_list import WorkspaceItemList


class WorkspaceLibraryPanel(BaseWidget):
    """Left-side workspace library surface."""

    item_selected = Signal(str)
    collection_changed = Signal(str)

    def __init__(self, i18n, parent=None):
        super().__init__(i18n, parent)
        self.item_list = WorkspaceItemList(i18n, self)
        self._init_ui()

    def _init_ui(self) -> None:
        self.setProperty("role", ROLE_WORKSPACE_LIBRARY_PANEL)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.item_list)
        self.item_list.item_selected.connect(self.item_selected.emit)
        self.item_list.collection_changed.connect(self.collection_changed.emit)

    def set_items(self, items, *, metadata_by_item=None) -> None:
        self.item_list.set_items(items, metadata_by_item=metadata_by_item)

    def select_item(self, item_id: str) -> None:
        self.item_list.select_item(item_id)

    def current_item_id(self) -> str:
        return self.item_list.current_item_id()

    def current_collection(self) -> str:
        return self.item_list.current_collection()

    def set_collection(self, collection: str) -> None:
        self.item_list.set_collection(collection)
