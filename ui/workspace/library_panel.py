# SPDX-License-Identifier: Apache-2.0
"""Workspace library shell panel."""

from __future__ import annotations

from core.qt_imports import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QInputDialog,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    Qt,
    Signal,
)
from ui.base_widgets import BaseWidget
from ui.constants import ROLE_WORKSPACE_LIBRARY_PANEL
from ui.workspace.item_list import WorkspaceItemList

_VIEW_MODES = (
    ("workspace.structure_view", "structure"),
    ("workspace.event_view", "event"),
)
_TREE_DATA_ROLE = Qt.ItemDataRole.UserRole


class WorkspaceLibraryPanel(BaseWidget):
    """Left-side workspace library surface with dual views and folder actions."""

    item_selected = Signal(str)
    view_mode_changed = Signal(str)
    library_changed = Signal()

    def __init__(self, workspace_manager, i18n, parent=None):
        super().__init__(i18n, parent)
        self.workspace_manager = workspace_manager
        self.item_list = WorkspaceItemList(i18n, self)
        self._folder_items: dict[str, QTreeWidgetItem] = {}
        self._root_item: QTreeWidgetItem | None = None
        self._init_ui()
        self.refresh_folders()

    def _init_ui(self) -> None:
        self.setProperty("role", ROLE_WORKSPACE_LIBRARY_PANEL)
        layout = QVBoxLayout(self)

        self.title_label = QLabel(self.i18n.t("workspace.library_title"))
        layout.addWidget(self.title_label)

        self.view_mode_combo = QComboBox(self)
        for label_key, mode in _VIEW_MODES:
            self.view_mode_combo.addItem(self.i18n.t(label_key), mode)
        self.view_mode_combo.currentIndexChanged.connect(self._on_view_mode_changed)
        layout.addWidget(self.view_mode_combo)

        folder_actions = QHBoxLayout()
        self.new_folder_button = QPushButton(self)
        self.new_folder_button.clicked.connect(self._on_create_folder)
        folder_actions.addWidget(self.new_folder_button)

        self.rename_folder_button = QPushButton(self)
        self.rename_folder_button.clicked.connect(self._on_rename_folder)
        folder_actions.addWidget(self.rename_folder_button)

        self.delete_folder_button = QPushButton(self)
        self.delete_folder_button.clicked.connect(self._on_delete_folder)
        folder_actions.addWidget(self.delete_folder_button)

        self.move_to_folder_button = QPushButton(self)
        self.move_to_folder_button.clicked.connect(self._on_move_selected_item)
        folder_actions.addWidget(self.move_to_folder_button)

        layout.addLayout(folder_actions)

        self.folder_tree = QTreeWidget(self)
        self.folder_tree.setHeaderHidden(True)
        self.folder_tree.itemSelectionChanged.connect(self._on_folder_selection_changed)
        layout.addWidget(self.folder_tree)

        layout.addWidget(self.item_list, 1)

        self.item_list.item_selected.connect(self.item_selected.emit)
        self.item_list.set_view_mode(self.current_view_mode())
        self._sync_structure_controls()
        self.update_translations()

    def update_translations(self) -> None:
        self.title_label.setText(self.i18n.t("workspace.library_title"))
        current_mode = self.current_view_mode()
        self.view_mode_combo.blockSignals(True)
        self.view_mode_combo.clear()
        for label_key, mode in _VIEW_MODES:
            self.view_mode_combo.addItem(self.i18n.t(label_key), mode)
        index = self.view_mode_combo.findData(current_mode)
        if index >= 0:
            self.view_mode_combo.setCurrentIndex(index)
        self.view_mode_combo.blockSignals(False)

        self.new_folder_button.setText(self.i18n.t("common.new"))
        self.rename_folder_button.setText(self.i18n.t("common.rename"))
        self.delete_folder_button.setText(self.i18n.t("common.delete"))
        self.move_to_folder_button.setText(self.i18n.t("common.move"))
        self._update_root_item_label()

    def refresh_folders(self) -> None:
        """Rebuild the folder tree from the current workspace structure."""
        selected_folder_id = self.current_folder_id()
        folders = self.workspace_manager.list_folders()
        self._folder_items.clear()

        self.folder_tree.blockSignals(True)
        self.folder_tree.clear()

        self._root_item = QTreeWidgetItem([self.i18n.t("workspace.library_title")])
        self._root_item.setData(0, _TREE_DATA_ROLE, None)
        self.folder_tree.addTopLevelItem(self._root_item)

        for folder in folders:
            item = QTreeWidgetItem([folder.name])
            item.setData(0, _TREE_DATA_ROLE, folder.id)
            self._folder_items[folder.id] = item

        for folder in folders:
            item = self._folder_items[folder.id]
            parent_item = self._folder_items.get(folder.parent_id, self._root_item)
            parent_item.addChild(item)

        self._root_item.setExpanded(True)
        for item in self._folder_items.values():
            item.setExpanded(True)

        self.folder_tree.blockSignals(False)
        self.select_folder(selected_folder_id)

    def set_items(self, items, *, metadata_by_item=None) -> None:
        self.item_list.set_view_mode(self.current_view_mode())
        self.item_list.set_items(items, metadata_by_item=metadata_by_item)

    def select_item(self, item_id: str) -> None:
        self.item_list.select_item(item_id)

    def current_item_id(self) -> str:
        return self.item_list.current_item_id()

    def current_view_mode(self) -> str:
        return self.view_mode_combo.currentData() or "structure"

    def set_view_mode(self, view_mode: str) -> None:
        index = self.view_mode_combo.findData(view_mode)
        if index >= 0:
            self.view_mode_combo.setCurrentIndex(index)

    def current_folder_id(self) -> str | None:
        current_item = self.folder_tree.currentItem()
        if current_item is None:
            return None
        return current_item.data(0, _TREE_DATA_ROLE)

    def select_folder(self, folder_id: str | None) -> None:
        target_item = self._root_item if folder_id is None else self._folder_items.get(folder_id)
        if target_item is None:
            target_item = self._root_item
        if target_item is not None:
            self.folder_tree.setCurrentItem(target_item)

    def _on_view_mode_changed(self, _index: int) -> None:
        self.item_list.set_view_mode(self.current_view_mode())
        self._sync_structure_controls()
        self.view_mode_changed.emit(self.current_view_mode())
        self.library_changed.emit()

    def _on_folder_selection_changed(self) -> None:
        if self.current_view_mode() == "structure":
            self.library_changed.emit()

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
        self.workspace_manager.create_folder(name, parent_id=self.current_folder_id())
        self.refresh_folders()
        self.library_changed.emit()

    def _on_rename_folder(self) -> None:
        folder_id = self.current_folder_id()
        if self.current_view_mode() != "structure" or not folder_id:
            return
        folder = self.workspace_manager.get_folder(folder_id)
        if folder is None:
            return
        name, accepted = QInputDialog.getText(
            self,
            self.i18n.t("workspace.library_title"),
            self.i18n.t("common.rename"),
            text=folder.name,
        )
        name = name.strip()
        if not accepted or not name:
            return
        self.workspace_manager.rename_folder(folder_id, name)
        self.refresh_folders()
        self.select_folder(folder_id)
        self.library_changed.emit()

    def _on_delete_folder(self) -> None:
        folder_id = self.current_folder_id()
        if self.current_view_mode() != "structure" or not folder_id:
            return
        if not self.workspace_manager.delete_folder(folder_id):
            self.show_warning(
                self.i18n.t("common.warning"),
                self.i18n.t("workspace.delete_failed"),
            )
            return
        self.refresh_folders()
        self.library_changed.emit()

    def _on_move_selected_item(self) -> None:
        if self.current_view_mode() != "structure":
            return
        item_id = self.current_item_id()
        if not item_id:
            return
        self.workspace_manager.move_item_to_folder(item_id, self.current_folder_id())
        self.library_changed.emit()

    def _sync_structure_controls(self) -> None:
        structure_visible = self.current_view_mode() == "structure"
        self.folder_tree.setVisible(structure_visible)
        self.new_folder_button.setVisible(structure_visible)
        self.rename_folder_button.setVisible(structure_visible)
        self.delete_folder_button.setVisible(structure_visible)
        self.move_to_folder_button.setVisible(structure_visible)

    def _update_root_item_label(self) -> None:
        if self._root_item is not None:
            self._root_item.setText(0, self.i18n.t("workspace.library_title"))
