# SPDX-License-Identifier: Apache-2.0
"""Tests for workspace summary and meeting brief services."""

from unittest.mock import Mock

from data.database.connection import DatabaseConnection
from data.storage.file_manager import FileManager

from core.workspace.manager import WorkspaceManager


def test_generate_meeting_brief_writes_summary_assets(tmp_path):
    db = DatabaseConnection(str(tmp_path / "workspace_summary.db"))
    db.initialize_schema()
    file_manager = FileManager(str(tmp_path / "files"))

    settings_manager = Mock()
    settings_manager.get_workspace_ai_preferences.return_value = {
        "default_summary_strategy": "extractive",
        "default_meeting_model": "extractive-default",
        "default_meeting_template": "standard",
        "gguf_runtime_command": [],
    }
    model_manager = Mock()

    workspace_manager = WorkspaceManager(
        db,
        file_manager,
        settings_manager=settings_manager,
        model_manager=model_manager,
    )

    doc = tmp_path / "meeting.txt"
    doc.write_text(
        "We decided to ship the workspace page next week. "
        "Alice will update the UI. Bob will validate the release checklist. "
        "Next step is to review the rollout on Friday.",
        encoding="utf-8",
    )
    item_id = workspace_manager.import_document(str(doc))

    result = workspace_manager.generate_meeting_brief(item_id)
    assets = workspace_manager.get_assets(item_id)

    assert "summary_asset_id" in result
    assert "action_items_asset_id" in result
    assert any(asset.asset_role == "summary" for asset in assets)
    assert any(asset.asset_role == "action_items" for asset in assets)
