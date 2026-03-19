# SPDX-License-Identifier: Apache-2.0
"""Workspace main widget."""

from __future__ import annotations

from core.qt_imports import (
    QAction,
    QFileDialog,
    QHBoxLayout,
    QSplitter,
    QTabBar,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
    Qt,
)
from ui.base_widgets import BaseWidget
from ui.constants import (
    ROLE_WORKSPACE_DOCUMENT_TABS,
    ROLE_WORKSPACE_SURFACE,
    ROLE_WORKSPACE_TAB_ACTION,
    ROLE_WORKSPACE_TAB_CLOSE,
    WORKSPACE_CONTENT_SPLITTER_DEFAULT_SIZES,
    WORKSPACE_EDITOR_STAGE_MIN_WIDTH,
    WORKSPACE_INSPECTOR_PANEL_MIN_WIDTH,
    WORKSPACE_LIBRARY_PANEL_MIN_WIDTH,
)
from ui.workspace.detached_document_window import DetachedDocumentWindow
from ui.workspace.editor_panel import WorkspaceEditorPanel
from ui.workspace.inspector_panel import WorkspaceInspectorPanel, set_trailing_splitter_panel_visible
from ui.workspace.library_panel import WorkspaceLibraryPanel


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
        self._suspend_tree_selection_sync = False
        self._inspector_expanded_sizes = list(WORKSPACE_CONTENT_SPLITTER_DEFAULT_SIZES)
        self._init_ui()
        self.refresh_items()

    def _init_ui(self) -> None:
        self.setProperty("role", ROLE_WORKSPACE_SURFACE)
        layout = QVBoxLayout(self)
        self.library_panel = WorkspaceLibraryPanel(self.workspace_manager, self.i18n, self)
        self.item_list = self.library_panel
        self.document_tabs = QTabWidget(self)
        self.document_tabs.setProperty("role", ROLE_WORKSPACE_DOCUMENT_TABS)
        self.document_tabs.setDocumentMode(True)
        self.document_tabs.setElideMode(Qt.TextElideMode.ElideRight)
        self.document_tabs.setUsesScrollButtons(True)
        self.document_tabs.setTabsClosable(False)
        self.document_tabs.currentChanged.connect(self._on_current_document_changed)
        self.document_tabs.tabBar().setExpanding(False)
        self.document_tabs.tabBar().setDrawBase(False)

        self.open_current_item_in_window_action = QAction(self)
        self.open_current_item_in_window_action.triggered.connect(
            self._open_current_item_in_detached_window
        )
        self.toggle_inspector_action = QAction(self)
        self.toggle_inspector_action.triggered.connect(self._toggle_inspector_panel)
        self.tab_actions_container = QWidget(self.document_tabs)
        self.tab_actions_layout = QHBoxLayout(self.tab_actions_container)
        self.tab_actions_layout.setContentsMargins(0, 0, 0, 0)
        self.tab_actions_layout.setSpacing(8)
        self.inspector_toggle_button = QToolButton(self.tab_actions_container)
        self.inspector_toggle_button.setProperty("role", ROLE_WORKSPACE_TAB_ACTION)
        self.inspector_toggle_button.setAutoRaise(False)
        self.inspector_toggle_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.inspector_toggle_button.setDefaultAction(self.toggle_inspector_action)
        self.tab_actions_layout.addWidget(self.inspector_toggle_button)
        self.open_in_window_button = QToolButton(self)
        self.open_in_window_button.setProperty("role", ROLE_WORKSPACE_TAB_ACTION)
        self.open_in_window_button.setAutoRaise(False)
        self.open_in_window_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.open_in_window_button.setDefaultAction(self.open_current_item_in_window_action)
        self.tab_actions_layout.addWidget(self.open_in_window_button)
        self.document_tabs.setCornerWidget(self.tab_actions_container, Qt.Corner.TopRightCorner)

        editor_stage = QWidget(self)
        editor_stage.setMinimumWidth(WORKSPACE_EDITOR_STAGE_MIN_WIDTH)
        editor_stage_layout = QVBoxLayout(editor_stage)
        editor_stage_layout.setContentsMargins(0, 0, 0, 0)
        editor_stage_layout.addWidget(self.document_tabs)
        self.inspector_panel = WorkspaceInspectorPanel(self.workspace_manager, self.i18n, self)
        self.inspector_panel.setMinimumWidth(WORKSPACE_INSPECTOR_PANEL_MIN_WIDTH)
        self.recording_panel = self.inspector_panel.recording_panel
        self.task_panel = None
        self.inspector_panel.set_editor_panel(None)

        self.library_panel.setMinimumWidth(WORKSPACE_LIBRARY_PANEL_MIN_WIDTH)

        content_splitter = QSplitter(Qt.Orientation.Horizontal, self)
        content_splitter.addWidget(self.library_panel)
        content_splitter.addWidget(editor_stage)
        content_splitter.addWidget(self.inspector_panel)
        content_splitter.setStretchFactor(0, 1)
        content_splitter.setStretchFactor(1, 2)
        content_splitter.setStretchFactor(2, 1)
        content_splitter.setSizes(list(WORKSPACE_CONTENT_SPLITTER_DEFAULT_SIZES))
        self.content_splitter = content_splitter

        self.library_panel.item_selected.connect(self._on_item_selected)
        self.library_panel.view_mode_changed.connect(self.refresh_items)
        self.library_panel.library_changed.connect(self.refresh_items)
        self.library_panel.import_document_requested.connect(self._import_document)
        self.library_panel.new_note_requested.connect(self._create_note)
        self.library_panel.open_in_window_requested.connect(self._open_item_in_detached_window)
        body = QWidget(self)
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.addWidget(content_splitter, 1)
        layout.addWidget(body, 1)
        self.update_translations()

    def update_translations(self) -> None:
        self.library_panel.update_translations()
        self.inspector_panel.update_translations()
        self._update_inspector_toggle_action()
        self.open_current_item_in_window_action.setText(
            self.i18n.t("workspace.open_in_new_window")
        )
        self.open_current_item_in_window_action.setToolTip(
            self.i18n.t("workspace.open_in_new_window")
        )
        for index in range(self.document_tabs.count()):
            editor_panel = self.document_tabs.widget(index)
            if hasattr(editor_panel, "update_translations"):
                editor_panel.update_translations()
        self._sync_document_tab_buttons()
        for detached_window in self._detached_windows.values():
            detached_window.update_translations()

    def refresh_items(self) -> None:
        current_open_item_id = self.editor_panel.current_item_id() if self.editor_panel is not None else ""
        items = self.workspace_manager.list_items(
            view_mode=self.library_panel.current_view_mode(),
        )
        metadata_by_item = self.workspace_manager.get_item_list_metadata(items)
        self._items_by_id = {item.id: item for item in items}
        self.library_panel.set_items(items, metadata_by_item=metadata_by_item)
        tree_selection_kind = self.library_panel.current_selection_kind()
        tree_selection_value = self.library_panel.current_selection_value()
        self._refresh_document_tabs()
        if items and tree_selection_kind == "item" and tree_selection_value in self._items_by_id:
            self.open_item(tree_selection_value)
        elif items and tree_selection_kind in {"folder", "event"}:
            if current_open_item_id in self._items_by_id:
                self.open_item(current_open_item_id, sync_tree_selection=False)
            else:
                self.open_item(items[0].id, sync_tree_selection=False)
        elif items and current_open_item_id in self._items_by_id:
            self.open_item(current_open_item_id)
        elif items:
            self.open_item(items[0].id)
        else:
            self._clear_document_stage()

    def open_item(
        self,
        item_id: str,
        asset_role: str | None = None,
        view_mode: str | None = None,
        *,
        sync_tree_selection: bool = True,
    ) -> bool:
        """Refresh and focus a specific workspace item."""
        if item_id not in self._items_by_id:
            item = self.workspace_manager.get_item(item_id)
            if item is None:
                return False
            self.library_panel.select_folder(getattr(item, "folder_id", None))
            self.refresh_items()
        item = self._items_by_id.get(item_id)
        if item is None:
            return False

        editor_panel = self._ensure_document_tab(item_id)
        previous_suspend_state = self._suspend_tree_selection_sync
        self._suspend_tree_selection_sync = not sync_tree_selection
        try:
            self.document_tabs.setCurrentWidget(editor_panel)
        finally:
            self._suspend_tree_selection_sync = previous_suspend_state
        if sync_tree_selection:
            self.library_panel.select_item(item_id)
        self.inspector_panel.set_item(item)
        self.inspector_panel.set_editor_panel(editor_panel)
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
        editor_panel.item_renamed.connect(self._on_editor_item_renamed)
        editor_panel.set_item(item)
        self.document_tabs.addTab(editor_panel, item.title if item is not None else item_id)
        self._sync_document_tab_buttons()
        return editor_panel

    def _refresh_document_tabs(self) -> None:
        for index in range(self.document_tabs.count() - 1, -1, -1):
            editor_panel = self.document_tabs.widget(index)
            if not isinstance(editor_panel, WorkspaceEditorPanel):
                continue
            item_id = editor_panel.current_item_id()
            item = self.workspace_manager.get_item(item_id) if item_id else None
            if item is None:
                self._close_document_tab(index)
                continue
            editor_panel.set_item(item)
            self.document_tabs.setTabText(index, item.title)
        self._sync_document_tab_buttons()

    def _close_document_tab(self, index: int) -> None:
        widget = self.document_tabs.widget(index)
        self.document_tabs.removeTab(index)
        if widget is not None:
            widget.deleteLater()
        self._sync_document_tab_buttons()
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
        self.inspector_panel.set_editor_panel(editor_panel)
        if item_id and not self._suspend_tree_selection_sync:
            self.library_panel.select_item(item_id)

    def _open_current_item_in_detached_window(self) -> None:
        editor_panel = self.editor_panel
        asset_role = editor_panel.current_asset_role() if editor_panel is not None else None
        self._open_item_in_detached_window(self.current_item_id(), asset_role=asset_role)

    def _open_item_in_detached_window(self, item_id: str, asset_role: str | None = None) -> None:
        if not item_id:
            return
        window = self._detached_windows.get(item_id)
        if window is None:
            window = DetachedDocumentWindow(
                self.workspace_manager,
                self.i18n,
                item_id,
                asset_role=asset_role,
                parent=self.window(),
            )
            window.destroyed.connect(lambda _obj=None, closed_item_id=item_id: self._detached_windows.pop(closed_item_id, None))
            self._detached_windows[item_id] = window
        else:
            window.load_item(item_id, asset_role=asset_role)
        window.show()
        window.raise_()
        window.activateWindow()

    def _sync_document_tab_buttons(self) -> None:
        tab_bar = self.document_tabs.tabBar()
        for index in range(self.document_tabs.count()):
            button = tab_bar.tabButton(index, QTabBar.ButtonPosition.RightSide)
            if not isinstance(button, QToolButton) or button.property("role") != ROLE_WORKSPACE_TAB_CLOSE:
                button = QToolButton(tab_bar)
                button.setProperty("role", ROLE_WORKSPACE_TAB_CLOSE)
                button.setAutoRaise(False)
                button.setText("x")
                button.setFixedSize(18, 18)
                button.clicked.connect(self._close_document_tab_from_button)
                tab_bar.setTabButton(index, QTabBar.ButtonPosition.RightSide, button)
            button.setToolTip(self.i18n.t("common.close"))

    def _close_document_tab_from_button(self) -> None:
        sender = self.sender()
        tab_bar = self.document_tabs.tabBar()
        for index in range(self.document_tabs.count()):
            if tab_bar.tabButton(index, QTabBar.ButtonPosition.RightSide) is sender:
                self._close_document_tab(index)
                return

    def _toggle_inspector_panel(self) -> None:
        self._set_inspector_visible(not self._is_inspector_panel_open())

    def _set_inspector_visible(self, visible: bool) -> None:
        self._inspector_expanded_sizes = set_trailing_splitter_panel_visible(
            self.content_splitter,
            self.inspector_panel,
            visible=visible,
            expanded_sizes=self._inspector_expanded_sizes,
            fallback_sizes=WORKSPACE_CONTENT_SPLITTER_DEFAULT_SIZES,
        )
        self._update_inspector_toggle_action()

    def _is_inspector_panel_open(self) -> bool:
        return not self.inspector_panel.isHidden()

    def _update_inspector_toggle_action(self) -> None:
        text_key = (
            "workspace.hide_inspector_panel"
            if self._is_inspector_panel_open()
            else "workspace.show_inspector_panel"
        )
        text = self.i18n.t(text_key)
        self.toggle_inspector_action.setText(text)
        self.toggle_inspector_action.setToolTip(text)

    def _clear_document_stage(self) -> None:
        self.inspector_panel.set_item(None)
        self.inspector_panel.set_editor_panel(None)

    def _on_editor_item_renamed(self, item_id: str) -> None:
        self.refresh_items()
        self.open_item(item_id)

    def _import_document(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(self, self.i18n.t("workspace.import_document"))
        if not file_path:
            return
        item_id = self.workspace_manager.import_document(file_path)
        if item_id:
            self.open_item(item_id)

    def _create_note(self) -> None:
        item_id = self.workspace_manager.create_note(
            title=self.i18n.t("workspace.new_note_default_title")
        )
        if item_id:
            self.refresh_items()
            self.open_item(item_id)
