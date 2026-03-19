# SPDX-License-Identifier: Apache-2.0
"""Workspace inspector shell panel."""

from __future__ import annotations

from core.qt_imports import QGridLayout, QHBoxLayout, QLabel, QPushButton, QSize, QSplitter, QVBoxLayout, QWidget
from ui.base_widgets import BaseWidget
from ui.common.svg_icons import build_svg_icon
from ui.constants import (
    ROLE_WORKSPACE_AI_LAUNCHER,
    ROLE_WORKSPACE_INSPECTOR_PANEL,
    ROLE_WORKSPACE_INSPECTOR_SECTION,
    ROLE_WORKSPACE_INSPECTOR_SECTION_TITLE,
    ROLE_WORKSPACE_META_LABEL,
    ROLE_WORKSPACE_META_VALUE,
    ROLE_WORKSPACE_TAB_ACTION,
)
from ui.workspace.editor_panel import WorkspaceAIPopover
from ui.workspace.item_list import format_workspace_source_label, format_workspace_updated_at
from ui.workspace.recording_panel import WorkspaceRecordingPanel


def set_trailing_splitter_panel_visible(
    splitter: QSplitter,
    panel: QWidget,
    *,
    visible: bool,
    expanded_sizes: list[int] | tuple[int, ...] | None = None,
    fallback_sizes: list[int] | tuple[int, ...] | None = None,
) -> list[int]:
    """Show or hide the trailing splitter panel while preserving usable sizes."""
    current_sizes = list(splitter.sizes())
    if visible:
        panel.show()
        target_sizes = list(expanded_sizes or fallback_sizes or current_sizes)
        if len(target_sizes) >= 2 and target_sizes[-1] <= 0:
            fallback = list(fallback_sizes or current_sizes)
            if len(fallback) >= 2:
                target_sizes = fallback
        splitter.setSizes(target_sizes)
        return list(target_sizes)

    panel.hide()
    collapsed_sizes = list(current_sizes)
    if len(collapsed_sizes) >= 2:
        collapsed_sizes[-2] = max(0, collapsed_sizes[-2] + collapsed_sizes[-1])
        collapsed_sizes[-1] = 0
        splitter.setSizes(collapsed_sizes)
    return current_sizes


