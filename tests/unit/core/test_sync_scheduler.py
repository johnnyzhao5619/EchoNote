# SPDX-License-Identifier: Apache-2.0
"""
Unit tests for SyncScheduler.

Tests automatic calendar synchronization scheduling, retry logic,
and error handling.
"""

import time
from datetime import datetime, timedelta
from unittest.mock import MagicMock, Mock, patch

import pytest

from core.calendar.sync_scheduler import SyncScheduler


class MockCalendarManager:
    """Mock calendar manager for testing."""

    def __init__(self):
        self.db = Mock()
        self.sync_calls = []
        self.sync_failures = {}

    def sync_external_calendar(self, provider):
        """Mock sync external calendar."""
        self.sync_calls.append(provider)

        # Simulate failure if configured
        if provider in self.sync_failures:
            raise RuntimeError(f"Sync failed for {provider}")


@pytest.fixture
def mock_calendar_manager():
    """Create mock calendar manager."""
    return MockCalendarManager()


@pytest.fixture
def sync_scheduler(mock_calendar_manager):
    """Create SyncScheduler instance."""
    return SyncScheduler(mock_calendar_manager, interval_minutes=15)


class TestSyncSchedulerInitialization:
    """Test SyncScheduler initialization."""

    def test_init_default_interval(self, mock_calendar_manager):
        """Test initialization with default interval."""
        scheduler = SyncScheduler(mock_calendar_manager)
        assert scheduler.calendar_manager == mock_calendar_manager
        assert scheduler.interval_minutes == 15
        assert not scheduler.is_running
        assert scheduler.retry_state == {}

    def test_init_custom_interval(self, mock_calendar_manager):
        """Test initialization with custom interval."""
        scheduler = SyncScheduler(mock_calendar_manager, interval_minutes=30)
        assert scheduler.interval_minutes == 30

    def test_init_creates_scheduler(self, sync_scheduler):
        """Test that scheduler is created."""
        assert sync_scheduler.scheduler is not None


class TestSyncSchedulerLifecycle:
    """Test scheduler lifecycle management."""

    def test_start_scheduler(self, sync_scheduler):
        """Test starting the scheduler."""
        sync_scheduler.start()

        assert sync_scheduler.is_running

        # Cleanup
        sync_scheduler.stop()

    def test_start_already_running(self, sync_scheduler):
        """Test starting when already running."""
        sync_scheduler.start()

        # Try to start again
        sync_scheduler.start()  # Should log warning but not raise

        assert sync_scheduler.is_running

        # Cleanup
        sync_scheduler.stop()

    def test_stop_scheduler(self, sync_scheduler):
        """Test stopping the scheduler."""
        sync_scheduler.start()
        sync_scheduler.stop()

        assert not sync_scheduler.is_running

    def test_stop_not_running(self, sync_scheduler):
        """Test stopping when not running."""
        # Should log warning but not raise
        sync_scheduler.stop()

        assert not sync_scheduler.is_running


class TestSyncSchedulerManualSync:
    """Test manual sync triggering."""

    def test_sync_now(self, sync_scheduler):
        """Test triggering manual sync."""
        sync_scheduler.start()

        # Trigger manual sync
        sync_scheduler.sync_now()

        # Cleanup
        sync_scheduler.stop()

    def test_sync_now_not_running(self, sync_scheduler):
        """Test manual sync when scheduler not running."""
        # Should log warning but not raise
        sync_scheduler.sync_now()

class TestSyncSchedulerSyncAll:
    """Test sync all functionality."""

    def test_sync_all_no_active_syncs(self, sync_scheduler, mock_calendar_manager):
        """Test sync when no active syncs configured."""
        with patch("data.database.models.CalendarSyncStatus") as mock_status:
            mock_status.get_all_active.return_value = []

            sync_scheduler._sync_all()

            # Should not call sync
            assert len(mock_calendar_manager.sync_calls) == 0

    def test_sync_all_single_provider(self, sync_scheduler, mock_calendar_manager):
        """Test syncing single provider."""
        mock_sync_status = Mock()
        mock_sync_status.provider = "google"

        with patch("data.database.models.CalendarSyncStatus") as mock_status:
            mock_status.get_all_active.return_value = [mock_sync_status]

            sync_scheduler._sync_all()

            assert "google" in mock_calendar_manager.sync_calls

    def test_sync_all_multiple_providers(self, sync_scheduler, mock_calendar_manager):
        """Test syncing multiple providers."""
        mock_sync1 = Mock()
        mock_sync1.provider = "google"
        mock_sync2 = Mock()
        mock_sync2.provider = "outlook"

        with patch("data.database.models.CalendarSyncStatus") as mock_status:
            mock_status.get_all_active.return_value = [mock_sync1, mock_sync2]

            sync_scheduler._sync_all()

            assert "google" in mock_calendar_manager.sync_calls
            assert "outlook" in mock_calendar_manager.sync_calls

    def test_sync_all_with_failure(self, sync_scheduler, mock_calendar_manager):
        """Test sync with one provider failing."""
        mock_calendar_manager.sync_failures["google"] = True

        mock_sync1 = Mock()
        mock_sync1.provider = "google"
        mock_sync2 = Mock()
        mock_sync2.provider = "outlook"

        with patch("data.database.models.CalendarSyncStatus") as mock_status:
            mock_status.get_all_active.return_value = [mock_sync1, mock_sync2]

            sync_scheduler._sync_all()

            # Both should be attempted
            assert "google" in mock_calendar_manager.sync_calls
            assert "outlook" in mock_calendar_manager.sync_calls

            # Retry state should be set for failed provider
            assert "google" in sync_scheduler.retry_state


