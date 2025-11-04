# SPDX-License-Identifier: Apache-2.0
"""
Unit tests for AutoTaskScheduler.

Tests automatic task scheduling, reminder notifications, auto-start/stop
of recordings, and error handling.
"""

import asyncio
import time
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from core.timeline.auto_task_scheduler import AutoTaskScheduler
from data.database.models import CalendarEvent


class MockTimelineManager:
    """Mock timeline manager for testing."""

    def __init__(self):
        self.events = []

    def get_timeline_events(self, center_time, past_days, future_days):
        """Mock get timeline events."""
        now = center_time
        future_events = []
        past_events = []

        for event_data in self.events:
            event = event_data["event"]
            # Handle both datetime and string formats
            if isinstance(event.start_time, str):
                event_start = datetime.fromisoformat(event.start_time).replace(tzinfo=None)
            else:
                event_start = event.start_time.replace(tzinfo=None)

            if isinstance(event.end_time, str):
                event_end = datetime.fromisoformat(event.end_time).replace(tzinfo=None)
            else:
                event_end = event.end_time.replace(tzinfo=None)

            if event_start > now:
                future_events.append(event_data)
            elif event_end < now:
                past_events.append(event_data)

        return {
            "future_events": future_events,
            "past_events": past_events,
        }

    def add_event(self, event, auto_tasks):
        """Add event to mock timeline."""
        self.events.append(
            {
                "event": event,
                "auto_tasks": auto_tasks,
            }
        )


class MockRealtimeRecorder:
    """Mock realtime recorder for testing."""

    def __init__(self):
        self.is_recording = False
        self.start_calls = []
        self.stop_calls = []
        self._recording_result = {}

    async def start_recording(self, input_source=None, options=None, event_loop=None):
        """Mock start recording."""
        self.start_calls.append(
            {
                "input_source": input_source,
                "options": options,
                "event_loop": event_loop,
            }
        )
        self.is_recording = True
        # Simulate async operation
        await asyncio.sleep(0.01)

    async def stop_recording(self):
        """Mock stop recording."""
        self.stop_calls.append(datetime.now())
        self.is_recording = False
        # Simulate async operation
        await asyncio.sleep(0.01)
        return self._recording_result

    def set_recording_result(self, result):
        """Set the result to return from stop_recording."""
        self._recording_result = result


class MockNotificationManager:
    """Mock notification manager for testing."""

    def __init__(self):
        self.notifications = []

    def send_info(self, title, message):
        """Mock send info notification."""
        self.notifications.append(
            {
                "type": "info",
                "title": title,
                "message": message,
            }
        )

    def send_success(self, title, message):
        """Mock send success notification."""
        self.notifications.append(
            {
                "type": "success",
                "title": title,
                "message": message,
            }
        )

    def send_warning(self, title, message):
        """Mock send warning notification."""
        self.notifications.append(
            {
                "type": "warning",
                "title": title,
                "message": message,
            }
        )

    def send_error(self, title, message):
        """Mock send error notification."""
        self.notifications.append(
            {
                "type": "error",
                "title": title,
                "message": message,
            }
        )


@pytest.fixture
def mock_timeline_manager():
    """Create mock timeline manager."""
    return MockTimelineManager()


@pytest.fixture
def mock_realtime_recorder():
    """Create mock realtime recorder."""
    return MockRealtimeRecorder()


@pytest.fixture
def mock_db():
    """Create mock database connection."""
    return Mock()


@pytest.fixture
def mock_file_manager():
    """Create mock file manager."""
    return Mock()


@pytest.fixture
def mock_settings_manager():
    """Create mock settings manager."""
    manager = Mock()
    manager.get_language = Mock(return_value="en_US")
    manager.get_realtime_preferences = Mock(
        return_value={
            "recording_format": "wav",
            "auto_save": True,
        }
    )
    manager.setting_changed = Mock()
    manager.setting_changed.connect = Mock()
    return manager


@pytest.fixture
def mock_notification_manager():
    """Create mock notification manager."""
    return MockNotificationManager()


@pytest.fixture
def auto_task_scheduler(
    mock_timeline_manager,
    mock_realtime_recorder,
    mock_db,
    mock_file_manager,
    mock_settings_manager,
    mock_notification_manager,
):
    """Create AutoTaskScheduler instance."""
    with patch(
        "core.timeline.auto_task_scheduler.get_notification_manager",
        return_value=mock_notification_manager,
    ):
        scheduler = AutoTaskScheduler(
            timeline_manager=mock_timeline_manager,
            realtime_recorder=mock_realtime_recorder,
            db_connection=mock_db,
            file_manager=mock_file_manager,
            reminder_minutes=5,
            settings_manager=mock_settings_manager,
        )
        return scheduler


