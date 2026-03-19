# SPDX-License-Identifier: Apache-2.0
"""Unit tests for workspace manager."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from data.database.connection import DatabaseConnection
from data.database.models import CalendarEvent, TranscriptionTask, WorkspaceAsset, WorkspaceItem
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
    assert Path(source_asset.file_path).parent.name == "notes.assets"
    assert text_asset.file_path.endswith("工作台条目/notes.md")
    assert Path(text_asset.file_path).read_text(encoding="utf-8") == "meeting notes"
    assert text_asset.text_content is None


def test_workspace_note_is_stored_as_markdown_file_in_vault(tmp_path):
    manager = build_workspace_manager(tmp_path)

    note_id = manager.create_note(title="Plan", text_content="hello")
    asset = manager.get_primary_text_asset(note_id)

    assert asset is not None
    assert asset.file_path.endswith("工作台条目/Plan.md")
    assert Path(asset.file_path).read_text(encoding="utf-8") == "hello"
    assert asset.content_type == "text/markdown"
    assert asset.text_content is None


def test_read_asset_text_prefers_file_over_stale_database_content(tmp_path):
    manager = build_workspace_manager(tmp_path)

    note_id = manager.create_note(title="Plan", text_content="hello")
    asset = manager.get_primary_text_asset(note_id)

    assert asset is not None
    asset.text_content = "stale"
    asset.save(manager.db)

    assert manager.read_asset_text(asset) == "hello"


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


def test_workspace_manager_supports_folders_and_dual_library_views(tmp_path):
    manager = build_workspace_manager(tmp_path)
    folder_id = manager.create_folder("Projects")
    note_id = manager.create_note(title="Plan")
    event = CalendarEvent(
        title="Planning Session",
        start_time="2026-03-15T13:00:00+00:00",
        end_time="2026-03-15T14:00:00+00:00",
    )
    event.save(manager.db)

    note = manager.get_item(note_id)
    assert note is not None
    note.source_event_id = event.id
    note.save(manager.db)

    manager.move_item_to_folder(note_id, folder_id)

    structure_items = manager.list_items(view_mode="structure", folder_id=folder_id)
    event_items = manager.list_items(view_mode="event")
    filtered_event_items = manager.list_items(view_mode="event", event_id=event.id)

    assert [item.id for item in structure_items] == [note_id]
    assert note_id in [item.id for item in event_items]
    assert [item.id for item in filtered_event_items] == [note_id]

    event_navigation = manager.get_event_navigation_entries()
    assert event_navigation[0]["event_id"] == event.id
    assert event_navigation[0]["event_title"] == "Planning Session"
    assert event_navigation[0]["item_count"] == 1


def test_workspace_manager_builds_context_metadata_for_event_and_batch_links(tmp_path):
    manager = build_workspace_manager(tmp_path)
    event = CalendarEvent(
        title="Planning Session",
        start_time="2026-03-15T13:00:00+00:00",
        end_time="2026-03-15T14:00:00+00:00",
    )
    event.save(manager.db)

    recording_path = tmp_path / "meeting.wav"
    recording_path.write_bytes(b"RIFF")
    transcript_path = tmp_path / "meeting.md"
    transcript_path.write_text("hello", encoding="utf-8")

    task = TranscriptionTask(
        id="task-context-1",
        file_path=str(recording_path),
        file_name=recording_path.name,
        status="completed",
    )
    task.save(manager.db)

    item_id = manager.publish_transcription_task(
        task,
        transcript_path=str(transcript_path),
        event_id=event.id,
    )

    metadata = manager.get_item_context_metadata(item_id)

    assert metadata["event_title"] == "Planning Session"
    assert metadata["task_id"] == "task-context-1"
    assert metadata["original_file_name"] == "meeting.wav"


def test_event_linked_items_default_into_event_folder_but_keep_link_after_move(tmp_path):
    manager = build_workspace_manager(tmp_path)
    event = CalendarEvent(
        title="Design Review",
        start_time="2026-03-15T09:00:00+00:00",
        end_time="2026-03-15T10:00:00+00:00",
    )
    event.save(manager.db)

    item_id = manager.create_note(title="Review Notes", event_id=event.id)
    item = manager.get_item(item_id)

    assert item is not None
    event_folder = manager.get_folder(item.folder_id)
    assert event_folder is not None
    assert getattr(event_folder, "folder_kind", None) == "event"
    assert getattr(event_folder, "source_event_id", None) == event.id
    assert item.source_event_id == event.id

    archive_folder_id = manager.create_folder("Archive")
    manager.move_item_to_folder(item_id, archive_folder_id)
    moved = manager.get_item(item_id)

    assert moved is not None
    assert moved.folder_id == archive_folder_id
    assert moved.source_event_id == event.id


def test_batch_task_items_default_into_batch_folder_but_keep_task_link_after_move(tmp_path):
    manager = build_workspace_manager(tmp_path)
    recording_path = tmp_path / "meeting.wav"
    recording_path.write_bytes(b"RIFF")
    transcript_path = tmp_path / "meeting.md"
    transcript_path.write_text("hello", encoding="utf-8")

    persisted_task = TranscriptionTask(
        id="task-1",
        file_path=str(recording_path),
        file_name=recording_path.name,
        status="completed",
    )
    persisted_task.save(manager.db)
    task = SimpleNamespace(
        id=persisted_task.id,
        file_path=persisted_task.file_path,
        file_name=persisted_task.file_name,
        status=persisted_task.status,
    )

    item_id = manager.publish_transcription_task(task, transcript_path=str(transcript_path))
    item = manager.get_item(item_id)

    assert item is not None
    batch_folder = manager.get_folder(item.folder_id)
    assert batch_folder is not None
    assert getattr(batch_folder, "folder_kind", None) == "batch_task"
    assert item.source_task_id == "task-1"

    archive_folder_id = manager.create_folder("Archive")
    manager.move_item_to_folder(item_id, archive_folder_id)
    moved = manager.get_item(item_id)

    assert moved is not None
    assert moved.folder_id == archive_folder_id
    assert moved.source_task_id == "task-1"


def test_workspace_manager_ensures_system_folders_and_normalizes_unassigned_items(tmp_path):
    manager = build_workspace_manager(tmp_path)
    loose_document_id = create_workspace_document(manager, title="Loose Doc")

    inbox_folder = manager.ensure_inbox_folder()
    event_root_folder = manager.ensure_event_root_folder()
    batch_root_folder = manager.ensure_batch_task_root_folder()

    folders = manager.list_folders()
    folder_names = {folder.name for folder in folders}
    normalized_item = manager.get_item(loose_document_id)

    assert normalized_item is not None
    assert normalized_item.folder_id == inbox_folder.id
    assert {"工作台条目", "事件", "批量任务"} <= folder_names
    assert inbox_folder.folder_kind == "inbox"
    assert event_root_folder.folder_kind == "system_root"
    assert batch_root_folder.folder_kind == "batch_task"


def test_workspace_manager_renames_moves_and_deletes_folders(tmp_path):
    manager = build_workspace_manager(tmp_path)
    source_folder_id = manager.create_folder("Projects")
    target_folder_id = manager.create_folder("Archive")
    child_folder_id = manager.create_folder("Sprint", parent_id=source_folder_id)
    note_id = manager.create_note(title="Plan")

    manager.rename_folder(source_folder_id, "Active Projects")
    manager.move_folder(child_folder_id, target_folder_id)
    manager.move_item_to_folder(note_id, target_folder_id)

    renamed_folder = manager.get_folder(source_folder_id)
    moved_folder = manager.get_folder(child_folder_id)

    assert renamed_folder is not None
    assert renamed_folder.name == "Active Projects"
    assert moved_folder is not None
    assert moved_folder.parent_id == target_folder_id
    assert manager.delete_folder(source_folder_id) is True


def test_rename_and_move_item_sync_markdown_file_path(tmp_path):
    manager = build_workspace_manager(tmp_path)
    folder_id = manager.create_folder("Projects")
    note_id = manager.create_note(title="Plan", text_content="hello")

    manager.move_item_to_folder(note_id, folder_id)
    manager.rename_item(note_id, "Spec")

    asset = manager.get_primary_text_asset(note_id)

    assert asset is not None
    assert asset.file_path.endswith("工作台条目/Projects/Spec.md")
    assert Path(asset.file_path).read_text(encoding="utf-8") == "hello"


def test_rename_folder_syncs_descendant_markdown_paths(tmp_path):
    manager = build_workspace_manager(tmp_path)
    folder_id = manager.create_folder("Projects")
    note_id = manager.create_note(title="Plan", text_content="hello")
    manager.move_item_to_folder(note_id, folder_id)

    manager.rename_folder(folder_id, "Active Projects")

    asset = manager.get_primary_text_asset(note_id)

    assert asset is not None
    assert asset.file_path.endswith("工作台条目/Active Projects/Plan.md")
    assert Path(asset.file_path).read_text(encoding="utf-8") == "hello"


def test_workspace_manager_creates_unique_note_titles_within_same_folder(tmp_path):
    manager = build_workspace_manager(tmp_path)

    first_id = manager.create_note(title="未命名笔记")
    second_id = manager.create_note(title="未命名笔记")

    first_item = manager.get_item(first_id)
    second_item = manager.get_item(second_id)

    assert first_item is not None
    assert second_item is not None
    assert first_item.title == "未命名笔记"
    assert second_item.title == "未命名笔记 2"


def test_workspace_manager_rejects_duplicate_names_for_renaming_and_folder_creation(tmp_path):
    from core.workspace.manager import WorkspaceValidationError

    manager = build_workspace_manager(tmp_path)
    note_id = manager.create_note(title="Plan")
    inbox_folder = manager.ensure_inbox_folder()

    with pytest.raises(WorkspaceValidationError, match="duplicate_name"):
        manager.create_folder("Plan", parent_id=inbox_folder.id)

    folder_id = manager.create_folder("Projects")
    manager.move_item_to_folder(note_id, folder_id)
    another_note_id = manager.create_note(title="Spec")
    manager.move_item_to_folder(another_note_id, folder_id)

    with pytest.raises(WorkspaceValidationError, match="duplicate_name"):
        manager.rename_item(another_note_id, "Plan")


def test_workspace_manager_delete_item_removes_assets_and_files(tmp_path):
    manager = build_workspace_manager(tmp_path)
    item_id = manager.create_note(title="Plan", text_content="Hello")
    asset = manager.get_primary_text_asset(item_id)
    assert asset is not None
    asset_path = Path(asset.file_path)
    assert asset_path.exists()

    assert manager.delete_item(item_id) is True
    assert manager.get_item(item_id) is None
    assert manager.get_primary_text_asset(item_id) is None
    assert not asset_path.exists()


def test_workspace_manager_move_item_rejects_duplicate_names_and_system_root_targets(tmp_path):
    from core.workspace.manager import WorkspaceValidationError

    manager = build_workspace_manager(tmp_path)
    archive_folder_id = manager.create_folder("Archive")
    drafts_folder_id = manager.create_folder("Drafts")
    first_note_id = manager.create_note(title="Plan")
    second_note_id = manager.create_note(title="Plan")
    event_root_folder = manager.ensure_event_root_folder()
    batch_root_folder = manager.ensure_batch_task_root_folder()

    manager.move_item_to_folder(first_note_id, archive_folder_id)
    manager.move_item_to_folder(second_note_id, drafts_folder_id)
    manager.rename_item(second_note_id, "Plan")

    with pytest.raises(WorkspaceValidationError, match="duplicate_name"):
        manager.move_item_to_folder(second_note_id, archive_folder_id)

    with pytest.raises(WorkspaceValidationError, match="invalid_move_target"):
        manager.move_item_to_folder(second_note_id, event_root_folder.id)

    with pytest.raises(WorkspaceValidationError, match="invalid_move_target"):
        manager.move_item_to_folder(second_note_id, batch_root_folder.id)


def test_workspace_manager_move_and_delete_cleanup_empty_event_folder(tmp_path):
    manager = build_workspace_manager(tmp_path)
    event = CalendarEvent(
        title="Recording Session",
        start_time="2026-03-16T19:30:00+00:00",
        end_time="2026-03-16T20:00:00+00:00",
    )
    event.save(manager.db)
    note_id = manager.create_note(title="Session Note", event_id=event.id)
    event_folder_id = manager.resolve_default_folder_id(event_id=event.id)
    archive_folder_id = manager.create_folder("Archive")

    assert manager.get_folder(event_folder_id) is not None

    manager.move_item_to_folder(note_id, archive_folder_id)

    assert manager.get_folder(event_folder_id) is None

    another_note_id = manager.create_note(title="Session Note", event_id=event.id)
    new_event_folder_id = manager.resolve_default_folder_id(event_id=event.id)
    assert manager.get_folder(new_event_folder_id) is not None

    assert manager.delete_item(another_note_id) is True
    assert manager.get_folder(new_event_folder_id) is None


def test_workspace_manager_delete_generated_event_folder_removes_contents(tmp_path):
    manager = build_workspace_manager(tmp_path)
    event = CalendarEvent(
        title="Realtime Session",
        start_time="2026-03-16T21:00:00+00:00",
        end_time="2026-03-16T22:00:00+00:00",
    )
    event.save(manager.db)
    note_id = manager.create_note(title="Realtime Note", event_id=event.id)
    folder_id = manager.resolve_default_folder_id(event_id=event.id)

    summary = manager.get_folder_cleanup_summary(folder_id)

    assert summary["linked_item_count"] == 1
    assert manager.delete_generated_folder(folder_id) == 1
    assert manager.get_item(note_id) is None
    assert manager.get_folder(folder_id) is None
