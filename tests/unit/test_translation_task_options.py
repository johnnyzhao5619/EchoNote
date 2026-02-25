# SPDX-License-Identifier: Apache-2.0
"""Unit tests for shared translation task option helpers."""

from unittest.mock import Mock

from ui.common.translation_task_options import (
    build_event_translation_task_options,
    enqueue_event_translation_task,
)


def test_build_event_translation_task_options_uses_markdown_output_for_md_file():
    options = build_event_translation_task_options(
        settings_manager=None,
        event_id="evt-1",
        transcript_path="/tmp/transcript.md",
    )

    assert options["event_id"] == "evt-1"
    assert options["output_format"] == "md"


def test_enqueue_event_translation_task_returns_false_when_manager_missing():
    queued = enqueue_event_translation_task(
        transcription_manager=None,
        settings_manager=None,
        event_id="evt-1",
        transcript_path="/tmp/transcript.txt",
        logger=Mock(),
        context_label="timeline transcript translation",
    )

    assert queued is False


def test_enqueue_event_translation_task_handles_missing_transcript_callback():
    on_missing_transcript = Mock()
    transcription_manager = Mock()
    transcription_manager.translation_engine = object()

    queued = enqueue_event_translation_task(
        transcription_manager=transcription_manager,
        settings_manager=None,
        event_id="evt-1",
        transcript_path="",
        logger=Mock(),
        context_label="timeline transcript translation",
        on_missing_transcript=on_missing_transcript,
    )

    assert queued is False
    on_missing_transcript.assert_called_once()
    transcription_manager.add_translation_task.assert_not_called()


def test_enqueue_event_translation_task_handles_translation_unavailable_callback():
    on_translation_unavailable = Mock()
    transcription_manager = Mock()
    transcription_manager.translation_engine = None

    queued = enqueue_event_translation_task(
        transcription_manager=transcription_manager,
        settings_manager=None,
        event_id="evt-1",
        transcript_path="/tmp/transcript.txt",
        logger=Mock(),
        context_label="timeline transcript translation",
        on_translation_unavailable=on_translation_unavailable,
    )

    assert queued is False
    on_translation_unavailable.assert_called_once()
    transcription_manager.add_translation_task.assert_not_called()


def test_enqueue_event_translation_task_queues_task_and_invokes_success_callback():
    on_queued = Mock()
    transcription_manager = Mock()
    transcription_manager.translation_engine = object()
    logger = Mock()

    queued = enqueue_event_translation_task(
        transcription_manager=transcription_manager,
        settings_manager=None,
        event_id="evt-1",
        transcript_path="/tmp/transcript.md",
        logger=logger,
        context_label="timeline transcript translation",
        on_queued=on_queued,
    )

    assert queued is True
    on_queued.assert_called_once()
    transcription_manager.add_translation_task.assert_called_once()
    args, kwargs = transcription_manager.add_translation_task.call_args
    assert args[0] == "/tmp/transcript.md"
    assert kwargs["options"]["event_id"] == "evt-1"
    assert kwargs["options"]["output_format"] == "md"


def test_enqueue_event_translation_task_invokes_failure_callback_when_submit_fails():
    on_failed = Mock()
    transcription_manager = Mock()
    transcription_manager.translation_engine = object()
    transcription_manager.add_translation_task.side_effect = RuntimeError("queue-failed")
    logger = Mock()

    queued = enqueue_event_translation_task(
        transcription_manager=transcription_manager,
        settings_manager=None,
        event_id="evt-1",
        transcript_path="/tmp/transcript.txt",
        logger=logger,
        context_label="calendar transcript translation",
        on_failed=on_failed,
    )

    assert queued is False
    on_failed.assert_called_once()
    assert isinstance(on_failed.call_args.args[0], RuntimeError)
    logger.error.assert_called_once()
