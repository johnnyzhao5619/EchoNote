# SPDX-License-Identifier: Apache-2.0
"""Local workspace tool rail for view switching and shell utilities."""

from __future__ import annotations

from core.qt_imports import QButtonGroup, QVBoxLayout, QPushButton, QWidget, Signal
from ui.base_widgets import BaseWidget
from ui.constants import (
    PAGE_COMPACT_SPACING,
    PAGE_DENSE_SPACING,
    ROLE_WORKSPACE_MODE_BUTTON_GROUP,
    WORKSPACE_TOOL_RAIL_BUTTON_MIN_HEIGHT,
    WORKSPACE_TOOL_RAIL_WIDTH,
    ROLE_WORKSPACE_TOOL_RAIL,
)


class WorkspaceToolRail(BaseWidget):
    """Compact local tool rail for workspace-specific navigation and utilities."""

    view_mode_requested = Signal(str)
    toggle_inspector_requested = Signal()

    def __init__(self, i18n, parent=None):
        super().__init__(i18n, parent)
        self._init_ui()

    def _init_ui(self) -> None:
        self.setProperty("role", ROLE_WORKSPACE_TOOL_RAIL)
        self.setFixedWidth(WORKSPACE_TOOL_RAIL_WIDTH)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(PAGE_COMPACT_SPACING)

        self.mode_button_group = QButtonGroup(self)
        self.mode_button_group.setExclusive(True)
        self.mode_button_group_widget = QWidget(self)
        self.mode_button_group_widget.setProperty("role", ROLE_WORKSPACE_MODE_BUTTON_GROUP)
        mode_group_layout = QVBoxLayout(self.mode_button_group_widget)
        mode_group_layout.setContentsMargins(0, 0, 0, 0)
        mode_group_layout.setSpacing(PAGE_DENSE_SPACING)

        self.structure_view_button = QPushButton(self)
        self.structure_view_button.setCheckable(True)
        self.structure_view_button.setProperty("role", "toolbar-secondary-action")
        self.structure_view_button.setMinimumHeight(WORKSPACE_TOOL_RAIL_BUTTON_MIN_HEIGHT)
        self.structure_view_button.clicked.connect(
            lambda checked=False: self.view_mode_requested.emit("structure")
        )
        self.mode_button_group.addButton(self.structure_view_button)
        mode_group_layout.addWidget(self.structure_view_button)

        self.event_view_button = QPushButton(self)
        self.event_view_button.setCheckable(True)
        self.event_view_button.setProperty("role", "toolbar-secondary-action")
        self.event_view_button.setMinimumHeight(WORKSPACE_TOOL_RAIL_BUTTON_MIN_HEIGHT)
        self.event_view_button.clicked.connect(
            lambda checked=False: self.view_mode_requested.emit("event")
        )
        self.mode_button_group.addButton(self.event_view_button)
        mode_group_layout.addWidget(self.event_view_button)

        layout.addWidget(self.mode_button_group_widget)

        self.toggle_inspector_button = QPushButton(self)
        self.toggle_inspector_button.setProperty("role", "toolbar-secondary-action")
        self.toggle_inspector_button.setMinimumHeight(WORKSPACE_TOOL_RAIL_BUTTON_MIN_HEIGHT)
        self.toggle_inspector_button.clicked.connect(self.toggle_inspector_requested.emit)
        layout.addWidget(self.toggle_inspector_button)

        layout.addStretch()
        self.update_translations()
        self.set_active_view_mode("structure")

    def update_translations(self) -> None:
        self.structure_view_button.setText(self.i18n.t("workspace.structure_view"))
        self.event_view_button.setText(self.i18n.t("workspace.event_view"))
        self.toggle_inspector_button.setText(self.i18n.t("common.more"))

    def set_active_view_mode(self, view_mode: str) -> None:
        is_structure = view_mode == "structure"
        self.structure_view_button.setChecked(is_structure)
        self.event_view_button.setChecked(not is_structure)
