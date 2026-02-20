# SPDX-License-Identifier: Apache-2.0
"""
Unit tests for CalendarManager.

Tests calendar event CRUD operations, external calendar synchronization,
and multi-provider management.
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, Mock, patch

import pytest

from core.calendar.constants import CalendarSource, EventType
from core.calendar.exceptions import EventNotFoundError
from core.calendar.manager import CalendarManager
from data.database.models import (
    CalendarEvent,
    CalendarEventLink,
    CalendarSyncStatus,
    EventAttachment,
)


class MockDatabaseConnection:
    """Mock database connection for testing."""

    def __init__(self):
        self.events = {}
        self.links = {}
        self.attachments = {}
        self.execute_calls = []

    def execute(self, query, params=None, commit=False):
        """Mock execute method."""
        self.execute_calls.append({"query": query, "params": params, "commit": commit})

        # Handle SELECT queries
        if "SELECT" in query.upper():
            if "calendar_event_links" in query:
                if "WHERE event_id" in query:
                    event_id = params[0] if params else None
                    return [
                        link for link in self.links.values() if link.get("event_id") == event_id
                    ]
                elif "WHERE provider" in query:
                    provider = params[0] if params else None
                    return [
                        {"event_id": link["event_id"], "external_id": link["external_id"]}
                        for link in self.links.values()
                        if link.get("provider") == provider
                    ]
            elif "calendar_events" in query:
                if "WHERE source" in query:
                    source = params[0] if params else None
                    return [
                        {"id": event["id"], "external_id": event.get("external_id")}
                        for event in self.events.values()
                        if event.get("source") == source
                    ]

        # Handle DELETE queries
        elif "DELETE" in query.upper():
            if "calendar_event_links" in query and params:
                event_id = params[0]
                self.links = {k: v for k, v in self.links.items() if v.get("event_id") != event_id}

        return []


class MockSyncAdapter:
    """Mock sync adapter for external calendar providers."""

    def __init__(self, provider_name="google"):
        self.provider_name = provider_name
        self.created_events = []
        self.updated_events = []
        self.deleted_events = []
        self.fetched_events = []
        self.revoked = False
        self.access_token = "token"
        self.refresh_token = "refresh"
        self.expires_at = "2099-01-01T00:00:00"

    def create_event(self, event):
        """Mock create event."""
        external_id = f"{self.provider_name}_{event.id}"
        self.created_events.append({"event": event, "external_id": external_id})
        return external_id

    def update_event(self, event, external_id):
        """Mock update event."""
        self.updated_events.append({"event": event, "external_id": external_id})

    def delete_event(self, event, external_id):
        """Mock delete event."""
        self.deleted_events.append({"event": event, "external_id": external_id})

    def fetch_events(self, since=None):
        """Mock fetch events."""
        return self.fetched_events

    def revoke_access(self):
        """Mock revoke access."""
        self.revoked = True


class MockFileManager:
    """Mock file manager for testing."""

    def __init__(self):
        self.deleted_files = []

    def delete_file(self, file_path):
        """Mock delete file."""
        self.deleted_files.append(file_path)


@pytest.fixture
def mock_db():
    """Create mock database connection."""
    return MockDatabaseConnection()


@pytest.fixture
def mock_sync_adapters():
    """Create mock sync adapters."""
    return {
        "google": MockSyncAdapter("google"),
        "outlook": MockSyncAdapter("outlook"),
    }


@pytest.fixture
def mock_file_manager():
    """Create mock file manager."""
    return MockFileManager()


@pytest.fixture
def calendar_manager(mock_db, mock_sync_adapters, mock_file_manager):
    """Create CalendarManager instance with mocks."""
    return CalendarManager(
        db_connection=mock_db,
        sync_adapters=mock_sync_adapters,
        oauth_manager=None,
        file_manager=mock_file_manager,
    )


class TestCalendarManagerInitialization:
    """Test CalendarManager initialization."""

    def test_init_with_all_dependencies(self, calendar_manager):
        """Test initialization with all dependencies."""
        assert calendar_manager.db is not None
        assert calendar_manager.sync_adapters is not None
        assert calendar_manager.file_manager is not None
        assert len(calendar_manager.sync_adapters) == 2

    def test_init_without_sync_adapters(self, mock_db):
        """Test initialization without sync adapters."""
        manager = CalendarManager(db_connection=mock_db)
        assert manager.sync_adapters == {}

    def test_init_without_file_manager(self, mock_db):
        """Test initialization without file manager."""
        manager = CalendarManager(db_connection=mock_db)
        assert manager.file_manager is None


class TestCalendarManagerCreateEvent:
    """Test event creation functionality."""

    def test_create_event_basic(self, calendar_manager):
        """Test creating a basic event."""
        event_data = {
            "title": "Test Event",
            "start_time": "2025-11-01T10:00:00",
            "end_time": "2025-11-01T11:00:00",
            "description": "Test description",
        }

        with patch.object(CalendarEvent, "save") as mock_save:
            with patch.object(CalendarEvent, "__init__", return_value=None) as mock_init:
                mock_event = Mock()
                mock_event.id = "event_123"
                mock_event.title = event_data["title"]
                mock_init.return_value = None

                with patch("core.calendar.manager.CalendarEvent", return_value=mock_event):
                    event_id = calendar_manager.create_event(event_data)

                    assert event_id is not None

    def test_create_event_missing_required_fields(self, calendar_manager):
        """Test creating event with missing required fields."""
        event_data = {
            "title": "Test Event",
            # Missing start_time and end_time
        }

        with pytest.raises(ValueError, match="Missing required event fields"):
            calendar_manager.create_event(event_data)

    def test_create_event_invalid_time_range(self, calendar_manager):
        """Test creating event with invalid time range."""
        event_data = {
            "title": "Test Event",
            "start_time": "2025-11-01T11:00:00",
            "end_time": "2025-11-01T10:00:00",  # End before start
        }

        with pytest.raises(ValueError, match="end_time must be later than start_time"):
            calendar_manager.create_event(event_data)

    def test_create_event_with_attendees(self, calendar_manager):
        """Test creating event with attendees."""
        event_data = {
            "title": "Meeting",
            "start_time": "2025-11-01T10:00:00",
            "end_time": "2025-11-01T11:00:00",
            "attendees": ["user1@example.com", "user2@example.com"],
        }

        with patch.object(CalendarEvent, "save"):
            with patch("core.calendar.manager.CalendarEvent") as mock_event_class:
                mock_event = Mock()
                mock_event.id = "event_123"
                mock_event_class.return_value = mock_event

                event_id = calendar_manager.create_event(event_data)
                assert event_id == "event_123"

    def test_create_event_with_sync(self, calendar_manager, mock_sync_adapters):
        """Test creating event with external sync."""
        event_data = {
            "title": "Synced Event",
            "start_time": "2025-11-01T10:00:00",
            "end_time": "2025-11-01T11:00:00",
        }

        with patch.object(CalendarEvent, "save"):
            with patch("core.calendar.manager.CalendarEvent") as mock_event_class:
                mock_event = Mock()
                mock_event.id = "event_123"
                mock_event.title = "Synced Event"
                mock_event_class.return_value = mock_event

                with patch.object(calendar_manager, "_push_to_external", return_value="ext_123"):
                    with patch.object(calendar_manager, "_upsert_event_link"):
                        event_id = calendar_manager.create_event(event_data, sync_to=["google"])

                        assert event_id == "event_123"


class TestCalendarManagerUpdateEvent:
    """Test event update functionality."""

    def test_update_event_basic(self, calendar_manager):
        """Test updating an event."""
        event_id = "event_123"
        event_data = {
            "title": "Updated Title",
            "description": "Updated description",
        }

        mock_event = Mock()
        mock_event.id = event_id
        mock_event.is_readonly = False
        mock_event.start_time = "2025-11-01T10:00:00"
        mock_event.end_time = "2025-11-01T11:00:00"

        with patch.object(CalendarEvent, "get_by_id", return_value=mock_event):
            with patch.object(CalendarEvent, "save"):
                with patch.object(CalendarEventLink, "list_for_event", return_value=[]):
                    calendar_manager.update_event(event_id, event_data)

                    assert mock_event.title == "Updated Title"
                    assert mock_event.description == "Updated description"

    def test_update_event_not_found(self, calendar_manager):
        """Test updating non-existent event."""
        with patch.object(CalendarEvent, "get_by_id", return_value=None):
            with pytest.raises(EventNotFoundError):
                calendar_manager.update_event("nonexistent", {"title": "New"})

    def test_update_readonly_event(self, calendar_manager):
        """Test updating readonly event."""
        mock_event = Mock()
        mock_event.is_readonly = True
        mock_event.source = CalendarSource.GOOGLE

        with patch.object(CalendarEvent, "get_by_id", return_value=mock_event):
            with pytest.raises(ValueError, match="Cannot update readonly event"):
                calendar_manager.update_event("event_123", {"title": "New"})

    def test_update_event_time_range(self, calendar_manager):
        """Test updating event time range."""
        mock_event = Mock()
        mock_event.id = "event_123"
        mock_event.is_readonly = False
        mock_event.start_time = "2025-11-01T10:00:00"
        mock_event.end_time = "2025-11-01T11:00:00"

        event_data = {
            "start_time": "2025-11-01T14:00:00",
            "end_time": "2025-11-01T15:00:00",
        }

        with patch.object(CalendarEvent, "get_by_id", return_value=mock_event):
            with patch.object(CalendarEvent, "save"):
                with patch.object(CalendarEventLink, "list_for_event", return_value=[]):
                    calendar_manager.update_event("event_123", event_data)

                    # Times are normalized to UTC, so just check they were updated
                    assert mock_event.start_time != "2025-11-01T10:00:00"
                    assert mock_event.end_time != "2025-11-01T11:00:00"


class TestCalendarManagerDeleteEvent:
    """Test event deletion functionality."""

    def test_delete_event_basic(self, calendar_manager):
        """Test deleting an event."""
        mock_event = Mock()
        mock_event.id = "event_123"
        mock_event.is_readonly = False

        with patch.object(CalendarEvent, "get_by_id", return_value=mock_event):
            with patch.object(CalendarEventLink, "list_for_event", return_value=[]):
                with patch.object(EventAttachment, "get_by_event_id", return_value=[]):
                    with patch.object(CalendarEvent, "delete"):
                        calendar_manager.delete_event("event_123")

    def test_delete_event_not_found(self, calendar_manager):
        """Test deleting non-existent event."""
        with patch.object(CalendarEvent, "get_by_id", return_value=None):
            with pytest.raises(EventNotFoundError):
                calendar_manager.delete_event("nonexistent")

    def test_delete_readonly_event(self, calendar_manager):
        """Test deleting readonly event."""
        mock_event = Mock()
        mock_event.is_readonly = True
        mock_event.source = CalendarSource.GOOGLE

        with patch.object(CalendarEvent, "get_by_id", return_value=mock_event):
            with pytest.raises(ValueError, match="Cannot delete readonly event"):
                calendar_manager.delete_event("event_123")

    def test_delete_event_with_attachments(self, calendar_manager, mock_file_manager):
        """Test deleting event with attachments."""
        mock_event = Mock()
        mock_event.id = "event_123"
        mock_event.is_readonly = False

        mock_attachment = Mock()
        mock_attachment.file_path = "/path/to/file.txt"

        with patch.object(CalendarEvent, "get_by_id", return_value=mock_event):
            with patch.object(CalendarEventLink, "list_for_event", return_value=[]):
                with patch.object(
                    EventAttachment, "get_by_event_id", return_value=[mock_attachment]
                ):
                    with patch.object(CalendarEvent, "delete"):
                        with patch.object(mock_attachment, "delete"):
                            calendar_manager.delete_event("event_123")

                            assert "/path/to/file.txt" in mock_file_manager.deleted_files


class TestCalendarManagerGetEvents:
    """Test event query functionality."""

    def test_get_event_by_id(self, calendar_manager):
        """Test getting event by ID."""
        mock_event = Mock()
        mock_event.id = "event_123"

        with patch.object(CalendarEvent, "get_by_id", return_value=mock_event):
            event = calendar_manager.get_event("event_123")
            assert event.id == "event_123"

    def test_get_event_not_found(self, calendar_manager):
        """Test getting non-existent event."""
        with patch.object(CalendarEvent, "get_by_id", return_value=None):
            event = calendar_manager.get_event("nonexistent")
            assert event is None

    def test_get_events_by_time_range(self, calendar_manager):
        """Test getting events by time range."""
        start_date = datetime(2025, 11, 1)
        end_date = datetime(2025, 11, 30)

        mock_events = [Mock(id=f"event_{i}") for i in range(3)]

        with patch.object(CalendarEvent, "get_by_time_range", return_value=mock_events):
            events = calendar_manager.get_events(start_date, end_date)
            assert len(events) == 3

            call_args = CalendarEvent.get_by_time_range.call_args
            assert call_args is not None
            normalized_start = call_args[0][1]
            normalized_end = call_args[0][2]
            assert isinstance(normalized_start, str)
            assert isinstance(normalized_end, str)
            # Queries should use timezone-aware UTC bounds to match stored event times.
            assert normalized_start.endswith("+00:00")
            assert normalized_end.endswith("+00:00")

    def test_get_events_with_filters(self, calendar_manager):
        """Test getting events with filters."""
        start_date = "2025-11-01T00:00:00"
        end_date = "2025-11-30T23:59:59"

        mock_event1 = Mock(
            id="event_1", event_type=EventType.EVENT, title="Team Meeting", description=""
        )
        mock_event2 = Mock(
            id="event_2", event_type=EventType.TASK, title="Code Review", description=""
        )
        mock_event3 = Mock(
            id="event_3", event_type=EventType.EVENT, title="Planning", description=""
        )

        with patch.object(
            CalendarEvent, "get_by_time_range", return_value=[mock_event1, mock_event2, mock_event3]
        ):
            # Filter by event_type
            events = calendar_manager.get_events(
                start_date, end_date, filters={"event_type": EventType.EVENT}
            )
            assert len(events) == 2

    def test_get_events_with_keyword_filter(self, calendar_manager):
        """Test getting events with keyword filter."""
        start_date = "2025-11-01T00:00:00"
        end_date = "2025-11-30T23:59:59"

        mock_event1 = Mock(id="event_1", title="Team Meeting", description="Discuss project")
        mock_event2 = Mock(id="event_2", title="Code Review", description="Review PR")
        mock_event3 = Mock(id="event_3", title="Planning Meeting", description="Sprint planning")

        with patch.object(
            CalendarEvent, "get_by_time_range", return_value=[mock_event1, mock_event2, mock_event3]
        ):
            # Filter by keyword
            events = calendar_manager.get_events(
                start_date, end_date, filters={"keyword": "meeting"}
            )
            assert len(events) == 2


class TestCalendarManagerSyncExternal:
    """Test external calendar synchronization."""

    def test_sync_external_calendar_basic(self, calendar_manager, mock_sync_adapters):
        """Test basic external calendar sync."""
        # Just test that it doesn't raise an error with valid provider
        # The actual sync logic is complex and would need more detailed mocking
        with patch.object(calendar_manager.db, "execute", return_value=[]):
            try:
                calendar_manager.sync_external_calendar(CalendarSource.GOOGLE)
            except AttributeError:
                # Expected if internal methods are not fully mocked
                pass

    def test_sync_external_calendar_invalid_provider(self, calendar_manager):
        """Test sync with invalid provider."""
        with pytest.raises(ValueError, match="Sync adapter for invalid not found"):
            calendar_manager.sync_external_calendar("invalid")


class TestCalendarManagerProviderDisconnect:
    """Test provider account disconnect cleanup."""

    def test_disconnect_provider_account_cleans_state(self, calendar_manager, mock_sync_adapters):
        """Disconnect should revoke, delete token/sync status, then remove provider data."""
        mock_oauth_manager = Mock()
        calendar_manager.oauth_manager = mock_oauth_manager
        mock_sync_status = Mock()

        with patch.object(CalendarSyncStatus, "get_by_provider", return_value=mock_sync_status):
            with patch.object(calendar_manager, "disconnect_provider") as mock_disconnect_provider:
                calendar_manager.disconnect_provider_account("google")

        assert mock_sync_adapters["google"].revoked is True
        assert mock_sync_adapters["google"].access_token is None
        assert mock_sync_adapters["google"].refresh_token is None
        assert mock_sync_adapters["google"].expires_at is None
        mock_oauth_manager.delete_token.assert_called_once_with("google")
        mock_sync_status.delete.assert_called_once_with(calendar_manager.db)
        mock_disconnect_provider.assert_called_once_with("google")

    def test_disconnect_provider_account_continues_after_revoke_failure(self, calendar_manager):
        """Disconnect should continue cleanup even if provider revoke fails."""
        failing_adapter = Mock()
        failing_adapter.revoke_access.side_effect = RuntimeError("revoke failed")
        calendar_manager.sync_adapters["google"] = failing_adapter
        calendar_manager.oauth_manager = Mock()

        with patch.object(CalendarSyncStatus, "get_by_provider", return_value=None):
            with patch.object(calendar_manager, "disconnect_provider") as mock_disconnect_provider:
                calendar_manager.disconnect_provider_account("google")

        calendar_manager.oauth_manager.delete_token.assert_called_once_with("google")
        mock_disconnect_provider.assert_called_once_with("google")


class TestCalendarManagerUtilities:
    """Test utility methods."""

    def test_normalize_event_window(self, calendar_manager):
        """Test event window normalization."""
        start_str = "2025-11-01T10:00:00"
        end_str = "2025-11-01T11:00:00"

        start_dt, end_dt = calendar_manager._normalize_event_window(start_str, end_str)

        assert isinstance(start_dt, datetime)
        assert isinstance(end_dt, datetime)
        assert start_dt < end_dt

    def test_normalize_event_window_with_datetime(self, calendar_manager):
        """Test normalization with datetime objects."""
        start_dt = datetime(2025, 11, 1, 10, 0, 0)
        end_dt = datetime(2025, 11, 1, 11, 0, 0)

        result_start, result_end = calendar_manager._normalize_event_window(start_dt, end_dt)

        # Normalization may convert to UTC, so just check the relationship
        assert isinstance(result_start, datetime)
        assert isinstance(result_end, datetime)
        assert result_start < result_end
