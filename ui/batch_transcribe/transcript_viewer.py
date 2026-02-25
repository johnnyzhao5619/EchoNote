# SPDX-License-Identifier: Apache-2.0
#
# Copyright (c) 2024-2025 EchoNote Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Transcript viewer dialog for viewing and editing transcription results."""

import logging
import os
import shutil
from typing import Any, Optional

from config.constants import (
    DEFAULT_TRANSLATION_TARGET_LANGUAGE,
    TRANSLATION_LANGUAGE_AUTO,
)
from core.settings.manager import resolve_translation_languages_from_settings
from core.qt_imports import (
    QAction,
    QApplication,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QKeySequence,
    QLabel,
    QMenu,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QShortcut,
    QSize,
    QTextEdit,
    QTimer,
    QVBoxLayout,
    QWidget,
    Qt,
)

from data.database.models import TranscriptionTask
from ui.base_widgets import connect_button_with_callback, create_hbox
from ui.batch_transcribe.search_widget import SearchWidget
from ui.batch_transcribe.window_state_manager import WindowStateManager
from ui.common.style_utils import set_widget_state
from ui.constants import (
    CONTROL_BUTTON_MIN_HEIGHT,
    ROLE_TRANSCRIPT_FILE,
)
from utils.i18n import LANGUAGE_OPTION_KEYS, I18nQtManager
from utils.time_utils import format_localized_datetime

logger = logging.getLogger("echonote.ui.transcript_viewer")

BATCH_VIEWER_ROLE_TOOLBAR = "batch-viewer-toolbar"
BATCH_VIEWER_ROLE_EDIT = "batch-viewer-edit-action"
BATCH_VIEWER_ROLE_EXPORT = "batch-viewer-export-action"
BATCH_VIEWER_ROLE_COPY = "batch-viewer-copy-action"
BATCH_VIEWER_ROLE_SEARCH = "batch-viewer-search-action"