class WorkspaceInspectorPanel(BaseWidget):
    """Right-side workspace inspector that hosts contextual media preview."""

    def __init__(self, workspace_manager, i18n, parent=None):
        super().__init__(i18n, parent)
        self.workspace_manager = workspace_manager
        self.recording_panel = WorkspaceRecordingPanel(workspace_manager, i18n, self)
        self._editor_panel = None
        self._current_item = None
        self._init_ui()

    def _init_ui(self) -> None:
        self.setProperty("role", ROLE_WORKSPACE_INSPECTOR_PANEL)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)
        self.controls_section = QWidget(self)
        self.controls_section.setProperty("role", ROLE_WORKSPACE_INSPECTOR_SECTION)
        controls_layout = QVBoxLayout(self.controls_section)
        controls_layout.setContentsMargins(10, 10, 10, 10)
        controls_layout.setSpacing(10)
        self.shell_actions_row = QWidget(self.controls_section)
        shell_actions_layout = QHBoxLayout(self.shell_actions_row)
        shell_actions_layout.setContentsMargins(0, 0, 0, 0)
        shell_actions_layout.setSpacing(8)
        shell_actions_layout.addStretch()
        controls_layout.addWidget(self.shell_actions_row)
        self.shell_actions_layout = shell_actions_layout
        self.ai_launch_button = QPushButton(self.controls_section)
        self.ai_launch_button.setProperty("role", ROLE_WORKSPACE_AI_LAUNCHER)
        self.ai_launch_button.setIconSize(QSize(16, 16))
        self.ai_launch_button.clicked.connect(self._toggle_ai_popover)
        controls_layout.addWidget(self.ai_launch_button)
        layout.addWidget(self.controls_section)

        self.media_section = QWidget(self)
        self.media_section.setProperty("role", ROLE_WORKSPACE_INSPECTOR_SECTION)
        media_layout = QVBoxLayout(self.media_section)
        media_layout.setContentsMargins(10, 10, 10, 10)
        media_layout.setSpacing(8)
        self.media_section_title = QLabel(self.media_section)
        self.media_section_title.setProperty("role", ROLE_WORKSPACE_INSPECTOR_SECTION_TITLE)
        media_layout.addWidget(self.media_section_title)
        media_layout.addWidget(self.recording_panel)
        layout.addWidget(self.media_section)

        self.metadata_section = QWidget(self)
        self.metadata_section.setProperty("role", ROLE_WORKSPACE_INSPECTOR_SECTION)
        metadata_layout = QVBoxLayout(self.metadata_section)
        metadata_layout.setContentsMargins(10, 10, 10, 10)
        metadata_layout.setSpacing(10)
        self.metadata_section_title = QLabel(self.metadata_section)
        self.metadata_section_title.setProperty("role", ROLE_WORKSPACE_INSPECTOR_SECTION_TITLE)
        metadata_layout.addWidget(self.metadata_section_title)
        self.metadata_grid = QGridLayout()
        self.metadata_grid.setContentsMargins(0, 0, 0, 0)
        self.metadata_grid.setHorizontalSpacing(10)
        self.metadata_grid.setVerticalSpacing(8)
        metadata_layout.addLayout(self.metadata_grid)
        (
            self.source_title_label,
            self.source_value_label,
        ) = self._create_metadata_row(0)
        (
            self.event_title_label,
            self.event_value_label,
        ) = self._create_metadata_row(1)
        (
            self.task_title_label,
            self.task_value_label,
        ) = self._create_metadata_row(2)
        (
            self.original_file_title_label,
            self.original_file_value_label,
        ) = self._create_metadata_row(3)
        (
            self.updated_title_label,
            self.updated_value_label,
        ) = self._create_metadata_row(4)
        layout.addWidget(self.metadata_section)
        layout.addStretch()
        self.ai_popover = WorkspaceAIPopover(self.i18n, self)
        self.ai_popover.summary_requested.connect(self._generate_summary)
        self.ai_popover.meeting_brief_requested.connect(self._generate_meeting_brief)
        self.update_translations()

    def _create_metadata_row(self, row: int) -> tuple[QLabel, QLabel]:
        title_label = QLabel(self.metadata_section)
        title_label.setProperty("role", ROLE_WORKSPACE_META_LABEL)
        value_label = QLabel(self.metadata_section)
        value_label.setProperty("role", ROLE_WORKSPACE_META_VALUE)
        value_label.setWordWrap(True)
        self.metadata_grid.addWidget(title_label, row, 0)
        self.metadata_grid.addWidget(value_label, row, 1)
        self.metadata_grid.setColumnStretch(1, 1)
        return title_label, value_label

    def set_item(self, item) -> None:
        self._current_item = item
        self.recording_panel.set_item(item)
        context_metadata = {}
        if item is not None:
            context_metadata = self.workspace_manager.get_item_context_metadata(item.id)
        source_value = "-"
        updated_value = ""
        event_value = "-"
        task_value = "-"
        original_file_value = "-"
        if item is not None:
            source_value = format_workspace_source_label(
                self.i18n,
                getattr(item, "source_kind", "") or getattr(item, "item_type", ""),
            )
            updated_value = getattr(item, "updated_at", "") or ""
            event_value = (
                str(context_metadata.get("event_title") or context_metadata.get("event_id") or "-")
            )
            task_value = str(context_metadata.get("task_id") or "-")
            original_file_value = str(context_metadata.get("original_file_name") or "-")
        self.source_value_label.setText(source_value or "-")
        self.event_value_label.setText(event_value or "-")
        self.task_value_label.setText(task_value or "-")
        self.original_file_value_label.setText(original_file_value or "-")
        self.updated_value_label.setText(format_workspace_updated_at(updated_value) or "-")

    def set_editor_panel(self, editor_panel) -> None:
        self._editor_panel = editor_panel
        if editor_panel is None:
            self.ai_popover.hide()
        self.ai_launch_button.setEnabled(
            editor_panel is not None
            and callable(getattr(editor_panel, "current_item_id", None))
            and bool(editor_panel.current_item_id())
        )

    def update_translations(self) -> None:
        self.ai_launch_button.setText(self.i18n.t("workspace.inspector_section_ai"))
        self.ai_launch_button.setToolTip(self.i18n.t("workspace.ai_panel_subtitle"))
        self.ai_launch_button.setAccessibleName(self.i18n.t("workspace.inspector_section_ai"))
        self.ai_launch_button.setIcon(self._build_shell_icon("spark"))
        self.media_section_title.setText(self.i18n.t("workspace.inspector_section_media"))
        self.metadata_section_title.setText(self.i18n.t("workspace.inspector_section_metadata"))
        self.source_title_label.setText(self.i18n.t("workspace.inspector_label_source"))
        self.event_title_label.setText(self.i18n.t("workspace.inspector_label_event"))
        self.task_title_label.setText(self.i18n.t("workspace.inspector_label_task"))
        self.original_file_title_label.setText(self.i18n.t("workspace.inspector_label_original_file"))
        self.updated_title_label.setText(self.i18n.t("workspace.inspector_label_updated"))
        self.recording_panel.update_translations()
        self.ai_popover.update_translations()
        self.set_item(self._current_item)

    def attach_shell_action_widgets(self, widgets: list[QWidget]) -> None:
        while self.shell_actions_layout.count() > 1:
            item = self.shell_actions_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
        for widget in widgets:
            widget.setProperty("role", ROLE_WORKSPACE_TAB_ACTION)
            widget.show()
            self.shell_actions_layout.insertWidget(self.shell_actions_layout.count() - 1, widget)

    def _toggle_ai_popover(self) -> None:
        if self._editor_panel is None:
            return
        if self.ai_popover.isVisible():
            self.ai_popover.hide()
            return
        self.ai_popover.popup_from(self.ai_launch_button)

    def _generate_summary(self) -> None:
        if self._editor_panel is not None:
            self._editor_panel.generate_summary()

    def _generate_meeting_brief(self) -> None:
        if self._editor_panel is not None:
            self._editor_panel.generate_meeting_brief()

    def _build_shell_icon(self, icon_name: str):
        color = self.palette().buttonText().color().name()
        return build_svg_icon(icon_name, color)
