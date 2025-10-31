# SPDX-License-Identifier: Apache-2.0
"""
Unit tests for TranscriptionManager.

Tests transcription task management, lifecycle, and coordination with
speech engines and database.
"""

import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from core.transcription.manager import TranscriptionManager, TaskNotFoundError
from data.database.models import TranscriptionTask


class MockDatabaseConnection:
    """Mock database connection for testing."""

    def __init__(self):
        self.tasks = {}
        self.execute_calls = []

    def execute(self, query, params=None, commit=False):
        """Mock execute method."""
        self.execute_calls.append((query, params, commit))

        # Handle SELECT queries
        if query.strip().upper().startswith("SELECT"):
            # Handle COUNT queries
            if "COUNT(*)" in query.upper():
                if "WHERE status" in query and params:
                    status = params[0]
                    count = sum(1 for t in self.tasks.values() if t.get("status") == status)
                    return [{"count": count}]
                return [{"count": len(self.tasks)}]
            
            if "WHERE id = ?" in query and params:
                task_id = params[0]
                if task_id in self.tasks:
                    return [self.tasks[task_id]]
                return []
            elif "WHERE status" in query and params:
                status = params[0]
                return [t for t in self.tasks.values() if t.get("status") == status]
            else:
                return list(self.tasks.values())

        # Handle INSERT/UPDATE
        if "INSERT OR REPLACE" in query and params:
            task_id = params[0]
            self.tasks[task_id] = {
                "id": params[0],
                "file_path": params[1],
                "file_name": params[2],
                "file_size": params[3],
                "audio_duration": params[4],
                "status": params[5],
                "progress": params[6],
                "language": params[7],
                "engine": params[8],
                "output_format": params[9],
                "output_path": params[10],
                "error_message": params[11],
                "created_at": params[12],
                "started_at": params[13],
                "completed_at": params[14],
            }

        # Handle DELETE
        if "DELETE" in query and params:
            task_id = params[0]
            self.tasks.pop(task_id, None)

        return []

    def execute_many(self, query, params_list):
        """Mock execute_many method."""
        for params in params_list:
            self.execute(query, params, commit=True)


class MockSpeechEngine:
    """Mock speech engine for testing."""

    def __init__(self):
        self.transcribe_calls = []

    def get_name(self):
        """Get engine name."""
        return "mock-engine"

    async def transcribe_file(self, file_path, language=None, progress_callback=None):
        """Mock transcribe_file method."""
        self.transcribe_calls.append((file_path, language))

        # Simulate progress callbacks
        if progress_callback:
            for progress in [10, 30, 50, 70, 90, 100]:
                progress_callback(progress)
                await asyncio.sleep(0.01)

        # Return mock result
        return {
            "segments": [
                {"start": 0.0, "end": 2.0, "text": "Hello world"},
                {"start": 2.0, "end": 4.0, "text": "This is a test"},
            ],
            "duration": 4.0,
        }


