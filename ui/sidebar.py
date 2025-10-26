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
Sidebar navigation for EchoNote application.

Provides navigation buttons for switching between different features.
"""

import logging
from typing import Dict, Optional

from PySide6.QtCore import Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QPushButton, QSizePolicy, QVBoxLayout, QWidget

from utils.i18n import I18nQtManager

logger = logging.getLogger("echonote.ui.sidebar")


class Sidebar(QWidget):
    """
    Sidebar navigation widget with buttons for different pages.

    Emits page_changed signal when a navigation button is clicked.
    """

    # Signal emitted when page changes
    page_changed = Signal(str)

    def __init__(self, i18n: I18nQtManager):
        """
        Initialize sidebar.

        Args:
            i18n: Internationalization manager
        """
        super().__init__()

        self.i18n = i18n

        # Dictionary to store navigation buttons
        self.nav_buttons: Dict[str, QPushButton] = {}

        # Current active page
        self.current_page: Optional[str] = None

        # Setup UI
        self.setup_ui()

        # Connect language change signal
        self.i18n.language_changed.connect(self._on_language_changed)

        logger.debug("Sidebar initialized")

    def setup_ui(self):
        """Set up the sidebar UI."""
        # Set fixed width for sidebar
        self.setFixedWidth(200)

        # Set object name for styling
        self.setObjectName("sidebar")

        # Create layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Add spacing at top
        layout.addSpacing(20)

        # Create navigation buttons
        self._create_nav_buttons(layout)

        # Add stretch to push buttons to top
        layout.addStretch()

        # Set default active page
        self.set_active_page("batch_transcribe")

    def _create_nav_buttons(self, layout: QVBoxLayout):
        """
        Create navigation buttons.

        Args:
            layout: Layout to add buttons to
        """
        # Define navigation items
        nav_items = [
            {
                "name": "batch_transcribe",
                "text_key": "sidebar.batch_transcribe",
                "icon": None,  # Icons will be added in task 9.4
            },
            {
                "name": "realtime_record",
                "text_key": "sidebar.realtime_record",
                "icon": None,
            },
            {"name": "calendar_hub", "text_key": "sidebar.calendar_hub", "icon": None},
            {"name": "timeline", "text_key": "sidebar.timeline", "icon": None},
            {"name": "settings", "text_key": "sidebar.settings", "icon": None},
        ]

        # Create button for each navigation item
        for item in nav_items:
            button = self._create_nav_button(item["name"], item["text_key"], item["icon"])

            # Add to layout
            layout.addWidget(button)

            # Store reference
            self.nav_buttons[item["name"]] = button

        logger.debug(f"Created {len(nav_items)} navigation buttons")

    def _create_nav_button(
        self, name: str, text_key: str, icon: Optional[str] = None
    ) -> QPushButton:
        """
        Create a single navigation button.

        Args:
            name: Internal name for the button
            text_key: Translation key for button text
            icon: Optional icon path

        Returns:
            Navigation button
        """
        button = QPushButton()

        # Set button properties
        button.setObjectName(f"nav_button_{name}")
        button.setCheckable(True)
        button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        button.setMinimumHeight(50)

        # Set text from translation
        button.setText(self.i18n.t(text_key))

        # Set icon if provided
        if icon:
            button.setIcon(QIcon(icon))

        # Connect click event
        button.clicked.connect(lambda: self._on_button_clicked(name))

        return button

    def _on_button_clicked(self, page_name: str):
        """
        Handle navigation button click.

        Args:
            page_name: Name of the page to navigate to
        """
        # Set this button as active
        self.set_active_page(page_name)

        # Emit page changed signal
        self.page_changed.emit(page_name)

        logger.debug(f"Navigation button clicked: {page_name}")

    def set_active_page(self, page_name: str):
        """
        Set the active page and update button states.

        Args:
            page_name: Name of the page to set as active
        """
        if page_name not in self.nav_buttons:
            logger.warning(f"Page '{page_name}' not found in navigation buttons")
            return

        # Update button states
        for name, button in self.nav_buttons.items():
            if name == page_name:
                button.setChecked(True)
                button.setProperty("active", True)
            else:
                button.setChecked(False)
                button.setProperty("active", False)

            # Force style update
            button.style().unpolish(button)
            button.style().polish(button)

        self.current_page = page_name

        logger.debug(f"Active page set to: {page_name}")

    def _on_language_changed(self, language: str):
        """
        Handle language change event.

        Args:
            language: New language code
        """
        logger.debug(f"Updating sidebar text for language: {language}")

        # Update button text
        button_text_keys = {
            "batch_transcribe": "sidebar.batch_transcribe",
            "realtime_record": "sidebar.realtime_record",
            "calendar_hub": "sidebar.calendar_hub",
            "timeline": "sidebar.timeline",
            "settings": "sidebar.settings",
        }

        for name, text_key in button_text_keys.items():
            if name in self.nav_buttons:
                button = self.nav_buttons[name]
                button.setText(self.i18n.t(text_key))
