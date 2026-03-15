# SPDX-License-Identifier: Apache-2.0
"""Reusable text editor panels for workspace assets and transcript viewers."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Optional

from core.qt_imports import (
    QAction,
    QApplication,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QTimer,
    QVBoxLayout,
    QWidget,
    Signal,
)

from ui.base_widgets import BaseWidget, connect_button_with_callback, create_hbox
from ui.batch_transcribe.search_widget import SearchWidget
from ui.common.style_utils import set_widget_state
from ui.constants import (
    ROLE_TOOLBAR_SECONDARY_ACTION,
    ROLE_WORKSPACE_AI_ACTION,
    ROLE_WORKSPACE_ASSET_SELECTOR,
    ROLE_WORKSPACE_EDITOR_PANEL,
)
from utils.i18n import I18nQtManager

logger = logging.getLogger("echonote.ui.workspace.editor_panel")

BATCH_VIEWER_ROLE_TOOLBAR = "batch-viewer-toolbar"
BATCH_VIEWER_ROLE_EDIT = "batch-viewer-edit-action"
BATCH_VIEWER_ROLE_EXPORT = "batch-viewer-export-action"
BATCH_VIEWER_ROLE_COPY = "batch-viewer-copy-action"
BATCH_VIEWER_ROLE_SEARCH = "batch-viewer-search-action"

EDITOR_ROLE_TOOLBAR = BATCH_VIEWER_ROLE_TOOLBAR
EDITOR_ROLE_EDIT = BATCH_VIEWER_ROLE_EDIT
EDITOR_ROLE_EXPORT = BATCH_VIEWER_ROLE_EXPORT
EDITOR_ROLE_COPY = BATCH_VIEWER_ROLE_COPY
EDITOR_ROLE_SEARCH = BATCH_VIEWER_ROLE_SEARCH


@dataclass(frozen=True)
class EditorRoleSet:
    toolbar: str
    edit: str
    export: str
    copy: str
    search: str


BATCH_VIEWER_ROLE_SET = EditorRoleSet(
    toolbar=BATCH_VIEWER_ROLE_TOOLBAR,
    edit=BATCH_VIEWER_ROLE_EDIT,
    export=BATCH_VIEWER_ROLE_EXPORT,
    copy=BATCH_VIEWER_ROLE_COPY,
    search=BATCH_VIEWER_ROLE_SEARCH,
)

WORKSPACE_EDITOR_ROLE_SET = EditorRoleSet(
    toolbar=ROLE_WORKSPACE_EDITOR_PANEL,
    edit=ROLE_TOOLBAR_SECONDARY_ACTION,
    export=ROLE_TOOLBAR_SECONDARY_ACTION,
    copy=ROLE_TOOLBAR_SECONDARY_ACTION,
    search=ROLE_TOOLBAR_SECONDARY_ACTION,
)

WORKSPACE_ASSET_LABELS = {
    "document_text": "Document",
    "transcript": "Transcript",
    "translation": "Translation",
    "summary": "Summary",
    "meeting_brief": "Meeting Brief",
    "decisions": "Decisions",
    "action_items": "Action Items",
    "next_steps": "Next Steps",
    "outline": "Outline",
    "source_document": "Source Document",
}

WORKSPACE_ASSET_ORDER = {
    "document_text": 0,
    "transcript": 1,
    "translation": 2,
    "summary": 3,
    "meeting_brief": 4,
    "decisions": 5,
    "action_items": 6,
    "next_steps": 7,
    "outline": 8,
    "source_document": 9,
}


class TextEditorPanel(BaseWidget):
    """Shared text editor with search, edit, save, copy, and export actions."""

    content_saved = Signal()

    def __init__(
        self,
        i18n: I18nQtManager,
        *,
        settings_manager=None,
        save_handler: Optional[Callable[[str], None]] = None,
        export_handler: Optional[Callable[[str, str, str], None]] = None,
        export_formats: Iterable[str] = ("txt", "md"),
        save_success_key: str = "viewer.save_success",
        export_dialog_title_key: str = "viewer.export_dialog_title",
        export_success_key: str = "workspace.export_success",
        export_error_title_key: str = "viewer.export_error",
        search_button_key: str = "viewer.search",
        role_set: EditorRoleSet = BATCH_VIEWER_ROLE_SET,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(i18n, parent)
        self.settings_manager = settings_manager
        self.save_handler = save_handler
        self.export_handler = export_handler
        self.export_formats = tuple(export_formats)
        self.save_success_key = save_success_key
        self.export_dialog_title_key = export_dialog_title_key
        self.export_success_key = export_success_key
        self.export_error_title_key = export_error_title_key
        self.search_button_key = search_button_key
        self.role_set = role_set
        self.current_display_name = "document"
        self.current_file_path = ""
        self.is_modified = False
        self.is_edit_mode = False

        self._init_ui()
        self.update_translations()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)

        self.toolbar_frame = QFrame()
        self.toolbar_frame.setProperty("role", self.role_set.toolbar)
        self.toolbar_frame.setFrameShape(QFrame.Shape.NoFrame)
        self.toolbar_layout = QHBoxLayout(self.toolbar_frame)

        self.edit_button = QPushButton()
        self.edit_button.setProperty("role", self.role_set.edit)
        connect_button_with_callback(self.edit_button, self.toggle_edit_mode)
        self.toolbar_layout.addWidget(self.edit_button)

        self.export_button = QPushButton()
        self.export_button.setProperty("role", self.role_set.export)
        self._create_export_menu()
        self.toolbar_layout.addWidget(self.export_button)

        self.copy_button = QPushButton()
        self.copy_button.setProperty("role", self.role_set.copy)
        connect_button_with_callback(self.copy_button, self.copy_all)
        self.toolbar_layout.addWidget(self.copy_button)

        self.search_button = QPushButton()
        self.search_button.setProperty("role", self.role_set.search)
        connect_button_with_callback(self.search_button, self.toggle_search)
        self.toolbar_layout.addWidget(self.search_button)

        self.toolbar_layout.addStretch()
        layout.addWidget(self.toolbar_frame)

        self.search_widget = SearchWidget(None, self.i18n, self.settings_manager, self)
        layout.addWidget(self.search_widget)

        self.text_edit = QTextEdit()
        self.text_edit.setObjectName("transcript_text_edit")
        self.text_edit.setReadOnly(True)
        self.text_edit.textChanged.connect(self._on_text_changed)
        self._optimize_text_edit()
        layout.addWidget(self.text_edit, 1)

        self.search_widget.text_edit = self.text_edit
        self._set_edit_button_active_state(False)

    def insert_toolbar_widget(self, widget: QWidget) -> None:
        """Insert an extra widget before the toolbar stretch."""
        self.toolbar_layout.insertWidget(max(0, self.toolbar_layout.count() - 1), widget)

    def set_document_context(
        self,
        *,
        display_name: str,
        file_path: Optional[str] = None,
        save_handler: Optional[Callable[[str], None]] = None,
        export_handler: Optional[Callable[[str, str, str], None]] = None,
        export_formats: Optional[Iterable[str]] = None,
    ) -> None:
        """Update callbacks and file metadata for the current document."""
        self.current_display_name = display_name or "document"
        self.current_file_path = file_path or ""
        if save_handler is not None:
            self.save_handler = save_handler
        if export_handler is not None:
            self.export_handler = export_handler
        if export_formats is not None:
            self.export_formats = tuple(export_formats)
            self._create_export_menu()

    def set_text_content(self, content: str) -> None:
        """Replace text content without marking the editor dirty."""
        self.text_edit.setUpdatesEnabled(False)
        undo_enabled = self.text_edit.isUndoRedoEnabled()
        self.text_edit.setUndoRedoEnabled(False)
        try:
            self.text_edit.setPlainText(content)
            cursor = self.text_edit.textCursor()
            cursor.movePosition(cursor.MoveOperation.Start)
            self.text_edit.setTextCursor(cursor)
        finally:
            self.text_edit.setUndoRedoEnabled(undo_enabled)
            self.text_edit.setUpdatesEnabled(True)
            self.text_edit.document().clearUndoRedoStacks()
        self.is_modified = False

    def toggle_edit_mode(self) -> None:
        """Toggle between read-only and editable mode."""
        if self.is_edit_mode:
            self.save_changes()
            return

        self.is_edit_mode = True
        self.text_edit.setReadOnly(False)
        self.text_edit.document().clearUndoRedoStacks()
        self._set_edit_button_active_state(True)
        self.update_translations()

    def save_changes(self) -> None:
        """Persist current content via callback or direct file write."""
        if not self.is_modified:
            self._leave_edit_mode()
            return

        content = self.text_edit.toPlainText()
        try:
            if callable(self.save_handler):
                self.save_handler(content)
            elif self.current_file_path:
                target_path = Path(self.current_file_path).expanduser()
                target_path.parent.mkdir(parents=True, exist_ok=True)
                target_path.write_text(content, encoding="utf-8")
            else:
                raise ValueError("Text editor is missing a save target")

            self.is_modified = False
            self._leave_edit_mode()
            self.show_info(self.i18n.t("common.success"), self.i18n.t(self.save_success_key))
            self.content_saved.emit()
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to save editor content: %s", exc, exc_info=True)
            self._show_save_error_with_retry(
                self.i18n.t("viewer.save_error_details", error=str(exc)),
                str(exc),
            )

    def toggle_search(self) -> None:
        """Toggle the shared search widget visibility."""
        if self.search_widget.isVisible():
            self.search_widget.hide_search()
        else:
            self.search_widget.show_search()

    def copy_all(self) -> None:
        """Copy the full text content to clipboard."""
        clipboard = QApplication.clipboard()
        clipboard.setText(self.text_edit.toPlainText())
        original_text = self.copy_button.text()
        self.copy_button.setText(self.i18n.t("common.copied"))
        self.copy_button.setEnabled(False)
        QTimer.singleShot(2000, lambda: self._reset_copy_button(original_text))

    def export_as(self, format_name: str) -> None:
        """Export current text content to the target format."""
        default_name = f"{Path(self.current_display_name).stem or 'document'}.{format_name}"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            self.i18n.t(self.export_dialog_title_key),
            default_name,
            f"{format_name.upper()} (*.{format_name})",
        )
        if not file_path:
            return

        try:
            text_content = self.text_edit.toPlainText()
            if callable(self.export_handler):
                self.export_handler(format_name, file_path, text_content)
            else:
                Path(file_path).write_text(text_content, encoding="utf-8")
            self.show_info(
                self.i18n.t("common.success"),
                self.i18n.t(self.export_success_key, path=file_path),
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to export editor content: %s", exc, exc_info=True)
            self.show_error(self.i18n.t(self.export_error_title_key), str(exc))

    def update_translations(self) -> None:
        self.edit_button.setText(
            self.i18n.t("common.save") if self.is_edit_mode else self.i18n.t("common.edit")
        )
        self.copy_button.setText(self.i18n.t("viewer.copy_all"))
        self.export_button.setText(self.i18n.t("viewer.export"))
        self.search_button.setText(self.i18n.t(self.search_button_key))

        if getattr(self, "export_txt_action", None):
            self.export_txt_action.setText(self.i18n.t("viewer.export_txt"))
        if getattr(self, "export_srt_action", None):
            self.export_srt_action.setText(self.i18n.t("viewer.export_srt"))
        if getattr(self, "export_md_action", None):
            self.export_md_action.setText(self.i18n.t("viewer.export_md"))

    def _on_text_changed(self) -> None:
        if self.is_edit_mode:
            self.is_modified = True

    def _leave_edit_mode(self) -> None:
        self.is_edit_mode = False
        self.text_edit.setReadOnly(True)
        self._set_edit_button_active_state(False)
        self.update_translations()

    def _set_edit_button_active_state(self, is_active: bool) -> None:
        set_widget_state(self.edit_button, "active" if is_active else "default")

    def _create_export_menu(self) -> None:
        export_menu = QMenu(self)
        self.export_txt_action = None
        self.export_srt_action = None
        self.export_md_action = None
        for format_name in self.export_formats:
            action = QAction(self.i18n.t(f"viewer.export_{format_name}"), self)
            action.triggered.connect(
                lambda _checked=False, selected_format=format_name: self.export_as(selected_format)
            )
            export_menu.addAction(action)
            setattr(self, f"export_{format_name}_action", action)
        self.export_button.setMenu(export_menu)

    def _optimize_text_edit(self) -> None:
        self.text_edit.document().setMaximumBlockCount(0)
        self.text_edit.setUndoRedoEnabled(True)
        self.text_edit.setTabStopDistance(40)
        self.text_edit.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.text_edit.setAcceptRichText(False)

    def _show_save_error_with_retry(self, error_msg: str, details: str) -> None:
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Icon.Critical)
        msg_box.setWindowTitle(self.i18n.t("common.error"))
        msg_box.setText(error_msg)
        msg_box.setDetailedText(details)
        retry_button = msg_box.addButton(
            self.i18n.t("viewer.save_retry"),
            QMessageBox.ButtonRole.AcceptRole,
        )
        msg_box.addButton(self.i18n.t("common.cancel"), QMessageBox.ButtonRole.RejectRole)
        msg_box.exec()
        if msg_box.clickedButton() == retry_button:
            self.save_changes()

    def _reset_copy_button(self, text: str) -> None:
        try:
            self.copy_button.setText(text)
            self.copy_button.setEnabled(True)
        except RuntimeError:
            return


class WorkspaceEditorPanel(TextEditorPanel):
    """Workspace-specific editor with asset switching and AI actions."""

    def __init__(self, workspace_manager, i18n: I18nQtManager, *, parent: Optional[QWidget] = None):
        self.workspace_manager = workspace_manager
        self.current_item = None
        self.current_asset = None
        self._text_assets = []
        super().__init__(
            i18n,
            settings_manager=getattr(workspace_manager, "settings_manager", None),
            save_success_key="workspace.save_success",
            export_dialog_title_key="workspace.export_dialog_title",
            export_success_key="workspace.export_success",
            export_error_title_key="workspace.export_failed_title",
            search_button_key="transcript.search",
            role_set=WORKSPACE_EDITOR_ROLE_SET,
            parent=parent,
        )
        self._init_workspace_controls()

    def _init_workspace_controls(self) -> None:
        self.setProperty("role", ROLE_WORKSPACE_EDITOR_PANEL)
        self.document_title_label = QLabel()
        self.layout().insertWidget(0, self.document_title_label)

        self.asset_selector = QComboBox()
        self.asset_selector.setProperty("role", ROLE_WORKSPACE_ASSET_SELECTOR)
        self.asset_selector.currentIndexChanged.connect(self._on_asset_changed)
        self.insert_toolbar_widget(self.asset_selector)

        self.summary_button = QPushButton(self.i18n.t("workspace.generate_summary"))
        self.summary_button.setProperty("role", ROLE_WORKSPACE_AI_ACTION)
        connect_button_with_callback(self.summary_button, self._generate_summary)
        self.insert_toolbar_widget(self.summary_button)

        self.meeting_brief_button = QPushButton(self.i18n.t("workspace.generate_meeting_brief"))
        self.meeting_brief_button.setProperty("role", ROLE_WORKSPACE_AI_ACTION)
        connect_button_with_callback(self.meeting_brief_button, self._generate_meeting_brief)
        self.insert_toolbar_widget(self.meeting_brief_button)

        self.asset_selector.setMinimumWidth(180)

    def set_item(self, item) -> None:
        """Load editable assets for the selected workspace item."""
        self.current_item = item
        self.current_asset = None
        self._text_assets = []
        self.document_title_label.setText(item.title if item is not None else "")
        self.asset_selector.blockSignals(True)
        self.asset_selector.clear()

        if item is not None:
            assets = self.workspace_manager.get_assets(item.id)
            self._text_assets = [
                asset for asset in assets if self.workspace_manager.read_asset_text(asset)
            ]
            self._text_assets.sort(
                key=lambda asset: (
                    WORKSPACE_ASSET_ORDER.get(asset.asset_role, 999),
                    asset.created_at or "",
                )
            )
            preferred_id = getattr(item, "primary_text_asset_id", None)
            selected_index = 0
            for index, asset in enumerate(self._text_assets):
                self.asset_selector.addItem(self._label_for_asset(asset), asset.id)
                if preferred_id and asset.id == preferred_id:
                    selected_index = index
            if self._text_assets:
                self.asset_selector.setCurrentIndex(selected_index)
                self.current_asset = self._text_assets[selected_index]
                self._load_current_asset()
            else:
                self.set_document_context(display_name=item.title or item.id, file_path=None)
                self.set_text_content("")
        else:
            self.set_document_context(display_name="workspace", file_path=None)
            self.set_text_content("")

        self.asset_selector.blockSignals(False)
        self._update_action_states()

    def update_translations(self) -> None:
        super().update_translations()
        if hasattr(self, "summary_button"):
            self.summary_button.setText(self.i18n.t("workspace.generate_summary"))
        if hasattr(self, "meeting_brief_button"):
            self.meeting_brief_button.setText(self.i18n.t("workspace.generate_meeting_brief"))

    def _on_asset_changed(self, index: int) -> None:
        if index < 0 or index >= len(self._text_assets):
            return
        self.current_asset = self._text_assets[index]
        self._load_current_asset()

    def _load_current_asset(self) -> None:
        if self.current_asset is None:
            self.set_text_content("")
            return
        display_name = Path(self.current_asset.file_path).name if self.current_asset.file_path else self.current_asset.asset_role
        self.set_document_context(
            display_name=display_name,
            file_path=self.current_asset.file_path,
            save_handler=self._save_current_asset,
            export_formats=("txt", "md"),
        )
        self.set_text_content(self.workspace_manager.read_asset_text(self.current_asset))

    def _save_current_asset(self, text_content: str) -> None:
        if self.current_asset is None:
            raise ValueError("No workspace asset selected")
        self.current_asset = self.workspace_manager.update_text_asset(self.current_asset.id, text_content)

    def _generate_summary(self) -> None:
        if self.current_item is None:
            return
        self.workspace_manager.generate_summary(self.current_item.id)
        self.set_item(self.workspace_manager.get_item(self.current_item.id))
        self._select_asset_role("summary")
        self.show_info(self.i18n.t("common.success"), self.i18n.t("workspace.summary_ready"))

    def _generate_meeting_brief(self) -> None:
        if self.current_item is None:
            return
        self.workspace_manager.generate_meeting_brief(self.current_item.id)
        self.set_item(self.workspace_manager.get_item(self.current_item.id))
        self._select_asset_role("meeting_brief")
        self.show_info(
            self.i18n.t("common.success"),
            self.i18n.t("workspace.meeting_brief_ready"),
        )

    def _select_asset_role(self, asset_role: str) -> None:
        for index, asset in enumerate(self._text_assets):
            if asset.asset_role == asset_role:
                self.asset_selector.setCurrentIndex(index)
                break

    def select_asset_role(self, asset_role: str) -> None:
        """Public wrapper used by workspace routing helpers."""
        self._select_asset_role(asset_role)

    def _label_for_asset(self, asset) -> str:
        role_label = WORKSPACE_ASSET_LABELS.get(
            asset.asset_role,
            asset.asset_role.replace("_", " ").title(),
        )
        file_name = Path(asset.file_path).name if asset.file_path else role_label
        return f"{role_label}: {file_name}"

    def _update_action_states(self) -> None:
        has_item = self.current_item is not None
        self.edit_button.setEnabled(self.current_asset is not None)
        self.copy_button.setEnabled(self.current_asset is not None)
        self.export_button.setEnabled(self.current_asset is not None)
        self.search_button.setEnabled(self.current_asset is not None)
        self.summary_button.setEnabled(has_item)
        self.meeting_brief_button.setEnabled(has_item)

    def current_item_id(self) -> str:
        """Expose the currently loaded workspace item identifier."""
        return self.current_item.id if self.current_item is not None else ""
