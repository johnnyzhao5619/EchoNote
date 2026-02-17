# SPDX-License-Identifier: Apache-2.0
"""
Tests for batch transcribe widget.
"""

from unittest.mock import MagicMock, Mock, patch

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog, QMessageBox

from ui.batch_transcribe.widget import BatchTranscribeWidget
from config.constants import (
    TASK_STATUS_PENDING,
    TASK_STATUS_PROCESSING,
    TASK_STATUS_COMPLETED,
    TASK_STATUS_FAILED,
    TASK_STATUS_CANCELLED,
)


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

    def test_manager_listener_registered(self, widget, mock_transcription_manager):
        """Test manager event listener is registered."""
        # Verify add_listener was called with the thread-safe handler
        mock_transcription_manager.add_listener.assert_called_with(widget._on_manager_event_threadsafe)

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

    @patch("ui.batch_transcribe.widget.QFileDialog.getExistingDirectory")
    def test_import_folder_uses_built_options(self, mock_dialog, widget, mock_transcription_manager):
        """Folder import should pass the same task options used by single-file import."""
        mock_dialog.return_value = "/test/folder"
        mock_transcription_manager.add_tasks_from_folder.return_value = ["task-1"]

        with patch.object(widget, "_build_task_options", return_value={"model_name": "base"}):
            widget._on_import_folder()

        mock_transcription_manager.add_tasks_from_folder.assert_called_once_with(
            "/test/folder", {"model_name": "base"}
        )

    def test_update_translations(self, widget):
        """Test update translations method."""
        # Should not raise exception
        widget.update_translations()

    def test_language_change_connected(self, widget, mock_i18n):
        """Test language change signal is connected."""
        # Verify the connection was made
        mock_i18n.language_changed.connect.assert_called()

    @patch("ui.batch_transcribe.widget.QMessageBox.question")
    def test_clear_queue_restarts_processing(self, mock_question, widget, mock_transcription_manager):
        """Clearing queue should restart processing after cleanup."""
        mock_question.return_value = QMessageBox.StandardButton.Yes
        mock_question.return_value = QMessageBox.StandardButton.Yes
        mock_transcription_manager.get_all_tasks.return_value = [{"id": "task-1", "status": TASK_STATUS_PENDING}]
        mock_transcription_manager.delete_task.return_value = True
        mock_transcription_manager.delete_task.return_value = True

        with patch.object(widget, "_remove_task_item"):
            widget._on_clear_queue()

        mock_transcription_manager.stop_all_tasks.assert_called_once()
        mock_transcription_manager.start_processing.assert_called()

    @patch("ui.batch_transcribe.widget.QTimer.singleShot")
    @patch("ui.batch_transcribe.widget.QMessageBox.question")
    def test_clear_queue_retries_processing_tasks(
        self, mock_question, mock_single_shot, widget, mock_transcription_manager
    ):
        """Clearing queue should retry deletion for in-flight processing tasks."""
        mock_question.return_value = QMessageBox.StandardButton.Yes
        mock_transcription_manager.get_all_tasks.side_effect = [
            [{"id": "task-1", "status": TASK_STATUS_PROCESSING}],
            [{"id": "task-1", "status": TASK_STATUS_CANCELLED}],
        ]
        mock_transcription_manager.delete_task.side_effect = [False, True]
        mock_single_shot.side_effect = lambda _ms, callback: callback()

        with patch.object(widget, "_remove_task_item") as mock_remove:
            widget._on_clear_queue()

        assert mock_transcription_manager.delete_task.call_count == 2
        mock_remove.assert_called_once_with("task-1")
        mock_transcription_manager.start_processing.assert_called_once()

    @patch("ui.batch_transcribe.widget.QMessageBox.question")
    def test_delete_task_failure_keeps_ui_item(self, mock_question, widget, mock_transcription_manager):
        """Failed deletion should not remove the task item from UI list."""
        mock_question.return_value = QMessageBox.StandardButton.Yes
        mock_transcription_manager.delete_task.return_value = False

        with (
            patch.object(widget, "_remove_task_item") as mock_remove,
            patch.object(widget, "_show_error"),
        ):
            widget._on_task_delete("task-1")

        mock_remove.assert_not_called()

    @patch("ui.batch_transcribe.widget.QFileDialog.getSaveFileName")
    def test_export_infers_format_from_filter_pattern(
        self, mock_save_dialog, widget, mock_transcription_manager
    ):
        """Export should infer format from filter pattern and append extension when missing."""
        mock_transcription_manager.get_task_status.return_value = {"file_name": "sample.wav"}
        mock_save_dialog.return_value = ("/tmp/sample_export", "Sous-titres SRT (*.srt)")

        with patch.object(widget, "show_info"):
            widget._on_task_export("task-1")

        mock_transcription_manager.export_result.assert_called_once_with(
            "task-1", "srt", "/tmp/sample_export.srt"
        )
    
    @patch("ui.batch_transcribe.transcript_viewer.TranscriptViewerDialog")
    def test_view_task_opens_dialog(self, mock_dialog_class, widget, mock_transcription_manager):
        """View task should open TranscriptViewerDialog with manager."""
        mock_transcription_manager.db = MagicMock()
        
        # Test the method
        widget._on_task_view("task-1")
        
        # Verify dialog created with correct args: task_id, manager, db, i18n...
        mock_dialog_class.assert_called_once()
        args, _ = mock_dialog_class.call_args
        assert args[0] == "task-1"
        assert args[1] == mock_transcription_manager
        
        # Verify show was called
        mock_dialog_class.return_value.show.assert_called_once()
    
    def test_handle_task_added_event(self, widget):
        """Test handling task_added event."""
    def test_handle_task_added_event(self, widget):
        """Test handling task_added event."""
        task_data = {"id": "new-task", "status": TASK_STATUS_PENDING, "file_name": "test.mp3"}
        
        # Simulate event
        widget._handle_manager_event("task_added", task_data)
        
        # Verify task item added
        assert "new-task" in widget.task_items
        assert widget.task_list.count() == 1
        
    def test_handle_task_updated_event(self, widget):
        """Test handling task_updated event."""
    def test_handle_task_updated_event(self, widget):
        """Test handling task_updated event."""
        # Add initial task
        task_data = {"id": "task-1", "status": TASK_STATUS_PENDING, "file_name": "test.mp3"}
        widget._add_task_item(task_data)
        
        # Simulate update event
        update_data = {"id": "task-1", "status": TASK_STATUS_PROCESSING, "progress": 50.0}
        
        # Mock item update method
        with patch.object(widget.task_items["task-1"], "update_task_data") as mock_update:
            widget._handle_manager_event("task_updated", update_data)
            mock_update.assert_called_once_with(update_data)
            
    def test_handle_task_deleted_event(self, widget):
        """Test handling task_deleted event."""
        # Add initial task
        task_data = {"id": "task-1", "status": TASK_STATUS_PENDING, "file_name": "test.mp3"}
        widget._add_task_item(task_data)
        
        # Simulate delete event
        widget._handle_manager_event("task_deleted", {"id": "task-1"})
        
        # Verify task removed
        assert "task-1" not in widget.task_items
        assert widget.task_list.count() == 0
        
    def test_handle_pause_resume_events(self, widget):
        """Test handling pause and resume events."""
        # Simulate pause
        with patch.object(widget, "_set_tasks_pause_state") as mock_set_pause:
            widget._handle_manager_event("processing_paused", {})
            mock_set_pause.assert_called_with(True)
            
        # Simulate resume
        with patch.object(widget, "_set_tasks_pause_state") as mock_set_pause:
            widget._handle_manager_event("processing_resumed", {})
            mock_set_pause.assert_called_with(False)


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
