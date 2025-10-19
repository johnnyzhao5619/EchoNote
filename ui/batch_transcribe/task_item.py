"""
Task item widget for batch transcription.

Displays individual transcription task information and controls.
"""

import logging
from typing import Optional, Dict, Any

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QProgressBar, QMenu
)
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QAction

from utils.i18n import I18nQtManager


logger = logging.getLogger('echonote.ui.batch_transcribe.task_item')


class TaskItem(QWidget):
    """
    Widget displaying a single transcription task.

    Shows task information, progress, and action buttons.
    """

    # Signals
    start_clicked = pyqtSignal(str)  # task_id
    pause_clicked = pyqtSignal(str)  # task_id
    cancel_clicked = pyqtSignal(str)  # task_id
    delete_clicked = pyqtSignal(str)  # task_id
    view_clicked = pyqtSignal(str)  # task_id
    export_clicked = pyqtSignal(str)  # task_id
    retry_clicked = pyqtSignal(str)  # task_id

    def __init__(
        self,
        task_data: Dict[str, Any],
        i18n: I18nQtManager,
        parent: Optional[QWidget] = None
    ):
        """
        Initialize task item widget.

        Args:
            task_data: Task information dictionary
            i18n: Internationalization manager
            parent: Parent widget
        """
        super().__init__(parent)

        self.task_data = task_data
        self.task_id = task_data['id']
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
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # Set background and border
        self.setStyleSheet("""
            TaskItem {
                background-color: #f5f5f5;
                border: 1px solid #ddd;
                border-radius: 5px;
            }
            TaskItem:hover {
                background-color: #eeeeee;
            }
        """)

        # Top row: filename and status
        top_layout = QHBoxLayout()
        top_layout.setSpacing(10)

        # File icon and name
        filename_label = QLabel()
        filename_label.setObjectName("filename_label")
        filename_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        top_layout.addWidget(filename_label)
        self.filename_label = filename_label

        # Spacer
        top_layout.addStretch()

        # Status label
        status_label = QLabel()
        status_label.setObjectName("status_label")
        top_layout.addWidget(status_label)
        self.status_label = status_label

        layout.addLayout(top_layout)

        # Info row: size, duration, language
        info_layout = QHBoxLayout()
        info_layout.setSpacing(15)

        info_label = QLabel()
        info_label.setObjectName("info_label")
        info_label.setStyleSheet("color: #666; font-size: 12px;")
        info_layout.addWidget(info_label)
        self.info_label = info_label

        info_layout.addStretch()

        layout.addLayout(info_layout)

        # Progress bar (only shown when processing)
        progress_bar = QProgressBar()
        progress_bar.setObjectName("progress_bar")
        progress_bar.setMinimum(0)
        progress_bar.setMaximum(100)
        progress_bar.setTextVisible(True)
        progress_bar.setVisible(False)
        layout.addWidget(progress_bar)
        self.progress_bar = progress_bar

        # Error message (only shown when failed)
        error_label = QLabel()
        error_label.setObjectName("error_label")
        error_label.setStyleSheet("color: #d32f2f; font-size: 12px;")
        error_label.setWordWrap(True)
        error_label.setVisible(False)
        layout.addWidget(error_label)
        self.error_label = error_label

        # Action buttons row
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(8)

        # Start button
        start_btn = QPushButton()
        start_btn.setObjectName("start_btn")
        start_btn.clicked.connect(lambda: self.start_clicked.emit(
            self.task_id
        ))
        actions_layout.addWidget(start_btn)
        self.start_btn = start_btn

        # Pause button
        pause_btn = QPushButton()
        pause_btn.setObjectName("pause_btn")
        pause_btn.clicked.connect(lambda: self.pause_clicked.emit(
            self.task_id
        ))
        pause_btn.setVisible(False)
        actions_layout.addWidget(pause_btn)
        self.pause_btn = pause_btn

        # Cancel button
        cancel_btn = QPushButton()
        cancel_btn.setObjectName("cancel_btn")
        cancel_btn.clicked.connect(lambda: self.cancel_clicked.emit(
            self.task_id
        ))
        actions_layout.addWidget(cancel_btn)
        self.cancel_btn = cancel_btn

        # Delete button
        delete_btn = QPushButton()
        delete_btn.setObjectName("delete_btn")
        delete_btn.clicked.connect(lambda: self.delete_clicked.emit(
            self.task_id
        ))
        actions_layout.addWidget(delete_btn)
        self.delete_btn = delete_btn

        # View button
        view_btn = QPushButton()
        view_btn.setObjectName("view_btn")
        view_btn.clicked.connect(lambda: self.view_clicked.emit(
            self.task_id
        ))
        view_btn.setVisible(False)
        actions_layout.addWidget(view_btn)
        self.view_btn = view_btn

        # Export button
        export_btn = QPushButton()
        export_btn.setObjectName("export_btn")
        export_btn.clicked.connect(lambda: self.export_clicked.emit(
            self.task_id
        ))
        export_btn.setVisible(False)
        actions_layout.addWidget(export_btn)
        self.export_btn = export_btn

        # Retry button
        retry_btn = QPushButton()
        retry_btn.setObjectName("retry_btn")
        retry_btn.clicked.connect(lambda: self.retry_clicked.emit(
            self.task_id
        ))
        retry_btn.setVisible(False)
        actions_layout.addWidget(retry_btn)
        self.retry_btn = retry_btn

        actions_layout.addStretch()

        layout.addLayout(actions_layout)

        # Update translations
        self.update_translations()
        
        # Set minimum height to ensure all content is visible
        self.setMinimumHeight(150)

        logger.debug("Task item UI setup complete")

    def update_translations(self):
        """Update all UI text with current language translations."""
        try:
            # Update button labels
            self.start_btn.setText(
                self.i18n.t('batch_transcribe.actions.start')
            )
            self._update_pause_button_text()
            self.cancel_btn.setText(
                self.i18n.t('batch_transcribe.actions.cancel')
            )
            self.delete_btn.setText(
                self.i18n.t('common.delete')
            )
            self.view_btn.setText(
                self.i18n.t('batch_transcribe.actions.view')
            )
            self.export_btn.setText(
                self.i18n.t('batch_transcribe.actions.export')
            )
            self.retry_btn.setText(
                self.i18n.t('batch_transcribe.actions.retry')
            )

            # Update status label
            self._update_status_label()

            logger.debug("Task item translations updated")

        except Exception as e:
            logger.error(f"Error updating translations: {e}")

    def sizeHint(self):
        """Return the recommended size for this widget."""
        from PyQt6.QtCore import QSize
        # Return a fixed size to ensure consistent layout
        return QSize(800, 150)

    def update_display(self):
        """Update display based on current task data."""
        try:
            # Update filename
            self.filename_label.setText(
                f"📄 {self.task_data.get('file_name', 'Unknown')}"
            )

            # Update info
            info_parts = []

            # File size
            file_size = self.task_data.get('file_size')
            if file_size:
                size_mb = file_size / (1024 * 1024)
                info_parts.append(f"Size: {size_mb:.1f} MB")

            # Duration
            duration = self.task_data.get('audio_duration')
            if duration:
                minutes = int(duration // 60)
                seconds = int(duration % 60)
                info_parts.append(f"Duration: {minutes}:{seconds:02d}")

            # Language
            language = self.task_data.get('language')
            if language:
                info_parts.append(f"Language: {language}")

            self.info_label.setText(" | ".join(info_parts))

            # Update status
            self._update_status_label()

            # Update progress bar
            status = self.task_data.get('status', 'pending')
            progress = self.task_data.get('progress', 0)

            if status == 'processing':
                self.progress_bar.setVisible(True)
                self.progress_bar.setValue(int(progress))
                logger.debug(
                    f"Task {self.task_id} progress bar set to {int(progress)}%"
                )
            else:
                self.progress_bar.setVisible(False)

            # Update error message
            error_msg = self.task_data.get('error_message')
            if error_msg and status == 'failed':
                self.error_label.setText(f"Error: {error_msg}")
                self.error_label.setVisible(True)
            else:
                self.error_label.setVisible(False)

            # Update button visibility based on status
            self._update_button_visibility(status)

            logger.debug(f"Task item display updated for {self.task_id}")

        except Exception as e:
            logger.error(f"Error updating display: {e}")

    def _update_status_label(self):
        """Update status label with translated text and styling."""
        status = self.task_data.get('status', 'pending')

        # Get translated status text
        status_key = f'batch_transcribe.status.{status}'
        status_text = self.i18n.t(status_key)

        # Apply styling based on status
        if status == 'pending':
            style = "color: #666; font-weight: bold;"
            icon = "⏳"
        elif status == 'processing':
            style = "color: #1976d2; font-weight: bold;"
            icon = "⚙️"
        elif status == 'completed':
            style = "color: #388e3c; font-weight: bold;"
            icon = "✓"
        elif status == 'failed':
            style = "color: #d32f2f; font-weight: bold;"
            icon = "✗"
        else:
            style = "color: #666; font-weight: bold;"
            icon = ""

        self.status_label.setText(f"{icon} {status_text}")
        self.status_label.setStyleSheet(style)

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
        if status == 'pending':
            # Tasks start automatically when added to queue
            # Only show cancel and delete buttons
            self.cancel_btn.setVisible(True)
            self.delete_btn.setVisible(True)
        elif status == 'processing':
            self.cancel_btn.setVisible(True)
            self.pause_btn.setVisible(True)
            self._update_pause_button_text()
        elif status == 'completed':
            self.view_btn.setVisible(True)
            self.export_btn.setVisible(True)
            self.delete_btn.setVisible(True)
        elif status == 'failed':
            self.retry_btn.setVisible(True)
            self.delete_btn.setVisible(True)

    def set_processing_paused(self, paused: bool):
        """Update pause/resume state for processing tasks."""
        if self._processing_paused == paused:
            return

        self._processing_paused = paused
        self._update_pause_button_text()

        status = self.task_data.get('status', 'pending')
        if status == 'processing':
            self.pause_btn.setVisible(True)

    def _update_pause_button_text(self):
        """Update pause button text based on processing state."""
        action_key = (
            'batch_transcribe.actions.resume'
            if self._processing_paused
            else 'batch_transcribe.actions.pause'
        )
        try:
            self.pause_btn.setText(self.i18n.t(action_key))
        except Exception:
            # Fallback to default text in case translation missing
            self.pause_btn.setText('Resume' if self._processing_paused else 'Pause')

    def update_task_data(self, task_data: Dict[str, Any]):
        """
        Update task data and refresh display.

        Args:
            task_data: New task data
        """
        self.task_data = task_data
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

            status = self.task_data.get('status', 'pending')

            # Add actions based on status
            if status == 'pending':
                start_action = QAction(
                    self.i18n.t('batch_transcribe.actions.start'),
                    self
                )
                start_action.triggered.connect(
                    lambda: self.start_clicked.emit(self.task_id)
                )
                menu.addAction(start_action)

            elif status == 'processing':
                cancel_action = QAction(
                    self.i18n.t('batch_transcribe.actions.cancel'),
                    self
                )
                cancel_action.triggered.connect(
                    lambda: self.cancel_clicked.emit(self.task_id)
                )
                menu.addAction(cancel_action)

            elif status == 'completed':
                view_action = QAction(
                    self.i18n.t('batch_transcribe.actions.view'),
                    self
                )
                view_action.triggered.connect(
                    lambda: self.view_clicked.emit(self.task_id)
                )
                menu.addAction(view_action)

                export_action = QAction(
                    self.i18n.t('batch_transcribe.actions.export'),
                    self
                )
                export_action.triggered.connect(
                    lambda: self.export_clicked.emit(self.task_id)
                )
                menu.addAction(export_action)

            elif status == 'failed':
                retry_action = QAction(
                    self.i18n.t('batch_transcribe.actions.retry'),
                    self
                )
                retry_action.triggered.connect(
                    lambda: self.retry_clicked.emit(self.task_id)
                )
                menu.addAction(retry_action)

            # Always show delete
            menu.addSeparator()
            delete_action = QAction(
                self.i18n.t('common.delete'),
                self
            )
            delete_action.triggered.connect(
                lambda: self.delete_clicked.emit(self.task_id)
            )
            menu.addAction(delete_action)

            # Show menu
            menu.exec(event.globalPos())

        except Exception as e:
            logger.error(f"Error showing context menu: {e}")
