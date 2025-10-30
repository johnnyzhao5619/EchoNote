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
"""
Transcript viewer dialog for viewing and editing transcription results.

Provides a dedicated window for viewing, editing, searching, and exporting
transcription results with full i18n and theme support.
"""

import logging
import os
from typing import Optional

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QAction, QFont, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from core.transcription.format_converter import FormatConverter
from data.database.models import TranscriptionTask
from ui.base_widgets import create_hbox, connect_button_with_callback
from ui.batch_transcribe.file_operations import FileExporter, FileLoadWorker
from ui.batch_transcribe.search_widget import SearchWidget
from ui.batch_transcribe.theme_manager import TranscriptViewerThemeManager
from ui.batch_transcribe.window_state_manager import WindowStateManager
from utils.i18n import I18nQtManager

logger = logging.getLogger("echonote.ui.transcript_viewer")


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
        db_connection,
        i18n: I18nQtManager,
        settings_manager=None,
        parent: Optional[QDialog] = None,
    ):
        """
        Initialize transcript viewer dialog.

        Args:
            task_id: Transcription task ID
            db_connection: Database connection instance
            i18n: Internationalization manager
            settings_manager: Settings manager for theme detection
            parent: Parent widget
        """
        super().__init__(parent)

        # Remove default dialog buttons
        self.setModal(False)

        self.task_id = task_id
        self.db_connection = db_connection
        self.i18n = i18n
        self.settings_manager = settings_manager
        self.is_modified = False
        self.is_edit_mode = False

        # Initialize managers
        self.window_state_manager = WindowStateManager(self)
        self.theme_manager = TranscriptViewerThemeManager(self, settings_manager)
        self.file_exporter = FileExporter(i18n)

        # File loading state
        self.load_worker = None
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

        # Start async file loading
        self._start_async_file_load()

        # Connect signals
        self.i18n.language_changed.connect(self.update_language)

        # Connect theme change signal if settings manager available
        if self.settings_manager:
            self.settings_manager.setting_changed.connect(self._on_setting_changed)

        # Apply initial translations
        self.update_language()

        # Restore window state
        self._restore_window_state()

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

    def _start_async_file_load(self):
        """Start asynchronous file loading with progress indicator."""
        output_path = self.task_data.get("output_path")

        # Validate output path
        if not output_path:
            error_msg = self.i18n.t("viewer.file_not_found_details")
            logger.error(f"Task {self.task_id} has no output_path")
            self._show_error_and_close(error_msg)
            return

        if not os.path.exists(output_path):
            error_msg = self.i18n.t("viewer.file_not_found_details")
            logger.error(f"Transcript file not found: {output_path}")
            self._show_error_and_close(error_msg)
            return

        # Check file permissions
        if not os.access(output_path, os.R_OK):
            error_msg = self.i18n.t("viewer.file_read_error_permission")
            logger.error(f"No read permission for file: {output_path}")
            self._show_error_and_close(error_msg)
            return

        try:
            # Check file size to determine if we need progress dialog
            file_size = os.path.getsize(output_path)
            show_progress = file_size > 1024 * 1024  # Show for files > 1MB

            if show_progress:
                # Create progress dialog
                self.progress_dialog = QProgressDialog(
                    self.i18n.t("viewer.loading"), self.i18n.t("common.cancel"), 0, 100, self
                )
                self.progress_dialog.setWindowTitle(self.i18n.t("viewer.loading_title"))
                self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
                self.progress_dialog.setMinimumDuration(0)
                self.progress_dialog.canceled.connect(self._cancel_file_load)

            # Create and start worker thread
            self.load_worker = FileLoadWorker(output_path)
            self.load_worker.finished.connect(self._on_file_loaded)
            self.load_worker.error.connect(self._on_file_load_error)

            if show_progress:
                self.load_worker.progress.connect(self.progress_dialog.setValue)

            self.load_worker.start()
            logger.info(f"Started async loading of {output_path} ({file_size} bytes)")

        except OSError as e:
            error_msg = self.i18n.t("viewer.file_read_error_details", error=str(e))
            logger.error(f"OS error accessing file {output_path}: {e}", exc_info=True)
            self._show_error_and_close(error_msg)

    def _on_file_loaded(self, content: str):
        """
        Handle successful file load.

        Args:
            content: Loaded transcript content
        """
        self.transcript_content = content

        # Update text edit with content (optimized for large text)
        self._set_text_content_optimized(content)

        # Close progress dialog if shown
        if self.progress_dialog:
            self.progress_dialog.close()
            self.progress_dialog = None

        # Clean up worker
        if self.load_worker:
            self.load_worker.deleteLater()
            self.load_worker = None

        logger.info(f"File loaded successfully ({len(content)} characters)")

    def _on_file_load_error(self, error_msg: str):
        """
        Handle file load error.

        Args:
            error_msg: Error message
        """
        logger.error(f"File load error: {error_msg}")

        # Close progress dialog if shown
        if self.progress_dialog:
            self.progress_dialog.close()
            self.progress_dialog = None

        # Clean up worker
        if self.load_worker:
            self.load_worker.deleteLater()
            self.load_worker = None

        # Translate error message based on error type
        translated_msg = self._translate_file_error(error_msg)

        # Show error and close dialog
        self._show_error_and_close(translated_msg)

    def _translate_file_error(self, error_msg: str) -> str:
        """
        Translate file error message to user-friendly localized text.

        Args:
            error_msg: Raw error message

        Returns:
            Translated error message
        """
        error_lower = error_msg.lower()

        # Check for specific error types
        if "file not found" in error_lower or "not found" in error_lower:
            return self.i18n.t("viewer.file_not_found_details")
        elif "permission denied" in error_lower or "permission" in error_lower:
            return self.i18n.t("viewer.file_read_error_permission")
        elif (
            "invalid file encoding" in error_lower
            or "unicode" in error_lower
            or "decode" in error_lower
        ):
            return self.i18n.t("viewer.file_format_error_details", error=error_msg)
        else:
            # Generic error with details
            return self.i18n.t("viewer.file_read_error_details", error=error_msg)

    def _cancel_file_load(self):
        """Cancel ongoing file load operation."""
        if self.load_worker:
            self.load_worker.cancel()
            self.load_worker.wait()
            self.load_worker.deleteLater()
            self.load_worker = None

        logger.info(self.i18n.t("logging.batch_transcribe_viewer.file_load_cancelled"))
        self.close()

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
        self.setWindowTitle(f"Transcript Viewer - {self.task_data['file_name']}")
        self.setMinimumSize(QSize(800, 600))
        self.resize(QSize(1000, 800))

        # Main layout
        main_layout = QVBoxLayout(self)
        # # main_layout.setSpacing(0)

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
        # # layout.setSpacing(8)

        # File name (larger font)
        self.file_name_label = QLabel()
        file_font = QFont()
        file_font.setPointSize(12)
        file_font.setBold(True)
        self.file_name_label.setFont(file_font)
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
        frame.setFrameShape(QFrame.Shape.NoFrame)

        layout = QHBoxLayout(frame)
        # # layout.setSpacing(12)

        # Edit/Save button
        self.edit_button = QPushButton()
        self.edit_button.setObjectName("edit_button")
        self.edit_button.setMinimumHeight(36)
        connect_button_with_callback(self.edit_button, self.toggle_edit_mode)
        layout.addWidget(self.edit_button)

        # Export button with dropdown menu
        self.export_button = QPushButton()
        self.export_button.setObjectName("export_button")
        self.export_button.setMinimumHeight(36)
        self._create_export_menu()
        layout.addWidget(self.export_button)

        # Copy all button
        self.copy_button = QPushButton()
        self.copy_button.setObjectName("copy_button")
        self.copy_button.setMinimumHeight(36)
        connect_button_with_callback(self.copy_button, self.copy_all)
        layout.addWidget(self.copy_button)

        # Search button
        self.search_button = QPushButton()
        self.search_button.setObjectName("search_button")
        self.search_button.setMinimumHeight(36)
        connect_button_with_callback(self.search_button, self._toggle_search)
        layout.addWidget(self.search_button)

        layout.addStretch()

        return frame

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
        # # layout.setSpacing(0)

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
            # Format datetime (just show date and time, not full ISO)
            try:
                from datetime import datetime

                dt = datetime.fromisoformat(completed_at)
                completed_text = dt.strftime("%Y-%m-%d %H:%M")
            except (ValueError, TypeError):
                completed_text = completed_at
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
            import shutil

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

    def export_as(self, format: str):
        """
        Export transcript to specified format.

        Args:
            format: Export format ('txt', 'srt', or 'md')
        """
        logger.debug(f"Export as {format} requested")

        try:
            # Get default filename
            base_name = os.path.splitext(self.task_data["file_name"])[0]
            default_filename = f"{base_name}.{format}"

            # Set up file dialog
            file_dialog = QFileDialog(self)
            file_dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
            file_dialog.setDefaultSuffix(format)

            # Set file filter based on format
            filters = {
                "txt": self.i18n.t("viewer.export_txt") + " (*.txt)",
                "srt": self.i18n.t("viewer.export_srt") + " (*.srt)",
                "md": self.i18n.t("viewer.export_md") + " (*.md)",
            }
            file_dialog.setNameFilter(filters.get(format, ""))
            file_dialog.selectFile(default_filename)

            # Show dialog and get selected file
            if file_dialog.exec() != QFileDialog.DialogCode.Accepted:
                logger.debug("Export cancelled by user")
                return

            save_path = file_dialog.selectedFiles()[0]
            logger.info(f"Exporting to {save_path} as {format}")

            # Get current content (edited or original)
            content = self.text_edit.toPlainText()

            # Export based on format
            if format == "txt":
                self._export_txt(save_path, content)
            elif format == "srt":
                self._export_srt(save_path, content)
            elif format == "md":
                self._export_md(save_path, content)

            # Show success notification
            self.show_info(
                self.i18n.t("common.success"),
                self.i18n.t("viewer.export_success", format=format.upper()),
            )

            logger.info(f"Successfully exported to {save_path}")

        except Exception as e:
            logger.error(f"Export failed: {e}", exc_info=True)
            self._show_export_error(format, str(e))

    def _export_txt(self, save_path: str, content: str):
        """
        Export as plain text (remove timestamps if present).

        Args:
            save_path: Path to save the file
            content: Text content to export

        Raises:
            PermissionError: If file cannot be written due to permissions
            OSError: If disk is full or other OS error
            IOError: If file cannot be written
        """
        try:
            # Validate content
            if not content or not content.strip():
                raise ValueError(self.i18n.t("exceptions.batch_transcribe_viewer.content_is_empty"))

            # Check directory exists
            save_dir = os.path.dirname(save_path)
            if save_dir and not os.path.exists(save_dir):
                raise FileNotFoundError(f"Directory does not exist: {save_dir}")

            # Check write permission
            if os.path.exists(save_path) and not os.access(save_path, os.W_OK):
                raise PermissionError(f"No write permission for file: {save_path}")

            # Check directory write permission if file doesn't exist
            if not os.path.exists(save_path):
                check_dir = save_dir if save_dir else "."
                if not os.access(check_dir, os.W_OK):
                    raise PermissionError(f"No write permission for directory: {check_dir}")

            # Check disk space
            import shutil

            stat = shutil.disk_usage(save_dir if save_dir else ".")
            if stat.free < 1024 * 1024:  # Less than 1MB free
                raise OSError(
                    self.i18n.t("exceptions.batch_transcribe_viewer.insufficient_disk_space")
                )

            # Remove timestamp markers like [00:00:15] if present
            import re

            lines = content.split("\n")
            clean_lines = []

            for line in lines:
                # Remove timestamp pattern [HH:MM:SS] or [MM:SS]
                clean_line = re.sub(r"\[\d{1,2}:\d{2}(?::\d{2})?\]\s*", "", line)
                if clean_line.strip():
                    clean_lines.append(clean_line.strip())

            # Write to file
            with open(save_path, "w", encoding="utf-8") as f:
                f.write("\n".join(clean_lines))

            logger.debug(f"Exported {len(clean_lines)} lines as TXT")

        except PermissionError as e:
            logger.error(f"Permission error writing TXT file: {e}", exc_info=True)
            raise PermissionError(self.i18n.t("viewer.export_error_permission"))
        except OSError as e:
            logger.error(f"OS error writing TXT file: {e}", exc_info=True)
            if "disk" in str(e).lower() or "space" in str(e).lower():
                raise OSError(self.i18n.t("viewer.export_error_disk_full"))
            else:
                raise OSError(self.i18n.t("viewer.export_error_details", error=str(e)))
        except ValueError as e:
            logger.error(f"Invalid content for TXT export: {e}")
            raise ValueError(self.i18n.t("viewer.export_error_invalid_content"))
        except Exception as e:
            logger.error(f"Unexpected error in TXT export: {e}", exc_info=True)
            raise Exception(self.i18n.t("viewer.export_error_details", error=str(e)))

    def _export_srt(self, save_path: str, content: str):
        """
        Export as SRT subtitle format.

        Args:
            save_path: Path to save the file
            content: Text content to export

        Raises:
            PermissionError: If file cannot be written due to permissions
            OSError: If disk is full or other OS error
            ValueError: If content cannot be parsed
            IOError: If file cannot be written
        """
        try:
            # Validate content
            if not content or not content.strip():
                raise ValueError(self.i18n.t("exceptions.batch_transcribe_viewer.content_is_empty"))

            # Check directory exists
            save_dir = os.path.dirname(save_path)
            if save_dir and not os.path.exists(save_dir):
                raise FileNotFoundError(f"Directory does not exist: {save_dir}")

            # Check write permission
            if os.path.exists(save_path) and not os.access(save_path, os.W_OK):
                raise PermissionError(f"No write permission for file: {save_path}")

            # Check directory write permission if file doesn't exist
            if not os.path.exists(save_path):
                check_dir = save_dir if save_dir else "."
                if not os.access(check_dir, os.W_OK):
                    raise PermissionError(f"No write permission for directory: {check_dir}")

            # Check disk space
            import shutil

            stat = shutil.disk_usage(save_dir if save_dir else ".")
            if stat.free < 1024 * 1024:  # Less than 1MB free
                raise OSError("Insufficient disk space")

            # Parse content to extract segments with timestamps
            segments = self._parse_transcript_content(content)

            if not segments:
                # If no timestamps found, create simple segments
                logger.warning(
                    self.i18n.t(
                        "logging.batch_transcribe_viewer.no_timestamps_found_creating_basic_srt"
                    )
                )
                segments = self._create_basic_segments(content)

            if not segments:
                raise ValueError("No content to export")

            # Use FormatConverter to generate SRT
            converter = FormatConverter()
            srt_content = converter._to_srt(segments)

            # Write to file
            with open(save_path, "w", encoding="utf-8") as f:
                f.write(srt_content)

            logger.debug(f"Exported {len(segments)} segments as SRT")

        except PermissionError as e:
            logger.error(f"Permission error writing SRT file: {e}", exc_info=True)
            raise PermissionError(self.i18n.t("viewer.export_error_permission"))
        except OSError as e:
            logger.error(f"OS error writing SRT file: {e}", exc_info=True)
            if "disk" in str(e).lower() or "space" in str(e).lower():
                raise OSError(self.i18n.t("viewer.export_error_disk_full"))
            else:
                raise OSError(self.i18n.t("viewer.export_error_details", error=str(e)))
        except ValueError as e:
            logger.error(f"Invalid content for SRT export: {e}")
            raise ValueError(self.i18n.t("viewer.export_error_invalid_content"))
        except Exception as e:
            logger.error(f"Unexpected error in SRT export: {e}", exc_info=True)
            raise Exception(self.i18n.t("viewer.export_error_details", error=str(e)))

    def _parse_transcript_content(self, content: str):
        """
        Parse transcript content to extract segments with timestamps.

        Args:
            content: Transcript text content

        Returns:
            List of segment dicts with 'start', 'end', 'text' keys
        """
        import re

        segments = []
        lines = content.split("\n")

        # Pattern to match timestamps like [00:00:15] or [00:15]
        timestamp_pattern = r"\[(\d{1,2}):(\d{2})(?::(\d{2}))?\]"

        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue

            # Try to find timestamp at start of line
            match = re.match(timestamp_pattern + r"\s*(.*)", line)
            if match:
                # Extract timestamp components
                hours = 0
                minutes = int(match.group(1))
                seconds = int(match.group(2))

                # Check if there's a third group (seconds in HH:MM:SS format)
                if match.group(3):
                    hours = minutes
                    minutes = seconds
                    seconds = int(match.group(3))

                start_time = hours * 3600 + minutes * 60 + seconds
                text = match.group(4) if match.group(4) else match.group(3)

                # Estimate end time (start of next segment or +5 seconds)
                end_time = start_time + 5

                # Look ahead for next timestamp to set accurate end time
                for next_line in lines[i + 1 :]:
                    next_match = re.match(timestamp_pattern, next_line)
                    if next_match:
                        next_hours = 0
                        next_minutes = int(next_match.group(1))
                        next_seconds = int(next_match.group(2))
                        if next_match.group(3):
                            next_hours = next_minutes
                            next_minutes = next_seconds
                            next_seconds = int(next_match.group(3))
                        end_time = next_hours * 3600 + next_minutes * 60 + next_seconds
                        break

                segments.append(
                    {"start": start_time, "end": end_time, "text": text.strip() if text else line}
                )

        return segments

    def _create_basic_segments(self, content: str):
        """
        Create basic segments without timestamps (5-second intervals).

        Args:
            content: Text content

        Returns:
            List of segment dicts
        """
        lines = [line.strip() for line in content.split("\n") if line.strip()]
        segments = []

        for i, line in enumerate(lines):
            segments.append({"start": i * 5.0, "end": (i + 1) * 5.0, "text": line})

        return segments

    def _export_md(self, save_path: str, content: str):
        """
        Export as Markdown format.

        Args:
            save_path: Path to save the file
            content: Text content to export

        Raises:
            PermissionError: If file cannot be written due to permissions
            OSError: If disk is full or other OS error
            ValueError: If content is empty
            IOError: If file cannot be written
        """
        try:
            # Validate content
            if not content or not content.strip():
                raise ValueError(self.i18n.t("exceptions.batch_transcribe_viewer.content_is_empty"))

            # Check directory exists
            save_dir = os.path.dirname(save_path)
            if save_dir and not os.path.exists(save_dir):
                raise FileNotFoundError(f"Directory does not exist: {save_dir}")

            # Check write permission
            if os.path.exists(save_path) and not os.access(save_path, os.W_OK):
                raise PermissionError(f"No write permission for file: {save_path}")

            # Check directory write permission if file doesn't exist
            if not os.path.exists(save_path):
                check_dir = save_dir if save_dir else "."
                if not os.access(check_dir, os.W_OK):
                    raise PermissionError(f"No write permission for directory: {check_dir}")

            # Check disk space
            import shutil

            stat = shutil.disk_usage(save_dir if save_dir else ".")
            if stat.free < 1024 * 1024:  # Less than 1MB free
                raise OSError("Insufficient disk space")

            # Parse content to extract segments with timestamps
            segments = self._parse_transcript_content(content)

            if segments:
                # Use FormatConverter to generate Markdown
                converter = FormatConverter()
                md_content = converter._to_md(segments)
            else:
                # If no timestamps, create simple markdown
                logger.warning(
                    self.i18n.t(
                        "logging.batch_transcribe_viewer.no_timestamps_found_creating_basic_markdown"
                    )
                )
                md_content = self._create_basic_markdown(content)

            if not md_content or md_content.strip() == "# Transcription":
                raise ValueError("No content to export")

            # Write to file
            with open(save_path, "w", encoding="utf-8") as f:
                f.write(md_content)

            logger.debug(f"Exported as Markdown to {save_path}")

        except PermissionError as e:
            logger.error(f"Permission error writing Markdown file: {e}", exc_info=True)
            raise PermissionError(self.i18n.t("viewer.export_error_permission"))
        except OSError as e:
            logger.error(f"OS error writing Markdown file: {e}", exc_info=True)
            if "disk" in str(e).lower() or "space" in str(e).lower():
                raise OSError(self.i18n.t("viewer.export_error_disk_full"))
            else:
                raise OSError(self.i18n.t("viewer.export_error_details", error=str(e)))
        except ValueError as e:
            logger.error(f"Invalid content for Markdown export: {e}")
            raise ValueError(self.i18n.t("viewer.export_error_invalid_content"))
        except Exception as e:
            logger.error(f"Unexpected error in Markdown export: {e}", exc_info=True)
            raise Exception(self.i18n.t("viewer.export_error_details", error=str(e)))

    def _create_basic_markdown(self, content: str):
        """
        Create basic Markdown without timestamps.

        Args:
            content: Text content

        Returns:
            Markdown formatted string
        """
        lines = [line.strip() for line in content.split("\n") if line.strip()]

        md_lines = ["# Transcription\n"]
        for line in lines:
            md_lines.append(f"{line}\n")

        return "\n".join(md_lines)

    def _show_export_error(self, format: str, error_msg: str):
        """
        Show export error dialog with retry option and user-friendly message.

        Args:
            format: Export format that failed
            error_msg: Error message
        """
        # Create custom message box with retry option
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Icon.Critical)
        msg_box.setWindowTitle(self.i18n.t("common.error"))

        # Use translated error message if available, otherwise show generic error
        if error_msg:
            msg_box.setText(error_msg)
        else:
            msg_box.setText(self.i18n.t("viewer.export_error"))

        # Add detailed text for technical details
        msg_box.setDetailedText(f"Export format: {format.upper()}\nError: {error_msg}")

        # Add buttons
        retry_button = msg_box.addButton(
            self.i18n.t("viewer.export_retry"), QMessageBox.ButtonRole.AcceptRole
        )
        msg_box.addButton(self.i18n.t("common.cancel"), QMessageBox.ButtonRole.RejectRole)

        msg_box.setDefaultButton(retry_button)
        msg_box.exec()

        # Check which button was clicked
        if msg_box.clickedButton() == retry_button:
            # User wants to retry
            logger.info(f"User chose to retry export as {format}")
            self.export_as(format)
        else:
            # User cancelled
            logger.info(f"User cancelled export as {format}")

    def copy_all(self):
        """
        Copy all transcript content to clipboard.

        Copies the complete transcript text including timestamps (if present)
        to the system clipboard and shows a temporary notification.
        """
        try:
            # Get all text content
            content = self.text_edit.toPlainText()

            # Copy to clipboard
            clipboard = QApplication.clipboard()
            clipboard.setText(content)

            # Show temporary notification
            self._show_copy_notification()

            logger.info(
                self.i18n.t("logging.batch_transcribe_viewer.copied_all_transcript_to_clipboard")
            )

        except Exception as e:
            logger.error(f"Failed to copy to clipboard: {e}")
            self.show_warning(self.i18n.t("common.error"), self.i18n.t("viewer.copy_error"))

    def _show_copy_notification(self):
        """
        Show temporary notification that content was copied.

        Displays a brief message box that auto-closes after 1.5 seconds.
        """
        # Create a simple message box
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Icon.Information)
        msg_box.setWindowTitle(self.i18n.t("common.success"))
        msg_box.setText(self.i18n.t("viewer.copied"))
        msg_box.setStandardButtons(QMessageBox.StandardButton.NoButton)

        # Show the message box
        msg_box.show()

        # Auto-close after 1.5 seconds
        QTimer.singleShot(1500, msg_box.close)

        logger.debug("Showing copy notification")

    def _text_context_menu_event(self, event):
        """
        Handle context menu event for text edit widget.

        Creates a custom context menu with Copy and Select All options.

        Args:
            event: QContextMenuEvent
        """
        # Create context menu
        context_menu = QMenu(self)

        # Copy action (only enabled if text is selected)
        copy_action = QAction(self.i18n.t("common.copy"), self)
        copy_action.setShortcut(QKeySequence.StandardKey.Copy)
        copy_action.triggered.connect(self.text_edit.copy)
        copy_action.setEnabled(self.text_edit.textCursor().hasSelection())
        context_menu.addAction(copy_action)

        # Select All action
        select_all_action = QAction(self.i18n.t("viewer.select_all"), self)
        select_all_action.setShortcut(QKeySequence.StandardKey.SelectAll)
        select_all_action.triggered.connect(self.text_edit.selectAll)
        context_menu.addAction(select_all_action)

        # Show menu at cursor position
        context_menu.exec(event.globalPos())

        logger.debug("Context menu shown")

    def update_language(self):
        """Update UI text with current language translations."""
        # Window title
        self.setWindowTitle(self.i18n.t("viewer.title", filename=self.task_data["file_name"]))

        # Metadata labels
        self.duration_label.setText(
            self.i18n.t("viewer.metadata.duration") + f": {self.duration_value}"
        )
        self.language_label.setText(
            self.i18n.t("viewer.metadata.language") + f": {self.language_value}"
        )
        self.engine_label.setText(self.i18n.t("viewer.metadata.engine") + f": {self.engine_value}")
        self.completed_label.setText(
            self.i18n.t("viewer.metadata.completed") + f": {self.completed_value}"
        )

        # Toolbar buttons
        if self.is_edit_mode:
            self.edit_button.setText(self.i18n.t("common.save"))
        else:
            self.edit_button.setText(self.i18n.t("common.edit"))

        self.export_button.setText(self.i18n.t("viewer.export"))
        self.copy_button.setText(self.i18n.t("viewer.copy_all"))
        self.search_button.setText(self.i18n.t("viewer.search"))

        # Update export menu items
        if hasattr(self, "export_txt_action"):
            self.export_txt_action.setText(self.i18n.t("viewer.export_txt"))
        if hasattr(self, "export_srt_action"):
            self.export_srt_action.setText(self.i18n.t("viewer.export_srt"))
        if hasattr(self, "export_md_action"):
            self.export_md_action.setText(self.i18n.t("viewer.export_md"))

        logger.debug("Language updated")

    def _on_setting_changed(self, key: str, value):
        """
        Handle setting changes.

        Args:
            key: Setting key that changed
            value: New value
        """
        if key == "ui.theme":
            # Theme changed, apply new theme
            self.apply_theme(value)
            logger.debug(f"Theme setting changed to: {value}")

    def apply_theme(self, theme: str = None):
        """
        Apply theme to the viewer.

        This method is called when the application theme changes.
        Since QSS is applied globally, most styling is automatic.
        We only need to update dynamic elements like search highlights.

        Args:
            theme: Theme name ('light', 'dark', or 'system')
                   If None, detects current theme from settings
        """
        try:
            # Detect current theme if not provided
            if theme is None and self.settings_manager:
                theme = self.settings_manager.get_setting("ui.theme")
                if theme == "system":
                    theme = self._detect_system_theme()

            # Update search widget highlight colors
            if hasattr(self, "search_widget") and self.search_widget:
                self.search_widget.update_highlight_color()

            logger.debug(f"Theme applied to transcript viewer: {theme}")

        except Exception as e:
            logger.error(f"Error applying theme: {e}")

    def _detect_system_theme(self) -> str:
        """
        Detect system theme preference.

        Returns:
            'light' or 'dark'
        """
        try:
            import platform

            system = platform.system()

            if system == "Darwin":  # macOS
                import subprocess

                result = subprocess.run(
                    ["defaults", "read", "-g", "AppleInterfaceStyle"],
                    capture_output=True,
                    text=True,
                )
                if result.returncode == 0 and "Dark" in result.stdout:
                    return "dark"
                return "light"

            elif system == "Windows":  # Windows
                try:
                    import winreg

                    registry = winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER)
                    key = winreg.OpenKey(
                        registry, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
                    )
                    value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
                    winreg.CloseKey(key)
                    return "light" if value == 1 else "dark"
                except Exception:
                    return "light"

            else:
                # Default to light for other systems
                return "light"

        except Exception as e:
            logger.warning(f"Could not detect system theme: {e}")
            return "light"

    def _save_window_state(self):
        """Save window geometry and state to settings."""
        try:
            # Save window geometry (position and size)
            self.settings.setValue("window/geometry", self.saveGeometry())

            # Note: QDialog doesn't have saveState() like QMainWindow
            # Window state (maximized, etc.) is handled by geometry

            logger.debug("Window state saved")
        except Exception as e:
            logger.error(f"Error saving window state: {e}")

    def _restore_window_state(self):
        """Restore window geometry and state from settings."""
        try:
            # Restore geometry
            geometry = self.settings.value("window/geometry")
            if geometry:
                self.restoreGeometry(geometry)
                logger.debug("Window geometry restored")

            # Note: QDialog doesn't have restoreState() like QMainWindow
            # Window state (maximized, etc.) is handled by geometry
        except Exception as e:
            logger.error(f"Error restoring window state: {e}")

    def closeEvent(self, event):
        """
        Handle window close event with cleanup.

        Args:
            event: QCloseEvent
        """
        # Cancel any ongoing file load
        if self.load_worker and self.load_worker.isRunning():
            self.load_worker.cancel()
            self.load_worker.wait()

        # Save window state before closing
        self._save_window_state()

        if self.is_modified:
            # Show unsaved changes dialog
            reply = QMessageBox.question(
                self,
                self.i18n.t("viewer.unsaved_title"),
                self.i18n.t("viewer.unsaved_message"),
                QMessageBox.StandardButton.Save
                | QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Save,
            )

            if reply == QMessageBox.StandardButton.Save:
                self.save_changes()
                self._cleanup_resources()
                event.accept()
            elif reply == QMessageBox.StandardButton.Discard:
                self._cleanup_resources()
                event.accept()
            else:
                event.ignore()
        else:
            self._cleanup_resources()
            event.accept()

    def _cleanup_resources(self):
        """
        Clean up resources before closing.

        Frees memory by clearing text content and undo stacks.
        """
        try:
            # Clear text content to free memory (only if text_edit exists)
            if self.text_edit is not None:
                self.text_edit.clear()

                # Clear undo/redo stacks
                self.text_edit.document().clearUndoRedoStacks()

            # Clear search widget cache
            if hasattr(self, "search_widget"):
                self.search_widget.clear_highlights()

            logger.debug("Resources cleaned up")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

    def _show_error_and_close(self, message: str):
        """
        Show error message and close dialog.

        Args:
            message: Error message to display
        """
        QMessageBox.critical(
            self.parent() if self.parent() else None, self.i18n.t("common.error"), message
        )
        self.close()
