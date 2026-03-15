# SPDX-License-Identifier: Apache-2.0
"""Unit tests for workspace manager."""

from pathlib import Path

from data.database.connection import DatabaseConnection
from data.storage.file_manager import FileManager


def test_import_document_creates_workspace_item(tmp_path):
    """Importing a document should create a unified workspace item."""
    from core.workspace.manager import WorkspaceManager

    db = DatabaseConnection(str(tmp_path / "workspace.db"))
    db.initialize_schema()
    file_manager = FileManager(str(tmp_path / "files"))
    workspace_manager = WorkspaceManager(db, file_manager)

    doc = tmp_path / "agenda.md"
    doc.write_text("# Agenda", encoding="utf-8")

    item_id = workspace_manager.import_document(str(doc))
    item = workspace_manager.get_item(item_id)
    assets = workspace_manager.get_assets(item_id)

    assert item is not None
    assert item.item_type == "document"
    assert item.primary_text_asset_id is not None
    assert any(asset.asset_role == "source_document" for asset in assets)
    assert any(asset.asset_role == "document_text" for asset in assets)


def test_import_document_copies_source_and_extracted_text(tmp_path):
    """Workspace import should persist both original document and editable text."""
    from core.workspace.manager import WorkspaceManager

    db = DatabaseConnection(str(tmp_path / "workspace_assets.db"))
    db.initialize_schema()
    file_manager = FileManager(str(tmp_path / "files"))
    workspace_manager = WorkspaceManager(db, file_manager)

    doc = tmp_path / "notes.txt"
    doc.write_text("meeting notes", encoding="utf-8")

    item_id = workspace_manager.import_document(str(doc))
    assets = workspace_manager.get_assets(item_id)

    source_asset = next(asset for asset in assets if asset.asset_role == "source_document")
    text_asset = next(asset for asset in assets if asset.asset_role == "document_text")

    assert Path(source_asset.file_path).exists()
    assert Path(text_asset.file_path).exists()
    assert Path(text_asset.file_path).read_text(encoding="utf-8") == "meeting notes"
