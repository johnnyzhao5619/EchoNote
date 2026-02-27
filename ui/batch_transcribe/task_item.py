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
Task item widget for batch transcription.

Displays individual transcription task information and controls.
"""

import logging
from typing import Any, Dict, Optional

from core.qt_imports import (
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    Qt,
    QVBoxLayout,
    QWidget,
    Signal,
)

# Import base widget
from ui.base_widgets import BaseWidget, create_hbox
from ui.common.style_utils import set_widget_state
from ui.constants import (
    ROLE_TASK_ACTION_CANCEL,
    ROLE_TASK_ACTION_DELETE,
    ROLE_TASK_ACTION_EXPORT,
    ROLE_TASK_ACTION_PAUSE,
    ROLE_TASK_ACTION_RETRY,
    ROLE_TASK_ACTION_START,
    ROLE_TASK_ACTION_VIEW,
    ROLE_TASK_ERROR,
    ROLE_TASK_FILENAME,
    ROLE_TASK_INFO,
    ROLE_TASK_ITEM,
    ROLE_TASK_STATUS,
    TASK_ITEM_MIN_HEIGHT,
)
from utils.i18n import I18nQtManager

logger = logging.getLogger("echonote.ui.batch_transcribe.task_item")



class TaskItem(BaseWidget):
    """
    Widget displaying a single transcription task.

    Shows task information, progress, and action buttons.
    """

    # Signals
    start_clicked = Signal(str)  # task_id
    pause_clicked = Signal(str)  # task_id
    cancel_clicked = Signal(str)  # task_id
    delete_clicked = Signal(str)  # task_id
    view_clicked = Signal(str)  # task_id
    export_clicked = Signal(str)  # task_id
    retry_clicked = Signal(str)  # task_id

    def __init__(
        self, task_data: Dict[str, Any], i18n: I18nQtManager, parent: Optional[QWidget] = None
    ):
        """
        Initialize task item widget.

        Args:
            task_data: Task information dictionary
            i18n: Internationalization manager
            parent: Parent widget
        """
        super().__init__(i18n, parent)

        self.task_data = task_data
        self.task_id = task_data["id"]
        self.i18n = i18n
        self._processing_paused = False

        # Setup UI
        self.setup_ui()

        # Update display
        self.update_display()

        # Connect language change signal
        self.i18n.language_changed.connect(self.update_translations)

        logger.debug(f"Task item created for task {self.task_id}")

    def setup_ui(self):
        """Set up the user interface."""
        # Main layout
        layout = QVBoxLayout(self)

        # Set semantic properties for theming
        self.setProperty("role", ROLE_TASK_ITEM)

        # Create filename and status labels
        self.filename_label = QLabel()
        self.filename_label.setObjectName("filename_label")
        self.filename_label.setProperty("role", ROLE_TASK_FILENAME)

        self.status_label = QLabel()

        # Create task header
        top_layout = create_hbox(spacing=10)
        top_layout.addWidget(self.filename_label)
        top_layout.addStretch()
        top_layout.addWidget(self.status_label)
        layout.addLayout(top_layout)

        # Create info label and row
        self.info_label = QLabel()
        self.info_label.setObjectName("info_label")
        self.info_label.setProperty("role", ROLE_TASK_INFO)

        info_layout = create_hbox(spacing=15)
        info_layout.addWidget(self.info_label)
        info_layout.addStretch()

        layout.addLayout(info_layout)

        # Progress bar (only shown when processing)
        progress_bar = QProgressBar()
        progress_bar.setMinimum(0)
        progress_bar.setMaximum(100)
        progress_bar.setTextVisible(True)
        progress_bar.setVisible(False)
        layout.addWidget(progress_bar)
        self.progress_bar = progress_bar

        # Error message (only shown when failed)
        error_label = QLabel()
        error_label.setProperty("role", ROLE_TASK_ERROR)
        error_label.setWordWrap(True)
        error_label.setVisible(False)
        layout.addWidget(error_label)
        self.error_label = error_label

        # Action buttons row
        actions_layout = create_hbox(spacing=8)

        # Create action buttons
        self.start_btn = QPushButton()
        self.start_btn.setProperty("role", ROLE_TASK_ACTION_START)
        actions_layout.addWidget(self.start_btn)

        self.pause_btn = QPushButton()
        self.pause_btn.setProperty("role", ROLE_TASK_ACTION_PAUSE)
        self.pause_btn.setVisible(False)
        actions_layout.addWidget(self.pause_btn)

        self.cancel_btn = QPushButton()
        self.cancel_btn.setProperty("role", ROLE_TASK_ACTION_CANCEL)
        actions_layout.addWidget(self.cancel_btn)

        self.delete_btn = QPushButton()
        self.delete_btn.setProperty("role", ROLE_TASK_ACTION_DELETE)
        actions_layout.addWidget(self.delete_btn)

        self.view_btn = QPushButton()
        self.view_btn.setProperty("role", ROLE_TASK_ACTION_VIEW)
        self.view_btn.setVisible(False)
        actions_layout.addWidget(self.view_btn)

        self.export_btn = QPushButton()
        self.export_btn.setProperty("role", ROLE_TASK_ACTION_EXPORT)
        self.export_btn.setVisible(False)
        actions_layout.addWidget(self.export_btn)

        self.retry_btn = QPushButton()
        self.retry_btn.setProperty("role", ROLE_TASK_ACTION_RETRY)
        self.retry_btn.setVisible(False)
        actions_layout.addWidget(self.retry_btn)

        # Connect all task action buttons using helper
        from ui.signal_helpers import connect_task_action_buttons

        connect_task_action_buttons(
            self.start_btn,
            self.pause_btn,
            self.cancel_btn,
            self.delete_btn,
            self.view_btn,
            self.export_btn,
            self.retry_btn,
            self.task_id,
            self.start_clicked,
            self.pause_clicked,
            self.cancel_clicked,
            self.delete_clicked,
            self.view_clicked,
            self.export_clicked,
            self.retry_clicked,
        )

        actions_layout.addStretch()

        layout.addLayout(actions_layout)

        # Update translations
        self.update_translations()

        # Set minimum height to ensure all content is visible
        self.setMinimumHeight(TASK_ITEM_MIN_HEIGHT)

        logger.debug("Task item UI setup complete")

    def update_translations(self):
        """Update all UI text with current language translations."""
        try:
            # Update button labels
            self.start_btn.setText(self.i18n.t("batch_transcribe.actions.start"))
            self._update_pause_button_text()
            self.cancel_btn.setText(self.i18n.t("batch_transcribe.actions.cancel"))
            self.delete_btn.setText(self.i18n.t("common.delete"))
            self.view_btn.setText(self.i18n.t("batch_transcribe.actions.view"))
            self.export_btn.setText(self.i18n.t("batch_transcribe.actions.export"))
            self.retry_btn.setText(self.i18n.t("batch_transcribe.actions.retry"))

            # Update textual elements that depend on translations
            self._update_status_label()
            self._update_filename_label()
            self._update_info_label()
            self._update_error_label()

            logger.debug("Task item translations updated")

        except Exception as e:
            logger.error(f"Error updating translations: {e}")

    def sizeHint(self):
        """Return the recommended size for this widget."""
        from core.qt_imports import QSize

        # Return a fixed size to ensure consistent layout
        return QSize(800, 150)

    def update_display(self):
        """Update display based on current task data."""
        try:
            # Update filename
            self._update_filename_label()

            # Update info
            self._update_info_label()

            # Update status
            self._update_status_label()

            # Update progress bar
            status = self.task_data.get("status", "pending")
            progress = self.task_data.get("progress", 0)

            if status == "processing":
                self.progress_bar.setVisible(True)
                self.progress_bar.setValue(int(progress))
                logger.debug(f"Task {self.task_id} progress bar set to {int(progress)}%")
            else:
                self.progress_bar.setVisible(False)

            # Update error message
            self._update_error_label()

            # Update button visibility based on status
            self._update_button_visibility(status)

            logger.debug(f"Task item display updated for {self.task_id}")

        except Exception as e:
            logger.error(f"Error updating display: {e}")

    def _update_status_label(self):
        """Update status label with translated text and styling."""
        status = self.task_data.get("status", "pending")

        # Get translated status text
        status_key = f"batch_transcribe.status.{status}"
        status_text = self.i18n.t(status_key)

        # Set semantic properties for theming
        self.status_label.setProperty("role", ROLE_TASK_STATUS)

        if status == "pending":
            set_widget_state(self.status_label, "pending")
        elif status == "processing":
            set_widget_state(self.status_label, "processing")
        elif status == "completed":
            set_widget_state(self.status_label, "completed")
        elif status == "failed":
            set_widget_state(self.status_label, "failed")
        else:
            set_widget_state(self.status_label, "cancelled")

        self.status_label.setText(status_text)

    def _update_filename_label(self):
        """Update filename label with fallback translation if needed."""
        file_name = self.task_data.get("file_name")
        if not file_name:
            file_name = self.i18n.t("batch_transcribe.info.unknown")
        self.filename_label.setText(file_name)

    def _update_info_label(self):
        """Update informational label with translated text."""
        info_parts = []

        task_kind = self.task_data.get("task_kind")
        if task_kind == "translation":
            info_parts.append(self.i18n.t("batch_transcribe.task_kind_translation"))
        else:
            info_parts.append(self.i18n.t("batch_transcribe.task_kind_transcription"))

        file_size = self.task_data.get("file_size")
        if file_size:
            size_mb = file_size / (1024 * 1024)
            info_parts.append(self.i18n.t("batch_transcribe.info.size", size=f"{size_mb:.1f} MB"))

        duration = self.task_data.get("audio_duration")
        if duration:
            minutes = int(duration // 60)
            seconds = int(duration % 60)
            info_parts.append(
                self.i18n.t("batch_transcribe.info.duration", duration=f"{minutes}:{seconds:02d}")
            )

        language = self.task_data.get("language")
        if language:
            info_parts.append(self.i18n.t("batch_transcribe.info.language", language=language))

        quality_note = (self.task_data.get("quality_note") or "").strip()
        if quality_note:
            info_parts.append(quality_note)

        self.info_label.setText(" | ".join(info_parts))

    def _update_error_label(self):
        """Update error label text and visibility with translations."""
        status = self.task_data.get("status", "pending")
        error_msg = self.task_data.get("error_message")
        if error_msg and status == "failed":
            self.error_label.setText(self.i18n.t("batch_transcribe.info.error", error=error_msg))
            self.error_label.setVisible(True)
        else:
            self.error_label.setVisible(False)

    def _update_button_visibility(self, status: str):
        """
        Update button visibility based on task status.

        Args:
            status: Task status
        """
        # Hide all buttons first
        self.start_btn.setVisible(False)
        self.pause_btn.setVisible(False)
        self.cancel_btn.setVisible(False)
        self.delete_btn.setVisible(False)
        self.view_btn.setVisible(False)
        self.export_btn.setVisible(False)
        self.retry_btn.setVisible(False)

        # Show buttons based on status
        if status == "pending":
            # Tasks start automatically when added to queue
            # Only show cancel and delete buttons
            self.cancel_btn.setVisible(True)
            self.delete_btn.setVisible(True)
        elif status == "processing":
            self.cancel_btn.setVisible(True)
            self.pause_btn.setVisible(True)
            self._update_pause_button_text()
        elif status == "completed":
            self.view_btn.setVisible(True)
            self.export_btn.setVisible(True)
            self.delete_btn.setVisible(True)
        elif status == "failed":
            self.retry_btn.setVisible(True)
            self.delete_btn.setVisible(True)
        elif status == "cancelled":
            self.delete_btn.setVisible(True)
        else:
            # Unknown terminal states should still allow cleanup from UI.
            self.delete_btn.setVisible(True)

    def set_processing_paused(self, paused: bool):
        """Update pause/resume state for processing tasks."""
        if self._processing_paused == paused:
            return

        self._processing_paused = paused
        self._update_pause_button_text()

        status = self.task_data.get("status", "pending")
        if status == "processing":
            self.pause_btn.setVisible(True)

    def _update_pause_button_text(self):
        """Update pause button text based on processing state."""
        action_key = (
            "batch_transcribe.actions.resume"
            if self._processing_paused
            else "batch_transcribe.actions.pause"
        )
        try:
            self.pause_btn.setText(self.i18n.t(action_key))
        except Exception:
            # Fallback to key-based label when translation manager is unavailable.
            fallback_text = action_key.rsplit(".", maxsplit=1)[-1].replace("_", " ").title()
            self.pause_btn.setText(fallback_text)

    def update_task_data(self, task_data: Dict[str, Any]):
        """
        Update task data and refresh display.

        Args:
            task_data: New task data
        """
        if not task_data:
            return

        # Manager events can be partial (e.g. progress-only updates).
        # Merge payload to avoid dropping stable metadata like file_name.
        merged = dict(self.task_data)
        merged.update(task_data)
        self.task_data = merged
        self.update_display()

    def contextMenuEvent(self, event):
        """
        Handle right-click context menu.

        Args:
            event: Context menu event
        """
        try:
            # Create context menu
            menu = QMenu(self)

            status = self.task_data.get("status", "pending")

            # Add actions based on status
            if status == "pending":
                start_action = QAction(self.i18n.t("batch_transcribe.actions.start"), self)
                start_action.triggered.connect(lambda: self.start_clicked.emit(self.task_id))
                menu.addAction(start_action)

            elif status == "processing":
                cancel_action = QAction(self.i18n.t("batch_transcribe.actions.cancel"), self)
                cancel_action.triggered.connect(lambda: self.cancel_clicked.emit(self.task_id))
                menu.addAction(cancel_action)

            elif status == "completed":
                view_action = QAction(self.i18n.t("batch_transcribe.actions.view"), self)
                view_action.triggered.connect(lambda: self.view_clicked.emit(self.task_id))
                menu.addAction(view_action)

                export_action = QAction(self.i18n.t("batch_transcribe.actions.export"), self)
                export_action.triggered.connect(lambda: self.export_clicked.emit(self.task_id))
                menu.addAction(export_action)

            elif status == "failed":
                retry_action = QAction(self.i18n.t("batch_transcribe.actions.retry"), self)
                retry_action.triggered.connect(lambda: self.retry_clicked.emit(self.task_id))
                menu.addAction(retry_action)

            # Always show delete
            menu.addSeparator()
            delete_action = QAction(self.i18n.t("common.delete"), self)
            delete_action.triggered.connect(lambda: self.delete_clicked.emit(self.task_id))
            menu.addAction(delete_action)

            # Show menu
            menu.exec(event.globalPos())

        except Exception as e:
            logger.error(f"Error showing context menu: {e}")
