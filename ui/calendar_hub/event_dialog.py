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
Event Dialog for EchoNote Calendar.

Provides dialog for creating and editing calendar events.
"""

import logging
from datetime import datetime
from typing import Any, Dict, Optional

from PySide6.QtCore import QDateTime
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateTimeEdit,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QTextEdit,
    QVBoxLayout,
)

from ui.base_widgets import (
    create_button,
    create_primary_button,
    create_hbox,
    connect_button_with_callback,
)

from utils.i18n import I18nQtManager

logger = logging.getLogger("echonote.ui.event_dialog")


class EventDialog(QDialog):
    """
    Dialog for creating and editing calendar events.

    Provides form for event information and validation.
    """

    def __init__(
        self,
        i18n: I18nQtManager,
        connected_accounts: Dict[str, str],
        event_data: Optional[Dict[str, Any]] = None,
        parent: Optional[QDialog] = None,
    ):
        """
        Initialize event dialog.

        Args:
            i18n: Internationalization manager
            connected_accounts: Dictionary of connected accounts
                               {provider: email}
            event_data: Optional existing event data for editing
            parent: Parent widget
        """
        super().__init__(parent)

        self.i18n = i18n
        self.connected_accounts = connected_accounts
        self.event_data = event_data
        self.is_edit_mode = event_data is not None

        # Result data
        self.result_data: Optional[Dict[str, Any]] = None

        self.setup_ui()

        # Populate form if editing
        if self.is_edit_mode:
            self._populate_form()

        logger.debug(
            f"EventDialog initialized in " f"{'edit' if self.is_edit_mode else 'create'} mode"
        )

    def setup_ui(self):
        """Set up the dialog UI."""
        # Set dialog properties
        title = "Edit Event" if self.is_edit_mode else self.i18n.t("calendar_hub.create_event")
        self.setWindowTitle(title)
        self.setMinimumWidth(500)

        # Main layout
        layout = QVBoxLayout(self)

        # Create form
        form = self._create_form()
        layout.addLayout(form)

        # Create sync options (if accounts connected)
        if self.connected_accounts and not self.is_edit_mode:
            sync_group = self._create_sync_options()
            layout.addWidget(sync_group)

        # Create buttons
        buttons = self._create_buttons()
        layout.addLayout(buttons)

    def _create_form(self) -> QFormLayout:
        """
        Create event information form.

        Returns:
            Form layout
        """
        form = QFormLayout()

        # Title (required)
        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText(
            self.i18n.t("calendar_hub.event_dialog.title_placeholder")
        )
        form.addRow("Title *:", self.title_input)

        # Event type
        self.type_combo = QComboBox()
        self.type_combo.addItems(
            [
                self.i18n.t("calendar_hub.event_types.event"),
                self.i18n.t("calendar_hub.event_types.task"),
                self.i18n.t("calendar_hub.event_types.appointment"),
            ]
        )
        form.addRow("Type *:", self.type_combo)

        # Start time (required)
        self.start_time_input = QDateTimeEdit()
        self.start_time_input.setCalendarPopup(True)
        self.start_time_input.setDateTime(QDateTime.currentDateTime())
        self.start_time_input.setDisplayFormat("yyyy-MM-dd HH:mm")
        form.addRow("Start Time *:", self.start_time_input)

        # End time (required)
        self.end_time_input = QDateTimeEdit()
        self.end_time_input.setCalendarPopup(True)
        # Default to 1 hour after start
        default_end = QDateTime.currentDateTime().addSecs(3600)
        self.end_time_input.setDateTime(default_end)
        self.end_time_input.setDisplayFormat("yyyy-MM-dd HH:mm")
        form.addRow("End Time *:", self.end_time_input)

        # Location (optional)
        self.location_input = QLineEdit()
        self.location_input.setPlaceholderText(
            self.i18n.t("calendar_hub.event_dialog.location_placeholder")
        )
        form.addRow("Location:", self.location_input)

        # Attendees (optional)
        self.attendees_input = QLineEdit()
        self.attendees_input.setPlaceholderText(
            self.i18n.t("calendar_hub.event_dialog.attendees_placeholder")
        )
        form.addRow("Attendees:", self.attendees_input)

        # Description (optional)
        self.description_input = QTextEdit()
        self.description_input.setPlaceholderText(
            self.i18n.t("calendar_hub.event_dialog.description_placeholder")
        )
        self.description_input.setMaximumHeight(100)
        form.addRow("Description:", self.description_input)

        # Reminder (optional)
        self.reminder_combo = QComboBox()
        self.reminder_combo.addItems(
            [
                "No reminder",
                "5 minutes before",
                "10 minutes before",
                "15 minutes before",
                "30 minutes before",
                "1 hour before",
                "1 day before",
            ]
        )
        form.addRow("Reminder:", self.reminder_combo)

        return form

    def _create_sync_options(self) -> QGroupBox:
        """
        Create sync options group.

        Returns:
            Sync options group box
        """
        group = QGroupBox(self.i18n.t("calendar_hub.sync_external_calendars"))
        layout = QVBoxLayout(group)

        # Create checkbox for each connected account
        self.sync_checkboxes: Dict[str, QCheckBox] = {}

        for provider, email in self.connected_accounts.items():
            checkbox = QCheckBox(f"Sync to {provider.capitalize()} ({email})")
            layout.addWidget(checkbox)
            self.sync_checkboxes[provider] = checkbox

        return group

    def _create_buttons(self) -> QHBoxLayout:
        """
        Create dialog buttons.

        Returns:
            Buttons layout
        """
        buttons_layout = create_hbox()
        buttons_layout.addStretch()

        # Cancel button
        cancel_btn = create_button(self.i18n.t("common.cancel"))
        connect_button_with_callback(cancel_btn, self.reject)
        buttons_layout.addWidget(cancel_btn)

        # Save button
        save_text = (
            self.i18n.t("common.save")
            if self.is_edit_mode
            else self.i18n.t("calendar_hub.create_event")
        )
        save_btn = create_button(save_text)
        save_btn = create_primary_button(save_btn.text())
        connect_button_with_callback(save_btn, self._on_save_clicked)
        buttons_layout.addWidget(save_btn)

        return buttons_layout

    def _populate_form(self):
        """Populate form with existing event data."""
        if not self.event_data:
            return

        # Title
        if "title" in self.event_data:
            self.title_input.setText(self.event_data["title"])

        # Type
        if "event_type" in self.event_data:
            type_map = {"Event": 0, "Task": 1, "Appointment": 2}
            index = type_map.get(self.event_data["event_type"], 0)
            self.type_combo.setCurrentIndex(index)

        # Start time
        if "start_time" in self.event_data:
            start_time = self.event_data["start_time"]
            if isinstance(start_time, str):
                start_time = datetime.fromisoformat(start_time)
            qdt = QDateTime(start_time)
            self.start_time_input.setDateTime(qdt)

        # End time
        if "end_time" in self.event_data:
            end_time = self.event_data["end_time"]
            if isinstance(end_time, str):
                end_time = datetime.fromisoformat(end_time)
            qdt = QDateTime(end_time)
            self.end_time_input.setDateTime(qdt)

        # Location
        if "location" in self.event_data:
            self.location_input.setText(self.event_data["location"] or "")

        # Attendees
        if "attendees" in self.event_data:
            attendees = self.event_data["attendees"]
            if attendees:
                self.attendees_input.setText(", ".join(attendees))

        # Description
        if "description" in self.event_data:
            self.description_input.setPlainText(self.event_data["description"] or "")

        # Reminder
        if "reminder_minutes" in self.event_data:
            minutes = self.event_data["reminder_minutes"]
            reminder_map = {None: 0, 5: 1, 10: 2, 15: 3, 30: 4, 60: 5, 1440: 6}
            index = reminder_map.get(minutes, 0)
            self.reminder_combo.setCurrentIndex(index)

    def _on_save_clicked(self):
        """Handle save button click."""
        # Validate form
        if not self._validate_form():
            return

        # Collect form data
        self.result_data = self._collect_form_data()

        # Accept dialog
        self.accept()

        logger.debug("Event data saved")

    def _validate_form(self) -> bool:
        """
        Validate form inputs.

        Returns:
            True if valid, False otherwise
        """
        # Check required fields
        if not self.title_input.text().strip():
            self.show_warning(
                self.i18n.t("calendar_hub.event_dialog.validation_error"),
                self.i18n.t("calendar_hub.event_dialog.title_required"),
            )
            self.title_input.setFocus()
            return False

        # Check start time < end time
        start_time = self.start_time_input.dateTime().toPyDateTime()
        end_time = self.end_time_input.dateTime().toPyDateTime()

        if start_time >= end_time:
            self.show_warning(
                self.i18n.t("calendar_hub.event_dialog.validation_error"),
                self.i18n.t("calendar_hub.event_dialog.end_after_start"),
            )
            self.end_time_input.setFocus()
            return False

        # Validate attendees email format (basic check)
        attendees_text = self.attendees_input.text().strip()
        if attendees_text:
            emails = [e.strip() for e in attendees_text.split(",")]
            for email in emails:
                if email and "@" not in email:
                    self.show_warning(
                        self.i18n.t("calendar_hub.event_dialog.validation_error"),
                        self.i18n.t("calendar_hub.event_dialog.invalid_email").format(email=email),
                    )
                    self.attendees_input.setFocus()
                    return False

        return True

    def _collect_form_data(self) -> Dict[str, Any]:
        """
        Collect form data into dictionary.

        Returns:
            Event data dictionary
        """
        # Get event type
        type_map = ["Event", "Task", "Appointment"]
        event_type = type_map[self.type_combo.currentIndex()]

        # Get reminder minutes
        reminder_map = [None, 5, 10, 15, 30, 60, 1440]
        reminder_minutes = reminder_map[self.reminder_combo.currentIndex()]

        # Get attendees
        attendees_text = self.attendees_input.text().strip()
        attendees = []
        if attendees_text:
            attendees = [e.strip() for e in attendees_text.split(",")]

        # Get sync options
        sync_to = []
        if hasattr(self, "sync_checkboxes"):
            for provider, checkbox in self.sync_checkboxes.items():
                if checkbox.isChecked():
                    sync_to.append(provider)

        data = {
            "title": self.title_input.text().strip(),
            "event_type": event_type,
            "start_time": self.start_time_input.dateTime().toPyDateTime(),
            "end_time": self.end_time_input.dateTime().toPyDateTime(),
            "location": self.location_input.text().strip() or None,
            "attendees": attendees if attendees else None,
            "description": self.description_input.toPlainText().strip() or None,
            "reminder_minutes": reminder_minutes,
            "sync_to": sync_to if sync_to else None,
        }

        # Add event ID if editing
        if self.is_edit_mode and "id" in self.event_data:
            data["id"] = self.event_data["id"]

        return data

    def get_event_data(self) -> Optional[Dict[str, Any]]:
        """
        Get the collected event data.

        Returns:
            Event data dictionary or None if cancelled
        """
        return self.result_data
