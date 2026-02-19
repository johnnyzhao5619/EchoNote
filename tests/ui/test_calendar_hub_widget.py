# SPDX-License-Identifier: Apache-2.0
"""UI tests for calendar hub semantic style hooks."""

from unittest.mock import MagicMock, patch

from ui.calendar_hub.widget import CalendarHubWidget


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
