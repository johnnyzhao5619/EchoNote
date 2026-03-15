# SPDX-License-Identifier: Apache-2.0
"""Workspace main widget."""

from __future__ import annotations

from core.qt_imports import QSplitter, QVBoxLayout, QWidget, Qt
from ui.base_widgets import BaseWidget
from ui.constants import ROLE_WORKSPACE_SURFACE
from ui.workspace.editor_panel import WorkspaceEditorPanel
from ui.workspace.item_list import WorkspaceItemList
from ui.workspace.recording_control_panel import WorkspaceRecordingControlPanel
from ui.workspace.recording_panel import WorkspaceRecordingPanel
from ui.workspace.task_panel import WorkspaceTaskPanel
from ui.workspace.toolbar import WorkspaceToolbar


class WorkspaceWidget(BaseWidget):
    """Unified workspace page with item list, editor, and recording playback."""

    def __init__(
        self,
        workspace_manager,
        i18n,
        *,
        transcription_manager=None,
        realtime_recorder=None,
        parent=None,
    ):
        super().__init__(i18n, parent)
        self.workspace_manager = workspace_manager
        self.transcription_manager = transcription_manager
        self.realtime_recorder = realtime_recorder
        self._items_by_id = {}
        self._init_ui()
        self.refresh_items()

    def _init_ui(self) -> None:
        self.setProperty("role", ROLE_WORKSPACE_SURFACE)
        layout = QVBoxLayout(self)
        self.toolbar = WorkspaceToolbar(self.workspace_manager, self.i18n, self)
        self.item_list = WorkspaceItemList(self.i18n, self)
        self.editor_panel = WorkspaceEditorPanel(self.workspace_manager, self.i18n, parent=self)
        self.recording_control_panel = WorkspaceRecordingControlPanel(
            self.realtime_recorder,
            self.i18n,
            self,
        )
        self.recording_panel = WorkspaceRecordingPanel(self.workspace_manager, self.i18n, self)
        self.task_panel = None

        left_splitter = QSplitter(Qt.Orientation.Vertical, self)
        if self.transcription_manager is not None:
            self.task_panel = WorkspaceTaskPanel(
                self.transcription_manager,
                self.i18n,
                settings_manager=getattr(self.workspace_manager, "settings_manager", None),
                parent=self,
            )
            self.task_panel.workspace_refresh_requested.connect(self.refresh_items)
            left_splitter.addWidget(self.task_panel)
        left_splitter.addWidget(self.item_list)
        left_splitter.setStretchFactor(0, 1)
        left_splitter.setStretchFactor(1, 1)

        content_splitter = QSplitter(Qt.Orientation.Horizontal, self)
        content_splitter.addWidget(left_splitter)
        content_splitter.addWidget(self.editor_panel)

        recording_column = QWidget(self)
        recording_layout = QVBoxLayout(recording_column)
        recording_layout.setContentsMargins(0, 0, 0, 0)
        recording_layout.addWidget(self.recording_control_panel)
        recording_layout.addWidget(self.recording_panel, 1)
        content_splitter.addWidget(recording_column)
        content_splitter.setStretchFactor(0, 1)
        content_splitter.setStretchFactor(1, 2)
        content_splitter.setStretchFactor(2, 2)

        self.item_list.item_selected.connect(self._on_item_selected)
        self.item_list.collection_changed.connect(self.refresh_items)
        self.toolbar.item_open_requested.connect(self.open_item)
        self.toolbar.recording_requested.connect(self._focus_recording_panel)
        self.recording_control_panel.workspace_item_requested.connect(self.open_item)

        layout.addWidget(self.toolbar)
        layout.addWidget(content_splitter, 1)

    def refresh_items(self) -> None:
        current_item_id = self.item_list.current_item_id()
        items = self.workspace_manager.list_items(collection=self.item_list.current_collection())
        metadata_by_item = self.workspace_manager.get_item_list_metadata(items)
        self._items_by_id = {item.id: item for item in items}
        self.item_list.set_items(items, metadata_by_item=metadata_by_item)
        if items and current_item_id in self._items_by_id:
            self.item_list.select_item(current_item_id)
            self._on_item_selected(current_item_id)
        elif items:
            self._on_item_selected(items[0].id)
        else:
            self._on_item_selected("")

    def open_item(self, item_id: str, asset_role: str | None = None) -> bool:
        """Refresh and focus a specific workspace item."""
        self.refresh_items()
        if item_id and item_id not in self._items_by_id and self.item_list.current_collection() != "all":
            self.item_list.set_collection("all")
            self.refresh_items()
        if item_id and item_id in self._items_by_id:
            self.item_list.select_item(item_id)
            self._on_item_selected(item_id)
            if asset_role == "audio":
                self.recording_panel.setFocus()
            elif asset_role:
                self.editor_panel.select_asset_role(asset_role)
            return True
        return False

    def current_item_id(self) -> str:
        """Return the currently selected workspace item identifier."""
        return self.item_list.current_item_id()

    def _on_item_selected(self, item_id: str) -> None:
        item = self._items_by_id.get(item_id)
        self.editor_panel.set_item(item)
        self.recording_panel.set_item(item)

    def _focus_recording_panel(self) -> None:
        self.recording_control_panel.record_button.setFocus()
