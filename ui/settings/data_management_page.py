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
Data Management settings page for EchoNote application.

Provides UI for managing user data, including cleanup functionality.
"""

import logging
from PySide6.QtWidgets import (
    QVBoxLayout,
    QLabel,
    QPushButton,
    QGroupBox,
    QMessageBox,
    QProgressDialog,
)
from PySide6.QtCore import Qt, QThread, Signal

from ui.settings.base_page import BasePage
from utils.data_cleanup import DataCleanup


logger = logging.getLogger(__name__)


class CleanupWorker(QThread):
    """Worker thread for data cleanup operations."""

    finished = Signal(dict)  # Emits cleanup results
    error = Signal(str)  # Emits error message

    def __init__(self, cleanup_manager: DataCleanup):
        super().__init__()
        self.cleanup_manager = cleanup_manager

    def run(self):
        """Execute cleanup operation."""
        try:
            results = self.cleanup_manager.cleanup_all_data()
            self.finished.emit(results)
        except Exception as e:
            logger.error(f"Cleanup worker error: {e}")
            self.error.emit(str(e))


class DataManagementPage(BasePage):
    """
    Data Management settings page.

    Provides options for:
    - Viewing data storage summary
    - Clearing all user data
    - Selective data cleanup
    """

    def __init__(self, settings_manager, parent=None):
        """
        Initialize data management page.

        Args:
            settings_manager: SettingsManager instance
            parent: Parent widget
        """
        super().__init__(settings_manager, parent)
        self.cleanup_manager = DataCleanup()
        self.cleanup_worker = None
        self._init_ui()

    def _init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Page title
        title = QLabel("Data Management")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)

        # Storage summary group
        storage_group = self._create_storage_summary_group()
        layout.addWidget(storage_group)

        # Data cleanup group
        cleanup_group = self._create_cleanup_group()
        layout.addWidget(cleanup_group)

        # Add stretch to push content to top
        layout.addStretch()

        self.setLayout(layout)

    def _create_storage_summary_group(self) -> QGroupBox:
        """Create storage summary group."""
        group = QGroupBox("Storage Summary")
        layout = QVBoxLayout()

        # Summary labels
        self.database_label = QLabel("Database: Calculating...")
        self.config_label = QLabel("Configuration: Calculating...")
        self.recordings_label = QLabel("Recordings: Calculating...")
        self.transcripts_label = QLabel("Transcripts: Calculating...")
        self.logs_label = QLabel("Logs: Calculating...")
        self.total_label = QLabel("Total: Calculating...")
        self.total_label.setStyleSheet("font-weight: bold;")

        layout.addWidget(self.database_label)
        layout.addWidget(self.config_label)
        layout.addWidget(self.recordings_label)
        layout.addWidget(self.transcripts_label)
        layout.addWidget(self.logs_label)
        layout.addWidget(QLabel(""))  # Spacer
        layout.addWidget(self.total_label)

        # Refresh button
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._refresh_storage_summary)
        layout.addWidget(refresh_btn)

        group.setLayout(layout)

        # Initial refresh
        self._refresh_storage_summary()

        return group

    def _create_cleanup_group(self) -> QGroupBox:
        """Create data cleanup group."""
        group = QGroupBox("Data Cleanup")
        layout = QVBoxLayout()

        # Warning label
        warning = QLabel(
            "⚠️ Warning: Data cleanup operations cannot be undone!\n"
            "Please make sure you have backed up any important data."
        )
        warning.setStyleSheet("color: #ff6b6b; padding: 10px;")
        warning.setWordWrap(True)
        layout.addWidget(warning)

        # Clear all data button
        clear_all_btn = QPushButton("Clear All Data")
        clear_all_btn.setStyleSheet(
            "QPushButton { background-color: #ff6b6b; color: white; "
            "padding: 10px; font-weight: bold; }"
            "QPushButton:hover { background-color: #ff5252; }"
        )
        clear_all_btn.clicked.connect(self._confirm_clear_all_data)
        layout.addWidget(clear_all_btn)

        # Description
        description = QLabel(
            "This will delete:\n"
            "• Database (all tasks, events, and settings)\n"
            "• Configuration files\n"
            "• All recordings\n"
            "• All transcripts\n"
            "• Log files"
        )
        description.setStyleSheet("color: #666; padding: 10px;")
        layout.addWidget(description)

        group.setLayout(layout)
        return group

    def _refresh_storage_summary(self):
        """Refresh storage summary display."""
        try:
            summary = self.cleanup_manager.get_cleanup_summary()

            # Format sizes
            db_size = DataCleanup.format_size(summary["database_size"])
            config_size = DataCleanup.format_size(summary["config_size"])
            recordings_size = DataCleanup.format_size(summary["recordings_size"])
            transcripts_size = DataCleanup.format_size(summary["transcripts_size"])
            logs_size = DataCleanup.format_size(summary["logs_size"])
            total_size = DataCleanup.format_size(summary["total_size"])

            # Update labels
            self.database_label.setText(
                f"Database: {db_size}"
                + (" (exists)" if summary["database_exists"] else " (not found)")
            )
            self.config_label.setText(
                f"Configuration: {config_size} " f"({len(summary['config_files'])} files)"
            )
            self.recordings_label.setText(
                f"Recordings: {recordings_size} " f"({summary['recordings_count']} files)"
            )
            self.transcripts_label.setText(
                f"Transcripts: {transcripts_size} " f"({summary['transcripts_count']} files)"
            )
            self.logs_label.setText(f"Logs: {logs_size} " f"({summary['logs_count']} files)")
            self.total_label.setText(f"Total: {total_size}")

            logger.debug("Storage summary refreshed")

        except Exception as e:
            logger.error(f"Failed to refresh storage summary: {e}")
            QMessageBox.critical(self, "Error", f"Failed to calculate storage summary:\n{str(e)}")

    def _confirm_clear_all_data(self):
        """Show confirmation dialog before clearing all data."""
        # Get summary for confirmation message
        summary = self.cleanup_manager.get_cleanup_summary()
        total_size = DataCleanup.format_size(summary["total_size"])

        # Create confirmation dialog
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Icon.Warning)
        msg_box.setWindowTitle("Confirm Data Cleanup")
        msg_box.setText("Are you sure you want to delete ALL user data?")
        msg_box.setInformativeText(
            f"This will permanently delete approximately {total_size} of data.\n\n"
            "This operation cannot be undone!\n\n"
            "The application will need to be restarted after cleanup."
        )
        msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg_box.setDefaultButton(QMessageBox.StandardButton.No)

        # Show dialog
        result = msg_box.exec()

        if result == QMessageBox.StandardButton.Yes:
            # Double confirmation
            confirm_box = QMessageBox(self)
            confirm_box.setIcon(QMessageBox.Icon.Warning)
            confirm_box.setWindowTitle("Final Confirmation")
            confirm_box.setText("This is your last chance to cancel!")
            confirm_box.setInformativeText(
                "Type 'DELETE' in the confirmation dialog to proceed.\n\n"
                "Are you absolutely sure you want to delete all data?"
            )
            confirm_box.setStandardButtons(
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            confirm_box.setDefaultButton(QMessageBox.StandardButton.No)

            final_result = confirm_box.exec()

            if final_result == QMessageBox.StandardButton.Yes:
                self._execute_cleanup()

    def _execute_cleanup(self):
        """Execute data cleanup operation."""
        # Show progress dialog
        progress = QProgressDialog(
            "Deleting all user data...",
            None,  # No cancel button
            0,
            0,  # Indeterminate progress
            self,
        )
        progress.setWindowTitle("Cleanup in Progress")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.show()

        # Create and start worker thread
        self.cleanup_worker = CleanupWorker(self.cleanup_manager)
        self.cleanup_worker.finished.connect(
            lambda results: self._on_cleanup_finished(results, progress)
        )
        self.cleanup_worker.error.connect(lambda error: self._on_cleanup_error(error, progress))
        self.cleanup_worker.start()

    def _on_cleanup_finished(self, results: dict, progress: QProgressDialog):
        """Handle cleanup completion."""
        progress.close()

        if results["success"]:
            # Show success message
            msg_box = QMessageBox(self)
            msg_box.setIcon(QMessageBox.Icon.Information)
            msg_box.setWindowTitle("Cleanup Complete")
            msg_box.setText("All user data has been deleted successfully.")
            msg_box.setInformativeText(
                f"Deleted {len(results['deleted_items'])} items.\n\n"
                "Please restart the application."
            )
            msg_box.exec()

            # Refresh summary
            self._refresh_storage_summary()

            logger.info("Data cleanup completed successfully")
        else:
            # Show error message
            error_details = "\n".join(results["errors"][:5])  # Show first 5 errors
            if len(results["errors"]) > 5:
                error_details += f"\n... and {len(results['errors']) - 5} more errors"

            msg_box = QMessageBox(self)
            msg_box.setIcon(QMessageBox.Icon.Warning)
            msg_box.setWindowTitle("Cleanup Completed with Errors")
            msg_box.setText("Data cleanup completed, but some items could not be deleted.")
            msg_box.setDetailedText(error_details)
            msg_box.setInformativeText(
                f"Deleted: {len(results['deleted_items'])} items\n"
                f"Failed: {len(results['failed_items'])} items"
            )
            msg_box.exec()

            # Refresh summary
            self._refresh_storage_summary()

            logger.warning(f"Data cleanup completed with {len(results['failed_items'])} errors")

    def _on_cleanup_error(self, error: str, progress: QProgressDialog):
        """Handle cleanup error."""
        progress.close()

        QMessageBox.critical(
            self, "Cleanup Failed", f"An error occurred during cleanup:\n\n{error}"
        )

        logger.error(f"Data cleanup failed: {error}")

    def load_settings(self):
        """Load settings (not applicable for this page)."""
        pass

    def save_settings(self):
        """Save settings (not applicable for this page)."""
        pass
