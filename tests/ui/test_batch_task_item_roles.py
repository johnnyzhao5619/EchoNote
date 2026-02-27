# SPDX-License-Identifier: Apache-2.0
"""
Tests for task item semantic style hooks.
"""

import pytest

from ui.batch_transcribe.task_item import TaskItem

pytestmark = pytest.mark.ui


def test_task_item_action_buttons_use_semantic_roles(qapp, mock_i18n):
    """Task action buttons should expose semantic roles for unified styling."""
    task = {"id": "task-1", "file_name": "demo.wav", "status": "pending"}
    widget = TaskItem(task_data=task, i18n=mock_i18n)

    assert widget.start_btn.property("role") == "task-action-start"
    assert widget.pause_btn.property("role") == "task-action-pause"
    assert widget.cancel_btn.property("role") == "task-action-cancel"
    assert widget.delete_btn.property("role") == "task-action-delete"
    assert widget.view_btn.property("role") == "task-action-view"
    assert widget.export_btn.property("role") == "task-action-export"
    assert widget.retry_btn.property("role") == "task-action-retry"


def test_task_item_partial_update_preserves_filename(qapp, mock_i18n):
    """Progress-only updates should not drop filename metadata."""
    task = {"id": "task-1", "file_name": "demo.wav", "status": "pending"}
    widget = TaskItem(task_data=task, i18n=mock_i18n)

    widget.update_task_data({"id": "task-1", "status": "processing", "progress": 21.0})

    assert widget.task_data.get("file_name") == "demo.wav"
    assert widget.filename_label.text() == "demo.wav"


def test_task_item_cancelled_state_keeps_delete_entry(qapp, mock_i18n):
    """Cancelled tasks should still expose delete action for cleanup."""
    task = {"id": "task-cancelled", "file_name": "demo.wav", "status": "cancelled"}
    widget = TaskItem(task_data=task, i18n=mock_i18n)

    assert not widget.delete_btn.isHidden()


def test_task_item_shows_quality_note_in_info_line(qapp, mock_i18n):
    """Quality note should be visible in task info for operator diagnostics."""
    task = {
        "id": "task-quality",
        "file_name": "demo.wav",
        "status": "completed",
        "quality_note": "Translation quality guard triggered",
    }
    widget = TaskItem(task_data=task, i18n=mock_i18n)

    assert "Translation quality guard triggered" in widget.info_label.text()
