# SPDX-License-Identifier: Apache-2.0
"""Persistent recording dock shown at the application shell level."""

from __future__ import annotations

from core.qt_imports import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget
from ui.base_widgets import BaseWidget
from ui.constants import (
    APP_RECORDING_DOCK_MARGINS,
    APP_RECORDING_DOCK_MIN_HEIGHT,
    PAGE_DENSE_SPACING,
    ROLE_REALTIME_RECORDING_DOCK,
)


class RealtimeRecordingDock(BaseWidget):
    """Shell-level recording dock with reserved space for future task drawer content."""

    def __init__(self, realtime_recorder, i18n, parent=None):
        super().__init__(i18n, parent)
        self.realtime_recorder = realtime_recorder
        self._expanded = False
        self._task_drawer_widget: QWidget | None = None
        self._init_ui()
        self.update_translations()

    def _init_ui(self) -> None:
        self.setProperty("role", ROLE_REALTIME_RECORDING_DOCK)
        self.setMinimumHeight(APP_RECORDING_DOCK_MIN_HEIGHT)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(*APP_RECORDING_DOCK_MARGINS)
        layout.setSpacing(PAGE_DENSE_SPACING)

        self.task_drawer_host = QWidget(self)
        self.task_drawer_host.hide()
        self.task_drawer_layout = QVBoxLayout(self.task_drawer_host)
        self.task_drawer_layout.setContentsMargins(0, 0, 0, 0)
        self.task_drawer_layout.setSpacing(PAGE_DENSE_SPACING)
        layout.addWidget(self.task_drawer_host)

        self.compact_panel = QWidget(self)
        compact_layout = QHBoxLayout(self.compact_panel)
        compact_layout.setContentsMargins(0, 0, 0, 0)
        compact_layout.setSpacing(PAGE_DENSE_SPACING)

        self.title_label = QLabel(self.compact_panel)
        compact_layout.addWidget(self.title_label)

        self.status_label = QLabel(self.compact_panel)
        compact_layout.addWidget(self.status_label)

        compact_layout.addStretch()

        self.expand_button = QPushButton(self.compact_panel)
        self.expand_button.hide()
        compact_layout.addWidget(self.expand_button)

        layout.addWidget(self.compact_panel)

        self.full_panel = QWidget(self)
        self.full_panel.hide()
        layout.addWidget(self.full_panel)

    def update_translations(self) -> None:
        self.title_label.setText(self.i18n.t("workspace.recording_controls_title"))
        self.status_label.setText(self._status_text())
        self.expand_button.setText(self.i18n.t("common.more"))

    def set_task_drawer_widget(self, widget: QWidget | None) -> None:
        """Attach a widget above the dock for future task-drawer reuse."""
        if self._task_drawer_widget is widget:
            return

        if self._task_drawer_widget is not None:
            self.task_drawer_layout.removeWidget(self._task_drawer_widget)
            self._task_drawer_widget.setParent(None)

        self._task_drawer_widget = widget
        if widget is None:
            self.task_drawer_host.hide()
            return

        self.task_drawer_layout.addWidget(widget)
        self.task_drawer_host.show()

    def set_expanded(self, expanded: bool) -> None:
        """Toggle future full-panel visibility without duplicating dock state."""
        self._expanded = bool(expanded)
        self.full_panel.setVisible(self._expanded)

    def refresh_status(self) -> None:
        """Refresh the compact status text from the shared recorder state."""
        self.status_label.setText(self._status_text())

    def _status_text(self) -> str:
        is_recording = bool(getattr(self.realtime_recorder, "is_recording", False))
        key = "workspace.recording_active" if is_recording else "workspace.recording_idle"
        return self.i18n.t(key)
