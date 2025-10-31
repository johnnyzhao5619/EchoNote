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

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QGroupBox,
    QLabel,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QVBoxLayout,
)

from ui.base_widgets import connect_button_with_callback, create_button, create_vbox
from ui.settings.base_page import BaseSettingsPage
from utils.data_cleanup import DataCleanup

logger = logging.getLogger(__name__)


class CleanupWorker(QThread):
    """Worker thread for data cleanup operations."""

    finished = Signal(dict)  # Emits cleanup results
    error = Signal(str)  # Emits error message

    def __init__(self, cleanup_manager: DataCleanup):
        self.cleanup_manager = cleanup_manager

    def run(self):
        """Execute cleanup operation."""
        try:
            results = self.cleanup_manager.cleanup_all_data()
            self.finished.emit(results)
        except Exception as e:
            logger.error(f"Cleanup worker error: {e}")
            self.error.emit(str(e))


class DataManagementPage(BaseSettingsPage):
    """
    Data Management settings page.

    Provides options for:
    - Viewing data storage summary
    - Clearing all user data
    - Selective data cleanup
    """

    def __init__(self, settings_manager, i18n, parent=None):
        """
        Initialize data management page.

        Args:
            settings_manager: SettingsManager instance
            i18n: Internationalization manager
            parent: Parent widget
        """
        super().__init__(settings_manager, i18n)
        self.cleanup_manager = DataCleanup()
        self.cleanup_worker = None
        self._init_ui()

    def _init_ui(self):
        """Initialize the user interface."""
        layout = create_vbox()
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Page title
        self.title_label = QLabel(self.i18n.t("data_management.title"))
        self.title_label.setProperty("role", "calendar-header")
        layout.addWidget(self.title_label)

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
        self.storage_group = QGroupBox(self.i18n.t("settings.storage_summary"))
        layout = create_vbox()

        # Summary labels
        self.database_label = QLabel(self.i18n.t("data_management.storage_labels.database"))
        self.config_label = QLabel(self.i18n.t("data_management.storage_labels.configuration"))
        self.recordings_label = QLabel(self.i18n.t("data_management.storage_labels.recordings"))
        self.transcripts_label = QLabel(self.i18n.t("data_management.storage_labels.transcripts"))
        self.logs_label = QLabel(self.i18n.t("data_management.storage_labels.logs"))
        self.total_label = QLabel(self.i18n.t("data_management.storage_labels.total"))
        self.total_label.setProperty("role", "audio-file")

        layout.addWidget(self.database_label)
        layout.addWidget(self.config_label)
        layout.addWidget(self.recordings_label)
        layout.addWidget(self.transcripts_label)
        layout.addWidget(self.logs_label)
        layout.addWidget(QLabel(""))  # Spacer
        layout.addWidget(self.total_label)

        # Refresh button
        self.refresh_btn = create_button(self.i18n.t("common.refresh"))
        connect_button_with_callback(self.refresh_btn, self._refresh_storage_summary)
        layout.addWidget(self.refresh_btn)

        self.storage_group.setLayout(layout)

        # Initial refresh
        self._refresh_storage_summary()

        return self.storage_group

    def _create_cleanup_group(self) -> QGroupBox:
        """Create data cleanup group."""
        self.cleanup_group = QGroupBox(self.i18n.t("settings.data_cleanup"))
        layout = create_vbox()

        # Warning label
        warning = QLabel(
            "⚠️ Warning: Data cleanup operations cannot be undone!\n"
            "Please make sure you have backed up any important data."
        )
        warning.setProperty("role", "data-warning")
        warning.setWordWrap(True)
        layout.addWidget(warning)

        # Clear all data button
        self.clear_all_btn = create_button(self.i18n.t("data_management.clear_all"))
        self.clear_all_btn.setProperty("role", "data-delete-all")
        connect_button_with_callback(self.clear_all_btn, self._confirm_clear_all_data)
        layout.addWidget(self.clear_all_btn)

        # Description
        self.description_label = QLabel(self.i18n.t("data_management.clear_all_description"))
        self.description_label.setProperty("role", "data-description")
        layout.addWidget(self.description_label)

        self.cleanup_group.setLayout(layout)
        return self.cleanup_group

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
            db_status = (
                self.i18n.t("data_management.storage_status.exists")
                if summary["database_exists"]
                else self.i18n.t("data_management.storage_status.not_found")
            )
            self.database_label.setText(
                f"{self.i18n.t('data_management.storage_labels.database_prefix')}: {db_size} ({db_status})"
            )
            self.config_label.setText(
                f"{self.i18n.t('data_management.storage_labels.configuration_prefix')}: {config_size} ({len(summary['config_files'])} {self.i18n.t('data_management.storage_labels.files')})"
            )
            self.recordings_label.setText(
                f"{self.i18n.t('data_management.storage_labels.recordings_prefix')}: {recordings_size} ({summary['recordings_count']} {self.i18n.t('data_management.storage_labels.files')})"
            )
            self.transcripts_label.setText(
                f"{self.i18n.t('data_management.storage_labels.transcripts_prefix')}: {transcripts_size} ({summary['transcripts_count']} {self.i18n.t('data_management.storage_labels.files')})"
            )
            self.logs_label.setText(
                f"{self.i18n.t('data_management.storage_labels.logs_prefix')}: {logs_size} ({summary['logs_count']} {self.i18n.t('data_management.storage_labels.files')})"
            )
            self.total_label.setText(
                f"{self.i18n.t('data_management.storage_labels.total_prefix')}: {total_size}"
            )

            logger.debug("Storage summary refreshed")

        except Exception as e:
            logger.error(f"Failed to refresh storage summary: {e}")
            self.show_error(
                self.i18n.t("common.error"), f"Failed to calculate storage summary:\n{str(e)}"
            )

    def _confirm_clear_all_data(self):
        """Show confirmation dialog before clearing all data."""
        # Get summary for confirmation message
        summary = self.cleanup_manager.get_cleanup_summary()
        total_size = DataCleanup.format_size(summary["total_size"])

        # Create confirmation dialog
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Icon.Warning)
        msg_box.setWindowTitle(self.i18n.t("data_management.confirm_cleanup"))
        msg_box.setText(self.i18n.t("data_management.confirm_delete"))
        msg_box.setInformativeText(
            self.i18n.t("data_management.confirm_delete_details", size=total_size)
        )
        msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg_box.setDefaultButton(QMessageBox.StandardButton.No)

        # Show dialog
        result = msg_box.exec()

        if result == QMessageBox.StandardButton.Yes:
            # Double confirmation
            confirm_box = QMessageBox(self)
            confirm_box.setIcon(QMessageBox.Icon.Warning)
            confirm_box.setWindowTitle(self.i18n.t("data_management.final_confirmation"))
            confirm_box.setText(self.i18n.t("data_management.last_chance"))
            confirm_box.setInformativeText(
                self.i18n.t("data_management.final_confirmation_details")
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
            self.i18n.t("data_management.cleanup_progress_message"),
            None,  # No cancel button
            0,
            0,  # Indeterminate progress
            self,
        )
        progress.setWindowTitle(self.i18n.t("data_management.cleanup_progress"))
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
            msg_box.setWindowTitle(self.i18n.t("data_management.cleanup_complete"))
            msg_box.setText(self.i18n.t("data_management.cleanup_success"))
            msg_box.setInformativeText(
                self.i18n.t(
                    "data_management.cleanup_success_details", count=len(results["deleted_items"])
                )
            )
            msg_box.exec()

            # Refresh summary
            self._refresh_storage_summary()

            logger.info(
                self.i18n.t("logging.settings.data_management_page.cleanup_completed_successfully")
            )
        else:
            # Show error message
            error_details = "\n".join(results["errors"][:5])  # Show first 5 errors
            if len(results["errors"]) > 5:
                more_errors_count = len(results["errors"]) - 5
                error_details += (
                    f"\n{self.i18n.t('data_management.more_errors', count=more_errors_count)}"
                )

            msg_box = QMessageBox(self)
            msg_box.setIcon(QMessageBox.Icon.Warning)
            msg_box.setWindowTitle(self.i18n.t("data_management.cleanup_errors"))
            msg_box.setText(self.i18n.t("data_management.cleanup_partial"))
            msg_box.setDetailedText(error_details)
            msg_box.setInformativeText(
                self.i18n.t(
                    "data_management.cleanup_partial_details",
                    deleted=len(results["deleted_items"]),
                    failed=len(results["failed_items"]),
                )
            )
            msg_box.exec()

            # Refresh summary
            self._refresh_storage_summary()

            logger.warning(f"Data cleanup completed with {len(results['failed_items'])} errors")

    def _on_cleanup_error(self, error: str, progress: QProgressDialog):
        """Handle cleanup error."""
        progress.close()

        self.show_error(
            self.i18n.t("dialogs.settings.data_management.cleanup_failed"),
            f"An error occurred during cleanup:\n\n{error}",
        )

        logger.error(f"Data cleanup failed: {error}")

    def load_settings(self):
        """Load settings (not applicable for this page)."""

    def save_settings(self):
        """Save settings (not applicable for this page)."""

    def validate_settings(self):
        """Validate settings (not applicable for this page)."""
        return True, ""

    def update_translations(self):
        """Update UI text after language change."""
        # Update title
        if hasattr(self, "title_label"):
            self.title_label.setText(self.i18n.t("data_management.title"))

        # Update storage summary labels
        if hasattr(self, "database_label"):
            self.database_label.setText(self.i18n.t("data_management.storage_labels.database"))
        if hasattr(self, "config_label"):
            self.config_label.setText(self.i18n.t("data_management.storage_labels.configuration"))
        if hasattr(self, "recordings_label"):
            self.recordings_label.setText(self.i18n.t("data_management.storage_labels.recordings"))
        if hasattr(self, "transcripts_label"):
            self.transcripts_label.setText(
                self.i18n.t("data_management.storage_labels.transcripts")
            )
        if hasattr(self, "logs_label"):
            self.logs_label.setText(self.i18n.t("data_management.storage_labels.logs"))
        if hasattr(self, "total_label"):
            self.total_label.setText(self.i18n.t("data_management.storage_labels.total"))

        # Update buttons
        if hasattr(self, "refresh_btn"):
            self.refresh_btn.setText(self.i18n.t("common.refresh"))
        if hasattr(self, "clear_all_btn"):
            self.clear_all_btn.setText(self.i18n.t("data_management.clear_all"))

        # Update group titles
        if hasattr(self, "storage_group"):
            self.storage_group.setTitle(self.i18n.t("settings.storage_summary"))
        if hasattr(self, "cleanup_group"):
            self.cleanup_group.setTitle(self.i18n.t("data_management.title"))

        # Update description
        if hasattr(self, "description_label"):
            self.description_label.setText(self.i18n.t("data_management.clear_all_description"))

        # Refresh storage summary to update the text
        self._refresh_storage_summary()
