# SPDX-License-Identifier: Apache-2.0
"""Tests for timeline delete-event wiring and workspace routing."""

from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import QWidget

from ui.timeline.widget import TimelineWidget

pytestmark = pytest.mark.ui


class _MainWindowStub(QWidget):
    def __init__(self):
        super().__init__()
        self.current_page_name = None
        self.open_calls = []

    def open_workspace_item(
        self,
        *,
        item_id: str,
        asset_role: str | None = None,
        view_mode: str | None = None,
    ) -> bool:
        self.current_page_name = "workspace"
        self.open_calls.append((item_id, asset_role, view_mode))
        return True


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


def test_timeline_event_view_workspace_route_for_transcript(
    qapp, mock_i18n, mock_settings_manager
):
    timeline_manager = MagicMock()
    timeline_manager.calendar_manager = MagicMock()
    timeline_manager.workspace_manager = MagicMock()
    timeline_manager.workspace_manager.get_event_item_id.return_value = "workspace-item-1"
    main_window = _MainWindowStub()

    with (
        patch("ui.timeline.widget.QTimer.singleShot", side_effect=lambda _ms, _cb: None),
        patch("ui.timeline.widget.open_or_activate_text_viewer") as mock_viewer,
    ):
        widget = TimelineWidget(
            timeline_manager=timeline_manager,
            transcription_manager=MagicMock(),
            i18n=mock_i18n,
            parent=main_window,
            settings_manager=mock_settings_manager,
        )

    widget._on_view_transcript(event_id="event-1")

    assert main_window.current_page_name == "workspace"
    assert main_window.open_calls == [("workspace-item-1", "transcript", "event")]
    mock_viewer.assert_not_called()
