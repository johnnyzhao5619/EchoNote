# SPDX-License-Identifier: Apache-2.0
"""UI tests for calendar hub semantic style hooks."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
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


def test_calendar_hub_edit_dialog_prefills_translation_auto_task(qapp, mock_i18n):
    calendar_manager = MagicMock()
    calendar_manager.get_events.return_value = []
    calendar_manager.db = MagicMock()
    oauth_manager = MagicMock()
    transcription_manager = MagicMock()
    transcription_manager.translation_engine = object()

    event = SimpleNamespace(
        id="event-translation",
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
        widget = CalendarHubWidget(
            calendar_manager,
            oauth_manager,
            mock_i18n,
            transcription_manager=transcription_manager,
        )

    captured = {}

    class _CaptureDialog:
        def __init__(self, *args, **_kwargs):
            captured["event_data"] = args[2] if len(args) > 2 else None

        def exec(self):
            return QDialog.DialogCode.Rejected

    mock_config = SimpleNamespace(
        enable_transcription=True,
        enable_translation=True,
        translation_target_language="fr",
    )

    with (
        patch("data.database.models.AutoTaskConfig.get_by_event_id", return_value=mock_config),
        patch("data.database.models.EventAttachment.get_by_event_id", return_value=[]),
        patch("ui.calendar_hub.event_dialog.EventDialog", _CaptureDialog),
    ):
        widget._show_event_dialog(event)

    assert captured["event_data"]["auto_transcribe"] is True
    assert captured["event_data"]["enable_translation"] is True
    assert captured["event_data"]["translation_target_lang"] == "fr"


def test_calendar_hub_view_recording_prefers_requester_as_dialog_parent(qapp, mock_i18n):
    calendar_manager = MagicMock()
    calendar_manager.get_events.return_value = []
    oauth_manager = MagicMock()

    with patch.object(CalendarHubWidget, "_load_connected_accounts", return_value=None):
        widget = CalendarHubWidget(calendar_manager, oauth_manager, mock_i18n)

    requester = QDialog()
    with patch("ui.calendar_hub.widget.open_or_activate_audio_player") as mock_open_audio:
        widget._on_view_recording(
            file_path="/tmp/demo_recording.wav",
            transcript_path="/tmp/demo_transcript.txt",
            translation_path="/tmp/demo_translation.txt",
            parent_hint=requester,
        )

    mock_open_audio.assert_called_once()
    kwargs = mock_open_audio.call_args.kwargs
    assert kwargs["parent"] is requester
    assert kwargs["cache_key"].startswith("/tmp/demo_recording.wav::")


def test_calendar_hub_translate_transcript_prompts_language_before_queue(qapp, mock_i18n):
    calendar_manager = MagicMock()
    calendar_manager.get_events.return_value = []
    oauth_manager = MagicMock()

    with patch.object(CalendarHubWidget, "_load_connected_accounts", return_value=None):
        widget = CalendarHubWidget(
            calendar_manager,
            oauth_manager,
            mock_i18n,
            transcription_manager=MagicMock(),
        )

    selected_languages = {
        "translation_source_lang": "en",
        "translation_target_lang": "fr",
    }
    with (
        patch(
            "ui.calendar_hub.widget.prompt_event_translation_languages",
            return_value=selected_languages,
        ) as mock_prompt,
        patch("ui.calendar_hub.widget.enqueue_event_translation_task", return_value=True) as mock_enqueue,
    ):
        widget._on_translate_transcript_requested(
            event_id="event-1",
            transcript_path="/tmp/transcript.txt",
        )

    mock_prompt.assert_called_once()
    enqueue_kwargs = mock_enqueue.call_args.kwargs
    assert enqueue_kwargs["translation_source_lang"] == "en"
    assert enqueue_kwargs["translation_target_lang"] == "fr"


def test_calendar_hub_translate_transcript_prompt_cancelled_skips_queue(qapp, mock_i18n):
    calendar_manager = MagicMock()
    calendar_manager.get_events.return_value = []
    oauth_manager = MagicMock()

    with patch.object(CalendarHubWidget, "_load_connected_accounts", return_value=None):
        widget = CalendarHubWidget(
            calendar_manager,
            oauth_manager,
            mock_i18n,
            transcription_manager=MagicMock(),
        )

    with (
        patch(
            "ui.calendar_hub.widget.prompt_event_translation_languages",
            return_value=None,
        ),
        patch("ui.calendar_hub.widget.enqueue_event_translation_task") as mock_enqueue,
    ):
        widget._on_translate_transcript_requested(
            event_id="event-1",
            transcript_path="/tmp/transcript.txt",
        )

    mock_enqueue.assert_not_called()


def test_calendar_hub_secondary_transcribe_uses_config_language_and_dialog_preferences(
    qapp, mock_i18n
):
    calendar_manager = MagicMock()
    calendar_manager.get_events.return_value = []
    calendar_manager.db = MagicMock()
    oauth_manager = MagicMock()
    transcription_manager = MagicMock()
    transcription_manager.add_task = MagicMock(return_value="task-1")

    with patch.object(CalendarHubWidget, "_load_connected_accounts", return_value=None):
        widget = CalendarHubWidget(
            calendar_manager,
            oauth_manager,
            mock_i18n,
            transcription_manager=transcription_manager,
        )

    config = SimpleNamespace(
        transcription_language="ja",
        enable_translation=True,
        translation_target_language="de",
    )
    with (
        patch(
            "ui.common.secondary_transcribe_dialog.select_secondary_transcribe_model",
            return_value={"model_name": "large-v3", "model_path": "/tmp/large-v3"},
        ),
        patch("data.database.models.AutoTaskConfig.get_by_event_id", return_value=config),
    ):
        widget._on_secondary_transcribe_requested(
            event_id="event-1",
            recording_path="/tmp/demo.wav",
            dialog_data={
                "enable_translation": False,
                "translation_target_lang": "fr",
            },
        )

    transcription_manager.add_task.assert_called_once()
    _, kwargs = transcription_manager.add_task.call_args
    options = kwargs["options"]
    assert options["language"] == "ja"
    assert options["enable_translation"] is False
    assert options["translation_source_lang"] == "auto"
    assert options["translation_target_lang"] == "fr"
