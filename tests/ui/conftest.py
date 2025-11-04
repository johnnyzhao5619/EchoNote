# SPDX-License-Identifier: Apache-2.0
"""
Pytest fixtures for UI tests.
"""

import sys
from unittest.mock import MagicMock, Mock

import pytest
from PySide6.QtWidgets import QApplication

from utils.i18n import I18nQtManager


@pytest.fixture(scope="session")
def qapp():
    """Create QApplication instance for UI testing."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app


@pytest.fixture
def mock_i18n():
    """Create a mock I18nQtManager for testing."""
    i18n = Mock(spec=I18nQtManager)
    i18n.t = Mock(side_effect=lambda key, **kwargs: key)
    i18n.language_changed = Mock()
    i18n.language_changed.connect = Mock()
    return i18n


@pytest.fixture
def mock_transcription_manager():
    """Create a mock TranscriptionManager for testing."""
    manager = MagicMock()
    manager.add_task = Mock(return_value="test-task-id")
    manager.add_tasks_from_folder = Mock(return_value=["task-1", "task-2"])
    manager.start_processing = Mock()
    manager.pause_processing = Mock()
    manager.resume_processing = Mock()
    manager.cancel_task = Mock()
    manager.get_task_status = Mock(return_value={"status": "pending"})
    return manager


@pytest.fixture
def mock_realtime_recorder():
    """Create a mock RealtimeRecorder for testing."""
    from unittest.mock import PropertyMock

    recorder = MagicMock()
    recorder.start_recording = Mock()
    recorder.stop_recording = Mock()
    # Use PropertyMock to ensure is_recording returns a boolean
    type(recorder).is_recording = PropertyMock(return_value=False)
    recorder.add_marker = Mock()
    recorder.set_callbacks = Mock()
    return recorder


@pytest.fixture
def mock_audio_capture():
    """Create a mock AudioCapture for testing."""
    capture = MagicMock()
    capture.list_devices = Mock(
        return_value=[
            {"index": 0, "name": "Default Device", "channels": 2},
            {"index": 1, "name": "Test Device", "channels": 1},
        ]
    )
    capture.get_default_device = Mock(return_value=0)
    return capture


@pytest.fixture
def mock_settings_manager():
    """Create a mock SettingsManager for testing."""
    manager = MagicMock()
    manager.get = Mock(side_effect=lambda key, default=None: default)
    manager.set = Mock()
    manager.save = Mock()
    manager.get_all = Mock(return_value={})
    manager.get_all_settings = Mock(return_value={})
    manager.get_realtime_preferences = Mock(
        return_value={"recording_format": "wav", "auto_save": True}
    )
    manager.setting_changed = Mock()
    manager.setting_changed.connect = Mock()
    return manager


@pytest.fixture
def mock_model_manager():
    """Create a mock ModelManager for testing."""
    manager = MagicMock()
    manager.list_models = Mock(return_value=[])
    manager.download_model = Mock()
    manager.delete_model = Mock()
    return manager
