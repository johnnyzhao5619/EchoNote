# SPDX-License-Identifier: Apache-2.0
"""Unit tests for workspace manager."""

from pathlib import Path

from data.database.connection import DatabaseConnection
from data.database.models import CalendarEvent, WorkspaceAsset, WorkspaceItem
from data.storage.file_manager import FileManager


def build_workspace_manager(tmp_path):
    from core.workspace.manager import WorkspaceManager

    db = DatabaseConnection(str(tmp_path / "workspace.db"))
    db.initialize_schema()
    file_manager = FileManager(str(tmp_path / "files"))
    return WorkspaceManager(db, file_manager)


def create_workspace_recording(manager, *, title: str, status: str = "completed") -> str:
    item = WorkspaceItem(
        title=title,
        item_type="recording",
        source_kind="realtime_recording",
        status=status,
    )
    item.save(manager.db)
    audio_path = Path(manager.file_manager.get_workspace_path(item.id, "audio", f"{title}.wav"))
    audio_path.parent.mkdir(parents=True, exist_ok=True)
    audio_path.write_bytes(b"RIFF")
    transcript_path = Path(manager.file_manager.get_workspace_path(item.id, "text", f"{title}.md"))
    transcript_path.parent.mkdir(parents=True, exist_ok=True)
    transcript_path.write_text(f"{title} transcript", encoding="utf-8")

    audio_asset = WorkspaceAsset(
        item_id=item.id,
        asset_role="audio",
        file_path=str(audio_path),
        content_type="audio/wav",
    )
    audio_asset.save(manager.db)
    transcript_asset = WorkspaceAsset(
        item_id=item.id,
        asset_role="transcript",
        file_path=str(transcript_path),
        text_content=transcript_path.read_text(encoding="utf-8"),
        content_type="text/markdown",
    )
    transcript_asset.save(manager.db)
    item.primary_audio_asset_id = audio_asset.id
    item.primary_text_asset_id = transcript_asset.id
    item.save(manager.db)
    return item.id


def create_workspace_document(manager, *, title: str, status: str = "active") -> str:
    item = WorkspaceItem(
        title=title,
        item_type="document",
        source_kind="workspace_note",
        status=status,
    )
    item.save(manager.db)
    document_path = Path(manager.file_manager.get_workspace_path(item.id, "notes", f"{title}.md"))
    document_path.parent.mkdir(parents=True, exist_ok=True)
    document_path.write_text(f"{title} body", encoding="utf-8")
    asset = WorkspaceAsset(
        item_id=item.id,
        asset_role="document_text",
        file_path=str(document_path),
        text_content=document_path.read_text(encoding="utf-8"),
        content_type="text/markdown",
    )
    asset.save(manager.db)
    item.primary_text_asset_id = asset.id
    item.save(manager.db)
    return item.id


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
    assert kept_item.status == "orphaned"

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


def test_get_event_cleanup_summary_reports_workspace_linkage(tmp_path):
    """Delete confirmation should be able to describe linked workspace assets."""
    from core.workspace.manager import WorkspaceManager

    db = DatabaseConnection(str(tmp_path / "workspace_cleanup_summary.db"))
    db.initialize_schema()
    file_manager = FileManager(str(tmp_path / "files"))
    workspace_manager = WorkspaceManager(db, file_manager)

    doc = tmp_path / "summary_source.txt"
    doc.write_text("workspace linked content", encoding="utf-8")
    event = CalendarEvent(
        title="Linked Event",
        start_time="2026-03-15T11:00:00+00:00",
        end_time="2026-03-15T12:00:00+00:00",
    )
    event.save(db)
    item_id = workspace_manager.import_document(str(doc))
    item = workspace_manager.get_item(item_id)
    assert item is not None
    item.source_event_id = event.id
    item.save(db)

    summary = workspace_manager.get_event_cleanup_summary(event.id)

    assert summary["linked_item_count"] == 1
    assert summary["linked_asset_count"] == 2
    assert summary["has_workspace_assets"] is True
    assert summary["asset_roles"] == ["document_text", "source_document"]


def test_workspace_manager_lists_filtered_collections(tmp_path):
    manager = build_workspace_manager(tmp_path)
    create_workspace_recording(manager, title="Call")
    create_workspace_document(manager, title="Agenda")

    recordings = manager.list_items(collection="recordings")
    documents = manager.list_items(collection="documents")

    assert [item.title for item in recordings] == ["Call"]
    assert [item.title for item in documents] == ["Agenda"]


def test_workspace_manager_lists_orphaned_collection(tmp_path):
    manager = build_workspace_manager(tmp_path)
    orphaned_id = create_workspace_document(manager, title="Detached", status="orphaned")
    create_workspace_document(manager, title="Fresh")

    orphaned_items = manager.list_items(collection="orphaned")

    assert [item.id for item in orphaned_items] == [orphaned_id]


def test_workspace_manager_lists_recent_collection_in_updated_order(tmp_path):
    manager = build_workspace_manager(tmp_path)
    old_id = create_workspace_document(manager, title="Old")
    recent_id = create_workspace_recording(manager, title="Recent")

    recent_items = manager.list_items(collection="recent")

    assert [item.id for item in recent_items[:2]] == [recent_id, old_id]
