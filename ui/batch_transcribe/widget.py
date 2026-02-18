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
Batch transcription widget.

Provides UI for importing audio files and managing transcription tasks.
"""

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Dict, Optional

from core.transcription.manager import TranscriptionManager
from ui.base_widgets import (
    BaseWidget,
    connect_button_with_callback,
    create_button,
    create_hbox,
    create_primary_button,
    create_vbox,
)
from ui.batch_transcribe.task_item import TaskItem
from ui.constants import PAGE_COMPACT_SPACING, PAGE_CONTENT_MARGINS, PAGE_LAYOUT_SPACING
from ui.qt_imports import (
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSize,
    Qt,
    QTimer,
    QVBoxLayout,
    QWidget,
    Signal,
)
from utils.i18n import I18nQtManager

if TYPE_CHECKING:
    from ui.batch_transcribe.transcript_viewer import TranscriptViewerDialog

logger = logging.getLogger("echonote.ui.batch_transcribe")


class BatchTranscribeWidget(BaseWidget):
    """
    Main widget for batch audio transcription.

    Provides file import, engine selection, and task queue management.
    """

    # Signal emitted when a task is added
    task_added = Signal(str)  # task_id
    # Internal signal for manager events (thread-safe bridge)
    manager_event = Signal(str, dict)

    _CLEAR_QUEUE_MAX_RETRIES = 10
    _CLEAR_QUEUE_RETRY_INTERVAL_MS = 300

    def __init__(
        self,
        transcription_manager: TranscriptionManager,
        i18n: I18nQtManager,
        model_manager=None,
        parent: Optional[QWidget] = None,
    ):
        """
        Initialize batch transcribe widget.

        Args:
            transcription_manager: Transcription manager instance
            i18n: Internationalization manager
            model_manager: Model manager instance (optional)
            parent: Parent widget
        """
        super().__init__(i18n, parent)

        self.transcription_manager = transcription_manager
        self.model_manager = model_manager

        # Task item widgets dictionary (task_id -> TaskItem)
        self.task_items: Dict[str, TaskItem] = {}

        # Open transcript viewer windows dictionary (task_id -> TranscriptViewerDialog)
        self.open_viewers: Dict[str, "TranscriptViewerDialog"] = {}

        # Download guide widget reference
        self.download_guide_widget: Optional[QWidget] = None
        self._clear_queue_in_progress = False

        # Setup UI
        self.setup_ui()

        # Connect language change signal
        self.i18n.language_changed.connect(self.update_translations)

        # Connect model manager signals if available
        if self.model_manager:
            self.model_manager.models_updated.connect(self._update_model_list)

        # Connect manager event signal
        self.manager_event.connect(self._handle_manager_event)

        # Register event listener with manager
        self.transcription_manager.add_listener(self._on_manager_event_threadsafe)

        # Initial load of tasks
        self._refresh_tasks()

        # Start transcription processing
        logger.info(self.i18n.t("logging.batch_transcribe.starting_task_processing"))
        try:
            self.transcription_manager.start_processing()
            logger.info(self.i18n.t("logging.batch_transcribe.processing_started"))
        except Exception as e:
            logger.error(f"Failed to start transcription processing: {e}")

        logger.info(self.i18n.t("logging.batch_transcribe.widget_initialized"))

    def setup_ui(self):
        """Set up the user interface."""
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(*PAGE_CONTENT_MARGINS)
        layout.setSpacing(PAGE_LAYOUT_SPACING)

        # Title
        self.title_label = QLabel(self.i18n.t("batch_transcribe.title"))
        self.title_label.setObjectName("page_title")
        layout.addWidget(self.title_label)

        # Toolbar
        toolbar_layout = create_hbox(spacing=PAGE_COMPACT_SPACING)

        # Import file button
        import_file_btn = QPushButton()
        import_file_btn.setObjectName("import_file_btn")
        connect_button_with_callback(import_file_btn, self._on_import_file)
        toolbar_layout.addWidget(import_file_btn)
        self.import_file_btn = import_file_btn

        # Import folder button
        import_folder_btn = QPushButton()
        import_folder_btn.setObjectName("import_folder_btn")
        connect_button_with_callback(import_folder_btn, self._on_import_folder)
        toolbar_layout.addWidget(import_folder_btn)
        self.import_folder_btn = import_folder_btn

        # Clear queue button
        clear_queue_btn = QPushButton()
        clear_queue_btn.setObjectName("clear_queue_btn")
        connect_button_with_callback(clear_queue_btn, self._on_clear_queue)
        toolbar_layout.addWidget(clear_queue_btn)
        self.clear_queue_btn = clear_queue_btn

        # Spacer
        toolbar_layout.addStretch()

        # Model selection (if model_manager is available)
        if self.model_manager:
            model_label = QLabel()
            model_label.setObjectName("model_label")
            toolbar_layout.addWidget(model_label)
            self.model_label = model_label

            model_combo = QComboBox()
            model_combo.setObjectName("model_combo")
            model_combo.setMinimumWidth(150)
            toolbar_layout.addWidget(model_combo)
            self.model_combo = model_combo

            # Populate with available models
            self._update_model_list()
        else:
            # Fallback to engine selection for backward compatibility
            engine_label = QLabel()
            engine_label.setObjectName("engine_label")
            toolbar_layout.addWidget(engine_label)
            self.engine_label = engine_label

            engine_combo = QComboBox()
            engine_combo.setObjectName("engine_combo")
            engine_combo.setMinimumWidth(150)
            # Populate with available engines
            self._populate_engines(engine_combo)
            toolbar_layout.addWidget(engine_combo)
            self.engine_combo = engine_combo

        layout.addLayout(toolbar_layout)

        # Task queue label
        queue_label = QLabel()
        queue_label.setObjectName("section_title")
        layout.addWidget(queue_label)
        self.queue_label = queue_label

        # Task list
        task_list = QListWidget()
        task_list.setObjectName("task_list")
        layout.addWidget(task_list)
        self.task_list = task_list

        # Update translations
        self.update_translations()

        logger.debug("Batch transcribe UI setup complete")

    def _populate_engines(self, combo: QComboBox):
        """
        Populate engine combo box with available engines.

        Args:
            combo: Combo box to populate
        """
        try:
            # Get current engine name
            if (
                self.transcription_manager
                and hasattr(self.transcription_manager, "speech_engine")
                and self.transcription_manager.speech_engine
            ):
                current_engine = self.transcription_manager.speech_engine.get_name()
                # Add current engine
                combo.addItem(current_engine)
                logger.debug(f"Populated engines: {current_engine}")
            else:
                # No engine available
                combo.addItem(self.i18n.t("ui_strings.batch_transcribe.no_engine_configured"))
                combo.setEnabled(False)
                logger.warning(self.i18n.t("logging.batch_transcribe.no_speech_engine"))
        except Exception as e:
            logger.error(f"Error populating engines: {e}")
            combo.addItem(self.i18n.t("ui_strings.batch_transcribe.error_loading_engines"))
            combo.setEnabled(False)

    def _update_model_list(self):
        """Update model combo box with downloaded models."""
        if not self.model_manager or not hasattr(self, "model_combo"):
            return

        try:
            # Save current selection
            current_model = self.model_combo.currentText()

            # Clear combo box
            self.model_combo.clear()

            # Get downloaded models
            downloaded_models = self.model_manager.get_downloaded_models()

            if not downloaded_models:
                # No models available
                self.model_combo.addItem(self.i18n.t("batch_transcribe.no_models_available"))
                self.model_combo.setEnabled(False)

                # Show download guide
                self._show_download_guide()

                logger.warning(self.i18n.t("logging.batch_transcribe.no_models_downloaded"))
            else:
                # Enable combo box
                self.model_combo.setEnabled(True)

                # Hide download guide if visible
                if self.download_guide_widget:
                    self.download_guide_widget.hide()

                # Add models to combo box
                for model in downloaded_models:
                    self.model_combo.addItem(model.name)

                # Restore previous selection if still available
                index = self.model_combo.findText(current_model)
                if index >= 0:
                    self.model_combo.setCurrentIndex(index)
                else:
                    # Select recommended model or first available model
                    try:
                        default_model = self.model_manager.recommend_model()
                        if default_model:
                            index = self.model_combo.findText(default_model)
                            if index >= 0:
                                self.model_combo.setCurrentIndex(index)
                    except Exception as e:
                        logger.debug(f"Could not get recommended model: {e}")

                logger.info(f"Updated model list: {len(downloaded_models)} models")

        except Exception as e:
            logger.error(f"Error updating model list: {e}")
            self.model_combo.addItem(
                self.i18n.t("ui_strings.batch_transcribe.error_loading_models")
            )
            self.model_combo.setEnabled(False)

    def _show_download_guide(self):
        """Show download guide widget when no models are available."""
        if self.download_guide_widget:
            # Already showing
            self.download_guide_widget.show()
            return

        try:
            # Create download guide widget
            guide_frame = QFrame()
            guide_frame.setObjectName("download_guide_frame")
            guide_frame.setFrameShape(QFrame.Shape.StyledPanel)

            guide_layout = QVBoxLayout(guide_frame)

            # Message label
            message_label = QLabel(self.i18n.t("batch_transcribe.no_models_message"))
            message_label.setWordWrap(True)
            message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            guide_layout.addWidget(message_label)

            # Download button
            download_btn = create_button(self.i18n.t("batch_transcribe.go_to_download"))
            download_btn = create_primary_button(download_btn.text())
            connect_button_with_callback(download_btn, self._on_go_to_download)
            guide_layout.addWidget(download_btn, alignment=Qt.AlignmentFlag.AlignCenter)

            # Add to main layout (after toolbar, before task list)
            main_layout = self.layout()
            # Insert after toolbar (index 2: title, toolbar, guide, queue_label, task_list)
            main_layout.insertWidget(2, guide_frame)

            self.download_guide_widget = guide_frame

            logger.debug("Download guide widget created")

        except Exception as e:
            logger.error(f"Error creating download guide: {e}")

    def _on_go_to_download(self):
        """Handle 'Go to Download' button click."""
        try:
            # Emit signal to switch to settings page
            # We need to access the main window to switch pages
            main_window = self.window()
            if hasattr(main_window, "switch_page"):
                main_window.switch_page("settings")

                # Try to switch to model management page in settings
                settings_widget = main_window.pages.get("settings")
                if settings_widget and hasattr(settings_widget, "switch_to_page"):
                    # Give it a moment to switch pages
                    QTimer.singleShot(
                        100, lambda: settings_widget.switch_to_page("model_management")
                    )

                logger.info(self.i18n.t("logging.batch_transcribe.navigating_to_model_management"))
            else:
                logger.warning(
                    self.i18n.t("logging.batch_transcribe.cannot_navigate_main_window_not_found")
                )

        except Exception as e:
            logger.error(f"Error navigating to download page: {e}")

    def update_translations(self):
        """Update all UI text with current language translations."""
        try:
            # Update title
            self.title_label.setText(self.i18n.t("batch_transcribe.title"))

            # Update buttons
            self.import_file_btn.setText(self.i18n.t("batch_transcribe.import_file"))
            self.import_folder_btn.setText(self.i18n.t("batch_transcribe.import_folder"))
            self.clear_queue_btn.setText(self.i18n.t("batch_transcribe.clear_queue"))

            # Update model/engine label
            if hasattr(self, "model_label"):
                self.model_label.setText(self.i18n.t("batch_transcribe.model") + ":")
            elif hasattr(self, "engine_label"):
                self.engine_label.setText(self.i18n.t("batch_transcribe.engine") + ":")

            self._update_queue_label()

            # Update download guide if visible
            if self.download_guide_widget and self.download_guide_widget.isVisible():
                # Recreate the guide with updated translations
                self.download_guide_widget.hide()
                self.download_guide_widget.deleteLater()
                self.download_guide_widget = None
                self._show_download_guide()

            logger.debug("Translations updated")

        except Exception as e:
            logger.error(f"Error updating translations: {e}")

    def _update_queue_label(self):
        """Update queue label with current task count."""
        task_count = self.task_list.count()
        self.queue_label.setText(
            self.i18n.t("batch_transcribe.task_queue")
            + " "
            + self.i18n.t("batch_transcribe.tasks_count", count=task_count)
        )

    def _on_import_file(self):
        """Handle import file button click."""
        try:
            # Open file dialog
            file_filter = (
                "Audio/Video Files (*.mp3 *.wav *.m4a *.flac *.ogg "
                "*.opus *.mp4 *.avi *.mkv *.mov *.webm);;All Files (*)"
            )
            file_paths, _ = QFileDialog.getOpenFileNames(
                self, self.i18n.t("batch_transcribe.import_file"), "", file_filter
            )

            if not file_paths:
                return

            # Add tasks for each file
            for file_path in file_paths:
                self._add_task(file_path)

            logger.info(f"Imported {len(file_paths)} files")

        except Exception as e:
            logger.error(f"Error importing files: {e}")
            self._show_error(self.i18n.t("errors.unknown_error"), str(e))

    def _on_import_folder(self):
        """Handle import folder button click."""
        try:
            # Open folder dialog
            folder_path = QFileDialog.getExistingDirectory(
                self, self.i18n.t("batch_transcribe.import_folder"), ""
            )

            if not folder_path:
                return

            # Add tasks from folder with the same options used by single-file import
            options = self._build_task_options()
            task_ids = self.transcription_manager.add_tasks_from_folder(folder_path, options)
            logger.info(f"Added {len(task_ids)} tasks from folder")

            logger.info(f"Importing from folder: {folder_path}")

        except Exception as e:
            logger.error(f"Error importing folder: {e}")
            self._show_error(self.i18n.t("errors.unknown_error"), str(e))

    def _on_clear_queue(self):
        """Handle clear queue button click."""
        try:
            if self._clear_queue_in_progress:
                logger.info("Clear queue already in progress, ignoring duplicate request")
                return

            # Confirm with user
            reply = QMessageBox.question(
                self,
                self.i18n.t("batch_transcribe.clear_queue"),
                self.i18n.t("batch_transcribe.confirm_clear_queue"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )

            if reply == QMessageBox.StandardButton.Yes:
                self._clear_queue_in_progress = True
                self.clear_queue_btn.setEnabled(False)

                # Stop all running/pending tasks first to avoid race conditions
                self.transcription_manager.stop_all_tasks()

                self._clear_queue_with_retry(attempt=1)

        except Exception as e:
            logger.error(f"Error clearing queue: {e}")
            self._clear_queue_in_progress = False
            self.clear_queue_btn.setEnabled(True)
            self._show_error(self.i18n.t("errors.unknown_error"), str(e))

    def _clear_queue_with_retry(self, attempt: int):
        """Delete queue tasks with short retries to handle in-flight cancellation."""
        deleted_task_ids = set()
        remaining_processing_ids = []

        for task_data in self.transcription_manager.get_all_tasks():
            task_id = task_data["id"]
            if self.transcription_manager.delete_task(task_id):
                deleted_task_ids.add(task_id)
            elif task_data.get("status") == "processing":
                remaining_processing_ids.append(task_id)

        for task_id in list(deleted_task_ids):
            self._remove_task_item(task_id)

        if remaining_processing_ids and attempt < self._CLEAR_QUEUE_MAX_RETRIES:
            logger.info(
                "Clear queue retry %d/%d for %d processing task(s)",
                attempt,
                self._CLEAR_QUEUE_MAX_RETRIES,
                len(remaining_processing_ids),
            )
            QTimer.singleShot(
                self._CLEAR_QUEUE_RETRY_INTERVAL_MS,
                lambda: self._clear_queue_with_retry(attempt + 1),
            )
            return

        if remaining_processing_ids:
            logger.warning(
                "Clear queue partial completion, %d task(s) still processing after retries: %s",
                len(remaining_processing_ids),
                ", ".join(remaining_processing_ids),
            )
            self._notify_user(
                self.i18n.t(
                    "batch_transcribe.feedback.clear_queue_partial",
                    count=len(remaining_processing_ids),
                )
            )

        self.transcription_manager.start_processing()
        self._clear_queue_in_progress = False
        self.clear_queue_btn.setEnabled(True)
        self._update_queue_label()
        logger.info(self.i18n.t("logging.batch_transcribe.task_queue_cleared"))

    def _add_task(self, file_path: str):
        """
        Add a transcription task.

        Args:
            file_path: Path to audio/video file
        """
        try:
            options = self._build_task_options()

            # Add task to transcription manager
            task_id = self.transcription_manager.add_task(file_path, options)
            logger.info(f"Task added: {task_id}")

        except Exception as e:
            logger.error(f"Error adding task: {e}")
            self._show_error(self.i18n.t("errors.unknown_error"), str(e))

    def _build_task_options(self) -> Dict[str, str]:
        """Build task options from current UI selection."""
        options: Dict[str, str] = {}

        if self.model_manager and hasattr(self, "model_combo"):
            selected_model = self.model_combo.currentText()

            if selected_model and selected_model != self.i18n.t("batch_transcribe.no_models_available"):
                model_info = self.model_manager.get_model(selected_model)

                if not model_info or not model_info.is_downloaded:
                    raise ValueError(
                        self.i18n.t(
                            "batch_transcribe.model_not_available", model=selected_model
                        )
                    )

                options["model_name"] = selected_model
                options["model_path"] = model_info.local_path
                logger.debug(f"Using model {selected_model} at {model_info.local_path}")

        return options

    def _refresh_tasks(self):
        """Refresh task list from transcription manager."""
        try:
            # Get all tasks from manager
            all_tasks = self.transcription_manager.get_all_tasks()

            # Update existing task items and add new ones
            current_task_ids = set(self.task_items.keys())
            new_task_ids = {task["id"] for task in all_tasks}

            # Remove tasks that no longer exist
            for task_id in current_task_ids - new_task_ids:
                self._remove_task_item(task_id)

            # Add or update tasks
            for task_data in all_tasks:
                task_id = task_data["id"]

                if task_id in self.task_items:
                    # Update existing task item
                    if task_data.get("status") == "processing":
                        logger.debug(
                            f"Updating task {task_id}: "
                            f"progress={task_data.get('progress', 0):.1f}%"
                        )
                    self.task_items[task_id].update_task_data(task_data)
                else:
                    # Add new task item
                    self._add_task_item(task_data)

            # Keep periodic refresh lightweight: only update dynamic queue count.
            self._update_queue_label()
            self._set_tasks_pause_state(self.transcription_manager.is_paused())

        except Exception as e:
            logger.error(f"Error refreshing tasks: {e}")

    def _add_task_item(self, task_data: Dict):
        """
        Add a task item widget to the list.

        Args:
            task_data: Task information dictionary
        """
        try:
            task_id = task_data["id"]

            # Create task item widget
            task_item = TaskItem(task_data, self.i18n)

            # Connect signals
            task_item.start_clicked.connect(self._on_task_start)
            task_item.pause_clicked.connect(self._on_task_pause)
            task_item.cancel_clicked.connect(self._on_task_cancel)
            task_item.delete_clicked.connect(self._on_task_delete)
            task_item.view_clicked.connect(self._on_task_view)
            task_item.export_clicked.connect(self._on_task_export)
            task_item.retry_clicked.connect(self._on_task_retry)

            # Add to list widget
            list_item = QListWidgetItem(self.task_list)
            # Set a fixed size hint to prevent overlapping
            list_item.setSizeHint(QSize(800, 160))
            self.task_list.addItem(list_item)
            self.task_list.setItemWidget(list_item, task_item)

            # Store reference
            self.task_items[task_id] = task_item

            # Ensure pause button reflects current processing state
            task_item.set_processing_paused(self.transcription_manager.is_paused())

            logger.debug(f"Added task item for task {task_id}")

        except Exception as e:
            logger.error(f"Error adding task item: {e}")

    def _remove_task_item(self, task_id: str):
        """
        Remove a task item widget from the list.

        Args:
            task_id: Task identifier
        """
        try:
            if task_id not in self.task_items:
                return

            # Find and remove list item
            for i in range(self.task_list.count()):
                item = self.task_list.item(i)
                widget = self.task_list.itemWidget(item)
                if isinstance(widget, TaskItem) and widget.task_id == task_id:
                    self.task_list.takeItem(i)
                    break

            # Remove from dictionary
            del self.task_items[task_id]

            logger.debug(f"Removed task item for task {task_id}")

        except Exception as e:
            logger.error(f"Error removing task item: {e}")

    def _on_task_start(self, task_id: str):
        """Handle task start button click."""
        try:
            # Task will start automatically when added to queue
            logger.info(f"Start requested for task {task_id}")
        except Exception as e:
            logger.error(f"Error starting task: {e}")

    def _on_task_pause(self, task_id: str):
        """Handle task pause button click."""
        try:
            logger.debug(f"Pause toggle requested by task {task_id}")

            if self.transcription_manager.is_paused():
                self.transcription_manager.resume_processing()
                self._set_tasks_pause_state(False)
                message = self.i18n.t("batch_transcribe.feedback.resumed")
            else:
                self.transcription_manager.pause_processing()
                self._set_tasks_pause_state(True)
                message = self.i18n.t("batch_transcribe.feedback.paused")

            self._notify_user(message)
        except Exception as e:
            logger.error(f"Error toggling pause state: {e}")
            self._show_error(self.i18n.t("errors.unknown_error"), str(e))

    def _on_task_cancel(self, task_id: str):
        """Handle task cancel button click."""
        try:
            cancelled = self.transcription_manager.cancel_task(task_id)
            if cancelled:
                logger.info(f"Cancelled task {task_id}")
            else:
                logger.warning(f"Failed to cancel task {task_id}")
        except Exception as e:
            logger.error(f"Error cancelling task: {e}")

    def _on_task_delete(self, task_id: str):
        """Handle task delete button click."""
        try:
            # Confirm deletion
            reply = QMessageBox.question(
                self,
                self.i18n.t("common.delete"),
                self.i18n.t("batch_transcribe.confirm_delete_task"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )

            if reply == QMessageBox.StandardButton.Yes:
                deleted = self.transcription_manager.delete_task(task_id)
                if deleted:
                    self._remove_task_item(task_id)
                    logger.info(f"Deleted task {task_id}")
                else:
                    logger.warning(f"Failed to delete task {task_id}")
                    self._show_error(
                        self.i18n.t("common.warning"),
                        self.i18n.t("batch_transcribe.delete_processing_not_allowed"),
                    )

        except Exception as e:
            logger.error(f"Error deleting task: {e}")

    def _on_task_view(self, task_id: str):
        """Handle task view button click."""
        try:
            # Check if viewer for this task is already open
            if task_id in self.open_viewers:
                # Activate existing window
                existing_viewer = self.open_viewers[task_id]
                existing_viewer.raise_()
                existing_viewer.activateWindow()
                logger.info(f"Activated existing viewer for task {task_id}")
                return

            # Import here to avoid circular imports
            from ui.batch_transcribe.transcript_viewer import TranscriptViewerDialog

            # Get settings manager and db connection from managers
            settings_manager = None
            db_connection = None
            if hasattr(self, "parent") and self.parent():
                main_window = self.window()
                if hasattr(main_window, "managers"):
                    settings_manager = main_window.managers.get("settings_manager")

            # Get db connection from transcription manager
            db_connection = self.transcription_manager.db

            # Create and show transcript viewer dialog
            viewer = TranscriptViewerDialog(
                task_id,
                self.transcription_manager,
                db_connection,
                self.i18n,
                settings_manager=settings_manager,
                parent=self,
            )

            # Store reference to open viewer
            self.open_viewers[task_id] = viewer

            # Connect to viewer's finished signal to remove from dictionary
            viewer.finished.connect(lambda: self._on_viewer_closed(task_id))

            # Show viewer as non-modal window
            viewer.show()

            logger.info(f"Opened transcript viewer for task {task_id}")
        except Exception as e:
            logger.error(f"Error viewing task: {e}")
            self._show_error(self.i18n.t("common.error"), str(e))

    def _on_viewer_closed(self, task_id: str):
        """
        Handle viewer window closed event.

        Args:
            task_id: Task ID of the closed viewer
        """
        try:
            if task_id in self.open_viewers:
                del self.open_viewers[task_id]
                logger.info(f"Closed viewer for task {task_id}")
        except Exception as e:
            logger.error(f"Error removing viewer reference: {e}")

    def _on_manager_event_threadsafe(self, event_type: str, data: Dict):
        """
        Handle manager event from background thread.
        
        Emits signal to handle event on main UI thread.
        
        Args:
            event_type: Type of event
            data: Event data
        """
        try:
            self.manager_event.emit(event_type, data)
        except Exception as e:
            logger.error(f"Error emitting manager event: {e}")

    def _handle_manager_event(self, event_type: str, data: Dict):
        """
        Handle manager event on main thread.
        
        Args:
            event_type: Type of event
            data: Event data
        """
        try:
            if event_type == "task_added":
                task_id = data["id"]
                if task_id not in self.task_items:
                    self._add_task_item(data)
                    self._update_queue_label()
                    
            elif event_type == "task_updated":
                task_id = data["id"]
                if task_id in self.task_items:
                    self.task_items[task_id].update_task_data(data)
                elif task_id not in self.task_items:
                    # Might happen if we missed the add event or it was filtered
                    # We can try to fetch the full task data or ignore
                    pass
                    
            elif event_type == "task_deleted":
                task_id = data["id"]
                self._remove_task_item(task_id)
                self._update_queue_label()
                
            elif event_type == "processing_paused":
                self._set_tasks_pause_state(True)
                
            elif event_type == "processing_resumed":
                self._set_tasks_pause_state(False)
                
        except Exception as e:
            logger.error(f"Error handling manager event {event_type}: {e}")

    def _on_task_export(self, task_id: str):
        """Handle task export button click."""
        try:
            # Get task data
            task_data = self.transcription_manager.get_task_status(task_id)
            if not task_data:
                return

            # Open save dialog
            default_name = task_data["file_name"].rsplit(".", 1)[0]
            file_filter = self.i18n.t("batch_transcribe.export_file_filter")
            file_path, selected_filter = QFileDialog.getSaveFileName(
                self,
                self.i18n.t("batch_transcribe.actions.export"),
                default_name,
                file_filter,
            )

            if not file_path:
                return

            # Determine format from extension first, then selected filter pattern.
            file_extension = Path(file_path).suffix.lower()
            if file_extension in {".txt", ".srt", ".md"}:
                output_format = file_extension.lstrip(".")
            elif "*.srt" in selected_filter:
                output_format = "srt"
                file_path = f"{file_path}.srt"
            elif "*.md" in selected_filter:
                output_format = "md"
                file_path = f"{file_path}.md"
            else:
                output_format = "txt"
                file_path = f"{file_path}.txt"

            # Export
            self.transcription_manager.export_result(task_id, output_format, file_path)

            self.show_info(
                self.i18n.t("common.success"),
                self.i18n.t("batch_transcribe.export_success", path=file_path),
            )

            logger.info(f"Exported task {task_id} to {file_path}")

        except Exception as e:
            logger.error(f"Error exporting task: {e}")
            self._show_error(self.i18n.t("errors.unknown_error"), str(e))

    def _on_task_retry(self, task_id: str):
        """Handle task retry button click."""
        try:
            retried = self.transcription_manager.retry_task(task_id)
            if retried:
                logger.info(f"Retrying task {task_id}")
            else:
                logger.warning(f"Failed to retry task {task_id}")
        except Exception as e:
            logger.error(f"Error retrying task: {e}")

    def _show_error(self, title: str, message: str):
        """
        Show error message dialog.

        Args:
            title: Error title
            message: Error message
        """
        self.show_error(title, message)

    def _set_tasks_pause_state(self, paused: bool):
        """Update pause button state for all task items."""
        for task_item in self.task_items.values():
            task_item.set_processing_paused(paused)

    def _notify_user(self, message: str):
        """Display feedback to the user and log it."""
        status_bar = None
        main_window = self.window()

        if hasattr(main_window, "statusBar"):
            try:
                status_bar = main_window.statusBar()
            except Exception:
                status_bar = None

        if status_bar:
            status_bar.showMessage(message, 5000)

        logger.info(message)

    def close_all_viewers(self):
        """Close all open transcript viewer windows."""
        try:
            # Close all open viewers
            for task_id, viewer in list(self.open_viewers.items()):
                try:
                    viewer.close()
                except Exception as e:
                    logger.error(f"Error closing viewer for task {task_id}: {e}")

            # Clear the dictionary
            self.open_viewers.clear()

            logger.info(self.i18n.t("logging.batch_transcribe.closed_all_transcript_viewers"))
        except Exception as e:
            logger.error(f"Error closing all viewers: {e}")
