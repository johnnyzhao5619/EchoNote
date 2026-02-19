# SPDX-License-Identifier: Apache-2.0
"""UI tests for calendar hub semantic style hooks."""

import pytest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QDialog

from ui.calendar_hub.widget import CalendarHubWidget

pytestmark = pytest.mark.ui


def test_calendar_view_buttons_use_semantic_role(qapp, mock_i18n):
    calendar_manager = MagicMock()
    calendar_manager.get_events.return_value = []
    oauth_manager = MagicMock()

    with patch.object(CalendarHubWidget, "_load_connected_accounts", return_value=None):
        widget = CalendarHubWidget(calendar_manager, oauth_manager, mock_i18n)

    assert widget.month_btn.property("role") == "calendar-view-toggle"
    assert widget.week_btn.property("role") == "calendar-view-toggle"
    assert widget.day_btn.property("role") == "calendar-view-toggle"
    assert widget.prev_btn.property("role") == "calendar-nav-action"
    assert widget.today_btn.property("role") == "calendar-nav-action"
    assert widget.next_btn.property("role") == "calendar-nav-action"
    assert widget.sync_now_btn.property("role") == "calendar-utility-action"
    assert widget.add_account_btn.property("role") == "calendar-utility-action"
    assert widget.create_event_btn.property("role") == "calendar-primary-action"
    assert widget.create_event_btn.property("variant") == "primary"


def test_calendar_hub_edit_dialog_delete_routes_to_delete_handler(qapp, mock_i18n):
    calendar_manager = MagicMock()
    calendar_manager.get_events.return_value = []
    oauth_manager = MagicMock()

    event = SimpleNamespace(
        id="event-123",
        title="Test Event",
        event_type="event",
        start_time="2026-02-19T10:00:00",
        end_time="2026-02-19T11:00:00",
        location=None,
        attendees=[],
        description=None,
        reminder_minutes=None,
    )

    with patch.object(CalendarHubWidget, "_load_connected_accounts", return_value=None):
        widget = CalendarHubWidget(calendar_manager, oauth_manager, mock_i18n)

    class _DeleteDialog:
        def __init__(self, *_args, **_kwargs):
            pass

        def exec(self):
            return QDialog.DialogCode.Accepted

        def get_event_data(self):
            return {"id": "event-123"}

        def is_delete_requested(self):
            return True

    with (
        patch("ui.calendar_hub.event_dialog.EventDialog", _DeleteDialog),
        patch.object(widget, "_delete_event") as mock_delete_event,
    ):
        widget._show_event_dialog(event)

    mock_delete_event.assert_called_once_with("event-123")
