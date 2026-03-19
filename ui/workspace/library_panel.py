# SPDX-License-Identifier: Apache-2.0
"""Workspace library shell panel."""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from core.qt_imports import (
    QAbstractItemView,
    QApplication,
    QButtonGroup,
    QFont,
    QHBoxLayout,
    QIcon,
    QLabel,
    QInputDialog,
    QMenu,
    QMessageBox,
    QPalette,
    QPixmap,
    QPushButton,
    QSize,
    QSizePolicy,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QUrl,
    QVBoxLayout,
    QWidget,
    Qt,
    Signal,
)
from core.workspace.manager import WorkspaceValidationError
from ui.base_widgets import BaseWidget
from ui.constants import (
    CONTROL_BUTTON_MIN_HEIGHT,
    PAGE_DENSE_SPACING,
    ROLE_WORKSPACE_CONTEXT_LABEL,
    ROLE_WORKSPACE_EXPLORER_HEADER,
    ROLE_WORKSPACE_HEADER_ACTION,
    ROLE_WORKSPACE_LIBRARY_PANEL,
    ROLE_WORKSPACE_NAV_TREE,
)
from ui.workspace.item_list import build_workspace_item_tooltip

_TREE_KIND_ROLE = Qt.ItemDataRole.UserRole
_TREE_VALUE_ROLE = Qt.ItemDataRole.UserRole + 1
_TREE_LABEL_ROLE = Qt.ItemDataRole.UserRole + 2
_TREE_CONTEXT_ROLE = Qt.ItemDataRole.UserRole + 3
_HEADER_ACTION_ICON_SIZE = 16

from ui.common.svg_icons import build_svg_icon
from ui.workspace_drag_payload import (
    WORKSPACE_DRAG_SOURCE_BATCH_TASK,
    WORKSPACE_DRAG_SOURCE_EVENT,
    WORKSPACE_TEXT_DRAG_MIME,
    parse_workspace_text_drag_payload,
)


