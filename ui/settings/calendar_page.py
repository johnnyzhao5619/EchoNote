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
Calendar integration settings page.

Provides UI for managing external calendar account connections.
"""

import logging
from typing import Any, Dict, Tuple

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
)

from ui.settings.base_page import BaseSettingsPage
from ui.base_widgets import create_hbox, create_button
from utils.i18n import I18nQtManager

logger = logging.getLogger("echonote.ui.settings.calendar")


class CalendarSettingsPage(BaseSettingsPage):
    """Settings page for calendar integration configuration."""

    def __init__(self, settings_manager, i18n: I18nQtManager, managers: Dict[str, Any]):
        """
        Initialize calendar settings page.

        Args:
            settings_manager: SettingsManager instance
            i18n: Internationalization manager
            managers: Dictionary of other managers
        """
        super().__init__(settings_manager, i18n)
        self.managers = managers

        # Setup UI
        self.setup_ui()

        logger.debug("Calendar settings page initialized")

    def setup_ui(self):
        """Set up the calendar settings UI."""
        # Connected accounts section
        from PySide6.QtGui import QFont

        font = QFont()
        font.setPointSize(12)
        font.setBold(True)

        self.accounts_title = QLabel(self.i18n.t("settings.calendar.connected_accounts"))
        self.accounts_title.setFont(font)
        self.content_layout.addWidget(self.accounts_title)

        # Description
        self.desc_label = QLabel(self.i18n.t("settings.calendar.accounts_description"))
        self.desc_label.setWordWrap(True)
        self.desc_label.setProperty("role", "description")
        self.content_layout.addWidget(self.desc_label)

        self.add_spacing(10)

        # Accounts list
        self.accounts_list = QListWidget()
        self.accounts_list.setMinimumHeight(200)
        self.content_layout.addWidget(self.accounts_list)

        # Buttons layout
        buttons_layout = create_hbox()

        self.add_google_button = create_button(self.i18n.t("settings.calendar.add_google"))
        self.add_google_button.clicked.connect(self._on_add_google_clicked)
        buttons_layout.addWidget(self.add_google_button)

        self.add_outlook_button = create_button(self.i18n.t("settings.calendar.add_outlook"))
        self.add_outlook_button.clicked.connect(self._on_add_outlook_clicked)
        buttons_layout.addWidget(self.add_outlook_button)

        self.remove_button = create_button(self.i18n.t("settings.calendar.remove_account"))
        self.remove_button.clicked.connect(self._on_remove_clicked)
        self.remove_button.setEnabled(False)
        buttons_layout.addWidget(self.remove_button)

        buttons_layout.addStretch()

        self.content_layout.addLayout(buttons_layout)

        # Connect list selection change
        self.accounts_list.itemSelectionChanged.connect(self._on_selection_changed)

        self.add_spacing(20)

        # Sync settings section
        self.sync_title = QLabel(self.i18n.t("settings.calendar.sync_settings"))
        self.sync_title.setFont(font)
        self.content_layout.addWidget(self.sync_title)

        # Sync interval (this would be implemented if needed)
        self.sync_info = QLabel(self.i18n.t("settings.calendar.sync_info"))
        self.sync_info.setWordWrap(True)
        self.sync_info.setProperty("role", "description")
        self.content_layout.addWidget(self.sync_info)

        # Add stretch at the end
        self.content_layout.addStretch()

    def _on_selection_changed(self):
        """Handle account list selection change."""
        has_selection = len(self.accounts_list.selectedItems()) > 0
        self.remove_button.setEnabled(has_selection)

    def _on_add_google_clicked(self):
        """Handle add Google account button click."""
        self.show_info(
            self.i18n.t("settings.calendar.add_account"),
            self.i18n.t("settings.calendar.google_oauth_info"),
        )

        # In a real implementation, this would:
        # 1. Get calendar_manager from self.managers
        # 2. Initiate OAuth flow
        # 3. Add account to list on success

        logger.info(self.i18n.t("logging.settings.calendar_page.add_google_account_clicked"))

    def _on_add_outlook_clicked(self):
        """Handle add Outlook account button click."""
        self.show_info(
            self.i18n.t("settings.calendar.add_account"),
            self.i18n.t("settings.calendar.outlook_oauth_info"),
        )

        # In a real implementation, this would:
        # 1. Get calendar_manager from self.managers
        # 2. Initiate OAuth flow
        # 3. Add account to list on success

        logger.info(self.i18n.t("logging.settings.calendar_page.add_outlook_account_clicked"))

    def _on_remove_clicked(self):
        """Handle remove account button click."""
        selected_items = self.accounts_list.selectedItems()
        if not selected_items:
            return

        item = selected_items[0]
        account_data = item.data(Qt.ItemDataRole.UserRole)

        # Confirm removal
        reply = QMessageBox.question(
            self,
            self.i18n.t("settings.calendar.confirm_remove_title"),
            self.i18n.t(
                "settings.calendar.confirm_remove_message",
                account=account_data.get("email", "Unknown"),
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            # Remove from list
            row = self.accounts_list.row(item)
            self.accounts_list.takeItem(row)

            # In a real implementation, this would also:
            # 1. Revoke OAuth token
            # 2. Remove from database
            # 3. Stop syncing

            self._emit_changed()

            logger.info(f"Removed account: {account_data.get('email')}")

    def load_settings(self):
        """Load calendar settings into UI."""
        try:
            # Clear existing items
            self.accounts_list.clear()

            # In a real implementation, this would:
            # 1. Query database for connected accounts
            # 2. Add each account to the list

            # For now, we'll just check if there are any sync status records
            # This is a placeholder implementation

            logger.debug("Calendar settings loaded")

        except Exception as e:
            logger.error(f"Error loading calendar settings: {e}")

    def save_settings(self):
        """Save calendar settings from UI."""
        try:
            # Calendar account connections are managed in real-time
            # (when user adds/removes accounts), so there's nothing
            # to save here in the traditional sense

            logger.debug("Calendar settings saved")

        except Exception as e:
            logger.error(f"Error saving calendar settings: {e}")
            raise

    def validate_settings(self) -> Tuple[bool, str]:
        """
        Validate calendar settings.

        Returns:
            Tuple of (is_valid, error_message)
        """
        # No validation needed for calendar settings
        return True, ""

    def update_translations(self):
        """Update UI text after language change."""
        # Update section titles
        if hasattr(self, "accounts_title"):
            self.accounts_title.setText(self.i18n.t("settings.calendar.connected_accounts"))
        if hasattr(self, "sync_title"):
            self.sync_title.setText(self.i18n.t("settings.calendar.sync_settings"))

        # Update labels
        if hasattr(self, "desc_label"):
            self.desc_label.setText(self.i18n.t("settings.calendar.accounts_description"))
        if hasattr(self, "sync_info"):
            self.sync_info.setText(self.i18n.t("settings.calendar.sync_info"))

        # Update buttons
        if hasattr(self, "add_google_button"):
            self.add_google_button.setText(self.i18n.t("settings.calendar.add_google"))
        if hasattr(self, "add_outlook_button"):
            self.add_outlook_button.setText(self.i18n.t("settings.calendar.add_outlook"))
        if hasattr(self, "remove_button"):
            self.remove_button.setText(self.i18n.t("settings.calendar.remove_account"))

    def add_account_to_list(self, provider: str, email: str, status: str = "Connected"):
        """
        Add an account to the list.

        Args:
            provider: Provider name (Google/Outlook)
            email: Account email
            status: Connection status
        """
        item = QListWidgetItem(f"{provider}: {email} ({status})")
        item.setData(
            Qt.ItemDataRole.UserRole, {"provider": provider, "email": email, "status": status}
        )
        self.accounts_list.addItem(item)
