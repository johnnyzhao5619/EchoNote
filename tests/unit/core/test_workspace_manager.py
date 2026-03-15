# SPDX-License-Identifier: Apache-2.0
"""Unit tests for workspace manager."""

from pathlib import Path

from data.database.connection import DatabaseConnection
from data.database.models import CalendarEvent
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


def test_save_text_asset_preserves_existing_primary_text_asset(tmp_path):
    """Generated assets should not steal primary text from the editable source transcript."""
    from core.workspace.manager import WorkspaceManager

    db = DatabaseConnection(str(tmp_path / "workspace_primary.db"))
    db.initialize_schema()
    file_manager = FileManager(str(tmp_path / "files"))
    workspace_manager = WorkspaceManager(db, file_manager)

    doc = tmp_path / "notes.txt"
    doc.write_text("meeting notes", encoding="utf-8")
    item_id = workspace_manager.import_document(str(doc))
    item = workspace_manager.get_item(item_id)
    assert item is not None

    primary_before = item.primary_text_asset_id
    summary_asset = workspace_manager.save_text_asset(item_id, "summary", "short summary")
    item = workspace_manager.get_item(item_id)

    assert summary_asset.asset_role == "summary"
    assert item.primary_text_asset_id == primary_before


def test_remove_event_asset_role_reselects_primary_text_asset(tmp_path):
    """Removing the current primary transcript should promote the next best text asset."""
    from core.workspace.manager import WorkspaceManager

    db = DatabaseConnection(str(tmp_path / "workspace_remove_asset.db"))
    db.initialize_schema()
    file_manager = FileManager(str(tmp_path / "files"))
    workspace_manager = WorkspaceManager(db, file_manager)

    doc = tmp_path / "meeting.txt"
    doc.write_text("transcript body", encoding="utf-8")
    event = CalendarEvent(
        title="Meeting",
        start_time="2026-03-15T09:00:00+00:00",
        end_time="2026-03-15T10:00:00+00:00",
    )
    event.save(db)
    item_id = workspace_manager.import_document(str(doc))
    item = workspace_manager.get_item(item_id)
    assert item is not None
    item.source_event_id = event.id
    item.save(db)

    transcript_asset = workspace_manager.get_primary_text_asset(item_id)
    summary_asset = workspace_manager.save_text_asset(item_id, "summary", "summary body")

    item.primary_text_asset_id = transcript_asset.id
    item.save(db)

    assert workspace_manager.remove_event_asset_role(event.id, "document_text") is True

    refreshed = workspace_manager.get_item(item_id)
    assert refreshed is not None
    assert refreshed.primary_text_asset_id == summary_asset.id


def test_detach_and_delete_event_items_manage_workspace_lifecycle(tmp_path):
    """Event cleanup should either detach or fully remove workspace items."""
    from core.workspace.manager import WorkspaceManager

    db = DatabaseConnection(str(tmp_path / "workspace_event_delete.db"))
    db.initialize_schema()
    file_manager = FileManager(str(tmp_path / "files"))
    workspace_manager = WorkspaceManager(db, file_manager)

    doc = tmp_path / "agenda.txt"
    doc.write_text("agenda", encoding="utf-8")
    event_keep = CalendarEvent(
        title="Keep Event",
        start_time="2026-03-15T09:00:00+00:00",
        end_time="2026-03-15T10:00:00+00:00",
    )
    event_keep.save(db)
    item_id = workspace_manager.import_document(str(doc))
    item = workspace_manager.get_item(item_id)
    assert item is not None
    item.source_event_id = event_keep.id
    item.save(db)

    detached = workspace_manager.detach_event_items(event_keep.id)
    kept_item = workspace_manager.get_item(item_id)

    assert detached == 1
    assert kept_item is not None
    assert kept_item.source_event_id is None

    event_delete = CalendarEvent(
        title="Delete Event",
        start_time="2026-03-16T09:00:00+00:00",
        end_time="2026-03-16T10:00:00+00:00",
    )
    event_delete.save(db)
    item.source_event_id = event_delete.id
    item.save(db)
    assets = workspace_manager.get_assets(item_id)

    deleted = workspace_manager.delete_event_items(event_delete.id, delete_files=True)

    assert deleted == 1
    assert workspace_manager.get_item(item_id) is None
    assert all(not Path(asset.file_path).exists() for asset in assets if asset.file_path)
