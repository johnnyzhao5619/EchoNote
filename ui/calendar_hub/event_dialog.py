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

from PySide6.QtCore import QDateTime, Signal
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
    QWidget,
)

from core.calendar.constants import EventType
from ui.base_widgets import (
    connect_button_with_callback,
    create_button,
    create_hbox,
    create_primary_button,
)
from ui.constants import CALENDAR_EVENT_DESCRIPTION_MAX_HEIGHT, CALENDAR_EVENT_DIALOG_MIN_WIDTH
from utils.i18n import I18nQtManager

logger = logging.getLogger("echonote.ui.event_dialog")


class EventDialog(QDialog):
    """
    Dialog for creating and editing calendar events.

    Provides form for event information and validation.
    """

    secondary_transcribe_requested = Signal()

    def __init__(
        self,
        i18n: I18nQtManager,
        connected_accounts: Dict[str, str],
        event_data: Optional[Dict[str, Any]] = None,
        parent: Optional[QWidget] = None,
        allow_retranscribe: bool = False,
        is_past: bool = False,
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
        self.allow_retranscribe = allow_retranscribe
        self.is_past = is_past

        # Result data
        self.result_data: Optional[Dict[str, Any]] = None
        self._delete_requested = False

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
        title = (
            self.i18n.t("calendar_hub.event_dialog.edit_event_title")
            if self.is_edit_mode
            else self.i18n.t("calendar_hub.create_event")
        )
        self.setWindowTitle(title)
        self.setMinimumWidth(CALENDAR_EVENT_DIALOG_MIN_WIDTH)

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
        form.addRow(self.i18n.t("calendar_hub.event_dialog.title_label"), self.title_input)

        # Event type
        self.type_combo = QComboBox()
        self.type_combo.addItems(
            [
                self.i18n.t("calendar_hub.event_types.event"),
                self.i18n.t("calendar_hub.event_types.task"),
                self.i18n.t("calendar_hub.event_types.appointment"),
            ]
        )
        form.addRow(self.i18n.t("calendar_hub.event_dialog.type_label"), self.type_combo)

        # Start time (required)
        self.start_time_input = QDateTimeEdit()
        self.start_time_input.setCalendarPopup(True)
        self.start_time_input.setDateTime(QDateTime.currentDateTime())
        self.start_time_input.setDisplayFormat("yyyy-MM-dd HH:mm")
        form.addRow(
            self.i18n.t("calendar_hub.event_dialog.start_time_label"), self.start_time_input
        )

        # End time (required)
        self.end_time_input = QDateTimeEdit()
        self.end_time_input.setCalendarPopup(True)
        # Default to 1 hour after start
        default_end = QDateTime.currentDateTime().addSecs(3600)
        self.end_time_input.setDateTime(default_end)
        self.end_time_input.setDisplayFormat("yyyy-MM-dd HH:mm")
        form.addRow(self.i18n.t("calendar_hub.event_dialog.end_time_label"), self.end_time_input)

        # Location (optional)
        self.location_input = QLineEdit()
        self.location_input.setPlaceholderText(
            self.i18n.t("calendar_hub.event_dialog.location_placeholder")
        )
        form.addRow(self.i18n.t("calendar_hub.event_dialog.location_label"), self.location_input)

        # Attendees (optional)
        self.attendees_input = QLineEdit()
        self.attendees_input.setPlaceholderText(
            self.i18n.t("calendar_hub.event_dialog.attendees_placeholder")
        )
        form.addRow(self.i18n.t("calendar_hub.event_dialog.attendees_label"), self.attendees_input)

        # Description (optional)
        self.description_input = QTextEdit()
        self.description_input.setPlaceholderText(
            self.i18n.t("calendar_hub.event_dialog.description_placeholder")
        )
        self.description_input.setMaximumHeight(CALENDAR_EVENT_DESCRIPTION_MAX_HEIGHT)
        form.addRow(
            self.i18n.t("calendar_hub.event_dialog.description_label"), self.description_input
        )

        # Reminder (optional)
        self.reminder_combo = QComboBox()
        self.reminder_combo.addItems(
            [
                self.i18n.t("calendar_hub.event_dialog.reminder_none"),
                self.i18n.t("calendar_hub.event_dialog.reminder_5min"),
                self.i18n.t("calendar_hub.event_dialog.reminder_10min"),
                self.i18n.t("calendar_hub.event_dialog.reminder_15min"),
                self.i18n.t("calendar_hub.event_dialog.reminder_30min"),
                self.i18n.t("calendar_hub.event_dialog.reminder_1hour"),
                self.i18n.t("calendar_hub.event_dialog.reminder_1day"),
            ]
        )
        form.addRow(self.i18n.t("calendar_hub.event_dialog.reminder_label"), self.reminder_combo)

        # Auto-transcribe (optional)
        self.auto_transcribe_checkbox = QCheckBox(
            self.i18n.t(
                "calendar_hub.event_dialog.auto_transcribe",
                default="Auto-transcribe when event ends",
            )
        )
        if self.is_past:
            self.auto_transcribe_checkbox.hide()
        form.addRow("", self.auto_transcribe_checkbox)

        return form

    def _create_sync_options(self) -> QGroupBox:
        """
        Create sync options group.

        Returns:
            Sync options group box
        """
        group = QGroupBox(self.i18n.t("calendar_hub.event_dialog.sync_options"))
        layout = QVBoxLayout(group)

        # Create checkbox for each connected account
        self.sync_checkboxes: Dict[str, QCheckBox] = {}

        for provider, email in self.connected_accounts.items():
            checkbox_text = self.i18n.t(
                "calendar_hub.event_dialog.sync_to_provider",
                provider=provider.capitalize(),
                email=email,
            )
            checkbox = QCheckBox(checkbox_text)
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

        if self.is_edit_mode:
            delete_btn = create_button(self.i18n.t("common.delete"))
            delete_btn.setProperty("variant", "danger")
            delete_btn.setProperty("role", "danger")
            connect_button_with_callback(delete_btn, self._on_delete_clicked)
            buttons_layout.addWidget(delete_btn)

            # Check if we should show secondary transcription button
            if self.allow_retranscribe:
                retranscribe_btn = create_button(
                    self.i18n.t(
                        "timeline.secondary_transcribe", default="Secondary Transcription (HQ)"
                    )
                )
                connect_button_with_callback(
                    retranscribe_btn, self._on_secondary_transcribe_clicked
                )
                buttons_layout.addWidget(retranscribe_btn)

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
        save_btn = create_primary_button(save_text)
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
            type_map = {EventType.EVENT: 0, EventType.TASK: 1, EventType.APPOINTMENT: 2}
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

        # Auto-transcribe
        if "auto_transcribe" in self.event_data:
            self.auto_transcribe_checkbox.setChecked(bool(self.event_data["auto_transcribe"]))

    def _on_save_clicked(self):
        """Handle save button click."""
        # Validate form
        if not self._validate_form():
            return

        # Collect form data
        self._delete_requested = False
        self.result_data = self._collect_form_data()

        # Accept dialog
        self.accept()

        logger.debug("Event data saved")

    def _on_delete_clicked(self):
        """Mark dialog result as delete request and close."""
        if not self.is_edit_mode or not self.event_data:
            return

        event_id = self.event_data.get("id")
        if not event_id:
            return

        self._delete_requested = True
        self.result_data = {"id": event_id}
        self.accept()

    def _on_secondary_transcribe_clicked(self):
        """Handle secondary transcription button click."""
        self.secondary_transcribe_requested.emit()
        self.accept()

    def is_delete_requested(self) -> bool:
        """Return whether user requested deleting the current event."""
        return bool(self._delete_requested)

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
        start_time = self._qdatetime_to_python_datetime(self.start_time_input.dateTime())
        end_time = self._qdatetime_to_python_datetime(self.end_time_input.dateTime())

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
        type_map = [EventType.EVENT, EventType.TASK, EventType.APPOINTMENT]
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
            "start_time": self._qdatetime_to_python_datetime(self.start_time_input.dateTime()),
            "end_time": self._qdatetime_to_python_datetime(self.end_time_input.dateTime()),
            "location": self.location_input.text().strip() or None,
            "attendees": attendees if attendees else None,
            "description": self.description_input.toPlainText().strip() or None,
            "reminder_minutes": reminder_minutes,
            "sync_to": sync_to if sync_to else None,
            "auto_transcribe": getattr(self, "auto_transcribe_checkbox", QCheckBox()).isChecked(),
        }

        # Add event ID if editing
        if self.is_edit_mode and "id" in self.event_data:
            data["id"] = self.event_data["id"]

        return data

    @staticmethod
    def _qdatetime_to_python_datetime(value: QDateTime) -> datetime:
        """Convert QDateTime to Python datetime across Qt binding variants."""
        if not value.isValid():
            raise ValueError("Invalid datetime input")

        to_python = getattr(value, "toPython", None)
        if callable(to_python):
            result = to_python()
            if isinstance(result, datetime):
                return result

        to_py_datetime = getattr(value, "toPyDateTime", None)
        if callable(to_py_datetime):
            result = to_py_datetime()
            if isinstance(result, datetime):
                return result

        date_part = value.date()
        time_part = value.time()
        return datetime(
            date_part.year(),
            date_part.month(),
            date_part.day(),
            time_part.hour(),
            time_part.minute(),
            time_part.second(),
            time_part.msec() * 1000,
        )

    def get_event_data(self) -> Optional[Dict[str, Any]]:
        """
        Get the collected event data.

        Returns:
            Event data dictionary or None if cancelled
        """
        return self.result_data

    def show_warning(self, title: str, message: str):
        """
        Show warning message dialog.

        Args:
            title: Dialog title
            message: Warning message
        """
        from PySide6.QtWidgets import QMessageBox

        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Icon.Warning)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg_box.exec()
