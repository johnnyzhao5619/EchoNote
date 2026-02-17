# SPDX-License-Identifier: Apache-2.0
"""
Unit tests for database models.

Tests model creation, serialization, and database operations.
"""

from datetime import datetime
from unittest.mock import MagicMock, Mock

import pytest

from data.database.models import (
    CalendarEvent,
    TranscriptionTask,
    current_timestamp,
    generate_uuid,
)
from config.constants import (
    TASK_STATUS_PENDING,
    TASK_STATUS_COMPLETED,
    DEFAULT_TRANSCRIPTION_ENGINE,
    ENGINE_FASTER_WHISPER,
)


class TestHelperFunctions:
    """Test helper functions."""

    def test_generate_uuid(self):
        """Test UUID generation."""
        uuid1 = generate_uuid()
        uuid2 = generate_uuid()

        assert isinstance(uuid1, str)
        assert isinstance(uuid2, str)
        assert len(uuid1) == 36
        assert uuid1 != uuid2

    def test_current_timestamp(self):
        """Test timestamp generation."""
        timestamp = current_timestamp()

        assert isinstance(timestamp, str)
        # Should be parseable as ISO format
        datetime.fromisoformat(timestamp)


class TestTranscriptionTask:
    """Test TranscriptionTask model."""

    def test_create_default(self):
        """Test creating task with defaults."""
        task = TranscriptionTask()

        assert task.id is not None
        assert len(task.id) == 36
        assert task.status == TASK_STATUS_PENDING
        assert task.progress == 0.0
        assert task.engine == DEFAULT_TRANSCRIPTION_ENGINE

    def test_create_with_values(self):
        """Test creating task with specific values."""
        task = TranscriptionTask(
            file_path="/tmp/test.wav", file_name="test.wav", file_size=1024, language="en"
        )

        assert task.file_path == "/tmp/test.wav"
        assert task.file_name == "test.wav"
        assert task.file_size == 1024
        assert task.language == "en"

    def test_from_db_row(self):
        """Test creating task from database row."""
        row = {
            "id": "test-id",
            "file_path": "/tmp/test.wav",
            "file_name": "test.wav",
            "file_size": 1024,
            "audio_duration": 60.0,
            "status": TASK_STATUS_COMPLETED,
            "progress": 100.0,
            "language": "en",
            "engine": ENGINE_FASTER_WHISPER,
            "output_format": "txt",
            "output_path": "/tmp/output.txt",
            "error_message": None,
            "created_at": "2025-10-30T12:00:00",
            "started_at": "2025-10-30T12:01:00",
            "completed_at": "2025-10-30T12:02:00",
        }

        task = TranscriptionTask.from_db_row(row)

        assert task.id == "test-id"
        assert task.file_path == "/tmp/test.wav"
        assert task.status == TASK_STATUS_COMPLETED
        assert task.progress == 100.0

    def test_save(self):
        """Test saving task to database."""
        mock_db = Mock()
        mock_db.execute = Mock()

        task = TranscriptionTask(file_path="/tmp/test.wav", file_name="test.wav")

        task.save(mock_db)

        # Should call execute with INSERT query
        mock_db.execute.assert_called_once()
        call_args = mock_db.execute.call_args
        assert "INSERT OR REPLACE" in call_args[0][0]

    def test_get_by_id(self):
        """Test getting task by ID."""
        mock_db = Mock()
        mock_db.execute = Mock(
            return_value=[
                {
                    "id": "test-id",
                    "file_path": "/tmp/test.wav",
                    "file_name": "test.wav",
                    "file_size": 1024,
                    "audio_duration": 60.0,
                    "status": TASK_STATUS_COMPLETED,
                    "progress": 100.0,
                    "language": "en",
                    "engine": ENGINE_FASTER_WHISPER,
                    "output_format": "txt",
                    "output_path": "/tmp/output.txt",
                    "error_message": None,
                    "created_at": "2025-10-30T12:00:00",
                    "started_at": "2025-10-30T12:01:00",
                    "completed_at": "2025-10-30T12:02:00",
                }
            ]
        )

        task = TranscriptionTask.get_by_id(mock_db, "test-id")

        assert task is not None
        assert task.id == "test-id"

    def test_get_by_id_not_found(self):
        """Test getting non-existent task."""
        mock_db = Mock()
        mock_db.execute = Mock(return_value=[])

        task = TranscriptionTask.get_by_id(mock_db, "nonexistent")

        assert task is None

    def test_get_all(self):
        """Test getting all tasks."""
        mock_db = Mock()
        mock_db.execute = Mock(
            return_value=[
                {
                    "id": "task-1",
                    "file_path": "/tmp/test1.wav",
                    "file_name": "test1.wav",
                    "file_size": 1024,
                    "audio_duration": 60.0,
                    "status": TASK_STATUS_COMPLETED,
                    "progress": 100.0,
                    "language": "en",
                    "engine": ENGINE_FASTER_WHISPER,
                    "output_format": "txt",
                    "output_path": "/tmp/output1.txt",
                    "error_message": None,
                    "created_at": "2025-10-30T12:00:00",
                    "started_at": "2025-10-30T12:01:00",
                    "completed_at": "2025-10-30T12:02:00",
                },
                {
                    "id": "task-2",
                    "file_path": "/tmp/test2.wav",
                    "file_name": "test2.wav",
                    "file_size": 2048,
                    "audio_duration": 120.0,
                    "status": TASK_STATUS_PENDING,
                    "progress": 0.0,
                    "language": "zh",
                    "engine": ENGINE_FASTER_WHISPER,
                    "output_format": None,
                    "output_path": None,
                    "error_message": None,
                    "created_at": "2025-10-30T12:05:00",
                    "started_at": None,
                    "completed_at": None,
                },
            ]
        )

        tasks = TranscriptionTask.get_all(mock_db)

        assert len(tasks) == 2
        assert tasks[0].id == "task-1"
        assert tasks[1].id == "task-2"

    def test_get_all_filtered(self):
        """Test getting tasks filtered by status."""
        mock_db = Mock()
        mock_db.execute = Mock(return_value=[])

        TranscriptionTask.get_all(mock_db, status=TASK_STATUS_COMPLETED)

        call_args = mock_db.execute.call_args
        assert "WHERE status = ?" in call_args[0][0]

    def test_delete(self):
        """Test deleting task."""
        mock_db = Mock()
        mock_db.execute = Mock()

        task = TranscriptionTask(id="test-id")
        task.delete(mock_db)

        mock_db.execute.assert_called_once()
        call_args = mock_db.execute.call_args
        assert "DELETE FROM" in call_args[0][0]


