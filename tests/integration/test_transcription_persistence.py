# SPDX-License-Identifier: Apache-2.0
"""
Integration tests for TranscriptionManager.
"""

import tempfile
from pathlib import Path
from unittest.mock import Mock

import pytest

from core.transcription.manager import TranscriptionManager


class MockDatabaseConnection:
    """Minimal mock database for integration test."""

    def __init__(self):
        self.tasks = {}
        self.execute_calls = []

    def execute(self, query, params=None, commit=False):
        self.execute_calls.append((query, params, commit))
        # Handle simple INSERT
        if "INSERT OR REPLACE" in query and params:
            self.tasks[params[0]] = {"id": params[0], "status": params[5]}
        return []

    def execute_many(self, query, params_list):
        for params in params_list:
            self.execute(query, params, commit=True)


class MockSpeechEngine:
    """Minimal mock engine."""

    def get_name(self):
        return "mock-engine"

    # We won't actually call transcribe because we only test the add_task flow here
    # which triggers notification synchronously


class TestTranscriptionPersistence:
    """Integration tests for state persistence."""

    @pytest.fixture
    def manager(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config = {
                "default_save_path": str(tmpdir),
                "max_concurrent_tasks": 2,
            }
            db = MockDatabaseConnection()
            engine = MockSpeechEngine()
            return TranscriptionManager(db, engine, config)

    def test_manager_remains_running_after_notification(self, manager):
        """
        Verify that triggering a notification (via add_task) does NOT reset
        the manager's running state. This prevents regression of the bug
        where _notify_listeners was resetting self._running and self._thread.
        """
        # 1. Start processing (creates thread)
        manager.start_processing()
        assert manager._running is True
        assert manager._thread is not None
        assert manager._thread.is_alive()

        initial_thread = manager._thread

        # 2. Add a task. This calls _notify_listeners("task_added", ...) synchronously.
        #    If the bug exists, this will reset _running to False and _thread to None.
        with tempfile.NamedTemporaryFile(suffix=".mp3") as f:
            manager.add_task(f.name)

        # 3. Verify state is maintained
        assert manager._running is True, "Manager should still be running after notification"
        assert manager._thread is not None, "Thread reference should exist"
        assert manager._thread is initial_thread, "Thread should be the same instance"
        assert manager._thread.is_alive(), "Thread should still be alive"

        # Cleanup
        manager.stop_processing()
        assert manager._running is False
