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

    def test_get_timeline_events_date_filter_uses_overlap(
        self, timeline_manager, mock_calendar_manager
    ):
        """跨天事件只要与筛选日期重叠就应被包含。"""
        center_time = datetime(2025, 11, 2, 12, 0, 0)
        spanning_event = Mock()
        spanning_event.id = "event_overlap"
        spanning_event.title = "Overnight Event"
        spanning_event.start_time = "2025-11-01T23:00:00"
        spanning_event.end_time = "2025-11-02T01:00:00"
        spanning_event.event_type = "Event"
        spanning_event.source = "local"
        spanning_event.attendees = []
        mock_calendar_manager.get_events.return_value = [spanning_event]

        result = timeline_manager.get_timeline_events(
            center_time,
            past_days=2,
            future_days=1,
            filters={"start_date": "2025-11-02", "end_date": "2025-11-02"},
        )

        assert len(result["past_events"]) == 1
        assert result["past_events"][0]["event"].id == "event_overlap"

    def test_get_timeline_events_orders_future_events_farthest_first(
        self, timeline_manager, mock_calendar_manager
    ):
        """未来事件应按开始时间从最远到最近排序。"""
        center_time = datetime(2025, 11, 1, 12, 0, 0)

        near_event = Mock()
        near_event.id = "event_near"
        near_event.title = "Near Event"
        near_event.start_time = "2025-11-01T13:00:00"
        near_event.end_time = "2025-11-01T14:00:00"
        near_event.event_type = "Event"
        near_event.source = "local"
        near_event.attendees = []

        far_event = Mock()
        far_event.id = "event_far"
        far_event.title = "Far Event"
        far_event.start_time = "2025-11-01T18:00:00"
        far_event.end_time = "2025-11-01T19:00:00"
        far_event.event_type = "Event"
        far_event.source = "local"
        far_event.attendees = []

        mock_calendar_manager.get_events.return_value = [near_event, far_event]

        result = timeline_manager.get_timeline_events(center_time, past_days=1, future_days=1)

        assert [item["event"].id for item in result["future_events"]] == ["event_far", "event_near"]

    def test_get_timeline_events_upcoming_filter_uses_time_semantics(
        self, timeline_manager, mock_calendar_manager
    ):
        """'Upcoming' filter should include only events that have not started yet."""
        center_time = datetime.now().replace(microsecond=0)

        past_task = Mock()
        past_task.id = "task_past"
        past_task.title = "Past Task"
        past_task_start = center_time - timedelta(hours=2)
        past_task_end = center_time - timedelta(hours=1)
        past_task.start_time = past_task_start.isoformat()
        past_task.end_time = past_task_end.isoformat()
        past_task.event_type = "Task"
        past_task.source = "local"
        past_task.attendees = []

        future_event = Mock()
        future_event.id = "event_future"
        future_event.title = "Future Event"
        future_start = center_time + timedelta(hours=1)
        future_end = center_time + timedelta(hours=2)
        future_event.start_time = future_start.isoformat()
        future_event.end_time = future_end.isoformat()
        future_event.event_type = "Event"
        future_event.source = "local"
        future_event.attendees = []

        mock_calendar_manager.get_events.return_value = [past_task, future_event]

        result = timeline_manager.get_timeline_events(
            center_time,
            past_days=2,
            future_days=2,
            filters={"event_type": "__upcoming__"},
        )

        assert result["past_events"] == []
        assert [item["event"].id for item in result["future_events"]] == ["event_future"]


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

    def test_search_events_sorted_by_start_time_desc(self, timeline_manager):
        """搜索结果应按开始时间倒序稳定返回。"""
        older = Mock()
        older.id = "event_old"
        older.title = "Old Event"
        older.description = ""
        older.start_time = "2025-11-01T09:00:00"
        older.end_time = "2025-11-01T10:00:00"
        older.event_type = "Event"
        older.source = "local"
        older.attendees = []

        newer = Mock()
        newer.id = "event_new"
        newer.title = "New Event"
        newer.description = ""
        newer.start_time = "2025-11-02T09:00:00"
        newer.end_time = "2025-11-02T10:00:00"
        newer.event_type = "Event"
        newer.source = "local"
        newer.attendees = []

        with patch("data.database.models.CalendarEvent.search", return_value=[older, newer]):
            results = timeline_manager.search_events("")

        assert [item["event"].id for item in results] == ["event_new", "event_old"]


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
        """Default auto-task config should be exposed via public API and be copy-safe."""
        first = timeline_manager.get_default_auto_task_config()
        second = timeline_manager.get_default_auto_task_config()

        assert first == {
            "enable_transcription": False,
            "enable_recording": False,
            "transcription_language": None,
            "enable_translation": False,
            "translation_target_language": None,
        }
        assert second == first

        first["enable_recording"] = True
        assert second["enable_recording"] is False


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
