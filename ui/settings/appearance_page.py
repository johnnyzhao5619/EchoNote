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
Appearance settings page.

Provides UI for configuring theme settings.
"""

import logging
from typing import Any, Dict, Tuple

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QFrame, QLabel, QVBoxLayout

from ui.settings.base_page import BaseSettingsPage
from utils.i18n import I18nQtManager

logger = logging.getLogger("echonote.ui.settings.appearance")


class AppearanceSettingsPage(BaseSettingsPage):
    """Settings page for appearance configuration."""

    def __init__(self, settings_manager, i18n: I18nQtManager, managers: Dict[str, Any]):
        """
        Initialize appearance settings page.

        Args:
            settings_manager: SettingsManager instance
            i18n: Internationalization manager
            managers: Dictionary of other managers (for theme application)
        """
        super().__init__(settings_manager, i18n)
        self.managers = managers

        # Setup UI
        self.setup_ui()

        logger.debug("Appearance settings page initialized")

    def setup_ui(self):
        """Set up the appearance settings UI."""
        # Theme section
        from PySide6.QtGui import QFont

        font = QFont()
        font.setPointSize(12)
        font.setBold(True)

        self.theme_title = QLabel(self.i18n.t("settings.appearance.theme"))
        self.theme_title.setFont(font)
        self.content_layout.addWidget(self.theme_title)

        # Theme selection using mixin helper
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(
            [
                self.i18n.t("settings.appearance.light"),
                self.i18n.t("settings.appearance.dark"),
                self.i18n.t("settings.appearance.high_contrast"),
                self.i18n.t("settings.appearance.system"),
            ]
        )
        self.theme_combo.currentIndexChanged.connect(self._on_theme_changed)

        from ui.layout_utils import create_label_control_row

        theme_layout = create_label_control_row(
            self.i18n.t("settings.appearance.theme_select"), self.theme_combo
        )
        self.content_layout.addLayout(theme_layout)

        self.add_spacing(10)

        # Theme preview
        self.preview_label = QLabel(self.i18n.t("settings.appearance.preview"))
        self.content_layout.addWidget(self.preview_label)

        self.preview_frame = QFrame()
        self.preview_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.preview_frame.setMinimumHeight(150)

        preview_layout = QVBoxLayout(self.preview_frame)
        self.preview_text = QLabel(self.i18n.t("settings.appearance.preview_text"))
        self.preview_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview_layout.addWidget(self.preview_text)

        self.content_layout.addWidget(self.preview_frame)

        self.add_spacing(10)

        # Theme info
        self.info_label = QLabel(self.i18n.t("settings.appearance.theme_info"))
        self.info_label.setWordWrap(True)
        self.info_label.setProperty("role", "auto-start-desc")
        self.content_layout.addWidget(self.info_label)

        # Add stretch at the end
        self.content_layout.addStretch()

    def _on_theme_changed(self, index: int):
        """
        Handle theme selection change.

        Args:
            index: Selected theme index
        """
        # Map index to theme name
        theme_map = {0: "light", 1: "dark", 2: "high_contrast", 3: "system"}

        theme = theme_map.get(index, "light")

        # Apply theme immediately for preview
        if "main_window" in self.managers:
            main_window = self.managers["main_window"]
            if hasattr(main_window, "apply_theme"):
                main_window.apply_theme(theme)

        self._emit_changed()

        logger.debug(f"Theme changed to: {theme}")

    def load_settings(self):
        """Load appearance settings into UI."""
        try:
            # Theme
            theme = self.settings_manager.get_setting("ui.theme")
            if theme:
                # Map theme name to index
                theme_map = {"light": 0, "dark": 1, "high_contrast": 2, "system": 3}
                index = theme_map.get(theme, 0)
                self.theme_combo.setCurrentIndex(index)

            logger.debug("Appearance settings loaded")

        except Exception as e:
            logger.error(f"Error loading appearance settings: {e}")

    def save_settings(self):
        """Save appearance settings from UI."""
        try:
            # Theme
            theme_map = {0: "light", 1: "dark", 2: "high_contrast", 3: "system"}
            theme = theme_map.get(self.theme_combo.currentIndex(), "light")
            self.settings_manager.set_setting("ui.theme", theme)

            logger.debug("Appearance settings saved")

        except Exception as e:
            logger.error(f"Error saving appearance settings: {e}")
            raise

    def validate_settings(self) -> Tuple[bool, str]:
        """
        Validate appearance settings.

        Returns:
            Tuple of (is_valid, error_message)
        """
        # No validation needed
        return True, ""

    def update_translations(self):
        """Update UI text after language change."""
        # Update section title
        if hasattr(self, "theme_title"):
            self.theme_title.setText(self.i18n.t("settings.appearance.theme"))

        # Update labels
        if hasattr(self, "theme_label"):
            self.theme_label.setText(self.i18n.t("settings.appearance.theme_select"))
        if hasattr(self, "preview_label"):
            self.preview_label.setText(self.i18n.t("settings.appearance.preview"))
        if hasattr(self, "preview_text"):
            self.preview_text.setText(self.i18n.t("settings.appearance.preview_text"))
        if hasattr(self, "info_label"):
            self.info_label.setText(self.i18n.t("settings.appearance.theme_info"))

        # Update theme combo items
        if hasattr(self, "theme_combo"):
            current_index = self.theme_combo.currentIndex()
            self.theme_combo.blockSignals(True)
            self.theme_combo.clear()
            self.theme_combo.addItems(
                [
                    self.i18n.t("settings.appearance.light"),
                    self.i18n.t("settings.appearance.dark"),
                    self.i18n.t("settings.appearance.high_contrast"),
                    self.i18n.t("settings.appearance.system"),
                ]
            )
            self.theme_combo.setCurrentIndex(current_index)
            self.theme_combo.blockSignals(False)
