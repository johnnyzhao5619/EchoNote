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
Settings widget for EchoNote application.

Provides a comprehensive settings interface with categorized pages
for configuring all application features.
"""

import logging
from typing import Any, Dict

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ui.base_widgets import BaseWidget, create_hbox, create_vbox, create_button
from utils.i18n import I18nQtManager

logger = logging.getLogger("echonote.ui.settings")


class SettingsWidget(BaseWidget):
    """
    Main settings widget with categorized navigation and pages.

    Provides a two-panel layout with category list on the left
    and settings pages on the right.
    """

    # Signal emitted when settings are saved
    settings_saved = Signal()

    def __init__(
        self, settings_manager, i18n: I18nQtManager, managers: Dict[str, Any], parent=None
    ):
        """
        Initialize settings widget.

        Args:
            settings_manager: SettingsManager instance
            i18n: Internationalization manager
            managers: Dictionary of other managers (for API key testing, etc.)
            parent: Parent widget
        """
        super().__init__(i18n, parent)

        self.settings_manager = settings_manager
        self.managers = managers

        # Track unsaved changes
        self.has_unsaved_changes = False

        # Store original settings for change detection
        self.original_settings: Dict[str, Any] = {}

        # Settings pages dictionary
        self.settings_pages: Dict[str, QWidget] = {}

        # Setup UI
        self.setup_ui()

        # Load current settings
        self.load_settings()

        # Connect language change signal
        self.i18n.language_changed.connect(self._on_language_changed)

        logger.info(self.i18n.t("logging.settings.widget_initialized"))

    def setup_ui(self):
        """Set up the settings UI layout."""
        # Main layout
        main_layout = QVBoxLayout(self)
        # # main_layout.setSpacing(10)

        # Title
        self.title_label = QLabel(self.i18n.t("settings.title"))
        self.title_label.setObjectName("page_title")
        main_layout.addWidget(self.title_label)

        # Content layout (category list + pages)
        content_layout = create_hbox(spacing=20)

        # Category list
        self.category_list = self._create_category_list()
        content_layout.addWidget(self.category_list)

        # Settings pages container
        self.pages_container = QStackedWidget()
        self._create_settings_pages()
        content_layout.addWidget(self.pages_container, stretch=1)

        main_layout.addLayout(content_layout, stretch=1)

        # Now that pages_container is created, select first category
        # This will trigger _on_category_changed which needs pages_container
        self.category_list.setCurrentRow(0)

        # Separator line
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        main_layout.addWidget(separator)

        # Button layout
        button_layout = create_hbox()
        button_layout.addStretch()

        # Reset button
        self.reset_button = create_button(self.i18n.t("settings.reset"))
        self.reset_button.clicked.connect(self._on_reset_clicked)
        button_layout.addWidget(self.reset_button)

        # Cancel button
        self.cancel_button = create_button(self.i18n.t("settings.cancel"))
        self.cancel_button.clicked.connect(self._on_cancel_clicked)
        button_layout.addWidget(self.cancel_button)

        # Save button
        self.save_button = create_button(self.i18n.t("settings.save"))
        self.save_button.clicked.connect(self._on_save_clicked)
        self.save_button.setDefault(True)
        button_layout.addWidget(self.save_button)

        main_layout.addLayout(button_layout)

        logger.debug("Settings UI setup complete")

    def _create_category_list(self) -> QListWidget:
        """
        Create category navigation list.

        Returns:
            Category list widget
        """
        category_list = QListWidget()
        category_list.setFixedWidth(200)

        # Define categories
        categories = [
            ("transcription", "settings.category.transcription"),
            ("realtime", "settings.category.realtime"),
            ("model_management", "settings.category.model_management"),
            ("calendar", "settings.category.calendar"),
            ("timeline", "settings.category.timeline"),
            ("appearance", "settings.category.appearance"),
            ("language", "settings.category.language"),
        ]

        # Add category items
        for category_id, text_key in categories:
            item = QListWidgetItem(self.i18n.t(text_key))
            item.setData(Qt.ItemDataRole.UserRole, category_id)
            category_list.addItem(item)

        # Connect selection change
        category_list.currentRowChanged.connect(self._on_category_changed)

        # Don't select first category here - will be done after pages are created
        # to avoid triggering signal before pages_container exists

        return category_list

    def _create_settings_pages(self):
        """Create all settings pages and add to container."""
        try:
            # Import page classes
            from ui.settings.appearance_page import AppearanceSettingsPage
            from ui.settings.calendar_page import CalendarSettingsPage
            from ui.settings.language_page import LanguageSettingsPage
            from ui.settings.model_management_page import ModelManagementPage
            from ui.settings.realtime_page import RealtimeSettingsPage
            from ui.settings.timeline_page import TimelineSettingsPage
            from ui.settings.transcription_page import TranscriptionSettingsPage

            # Create pages
            pages = [
                (
                    "transcription",
                    TranscriptionSettingsPage(self.settings_manager, self.i18n, self.managers),
                ),
                ("realtime", RealtimeSettingsPage(self.settings_manager, self.i18n)),
                ("calendar", CalendarSettingsPage(self.settings_manager, self.i18n, self.managers)),
                ("timeline", TimelineSettingsPage(self.settings_manager, self.i18n)),
                (
                    "appearance",
                    AppearanceSettingsPage(self.settings_manager, self.i18n, self.managers),
                ),
                ("language", LanguageSettingsPage(self.settings_manager, self.i18n)),
            ]

            # Add model management page if model_manager is available
            if "model_manager" in self.managers:
                model_management_page = ModelManagementPage(
                    self.settings_manager, self.i18n, self.managers["model_manager"]
                )
                # Insert after realtime page (index 2)
                pages.insert(2, ("model_management", model_management_page))
            else:
                logger.warning(self.i18n.t("logging.settings.model_manager_not_available"))

            # Add pages to container
            for page_id, page_widget in pages:
                self.pages_container.addWidget(page_widget)
                self.settings_pages[page_id] = page_widget

                # Connect change signal
                if hasattr(page_widget, "settings_changed"):
                    page_widget.settings_changed.connect(self._on_settings_changed)

            logger.debug(f"Created {len(pages)} settings pages")

        except Exception as e:
            logger.error(f"Error creating settings pages: {e}", exc_info=True)
            # Create placeholder pages if real ones fail
            from PySide6.QtWidgets import QLabel, QVBoxLayout

            categories = [
                "transcription",
                "realtime",
                "model_management",
                "calendar",
                "timeline",
                "appearance",
                "language",
            ]

            for category in categories:
                placeholder = QWidget()
                layout = QVBoxLayout(placeholder)
                label = QLabel(f"Settings page for {category}\n(Error loading: {str(e)})")
                label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                layout.addWidget(label)

                self.pages_container.addWidget(placeholder)
                self.settings_pages[category] = placeholder

            logger.warning(f"Created {len(categories)} placeholder settings pages")

    def _on_category_changed(self, index: int):
        """
        Handle category selection change.

        Args:
            index: Selected category index
        """
        # Switch to corresponding page
        self.pages_container.setCurrentIndex(index)

        logger.debug(f"Switched to settings category: {index}")

    def load_settings(self):
        """Load current settings into all pages."""
        try:
            # Store original settings for change detection
            self.original_settings = self.settings_manager.get_all_settings()

            # Load settings into each page
            for page_widget in self.settings_pages.values():
                if hasattr(page_widget, "load_settings"):
                    page_widget.load_settings()

            # Reset change flag
            self.has_unsaved_changes = False
            self._update_button_states()

            logger.debug("Settings loaded")

        except Exception as e:
            logger.error(f"Error loading settings: {e}")
            self.show_error(
                self.i18n.t("settings.error.title"),
                self.i18n.t("settings.error.load_failed", error=str(e)),
            )

    def save_settings(self) -> bool:
        """
        Save settings from all pages.

        Returns:
            True if settings were saved successfully
        """
        try:
            # Validate settings in all pages
            for page_id, page_widget in self.settings_pages.items():
                if hasattr(page_widget, "validate_settings"):
                    is_valid, error_msg = page_widget.validate_settings()
                    if not is_valid:
                        self.show_warning(self.i18n.t("settings.validation.title"), error_msg)
                        # Switch to the page with error
                        page_index = list(self.settings_pages.keys()).index(page_id)
                        self.category_list.setCurrentRow(page_index)
                        return False

            # Save settings from each page
            for page_widget in self.settings_pages.values():
                if hasattr(page_widget, "save_settings"):
                    page_widget.save_settings()

            # Persist to disk
            if not self.settings_manager.save_settings():
                raise Exception(self.i18n.t("exceptions.settings.failed_to_save_to_disk"))

            # Update original settings
            self.original_settings = self.settings_manager.get_all_settings()

            # Reset change flag
            self.has_unsaved_changes = False
            self._update_button_states()

            # Emit signal
            self.settings_saved.emit()

            # Show success message
            self.show_info(
                self.i18n.t("settings.success.title"), self.i18n.t("settings.success.saved")
            )

            logger.info(self.i18n.t("logging.settings.saved_successfully"))
            return True

        except Exception as e:
            logger.error(f"Error saving settings: {e}")
            self.show_error(
                self.i18n.t("settings.error.title"),
                self.i18n.t("settings.error.save_failed", error=str(e)),
            )
            return False

    def _on_settings_changed(self):
        """Handle settings change in any page."""
        self.has_unsaved_changes = True
        self._update_button_states()

    def _update_button_states(self):
        """Update button enabled states based on changes."""
        self.save_button.setEnabled(self.has_unsaved_changes)
        self.cancel_button.setEnabled(self.has_unsaved_changes)

    def _on_save_clicked(self):
        """Handle save button click."""
        self.save_settings()

    def _on_cancel_clicked(self):
        """Handle cancel button click."""
        if self.has_unsaved_changes:
            # Confirm discard changes
            reply = QMessageBox.question(
                self,
                self.i18n.t("settings.confirm.title"),
                self.i18n.t("settings.confirm.discard_changes"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )

            if reply == QMessageBox.StandardButton.Yes:
                # Reload original settings
                self.load_settings()

    def _on_reset_clicked(self):
        """Handle reset button click."""
        # Confirm reset
        reply = QMessageBox.question(
            self,
            self.i18n.t("settings.confirm.title"),
            self.i18n.t("settings.confirm.reset_defaults"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                # Reset all settings to defaults
                self.settings_manager.reset_to_default()

                # Reload settings
                self.load_settings()

                self.show_info(
                    self.i18n.t("settings.success.title"),
                    self.i18n.t("settings.success.reset"),
                )

                logger.info(self.i18n.t("logging.settings.reset_to_defaults"))

            except Exception as e:
                logger.error(f"Error resetting settings: {e}")
                self.show_error(
                    self.i18n.t("settings.error.title"),
                    self.i18n.t("settings.error.reset_failed", error=str(e)),
                )

    def _on_language_changed(self, language: str):
        """
        Handle language change event.

        Args:
            language: New language code
        """
        logger.debug(f"Updating settings text for language: {language}")

        # Update title
        self.title_label.setText(self.i18n.t("settings.title"))

        # Update UI text
        # Note: This is a simplified implementation
        # In a real app, you'd update all text elements
        self.save_button.setText(self.i18n.t("settings.save"))
        self.cancel_button.setText(self.i18n.t("settings.cancel"))
        self.reset_button.setText(self.i18n.t("settings.reset"))

        # Update category list
        for i in range(self.category_list.count()):
            item = self.category_list.item(i)
            category_id = item.data(Qt.ItemDataRole.UserRole)
            item.setText(self.i18n.t(f"settings.category.{category_id}"))

        # Update pages
        for page_widget in self.settings_pages.values():
            if hasattr(page_widget, "update_translations"):
                page_widget.update_translations()

    def check_unsaved_changes(self) -> bool:
        """
        Check if there are unsaved changes and prompt user.

        Returns:
            True if it's safe to proceed (no changes or user confirmed discard)
        """
        if not self.has_unsaved_changes:
            return True

        reply = QMessageBox.question(
            self,
            self.i18n.t("settings.confirm.title"),
            self.i18n.t("settings.confirm.discard_changes"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        return reply == QMessageBox.StandardButton.Yes