class TestSyncSchedulerRetryLogic:
    """Test retry logic with exponential backoff."""

    def test_handle_sync_failure_first_attempt(self, sync_scheduler):
        """Test handling first sync failure."""
        provider = "google"

        with patch.object(sync_scheduler.scheduler, "add_job"):
            sync_scheduler._handle_sync_failure(provider)

            assert provider in sync_scheduler.retry_state
            assert sync_scheduler.retry_state[provider]["attempts"] == 1

    def test_handle_sync_failure_multiple_attempts(self, sync_scheduler):
        """Test handling multiple sync failures."""
        provider = "google"

        with patch.object(sync_scheduler.scheduler, "add_job"):
            # First failure
            sync_scheduler._handle_sync_failure(provider)
            assert sync_scheduler.retry_state[provider]["attempts"] == 1

            # Second failure
            sync_scheduler._handle_sync_failure(provider)
            assert sync_scheduler.retry_state[provider]["attempts"] == 2

            # Third failure
            sync_scheduler._handle_sync_failure(provider)
            assert sync_scheduler.retry_state[provider]["attempts"] == 3

    def test_handle_sync_failure_max_attempts(self, sync_scheduler):
        """Test max retry attempts reached."""
        provider = "google"

        with patch.object(sync_scheduler.scheduler, "add_job"):
            # Simulate 3 failures
            for _ in range(3):
                sync_scheduler._handle_sync_failure(provider)

            # Fourth failure should reset retry state
            sync_scheduler._handle_sync_failure(provider)

            # Retry state should be cleared
            assert provider not in sync_scheduler.retry_state

    def test_retry_sync_success(self, sync_scheduler, mock_calendar_manager):
        """Test successful retry."""
        provider = "google"
        sync_scheduler.retry_state[provider] = {"attempts": 1, "last_attempt": time.time()}

        with patch.object(sync_scheduler.scheduler, "remove_job"):
            sync_scheduler._retry_sync(provider)

            # Should clear retry state on success
            assert provider not in sync_scheduler.retry_state
            assert provider in mock_calendar_manager.sync_calls

    def test_retry_sync_failure(self, sync_scheduler, mock_calendar_manager):
        """Test failed retry."""
        provider = "google"
        mock_calendar_manager.sync_failures["google"] = True
        sync_scheduler.retry_state[provider] = {"attempts": 1, "last_attempt": time.time()}

        with patch.object(sync_scheduler.scheduler, "add_job"):
            sync_scheduler._retry_sync(provider)

            # Should increment retry attempts
            assert sync_scheduler.retry_state[provider]["attempts"] == 2


class TestSyncSchedulerStatus:
    """Test status and query methods."""

    def test_get_next_sync_time_not_running(self, sync_scheduler):
        """Test getting next sync time when not running."""
        next_time = sync_scheduler.get_next_sync_time()
        assert next_time is None

    def test_get_next_sync_time_running(self, sync_scheduler):
        """Test getting next sync time when running."""
        sync_scheduler.start()

        next_time = sync_scheduler.get_next_sync_time()

        # Should return a time string or None
        assert next_time is None or isinstance(next_time, str)

        # Cleanup
        sync_scheduler.stop()

    def test_get_status(self, sync_scheduler):
        """Test getting scheduler status."""
        status = sync_scheduler.get_status()

        assert isinstance(status, dict)
        assert "is_running" in status
        assert "interval_minutes" in status

    def test_get_status_running(self, sync_scheduler):
        """Test status when running."""
        sync_scheduler.start()

        status = sync_scheduler.get_status()

        assert status["is_running"] is True
        assert status["interval_minutes"] == 15

        # Cleanup
        sync_scheduler.stop()


class TestSyncSchedulerIntegration:
    """Test integration scenarios."""

    def test_full_lifecycle(self, sync_scheduler):
        """Test complete start-sync-stop lifecycle."""
        # Start scheduler
        sync_scheduler.start()
        assert sync_scheduler.is_running

        # Trigger manual sync
        sync_scheduler.sync_now()

        # Get status
        status = sync_scheduler.get_status()
        assert status["is_running"]

        # Stop scheduler
        sync_scheduler.stop()
        assert not sync_scheduler.is_running

    def test_retry_clears_on_success(self, sync_scheduler, mock_calendar_manager):
        """Test that retry state clears after successful sync."""
        provider = "google"

        # Set up initial failure
        mock_calendar_manager.sync_failures["google"] = True
        mock_sync = Mock()
        mock_sync.provider = provider

        with patch("data.database.models.CalendarSyncStatus") as mock_status:
            mock_status.get_all_active.return_value = [mock_sync]

            # First sync fails
            sync_scheduler._sync_all()
            assert provider in sync_scheduler.retry_state

            # Remove failure condition
            del mock_calendar_manager.sync_failures["google"]

            # Second sync succeeds
            sync_scheduler._sync_all()
            assert provider not in sync_scheduler.retry_state
