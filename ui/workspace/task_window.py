# SPDX-License-Identifier: Apache-2.0
"""Shell-level utility window for workspace batch tasks."""

from __future__ import annotations

from core.qt_imports import QCloseEvent, QVBoxLayout, QWidget, Qt
from ui.base_widgets import BaseWidget
from ui.workspace.task_panel import WorkspaceTaskPanel


class WorkspaceTaskWindow(BaseWidget):
    """Single-instance window that hosts the shared workspace task queue panel."""

    def __init__(
        self,
        transcription_manager,
        i18n,
        *,
        settings_manager=None,
        settings=None,
        workspace_manager=None,
        parent=None,
    ):
        super().__init__(i18n, parent)
        self.settings = settings
        self.setWindowFlag(Qt.WindowType.Window, True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        self.setMinimumSize(720, 520)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.panel = WorkspaceTaskPanel(
            transcription_manager,
            self.i18n,
            settings_manager=settings_manager,
            workspace_manager=workspace_manager,
            parent=self,
        )
        layout.addWidget(self.panel)
        self.update_translations()
        self.restore_window_state()

    def update_translations(self) -> None:
        self.setWindowTitle(self.i18n.t("workspace.task_window_title"))
        self.panel.update_translations()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        self.save_window_state()
        self.hide()
        event.ignore()

    def save_window_state(self) -> None:
        """Persist utility-window geometry via the shared shell settings."""
        if self.settings is None:
            return
        self.settings.setValue("workspace/task_window_geometry", self.saveGeometry())

    def restore_window_state(self) -> None:
        """Restore persisted geometry when available."""
        if self.settings is None:
            return
        geometry = self.settings.value("workspace/task_window_geometry")
        if geometry:
            self.restoreGeometry(geometry)
