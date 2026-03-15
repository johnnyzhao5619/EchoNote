# SPDX-License-Identifier: Apache-2.0
"""Workspace main widget."""

from __future__ import annotations

from core.qt_imports import QAction, QSplitter, QTabWidget, QToolButton, QVBoxLayout, QWidget, Qt
from ui.base_widgets import BaseWidget
from ui.constants import ROLE_WORKSPACE_SURFACE
from ui.workspace.detached_document_window import DetachedDocumentWindow
from ui.workspace.editor_panel import WorkspaceEditorPanel
from ui.workspace.inspector_panel import WorkspaceInspectorPanel
from ui.workspace.library_panel import WorkspaceLibraryPanel
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
        self._detached_windows: dict[str, DetachedDocumentWindow] = {}
        self._init_ui()
        self.refresh_items()

    def _init_ui(self) -> None:
        self.setProperty("role", ROLE_WORKSPACE_SURFACE)
        layout = QVBoxLayout(self)
        self.toolbar = WorkspaceToolbar(self.workspace_manager, self.i18n, self)
        self.toolbar.start_recording_button.hide()
        self.library_panel = WorkspaceLibraryPanel(self.workspace_manager, self.i18n, self)
        self.item_list = self.library_panel.item_list
        self.document_tabs = QTabWidget(self)
        self.document_tabs.setTabsClosable(True)
        self.document_tabs.tabCloseRequested.connect(self._close_document_tab)
        self.document_tabs.currentChanged.connect(self._on_current_document_changed)

        self.open_current_item_in_window_action = QAction(self)
        self.open_current_item_in_window_action.triggered.connect(
            self._open_current_item_in_detached_window
        )
        self.open_in_window_button = QToolButton(self)
        self.open_in_window_button.setDefaultAction(self.open_current_item_in_window_action)
        self.document_tabs.setCornerWidget(self.open_in_window_button, Qt.Corner.TopRightCorner)

        editor_stage = QWidget(self)
        editor_stage_layout = QVBoxLayout(editor_stage)
        editor_stage_layout.setContentsMargins(0, 0, 0, 0)
        editor_stage_layout.addWidget(self.document_tabs)
        self.inspector_panel = WorkspaceInspectorPanel(self.workspace_manager, self.i18n, self)
        self.recording_panel = self.inspector_panel.recording_panel
        self.task_panel = None

        left_splitter = QSplitter(Qt.Orientation.Vertical, self)
        left_splitter.addWidget(self.library_panel)
        left_splitter.setStretchFactor(0, 1)

        content_splitter = QSplitter(Qt.Orientation.Horizontal, self)
        content_splitter.addWidget(left_splitter)
        content_splitter.addWidget(editor_stage)
        content_splitter.addWidget(self.inspector_panel)
        content_splitter.setStretchFactor(0, 1)
        content_splitter.setStretchFactor(1, 2)
        content_splitter.setStretchFactor(2, 2)

        self.library_panel.item_selected.connect(self._on_item_selected)
        self.library_panel.view_mode_changed.connect(self.refresh_items)
        self.library_panel.library_changed.connect(self.refresh_items)
        self.toolbar.item_open_requested.connect(self.open_item)

        layout.addWidget(self.toolbar)
        layout.addWidget(content_splitter, 1)

    def refresh_items(self) -> None:
        current_item_id = self.library_panel.current_item_id()
        items = self.workspace_manager.list_items(
            view_mode=self.library_panel.current_view_mode(),
            folder_id=self.library_panel.current_folder_id(),
        )
        metadata_by_item = self.workspace_manager.get_item_list_metadata(items)
        self._items_by_id = {item.id: item for item in items}
        self.library_panel.set_items(items, metadata_by_item=metadata_by_item)
        self._refresh_document_tabs()
        if items and current_item_id in self._items_by_id:
            self.library_panel.select_item(current_item_id)
            self.open_item(current_item_id)
        elif items and self.current_item_id():
            self.open_item(self.current_item_id())
        elif items:
            self.open_item(items[0].id)
        else:
            self._clear_document_stage()

    def open_item(
        self,
        item_id: str,
        asset_role: str | None = None,
        view_mode: str | None = None,
    ) -> bool:
        """Refresh and focus a specific workspace item."""
        if view_mode and self.library_panel.current_view_mode() != view_mode:
            self.library_panel.set_view_mode(view_mode)
            self.refresh_items()
        if item_id not in self._items_by_id:
            item = self.workspace_manager.get_item(item_id)
            if item is None:
                return False
            if view_mode == "event":
                self.refresh_items()
            else:
                self.library_panel.set_view_mode("structure")
                self.library_panel.select_folder(getattr(item, "folder_id", None))
                self.refresh_items()
        item = self._items_by_id.get(item_id)
        if item is None:
            return False

        editor_panel = self._ensure_document_tab(item_id)
        self.document_tabs.setCurrentWidget(editor_panel)
        self.library_panel.select_item(item_id)
        self.inspector_panel.set_item(item)
        if asset_role == "audio":
            self.recording_panel.setFocus()
        elif asset_role:
            editor_panel.select_asset_role(asset_role)
        return True

    @property
    def editor_panel(self) -> WorkspaceEditorPanel | None:
        """Expose the active document editor for workspace callers/tests."""
        current_widget = self.document_tabs.currentWidget()
        return current_widget if isinstance(current_widget, WorkspaceEditorPanel) else None

    def current_item_id(self) -> str:
        """Return the currently selected workspace item identifier."""
        editor_panel = self.editor_panel
        if editor_panel is not None:
            return editor_panel.current_item_id()
        return self.library_panel.current_item_id()

    def _on_item_selected(self, item_id: str) -> None:
        if not item_id:
            self._clear_document_stage()
            return
        self.open_item(item_id)

    def _ensure_document_tab(self, item_id: str) -> WorkspaceEditorPanel:
        for index in range(self.document_tabs.count()):
            editor_panel = self.document_tabs.widget(index)
            if isinstance(editor_panel, WorkspaceEditorPanel) and editor_panel.current_item_id() == item_id:
                item = self._items_by_id.get(item_id) or self.workspace_manager.get_item(item_id)
                if item is not None:
                    editor_panel.set_item(item)
                    self.document_tabs.setTabText(index, item.title or item.id)
                return editor_panel

        item = self._items_by_id.get(item_id) or self.workspace_manager.get_item(item_id)
        editor_panel = WorkspaceEditorPanel(self.workspace_manager, self.i18n, parent=self.document_tabs)
        editor_panel.set_item(item)
        self.document_tabs.addTab(editor_panel, item.title if item is not None else item_id)
        return editor_panel

    def _refresh_document_tabs(self) -> None:
        for index in range(self.document_tabs.count()):
            editor_panel = self.document_tabs.widget(index)
            if not isinstance(editor_panel, WorkspaceEditorPanel):
                continue
            item_id = editor_panel.current_item_id()
            item = self.workspace_manager.get_item(item_id) if item_id else None
            editor_panel.set_item(item)
            self.document_tabs.setTabText(index, item.title if item is not None else item_id)

    def _close_document_tab(self, index: int) -> None:
        widget = self.document_tabs.widget(index)
        self.document_tabs.removeTab(index)
        if widget is not None:
            widget.deleteLater()
        if self.document_tabs.count() == 0:
            self._clear_document_stage()

    def _on_current_document_changed(self, index: int) -> None:
        if index < 0:
            self._clear_document_stage()
            return
        editor_panel = self.document_tabs.widget(index)
        if not isinstance(editor_panel, WorkspaceEditorPanel):
            return
        item_id = editor_panel.current_item_id()
        item = self.workspace_manager.get_item(item_id) if item_id else None
        self.inspector_panel.set_item(item)
        if item_id:
            self.library_panel.select_item(item_id)

    def _open_current_item_in_detached_window(self) -> None:
        item_id = self.current_item_id()
        if not item_id:
            return
        window = self._detached_windows.get(item_id)
        if window is None:
            window = DetachedDocumentWindow(self.workspace_manager, self.i18n, item_id, parent=self)
            window.destroyed.connect(lambda _obj=None, closed_item_id=item_id: self._detached_windows.pop(closed_item_id, None))
            self._detached_windows[item_id] = window
        else:
            window.load_item(item_id)
        window.show()
        window.raise_()
        window.activateWindow()

    def _clear_document_stage(self) -> None:
        self.inspector_panel.set_item(None)
