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

from core.qt_imports import (
    QAction,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
    Qt,
    Signal,
    Slot,
)
from ui.base_widgets import create_button, create_hbox
from ui.constants import CALENDAR_ACCOUNTS_LIST_MIN_HEIGHT, ROLE_DESCRIPTION
from ui.settings.base_page import BaseSettingsPage
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
        self.accounts_title = self.add_section_title(
            self.i18n.t("settings.calendar.connected_accounts")
        )

        # Description
        self.desc_label = QLabel(self.i18n.t("settings.calendar.accounts_description"))
        self.desc_label.setWordWrap(True)
        self.desc_label.setProperty("role", ROLE_DESCRIPTION)
        self.content_layout.addWidget(self.desc_label)

        self.add_spacing()

        # Accounts list
        self.accounts_list = QListWidget()
        self.accounts_list.setMinimumHeight(CALENDAR_ACCOUNTS_LIST_MIN_HEIGHT)
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

        self.add_section_spacing()

        # Sync settings section
        self.sync_title = self.add_section_title(self.i18n.t("settings.calendar.sync_settings"))

        # Sync interval (this would be implemented if needed)
        self.sync_info = QLabel(self.i18n.t("settings.calendar.sync_info"))
        self.sync_info.setWordWrap(True)
        self.sync_info.setProperty("role", ROLE_DESCRIPTION)
        self.content_layout.addWidget(self.sync_info)

        # Add stretch at the end
        self.content_layout.addStretch()

    def _on_selection_changed(self):
        """Handle account list selection change."""
        has_selection = len(self.accounts_list.selectedItems()) > 0
        self.remove_button.setEnabled(has_selection)

    def _on_add_google_clicked(self):
        """Handle add Google account button click."""
        self._connect_provider("google")

    def _on_add_outlook_clicked(self):
        """Handle add Outlook account button click."""
        self._connect_provider("outlook")

    def _connect_provider(self, provider: str) -> None:
        """Connect a provider account using the calendar hub workflow."""
        calendar_hub = self._get_calendar_hub_widget()
        if calendar_hub is None:
            self.show_warning(
                self.i18n.t("common.error"),
                self.i18n.t("calendar.error.sync_not_configured", provider=provider.capitalize()),
            )
            return

        try:
            calendar_hub.start_oauth_flow(provider)
            self.load_settings()
        except Exception as exc:
            logger.error("Failed to connect provider %s from settings page: %s", provider, exc)
            self.show_error(
                self.i18n.t("common.error"),
                self.i18n.t("calendar.error.auth_failed", error=str(exc)),
            )

    def _on_remove_clicked(self):
        """Handle remove account button click."""
        selected_items = self.accounts_list.selectedItems()
        if not selected_items:
            return

        item = selected_items[0]
        account_data = item.data(Qt.ItemDataRole.UserRole)

        # Confirm removal
        if self.show_question(
            self.i18n.t("settings.calendar.confirm_remove_title"),
            self.i18n.t(
                "settings.calendar.confirm_remove_message",
                account=account_data.get("email", "Unknown"),
            ),
        ):
            provider = account_data.get("provider")
            if not provider:
                return

            try:
                calendar_hub = self._get_calendar_hub_widget()
                if calendar_hub is not None:
                    calendar_hub.disconnect_account(provider, confirm=False)
                else:
                    self._disconnect_provider_without_hub(provider)

                self.load_settings()
                logger.info("Removed account for provider: %s", provider)
            except Exception as exc:
                logger.error("Failed to remove account for provider %s: %s", provider, exc)
                self.show_error(
                    self.i18n.t("common.error"),
                    self.i18n.t("calendar.error.disconnect_failed", error=str(exc)),
                )

    def _disconnect_provider_without_hub(self, provider: str) -> None:
        """Fallback disconnect path when calendar hub widget is unavailable."""
        calendar_manager = self.managers.get("calendar_manager")
        if not calendar_manager:
            raise RuntimeError("calendar_manager is not available")

        calendar_manager.disconnect_provider_account(provider)

    def load_settings(self):
        """Load calendar settings into UI."""
        try:
            # Clear existing items
            self.accounts_list.clear()
            calendar_manager = self.managers.get("calendar_manager")
            if not calendar_manager:
                logger.warning("calendar_manager is unavailable when loading calendar settings")
                return

            from data.database.models import CalendarSyncStatus

            statuses = CalendarSyncStatus.get_all_active(calendar_manager.db)
            for status in statuses:
                self.add_account_to_list(
                    provider=status.provider,
                    email=status.user_email or "",
                )

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

        # Rebuild account list so provider labels follow current language.
        self.load_settings()

    def add_account_to_list(self, provider: str, email: str, status: str = ""):
        """
        Add an account to the list.

        Args:
            provider: Provider name (Google/Outlook)
            email: Account email
            status: Connection status
        """
        provider_label = self._get_provider_label(provider)
        if status:
            item = QListWidgetItem(f"{provider_label}: {email} ({status})")
        else:
            item = QListWidgetItem(f"{provider_label}: {email}")
        item.setData(
            Qt.ItemDataRole.UserRole, {"provider": provider, "email": email, "status": status}
        )
        self.accounts_list.addItem(item)

    def _get_provider_label(self, provider: str) -> str:
        providers_map = {}
        if isinstance(self.i18n.translations, dict):
            providers_map = self.i18n.translations.get("calendar_hub", {}).get("providers", {})
        if isinstance(providers_map, dict):
            label = providers_map.get(provider)
            if isinstance(label, str) and label:
                return label
        return provider.capitalize()

    def _get_calendar_hub_widget(self):
        """Return the existing calendar hub widget when available."""
        main_window = self.managers.get("main_window")
        if not main_window:
            return None
        pages = getattr(main_window, "pages", {})
        widget = pages.get("calendar_hub") if isinstance(pages, dict) else None
        return widget
