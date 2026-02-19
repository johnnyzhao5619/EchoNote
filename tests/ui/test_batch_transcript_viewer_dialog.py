# SPDX-License-Identifier: Apache-2.0
"""
Tests for batch transcript viewer semantic style hooks.
"""

from unittest.mock import Mock

from ui.batch_transcribe.transcript_viewer import TranscriptViewerDialog


def test_transcript_viewer_toolbar_uses_semantic_roles(qapp, mock_i18n, monkeypatch, tmp_path):
    """Toolbar buttons and edit state should expose semantic hooks for styling."""
    task_data = {
        "id": "task-1",
        "file_name": "demo.wav",
        "file_path": str(tmp_path / "demo.wav"),
        "audio_duration": 65,
        "language": "en",
        "engine": "whisper",
        "output_path": str(tmp_path / "demo.txt"),
        "completed_at": "2026-01-01T10:00:00",
        "status": "completed",
    }
    monkeypatch.setattr(TranscriptViewerDialog, "_load_task_data", lambda self: task_data.copy())
    monkeypatch.setattr(TranscriptViewerDialog, "_load_content", lambda self: None)

    dialog = TranscriptViewerDialog(
        task_id="task-1",
        transcription_manager=Mock(),
        db_connection=Mock(),
        i18n=mock_i18n,
    )

    assert dialog.edit_button.property("role") == "batch-viewer-edit-action"
    assert dialog.export_button.property("role") == "batch-viewer-export-action"
    assert dialog.copy_button.property("role") == "batch-viewer-copy-action"
    assert dialog.search_button.property("role") == "batch-viewer-search-action"
    assert dialog.edit_button.parent().property("role") == "batch-viewer-toolbar"

    dialog.toggle_edit_mode()
    assert dialog.edit_button.property("state") == "active"

    dialog.toggle_edit_mode()
    assert dialog.edit_button.property("state") == "default"