class WorkspaceNavigationTree(QTreeWidget):
    """Tree widget with structure drag-and-drop hooks."""

    drop_requested = Signal(str, str, str, str)
    external_drop_requested = Signal(object, str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragEnabled(True)
        self.viewport().setAcceptDrops(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)

    def dropEvent(self, event) -> None:
        payload = self._external_workspace_drag_payload(event)
        if payload is not None:
            target_item = self.itemAt(event.position().toPoint())
            target_kind = str(target_item.data(0, _TREE_KIND_ROLE) or "") if target_item else ""
            target_value = str(target_item.data(0, _TREE_VALUE_ROLE) or "") if target_item else ""
            self.external_drop_requested.emit(payload, target_kind, target_value)
            event.acceptProposedAction()
            return
        source_item = self.currentItem()
        target_item = self.itemAt(event.position().toPoint())
        if source_item is None:
            event.ignore()
            return
        source_kind = str(source_item.data(0, _TREE_KIND_ROLE) or "")
        source_value = str(source_item.data(0, _TREE_VALUE_ROLE) or "")
        target_kind = str(target_item.data(0, _TREE_KIND_ROLE) or "") if target_item else ""
        target_value = str(target_item.data(0, _TREE_VALUE_ROLE) or "") if target_item else ""
        if source_kind == "folder" and target_kind != "folder":
            event.ignore()
            return
        self.drop_requested.emit(source_kind, source_value, target_kind, target_value)
        event.ignore()

    def dragEnterEvent(self, event) -> None:
        if self._external_workspace_drag_payload(event) is not None:
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:
        if self._external_workspace_drag_payload(event) is not None:
            event.acceptProposedAction()
            return
        super().dragMoveEvent(event)

    @staticmethod
    def _external_workspace_drag_payload(event) -> dict | None:
        mime_data = event.mimeData()
        if mime_data is None or not mime_data.hasFormat(WORKSPACE_TEXT_DRAG_MIME):
            return None
        raw_payload = mime_data.data(WORKSPACE_TEXT_DRAG_MIME)
        return parse_workspace_text_drag_payload(bytes(raw_payload))


class WorkspaceLibraryPanel(BaseWidget):
    """Left-side workspace navigator using a single tree structure."""

    item_selected = Signal(str)
    view_mode_changed = Signal(str)
    library_changed = Signal()
    import_document_requested = Signal()
    new_note_requested = Signal()
    open_in_window_requested = Signal(str)

    def __init__(self, workspace_manager, i18n, parent=None):
        super().__init__(i18n, parent)
        self.workspace_manager = workspace_manager
        self._workspace_items = []
        self._metadata_by_item: dict[str, dict] = {}
        self._pending_selection: tuple[str, str] | None = None
        self._folder_nodes: dict[str, QTreeWidgetItem] = {}
        self._item_nodes: dict[str, QTreeWidgetItem] = {}
        self._init_ui()

    def _init_ui(self) -> None:
        self.setProperty("role", ROLE_WORKSPACE_LIBRARY_PANEL)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(PAGE_DENSE_SPACING)

        self.explorer_header = QWidget(self)
        self.explorer_header.setProperty("role", ROLE_WORKSPACE_EXPLORER_HEADER)
        explorer_header_layout = QVBoxLayout(self.explorer_header)
        explorer_header_layout.setContentsMargins(0, 0, 0, 0)
        explorer_header_layout.setSpacing(PAGE_DENSE_SPACING)

        header_text_widget = QWidget(self.explorer_header)
        header_text_layout = QVBoxLayout(header_text_widget)
        header_text_layout.setContentsMargins(0, 0, 0, 0)
        header_text_layout.setSpacing(2)

        self.title_label = QLabel(self.i18n.t("workspace.library_title"))
        header_text_layout.addWidget(self.title_label)

        self.context_label = QLabel(self.explorer_header)
        self.context_label.setProperty("role", ROLE_WORKSPACE_CONTEXT_LABEL)
        header_text_layout.addWidget(self.context_label)

        explorer_header_layout.addWidget(header_text_widget)

        self.header_action_bar = QWidget(self.explorer_header)
        header_action_bar_layout = QHBoxLayout(self.header_action_bar)
        header_action_bar_layout.setContentsMargins(0, 0, 0, 0)
        header_action_bar_layout.setSpacing(PAGE_DENSE_SPACING)

        self.import_document_button = self._create_header_action_button(
            self.header_action_bar,
            icon_name="import",
        )
        self.import_document_button.clicked.connect(self.import_document_requested.emit)
        header_action_bar_layout.addWidget(self.import_document_button)

        self.new_note_button = self._create_header_action_button(
            self.header_action_bar,
            icon_name="new_note",
        )
        self.new_note_button.clicked.connect(self.new_note_requested.emit)
        header_action_bar_layout.addWidget(self.new_note_button)

        self.new_folder_button = self._create_header_action_button(
            self.header_action_bar,
            icon_name="new_folder",
        )
        self.new_folder_button.clicked.connect(self._on_create_folder)
        header_action_bar_layout.addWidget(self.new_folder_button)

        self.rename_folder_button = self._create_header_action_button(
            self.header_action_bar,
            icon_name="rename",
        )
        self.rename_folder_button.clicked.connect(self._on_rename_selection)
        header_action_bar_layout.addWidget(self.rename_folder_button)

        self.delete_folder_button = self._create_header_action_button(
            self.header_action_bar,
            icon_name="delete",
        )
        self.delete_folder_button.clicked.connect(self._on_delete_selection)
        header_action_bar_layout.addWidget(self.delete_folder_button)
        header_action_bar_layout.addStretch()
        explorer_header_layout.addWidget(self.header_action_bar)

        layout.addWidget(self.explorer_header)

        self.folder_tree = WorkspaceNavigationTree(self)
        self.folder_tree.setProperty("role", ROLE_WORKSPACE_NAV_TREE)
        self.folder_tree.setHeaderHidden(True)
        self.folder_tree.setUniformRowHeights(True)
        self.folder_tree.setIndentation(14)
        self.folder_tree.setRootIsDecorated(True)
        self.folder_tree.setItemsExpandable(True)
        self.folder_tree.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.folder_tree.itemSelectionChanged.connect(self._on_navigation_selection_changed)
        self.folder_tree.drop_requested.connect(self._on_tree_drop_requested)
        self.folder_tree.external_drop_requested.connect(self._on_external_workspace_drop_requested)
        self.folder_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.folder_tree.customContextMenuRequested.connect(self._on_custom_context_menu_requested)
        layout.addWidget(self.folder_tree, 1)

        self.folder_tree.setDragEnabled(True)
        self.folder_tree.viewport().setAcceptDrops(True)
        self.folder_tree.setAcceptDrops(True)
        self.folder_tree.setDropIndicatorShown(True)
        self._update_header_action_states()

        self.update_translations()

    def update_translations(self) -> None:
        self.title_label.setText(self.i18n.t("workspace.library_title"))
        self._update_header_action_button(
            self.import_document_button,
            tooltip=self.i18n.t("workspace.import_document"),
            icon_name="import",
        )
        self._update_header_action_button(
            self.new_note_button,
            tooltip=self.i18n.t("workspace.new_note"),
            icon_name="new_note",
        )
        self._update_header_action_button(
            self.new_folder_button,
            tooltip=self.i18n.t("workspace.new_folder"),
            icon_name="new_folder",
        )
        self._update_header_action_button(
            self.rename_folder_button,
            tooltip=self.i18n.t("common.rename"),
            icon_name="rename",
        )
        self._update_header_action_button(
            self.delete_folder_button,
            tooltip=self.i18n.t("common.delete"),
            icon_name="delete",
        )
        self.refresh_navigation()
        self._update_context_label()

    def _create_header_action_button(self, parent: QWidget, *, icon_name: str) -> QToolButton:
        button = QToolButton(parent)
        button.setProperty("role", ROLE_WORKSPACE_HEADER_ACTION)
        button.setAutoRaise(False)
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        button.setFixedSize(CONTROL_BUTTON_MIN_HEIGHT, CONTROL_BUTTON_MIN_HEIGHT)
        button.setIconSize(QSize(_HEADER_ACTION_ICON_SIZE, _HEADER_ACTION_ICON_SIZE))
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._update_header_action_button(button, tooltip="", icon_name=icon_name)
        return button

    def _update_header_action_button(
        self,
        button: QToolButton,
        *,
        tooltip: str,
        icon_name: str,
    ) -> None:
        button.setText("")
        button.setToolTip(tooltip)
        button.setAccessibleName(tooltip)
        button.setIcon(self._build_header_action_icon(icon_name))

    def _build_header_action_icon(self, icon_name: str) -> QIcon:
        color = self.palette().color(QPalette.ColorRole.ButtonText).name()
        return build_svg_icon(icon_name, color)

    def set_items(self, items, *, metadata_by_item=None) -> None:
        self._workspace_items = list(items)
        self._metadata_by_item = metadata_by_item or {}
        self.refresh_navigation()

    def refresh_navigation(self) -> None:
        pending_selection = self._pending_selection
        self._pending_selection = None
        selected_item_id = self.current_item_id()
        selected_folder_id = self.current_folder_id()

        self._folder_nodes.clear()
        self._item_nodes.clear()

        self.folder_tree.blockSignals(True)
        self.folder_tree.clear()

        self._build_structure_tree()

        if pending_selection is not None:
            self._select_tree_identity(*pending_selection)
        elif selected_item_id:
            self.select_item(selected_item_id)
        elif selected_folder_id:
            self.select_folder(selected_folder_id)

        self.folder_tree.blockSignals(False)
        self._update_context_label()

    def _build_structure_tree(self) -> None:
        folders = sorted(
            self.workspace_manager.list_folders(),
            key=self._folder_sort_key,
        )
        for folder in folders:
            node = QTreeWidgetItem([folder.name])
            node.setData(0, _TREE_KIND_ROLE, "folder")
            node.setData(0, _TREE_VALUE_ROLE, folder.id)
            node.setData(0, _TREE_LABEL_ROLE, folder.name)
            node.setData(0, _TREE_CONTEXT_ROLE, folder.id)
            node.setIcon(0, self._build_tree_icon(self._folder_icon_name(folder)))
            folder_font = QFont(self.font())
            folder_font.setBold(True)
            node.setFont(0, folder_font)
            self._folder_nodes[folder.id] = node

        for folder in folders:
            node = self._folder_nodes[folder.id]
            parent_node = self._folder_nodes.get(folder.parent_id)
            if parent_node is None:
                self.folder_tree.addTopLevelItem(node)
            else:
                parent_node.addChild(node)

        sorted_items = sorted(
            self._workspace_items,
            key=lambda item: ((item.folder_id or ""), -(self._item_sort_timestamp(item)), item.title.lower()),
        )
        for item in sorted_items:
            node = self._create_item_node(item, context_value=item.folder_id)
            parent_node = self._folder_nodes.get(item.folder_id)
            if parent_node is None:
                self.folder_tree.addTopLevelItem(node)
            else:
                parent_node.addChild(node)

        for node in self._folder_nodes.values():
            node.setExpanded(True)



    def _create_item_node(self, item, *, context_value: str | None) -> QTreeWidgetItem:
        title = item.title or item.id
        node = QTreeWidgetItem([title])
        node.setData(0, _TREE_KIND_ROLE, "item")
        node.setData(0, _TREE_VALUE_ROLE, item.id)
        node.setData(0, _TREE_LABEL_ROLE, title)
        node.setData(0, _TREE_CONTEXT_ROLE, context_value or "")
        node.setIcon(0, self._build_tree_icon("item"))
        tooltip = build_workspace_item_tooltip(
            self.i18n,
            title,
            self._metadata_by_item.get(item.id, {}),
            view_mode=self.current_view_mode(),
        )
        node.setToolTip(0, tooltip)
        self._item_nodes[item.id] = node
        return node

    @staticmethod
    def _item_sort_timestamp(item) -> int:
        updated_at = getattr(item, "updated_at", "") or ""
        try:
            return int(datetime.fromisoformat(updated_at.replace("Z", "+00:00")).timestamp())
        except Exception:
            return 0

    def current_view_mode(self) -> str:
        return "structure"

    def current_item_id(self) -> str:
        current_item = self._current_tree_item()
        if current_item is None or current_item.data(0, _TREE_KIND_ROLE) != "item":
            return ""
        return current_item.data(0, _TREE_VALUE_ROLE) or ""

    def current_selection_kind(self) -> str:
        current_item = self._current_tree_item()
        if current_item is None:
            return ""
        return str(current_item.data(0, _TREE_KIND_ROLE) or "")

    def current_selection_value(self) -> str:
        current_item = self._current_tree_item()
        if current_item is None:
            return ""
        return str(current_item.data(0, _TREE_VALUE_ROLE) or "")

    def current_folder_id(self) -> str | None:
        if self.current_view_mode() != "structure":
            return None
        current_item = self._current_tree_item()
        if current_item is None:
            return None
        kind = current_item.data(0, _TREE_KIND_ROLE)
        if kind == "folder":
            return current_item.data(0, _TREE_VALUE_ROLE)
        if kind == "item":
            context_value = current_item.data(0, _TREE_CONTEXT_ROLE)
            return context_value or None
        return None

    def current_event_id(self) -> str | None:
        if self.current_view_mode() != "event":
            return None
        current_item = self._current_tree_item()
        if current_item is None:
            return None
        kind = current_item.data(0, _TREE_KIND_ROLE)
        if kind == "event":
            value = current_item.data(0, _TREE_VALUE_ROLE)
            return value if value != "" else ""
        if kind == "item":
            value = current_item.data(0, _TREE_CONTEXT_ROLE)
            return value if value != "" else ""
        return None

    def select_item(self, item_id: str) -> None:
        self._select_tree_identity("item", item_id)

    def select_folder(self, folder_id: str | None) -> None:
        if self.current_view_mode() != "structure":
            return
        if not folder_id:
            self.folder_tree.clearSelection()
            return
        self._select_tree_identity("folder", folder_id)

    def select_event(self, event_id: str | None) -> None:
        if self.current_view_mode() != "event":
            return
        self._select_tree_identity("event", event_id or "")

    def find_item_node(self, item_id: str) -> QTreeWidgetItem | None:
        live_node = self._find_tree_node("item", item_id)
        if live_node is not None:
            self._item_nodes[item_id] = live_node
        return live_node

    def item_node_count(self) -> int:
        return len(self._item_nodes)

    def item_tooltip(self, item_id: str) -> str:
        node = self.find_item_node(item_id)
        if node is None:
            return ""
        return node.toolTip(0)

    def _current_tree_item(self) -> QTreeWidgetItem | None:
        try:
            return self.folder_tree.currentItem()
        except RuntimeError:
            return None

    def _set_current_tree_item(self, target_item: QTreeWidgetItem | None) -> None:
        if target_item is None:
            self.folder_tree.clearSelection()
            return
        self._expand_tree_item_ancestors(target_item)
        self.folder_tree.setCurrentItem(target_item)
        self.folder_tree.scrollToItem(
            target_item,
            QAbstractItemView.ScrollHint.PositionAtCenter,
        )

    def _select_tree_identity(self, kind: str, value: str) -> None:
        target_item = self._find_tree_node(kind, value)
        self._set_current_tree_item(target_item)

    def _find_tree_node(self, kind: str, value: str) -> QTreeWidgetItem | None:
        for index in range(self.folder_tree.topLevelItemCount()):
            top_level_item = self.folder_tree.topLevelItem(index)
            resolved = self._find_tree_node_in_subtree(top_level_item, kind, value)
            if resolved is not None:
                return resolved
        return None

    def _find_tree_node_in_subtree(
        self,
        node: QTreeWidgetItem | None,
        kind: str,
        value: str,
    ) -> QTreeWidgetItem | None:
        if node is None:
            return None
        node_kind = str(node.data(0, _TREE_KIND_ROLE) or "")
        node_value = str(node.data(0, _TREE_VALUE_ROLE) or "")
        if node_kind == kind and node_value == value:
            return node
        for child_index in range(node.childCount()):
            resolved = self._find_tree_node_in_subtree(node.child(child_index), kind, value)
            if resolved is not None:
                return resolved
        return None

    def _expand_tree_item_ancestors(self, node: QTreeWidgetItem) -> None:
        current = node.parent()
        while current is not None:
            current.setExpanded(True)
            current = current.parent()

    def _on_navigation_selection_changed(self) -> None:
        self._update_context_label()
        self._update_header_action_states()
        item_id = self.current_item_id()
        if item_id:
            self.item_selected.emit(item_id)

    def _on_custom_context_menu_requested(self, position) -> None:
        if self.current_view_mode() != "structure":
            return
        target_item = self.folder_tree.itemAt(position)
        if target_item is not None:
            self._set_current_tree_item(target_item)

        menu = QMenu(self)
        if target_item is None:
            self._populate_empty_context_menu(menu)
        else:
            kind = str(target_item.data(0, _TREE_KIND_ROLE) or "")
            value = str(target_item.data(0, _TREE_VALUE_ROLE) or "")
            if kind == "folder":
                self._populate_folder_context_menu(menu, value)
            elif kind == "item":
                self._populate_item_context_menu(menu, value)

        if menu.actions():
            menu.exec(self.folder_tree.viewport().mapToGlobal(position))

    def _populate_empty_context_menu(self, menu: QMenu) -> None:
        self._add_menu_action(
            menu,
            self.i18n.t("workspace.new_note"),
            lambda: self._create_note_in_folder(self.workspace_manager.ensure_inbox_folder().id),
        )
        self._add_menu_action(menu, self.i18n.t("workspace.new_folder"), self._on_create_folder)
        menu.addSeparator()
        self._add_menu_action(menu, self.i18n.t("workspace.import_document"), self.import_document_requested.emit)
        self._add_menu_action(
            menu,
            self.i18n.t("workspace.open_vault_root"),
            lambda: self._open_local_path(Path(self.workspace_manager.file_manager.workspace_dir)),
        )

    def _populate_folder_context_menu(self, menu: QMenu, folder_id: str) -> None:
        folder = self.workspace_manager.get_folder(folder_id)
        if folder is None:
            return
        folder_kind = getattr(folder, "folder_kind", "") or ""
        folder_path = self.workspace_manager.get_folder_filesystem_path(folder_id)

        if folder_kind in {"user", "inbox"}:
            self._add_menu_action(
                menu,
                self.i18n.t("workspace.new_note"),
                lambda: self._create_note_in_folder(folder_id),
            )
            self._add_menu_action(menu, self.i18n.t("workspace.new_folder"), self._on_create_folder)
            menu.addSeparator()

        if folder_path:
            self._add_menu_action(
                menu,
                self.i18n.t("workspace.open_local_folder"),
                lambda: self._open_local_path(Path(folder_path)),
            )
            self._add_menu_action(
                menu,
                self.i18n.t("workspace.copy_local_path"),
                lambda: self._copy_local_path(folder_path),
            )

        if self._can_manage_folder(folder_id):
            menu.addSeparator()
            self._add_menu_action(menu, self.i18n.t("common.rename"), self._on_rename_selection)
            self._add_menu_action(menu, self.i18n.t("common.delete"), self._on_delete_selection)
        elif self._can_delete_generated_folder(folder_id):
            menu.addSeparator()
            self._add_menu_action(menu, self.i18n.t("common.delete"), self._on_delete_selection)

    def _populate_item_context_menu(self, menu: QMenu, item_id: str) -> None:
        item = self.workspace_manager.get_item(item_id)
        if item is None:
            return
        item_path = self.workspace_manager.get_item_filesystem_path(item_id)

        self._add_menu_action(menu, self.i18n.t("workspace.open_item"), lambda: self._open_item(item_id))
        self._add_menu_action(
            menu,
            self.i18n.t("workspace.open_in_new_window"),
            lambda: self.open_in_window_requested.emit(item_id),
        )

        if item_path:
            menu.addSeparator()
            self._add_menu_action(
                menu,
                self.i18n.t("workspace.open_local_folder"),
                lambda: self._open_local_path(Path(item_path), open_parent=True),
            )
            self._add_menu_action(
                menu,
                self.i18n.t("workspace.copy_local_path"),
                lambda: self._copy_local_path(item_path),
            )

        menu.addSeparator()
        self._add_menu_action(menu, self.i18n.t("common.rename"), self._on_rename_selection)
        self._add_menu_action(menu, self.i18n.t("common.delete"), self._on_delete_selection)

    @staticmethod
    def _add_menu_action(menu: QMenu, text: str, callback) -> None:
        action = menu.addAction(text)
        action.triggered.connect(lambda _checked=False: callback())

    def _create_note_in_folder(self, folder_id: str) -> None:
        try:
            item_id = self.workspace_manager.create_note(
                title=self.i18n.t("workspace.new_note_default_title"),
                folder_id=folder_id,
            )
        except WorkspaceValidationError as exc:
            self._show_workspace_validation_error(exc)
            return
        self._pending_selection = ("item", item_id)
        self.library_changed.emit()

    def _open_item(self, item_id: str) -> None:
        current_item_id = self.current_item_id()
        self.select_item(item_id)
        if current_item_id == item_id:
            self.item_selected.emit(item_id)

    def _copy_local_path(self, path: str) -> None:
        QApplication.clipboard().setText(path)
        self.show_info(self.i18n.t("common.success"), self.i18n.t("common.copied"))

    def _open_local_path(self, path: Path, *, open_parent: bool = False) -> None:
        target_path = path.expanduser()
        if open_parent and target_path.is_file():
            target_path = target_path.parent
        if sys.platform == "darwin":
            subprocess.run(["open", str(target_path)], check=False)
        elif sys.platform.startswith("win"):
            os.startfile(str(target_path))  # type: ignore[attr-defined]
        else:
            subprocess.run(["xdg-open", str(target_path)], check=False)

    def _on_create_folder(self) -> None:
        if self.current_view_mode() != "structure":
            return
        name, accepted = QInputDialog.getText(
            self,
            self.i18n.t("workspace.library_title"),
            self.i18n.t("common.new"),
        )
        name = name.strip()
        if not accepted or not name:
            return
        try:
            self.workspace_manager.create_folder(name, parent_id=self.current_folder_id())
        except WorkspaceValidationError as exc:
            self._show_workspace_validation_error(exc)
            return
        self.library_changed.emit()

    def _on_rename_selection(self) -> None:
        if self.current_view_mode() != "structure":
            return
        selected_kind, selected_value = self._current_selection_identity()
        if selected_kind == "folder" and self._can_manage_folder(selected_value):
            folder = self.workspace_manager.get_folder(selected_value)
            if folder is None:
                return
            current_name = folder.name
        elif selected_kind == "item":
            item = self.workspace_manager.get_item(selected_value)
            if item is None:
                return
            current_name = item.title or item.id
        else:
            return
        name, accepted = QInputDialog.getText(
            self,
            self.i18n.t("workspace.library_title"),
            self.i18n.t("common.rename"),
            text=current_name,
        )
        name = name.strip()
        if not accepted or not name:
            return
        try:
            if selected_kind == "folder":
                self.workspace_manager.rename_folder(selected_value, name)
                self._pending_selection = ("folder", selected_value)
            else:
                self.workspace_manager.rename_item(selected_value, name)
                self._pending_selection = ("item", selected_value)
        except WorkspaceValidationError as exc:
            self._show_workspace_validation_error(exc)
            return
        self.library_changed.emit()

    def _on_delete_selection(self) -> None:
        if self.current_view_mode() != "structure":
            return
        selected_kind, selected_value = self._current_selection_identity()
        if selected_kind == "folder" and self._can_manage_folder(selected_value):
            folder = self.workspace_manager.get_folder(selected_value)
            if folder is None:
                return
            if not self.show_question(
                self.i18n.t("common.warning"),
                self.i18n.t("workspace.delete_folder_confirm", name=folder.name),
            ):
                return
            try:
                self.workspace_manager.delete_folder(selected_value)
            except WorkspaceValidationError as exc:
                self._show_workspace_validation_error(exc)
                return
            self.library_changed.emit()
            return
        if selected_kind == "folder" and self._can_delete_generated_folder(selected_value):
            folder = self.workspace_manager.get_folder(selected_value)
            if folder is None:
                return
            summary = self.workspace_manager.get_folder_cleanup_summary(selected_value)
            if not self.show_question(
                self.i18n.t("common.warning"),
                self.i18n.t(
                    "workspace.delete_generated_folder_confirm",
                    name=folder.name,
                    count=summary.get("linked_item_count", 0),
                ),
            ):
                return
            try:
                self.workspace_manager.delete_generated_folder(selected_value)
            except WorkspaceValidationError as exc:
                self._show_workspace_validation_error(exc)
                return
            self.library_changed.emit()
            return
        if selected_kind == "item":
            item = self.workspace_manager.get_item(selected_value)
            if item is None:
                return
            if not self.show_question(
                self.i18n.t("common.warning"),
                self.i18n.t("workspace.delete_item_confirm", name=item.title or item.id),
            ):
                return
            if not self.workspace_manager.delete_item(selected_value):
                self.show_warning(
                    self.i18n.t("common.warning"),
                    self.i18n.t("workspace.delete_item_failed"),
                )
                return
            self.library_changed.emit()
            return

    def _can_manage_folder(self, folder_id: str | None) -> bool:
        if not folder_id:
            return False
        folder = self.workspace_manager.get_folder(folder_id)
        return bool(folder is not None and getattr(folder, "folder_kind", "") == "user")

    def _update_header_action_states(self) -> None:
        selected_kind, selected_value = self._current_selection_identity()
        can_manage_folder = selected_kind == "folder" and self._can_manage_folder(selected_value)
        can_delete_generated_folder = selected_kind == "folder" and self._can_delete_generated_folder(
            selected_value
        )
        can_manage_item = selected_kind == "item" and self.workspace_manager.get_item(selected_value) is not None
        self.rename_folder_button.setEnabled(can_manage_folder or can_manage_item)
        self.delete_folder_button.setEnabled(
            can_manage_folder or can_delete_generated_folder or can_manage_item
        )

    def _current_selection_identity(self) -> tuple[str, str]:
        return self.current_selection_kind(), self.current_selection_value()

    def _show_workspace_validation_error(self, error: WorkspaceValidationError) -> None:
        if error.code == "duplicate_name":
            message = self.i18n.t("workspace.duplicate_name")
        elif error.code == "invalid_move_target":
            message = self.i18n.t("workspace.invalid_move_target")
        elif error.code == "folder_not_empty":
            message = self.i18n.t("workspace.delete_folder_failed")
        elif error.code == "folder_not_renamable":
            message = self.i18n.t("workspace.rename_folder_failed")
        elif error.code == "folder_not_deletable":
            message = self.i18n.t("workspace.delete_folder_failed")
        else:
            message = self.i18n.t("workspace.invalid_name")
        self.show_warning(self.i18n.t("common.warning"), message)

    def _confirm_system_item_transfer(self) -> str:
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Icon.Question)
        msg_box.setWindowTitle(self.i18n.t("common.confirm"))
        msg_box.setText(self.i18n.t("workspace.drag_from_system_prompt"))
        copy_btn = msg_box.addButton(
            self.i18n.t("workspace.action_copy"),
            QMessageBox.ButtonRole.AcceptRole,
        )
        move_btn = msg_box.addButton(
            self.i18n.t("workspace.action_move"),
            QMessageBox.ButtonRole.DestructiveRole,
        )
        cancel_btn = msg_box.addButton(
            self.i18n.t("common.cancel"),
            QMessageBox.ButtonRole.RejectRole,
        )
        msg_box.exec()
        clicked_btn = msg_box.clickedButton()
        if clicked_btn == copy_btn:
            return "copy"
        if clicked_btn == move_btn:
            return "move"
        if clicked_btn == cancel_btn:
            return "cancel"
        return "cancel"

    def _handle_workspace_item_transfer(
        self,
        item_id: str,
        target_folder_id: str,
        *,
        source_domain: str | None = None,
    ) -> None:
        item = self.workspace_manager.get_item(item_id)
        if item is None or item.folder_id == target_folder_id:
            return
        target_folder = self.workspace_manager.get_folder(target_folder_id)
        if target_folder is None:
            return

        resolved_source_domain = source_domain or ""
        if not resolved_source_domain:
            source_folder = self.workspace_manager.get_folder(item.folder_id)
            resolved_source_domain = getattr(source_folder, "folder_kind", "") if source_folder is not None else ""

        if resolved_source_domain in {WORKSPACE_DRAG_SOURCE_EVENT, WORKSPACE_DRAG_SOURCE_BATCH_TASK}:
            if not self.workspace_manager.item_has_text_content(item_id):
                self.show_warning(
                    self.i18n.t("common.warning"),
                    self.i18n.t("workspace.drag_text_only_warning"),
                )
                return
            transfer_mode = self._confirm_system_item_transfer()
            if transfer_mode == "cancel":
                return
            if transfer_mode == "copy":
                try:
                    suffix = self.i18n.t("workspace.copy_suffix")
                    new_item = self.workspace_manager.copy_item_to_folder(
                        item_id,
                        target_folder_id,
                        copy_suffix=suffix,
                    )
                    self._pending_selection = ("item", new_item.id)
                    self.library_changed.emit()
                    return
                except WorkspaceValidationError as exc:
                    self._show_workspace_validation_error(exc)
                    return
                except Exception as exc:  # noqa: BLE001
                    self.show_warning(self.i18n.t("common.warning"), str(exc))
                    return

        try:
            self.workspace_manager.move_item_to_folder(item_id, target_folder_id)
        except WorkspaceValidationError as exc:
            self._show_workspace_validation_error(exc)
            return
        self._pending_selection = ("item", item_id)
        self.library_changed.emit()

    def _on_tree_drop_requested(
        self,
        source_kind: str,
        source_value: str,
        target_kind: str,
        target_value: str,
    ) -> None:
        if self.current_view_mode() != "structure":
            return
        if source_kind == "item":
            target_folder_id = self._resolve_item_drop_target_folder_id(target_kind, target_value)
            if target_folder_id is None:
                return
            self._handle_workspace_item_transfer(source_value, target_folder_id)
            return

        if source_kind == "folder":
            if not self._can_manage_folder(source_value):
                return
            target_parent_id = self._resolve_folder_drop_target_parent_id(target_kind, target_value)
            folder = self.workspace_manager.get_folder(source_value)
            if folder is None or target_parent_id is None or folder.parent_id == target_parent_id:
                return
            try:
                self.workspace_manager.move_folder(source_value, target_parent_id)
            except ValueError:
                return
            self._pending_selection = ("folder", source_value)
            self.library_changed.emit()

    def _on_external_workspace_drop_requested(
        self,
        payload: dict,
        target_kind: str,
        target_value: str,
    ) -> None:
        if self.current_view_mode() != "structure":
            return
        target_folder_id = self._resolve_item_drop_target_folder_id(target_kind, target_value)
        if target_folder_id is None:
            return
        item_id = str(payload.get("workspace_item_id") or "")
        source_domain = str(payload.get("source_domain") or "")
        if not item_id or source_domain not in {
            WORKSPACE_DRAG_SOURCE_EVENT,
            WORKSPACE_DRAG_SOURCE_BATCH_TASK,
        }:
            return
        self._handle_workspace_item_transfer(
            item_id,
            target_folder_id,
            source_domain=source_domain,
        )

    def _resolve_item_drop_target_folder_id(self, target_kind: str, target_value: str) -> str | None:
        if target_kind == "folder":
            target_folder = self.workspace_manager.get_folder(target_value)
            return target_folder.id if target_folder is not None else None
        elif target_kind == "item":
            target_item = self.workspace_manager.get_item(target_value)
            return target_item.folder_id if target_item is not None else None
        return None

    def _can_delete_generated_folder(self, folder_id: str | None) -> bool:
        if not folder_id:
            return False
        folder = self.workspace_manager.get_folder(folder_id)
        return bool(folder is not None and getattr(folder, "folder_kind", "") == "event")

    def _resolve_folder_drop_target_parent_id(self, target_kind: str, target_value: str) -> str | None:
        if target_kind != "folder":
            return None
        target_folder = self.workspace_manager.get_folder(target_value)
        if target_folder is None:
            return None
        target_kind_name = getattr(target_folder, "folder_kind", "")
        if target_kind_name in {"user", "inbox"}:
            return target_folder.id
        return None

    @staticmethod
    def _folder_sort_key(folder) -> tuple:
        parent_id = folder.parent_id or ""
        if folder.parent_id is None:
            return (
                parent_id,
                WorkspaceLibraryPanel._top_level_folder_rank(folder),
                folder.name.lower(),
                folder.created_at,
            )
        return (
            parent_id,
            folder.name.lower(),
            folder.created_at,
        )

    @staticmethod
    def _top_level_folder_rank(folder) -> int:
        folder_kind = getattr(folder, "folder_kind", "") or ""
        if folder_kind == "inbox":
            return 0
        if folder_kind == "user":
            return 1
        if folder_kind == "system_root":
            return 8
        if folder_kind == "batch_task":
            return 9
        return 5

    @staticmethod
    def _folder_icon_name(folder) -> str:
        folder_kind = getattr(folder, "folder_kind", "") or ""
        if folder_kind == "inbox":
            return "folder_inbox"
        if folder_kind == "system_root":
            return "folder_event_root"
        if folder_kind == "batch_task":
            return "folder_batch_root"
        if folder_kind == "event":
            return "folder_event"
        return "folder"

    def _build_tree_icon(self, icon_name: str) -> QIcon:
        color = self.palette().color(QPalette.ColorRole.ButtonText).name()
        svg_markup = self._tree_icon_svg(icon_name, color)
        pixmap = QPixmap()
        if not pixmap.loadFromData(svg_markup.encode("utf-8"), "SVG"):
            return QIcon()
        return QIcon(pixmap)

    @staticmethod
    def _tree_icon_svg(icon_name: str, color: str) -> str:
        icons = {
            "folder": f"""
                <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 14 14" fill="none">
                  <path d="M1.75 4.25C1.75 3.83579 2.08579 3.5 2.5 3.5H4.7L5.6 4.4H11.5C11.9142 4.4 12.25 4.73579 12.25 5.15V10.75C12.25 11.1642 11.9142 11.5 11.5 11.5H2.5C2.08579 11.5 1.75 11.1642 1.75 10.75V4.25Z" stroke="{color}" stroke-width="1.2" stroke-linejoin="round"/>
                </svg>
            """,
            "folder_inbox": f"""
                <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 14 14" fill="none">
                  <path d="M2 3.25H12V8.25L10.75 10.75H3.25L2 8.25V3.25Z" stroke="{color}" stroke-width="1.2" stroke-linejoin="round"/>
                  <path d="M4 8.25H10" stroke="{color}" stroke-width="1.2" stroke-linecap="round"/>
                </svg>
            """,
            "folder_event_root": f"""
                <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 14 14" fill="none">
                  <rect x="2" y="3" width="10" height="8.5" rx="1.25" stroke="{color}" stroke-width="1.2"/>
                  <path d="M4.5 2V4.2" stroke="{color}" stroke-width="1.2" stroke-linecap="round"/>
                  <path d="M9.5 2V4.2" stroke="{color}" stroke-width="1.2" stroke-linecap="round"/>
                  <path d="M2 5.3H12" stroke="{color}" stroke-width="1.2"/>
                </svg>
            """,
            "folder_batch_root": f"""
                <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 14 14" fill="none">
                  <rect x="2" y="2.5" width="10" height="3" rx="1" stroke="{color}" stroke-width="1.2"/>
                  <rect x="2" y="5.5" width="10" height="3" rx="1" stroke="{color}" stroke-width="1.2"/>
                  <rect x="2" y="8.5" width="10" height="3" rx="1" stroke="{color}" stroke-width="1.2"/>
                </svg>
            """,
            "folder_event": f"""
                <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 14 14" fill="none">
                  <rect x="2" y="3" width="10" height="8.5" rx="1.25" stroke="{color}" stroke-width="1.2"/>
                  <path d="M2 5.3H12" stroke="{color}" stroke-width="1.2"/>
                </svg>
            """,
            "event_group": f"""
                <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 14 14" fill="none">
                  <rect x="2" y="2.5" width="10" height="9" rx="1.25" stroke="{color}" stroke-width="1.2"/>
                  <path d="M4.25 1.75V3.75" stroke="{color}" stroke-width="1.2" stroke-linecap="round"/>
                  <path d="M9.75 1.75V3.75" stroke="{color}" stroke-width="1.2" stroke-linecap="round"/>
                  <path d="M2 5H12" stroke="{color}" stroke-width="1.2"/>
                </svg>
            """,
            "item": f"""
                <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 14 14" fill="none">
                  <path d="M4 2.5H8.4L10.5 4.6V11C10.5 11.2761 10.2761 11.5 10 11.5H4C3.72386 11.5 3.5 11.2761 3.5 11V3C3.5 2.72386 3.72386 2.5 4 2.5Z" stroke="{color}" stroke-width="1.2" stroke-linejoin="round"/>
                  <path d="M8 2.5V5H10.5" stroke="{color}" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
            """,
        }
        return icons[icon_name]

    def _update_context_label(self) -> None:
        mode_key = (
            "workspace.structure_view"
            if self.current_view_mode() == "structure"
            else "workspace.event_view"
        )
        context_parts = [self.i18n.t(mode_key)]
        current_item = self.folder_tree.currentItem()
        if current_item is not None:
            label = current_item.data(0, _TREE_LABEL_ROLE)
            if label:
                context_parts.append(str(label))
        self.context_label.setText(" / ".join(context_parts))