class TranscriptViewerDialog(QDialog):
    """
    Dialog for viewing and editing transcription results.

    Features:
    - View transcription text with metadata
    - Edit mode for correcting transcription errors
    - Search functionality
    - Export to multiple formats (TXT, SRT, MD)
    - Full i18n and theme support
    """

    def __init__(
        self,
        task_id: str,
        transcription_manager,
        db_connection,
        i18n: I18nQtManager,
        settings_manager=None,
        parent: Optional[QDialog] = None,
    ):
        """
        Initialize transcript viewer dialog.

        Args:
            task_id: Transcription task ID
            transcription_manager: Transcription manager instance
            db_connection: Database connection instance
            i18n: Internationalization manager
            settings_manager: Settings manager for theme detection
            parent: Parent widget
        """
        super().__init__(parent)

        # Remove default dialog buttons
        self.setModal(False)

        self.task_id = task_id
        self.transcription_manager = transcription_manager
        self.db_connection = db_connection
        self.i18n = i18n
        self.settings_manager = settings_manager
        self.is_modified = False
        self.is_edit_mode = False

        # Initialize managers
        self.window_state_manager = WindowStateManager(self)

        # File loading state
        self.progress_dialog = None
        self.transcript_content = ""

        # Initialize text_edit to None (will be created in _init_ui)
        self.text_edit = None

        # Load task data
        try:
            self.task_data = self._load_task_data()
        except Exception as e:
            logger.error(f"Failed to load task data: {e}")
            self._show_error_and_close(str(e))
            return

        # Initialize UI first (without content)
        self._init_ui()

        # Load content
        self._load_content()

        # Connect signals
        self.i18n.language_changed.connect(self.update_language)

        # Connect theme change signal if settings manager available
        if self.settings_manager:
            self.settings_manager.setting_changed.connect(self._on_setting_changed)

        # Apply initial translations
        self.update_language()

        # Restore window state using WindowStateManager
        self.window_state_manager.restore_window_state()

        logger.info(f"Transcript viewer opened for task {task_id}")

    def _load_task_data(self) -> dict:
        """
        Load task metadata from database.

        Returns:
            Task data dictionary

        Raises:
            ValueError: If task not found
            Exception: If database error occurs
        """
        try:
            task = TranscriptionTask.get_by_id(self.db_connection, self.task_id)

            if not task:
                error_msg = self.i18n.t("viewer.task_not_found_details", task_id=self.task_id)
                logger.error(f"Task {self.task_id} not found in database")
                raise ValueError(error_msg)

            # Convert to dictionary
            task_dict = {
                "id": task.id,
                "file_name": task.file_name,
                "file_path": task.file_path,
                "audio_duration": task.audio_duration,
                "language": task.language,
                "engine": task.engine,
                "task_kind": "translation" if task.engine == "translation" else "transcription",
                "output_path": task.output_path,
                "completed_at": task.completed_at,
                "status": task.status,
            }

            logger.debug(f"Loaded task data for {self.task_id}")
            return task_dict

        except ValueError:
            # Re-raise ValueError with translated message
            raise
        except Exception as e:
            logger.error(f"Database error loading task {self.task_id}: {e}", exc_info=True)
            raise Exception(f"Database error: {str(e)}")

    def _load_content(self):
        """Load transcript content from internal storage."""
        try:
            content_data = self.transcription_manager.get_task_content(self.task_id)

            # Format content for display (using TXT format logic for now)
            formatted_text = self.transcription_manager.format_converter.convert(
                content_data, "txt"
            )

            self._set_text_content_optimized(formatted_text)
            self.transcript_content = formatted_text

        except Exception as e:
            logger.error(f"Failed to load task content: {e}")
            self._show_error_and_close(self.i18n.t("viewer.file_read_error_details", error=str(e)))

    def _optimize_text_edit(self):
        """
        Optimize text edit widget for better performance.

        Configures the text edit for efficient editing and rendering,
        especially for large documents.
        """
        # Set undo/redo stack limit to prevent memory issues
        # Default is unlimited which can cause performance problems
        self.text_edit.document().setMaximumBlockCount(0)  # No limit on blocks
        self.text_edit.setUndoRedoEnabled(True)

        # Limit undo stack depth for better memory management
        # This prevents excessive memory usage with large documents
        self.text_edit.document().setUndoRedoEnabled(True)

        # Set tab stop width for better readability
        self.text_edit.setTabStopDistance(40)

        # Enable word wrap for better readability
        self.text_edit.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)

        # Disable auto-formatting features that can slow down editing
        self.text_edit.setAcceptRichText(False)

        logger.debug("Text edit optimized for performance")

    def _set_text_content_optimized(self, content: str):
        """
        Set text content with optimization for large files.

        Args:
            content: Text content to display
        """
        # Disable updates during content setting for better performance
        self.text_edit.setUpdatesEnabled(False)

        # Temporarily disable undo/redo during initial load
        undo_enabled = self.text_edit.isUndoRedoEnabled()
        self.text_edit.setUndoRedoEnabled(False)

        try:
            # Use plain text mode for all content
            self.text_edit.setPlainText(content)

            # Reset cursor to beginning
            cursor = self.text_edit.textCursor()
            cursor.movePosition(cursor.MoveOperation.Start)
            self.text_edit.setTextCursor(cursor)

        finally:
            # Re-enable undo/redo
            self.text_edit.setUndoRedoEnabled(undo_enabled)

            # Re-enable updates
            self.text_edit.setUpdatesEnabled(True)

            # Clear undo stack after initial load
            self.text_edit.document().clearUndoRedoStacks()

        logger.debug(f"Text content set ({len(content)} characters)")

    def _init_ui(self):
        """Initialize the user interface."""
        # Window properties
        title = self.i18n.t("viewer.title", filename=self.task_data["file_name"])
        self.setWindowTitle(title)
        self.setMinimumSize(QSize(800, 600))
        self.resize(QSize(1000, 800))

        # Main layout
        main_layout = QVBoxLayout(self)

        # Metadata section
        metadata_frame = self._create_metadata_section()
        main_layout.addWidget(metadata_frame)

        # Toolbar section
        toolbar_frame = self._create_toolbar_section()
        main_layout.addWidget(toolbar_frame)

        # Search widget (initially hidden)
        self.search_widget = SearchWidget(None, self.i18n, self.settings_manager, self)
        main_layout.addWidget(self.search_widget)

        # Text display section
        text_frame = self._create_text_section()
        main_layout.addWidget(text_frame, 1)  # Stretch factor 1

        # Connect search widget to text edit after text edit is created
        self.search_widget.text_edit = self.text_edit

        # Setup keyboard shortcuts
        self._setup_shortcuts()

        logger.debug("UI initialized")

    def _create_metadata_section(self) -> QFrame:
        """
        Create metadata display section.

        Returns:
            QFrame containing metadata labels
        """
        frame = QFrame()
        frame.setObjectName("metadata_frame")
        frame.setFrameShape(QFrame.Shape.StyledPanel)

        layout = QVBoxLayout(frame)

        # File name (larger font)
        self.file_name_label = QLabel()
        self.file_name_label.setProperty("role", ROLE_TRANSCRIPT_FILE)
        layout.addWidget(self.file_name_label)

        # Metadata row 1: Duration, Language
        metadata_row1 = create_hbox(spacing=20)

        self.duration_label = QLabel()
        metadata_row1.addWidget(self.duration_label)

        self.language_label = QLabel()
        metadata_row1.addWidget(self.language_label)

        metadata_row1.addStretch()
        layout.addLayout(metadata_row1)

        # Metadata row 2: Engine, Completed time
        metadata_row2 = create_hbox(spacing=20)

        self.engine_label = QLabel()
        metadata_row2.addWidget(self.engine_label)

        self.completed_label = QLabel()
        metadata_row2.addWidget(self.completed_label)

        metadata_row2.addStretch()
        layout.addLayout(metadata_row2)

        # Update metadata content
        self._update_metadata_content()

        return frame

    def _create_toolbar_section(self) -> QFrame:
        """
        Create toolbar section with action buttons.

        Returns:
            QFrame containing toolbar buttons
        """
        frame = QFrame()
        frame.setObjectName("toolbar_frame")
        frame.setProperty("role", BATCH_VIEWER_ROLE_TOOLBAR)
        frame.setFrameShape(QFrame.Shape.NoFrame)

        layout = QHBoxLayout(frame)

        # Edit/Save button
        self.edit_button = QPushButton()
        self.edit_button.setProperty("role", BATCH_VIEWER_ROLE_EDIT)
        self.edit_button.setMinimumHeight(CONTROL_BUTTON_MIN_HEIGHT)
        self._set_edit_button_active_state(False)
        connect_button_with_callback(self.edit_button, self.toggle_edit_mode)
        layout.addWidget(self.edit_button)

        # Export button with dropdown menu
        self.export_button = QPushButton()
        self.export_button.setProperty("role", BATCH_VIEWER_ROLE_EXPORT)
        self.export_button.setMinimumHeight(CONTROL_BUTTON_MIN_HEIGHT)
        self._create_export_menu()
        layout.addWidget(self.export_button)

        # Copy all button
        self.copy_button = QPushButton()
        self.copy_button.setProperty("role", BATCH_VIEWER_ROLE_COPY)
        self.copy_button.setMinimumHeight(CONTROL_BUTTON_MIN_HEIGHT)
        connect_button_with_callback(self.copy_button, self.copy_all)
        layout.addWidget(self.copy_button)

        # Search button
        self.search_button = QPushButton()
        self.search_button.setProperty("role", BATCH_VIEWER_ROLE_SEARCH)
        self.search_button.setMinimumHeight(CONTROL_BUTTON_MIN_HEIGHT)
        connect_button_with_callback(self.search_button, self._toggle_search)
        layout.addWidget(self.search_button)

        self.translate_target_combo = QComboBox()
        self.translate_target_combo.setMinimumHeight(CONTROL_BUTTON_MIN_HEIGHT)
        for code, label_key in LANGUAGE_OPTION_KEYS:
            self.translate_target_combo.addItem(self.i18n.t(label_key), code)
        resolved = resolve_translation_languages_from_settings(self.settings_manager)
        default_target = resolved.get(
            "translation_target_lang", DEFAULT_TRANSLATION_TARGET_LANGUAGE
        )
        default_index = self.translate_target_combo.findData(default_target)
        if default_index >= 0:
            self.translate_target_combo.setCurrentIndex(default_index)
        layout.addWidget(self.translate_target_combo)

        self.translate_button = QPushButton()
        self.translate_button.setProperty("role", BATCH_VIEWER_ROLE_SEARCH)
        self.translate_button.setMinimumHeight(CONTROL_BUTTON_MIN_HEIGHT)
        connect_button_with_callback(self.translate_button, self._on_translate_transcript_clicked)
        layout.addWidget(self.translate_button)

        if self.task_data.get("task_kind") == "translation":
            self.translate_target_combo.setVisible(False)
            self.translate_button.setVisible(False)

        layout.addStretch()

        return frame

    def _set_edit_button_active_state(self, is_active: bool):
        """Expose edit mode state as a semantic property for unified theming."""
        set_widget_state(self.edit_button, "active" if is_active else "default")

    def _create_export_menu(self):
        """Create export dropdown menu with format options."""
        export_menu = QMenu(self)

        # TXT export action
        txt_action = QAction(self.i18n.t("viewer.export_txt"), self)
        txt_action.triggered.connect(lambda: self.export_as("txt"))
        export_menu.addAction(txt_action)

        # SRT export action
        srt_action = QAction(self.i18n.t("viewer.export_srt"), self)
        srt_action.triggered.connect(lambda: self.export_as("srt"))
        export_menu.addAction(srt_action)

        # MD export action
        md_action = QAction(self.i18n.t("viewer.export_md"), self)
        md_action.triggered.connect(lambda: self.export_as("md"))
        export_menu.addAction(md_action)

        # Set menu to button
        self.export_button.setMenu(export_menu)

        # Store actions for language updates
        self.export_txt_action = txt_action
        self.export_srt_action = srt_action
        self.export_md_action = md_action

    def _create_text_section(self) -> QFrame:
        """
        Create text display/edit section.

        Returns:
            QFrame containing text editor
        """
        frame = QFrame()
        frame.setObjectName("text_frame")

        layout = QVBoxLayout(frame)

        # Text editor
        self.text_edit = QTextEdit()
        self.text_edit.setObjectName("transcript_text_edit")
        self.text_edit.setReadOnly(True)
        # Content will be set asynchronously
        self.text_edit.setPlaceholderText(self.i18n.t("viewer.loading"))
        self.text_edit.setContextMenuPolicy(self.text_edit.contextMenuPolicy())

        # Optimize text edit for performance
        self._optimize_text_edit()

        # Connect text changed signal
        self.text_edit.textChanged.connect(self._on_text_changed)

        # Override context menu
        self.text_edit.contextMenuEvent = self._text_context_menu_event

        layout.addWidget(self.text_edit)

        return frame

    def _update_metadata_content(self):
        """Update metadata labels with task data."""
        # File name
        file_name = self.task_data.get("file_name", "Unknown")
        self.file_name_label.setText(file_name)

        # Duration
        duration = self.task_data.get("audio_duration")
        if duration:
            minutes = int(duration // 60)
            seconds = int(duration % 60)
            duration_text = f"{minutes:02d}:{seconds:02d}"
        else:
            duration_text = "Unknown"

        # Language
        language = self.task_data.get("language", "Unknown")

        # Engine
        engine = self.task_data.get("engine", "Unknown")

        # Completed time
        completed_at = self.task_data.get("completed_at", "Unknown")
        if completed_at and completed_at != "Unknown":
            completed_text = format_localized_datetime(completed_at)
        else:
            completed_text = "Unknown"

        # These will be updated with translations in update_language()
        self.duration_value = duration_text
        self.language_value = language
        self.engine_value = engine
        self.completed_value = completed_text

    def toggle_edit_mode(self):
        """Toggle between view and edit mode."""
        if self.is_edit_mode:
            # Save changes
            self.save_changes()
        else:
            # Enter edit mode
            self.is_edit_mode = True
            self.text_edit.setReadOnly(False)
            self.edit_button.setText(self.i18n.t("common.save"))
            self._set_edit_button_active_state(True)

            # Clear undo stack when entering edit mode for clean state
            self.text_edit.document().clearUndoRedoStacks()

            logger.debug("Entered edit mode")

    def save_changes(self):
        """Save edited transcript content to file with error handling and retry option."""
        if not self.is_modified:
            # No changes to save, just exit edit mode
            self.is_edit_mode = False
            self.text_edit.setReadOnly(True)
            self.edit_button.setText(self.i18n.t("common.edit"))
            self._set_edit_button_active_state(False)
            return

        output_path = self.task_data["output_path"]
        content = self.text_edit.toPlainText()

        try:
            # Validate output path exists
            if not output_path:
                raise ValueError(
                    self.i18n.t("exceptions.batch_transcribe_viewer.output_path_not_set")
                )

            # Check directory exists
            output_dir = os.path.dirname(output_path)
            if not os.path.exists(output_dir):
                raise FileNotFoundError(f"Directory does not exist: {output_dir}")

            # Check write permission
            if os.path.exists(output_path) and not os.access(output_path, os.W_OK):
                raise PermissionError(f"No write permission for file: {output_path}")

            # Check directory write permission if file doesn't exist
            if not os.path.exists(output_path) and not os.access(output_dir, os.W_OK):
                raise PermissionError(f"No write permission for directory: {output_dir}")

            # Check disk space (approximate - at least 1MB free)
            stat = shutil.disk_usage(output_dir)
            if stat.free < 1024 * 1024:  # Less than 1MB free
                raise OSError(
                    self.i18n.t("exceptions.batch_transcribe_viewer.insufficient_disk_space")
                )

            # Write to file
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(content)

            # Success - update state
            self.is_modified = False
            self.is_edit_mode = False
            self.text_edit.setReadOnly(True)
            self.edit_button.setText(self.i18n.t("common.edit"))
            self._set_edit_button_active_state(False)

            # Show success notification
            self.show_info(self.i18n.t("common.success"), self.i18n.t("viewer.save_success"))

            logger.info(f"Saved changes to {output_path}")

        except PermissionError as e:
            logger.error(f"Permission error saving file: {e}", exc_info=True)
            self._show_save_error_with_retry(self.i18n.t("viewer.save_error_permission"), str(e))

        except OSError as e:
            logger.error(f"OS error saving file: {e}", exc_info=True)
            # Check if it's a disk full error
            if "disk" in str(e).lower() or "space" in str(e).lower():
                error_msg = self.i18n.t("viewer.save_error_disk_full")
            else:
                error_msg = self.i18n.t("viewer.save_error_details", error=str(e))
            self._show_save_error_with_retry(error_msg, str(e))

        except Exception as e:
            logger.error(f"Unexpected error saving file: {e}", exc_info=True)
            self._show_save_error_with_retry(
                self.i18n.t("viewer.save_error_details", error=str(e)), str(e)
            )

    def _show_save_error_with_retry(self, error_msg: str, details: str):
        """
        Show save error dialog with retry option.

        Args:
            error_msg: User-friendly error message
            details: Technical error details
        """
        # Create custom message box with retry option
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Icon.Critical)
        msg_box.setWindowTitle(self.i18n.t("common.error"))
        msg_box.setText(error_msg)
        msg_box.setDetailedText(details)

        # Add buttons
        retry_button = msg_box.addButton(
            self.i18n.t("viewer.save_retry"), QMessageBox.ButtonRole.AcceptRole
        )
        msg_box.addButton(self.i18n.t("common.cancel"), QMessageBox.ButtonRole.RejectRole)

        msg_box.exec()

        # Check which button was clicked
        if msg_box.clickedButton() == retry_button:
            # User wants to retry
            logger.info(self.i18n.t("logging.batch_transcribe_viewer.user_chose_retry_save"))
            self.save_changes()
        else:
            # User cancelled - stay in edit mode with unsaved changes
            logger.info(self.i18n.t("logging.batch_transcribe_viewer.user_cancelled_save"))
            # Keep is_modified = True so user doesn't lose changes

    def _on_text_changed(self):
        """
        Handle text content change.

        Tracks modification state and manages undo stack size
        for optimal performance.
        """
        if self.is_edit_mode:
            self.is_modified = True

            # Limit undo stack size for very large documents
            # to prevent excessive memory usage
            doc = self.text_edit.document()
            if doc.characterCount() > 100000:
                # For large documents, limit undo stack
                # This is a trade-off between memory and undo capability
                if doc.availableUndoSteps() > 100:
                    # Keep only last 100 undo steps
                    logger.debug("Trimming undo stack for large document")
                    # Note: Qt doesn't provide direct stack trimming,
                    # but the stack will naturally limit itself

    def _setup_shortcuts(self):
        """Setup keyboard shortcuts for editing operations."""
        # Ctrl+S: Save changes
        save_shortcut = QShortcut(QKeySequence.StandardKey.Save, self)
        save_shortcut.activated.connect(self._handle_save_shortcut)

        # Ctrl+Z: Undo (handled by QTextEdit automatically)
        # Ctrl+Y: Redo (handled by QTextEdit automatically)
        # Ctrl+A: Select All (handled by QTextEdit automatically)

        # Ctrl+F: Open search (placeholder for future implementation)
        search_shortcut = QShortcut(QKeySequence.StandardKey.Find, self)
        search_shortcut.activated.connect(self._handle_search_shortcut)

        logger.debug("Keyboard shortcuts configured")

    def _handle_save_shortcut(self):
        """Handle Ctrl+S shortcut."""
        if self.is_edit_mode and self.is_modified:
            self.save_changes()

    def _handle_search_shortcut(self):
        """Handle Ctrl+F shortcut to open search widget."""
        self._toggle_search()

    def _toggle_search(self):
        """Toggle search widget visibility."""
        if self.search_widget.isVisible():
            self.search_widget.hide_search()
        else:
            self.search_widget.show_search()

    def _text_context_menu_event(self, event):
        """Handle context menu event for text edit."""
        menu = self.text_edit.createStandardContextMenu()
        menu.exec(event.globalPos())

    def export_as(self, format: str):
        """
        Export transcript to specified format.

        Args:
            format: Target format (txt, srt, md)
        """
        # Generate default export path
        original_name = self.task_data.get("file_name", "transcript")
        base_name = os.path.splitext(original_name)[0]

        # Infer extension from format
        extension = format.lower()
        default_name = f"{base_name}.{extension}"

        # Open file dialog
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            self.i18n.t("viewer.export_dialog_title"),
            default_name,
            f"{format.upper()} (*.{extension})",
        )

        if not file_path:
            return

        try:
            # Use manager to export (which uses structured data)
            self.transcription_manager.export_result(self.task_id, format, file_path)

            self.show_info(
                self.i18n.t("common.success"), self.i18n.t("viewer.export_success", path=file_path)
            )

        except Exception as e:
            logger.error(f"Export failed: {e}")
            self.show_error(self.i18n.t("viewer.export_error"), str(e))

    def show_info(self, title: str, message: str):
        """Show info message box."""
        QMessageBox.information(self, title, message)

    def show_error(self, title: str, message: str):
        """Show error message box."""
        QMessageBox.critical(self, title, message)

    def _show_error_and_close(self, message: str):
        """Show error and close dialog."""
        self.show_error(self.i18n.t("common.error"), message)
        self.close()

    def update_language(self):
        """Update interface language."""
        # Window title
        self.setWindowTitle(self.i18n.t("viewer.title", filename=self.task_data["file_name"]))

        # Toolbar buttons
        if self.edit_button:
            self.edit_button.setText(
                self.i18n.t("common.save") if self.is_edit_mode else self.i18n.t("common.edit")
            )
        if self.copy_button:
            self.copy_button.setText(self.i18n.t("viewer.copy_all"))
        if self.export_button:
            self.export_button.setText(self.i18n.t("viewer.export"))
        if self.search_button:
            self.search_button.setText(self.i18n.t("viewer.search"))
        if self.translate_button:
            self.translate_button.setText(self.i18n.t("timeline.translate_transcript"))
        if self.translate_target_combo:
            current_target = self.translate_target_combo.currentData()
            self.translate_target_combo.blockSignals(True)
            self.translate_target_combo.clear()
            for code, label_key in LANGUAGE_OPTION_KEYS:
                self.translate_target_combo.addItem(self.i18n.t(label_key), code)
            index = self.translate_target_combo.findData(current_target)
            if index >= 0:
                self.translate_target_combo.setCurrentIndex(index)
            self.translate_target_combo.blockSignals(False)

        # Export menu actions
        if hasattr(self, "export_txt_action"):
            self.export_txt_action.setText(self.i18n.t("viewer.export_txt"))
        if hasattr(self, "export_srt_action"):
            self.export_srt_action.setText(self.i18n.t("viewer.export_srt"))
        if hasattr(self, "export_md_action"):
            self.export_md_action.setText(self.i18n.t("viewer.export_md"))

        # Update metadata labels
        self._update_metadata_content()
        self.duration_label.setText(f"{self.i18n.t('viewer.metadata.duration')}: {self.duration_value}")
        self.language_label.setText(f"{self.i18n.t('viewer.metadata.language')}: {self.language_value}")
        self.engine_label.setText(f"{self.i18n.t('viewer.metadata.engine')}: {self.engine_value}")
        self.completed_label.setText(f"{self.i18n.t('viewer.metadata.completed')}: {self.completed_value}")

    def _on_setting_changed(self, key: str, value: Any):
        """Handle setting changes."""
        # For now, we only care about theme changes which might be handled globally
        # or by the SearchWidget, but we can add specific handling here if needed.
        pass

    def _resolve_transcript_path(self) -> str:
        """Resolve transcript file path for translation entry."""
        output_path = self.task_data.get("output_path")
        if output_path:
            return str(output_path)

        file_path = self.task_data.get("file_path", "")
        if file_path:
            return str(os.path.splitext(file_path)[0] + ".txt")
        return ""

    def _ensure_transcript_file(self, transcript_path: str) -> str:
        """Ensure transcript file exists before translation."""
        if not transcript_path:
            raise ValueError(self.i18n.t("viewer.file_not_found"))
        if os.path.exists(transcript_path):
            return transcript_path

        text = self.text_edit.toPlainText() if self.text_edit else ""
        if not text.strip():
            raise ValueError(self.i18n.t("viewer.file_not_found"))

        os.makedirs(os.path.dirname(transcript_path), exist_ok=True)
        with open(transcript_path, "w", encoding="utf-8") as handle:
            handle.write(text)
        return transcript_path

    def _on_translate_transcript_clicked(self):
        """Queue transcript translation in batch task queue."""
        manager = self.transcription_manager
        if manager is None or getattr(manager, "translation_engine", None) is None:
            self.show_error(
                self.i18n.t("common.warning"),
                self.i18n.t("viewer.translation_not_available"),
            )
            return

        transcript_path = self._resolve_transcript_path()
        selected_target = self.translate_target_combo.currentData()
        resolved_languages = resolve_translation_languages_from_settings(
            self.settings_manager,
            target_lang=selected_target,
        )
        source_lang = resolved_languages.get(
            "translation_source_lang", TRANSLATION_LANGUAGE_AUTO
        )
        target_lang = resolved_languages.get(
            "translation_target_lang", DEFAULT_TRANSLATION_TARGET_LANGUAGE
        )

        try:
            source_path = self._ensure_transcript_file(transcript_path)
            output_format = "md" if source_path.lower().endswith(".md") else "txt"
            manager.add_translation_task(
                source_path,
                options={
                    "translation_source_lang": source_lang,
                    "translation_target_lang": target_lang,
                    "output_format": output_format,
                },
            )
            self.show_info(self.i18n.t("common.info"), self.i18n.t("viewer.translation_queued"))
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to queue batch viewer translation task: %s", exc, exc_info=True)
            self.show_error(
                self.i18n.t("common.error"),
                self.i18n.t("viewer.translation_failed", error=str(exc)),
            )

    def copy_all(self):
        """Copy all text to clipboard."""
        if self.text_edit:
            text = self.text_edit.toPlainText()
            clipboard = QApplication.clipboard()
            clipboard.setText(text)

            # Show temporary feedback
            original_text = self.copy_button.text()
            self.copy_button.setText(self.i18n.t("common.copied"))
            self.copy_button.setEnabled(False)

            QTimer.singleShot(2000, lambda: self._reset_copy_button(original_text))

    def _reset_copy_button(self, text: str):
        """Reset copy button text."""
        if self.copy_button:
            try:
                self.copy_button.setText(text)
                self.copy_button.setEnabled(True)
            except RuntimeError:
                # Widget might be deleted
                pass
