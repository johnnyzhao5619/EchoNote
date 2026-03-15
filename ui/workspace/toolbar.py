# SPDX-License-Identifier: Apache-2.0
"""Workspace toolbar with unified create-entry actions."""

from __future__ import annotations

from core.qt_imports import QHBoxLayout, Signal
from ui.base_widgets import BaseWidget, create_button, create_primary_button


class WorkspaceToolbar(BaseWidget):
    """Expose primary workspace entry points from a single toolbar."""

    import_document_requested = Signal()
    new_note_requested = Signal()

    def __init__(self, workspace_manager, i18n, parent=None):
        super().__init__(i18n, parent)
        self.workspace_manager = workspace_manager
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.import_document_button = create_button(self.i18n.t("workspace.import_document"))
        self.import_document_button.clicked.connect(self.import_document_requested.emit)
        layout.addWidget(self.import_document_button)

        self.new_note_button = create_primary_button(self.i18n.t("workspace.new_note"))
        self.new_note_button.clicked.connect(self.new_note_requested.emit)
        layout.addWidget(self.new_note_button)

        layout.addStretch()

    def update_translations(self) -> None:
        self.import_document_button.setText(self.i18n.t("workspace.import_document"))
        self.new_note_button.setText(self.i18n.t("workspace.new_note"))