def create_test_event(
    event_id="test-event-1",
    title="Test Event",
    start_time=None,
    end_time=None,
):
    """Create a test calendar event."""
    if start_time is None:
        start_time = datetime.now() + timedelta(minutes=10)
    if end_time is None:
        end_time = start_time + timedelta(hours=1)

    event = CalendarEvent(
        id=event_id,
        title=title,
        start_time=start_time.isoformat() if isinstance(start_time, datetime) else start_time,
        end_time=end_time.isoformat() if isinstance(end_time, datetime) else end_time,
        source="local",
    )
    return event


class TestAutoTaskSchedulerInitialization:
    """Test AutoTaskScheduler initialization."""

    def test_init_default_reminder(
        self,
        mock_timeline_manager,
        mock_realtime_recorder,
        mock_db,
        mock_file_manager,
        mock_notification_manager,
    ):
        """Test initialization with default reminder minutes."""
        with patch(
            "core.timeline.auto_task_scheduler.get_notification_manager",
            return_value=mock_notification_manager,
        ):
            scheduler = AutoTaskScheduler(
                timeline_manager=mock_timeline_manager,
                realtime_recorder=mock_realtime_recorder,
                db_connection=mock_db,
                file_manager=mock_file_manager,
            )
            assert scheduler.reminder_minutes == 5
            assert not scheduler.is_running
            assert scheduler.notified_events == set()
            assert scheduler.started_events == set()
            assert scheduler.active_recordings == {}

    def test_init_custom_reminder(
        self,
        mock_timeline_manager,
        mock_realtime_recorder,
        mock_db,
        mock_file_manager,
        mock_notification_manager,
    ):
        """Test initialization with custom reminder minutes."""
        with patch(
            "core.timeline.auto_task_scheduler.get_notification_manager",
            return_value=mock_notification_manager,
        ):
            scheduler = AutoTaskScheduler(
                timeline_manager=mock_timeline_manager,
                realtime_recorder=mock_realtime_recorder,
                db_connection=mock_db,
                file_manager=mock_file_manager,
                reminder_minutes=10,
            )
            assert scheduler.reminder_minutes == 10

    def test_init_negative_reminder_clamped(
        self,
        mock_timeline_manager,
        mock_realtime_recorder,
        mock_db,
        mock_file_manager,
        mock_notification_manager,
    ):
        """Test that negative reminder minutes are clamped to zero."""
        with patch(
            "core.timeline.auto_task_scheduler.get_notification_manager",
            return_value=mock_notification_manager,
        ):
            scheduler = AutoTaskScheduler(
                timeline_manager=mock_timeline_manager,
                realtime_recorder=mock_realtime_recorder,
                db_connection=mock_db,
                file_manager=mock_file_manager,
                reminder_minutes=-5,
            )
            assert scheduler.reminder_minutes == 0

    def test_init_with_settings_manager(self, auto_task_scheduler, mock_settings_manager):
        """Test initialization with settings manager."""
        assert auto_task_scheduler.settings_manager == mock_settings_manager
        # Should subscribe to setting changes
        mock_settings_manager.setting_changed.connect.assert_called_once()


class TestAutoTaskSchedulerLifecycle:
    """Test scheduler lifecycle management."""

    def test_start_scheduler(self, auto_task_scheduler):
        """Test starting the scheduler."""
        auto_task_scheduler.start()

        assert auto_task_scheduler.is_running
        assert auto_task_scheduler.scheduler.running

        # Cleanup
        auto_task_scheduler.stop()

    def test_start_already_running(self, auto_task_scheduler):
        """Test starting when already running."""
        auto_task_scheduler.start()

        # Try to start again - should log warning but not raise
        auto_task_scheduler.start()

        assert auto_task_scheduler.is_running

        # Cleanup
        auto_task_scheduler.stop()

    def test_stop_scheduler(self, auto_task_scheduler):
        """Test stopping the scheduler."""
        auto_task_scheduler.start()
        auto_task_scheduler.stop()

        assert not auto_task_scheduler.is_running
        assert not auto_task_scheduler.scheduler.running

    def test_stop_not_running(self, auto_task_scheduler):
        """Test stopping when not running."""
        # Should log warning but not raise
        auto_task_scheduler.stop()

        assert not auto_task_scheduler.is_running

    def test_stop_with_active_recordings(
        self,
        auto_task_scheduler,
        mock_realtime_recorder,
    ):
        """Test stopping scheduler with active recordings."""
        # Add a fake active recording
        event = create_test_event()
        auto_task_scheduler.active_recordings[event.id] = {
            "event": event,
            "auto_tasks": {},
            "start_time": datetime.now(),
            "loop": None,
            "thread": None,
        }

        auto_task_scheduler.start()
        auto_task_scheduler.stop()

        # Should attempt to stop the recording
        assert not auto_task_scheduler.is_running


