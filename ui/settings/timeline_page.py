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
Timeline settings page.

Provides UI for configuring timeline view and auto-task settings.
"""

import logging
from typing import Tuple

from PySide6.QtWidgets import QCheckBox, QComboBox, QLabel, QSpinBox

from config.constants import (
    STANDARD_LABEL_WIDTH,
    TIMELINE_AUTO_STOP_GRACE_MAX_MINUTES,
    TIMELINE_REMINDER_MINUTES_OPTIONS,
    TIMELINE_STOP_CONFIRMATION_DELAY_MAX_MINUTES,
)
from ui.base_widgets import create_hbox
from ui.settings.base_page import BaseSettingsPage
from utils.i18n import I18nQtManager

logger = logging.getLogger("echonote.ui.settings.timeline")


class TimelineSettingsPage(BaseSettingsPage):
    """Settings page for timeline configuration."""

    def __init__(self, settings_manager, i18n: I18nQtManager):
        """
        Initialize timeline settings page.

        Args:
            settings_manager: SettingsManager instance
            i18n: Internationalization manager
        """
        super().__init__(settings_manager, i18n)

        # Setup UI
        self.setup_ui()

        logger.debug("Timeline settings page initialized")

    def setup_ui(self):
        """Set up the timeline settings UI."""
        # View range section
        self.view_range_title = self.add_section_title(self.i18n.t("settings.timeline.view_range"))

        # Past days
        self.past_days_spin = QSpinBox()
        self.past_days_spin.setMinimum(1)
        self.past_days_spin.setMaximum(365)
        self.past_days_spin.setValue(30)
        self.past_days_spin.setSuffix(" " + self.i18n.t("settings.timeline.days"))
        self.past_days_spin.valueChanged.connect(self._emit_changed)
        _, self.past_label = self.add_labeled_row(
            self.i18n.t("settings.timeline.past_days"),
            self.past_days_spin,
            label_width=STANDARD_LABEL_WIDTH,
        )

        # Future days
        self.future_days_spin = QSpinBox()
        self.future_days_spin.setMinimum(1)
        self.future_days_spin.setMaximum(365)
        self.future_days_spin.setValue(30)
        self.future_days_spin.setSuffix(" " + self.i18n.t("settings.timeline.days"))
        self.future_days_spin.valueChanged.connect(self._emit_changed)
        _, self.future_label = self.add_labeled_row(
            self.i18n.t("settings.timeline.future_days"),
            self.future_days_spin,
            label_width=STANDARD_LABEL_WIDTH,
        )

        # Page size
        self.page_size_spin = QSpinBox()
        self.page_size_spin.setMinimum(1)
        self.page_size_spin.setMaximum(500)
        self.page_size_spin.setValue(50)
        self.page_size_spin.valueChanged.connect(self._emit_changed)
        _, self.page_size_label = self.add_labeled_row(
            self.i18n.t("settings.timeline.page_size"),
            self.page_size_spin,
            label_width=STANDARD_LABEL_WIDTH,
        )

        self.add_section_spacing()

        # Notification settings section
        self.notifications_title = self.add_section_title(self.i18n.t("settings.timeline.notifications"))

        # Reminder time
        reminder_layout = create_hbox()
        self.reminder_label = QLabel(self.i18n.t("settings.timeline.reminder_time"))
        self.reminder_label.setMinimumWidth(STANDARD_LABEL_WIDTH)
        self.reminder_combo = QComboBox()
        self.reminder_combo.addItems([str(minutes) for minutes in TIMELINE_REMINDER_MINUTES_OPTIONS])
        self.reminder_combo.currentTextChanged.connect(self._emit_changed)
        self.reminder_suffix = QLabel(self.i18n.t("settings.timeline.minutes"))
        reminder_layout.addWidget(self.reminder_label)
        reminder_layout.addWidget(self.reminder_combo)
        reminder_layout.addWidget(self.reminder_suffix)
        reminder_layout.addStretch()
        self.content_layout.addLayout(reminder_layout)

        # Auto-stop grace time
        self.auto_stop_grace_spin = QSpinBox()
        self.auto_stop_grace_spin.setMinimum(0)
        self.auto_stop_grace_spin.setMaximum(TIMELINE_AUTO_STOP_GRACE_MAX_MINUTES)
        self.auto_stop_grace_spin.setSuffix(" " + self.i18n.t("settings.timeline.minutes"))
        self.auto_stop_grace_spin.valueChanged.connect(self._emit_changed)
        _, self.auto_stop_grace_label = self.add_labeled_row(
            self.i18n.t("settings.timeline.auto_stop_grace_minutes"),
            self.auto_stop_grace_spin,
            label_width=STANDARD_LABEL_WIDTH,
        )

        self.auto_stop_grace_desc = QLabel(
            self.i18n.t("settings.timeline.auto_stop_grace_description")
        )
        self.auto_stop_grace_desc.setWordWrap(True)
        self.auto_stop_grace_desc.setProperty("role", "auto-start-desc")
        self.content_layout.addWidget(self.auto_stop_grace_desc)

        self.stop_confirmation_delay_spin = QSpinBox()
        self.stop_confirmation_delay_spin.setMinimum(1)
        self.stop_confirmation_delay_spin.setMaximum(TIMELINE_STOP_CONFIRMATION_DELAY_MAX_MINUTES)
        self.stop_confirmation_delay_spin.setSuffix(" " + self.i18n.t("settings.timeline.minutes"))
        self.stop_confirmation_delay_spin.valueChanged.connect(self._emit_changed)
        _, self.stop_confirmation_delay_label = self.add_labeled_row(
            self.i18n.t("settings.timeline.stop_confirmation_delay_minutes"),
            self.stop_confirmation_delay_spin,
            label_width=STANDARD_LABEL_WIDTH,
        )

        self.stop_confirmation_delay_desc = QLabel(
            self.i18n.t("settings.timeline.stop_confirmation_delay_description")
        )
        self.stop_confirmation_delay_desc.setWordWrap(True)
        self.stop_confirmation_delay_desc.setProperty("role", "auto-start-desc")
        self.content_layout.addWidget(self.stop_confirmation_delay_desc)

        self.add_section_spacing()

        # Auto-start settings section
        self.auto_start_title = self.add_section_title(self.i18n.t("settings.timeline.auto_start"))

        # Enable auto-start
        self.auto_start_check = QCheckBox(self.i18n.t("settings.timeline.enable_auto_start"))
        self.auto_start_check.stateChanged.connect(self._emit_changed)
        self.content_layout.addWidget(self.auto_start_check)

        # Description
        self.auto_start_desc = QLabel(self.i18n.t("settings.timeline.auto_start_description"))
        self.auto_start_desc.setWordWrap(True)
        self.auto_start_desc.setProperty("role", "auto-start-desc")
        self.content_layout.addWidget(self.auto_start_desc)

        # Add stretch at the end
        self.content_layout.addStretch()

    def load_settings(self):
        """Load timeline settings into UI."""
        try:
            # View range
            past_days = self.settings_manager.get_setting("timeline.past_days")
            if past_days is not None:
                self.past_days_spin.setValue(past_days)

            future_days = self.settings_manager.get_setting("timeline.future_days")
            if future_days is not None:
                self.future_days_spin.setValue(future_days)

            page_size = self.settings_manager.get_setting("timeline.page_size")
            if page_size is not None:
                self.page_size_spin.setValue(page_size)

            # Reminder time
            reminder_minutes = self.settings_manager.get_setting("timeline.reminder_minutes")
            if reminder_minutes is not None:
                index = self.reminder_combo.findText(str(reminder_minutes))
                if index >= 0:
                    self.reminder_combo.setCurrentIndex(index)

            auto_stop_grace_minutes = self.settings_manager.get_setting(
                "timeline.auto_stop_grace_minutes"
            )
            if auto_stop_grace_minutes is not None:
                self.auto_stop_grace_spin.setValue(int(auto_stop_grace_minutes))
            stop_confirmation_delay_minutes = self.settings_manager.get_setting(
                "timeline.stop_confirmation_delay_minutes"
            )
            if stop_confirmation_delay_minutes is not None:
                self.stop_confirmation_delay_spin.setValue(int(stop_confirmation_delay_minutes))

            # Auto-start (if this setting exists)
            auto_start = self.settings_manager.get_setting("timeline.auto_start_enabled")
            if auto_start is not None:
                self.auto_start_check.setChecked(auto_start)

            logger.debug("Timeline settings loaded")

        except Exception as e:
            logger.error(f"Error loading timeline settings: {e}")

    def save_settings(self):
        """Save timeline settings from UI."""
        try:
            # View range
            self._set_setting_or_raise("timeline.past_days", self.past_days_spin.value())

            self._set_setting_or_raise("timeline.future_days", self.future_days_spin.value())
            self._set_setting_or_raise("timeline.page_size", self.page_size_spin.value())

            # Reminder time
            reminder_minutes = int(self.reminder_combo.currentText())
            self._set_setting_or_raise("timeline.reminder_minutes", reminder_minutes)
            self._set_setting_or_raise(
                "timeline.auto_stop_grace_minutes", self.auto_stop_grace_spin.value()
            )
            self._set_setting_or_raise(
                "timeline.stop_confirmation_delay_minutes",
                self.stop_confirmation_delay_spin.value(),
            )

            # Auto-start
            self._set_setting_or_raise(
                "timeline.auto_start_enabled", self.auto_start_check.isChecked()
            )

            logger.debug("Timeline settings saved")

        except Exception as e:
            logger.error(f"Error saving timeline settings: {e}")
            raise

    def validate_settings(self) -> Tuple[bool, str]:
        """
        Validate timeline settings.

        Returns:
            Tuple of (is_valid, error_message)
        """
        # All settings have valid ranges enforced by spinboxes/combos
        return True, ""

    def update_translations(self):
        """Update UI text after language change."""
        # Update section titles
        if hasattr(self, "view_range_title"):
            self.view_range_title.setText(self.i18n.t("settings.timeline.view_range"))
        if hasattr(self, "notifications_title"):
            self.notifications_title.setText(self.i18n.t("settings.timeline.notifications"))
        if hasattr(self, "auto_start_title"):
            self.auto_start_title.setText(self.i18n.t("settings.timeline.auto_start"))

        # Update labels
        if hasattr(self, "past_label"):
            self.past_label.setText(self.i18n.t("settings.timeline.past_days"))
        if hasattr(self, "future_label"):
            self.future_label.setText(self.i18n.t("settings.timeline.future_days"))
        if hasattr(self, "page_size_label"):
            self.page_size_label.setText(self.i18n.t("settings.timeline.page_size"))
        if hasattr(self, "reminder_label"):
            self.reminder_label.setText(self.i18n.t("settings.timeline.reminder_time"))
        if hasattr(self, "reminder_suffix"):
            self.reminder_suffix.setText(self.i18n.t("settings.timeline.minutes"))
        if hasattr(self, "auto_stop_grace_label"):
            self.auto_stop_grace_label.setText(
                self.i18n.t("settings.timeline.auto_stop_grace_minutes")
            )
        if hasattr(self, "auto_stop_grace_desc"):
            self.auto_stop_grace_desc.setText(
                self.i18n.t("settings.timeline.auto_stop_grace_description")
            )
        if hasattr(self, "stop_confirmation_delay_label"):
            self.stop_confirmation_delay_label.setText(
                self.i18n.t("settings.timeline.stop_confirmation_delay_minutes")
            )
        if hasattr(self, "stop_confirmation_delay_desc"):
            self.stop_confirmation_delay_desc.setText(
                self.i18n.t("settings.timeline.stop_confirmation_delay_description")
            )

        # Update checkbox
        if hasattr(self, "auto_start_check"):
            self.auto_start_check.setText(self.i18n.t("settings.timeline.enable_auto_start"))

        # Update description
        if hasattr(self, "auto_start_desc"):
            self.auto_start_desc.setText(self.i18n.t("settings.timeline.auto_start_description"))

        # Update spinbox suffixes
        if hasattr(self, "past_days_spin"):
            self.past_days_spin.setSuffix(" " + self.i18n.t("settings.timeline.days"))
        if hasattr(self, "future_days_spin"):
            self.future_days_spin.setSuffix(" " + self.i18n.t("settings.timeline.days"))
        if hasattr(self, "auto_stop_grace_spin"):
            self.auto_stop_grace_spin.setSuffix(" " + self.i18n.t("settings.timeline.minutes"))
        if hasattr(self, "stop_confirmation_delay_spin"):
            self.stop_confirmation_delay_spin.setSuffix(
                " " + self.i18n.t("settings.timeline.minutes")
            )
