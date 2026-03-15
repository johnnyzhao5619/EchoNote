# SPDX-License-Identifier: Apache-2.0
"""UI tests for the unified workspace widget."""

from pathlib import Path
from unittest.mock import Mock

import pytest

from core.workspace.manager import WorkspaceManager
from data.database.connection import DatabaseConnection
from data.database.models import TranscriptionTask, WorkspaceAsset, WorkspaceItem
from data.storage.file_manager import FileManager
from ui.common.audio_player import AudioPlayer
from ui.workspace.widget import WorkspaceWidget

pytestmark = pytest.mark.ui


@pytest.fixture
def workspace_manager(tmp_path):
    db = DatabaseConnection(str(tmp_path / "workspace_ui.db"))
    db.initialize_schema()
    file_manager = FileManager(str(tmp_path / "files"))
    manager = WorkspaceManager(db, file_manager)

    item = WorkspaceItem(title="Sprint Sync", item_type="recording", source_kind="realtime_recording")
    item.save(db)

    audio_path = tmp_path / "meeting.wav"
    audio_path.write_bytes(b"RIFF")
    transcript_path = tmp_path / "meeting.txt"
    transcript_path.write_text("Team reviewed roadmap and decided to ship alpha next week.", encoding="utf-8")

    transcript_asset = WorkspaceAsset(
        item_id=item.id,
        asset_role="transcript",
        file_path=str(transcript_path),
        text_content=transcript_path.read_text(encoding="utf-8"),
        content_type="text/plain",
    )
    transcript_asset.save(db)

    audio_asset = WorkspaceAsset(
        item_id=item.id,
        asset_role="audio",
        file_path=str(audio_path),
        content_type="audio/wav",
    )
    audio_asset.save(db)

    item.primary_text_asset_id = transcript_asset.id
    item.primary_audio_asset_id = audio_asset.id
    item.save(db)

    return manager


class StubTranscriptionManager:
    """Minimal transcription manager stub for workspace UI tests."""

    def __init__(self, db):
        self.db = db
        self._listeners = []

    def add_listener(self, callback):
        self._listeners.append(callback)

    def remove_listener(self, callback):
        if callback in self._listeners:
            self._listeners.remove(callback)

    def get_all_tasks(self, status=None):
        tasks = TranscriptionTask.get_all(self.db, status=status)
        return [
            {
                **task.to_dict(),
                "task_kind": "translation" if task.engine == "translation" else "transcription",
            }
            for task in tasks
        ]

    def is_paused(self):
        return False

    def emit(self, event_type, data):
        if event_type == "task_added":
            task = TranscriptionTask(
                id=data["id"],
                file_path=data["file_path"],
                file_name=data["file_name"],
                file_size=data.get("file_size"),
                status=data.get("status", "pending"),
                output_format=data.get("output_format"),
                engine="translation" if data.get("task_kind") == "translation" else "whisper",
            )
            task.save(self.db)
        for callback in list(self._listeners):
            callback(event_type, data)


@pytest.fixture
def transcription_manager(workspace_manager):
    task = TranscriptionTask(
        file_path="/tmp/demo.wav",
        file_name="demo.wav",
        file_size=1024,
        status="pending",
        output_format="txt",
    )
    task.save(workspace_manager.db)
    return StubTranscriptionManager(workspace_manager.db)


def test_workspace_widget_shows_editor_audio_and_task_regions(
    qapp, mock_i18n, workspace_manager, transcription_manager
):
    widget = WorkspaceWidget(workspace_manager, mock_i18n, transcription_manager=transcription_manager)

    assert widget.item_list is not None
    assert widget.editor_panel is not None
    assert widget.recording_panel is not None
    assert widget.task_panel is not None


