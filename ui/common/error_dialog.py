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
Error dialog for EchoNote application.

Provides a dialog for displaying error messages with details and copy functionality.
"""

import logging
from typing import Optional

from ui.base_widgets import connect_button_with_callback, create_hbox
from ui.constants import ERROR_DIALOG_DETAILS_MAX_HEIGHT, ERROR_DIALOG_MIN_WIDTH
from core.qt_imports import (
    QApplication,
    QDialog,
    QLabel,
    QPushButton,
    QTextEdit,
    QTimer,
    QVBoxLayout,
    QWidget,
)
from utils.i18n import I18nQtManager

logger = logging.getLogger("echonote.ui.error_dialog")


class ErrorDialog(QDialog):
    """
    Dialog for displaying error messages with details.

    Provides options to view detailed error information and copy to clipboard.
    """

    def __init__(
        self,
        title: str,
        message: str,
        details: Optional[str] = None,
        i18n: Optional[I18nQtManager] = None,
        parent: Optional[QWidget] = None,
    ):
        """
        Initialize error dialog.

        Args:
            title: Dialog title
            message: Error message
            details: Optional detailed error information
            i18n: Internationalization manager
            parent: Parent widget
        """
        super().__init__(parent)
        self.i18n = i18n
        self.setWindowTitle(title)
        self.setModal(True)

        if self.i18n:
            self.i18n.language_changed.connect(self._on_language_changed)

        self.error_title = title
        self.error_message = message
        self.error_details = details

        # Setup UI
        self.setup_ui()

    def setup_ui(self):
        """Set up the error dialog UI."""
        # Set dialog properties
        self.setWindowTitle(self.error_title)
        self.setMinimumWidth(ERROR_DIALOG_MIN_WIDTH)
        self.setModal(True)

        # Create layout
        layout = QVBoxLayout(self)

        # Create error message label
        message_label = QLabel(self.error_message)
        message_label.setWordWrap(True)
        message_label.setObjectName("error_message")
        layout.addWidget(message_label)

        # Create details section if details are provided
        if self.error_details:
            # Create details text edit
            self.details_text = QTextEdit()
            self.details_text.setPlainText(self.error_details)
            self.details_text.setReadOnly(True)
            self.details_text.setMaximumHeight(ERROR_DIALOG_DETAILS_MAX_HEIGHT)
            self.details_text.setObjectName("error_details")

            # Initially hide details
            self.details_text.hide()

            # Create show/hide details button
            self.details_button = QPushButton()
            self._update_details_button_text(False)
            connect_button_with_callback(self.details_button, self._toggle_details)

            layout.addWidget(self.details_button)
            layout.addWidget(self.details_text)

        # Create button layout
        button_layout = create_hbox()
        button_layout.addStretch()

        # Create copy button if details are provided
        if self.error_details:
            self.copy_button = QPushButton()
            self._update_copy_button_text()
            connect_button_with_callback(self.copy_button, self._copy_to_clipboard)
            button_layout.addWidget(self.copy_button)

        # Create OK button
        self.ok_button = QPushButton()
        self._update_ok_button_text()
        connect_button_with_callback(self.ok_button, self.accept)
        self.ok_button.setDefault(True)
        button_layout.addWidget(self.ok_button)

        layout.addLayout(button_layout)

    def _toggle_details(self):
        """Toggle visibility of error details."""
        if self.details_text.isVisible():
            self.details_text.hide()
            self._update_details_button_text(False)
        else:
            self.details_text.show()
            self._update_details_button_text(True)

    def _copy_to_clipboard(self):
        """Copy error details to clipboard."""
        clipboard = QApplication.clipboard()

        # Format error information
        error_info = f"{self.error_title}\n\n{self.error_message}"
        if self.error_details:
            error_info += f"\n\nDetails:\n{self.error_details}"

        clipboard.setText(error_info)

        # Update button text to show copied
        self.copy_button.setText(self.i18n.t("common.copied") if self.i18n else "Copied")

        # Reset button text after 2 seconds
        QTimer.singleShot(2000, self._update_copy_button_text)

        logger.debug("Error details copied to clipboard")

    def _update_details_button_text(self, showing: bool):
        """
        Update details button text.

        Args:
            showing: Whether details are currently showing
        """
        if self.i18n:
            text = self.i18n.t("common.hide_details" if showing else "common.show_details")
        else:
            text = "Hide Details" if showing else "Show Details"
        self.details_button.setText(text)

    def _update_copy_button_text(self):
        """Update copy button text."""
        self.copy_button.setText(self.i18n.t("common.copy") if self.i18n else "Copy")

    def _update_ok_button_text(self):
        """Update OK button text."""
        self.ok_button.setText(self.i18n.t("common.ok") if self.i18n else "OK")

    def _on_language_changed(self, language: str):
        """
        Handle language change event.

        Args:
            language: New language code
        """
        # Update button texts
        self._update_ok_button_text()

        if self.error_details:
            self._update_details_button_text(self.details_text.isVisible())
            self._update_copy_button_text()


def show_error_dialog(
    title: str,
    message: str,
    details: Optional[str] = None,
    i18n: Optional[I18nQtManager] = None,
    parent: Optional[QWidget] = None,
) -> int:
    """
    Show an error dialog.

    Args:
        title: Dialog title
        message: Error message
        details: Optional detailed error information
        i18n: Internationalization manager
        parent: Parent widget

    Returns:
        Dialog result code
    """
    dialog = ErrorDialog(title, message, details, i18n, parent)
    return dialog.exec()
