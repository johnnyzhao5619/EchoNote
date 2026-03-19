# SPDX-License-Identifier: Apache-2.0
"""Detached window for a single workspace document."""

from __future__ import annotations

from core.qt_imports import QPalette, QSplitter, QSize, QToolButton, QVBoxLayout, QWidget, Qt
from ui.common.svg_icons import build_svg_icon
from ui.constants import ROLE_WORKSPACE_TAB_ACTION, WORKSPACE_CONTENT_SPLITTER_DEFAULT_SIZES
from ui.workspace.editor_panel import WorkspaceEditorPanel
from ui.workspace.inspector_panel import WorkspaceInspectorPanel, set_trailing_splitter_panel_visible


class DetachedDocumentWindow(QWidget):
    """Show a single workspace document in an independent window."""

    def __init__(self, workspace_manager, i18n, item_id: str, asset_role: str | None = None, parent=None):
        super().__init__(parent, Qt.WindowType.Window)
        self.workspace_manager = workspace_manager
        self.i18n = i18n
        self.item_id = item_id
        self.editor_panel = WorkspaceEditorPanel(workspace_manager, i18n, parent=self)
        self.inspector_panel = WorkspaceInspectorPanel(workspace_manager, i18n, self)
        self._inspector_expanded_sizes = list(WORKSPACE_CONTENT_SPLITTER_DEFAULT_SIZES[1:])
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self._init_ui()
        self.editor_panel.item_renamed.connect(self._on_item_renamed)
        self.load_item(item_id, asset_role=asset_role)

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.inspector_toggle_button = QToolButton(self)
        self.inspector_toggle_button.setProperty("role", ROLE_WORKSPACE_TAB_ACTION)
        self.inspector_toggle_button.setAutoRaise(False)
        self.inspector_toggle_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.inspector_toggle_button.setIconSize(QSize(16, 16))
        self.inspector_toggle_button.clicked.connect(self._toggle_inspector_panel)
        self.editor_panel.insert_toolbar_widget(self.inspector_toggle_button)

        self.content_splitter = QSplitter(Qt.Orientation.Horizontal, self)
        self.content_splitter.addWidget(self.editor_panel)
        self.content_splitter.addWidget(self.inspector_panel)
        self.content_splitter.setStretchFactor(0, 3)
        self.content_splitter.setStretchFactor(1, 1)
        self.content_splitter.setSizes(list(self._inspector_expanded_sizes))
        layout.addWidget(self.content_splitter)
        self.resize(860, 720)
        self._update_inspector_toggle_button()

    def update_translations(self) -> None:
        self.editor_panel.update_translations()
        self.inspector_panel.update_translations()
        self._update_inspector_toggle_button()
        self._refresh_window_title()

    def load_item(self, item_id: str, asset_role: str | None = None) -> None:
        """Reload the target document and refresh the window title."""
        self.item_id = item_id
        item = self.workspace_manager.get_item(item_id)
        self.editor_panel.set_item(item)
        if asset_role:
            self.editor_panel.select_asset_role(asset_role)
        self.inspector_panel.set_item(item)
        self.inspector_panel.set_editor_panel(self.editor_panel)
        self._refresh_window_title()

    def _refresh_window_title(self) -> None:
        item = self.workspace_manager.get_item(self.item_id)
        title = item.title if item is not None else self.i18n.t("workspace.library_title")
        self.setWindowTitle(title)

    def _on_item_renamed(self, item_id: str) -> None:
        if item_id != self.item_id:
            return
        self._refresh_window_title()

    def _toggle_inspector_panel(self) -> None:
        self._set_inspector_visible(not self._is_inspector_panel_open())

    def _set_inspector_visible(self, visible: bool) -> None:
        self._inspector_expanded_sizes = set_trailing_splitter_panel_visible(
            self.content_splitter,
            self.inspector_panel,
            visible=visible,
            expanded_sizes=self._inspector_expanded_sizes,
            fallback_sizes=WORKSPACE_CONTENT_SPLITTER_DEFAULT_SIZES[1:],
        )
        self._update_inspector_toggle_button()

    def _is_inspector_panel_open(self) -> bool:
        return not self.inspector_panel.isHidden()

    def _update_inspector_toggle_button(self) -> None:
        text_key = (
            "workspace.hide_inspector_panel"
            if self._is_inspector_panel_open()
            else "workspace.show_inspector_panel"
        )
        text = self.i18n.t(text_key)
        self.inspector_toggle_button.setText("")
        self.inspector_toggle_button.setToolTip(text)
        self.inspector_toggle_button.setAccessibleName(text)
        self.inspector_toggle_button.setIcon(self._build_shell_icon("workspace_inspector"))

    def _build_shell_icon(self, icon_name: str):
        color = self.palette().color(QPalette.ColorRole.ButtonText).name()
        return build_svg_icon(icon_name, color)
