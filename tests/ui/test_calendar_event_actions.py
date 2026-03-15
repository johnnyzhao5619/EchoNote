# SPDX-License-Identifier: Apache-2.0
"""Tests for shared calendar event actions."""

from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

import pytest

from ui.calendar_event_actions import (
    _build_delete_copy,
    _build_export_payload,
    confirm_and_delete_event,
)

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


def test_build_export_payload_uses_workspace_assets():
    workspace_manager = MagicMock()
    workspace_manager.get_event_artifacts.return_value = {
        "attachments": [
            {
                "id": "asset-1",
                "type": "transcript",
                "path": "/tmp/transcript.txt",
                "size": 42,
                "created_at": "2026-03-15T01:00:00+00:00",
                "text_content": "hello",
            }
        ]
    }
    calendar_manager = SimpleNamespace(workspace_manager=workspace_manager)
    event = SimpleNamespace(id="evt-3", title="Export", is_readonly=False)

    payload = _build_export_payload(event, calendar_manager)

    assert payload["attachments"] == [
        {
            "id": "asset-1",
            "asset_role": "transcript",
            "file_path": "/tmp/transcript.txt",
            "file_size": 42,
            "created_at": "2026-03-15T01:00:00+00:00",
            "text_content": "hello",
        }
    ]


def test_build_delete_copy_uses_workspace_summary_when_assets_exist():
    class StubI18n:
        def t(self, key, **kwargs):
            return f"{key}|{kwargs}"

    event = SimpleNamespace(id="evt-4", title="Delete", is_readonly=False)

    copy = _build_delete_copy(
        StubI18n(),
        event,
        {
            "has_workspace_assets": True,
            "linked_item_count": 2,
            "linked_asset_count": 5,
            "asset_roles": ["audio", "transcript", "translation"],
        },
    )

    assert copy["message"] == "calendar.delete.confirm_message|{'title': 'Delete'}"
    assert "calendar.delete.confirm_hint_with_workspace" in copy["hint"]
    assert "'item_count': 2" in copy["hint"]
    assert "'asset_count': 5" in copy["hint"]