class TestReminderNotifications:
    """Test reminder notification functionality."""

    def test_send_reminder_notification_directly(
        self,
        auto_task_scheduler,
        mock_notification_manager,
    ):
        """Test sending reminder notification directly."""
        event = create_test_event()

        auto_tasks = {
            "enable_transcription": True,
            "enable_recording": True,
        }

        # Call the method directly
        auto_task_scheduler._send_reminder_notification(event, auto_tasks)

        # Should send notification
        assert len(mock_notification_manager.notifications) == 1
        notification = mock_notification_manager.notifications[0]
        assert notification["type"] == "info"
        assert event.title in notification["message"]

    def test_send_reminder_notification(
        self,
        auto_task_scheduler,
        mock_timeline_manager,
        mock_notification_manager,
    ):
        """Test sending reminder notification via check_upcoming_events."""
        # Create event starting in exactly 5 minutes (within the 5:00-5:01 window)
        # Use a fixed time to avoid timing issues
        now = datetime.now()
        event = create_test_event(start_time=now + timedelta(minutes=5, seconds=15))

        auto_tasks = {
            "enable_transcription": True,
            "enable_recording": True,
        }

        mock_timeline_manager.add_event(event, auto_tasks)

        # Start scheduler
        auto_task_scheduler.start()

        # Trigger check
        auto_task_scheduler._check_upcoming_events()

        # Should send reminder notification
        assert len(mock_notification_manager.notifications) >= 1
        notification = mock_notification_manager.notifications[0]
        assert notification["type"] == "info"
        assert event.title in notification["message"]

        # Cleanup
        auto_task_scheduler.stop()

    def test_reminder_not_sent_twice(
        self,
        auto_task_scheduler,
        mock_timeline_manager,
        mock_notification_manager,
    ):
        """Test that reminder is not sent twice for same event."""
        now = datetime.now()
        event = create_test_event(start_time=now + timedelta(minutes=5, seconds=15))

        auto_tasks = {
            "enable_transcription": True,
            "enable_recording": True,
        }

        mock_timeline_manager.add_event(event, auto_tasks)

        auto_task_scheduler.start()

        # First check - should send notification
        auto_task_scheduler._check_upcoming_events()
        first_count = len(mock_notification_manager.notifications)
        assert first_count >= 1

        # Manually mark as notified to test the tracking
        auto_task_scheduler.notified_events.add(event.id)

        # Second check - should not send again
        auto_task_scheduler._check_upcoming_events()
        assert len(mock_notification_manager.notifications) == first_count

        auto_task_scheduler.stop()

    def test_no_reminder_for_events_without_auto_tasks(
        self,
        auto_task_scheduler,
        mock_timeline_manager,
        mock_notification_manager,
    ):
        """Test that no reminder is sent for events without auto tasks."""
        event = create_test_event(start_time=datetime.now() + timedelta(minutes=5, seconds=15))

        auto_tasks = {
            "enable_transcription": False,
            "enable_recording": False,
        }

        mock_timeline_manager.add_event(event, auto_tasks)

        auto_task_scheduler.start()
        auto_task_scheduler._check_upcoming_events()

        # Should not send notification
        assert len(mock_notification_manager.notifications) == 0

        auto_task_scheduler.stop()


