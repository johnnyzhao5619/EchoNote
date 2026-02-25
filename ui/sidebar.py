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

from ui.base_widgets import BaseWidget
from ui.common.style_utils import set_widget_dynamic_property
from ui.navigation import NAV_ITEMS, NAV_PAGE_ORDER, NavigationItem
from core.qt_imports import (
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QPushButton,
    Qt,
    QVBoxLayout,
    QWidget,
    Signal,
    QSizePolicy,
    QStyle,
    QSize,
)
from ui.constants import (
    DEFAULT_LAYOUT_SPACING,
    ROLE_SIDEBAR_NAV_BUTTON,
    SIDEBAR_BUTTON_ICON_SIZE,
    SIDEBAR_BUTTON_MIN_HEIGHT,
    SIDEBAR_CONTAINER_MARGIN,
    SIDEBAR_WIDTH,
)
from utils.i18n import I18nQtManager

logger = logging.getLogger("echonote.ui.sidebar")


class Sidebar(BaseWidget):
    """
    Sidebar navigation widget with buttons for different pages.

    Emits page_changed signal when a navigation button is clicked.
    """

    # Signal emitted when page changes
    page_changed = Signal(str)

    def __init__(self, i18n: I18nQtManager, parent=None):
        """
        Initialize sidebar.

        Args:
            i18n: Internationalization manager
            parent: Parent widget
        """
        # Initialize attributes before creating UI elements.
        self.nav_buttons: Dict[str, QPushButton] = {}
        self.current_page: Optional[str] = None

        super().__init__(i18n, parent)

        # Setup UI
        self.setup_ui()

        # Connect language change signal
        self.i18n.language_changed.connect(self._on_language_changed)

        logger.debug("Sidebar initialized")

    def setup_ui(self):
        """Set up the sidebar UI."""
        # Set fixed width for sidebar

        self.setFixedWidth(SIDEBAR_WIDTH)
        self._icon_size = QSize(SIDEBAR_BUTTON_ICON_SIZE, SIDEBAR_BUTTON_ICON_SIZE)

        # Set object name for styling
        self.setObjectName("sidebar")

        # Create layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            SIDEBAR_CONTAINER_MARGIN,
            SIDEBAR_CONTAINER_MARGIN,
            SIDEBAR_CONTAINER_MARGIN,
            SIDEBAR_CONTAINER_MARGIN,
        )
        layout.setSpacing(DEFAULT_LAYOUT_SPACING)

        # Add spacing at top
        layout.addSpacing(DEFAULT_LAYOUT_SPACING)

        # Create navigation buttons
        self._create_nav_buttons(layout)

        # Add stretch to push buttons to top
        layout.addStretch()

        # Set default active page
        self.set_active_page(NAV_PAGE_ORDER[0])

    def _create_nav_buttons(self, layout: QVBoxLayout):
        """
        Create navigation buttons.

        Args:
            layout: Layout to add buttons to
        """
        # Create button for each navigation item
        for item in NAV_ITEMS:
            button = self._create_nav_button(item)

            # Add to layout
            layout.addWidget(button)

            # Store reference
            self.nav_buttons[item.page_name] = button

        logger.debug("Created %d navigation buttons", len(NAV_ITEMS))

    def _resolve_icon(self, item: NavigationItem):
        """Resolve a standard icon for a navigation item."""
        icon_map = {
            "file_list": QStyle.StandardPixmap.SP_FileDialogListView,
            "record": QStyle.StandardPixmap.SP_MediaPlay,
            "calendar": QStyle.StandardPixmap.SP_FileDialogContentsView,
            "timeline": QStyle.StandardPixmap.SP_BrowserReload,
            "settings": QStyle.StandardPixmap.SP_FileDialogDetailedView,
        }
        pixmap = icon_map.get(item.icon_name)
        if pixmap is None:
            return None
        return self.style().standardIcon(pixmap)

    def _create_nav_button(self, item: NavigationItem) -> QPushButton:
        """
        Create a single navigation button.

        Args:
            item: Navigation item configuration

        Returns:
            Navigation button
        """
        button = QPushButton()

        # Set button properties
        button.setObjectName(f"nav_button_{item.page_name}")
        button.setCheckable(True)
        button.setProperty("role", ROLE_SIDEBAR_NAV_BUTTON)
        button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        # Set text from translation
        button.setText(self.i18n.t(item.text_key))
        button.setToolTip(self.i18n.t(item.text_key))

        # Set icon from standard style set
        icon = self._resolve_icon(item)
        if icon is not None:
            button.setIcon(icon)
            button.setIconSize(self._icon_size)

        # Connect click event
        button.clicked.connect(lambda: self._on_button_clicked(item.page_name))

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
                set_widget_dynamic_property(button, "active", True)
            else:
                button.setChecked(False)
                set_widget_dynamic_property(button, "active", False)

        self.current_page = page_name

        logger.debug(f"Active page set to: {page_name}")

    def _on_language_changed(self, language: str):
        """
        Handle language change event.

        Args:
            language: New language code
        """
        logger.debug(f"Updating sidebar text for language: {language}")

        for item in NAV_ITEMS:
            button = self.nav_buttons.get(item.page_name)
            if button is None:
                continue
            translated = self.i18n.t(item.text_key)
            button.setText(translated)
            button.setToolTip(translated)
