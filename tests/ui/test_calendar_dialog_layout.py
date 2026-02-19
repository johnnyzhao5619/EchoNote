# SPDX-License-Identifier: Apache-2.0
"""
Tests for calendar dialog layout constants.
"""

from datetime import datetime
from unittest.mock import Mock

from PySide6.QtCore import QDate, QDateTime, QTime
from PySide6.QtWidgets import QTextEdit

from ui.calendar_hub.event_dialog import EventDialog
from ui.calendar_hub.oauth_dialog import OAuthDialog
from ui.constants import (
    CALENDAR_EVENT_DESCRIPTION_MAX_HEIGHT,
    CALENDAR_OAUTH_INSTRUCTIONS_MAX_HEIGHT,
)


def test_event_dialog_description_height_uses_constant(qapp, mock_i18n):
    dialog = EventDialog(i18n=mock_i18n, connected_accounts={})
    assert dialog.description_input.maximumHeight() == CALENDAR_EVENT_DESCRIPTION_MAX_HEIGHT


def test_oauth_dialog_instruction_height_uses_constant(qapp, mock_i18n):
    dialog = OAuthDialog(
        provider="google",
        authorization_url="https://example.com/oauth",
        i18n=mock_i18n,
        callback_host="127.0.0.1",
        callback_port=8765,
        state="state-token",
        code_verifier="code-verifier",
    )

    instruction_views = [view for view in dialog.findChildren(QTextEdit) if view.isReadOnly()]
    assert len(instruction_views) == 1
    assert instruction_views[0].maximumHeight() == CALENDAR_OAUTH_INSTRUCTIONS_MAX_HEIGHT


def test_event_dialog_collects_python_datetimes_without_qt_attribute_errors(qapp, mock_i18n):
    dialog = EventDialog(i18n=mock_i18n, connected_accounts={})
    dialog.title_input.setText("Test Event")

    start_qdt = QDateTime(QDate(2026, 2, 19), QTime(9, 30, 15, 123))
    end_qdt = QDateTime(QDate(2026, 2, 19), QTime(10, 0, 0, 0))
    dialog.start_time_input.setDateTime(start_qdt)
    dialog.end_time_input.setDateTime(end_qdt)

    data = dialog._collect_form_data()

    assert isinstance(data["start_time"], datetime)
    assert isinstance(data["end_time"], datetime)
    assert data["start_time"] < data["end_time"]


def test_event_dialog_validate_form_checks_time_order_without_crash(qapp, mock_i18n):
    dialog = EventDialog(i18n=mock_i18n, connected_accounts={})
    dialog.title_input.setText("Test Event")
    dialog.show_warning = Mock()

    start_qdt = QDateTime(QDate(2026, 2, 19), QTime(11, 0, 0))
    end_qdt = QDateTime(QDate(2026, 2, 19), QTime(10, 0, 0))
    dialog.start_time_input.setDateTime(start_qdt)
    dialog.end_time_input.setDateTime(end_qdt)

    assert dialog._validate_form() is False
    dialog.show_warning.assert_called_once()
