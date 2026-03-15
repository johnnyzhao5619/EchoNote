# SPDX-License-Identifier: Apache-2.0
"""Workspace inspector shell panel."""

from __future__ import annotations

from core.qt_imports import QVBoxLayout
from ui.base_widgets import BaseWidget
from ui.constants import ROLE_WORKSPACE_INSPECTOR_PANEL
from ui.workspace.recording_panel import WorkspaceRecordingPanel


class WorkspaceInspectorPanel(BaseWidget):
    """Right-side workspace inspector that hosts contextual media preview."""

    def __init__(self, workspace_manager, i18n, parent=None):
        super().__init__(i18n, parent)
        self.recording_panel = WorkspaceRecordingPanel(workspace_manager, i18n, self)
        self._init_ui()

    def _init_ui(self) -> None:
        self.setProperty("role", ROLE_WORKSPACE_INSPECTOR_PANEL)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.recording_panel)

    def set_item(self, item) -> None:
        self.recording_panel.set_item(item)
