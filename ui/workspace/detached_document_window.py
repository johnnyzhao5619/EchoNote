# SPDX-License-Identifier: Apache-2.0
"""Detached window for a single workspace document."""

from __future__ import annotations

from core.qt_imports import QVBoxLayout, QWidget
from ui.workspace.editor_panel import WorkspaceEditorPanel


class DetachedDocumentWindow(QWidget):
    """Show a single workspace document in an independent window."""

    def __init__(self, workspace_manager, i18n, item_id: str, parent=None):
        super().__init__(parent)
        self.workspace_manager = workspace_manager
        self.i18n = i18n
        self.item_id = item_id
        self.editor_panel = WorkspaceEditorPanel(workspace_manager, i18n, parent=self)
        self._init_ui()
        self.load_item(item_id)

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.editor_panel)
        self.resize(860, 720)

    def load_item(self, item_id: str) -> None:
        """Reload the target document and refresh the window title."""
        self.item_id = item_id
        item = self.workspace_manager.get_item(item_id)
        self.editor_panel.set_item(item)
        self.setWindowTitle(item.title if item is not None else self.i18n.t("workspace.library_title"))
