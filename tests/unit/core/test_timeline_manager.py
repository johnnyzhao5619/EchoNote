# SPDX-License-Identifier: Apache-2.0
"""
Unit tests for TimelineManager.

Tests timeline event aggregation, search functionality, and artifact retrieval.
"""

from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import pytest

from core.timeline.manager import TimelineManager


@pytest.fixture
def mock_calendar_manager():
    """Create mock calendar manager."""
    manager = Mock()
    manager.get_events = Mock(return_value=[])
    return manager


@pytest.fixture
def mock_db():
    """Create mock database connection."""
    db = Mock()
    db.execute = Mock(return_value=[])
    return db


@pytest.fixture
def timeline_manager(mock_calendar_manager, mock_db):
    """Create TimelineManager instance."""
    return TimelineManager(
        calendar_manager=mock_calendar_manager, db_connection=mock_db, i18n=None, translate=None
    )


class TestTimelineManagerInitialization:
    """Test TimelineManager initialization."""

    def test_init_basic(self, timeline_manager):
        """Test basic initialization."""
        assert timeline_manager.calendar_manager is not None
        assert timeline_manager.db is not None

    def test_init_with_translate(self, mock_calendar_manager, mock_db):
        """Test initialization with translate callback."""
        translate_fn = Mock(return_value="Translated")
        manager = TimelineManager(
            calendar_manager=mock_calendar_manager, db_connection=mock_db, translate=translate_fn
        )
        assert manager._translate_callback == translate_fn

    def test_init_with_both_i18n_and_translate_raises(self, mock_calendar_manager, mock_db):
        """Test that providing both i18n and translate raises error."""
        i18n = Mock()
        translate_fn = Mock()

        with pytest.raises(
            ValueError, match="Provide either an i18n manager or a translation callback"
        ):
            TimelineManager(
                calendar_manager=mock_calendar_manager,
                db_connection=mock_db,
                i18n=i18n,
                translate=translate_fn,
            )


class TestTimelineManagerGetEvents:
    """Test timeline event retrieval."""

    def test_get_timeline_events_basic(self, timeline_manager, mock_calendar_manager):
        """Test getting timeline events."""
        center_time = datetime(2025, 11, 1, 12, 0, 0)
        mock_event = Mock()
        mock_event.id = "event_1"
        mock_event.title = "Test Event"
        mock_event.start_time = "2025-11-01T10:00:00"
        mock_event.end_time = "2025-11-01T11:00:00"
        mock_calendar_manager.get_events.return_value = [mock_event]

        result = timeline_manager.get_timeline_events(center_time, past_days=7, future_days=7)

        # Returns a dict with past_events and future_events
        assert isinstance(result, dict)
        assert "past_events" in result or "future_events" in result

    def test_get_timeline_events_with_window(self, timeline_manager, mock_calendar_manager):
        """Test getting events with custom window."""
        center_time = datetime(2025, 11, 1, 12, 0, 0)
        mock_calendar_manager.get_events.return_value = []

        result = timeline_manager.get_timeline_events(center_time, past_days=14, future_days=14)

        assert isinstance(result, dict)


class TestTimelineManagerSearch:
    """Test search functionality."""

    def test_search_events_basic(self, timeline_manager):
        """Test basic event search."""
        with patch.object(timeline_manager.calendar_manager, "get_events", return_value=[]):
            results = timeline_manager.search_events("test query")

            assert isinstance(results, list)

    def test_search_events_empty_query(self, timeline_manager):
        """Test search with empty query."""
        results = timeline_manager.search_events("")

        assert results == []

    def test_search_events_with_filters(self, timeline_manager):
        """Test search with filters."""
        with patch.object(timeline_manager.calendar_manager, "get_events", return_value=[]):
            results = timeline_manager.search_events("test", filters={"event_type": "Meeting"})

            assert isinstance(results, list)


class TestTimelineManagerArtifacts:
    """Test artifact retrieval."""

    def test_get_event_artifacts_basic(self, timeline_manager):
        """Test getting event artifacts."""
        event_id = "event_123"

        with patch("data.database.models.EventAttachment.get_by_event_id", return_value=[]):
            artifacts = timeline_manager.get_event_artifacts(event_id)

            assert isinstance(artifacts, dict)
            assert "attachments" in artifacts

    def test_get_event_artifacts_with_attachments(self, timeline_manager):
        """Test getting artifacts with attachments."""
        event_id = "event_123"

        mock_attachment = Mock()
        mock_attachment.attachment_type = "recording"
        mock_attachment.file_path = "/path/to/recording.wav"
        mock_attachment.file_size = 1000

        with patch(
            "data.database.models.EventAttachment.get_by_event_id", return_value=[mock_attachment]
        ):
            artifacts = timeline_manager.get_event_artifacts(event_id)

            # Check that artifacts dict is returned
            assert isinstance(artifacts, dict)
            assert "attachments" in artifacts


class TestTimelineManagerAutoTask:
    """Test auto-task configuration."""

    def test_default_auto_task_config(self, timeline_manager):
        """Test default auto-task config."""
        # TimelineManager has _default_auto_task_config method
        assert hasattr(timeline_manager, "_default_auto_task_config")


class TestTimelineManagerUtilities:
    """Test utility methods."""

    def test_translate_with_callback(self, mock_calendar_manager, mock_db):
        """Test translation with callback."""
        translate_fn = Mock(return_value="Translated Text")
        manager = TimelineManager(
            calendar_manager=mock_calendar_manager, db_connection=mock_db, translate=translate_fn
        )

        result = manager._translate("key", "default")
        assert result == "Translated Text"

    def test_translate_without_callback(self, timeline_manager):
        """Test translation without callback returns default."""
        result = timeline_manager._translate("key", "default")
        assert result == "default"

    def test_translate_with_exception(self, mock_calendar_manager, mock_db):
        """Test translation handles exceptions."""
        translate_fn = Mock(side_effect=Exception("Translation error"))
        manager = TimelineManager(
            calendar_manager=mock_calendar_manager, db_connection=mock_db, translate=translate_fn
        )

        result = manager._translate("key", "default")
        assert result == "default"