class TestTranscriptionManager:
    """Test suite for TranscriptionManager."""

    @pytest.fixture
    def temp_audio_file(self):
        """Create a temporary audio file for testing."""
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(b"fake audio data")
            temp_path = Path(f.name)

        yield temp_path

        # Cleanup
        if temp_path.exists():
            temp_path.unlink()

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def mock_db(self):
        """Create mock database connection."""
        return MockDatabaseConnection()

    @pytest.fixture
    def mock_engine(self):
        """Create mock speech engine."""
        return MockSpeechEngine()

    @pytest.fixture
    def manager(self, mock_db, mock_engine, temp_dir):
        """Create TranscriptionManager instance."""
        config = {
            "default_save_path": str(temp_dir),
            "default_output_format": "txt",
            "max_concurrent_tasks": 2,
        }
        return TranscriptionManager(mock_db, mock_engine, config)

    # Initialization Tests
    def test_init_with_config(self, mock_db, mock_engine, temp_dir):
        """Test TranscriptionManager initialization with config."""
        config = {
            "default_save_path": str(temp_dir),
            "default_output_format": "srt",
            "max_concurrent_tasks": 3,
        }

        manager = TranscriptionManager(mock_db, mock_engine, config)

        assert manager.db == mock_db
        assert manager.speech_engine == mock_engine
        assert manager._default_output_format == "srt"
        assert manager.task_queue.max_concurrent == 3

    def test_init_without_config(self, mock_db, mock_engine):
        """Test TranscriptionManager initialization without config."""
        manager = TranscriptionManager(mock_db, mock_engine)

        assert manager.db == mock_db
        assert manager.speech_engine == mock_engine
        assert manager._default_output_format == "txt"

    # Task Addition Tests
    def test_add_task_success(self, manager, temp_audio_file):
        """Test adding a transcription task successfully."""
        task_id = manager.add_task(str(temp_audio_file))

        assert task_id is not None
        assert len(task_id) > 0

        # Verify task was saved to database
        assert task_id in manager.db.tasks
        task_data = manager.db.tasks[task_id]
        assert task_data["status"] == "pending"
        assert task_data["file_name"] == temp_audio_file.name

    def test_add_task_with_options(self, manager, temp_audio_file):
        """Test adding a task with custom options."""
        options = {
            "language": "en",
            "output_format": "srt",
        }

        task_id = manager.add_task(str(temp_audio_file), options)

        task_data = manager.db.tasks[task_id]
        assert task_data["language"] == "en"
        assert task_data["output_format"] == "srt"

    def test_add_task_file_not_found(self, manager):
        """Test adding a task with non-existent file."""
        with pytest.raises(FileNotFoundError):
            manager.add_task("/nonexistent/file.mp3")

    def test_add_task_unsupported_format(self, manager, temp_dir):
        """Test adding a task with unsupported file format."""
        unsupported_file = temp_dir / "test.txt"
        unsupported_file.write_text("not audio")

        with pytest.raises(ValueError, match="Unsupported file format"):
            manager.add_task(str(unsupported_file))

    def test_add_tasks_from_folder(self, manager, temp_dir):
        """Test adding multiple tasks from a folder."""
        # Create test audio files
        (temp_dir / "audio1.mp3").write_bytes(b"fake audio 1")
        (temp_dir / "audio2.wav").write_bytes(b"fake audio 2")
        (temp_dir / "not_audio.txt").write_text("not audio")

        task_ids = manager.add_tasks_from_folder(str(temp_dir))

        # Should add 2 audio files, skip the text file
        assert len(task_ids) == 2

    def test_add_tasks_from_folder_not_directory(self, manager, temp_audio_file):
        """Test adding tasks from a non-directory path."""
        with pytest.raises(NotADirectoryError):
            manager.add_tasks_from_folder(str(temp_audio_file))

    # Status Query Tests
    def test_get_task_status_existing(self, manager, temp_audio_file):
        """Test getting status of an existing task."""
        task_id = manager.add_task(str(temp_audio_file))

        status = manager.get_task_status(task_id)

        assert status is not None
        assert status["id"] == task_id
        assert status["status"] == "pending"
        assert status["file_name"] == temp_audio_file.name

    def test_get_task_status_nonexistent(self, manager):
        """Test getting status of a nonexistent task."""
        status = manager.get_task_status("nonexistent-id")

        assert status is None

    def test_get_all_tasks(self, manager, temp_dir):
        """Test getting all tasks."""
        # Create test files
        file1 = temp_dir / "audio1.mp3"
        file2 = temp_dir / "audio2.mp3"
        file1.write_bytes(b"fake audio 1")
        file2.write_bytes(b"fake audio 2")

        manager.add_task(str(file1))
        manager.add_task(str(file2))

        all_tasks = manager.get_all_tasks()

        assert len(all_tasks) == 2

    def test_get_all_tasks_filtered_by_status(self, manager, temp_dir):
        """Test getting tasks filtered by status."""
        file1 = temp_dir / "audio1.mp3"
        file1.write_bytes(b"fake audio")

        task_id = manager.add_task(str(file1))

        # Manually update status
        manager.db.tasks[task_id]["status"] = "completed"

        completed_tasks = manager.get_all_tasks(status="completed")
        pending_tasks = manager.get_all_tasks(status="pending")

        assert len(completed_tasks) == 1
        assert len(pending_tasks) == 0

    # Progress Callback Tests
    def test_register_progress_callback(self, manager, temp_audio_file):
        """Test registering a progress callback."""
        task_id = manager.add_task(str(temp_audio_file))

        callback = Mock()
        manager.register_progress_callback(task_id, callback)

        assert task_id in manager.progress_callbacks
        assert manager.progress_callbacks[task_id] == callback

    def test_unregister_progress_callback(self, manager, temp_audio_file):
        """Test unregistering a progress callback."""
        task_id = manager.add_task(str(temp_audio_file))

        callback = Mock()
        manager.register_progress_callback(task_id, callback)
        manager.unregister_progress_callback(task_id)

        assert task_id not in manager.progress_callbacks

    # Task Deletion Tests
    def test_delete_task(self, manager, temp_audio_file, temp_dir):
        """Test deleting a task."""
        task_id = manager.add_task(str(temp_audio_file))

        # Create fake internal format file
        internal_path = temp_dir / f"{task_id}.json"
        internal_path.write_text('{"segments": []}')

        with patch.object(manager, "_get_internal_format_path", return_value=str(internal_path)):
            result = manager.delete_task(task_id)

        assert result is True
        assert task_id not in manager.db.tasks

    def test_delete_nonexistent_task(self, manager):
        """Test deleting a nonexistent task."""
        result = manager.delete_task("nonexistent-id")

        assert result is False

    # Export Tests
    def test_export_result_txt(self, manager, temp_audio_file, temp_dir):
        """Test exporting transcription result to TXT format."""
        task_id = manager.add_task(str(temp_audio_file))

        # Manually set task as completed
        manager.db.tasks[task_id]["status"] = "completed"

        # Create fake internal format file
        internal_data = {
            "segments": [
                {"start": 0.0, "end": 2.0, "text": "Hello world"},
                {"start": 2.0, "end": 4.0, "text": "This is a test"},
            ]
        }
        internal_path = temp_dir / f"{task_id}.json"
        internal_path.write_text(json.dumps(internal_data))

        output_path = temp_dir / "output.txt"

        with patch.object(manager, "_get_internal_format_path", return_value=str(internal_path)):
            result_path = manager.export_result(task_id, "txt", str(output_path))

        assert Path(result_path).exists()
        content = Path(result_path).read_text()
        assert "Hello world" in content
        assert "This is a test" in content

    def test_export_result_task_not_found(self, manager):
        """Test exporting result for nonexistent task."""
        with pytest.raises(ValueError, match="not found"):
            manager.export_result("nonexistent-id", "txt", "/tmp/output.txt")

    def test_export_result_task_not_completed(self, manager, temp_audio_file):
        """Test exporting result for incomplete task."""
        task_id = manager.add_task(str(temp_audio_file))

        with pytest.raises(ValueError, match="not completed"):
            manager.export_result(task_id, "txt", "/tmp/output.txt")

    # Lifecycle Tests
    def test_start_processing(self, manager):
        """Test starting task processing."""
        manager.start_processing()

        assert manager._running is True
        assert manager._thread is not None

        # Cleanup
        manager.stop_processing()

    def test_stop_processing(self, manager):
        """Test stopping task processing."""
        manager.start_processing()
        manager.stop_processing()

        assert manager._running is False

    def test_pause_and_resume_processing(self, manager):
        """Test pausing and resuming task processing."""
        import time
        
        manager.start_processing()
        time.sleep(0.1)  # Give time for thread to start

        manager.pause_processing()
        time.sleep(0.1)  # Give time for pause to take effect
        assert manager.is_paused() is True

        manager.resume_processing()
        time.sleep(0.1)  # Give time for resume to take effect
        assert manager.is_paused() is False

        # Cleanup
        manager.stop_processing()

    def test_has_running_tasks(self, manager, temp_audio_file):
        """Test checking for running tasks."""
        task_id = manager.add_task(str(temp_audio_file))

        # Manually set task as processing
        manager.db.tasks[task_id]["status"] = "processing"

        # Should have running tasks
        result = manager.has_running_tasks()
        assert result is True

    # Configuration Tests
    def test_update_max_concurrent(self, manager):
        """Test updating max concurrent tasks."""
        initial_max = manager.task_queue.max_concurrent

        manager.update_max_concurrent(4)

        assert manager.task_queue.max_concurrent == 4
        assert manager.task_queue.max_concurrent != initial_max

    def test_update_max_concurrent_invalid(self, manager):
        """Test updating max concurrent with invalid value."""
        initial_max = manager.task_queue.max_concurrent

        manager.update_max_concurrent(10)  # Out of range

        # Should not change
        assert manager.task_queue.max_concurrent == initial_max

    # Edge Cases
    def test_add_task_with_invalid_path_type(self, manager):
        """Test adding task with invalid path type."""
        with pytest.raises((FileNotFoundError, TypeError)):
            manager.add_task(None)

    def test_get_internal_format_path(self, manager):
        """Test getting internal format path."""
        task_id = "test-task-id"

        path = manager._get_internal_format_path(task_id)

        assert task_id in path
        assert path.endswith(".json")

    def test_reload_engine(self, manager):
        """Test reloading speech engine."""
        # Should not raise an error
        manager.reload_engine()

    def test_manager_with_i18n(self, mock_db, mock_engine):
        """Test manager with i18n support."""
        class MockI18n:
            def t(self, key, **kwargs):
                return f"translated_{key}"

        manager = TranscriptionManager(mock_db, mock_engine, i18n=MockI18n())

        assert manager._translator is not None
