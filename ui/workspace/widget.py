# SPDX-License-Identifier: Apache-2.0
"""Workspace main widget."""

from __future__ import annotations

from core.qt_imports import QHBoxLayout
from ui.base_widgets import BaseWidget
from ui.constants import ROLE_WORKSPACE_SURFACE
from ui.workspace.editor_panel import WorkspaceEditorPanel
from ui.workspace.item_list import WorkspaceItemList
from ui.workspace.recording_panel import WorkspaceRecordingPanel


class WorkspaceWidget(BaseWidget):
    """Unified workspace page with item list, editor, and recording playback."""

    def __init__(self, workspace_manager, i18n, parent=None):
        super().__init__(i18n, parent)
        self.workspace_manager = workspace_manager
        self._items_by_id = {}
        self._init_ui()
        self.refresh_items()

    def _init_ui(self) -> None:
        self.setProperty("role", ROLE_WORKSPACE_SURFACE)
        layout = QHBoxLayout(self)
        self.item_list = WorkspaceItemList(self.i18n, self)
        self.editor_panel = WorkspaceEditorPanel(self.workspace_manager, self.i18n, parent=self)
        self.recording_panel = WorkspaceRecordingPanel(self.workspace_manager, self.i18n, self)

        self.item_list.item_selected.connect(self._on_item_selected)

        layout.addWidget(self.item_list, 1)
        layout.addWidget(self.editor_panel, 2)
        layout.addWidget(self.recording_panel, 2)

    def refresh_items(self) -> None:
        items = self.workspace_manager.list_items()
        self._items_by_id = {item.id: item for item in items}
        self.item_list.set_items(items)
        if items:
            self._on_item_selected(items[0].id)
        else:
            self._on_item_selected("")

    def _on_item_selected(self, item_id: str) -> None:
        item = self._items_by_id.get(item_id)
        self.editor_panel.set_item(item)
        self.recording_panel.set_item(item)