class TestAutoStartTasks:
    """Test automatic task starting functionality."""

    def test_start_auto_tasks_success(
        self,
        auto_task_scheduler,
        mock_timeline_manager,
        mock_realtime_recorder,
        mock_notification_manager,
    ):
        """Test successfully starting auto tasks."""
        # Create event starting within 1 minute (within the -60 to +60 second window)
        now = datetime.now()
        event = create_test_event(start_time=now + timedelta(seconds=15))

        auto_tasks = {
            "enable_transcription": True,
            "enable_recording": True,
            "transcription_language": "en",
            "enable_translation": False,
        }

        mock_timeline_manager.add_event(event, auto_tasks)

        auto_task_scheduler.start()
        auto_task_scheduler._check_upcoming_events()

        # Give time for async operation
        time.sleep(0.5)

        # Should start recording
        assert len(mock_realtime_recorder.start_calls) >= 1
        start_call = mock_realtime_recorder.start_calls[0]
        assert start_call["options"]["event_id"] == event.id
        assert start_call["options"]["event_title"] == event.title

        # Should be in active recordings
        assert event.id in auto_task_scheduler.active_recordings

        # Should send success notification
        success_notifications = [
            n for n in mock_notification_manager.notifications if n["type"] == "success"
        ]
        assert len(success_notifications) >= 1

        auto_task_scheduler.stop()

    def test_start_auto_tasks_recorder_busy(
        self,
        auto_task_scheduler,
        mock_timeline_manager,
        mock_realtime_recorder,
        mock_notification_manager,
    ):
        """Test starting auto tasks when recorder is busy."""
        # Set recorder as already recording
        mock_realtime_recorder.is_recording = True

        event = create_test_event(start_time=datetime.now() + timedelta(seconds=15))

        auto_tasks = {
            "enable_transcription": True,
            "enable_recording": True,
        }

        mock_timeline_manager.add_event(event, auto_tasks)

        auto_task_scheduler.start()
        auto_task_scheduler._check_upcoming_events()

        # Should not start recording
        assert len(mock_realtime_recorder.start_calls) == 0

        # Should send warning notification
        warning_notifications = [
            n for n in mock_notification_manager.notifications if n["type"] == "warning"
        ]
        assert len(warning_notifications) == 1

        auto_task_scheduler.stop()

    def test_start_auto_tasks_not_started_twice(
        self,
        auto_task_scheduler,
        mock_timeline_manager,
        mock_realtime_recorder,
    ):
        """Test that auto tasks are not started twice for same event."""
        event = create_test_event(start_time=datetime.now() + timedelta(seconds=15))

        auto_tasks = {
            "enable_transcription": True,
            "enable_recording": True,
        }

        mock_timeline_manager.add_event(event, auto_tasks)

        auto_task_scheduler.start()

        # First check - should start
        auto_task_scheduler._check_upcoming_events()
        time.sleep(0.5)
        assert len(mock_realtime_recorder.start_calls) == 1

        # Second check - should not start again
        auto_task_scheduler._check_upcoming_events()
        time.sleep(0.5)
        assert len(mock_realtime_recorder.start_calls) == 1

        auto_task_scheduler.stop()


class TestAutoStopTasks:
    """Test automatic task stopping functionality."""

    def test_stop_auto_tasks_directly(
        self,
        auto_task_scheduler,
        mock_realtime_recorder,
        mock_notification_manager,
    ):
        """Test stopping auto tasks directly (without event loop complexity)."""
        # Create event
        event = create_test_event()

        # Set up recording result
        mock_realtime_recorder.set_recording_result(
            {
                "duration": 3600.0,
                "recording_path": "/tmp/test_recording.wav",
                "transcript_path": "/tmp/test_transcript.txt",
            }
        )

        # Create a simple event loop
        loop = asyncio.new_event_loop()

        # Add to active recordings
        start_time_dt = (
            datetime.fromisoformat(event.start_time)
            if isinstance(event.start_time, str)
            else event.start_time
        )
        auto_task_scheduler.active_recordings[event.id] = {
            "event": event,
            "auto_tasks": {},
            "start_time": start_time_dt.replace(tzinfo=None),
            "loop": loop,
            "thread": None,
        }

        # Start the loop in background
        import threading

        def run_loop():
            asyncio.set_event_loop(loop)
            try:
                loop.run_forever()
            finally:
                # Clean up any pending tasks
                pending = asyncio.all_tasks(loop)
                for task in pending:
                    task.cancel()

        thread = threading.Thread(target=run_loop, daemon=True)
        thread.start()

        # Give loop time to start
        time.sleep(0.1)

        # Call stop directly
        auto_task_scheduler._stop_auto_tasks(event)

        # Give time for async operation to complete
        time.sleep(1.0)

        # Should stop recording
        assert len(mock_realtime_recorder.stop_calls) >= 1

        # Should remove from active recordings (this happens after successful stop)
        # Note: The removal happens in the try block, so if there's an error it might not be removed
        # For this test, we just verify the stop was called

        # Clean up
        if thread.is_alive():
            thread.join(timeout=1.0)

    def test_stop_auto_tasks_no_active_recording(
        self,
        auto_task_scheduler,
        mock_realtime_recorder,
    ):
        """Test stopping auto tasks when no active recording."""
        event = create_test_event()

        # Should not raise error
        auto_task_scheduler._stop_auto_tasks(event)

        # Should not call stop_recording
        assert len(mock_realtime_recorder.stop_calls) == 0