def test_workspace_editor_panel_save_updates_workspace_asset(qapp, mock_i18n, workspace_manager):
    widget = WorkspaceWidget(workspace_manager, mock_i18n)
    item = workspace_manager.list_items()[0]

    widget._on_item_selected(item.id)
    widget.editor_panel.show_info = Mock()
    widget.editor_panel.toggle_edit_mode()
    widget.editor_panel.text_edit.setPlainText("Updated transcript content")
    widget.editor_panel.save_changes()

    primary_asset = workspace_manager.get_primary_text_asset(item.id)
    assert workspace_manager.read_asset_text(primary_asset) == "Updated transcript content"


def test_workspace_editor_panel_generates_summary_asset(qapp, mock_i18n, workspace_manager):
    widget = WorkspaceWidget(workspace_manager, mock_i18n)
    item = workspace_manager.list_items()[0]
    widget._on_item_selected(item.id)
    widget.editor_panel.show_info = Mock()

    widget.editor_panel._generate_summary()

    roles = [asset.asset_role for asset in workspace_manager.get_assets(item.id)]
    assert "summary" in roles


def test_workspace_recording_panel_reuses_shared_audio_player(qapp, mock_i18n, workspace_manager):
    widget = WorkspaceWidget(workspace_manager, mock_i18n)

    assert isinstance(widget.recording_panel.audio_player, AudioPlayer)


def test_workspace_editor_panel_uses_stable_asset_labels(qapp, mock_i18n, workspace_manager):
    widget = WorkspaceWidget(workspace_manager, mock_i18n)
    item = workspace_manager.list_items()[0]

    widget._on_item_selected(item.id)
    labels = [
        widget.editor_panel.asset_selector.itemText(index)
        for index in range(widget.editor_panel.asset_selector.count())
    ]

    assert any(label.startswith("Transcript:") for label in labels)


def test_workspace_task_panel_renders_existing_tasks(
    qapp, mock_i18n, workspace_manager, transcription_manager
):
    widget = WorkspaceWidget(workspace_manager, mock_i18n, transcription_manager=transcription_manager)

    assert widget.task_panel.task_count() == 1
    assert widget.task_panel.task_items[0].filename_label.text() == "demo.wav"


def test_workspace_task_panel_updates_on_task_events(
    qapp, mock_i18n, workspace_manager, transcription_manager
):
    widget = WorkspaceWidget(workspace_manager, mock_i18n, transcription_manager=transcription_manager)

    transcription_manager.emit(
        "task_added",
        {
            "id": "task-2",
            "file_name": "translation.txt",
            "file_path": "/tmp/translation.txt",
            "file_size": 128,
            "status": "pending",
            "output_format": "txt",
            "task_kind": "translation",
        },
    )

    assert widget.task_panel.task_count() == 2
    assert {item.filename_label.text() for item in widget.task_panel.task_items} == {
        "demo.wav",
        "translation.txt",
    }


def test_workspace_widget_exposes_unified_create_toolbar(
    qapp, mock_i18n, workspace_manager, transcription_manager
):
    widget = WorkspaceWidget(workspace_manager, mock_i18n, transcription_manager=transcription_manager)
    widget.show()
    qapp.processEvents()

    assert widget.toolbar is not None
    assert widget.toolbar.import_document_button.isVisible()
    assert widget.toolbar.new_note_button.isVisible()
    assert widget.toolbar.start_recording_button.isVisible()


def test_workspace_toolbar_new_note_creates_workspace_item(
    qapp, mock_i18n, workspace_manager, transcription_manager
):
    widget = WorkspaceWidget(workspace_manager, mock_i18n, transcription_manager=transcription_manager)
    before_ids = {item.id for item in workspace_manager.list_items()}

    widget.toolbar.new_note_button.click()

    after_items = workspace_manager.list_items()
    created_items = [item for item in after_items if item.id not in before_ids]

    assert len(created_items) == 1
    assert created_items[0].source_kind == "workspace_note"
    assert workspace_manager.get_primary_text_asset(created_items[0].id) is not None
    assert widget.item_list.current_item_id() == created_items[0].id