class TestCalendarEvent:
    """Test CalendarEvent model."""

    def test_create_default(self):
        """Test creating event with defaults."""
        event = CalendarEvent()

        assert event.id is not None
        assert event.event_type == "Event"
        assert event.source == "local"
        assert not event.is_readonly

    def test_create_with_values(self):
        """Test creating event with specific values."""
        event = CalendarEvent(
            title="Test Event",
            start_time="2025-10-30T12:00:00",
            end_time="2025-10-30T13:00:00",
            location="Office",
        )

        assert event.title == "Test Event"
        assert event.start_time == "2025-10-30T12:00:00"
        assert event.end_time == "2025-10-30T13:00:00"
        assert event.location == "Office"

    def test_attendees_list(self):
        """Test event with attendees list."""
        event = CalendarEvent(title="Meeting", attendees=["user1@example.com", "user2@example.com"])

        assert len(event.attendees) == 2
        assert "user1@example.com" in event.attendees

    def test_save(self):
        """Test saving event to database."""
        mock_db = Mock()
        mock_db.execute = Mock()

        event = CalendarEvent(
            title="Test Event", start_time="2025-10-30T12:00:00", end_time="2025-10-30T13:00:00"
        )

        event.save(mock_db)

        mock_db.execute.assert_called_once()
        call_args = mock_db.execute.call_args
        assert "INSERT INTO calendar_events" in call_args[0][0]

    def test_from_db_row(self):
        """Test creating event from database row."""
        row = {
            "id": "event-1",
            "title": "Test Event",
            "event_type": "Meeting",
            "start_time": "2025-10-30T12:00:00",
            "end_time": "2025-10-30T13:00:00",
            "location": "Office",
            "attendees": '["user1@example.com"]',
            "description": "Test description",
            "reminder_minutes": 15,
            "reminder_use_default": None,
            "recurrence_rule": None,
            "source": "local",
            "external_id": None,
            "is_readonly": 0,
            "created_at": "2025-10-30T11:00:00",
            "updated_at": "2025-10-30T11:00:00",
        }

        event = CalendarEvent.from_db_row(row)

        assert event.id == "event-1"
        assert event.title == "Test Event"
        assert len(event.attendees) == 1