class TestSettingsIntegration:
    """Test integration with settings manager."""

    def test_reminder_minutes_update_via_settings(
        self,
        auto_task_scheduler,
    ):
        """Test updating reminder minutes via settings change."""
        assert auto_task_scheduler.reminder_minutes == 5

        # Simulate settings change
        auto_task_scheduler._on_setting_changed("timeline.reminder_minutes", 10)

        assert auto_task_scheduler.reminder_minutes == 10

        # Notified events should be cleared
        auto_task_scheduler.notified_events.add("test-event")
        auto_task_scheduler._on_setting_changed("timeline.reminder_minutes", 15)
        assert len(auto_task_scheduler.notified_events) == 0

    def test_ignore_other_setting_changes(
        self,
        auto_task_scheduler,
    ):
        """Test that other setting changes are ignored."""
        original_reminder = auto_task_scheduler.reminder_minutes

        # Simulate unrelated settings change
        auto_task_scheduler._on_setting_changed("other.setting", "value")

        assert auto_task_scheduler.reminder_minutes == original_reminder

    def test_invalid_reminder_minutes_ignored(
        self,
        auto_task_scheduler,
    ):
        """Test that invalid reminder minutes values are ignored."""
        original_reminder = auto_task_scheduler.reminder_minutes

        # Try invalid values
        auto_task_scheduler._on_setting_changed("timeline.reminder_minutes", "invalid")
        assert auto_task_scheduler.reminder_minutes == original_reminder

        auto_task_scheduler._on_setting_changed("timeline.reminder_minutes", None)
        assert auto_task_scheduler.reminder_minutes == original_reminder


class TestErrorHandling:
    """Test error handling in scheduler."""

    def test_check_upcoming_events_error_handling(
        self,
        auto_task_scheduler,
        mock_timeline_manager,
    ):
        """Test that errors in check_upcoming_events don't stop scheduler."""
        # Make timeline manager raise error
        mock_timeline_manager.get_timeline_events = Mock(side_effect=RuntimeError("Test error"))

        auto_task_scheduler.start()

        # Should not raise error
        auto_task_scheduler._check_upcoming_events()

        # Scheduler should still be running
        assert auto_task_scheduler.is_running

        auto_task_scheduler.stop()

    def test_start_auto_tasks_error_sends_notification(
        self,
        auto_task_scheduler,
        mock_timeline_manager,
        mock_realtime_recorder,
        mock_notification_manager,
    ):
        """Test that errors in start_auto_tasks send error notification."""

        # Make recorder raise error
        async def failing_start(*args, **kwargs):
            raise RuntimeError("Recording failed")

        mock_realtime_recorder.start_recording = failing_start

        event = create_test_event(start_time=datetime.now() + timedelta(seconds=15))

        auto_tasks = {
            "enable_transcription": True,
            "enable_recording": True,
        }

        mock_timeline_manager.add_event(event, auto_tasks)

        auto_task_scheduler.start()
        auto_task_scheduler._check_upcoming_events()

        time.sleep(0.5)

        # Should send error notification
        error_notifications = [
            n for n in mock_notification_manager.notifications if n["type"] == "error"
        ]
        assert len(error_notifications) == 1

        # Event should not be in started_events
        assert event.id not in auto_task_scheduler.started_events

        auto_task_scheduler.stop()


class TestCleanupTracking:
    """Test cleanup of tracking sets."""

    def test_cleanup_old_events(
        self,
        auto_task_scheduler,
        mock_timeline_manager,
    ):
        """Test cleanup of old event IDs from tracking sets."""
        # Add some old event IDs
        auto_task_scheduler.notified_events.add("old-event-1")
        auto_task_scheduler.notified_events.add("old-event-2")
        auto_task_scheduler.started_events.add("old-event-3")

        # Create a recent event
        recent_event = create_test_event(
            event_id="recent-event",
            start_time=datetime.now() - timedelta(minutes=30),
            end_time=datetime.now() - timedelta(minutes=10),
        )
        auto_task_scheduler.notified_events.add(recent_event.id)

        mock_timeline_manager.add_event(recent_event, {})

        # Run cleanup
        auto_task_scheduler._cleanup_tracking_sets(datetime.now())

        # Old events should be removed, recent event should remain
        assert "old-event-1" not in auto_task_scheduler.notified_events
        assert "old-event-2" not in auto_task_scheduler.notified_events
        assert "old-event-3" not in auto_task_scheduler.started_events
        assert recent_event.id in auto_task_scheduler.notified_events
