# SPDX-License-Identifier: Apache-2.0
"""Tests for shared calendar event actions."""

from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

import pytest

from ui.calendar_event_actions import confirm_and_delete_event

pytestmark = pytest.mark.ui


def test_confirm_and_delete_event_blocks_readonly_event(mock_i18n):
    parent = MagicMock()
    calendar_manager = MagicMock()
    event = SimpleNamespace(id="evt-readonly", title="Readonly", is_readonly=True)

    result = confirm_and_delete_event(
        parent=parent,
        i18n=mock_i18n,
        calendar_manager=calendar_manager,
        event=event,
    )

    assert result is False
    calendar_manager.delete_event.assert_not_called()
    assert parent.show_warning.call_count == 1


def test_confirm_and_delete_event_executes_delete_flow(mock_i18n):
    parent = MagicMock()
    calendar_manager = MagicMock()
    callback = Mock()
    event = SimpleNamespace(id="evt-1", title="Delete", is_readonly=False)

    with (
        patch(
            "ui.calendar_event_actions._choose_delete_action",
            return_value="delete_with_artifacts",
        ),
        patch("ui.calendar_event_actions._confirm_delete_second_step", return_value=True),
    ):
        result = confirm_and_delete_event(
            parent=parent,
            i18n=mock_i18n,
            calendar_manager=calendar_manager,
            event=event,
            on_deleted=callback,
        )

    assert result is True
    calendar_manager.delete_event.assert_called_once_with("evt-1", delete_artifacts=True)
    callback.assert_called_once()


def test_confirm_and_delete_event_can_keep_artifacts(mock_i18n):
    parent = MagicMock()
    calendar_manager = MagicMock()
    event = SimpleNamespace(id="evt-2", title="Keep Files", is_readonly=False)

    with (
        patch(
            "ui.calendar_event_actions._choose_delete_action",
            return_value="delete_event_only",
        ),
        patch("ui.calendar_event_actions._confirm_delete_second_step", return_value=True),
    ):
        result = confirm_and_delete_event(
            parent=parent,
            i18n=mock_i18n,
            calendar_manager=calendar_manager,
            event=event,
        )

    assert result is True
    calendar_manager.delete_event.assert_called_once_with("evt-2", delete_artifacts=False)
