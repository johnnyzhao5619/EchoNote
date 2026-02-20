# SPDX-License-Identifier: Apache-2.0
"""Tests for timeline delete-event wiring."""

from unittest.mock import MagicMock, patch

import pytest

from ui.timeline.widget import TimelineWidget

pytestmark = pytest.mark.ui


def test_timeline_widget_delete_event_uses_shared_flow(qapp, mock_i18n, mock_settings_manager):
    timeline_manager = MagicMock()
    timeline_manager.calendar_manager = MagicMock()

    with patch("ui.timeline.widget.QTimer.singleShot", side_effect=lambda _ms, _cb: None):
        widget = TimelineWidget(
            timeline_manager=timeline_manager,
            transcription_manager=MagicMock(),
            i18n=mock_i18n,
            settings_manager=mock_settings_manager,
        )

    event = MagicMock()
    event.id = "event-1"
    timeline_manager.calendar_manager.get_event.return_value = event

    with patch(
        "ui.calendar_event_actions.confirm_and_delete_event", return_value=True
    ) as mock_flow:
        widget._on_delete_event_requested("event-1")

    assert mock_flow.call_count == 1
