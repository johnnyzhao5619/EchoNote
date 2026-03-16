# SPDX-License-Identifier: Apache-2.0
"""Workspace inspector shell panel."""

from __future__ import annotations

from core.qt_imports import QLabel, QPushButton, QVBoxLayout, QWidget
from ui.base_widgets import BaseWidget
from ui.constants import (
    ROLE_WORKSPACE_AI_ACTION,
    ROLE_WORKSPACE_INSPECTOR_PANEL,
    ROLE_WORKSPACE_INSPECTOR_SECTION,
    ROLE_WORKSPACE_INSPECTOR_SECTION_TITLE,
    ROLE_WORKSPACE_META_VALUE,
)
from ui.workspace.item_list import format_workspace_source_label, format_workspace_updated_at
from ui.workspace.recording_panel import WorkspaceRecordingPanel


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
        self.ai_actions_section = QWidget(self)
        self.ai_actions_section.setProperty("role", ROLE_WORKSPACE_INSPECTOR_SECTION)
        ai_actions_layout = QVBoxLayout(self.ai_actions_section)
        ai_actions_layout.setContentsMargins(10, 10, 10, 10)
        ai_actions_layout.setSpacing(8)
        self.ai_section_title = QLabel(self.ai_actions_section)
        self.ai_section_title.setProperty("role", ROLE_WORKSPACE_INSPECTOR_SECTION_TITLE)
        ai_actions_layout.addWidget(self.ai_section_title)
        self.summary_button = QPushButton(self.ai_actions_section)
        self.summary_button.setProperty("role", ROLE_WORKSPACE_AI_ACTION)
        self.summary_button.clicked.connect(self._generate_summary)
        ai_actions_layout.addWidget(self.summary_button)

        self.meeting_brief_button = QPushButton(self.ai_actions_section)
        self.meeting_brief_button.setProperty("role", ROLE_WORKSPACE_AI_ACTION)
        self.meeting_brief_button.clicked.connect(self._generate_meeting_brief)
        ai_actions_layout.addWidget(self.meeting_brief_button)
        layout.addWidget(self.ai_actions_section)

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
        metadata_layout.setSpacing(6)
        self.metadata_section_title = QLabel(self.metadata_section)
        self.metadata_section_title.setProperty("role", ROLE_WORKSPACE_INSPECTOR_SECTION_TITLE)
        metadata_layout.addWidget(self.metadata_section_title)
        self.source_value_label = QLabel(self.metadata_section)
        self.source_value_label.setProperty("role", ROLE_WORKSPACE_META_VALUE)
        self.source_value_label.setWordWrap(True)
        metadata_layout.addWidget(self.source_value_label)
        self.event_value_label = QLabel(self.metadata_section)
        self.event_value_label.setProperty("role", ROLE_WORKSPACE_META_VALUE)
        self.event_value_label.setWordWrap(True)
        metadata_layout.addWidget(self.event_value_label)
        self.task_value_label = QLabel(self.metadata_section)
        self.task_value_label.setProperty("role", ROLE_WORKSPACE_META_VALUE)
        self.task_value_label.setWordWrap(True)
        metadata_layout.addWidget(self.task_value_label)
        self.original_file_value_label = QLabel(self.metadata_section)
        self.original_file_value_label.setProperty("role", ROLE_WORKSPACE_META_VALUE)
        self.original_file_value_label.setWordWrap(True)
        metadata_layout.addWidget(self.original_file_value_label)
        self.updated_value_label = QLabel(self.metadata_section)
        self.updated_value_label.setProperty("role", ROLE_WORKSPACE_META_VALUE)
        self.updated_value_label.setWordWrap(True)
        metadata_layout.addWidget(self.updated_value_label)
        layout.addWidget(self.metadata_section)
        layout.addStretch()
        self.update_translations()

    def set_item(self, item) -> None:
        self._current_item = item
        self.recording_panel.set_item(item)
        enabled = item is not None and self._editor_panel is not None
        self.summary_button.setEnabled(enabled)
        self.meeting_brief_button.setEnabled(enabled)
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
        self.source_value_label.setText(
            self.i18n.t("workspace.inspector_source", value=source_value or "-")
        )
        self.event_value_label.setText(
            self.i18n.t("workspace.inspector_event", value=event_value or "-")
        )
        self.task_value_label.setText(
            self.i18n.t("workspace.inspector_task", value=task_value or "-")
        )
        self.original_file_value_label.setText(
            self.i18n.t("workspace.inspector_original_file", value=original_file_value or "-")
        )
        self.updated_value_label.setText(
            self.i18n.t(
                "workspace.inspector_updated",
                value=format_workspace_updated_at(updated_value) or "-",
            )
        )

    def set_editor_panel(self, editor_panel) -> None:
        self._editor_panel = editor_panel
        has_item = (
            editor_panel is not None
            and callable(getattr(editor_panel, "current_item_id", None))
            and bool(editor_panel.current_item_id())
        )
        self.summary_button.setEnabled(has_item)
        self.meeting_brief_button.setEnabled(has_item)

    def update_translations(self) -> None:
        self.ai_section_title.setText(self.i18n.t("workspace.inspector_section_ai"))
        self.media_section_title.setText(self.i18n.t("workspace.inspector_section_media"))
        self.metadata_section_title.setText(self.i18n.t("workspace.inspector_section_metadata"))
        self.summary_button.setText(self.i18n.t("workspace.generate_summary"))
        self.meeting_brief_button.setText(self.i18n.t("workspace.generate_meeting_brief"))
        self.recording_panel.update_translations()
        self.set_item(self._current_item)

    def _generate_summary(self) -> None:
        if self._editor_panel is not None:
            self._editor_panel.generate_summary()

    def _generate_meeting_brief(self) -> None:
        if self._editor_panel is not None:
            self._editor_panel.generate_meeting_brief()
