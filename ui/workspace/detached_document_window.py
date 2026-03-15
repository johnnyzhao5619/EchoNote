# SPDX-License-Identifier: Apache-2.0
"""Detached window for a single workspace document."""

from __future__ import annotations

from core.qt_imports import QHBoxLayout, QLabel, QVBoxLayout, QWidget
from ui.workspace.editor_panel import WorkspaceEditorPanel
from ui.workspace.inspector_panel import WorkspaceInspectorPanel


class DetachedDocumentWindow(QWidget):
    """Show a single workspace document in an independent window."""

    def __init__(self, workspace_manager, i18n, item_id: str, parent=None):
        super().__init__(parent)
        self.workspace_manager = workspace_manager
        self.i18n = i18n
        self.item_id = item_id
        self.editor_panel = WorkspaceEditorPanel(workspace_manager, i18n, parent=self)
        self.inspector_panel = WorkspaceInspectorPanel(workspace_manager, i18n, self)
        self._init_ui()
        self.load_item(item_id)

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        content = QWidget(self)
        content_layout = QHBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)

        editor_stage = QWidget(content)
        editor_stage_layout = QVBoxLayout(editor_stage)
        editor_stage_layout.setContentsMargins(0, 0, 0, 0)
        self.document_title_label = QLabel(editor_stage)
        editor_stage_layout.addWidget(self.document_title_label)
        editor_stage_layout.addWidget(self.editor_panel)

        content_layout.addWidget(editor_stage, 1)
        content_layout.addWidget(self.inspector_panel)
        layout.addWidget(content)
        self.resize(860, 720)

    def update_translations(self) -> None:
        self.editor_panel.update_translations()
        self.inspector_panel.update_translations()
        item = self.workspace_manager.get_item(self.item_id)
        self.document_title_label.setText(
            item.title if item is not None else self.i18n.t("workspace.library_title")
        )
        self.setWindowTitle(
            item.title if item is not None else self.i18n.t("workspace.library_title")
        )

    def load_item(self, item_id: str) -> None:
        """Reload the target document and refresh the window title."""
        self.item_id = item_id
        item = self.workspace_manager.get_item(item_id)
        self.editor_panel.set_item(item)
        self.inspector_panel.set_item(item)
        self.inspector_panel.set_editor_panel(self.editor_panel)
        self.document_title_label.setText(
            item.title if item is not None else self.i18n.t("workspace.library_title")
        )
        self.setWindowTitle(item.title if item is not None else self.i18n.t("workspace.library_title"))
