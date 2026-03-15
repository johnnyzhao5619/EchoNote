# SPDX-License-Identifier: Apache-2.0
"""Tests for calendar auto task scheduler workspace integration."""

from types import SimpleNamespace
from unittest.mock import Mock, patch

from core.calendar.auto_task_scheduler import CalendarAutoTaskScheduler


def _build_scheduler():
    calendar_manager = Mock()
    calendar_manager.db = Mock()
    transcription_manager = Mock()
    return CalendarAutoTaskScheduler(calendar_manager, transcription_manager)


def test_process_event_submits_transcription_from_workspace_recording():
    scheduler = _build_scheduler()
    scheduler.calendar_manager.workspace_manager = Mock()
    scheduler.calendar_manager.workspace_manager.get_event_artifacts.return_value = {
        "recording": "/tmp/meeting.wav",
        "transcript": None,
        "translation": None,
        "attachments": [],
    }

    event = SimpleNamespace(id="evt-1")
    config = SimpleNamespace(
        enable_transcription=True,
        enable_translation=True,
        translation_target_language="en",
        transcription_language="zh",
        event_id="evt-1",
    )

    with (
        patch("core.calendar.auto_task_scheduler.CalendarEvent.get_by_id", return_value=event),
        patch("core.calendar.auto_task_scheduler.AutoTaskConfig.get_by_event_id", return_value=config),
        patch.object(scheduler, "_disable_auto_transcribe") as mock_disable,
    ):
        scheduler._process_event("evt-1")

    scheduler.transcription_manager.add_task.assert_called_once_with(
        "/tmp/meeting.wav",
        options={
            "event_id": "evt-1",
            "language": "zh",
            "enable_translation": True,
            "translation_target_lang": "en",
        },
    )
    mock_disable.assert_called_once_with(config)


def test_process_event_skips_when_workspace_already_has_transcript():
    scheduler = _build_scheduler()
    scheduler.calendar_manager.workspace_manager = Mock()
    scheduler.calendar_manager.workspace_manager.get_event_artifacts.return_value = {
        "recording": "/tmp/meeting.wav",
        "transcript": "/tmp/meeting.txt",
        "translation": None,
        "attachments": [],
    }

    event = SimpleNamespace(id="evt-2")
    config = SimpleNamespace(
        enable_transcription=True,
        enable_translation=False,
        translation_target_language=None,
        transcription_language="auto",
        event_id="evt-2",
    )

    with (
        patch("core.calendar.auto_task_scheduler.CalendarEvent.get_by_id", return_value=event),
        patch("core.calendar.auto_task_scheduler.AutoTaskConfig.get_by_event_id", return_value=config),
        patch.object(scheduler, "_disable_auto_transcribe") as mock_disable,
    ):
        scheduler._process_event("evt-2")

    scheduler.transcription_manager.add_task.assert_not_called()
    mock_disable.assert_called_once_with(config)


def test_process_event_returns_when_workspace_manager_missing():
    scheduler = _build_scheduler()
    scheduler.calendar_manager.workspace_manager = None
    event = SimpleNamespace(id="evt-3")
    config = SimpleNamespace(
        enable_transcription=True,
        enable_translation=False,
        translation_target_language=None,
        transcription_language="auto",
        event_id="evt-3",
    )

    with (
        patch("core.calendar.auto_task_scheduler.CalendarEvent.get_by_id", return_value=event),
        patch("core.calendar.auto_task_scheduler.AutoTaskConfig.get_by_event_id", return_value=config),
    ):
        scheduler._process_event("evt-3")

    scheduler.transcription_manager.add_task.assert_not_called()
