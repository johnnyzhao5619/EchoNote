# SPDX-License-Identifier: Apache-2.0
"""UI tests for timeline transcript viewer semantic style hooks."""

import pytest
from ui.timeline.transcript_viewer import TranscriptViewer, TranscriptViewerDialog

pytestmark = pytest.mark.ui


def test_transcript_viewer_action_buttons_use_semantic_roles(qapp, mock_i18n, tmp_path):
    transcript_path = tmp_path / "sample_transcript.txt"
    transcript_path.write_text("Hello world", encoding="utf-8")

    viewer = TranscriptViewer(str(transcript_path), mock_i18n)

    assert viewer.copy_button.property("role") == "timeline-copy-action"
    assert viewer.export_button.property("role") == "timeline-export-action"


def test_transcript_viewer_search_buttons_use_dialog_roles(qapp, mock_i18n, tmp_path):
    transcript_path = tmp_path / "sample_transcript.txt"
    transcript_path.write_text("Hello world", encoding="utf-8")

    viewer = TranscriptViewer(str(transcript_path), mock_i18n)

    assert viewer.search_button.property("role") == "dialog-secondary-action"
    assert viewer.clear_search_button.property("role") == "dialog-secondary-action"
    assert viewer.prev_button.property("role") == "dialog-nav-action"
    assert viewer.next_button.property("role") == "dialog-nav-action"


def test_transcript_viewer_dialog_close_button_uses_primary_dialog_role(qapp, mock_i18n, tmp_path):
    transcript_path = tmp_path / "sample_transcript.txt"
    transcript_path.write_text("Hello world", encoding="utf-8")

    dialog = TranscriptViewerDialog(str(transcript_path), mock_i18n)
    assert dialog.close_button.property("role") == "dialog-primary-action"
