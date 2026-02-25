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
Base class for settings pages.

Provides common functionality for all settings pages.
"""

import logging
from typing import Any, Optional, Tuple, TypedDict

from core.qt_imports import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    Qt,
    QVBoxLayout,
    QWidget,
    Signal,
)

from ui.base_widgets import BaseWidget, create_hbox, create_vbox
from ui.constants import (
    LABEL_MIN_WIDTH,
    PAGE_COMPACT_SPACING,
    PAGE_CONTENT_MARGINS,
    PAGE_LAYOUT_SPACING,
    ZERO_MARGINS,
)
from utils.i18n import I18nQtManager

logger = logging.getLogger("echonote.ui.settings.base")


class PostSaveMessage(TypedDict, total=False):
    """Structured message returned by ``apply_post_save`` hooks."""

    level: str
    message: str
    source: str


class BaseSettingsPage(BaseWidget):
    """
    Base class for settings pages.

    Provides common layout and functionality for all settings pages.
    """

    # Signal emitted when settings change
    settings_changed = Signal()
    COMPACT_SPACING = PAGE_COMPACT_SPACING
    SECTION_SPACING = PAGE_LAYOUT_SPACING

    def __init__(self, settings_manager, i18n: I18nQtManager, parent=None):
        """
        Initialize base settings page.

        Args:
            settings_manager: SettingsManager instance
            i18n: Internationalization manager
            parent: Parent widget
        """
        super().__init__(i18n, parent)

        self.settings_manager = settings_manager
        self.i18n = i18n

        # Main layout
        self.main_layout = create_vbox(spacing=PAGE_LAYOUT_SPACING, margins=PAGE_CONTENT_MARGINS)
        self.setLayout(self.main_layout)

        # Create scroll area for content
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)

        # Content widget
        self.content_widget = QWidget()
        self.content_layout = create_vbox(spacing=PAGE_LAYOUT_SPACING, margins=ZERO_MARGINS)
        self.content_widget.setLayout(self.content_layout)

        scroll_area.setWidget(self.content_widget)
        self.main_layout.addWidget(scroll_area)

    def add_section_title(self, title: str, layout: QWidget | None = None) -> QLabel:
        """
        Add a section title to the page or specified layout.

        Args:
            title: Section title text
            layout: Optional layout or widget to add to. If None, uses self.content_layout.
        """
        label = QLabel(title)
        label.setObjectName("section_title")

        target = layout if layout is not None else self.content_layout
        if hasattr(target, "addWidget"):
            target.addWidget(label)
        elif hasattr(target, "layout") and target.layout():
            target.layout().addWidget(label)

        return label

    def add_labeled_row(
        self,
        label_text: str,
        control_widget: QWidget,
        *,
        label_width: int = LABEL_MIN_WIDTH,
        layout: QWidget | None = None,
    ) -> tuple:
        """Add a standard label-control row and return (layout, label)."""
        row_layout = create_hbox()
        label = QLabel(label_text)
        label.setMinimumWidth(label_width)
        row_layout.addWidget(label)
        row_layout.addWidget(control_widget)
        row_layout.addStretch()

        target = layout if layout is not None else self.content_layout
        if hasattr(target, "addLayout"):
            target.addLayout(row_layout)
        elif hasattr(target, "layout") and target.layout():
            target.layout().addLayout(row_layout)

        return row_layout, label

    def add_spacing(self, height: int | None = None, layout: QWidget | None = None):
        """
        Add vertical spacing.

        Args:
            height: Spacing height in pixels
            layout: Optional layout to add to. If None, uses self.content_layout.
        """
        if height is None:
            height = self.COMPACT_SPACING

        target = layout if layout is not None else self.content_layout
        if hasattr(target, "addSpacing"):
            target.addSpacing(height)
        elif hasattr(target, "layout") and target.layout():
            target.layout().addSpacing(height)

    def add_section_spacing(self, layout: QWidget | None = None):
        """
        Add standard spacing between major settings sections.

        Args:
            layout: Optional layout to add to. If None, uses self.content_layout.
        """
        self.add_spacing(self.SECTION_SPACING, layout=layout)

    def _clear_layout(self, layout):
        """
        Safely clear all widgets from a layout.

        Args:
            layout: The layout to clear
        """
        if layout is None:
            return
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
            else:
                self._clear_layout(item.layout())

    def load_settings(self):
        """
        Load settings into the page.

        Should be overridden by subclasses.
        """

    def save_settings(self):
        """
        Save settings from the page.

        Should be overridden by subclasses.
        """

    def apply_post_save(self):
        """
        Apply runtime side effects after global settings save succeeds.

        Subclasses can override this for non-persistent follow-up actions
        (engine reload, key refresh, etc.). Optional return value:
        list[PostSaveMessage].
        """

    def validate_settings(self) -> Tuple[bool, str]:
        """
        Validate settings before saving.

        Should be overridden by subclasses if validation is needed.

        Returns:
            Tuple of (is_valid, error_message)
        """
        return True, ""

    def update_translations(self):
        """
        Update UI text after language change.

        Should be overridden by subclasses.
        """

    def _emit_changed(self):
        """Emit settings changed signal."""
        self.settings_changed.emit()

    def _set_setting_or_raise(self, key: str, value):
        """
        Persist a setting and raise when manager rejects it.

        Args:
            key: Setting key in dot notation
            value: Value to store
        """
        updated = self.settings_manager.set_setting(key, value)
        if not updated:
            raise ValueError(self.i18n.t("settings.error.setting_update_failed", key=key))

    def _navigate_to_settings_page(self, page_id: str) -> bool:
        """Navigate to a specific settings page when hosted inside ``SettingsWidget``."""
        parent_widget = self.parentWidget()
        while parent_widget is not None:
            show_page = getattr(parent_widget, "show_page", None)
            if callable(show_page):
                try:
                    return bool(show_page(page_id))
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Failed to navigate to settings page '%s': %s", page_id, exc)
                    return False
            parent_widget = parent_widget.parentWidget()
        return False

    def _find_settings_page_instance(self, page_id: str) -> Optional[Any]:
        """Return settings page instance from nearest ``SettingsWidget`` container."""
        parent_widget = self.parentWidget()
        while parent_widget is not None:
            settings_pages = getattr(parent_widget, "settings_pages", None)
            if isinstance(settings_pages, dict):
                return settings_pages.get(page_id)
            parent_widget = parent_widget.parentWidget()
        return None

    def _open_settings_page(self, page_id: str) -> Optional[Any]:
        """
        Navigate to settings page and return its instance when available.

        Flow:
        1. If already inside SettingsWidget, switch there directly.
        2. Otherwise switch main window to settings page and then select target.
        """
        if self._navigate_to_settings_page(page_id):
            page = self._find_settings_page_instance(page_id)
            if page is not None:
                return page

        main_window = self.window()
        if main_window is None or not hasattr(main_window, "switch_page"):
            return None

        main_window.switch_page("settings")
        settings_widget = getattr(main_window, "pages", {}).get("settings")
        if settings_widget and hasattr(settings_widget, "show_page"):
            if settings_widget.show_page(page_id):
                settings_pages = getattr(settings_widget, "settings_pages", None)
                if isinstance(settings_pages, dict):
                    return settings_pages.get(page_id)
        return None
