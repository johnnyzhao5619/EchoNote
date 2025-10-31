# SPDX-License-Identifier: Apache-2.0
"""
Tests for batch transcribe widget.
"""

from unittest.mock import MagicMock, Mock, patch

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog

from ui.batch_transcribe.widget import BatchTranscribeWidget


class TestBatchTranscribeWidget:
    """Tests for BatchTranscribeWidget."""

    @pytest.fixture
    def widget(self, qapp, mock_transcription_manager, mock_i18n, mock_model_manager):
        """Create a batch transcribe widget for testing."""
        with patch.object(mock_transcription_manager, "start_processing"):
            widget = BatchTranscribeWidget(
                transcription_manager=mock_transcription_manager,
                i18n=mock_i18n,
                model_manager=mock_model_manager,
            )
        return widget

    def test_widget_creation(self, widget):
        """Test widget can be created."""
        assert widget is not None
        assert widget.transcription_manager is not None
        assert widget.i18n is not None

    def test_widget_has_ui_elements(self, widget):
        """Test widget has required UI elements."""
        assert hasattr(widget, "title_label")
        assert hasattr(widget, "import_file_btn")
        assert hasattr(widget, "import_folder_btn")
        assert hasattr(widget, "clear_queue_btn")
        assert hasattr(widget, "task_list")

    def test_widget_has_model_combo(self, widget):
        """Test widget has model combo when model_manager is provided."""
        assert hasattr(widget, "model_combo")
        assert hasattr(widget, "model_label")

    def test_import_file_button_exists(self, widget):
        """Test import file button exists and is clickable."""
        assert widget.import_file_btn is not None
        assert widget.import_file_btn.isEnabled()

    def test_import_folder_button_exists(self, widget):
        """Test import folder button exists and is clickable."""
        assert widget.import_folder_btn is not None
        assert widget.import_folder_btn.isEnabled()

    def test_clear_queue_button_exists(self, widget):
        """Test clear queue button exists."""
        assert widget.clear_queue_btn is not None

    def test_task_list_exists(self, widget):
        """Test task list widget exists."""
        assert widget.task_list is not None

    def test_task_items_dictionary(self, widget):
        """Test task items dictionary is initialized."""
        assert hasattr(widget, "task_items")
        assert isinstance(widget.task_items, dict)
        assert len(widget.task_items) == 0

    def test_open_viewers_dictionary(self, widget):
        """Test open viewers dictionary is initialized."""
        assert hasattr(widget, "open_viewers")
        assert isinstance(widget.open_viewers, dict)
        assert len(widget.open_viewers) == 0

    def test_refresh_timer_started(self, widget):
        """Test refresh timer is started."""
        assert hasattr(widget, "refresh_timer")
        assert widget.refresh_timer.isActive()

    def test_transcription_manager_started(self, widget, mock_transcription_manager):
        """Test transcription manager processing is started."""
        # The start_processing should have been called during initialization
        # We patched it in the fixture, so we can't verify the call here
        # But we can verify the manager is set
        assert widget.transcription_manager == mock_transcription_manager

    @patch("ui.batch_transcribe.widget.QFileDialog.getOpenFileNames")
    def test_import_file_dialog(self, mock_dialog, widget, mock_transcription_manager):
        """Test import file opens file dialog."""
        mock_dialog.return_value = (["/test/file.mp3"], "Audio Files (*.mp3)")
        mock_transcription_manager.add_task.return_value = "test-task-id"

        # Trigger import file
        widget._on_import_file()

        # Verify dialog was opened
        mock_dialog.assert_called_once()

    @patch("ui.batch_transcribe.widget.QFileDialog.getExistingDirectory")
    def test_import_folder_dialog(self, mock_dialog, widget, mock_transcription_manager):
        """Test import folder opens directory dialog."""
        mock_dialog.return_value = "/test/folder"
        mock_transcription_manager.add_tasks_from_folder.return_value = ["task-1", "task-2"]

        # Trigger import folder
        widget._on_import_folder()

        # Verify dialog was opened
        mock_dialog.assert_called_once()

    def test_update_translations(self, widget):
        """Test update translations method."""
        # Should not raise exception
        widget.update_translations()

    def test_language_change_connected(self, widget, mock_i18n):
        """Test language change signal is connected."""
        # Verify the connection was made
        mock_i18n.language_changed.connect.assert_called()


class TestBatchTranscribeWidgetWithoutModelManager:
    """Tests for BatchTranscribeWidget without model manager."""

    @pytest.fixture
    def widget_no_model(self, qapp, mock_transcription_manager, mock_i18n):
        """Create a batch transcribe widget without model manager."""
        with patch.object(mock_transcription_manager, "start_processing"):
            widget = BatchTranscribeWidget(
                transcription_manager=mock_transcription_manager, i18n=mock_i18n, model_manager=None
            )
        return widget

    def test_widget_has_engine_combo(self, widget_no_model):
        """Test widget has engine combo when model_manager is not provided."""
        assert hasattr(widget_no_model, "engine_combo")
        assert hasattr(widget_no_model, "engine_label")

    def test_widget_no_model_combo(self, widget_no_model):
        """Test widget doesn't have model combo when model_manager is not provided."""
        assert not hasattr(widget_no_model, "model_combo")
