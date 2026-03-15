# SPDX-License-Identifier: Apache-2.0
"""UI tests for the unified workspace widget."""

from pathlib import Path
from unittest.mock import Mock

import pytest

from core.workspace.manager import WorkspaceManager
from data.database.connection import DatabaseConnection
from data.database.models import WorkspaceAsset, WorkspaceItem
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


def test_workspace_widget_shows_editor_and_audio_regions(qapp, mock_i18n, workspace_manager):
    widget = WorkspaceWidget(workspace_manager, mock_i18n)

    assert widget.item_list is not None
    assert widget.editor_panel is not None
    assert widget.recording_panel is not None


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
