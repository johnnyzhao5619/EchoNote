# SPDX-License-Identifier: Apache-2.0
"""UI tests for timeline event card semantic style hooks."""

from datetime import datetime
from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QLabel

from ui.timeline.event_card import EventCard

pytestmark = pytest.mark.ui


def test_event_card_title_uses_semantic_role(qapp, mock_i18n):
    """Event title should expose semantic role hook instead of legacy objectName."""
    event = SimpleNamespace(
        id="evt-1",
        title="Design Review",
        start_time=datetime(2026, 1, 1, 10, 0, 0),
        end_time=datetime(2026, 1, 1, 11, 0, 0),
        source="local",
        event_type="event",
        location="",
        attendees=[],
        description="",
    )
    card = EventCard({"event": event, "artifacts": {}}, is_future=False, i18n=mock_i18n)

    title_labels = [
        label for label in card.findChildren(QLabel) if label.property("role") == "event-title"
    ]
    assert len(title_labels) == 1
    assert title_labels[0].text() == "Design Review"
    assert all(label.objectName() != "title_label" for label in card.findChildren(QLabel))


def test_event_card_action_buttons_use_semantic_roles(qapp, mock_i18n):
    """Past-event action buttons should expose semantic role hooks for styling."""
    event = SimpleNamespace(
        id="evt-2",
        title="Sync Meeting",
        start_time=datetime(2026, 1, 1, 10, 0, 0),
        end_time=datetime(2026, 1, 1, 11, 0, 0),
        source="local",
        event_type="event",
        location="",
        attendees=[],
        description="",
    )
    card = EventCard(
        {
            "event": event,
            "artifacts": {
                "recording": "/tmp/meeting.wav",
                "transcript": "/tmp/meeting.txt",
                "translation": "/tmp/meeting_zh.txt",
            },
        },
        is_future=False,
        i18n=mock_i18n,
    )

    assert card.recording_btn.property("role") == "timeline-recording-action"
    assert card.secondary_transcribe_btn.property("role") == "timeline-secondary-transcribe-action"
    assert card.translate_btn.property("role") == "timeline-translation-action"
    assert card.view_text_btn.property("role") == "timeline-transcript-action"


def test_event_card_meta_labels_use_semantic_role(qapp, mock_i18n):
    """Event time/detail lines should expose semantic role for consistent typography."""
    event = SimpleNamespace(
        id="evt-3",
        title="Planning",
        start_time=datetime(2026, 1, 1, 9, 0, 0),
        end_time=datetime(2026, 1, 1, 9, 30, 0),
        source="local",
        event_type="event",
        location="Room A",
        attendees=["A", "B"],
        description="Notes",
    )
    card = EventCard({"event": event, "artifacts": {}}, is_future=False, i18n=mock_i18n)

    meta_labels = [
        label for label in card.findChildren(QLabel) if label.property("role") == "event-meta"
    ]
    assert len(meta_labels) >= 2


def test_event_card_delete_button_emits_event_id(qapp, mock_i18n):
    event = SimpleNamespace(
        id="evt-delete",
        title="Delete Me",
        start_time=datetime(2026, 1, 2, 9, 0, 0),
        end_time=datetime(2026, 1, 2, 10, 0, 0),
        source="local",
        event_type="event",
        location="",
        attendees=[],
        description="",
    )
    card = EventCard({"event": event, "artifacts": {}}, is_future=False, i18n=mock_i18n)

    captured = []
    card.delete_requested.connect(captured.append)
    card.delete_btn.click()

    assert card.delete_btn.property("variant") == "danger"
    assert captured == ["evt-delete"]


def test_event_card_view_text_prefers_transcript_when_both_exist(qapp, mock_i18n):
    event = SimpleNamespace(
        id="evt-view-both",
        title="View Both",
        start_time=datetime(2026, 1, 2, 9, 0, 0),
        end_time=datetime(2026, 1, 2, 10, 0, 0),
        source="local",
        event_type="event",
        location="",
        attendees=[],
        description="",
    )
    card = EventCard(
        {
            "event": event,
            "artifacts": {
                "transcript": "/tmp/meeting.txt",
                "translation": "/tmp/meeting_zh.txt",
            },
        },
        is_future=False,
        i18n=mock_i18n,
    )

    transcript_captured = []
    translation_captured = []
    card.view_transcript.connect(transcript_captured.append)
    card.view_translation.connect(translation_captured.append)
    card.view_text_btn.click()

    assert transcript_captured == ["/tmp/meeting.txt"]
    assert translation_captured == []


def test_event_card_view_text_uses_translation_when_transcript_missing(qapp, mock_i18n):
    event = SimpleNamespace(
        id="evt-view-translation",
        title="View Translation",
        start_time=datetime(2026, 1, 3, 9, 0, 0),
        end_time=datetime(2026, 1, 3, 10, 0, 0),
        source="local",
        event_type="event",
        location="",
        attendees=[],
        description="",
    )
    card = EventCard(
        {
            "event": event,
            "artifacts": {
                "translation": "/tmp/meeting_zh.txt",
            },
        },
        is_future=False,
        i18n=mock_i18n,
    )

    transcript_captured = []
    translation_captured = []
    card.view_transcript.connect(transcript_captured.append)
    card.view_translation.connect(translation_captured.append)
    card.view_text_btn.click()

    assert transcript_captured == []
    assert translation_captured == ["/tmp/meeting_zh.txt"]
