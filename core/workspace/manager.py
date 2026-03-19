# SPDX-License-Identifier: Apache-2.0
"""Workspace domain manager."""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional

from data.database.models import WorkspaceAsset, WorkspaceFolder, WorkspaceItem
from data.storage.file_manager import FileManager

from core.workspace.document_parser import DocumentParser
from core.workspace.import_service import WorkspaceImportService
from core.workspace.vault_layout import WorkspaceVaultLayout

TEXT_ASSET_ROLE_PRIORITY = {
    "document_text": 0,
    "transcript": 1,
    "meeting_brief": 2,
    "summary": 3,
    "translation": 4,
    "decisions": 5,
    "action_items": 6,
    "next_steps": 7,
    "outline": 8,
}

LIBRARY_VIEW_STRUCTURE = "structure"
LIBRARY_VIEW_EVENT = "event"
WORKSPACE_FOLDER_KIND_USER = "user"
WORKSPACE_FOLDER_KIND_INBOX = "inbox"
WORKSPACE_FOLDER_KIND_SYSTEM_ROOT = "system_root"
WORKSPACE_FOLDER_KIND_EVENT = "event"
WORKSPACE_FOLDER_KIND_BATCH_TASK = "batch_task"
WORKSPACE_SYSTEM_FOLDER_EVENTS = "事件"
WORKSPACE_SYSTEM_FOLDER_BATCH_TASKS = "批量任务"


class WorkspaceValidationError(ValueError):
    """Workspace domain validation error with stable codes for UI handling."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class WorkspaceManager:
    """High-level API for unified workspace items and assets."""

    def __init__(
        self,
        db_connection,
        file_manager: FileManager,
        *,
        document_parser: Optional[DocumentParser] = None,
        import_service: Optional[WorkspaceImportService] = None,
        settings_manager=None,
        model_manager=None,
    ):
        self.db = db_connection
        self.file_manager = file_manager
        self.settings_manager = settings_manager
        self.model_manager = model_manager
        self.document_parser = document_parser or DocumentParser()
        self.vault_layout = WorkspaceVaultLayout(self.file_manager.workspace_dir)
        self.import_service = import_service or WorkspaceImportService(
            db_connection,
            file_manager,
            document_parser=self.document_parser,
            vault_layout=self.vault_layout,
        )

    def set_settings_manager(self, settings_manager) -> None:
        """Attach settings manager after workspace manager initialization."""
        self.settings_manager = settings_manager

    def set_model_manager(self, model_manager) -> None:
        """Attach model manager after workspace manager initialization."""
        self.model_manager = model_manager

    def import_document(self, file_path: str) -> str:
        """Import a document into the unified workspace store."""
        folder_id = self.ensure_inbox_folder().id
        item = WorkspaceItem(
            title=self._build_unique_entry_name(
                Path(file_path).stem or Path(file_path).name,
                container_id=folder_id,
            ),
            item_type="document",
            source_kind="manual_import",
            folder_id=folder_id,
        )
        item.save(self.db)
        self.import_service.import_document(item, file_path)
        return item.id

    def create_note(
        self,
        *,
        title: str,
        text_content: str = "",
        event_id: Optional[str] = None,
        folder_id: Optional[str] = None,
    ) -> str:
        """Create a workspace-native note item backed by a document text asset."""
        folder_id = folder_id or self.resolve_default_folder_id(event_id=event_id)
        target_folder = self.get_folder(folder_id) if folder_id else None
        if (
            folder_id is not None
            and event_id is None
            and target_folder is not None
            and not self._folder_accepts_direct_items(target_folder)
        ):
            raise WorkspaceValidationError("invalid_move_target")
        item = WorkspaceItem(
            title=self._build_unique_entry_name(title, container_id=folder_id),
            item_type="document",
            source_kind="workspace_note",
            folder_id=folder_id,
            source_event_id=event_id,
            status="active",
        )
        item.save(self.db)
        self.save_text_asset(item.id, "document_text", text_content)
        return item.id

    def create_folder(
        self,
        name: str,
        *,
        parent_id: Optional[str] = None,
        folder_kind: str = WORKSPACE_FOLDER_KIND_USER,
        source_event_id: Optional[str] = None,
    ) -> str:
        """Create a user-managed workspace folder."""
        normalized_name = self._normalize_entry_name(name)
        if not normalized_name:
            raise WorkspaceValidationError("empty_name")
        self._ensure_entry_name_available(normalized_name, container_id=parent_id)
        folder = WorkspaceFolder(
            name=normalized_name,
            parent_id=parent_id,
            folder_kind=folder_kind,
            source_event_id=source_event_id,
        )
        folder.save(self.db)
        return folder.id

    def get_folder(self, folder_id: str) -> Optional[WorkspaceFolder]:
        """Fetch a workspace folder by identifier."""
        return WorkspaceFolder.get_by_id(self.db, folder_id)

    def list_folders(self) -> List[WorkspaceFolder]:
        """List all workspace folders for structure rendering."""
        self.normalize_structure_assignments()
        self.ensure_structure_root_folders()
        return self._list_folders_raw()

    def ensure_structure_root_folders(self) -> list[WorkspaceFolder]:
        """Ensure stable top-level folders for structure view navigation."""
        return [
            self.ensure_inbox_folder(),
            self.ensure_event_root_folder(),
            self.ensure_batch_task_root_folder(),
        ]

    def ensure_inbox_folder(self) -> WorkspaceFolder:
        """Return the singleton top-level folder for manually created/imported docs."""
        return self._ensure_special_folder(
            name="工作台条目",
            folder_kind=WORKSPACE_FOLDER_KIND_INBOX,
        )

    def ensure_event_root_folder(self) -> WorkspaceFolder:
        """Return the singleton system root folder for event-backed content."""
        return self._ensure_system_root_folder(
            name=WORKSPACE_SYSTEM_FOLDER_EVENTS,
        )

    def ensure_batch_task_root_folder(self) -> WorkspaceFolder:
        """Return the singleton system root folder for batch-task content."""
        return self._ensure_special_folder(
            name=WORKSPACE_SYSTEM_FOLDER_BATCH_TASKS,
            folder_kind=WORKSPACE_FOLDER_KIND_BATCH_TASK,
        )

    def ensure_event_folder(self, event_id: str) -> WorkspaceFolder:
        """Return the canonical event folder for a calendar event."""
        if not event_id:
            raise ValueError("event_id is required")
        for folder in self._list_folders_raw():
            if (
                folder.folder_kind == WORKSPACE_FOLDER_KIND_EVENT
                and folder.source_event_id == event_id
            ):
                return folder

        root_folder = self.ensure_event_root_folder()
        folder_name = self._resolve_event_folder_name(event_id)
        folder = WorkspaceFolder(
            name=folder_name,
            parent_id=root_folder.id,
            folder_kind=WORKSPACE_FOLDER_KIND_EVENT,
            source_event_id=event_id,
        )
        folder.save(self.db)
        return folder

    def resolve_default_folder_id(
        self,
        *,
        event_id: Optional[str] = None,
        task_id: Optional[str] = None,
    ) -> Optional[str]:
        """Resolve the default structure folder for new workspace items."""
        if task_id:
            return self.ensure_batch_task_root_folder().id
        if event_id:
            return self.ensure_event_folder(event_id).id
        return self.ensure_inbox_folder().id

    def rename_folder(self, folder_id: str, name: str) -> WorkspaceFolder:
        """Rename a workspace folder."""
        folder = self.get_folder(folder_id)
        if folder is None:
            raise ValueError(f"Unknown workspace folder: {folder_id}")
        if getattr(folder, "folder_kind", "") != WORKSPACE_FOLDER_KIND_USER:
            raise WorkspaceValidationError("folder_not_renamable")
        normalized_name = self._normalize_entry_name(name)
        if not normalized_name:
            raise WorkspaceValidationError("empty_name")
        self._ensure_entry_name_available(
            normalized_name,
            container_id=folder.parent_id,
            exclude_folder_id=folder.id,
        )
        folder.name = normalized_name
        folder.save(self.db)
        self._sync_folder_tree_asset_paths(folder.id)
        return folder

    def rename_item(self, item_id: str, title: str) -> WorkspaceItem:
        """Rename a workspace item while enforcing same-container uniqueness."""
        item = self.get_item(item_id)
        if item is None:
            raise ValueError(f"Unknown workspace item: {item_id}")
        normalized_title = self._normalize_entry_name(title)
        if not normalized_title:
            raise WorkspaceValidationError("empty_name")
        self._ensure_entry_name_available(
            normalized_title,
            container_id=item.folder_id,
            exclude_item_id=item.id,
        )
        item.title = normalized_title
        item.save(self.db)
        self._sync_item_asset_paths(item)
        return item

    def move_folder(self, folder_id: str, parent_id: Optional[str]) -> WorkspaceFolder:
        """Move a folder under a new parent folder."""
        folder = self.get_folder(folder_id)
        if folder is None:
            raise ValueError(f"Unknown workspace folder: {folder_id}")
        if parent_id == folder_id:
            raise ValueError("Folder cannot be its own parent")
        if parent_id is not None:
            parent = self.get_folder(parent_id)
            if parent is None:
                raise ValueError(f"Unknown target folder: {parent_id}")
            ancestor_id = parent.parent_id
            while ancestor_id:
                if ancestor_id == folder_id:
                    raise ValueError("Folder move would create a cycle")
                ancestor = self.get_folder(ancestor_id)
                ancestor_id = ancestor.parent_id if ancestor is not None else None
            if getattr(parent, "folder_kind", "") != WORKSPACE_FOLDER_KIND_USER:
                raise WorkspaceValidationError("invalid_move_target")
        folder.parent_id = parent_id
        folder.save(self.db)
        self._sync_folder_tree_asset_paths(folder.id)
        return folder

    def delete_folder(self, folder_id: str) -> bool:
        """Delete an empty workspace folder."""
        folder = self.get_folder(folder_id)
        if folder is None:
            return False
        if getattr(folder, "folder_kind", "") != WORKSPACE_FOLDER_KIND_USER:
            raise WorkspaceValidationError("folder_not_deletable")
        child_folders = [item for item in self.list_folders() if item.parent_id == folder_id]
        if child_folders:
            raise WorkspaceValidationError("folder_not_empty")
        linked_items = self.db.execute(
            "SELECT id FROM workspace_items WHERE folder_id = ? LIMIT 1",
            (folder_id,),
        )
        if linked_items:
            raise WorkspaceValidationError("folder_not_empty")
        folder.delete(self.db)
        return True

    def delete_item(self, item_id: str, *, delete_files: bool = True) -> bool:
        """Delete a workspace item together with its owned assets."""
        item = self.get_item(item_id)
        if item is None:
            return False
        folder_id = item.folder_id
        for asset in WorkspaceAsset.get_by_item_id(self.db, item.id):
            if delete_files:
                self._delete_asset_file(asset)
            asset.delete(self.db)
        item.delete(self.db)
        self._cleanup_empty_folder(folder_id)
        return True

    def move_item_to_folder(self, item_id: str, folder_id: Optional[str]) -> WorkspaceItem:
        """Assign a workspace item to a folder or move it back to root."""
        item = self.get_item(item_id)
        if item is None:
            raise ValueError(f"Unknown workspace item: {item_id}")
        if folder_id is None:
            folder_id = self.ensure_inbox_folder().id
        target_folder = self.get_folder(folder_id)
        if target_folder is None:
            raise ValueError(f"Unknown workspace folder: {folder_id}")
        if not self._folder_accepts_direct_items(target_folder):
            raise WorkspaceValidationError("invalid_move_target")
        source_folder = self.get_folder(item.folder_id) if item.folder_id else None
        if (
            source_folder is not None
            and getattr(source_folder, "folder_kind", "") in {WORKSPACE_FOLDER_KIND_EVENT, WORKSPACE_FOLDER_KIND_BATCH_TASK}
            and getattr(target_folder, "folder_kind", "") in {WORKSPACE_FOLDER_KIND_USER, WORKSPACE_FOLDER_KIND_INBOX}
            and not self.item_has_text_content(item.id)
        ):
            raise WorkspaceValidationError("invalid_move_target")
        self._ensure_entry_name_available(
            item.title or item.id,
            container_id=folder_id,
            exclude_item_id=item.id,
        )
        previous_folder_id = item.folder_id
        item.folder_id = folder_id
        item.save(self.db)
        self._sync_item_asset_paths(item)
        self._cleanup_empty_folder(previous_folder_id)
        return item

    def copy_item_to_folder(self, item_id: str, target_folder_id: Optional[str] = None, copy_suffix: str = " [Copy]") -> WorkspaceItem:
        """Create a full copy of a workspace item, including its assets, into a target folder."""
        item = self.get_item(item_id)
        if item is None:
            raise ValueError(f"Unknown workspace item: {item_id}")
        if target_folder_id is None:
            target_folder_id = self.ensure_inbox_folder().id
        target_folder = self.get_folder(target_folder_id)
        if target_folder is None:
            raise ValueError(f"Unknown workspace folder: {target_folder_id}")
        if not self._folder_accepts_direct_items(target_folder):
            raise WorkspaceValidationError("invalid_move_target")
        source_folder = self.get_folder(item.folder_id) if item.folder_id else None
        if (
            source_folder is not None
            and getattr(source_folder, "folder_kind", "") in {WORKSPACE_FOLDER_KIND_EVENT, WORKSPACE_FOLDER_KIND_BATCH_TASK}
            and getattr(target_folder, "folder_kind", "") in {WORKSPACE_FOLDER_KIND_USER, WORKSPACE_FOLDER_KIND_INBOX}
            and not self.item_has_text_content(item.id)
        ):
            raise WorkspaceValidationError("invalid_move_target")
        
        base_title = item.title or item.id
        new_title = self._build_unique_entry_name(
            f"{base_title}{copy_suffix}",
            container_id=target_folder_id,
        )
        
        new_item = WorkspaceItem(
            title=new_title,
            item_type=item.item_type,
            folder_id=target_folder_id,
            source_kind=item.source_kind,
            source_event_id=None,
            source_task_id=None,
            status=item.status,
        )
        new_item.save(self.db)
        
        assets = self.get_assets(item_id)
        mapped_primary_audio_asset_id = None
        mapped_primary_text_asset_id = None
        
        for asset in assets:
            new_asset = WorkspaceAsset(
                item_id=new_item.id,
                asset_role=asset.asset_role,
                content_type=asset.content_type,
                metadata_json=asset.metadata_json,
            )
            
            if asset.file_path:
                source_path = Path(asset.file_path).expanduser()
                if source_path.exists():
                    try:
                        if self._asset_has_readable_text(asset):
                            target_path = self._resolve_text_asset_path(
                                new_item,
                                asset.asset_role,
                                filename=self._preferred_text_asset_filename(asset),
                            )
                            self._write_text_file(target_path, self.read_asset_text(asset))
                        else:
                            target_path = self._resolve_attachment_asset_path(
                                new_item,
                                asset.asset_role,
                                source_path.name,
                            )
                            self.file_manager.copy_file(str(source_path), str(target_path), overwrite=True)
                        new_asset.file_path = str(target_path)
                    except Exception as exc:
                        import logging

                        logging.getLogger("echonote.workspace").error(
                            "Failed to copy asset file %s: %s",
                            source_path,
                            exc,
                        )
            
            new_asset.save(self.db)
            
            if asset.id == item.primary_audio_asset_id:
                mapped_primary_audio_asset_id = new_asset.id
            if asset.id == item.primary_text_asset_id:
                mapped_primary_text_asset_id = new_asset.id
                
        if mapped_primary_audio_asset_id or mapped_primary_text_asset_id:
            new_item.primary_audio_asset_id = mapped_primary_audio_asset_id
            new_item.primary_text_asset_id = mapped_primary_text_asset_id
            new_item.save(self.db)
            
        return new_item

    def get_folder_cleanup_summary(self, folder_id: str) -> dict:
        """Summarize folder-linked items/assets for destructive confirmations."""
        folder = self.get_folder(folder_id)
        if folder is None:
            return {
                "folder_id": folder_id,
                "folder_name": "",
                "folder_kind": "",
                "linked_item_count": 0,
                "linked_asset_count": 0,
            }
        items = WorkspaceItem.get_all(self.db, folder_id=folder_id, view_mode=LIBRARY_VIEW_STRUCTURE)
        linked_asset_count = 0
        for item in items:
            linked_asset_count += len(WorkspaceAsset.get_by_item_id(self.db, item.id))
        return {
            "folder_id": folder_id,
            "folder_name": folder.name,
            "folder_kind": getattr(folder, "folder_kind", "") or "",
            "linked_item_count": len(items),
            "linked_asset_count": linked_asset_count,
        }

    def delete_generated_folder(self, folder_id: str, *, delete_files: bool = True) -> int:
        """Delete an auto-generated workspace folder and all items it currently owns."""
        folder = self.get_folder(folder_id)
        if folder is None:
            return 0
        if getattr(folder, "folder_kind", "") != WORKSPACE_FOLDER_KIND_EVENT:
            raise WorkspaceValidationError("folder_not_deletable")
        child_folders = [candidate for candidate in self.list_folders() if candidate.parent_id == folder_id]
        if child_folders:
            raise WorkspaceValidationError("folder_not_empty")
        items = WorkspaceItem.get_all(self.db, folder_id=folder_id, view_mode=LIBRARY_VIEW_STRUCTURE)
        removed_count = 0
        for item in items:
            if self.delete_item(item.id, delete_files=delete_files):
                removed_count += 1
        folder = self.get_folder(folder_id)
        if folder is not None:
            folder.delete(self.db)
        return removed_count

    def get_item(self, item_id: str) -> Optional[WorkspaceItem]:
        """Fetch a workspace item by ID."""
        return WorkspaceItem.get_by_id(self.db, item_id)

    def list_items(
        self,
        *,
        collection: Optional[str] = None,
        item_type: Optional[str] = None,
        view_mode: str = LIBRARY_VIEW_STRUCTURE,
        folder_id: Optional[str] = None,
        event_id: Optional[str] = None,
    ) -> List[WorkspaceItem]:
        """List workspace items for the requested collection."""
        self.normalize_structure_assignments()
        resolved_collection = (collection or "all").strip().lower()
        resolved_item_type = item_type
        status = None
        limit = None

        if resolved_collection == "recordings":
            resolved_item_type = "recording"
        elif resolved_collection == "documents":
            resolved_item_type = "document"
        elif resolved_collection == "orphaned":
            status = "orphaned"
        elif resolved_collection == "recent":
            limit = 10

        return WorkspaceItem.get_all(
            self.db,
            item_type=resolved_item_type,
            status=status,
            folder_id=folder_id if view_mode == LIBRARY_VIEW_STRUCTURE else None,
            source_event_id=event_id if view_mode == LIBRARY_VIEW_EVENT else None,
            view_mode=view_mode,
            limit=limit,
        )

    def normalize_structure_assignments(self) -> None:
        """Hard-switch legacy items into stable structure folders."""
        self.ensure_structure_root_folders()
        folders_by_id = {
            folder.id: folder for folder in self._list_folders_raw()
        }
        items = WorkspaceItem.get_all(self.db)
        for item in items:
            if item.folder_id and item.folder_id in folders_by_id:
                continue
            target_folder_id = self.resolve_default_folder_id(
                event_id=item.source_event_id,
                task_id=item.source_task_id,
            )
            if item.folder_id == target_folder_id:
                continue
            self.db.execute(
                "UPDATE workspace_items SET folder_id = ? WHERE id = ?",
                (target_folder_id, item.id),
                commit=True,
            )

    def get_event_navigation_entries(self) -> list[dict]:
        """Build event-focused navigator entries for workspace event view."""
        rows = self.db.execute(
            """
            SELECT
                wi.source_event_id AS event_id,
                COALESCE(NULLIF(TRIM(ce.title), ''), '') AS event_title,
                COUNT(wi.id) AS item_count,
                MAX(wi.updated_at) AS updated_at
            FROM workspace_items AS wi
            LEFT JOIN calendar_events AS ce ON ce.id = wi.source_event_id
            GROUP BY wi.source_event_id, ce.title
            ORDER BY
                CASE WHEN wi.source_event_id IS NULL THEN 1 ELSE 0 END,
                MAX(wi.updated_at) DESC,
                COALESCE(NULLIF(TRIM(ce.title), ''), wi.source_event_id, '') ASC
            """
        )
        entries: list[dict] = []
        for row in rows:
            event_id = row["event_id"]
            event_title = (row["event_title"] or "").strip()
            entries.append(
                {
                    "event_id": event_id,
                    "event_title": event_title,
                    "item_count": int(row["item_count"] or 0),
                    "updated_at": row["updated_at"] or "",
                }
            )
        return entries

    def get_item_list_metadata(self, items: List[WorkspaceItem]) -> dict[str, dict]:
        """Build lightweight list metadata for workspace items."""
        assets_by_item = self._get_assets_for_item_ids([item.id for item in items])
        folder_names = {folder.id: folder.name for folder in self.list_folders()}
        event_titles = self._get_event_titles(
            [item.source_event_id for item in items if item.source_event_id]
        )
        task_sources = self._get_task_source_map(
            [item.source_task_id for item in items if item.source_task_id]
        )
        metadata_by_item: dict[str, dict] = {}
        for item in items:
            assets = assets_by_item.get(item.id, [])
            task_source = task_sources.get(item.source_task_id or "")
            metadata_by_item[item.id] = {
                "source": item.source_kind or item.item_type,
                "folder_name": folder_names.get(item.folder_id),
                "event_id": item.source_event_id,
                "event_title": event_titles.get(item.source_event_id or ""),
                "task_id": item.source_task_id,
                "original_file_name": self._resolve_original_file_name(
                    item,
                    assets,
                    task_source=task_source,
                ),
                "updated_at": item.updated_at,
                "has_audio": any(asset.asset_role == "audio" for asset in assets),
                "has_text": any(self._asset_has_readable_text(asset) for asset in assets),
                "is_orphaned": item.status == "orphaned",
            }
        return metadata_by_item

    def get_item_context_metadata(self, item_id: str) -> dict:
        """Return normalized metadata used by workspace inspector and editor chrome."""
        item = self.get_item(item_id)
        if item is None:
            return {}
        metadata = self.get_item_list_metadata([item]).get(item.id, {})
        metadata["item_title"] = item.title or item.id
        return metadata

    def get_assets(self, item_id: str, asset_role: Optional[str] = None) -> List[WorkspaceAsset]:
        """List assets for a workspace item."""
        if asset_role:
            return WorkspaceAsset.get_by_item_and_role(self.db, item_id, asset_role)
        return WorkspaceAsset.get_by_item_id(self.db, item_id)

    def get_primary_text_asset(self, item_id: str) -> Optional[WorkspaceAsset]:
        """Return the preferred editable text asset for a workspace item."""
        item = self.get_item(item_id)
        if item is None:
            return None

        if item.primary_text_asset_id:
            primary = WorkspaceAsset.get_by_id(self.db, item.primary_text_asset_id)
            if primary is not None:
                return primary

        for role in ("document_text", "transcript", "summary", "meeting_brief", "translation"):
            assets = self.get_assets(item_id, role)
            if assets:
                return assets[-1]
        return None

    def get_item_text_content(self, item_id: str) -> str:
        """Return the best available editable text for a workspace item."""
        primary_asset = self.get_primary_text_asset(item_id)
        if primary_asset is None:
            return ""
        return self.read_asset_text(primary_asset)

    def item_has_text_content(self, item_id: str) -> bool:
        """Return whether an item has at least one readable text asset."""
        return any(self._asset_has_readable_text(asset) for asset in self.get_assets(item_id))

    def get_folder_filesystem_path(self, folder_id: str) -> Optional[str]:
        """Return the resolved vault directory for a workspace folder."""
        folder = self.get_folder(folder_id)
        if folder is None:
            return None
        return str(self.vault_layout.folder_path(folder, folders_by_id=self._folder_lookup()))

    def get_item_filesystem_path(self, item_id: str) -> Optional[str]:
        """Return the most useful local path for a workspace item."""
        item = self.get_item(item_id)
        if item is None:
            return None
        primary_text_asset = self.get_primary_text_asset(item_id)
        if primary_text_asset is not None and primary_text_asset.file_path:
            return primary_text_asset.file_path
        primary_audio_asset_id = getattr(item, "primary_audio_asset_id", None)
        if primary_audio_asset_id:
            audio_asset = WorkspaceAsset.get_by_id(self.db, primary_audio_asset_id)
            if audio_asset is not None and audio_asset.file_path:
                return audio_asset.file_path
        assets = self.get_assets(item_id)
        if assets:
            if assets[0].file_path:
                return assets[0].file_path
        return str(self.vault_layout.item_asset_directory(item, folders_by_id=self._folder_lookup()))

    def read_asset_text(self, asset: WorkspaceAsset | None) -> str:
        """Read text content from a workspace asset."""
        if asset is None:
            return ""
        if asset.file_path:
            asset_path = Path(asset.file_path).expanduser()
            if asset_path.exists():
                return asset_path.read_text(encoding="utf-8")
        if asset.text_content:
            return asset.text_content
        return ""

    def update_text_asset(self, asset_id: str, text_content: str) -> WorkspaceAsset:
        """Update an existing text asset in place and persist file changes."""
        asset = WorkspaceAsset.get_by_id(self.db, asset_id)
        if asset is None:
            raise ValueError(f"Unknown workspace asset: {asset_id}")

        item = self.get_item(asset.item_id)
        if item is None:
            raise ValueError(f"Unknown workspace item for asset: {asset_id}")

        previous_path = str(asset.file_path or "").strip()
        target_path = self._resolve_text_asset_path(
            item,
            asset.asset_role,
            filename=self._preferred_text_asset_filename(asset),
        )
        self._write_text_file(target_path, text_content)
        if previous_path and previous_path != str(target_path):
            self._delete_owned_file(previous_path)

        asset.file_path = str(target_path)
        asset.text_content = None
        asset.content_type = self._guess_content_type(target_path)
        asset.metadata_json = json.dumps({"size_bytes": target_path.stat().st_size})
        asset.save(self.db)
        self._sync_primary_asset_refs(item)
        return WorkspaceAsset.get_by_id(self.db, asset.id) or asset

    def save_text_asset(
        self,
        item_id: str,
        asset_role: str,
        text_content: str,
        *,
        filename: Optional[str] = None,
        subfolder: str = "ai",
    ) -> WorkspaceAsset:
        """Persist generated text under a workspace item and upsert the matching asset."""
        item = self.get_item(item_id)
        if item is None:
            raise ValueError(f"Unknown workspace item: {item_id}")

        _ = filename, subfolder
        file_path = self._resolve_text_asset_path(item, asset_role, filename=filename)
        self._write_text_file(file_path, text_content)
        asset = self._save_asset(
            item,
            asset_role,
            file_path=str(file_path),
            text_content=None,
            metadata_json=json.dumps({"size_bytes": file_path.stat().st_size}),
        )
        self._sync_primary_asset_refs(item)
        return asset

    def generate_summary(self, item_id: str, strategy: Optional[str] = None) -> dict:
        """Generate and persist a summary for a workspace item."""
        from core.workspace.summary_service import SummaryService

        service = SummaryService(
            self,
            settings_manager=self.settings_manager,
            model_manager=self.model_manager,
        )
        return service.summarize(item_id, strategy=strategy)

    def generate_meeting_brief(self, item_id: str, template: Optional[str] = None) -> dict:
        """Generate and persist a structured meeting brief for a workspace item."""
        from core.workspace.meeting_brief_service import MeetingBriefService

        service = MeetingBriefService(
            self,
            settings_manager=self.settings_manager,
            model_manager=self.model_manager,
        )
        return service.generate(item_id, template=template)

    def publish_transcription_task(
        self,
        task,
        *,
        transcript_path: Optional[str] = None,
        translation_path: Optional[str] = None,
        event_id: Optional[str] = None,
        replace_existing: bool = False,
    ) -> str:
        """Publish a completed transcription task into the unified workspace."""
        existing_item = self._get_item_by_source_task_id(getattr(task, "id", None)) if getattr(task, "id", None) else None
        item = self._resolve_transcription_item(task, event_id=event_id, replace_existing=replace_existing)
        item.item_type = "recording"
        item.folder_id = item.folder_id or self.resolve_default_folder_id(
            event_id=event_id,
            task_id=getattr(task, "id", None),
        )
        item.source_kind = "batch_transcription"
        item.source_task_id = getattr(task, "id", None)
        item.source_event_id = event_id or item.source_event_id
        item.status = getattr(task, "status", "completed") or "completed"
        if existing_item is None:
            item.title = self._build_unique_entry_name(item.title, container_id=item.folder_id)
        item.save(self.db)

        audio_asset = self._upsert_file_asset(item, "audio", getattr(task, "file_path", None))
        transcript_asset = self._upsert_text_asset(item, "transcript", transcript_path)
        self._upsert_text_asset(item, "translation", translation_path)

        if audio_asset is not None:
            item.primary_audio_asset_id = audio_asset.id
        if transcript_asset is not None:
            item.primary_text_asset_id = transcript_asset.id
        self._sync_primary_asset_refs(
            item,
            preferred_text_asset_id=transcript_asset.id if transcript_asset else None,
            preferred_audio_asset_id=audio_asset.id if audio_asset else None,
        )
        return item.id

    def publish_recording_session(self, recording_result: dict) -> str:
        """Publish a realtime recording session and its artifacts to workspace."""
        event_id = recording_result.get("event_id")
        existing_item = self._get_latest_item_for_event(event_id) if event_id else None
        item = self._resolve_recording_item(recording_result, event_id=event_id)
        item.item_type = "recording"
        item.folder_id = item.folder_id or self.resolve_default_folder_id(event_id=event_id)
        item.source_kind = "realtime_recording"
        item.source_event_id = event_id or item.source_event_id
        item.status = "completed"
        if existing_item is None:
            item.title = self._build_unique_entry_name(item.title, container_id=item.folder_id)
        item.save(self.db)

        audio_asset = self._upsert_file_asset(item, "audio", recording_result.get("recording_path"))
        transcript_asset = self._upsert_text_asset(item, "transcript", recording_result.get("transcript_path"))
        self._upsert_text_asset(item, "translation", recording_result.get("translation_path"))
        self._upsert_text_asset(item, "outline", recording_result.get("markers_path"))

        if audio_asset is not None:
            item.primary_audio_asset_id = audio_asset.id
        if transcript_asset is not None:
            item.primary_text_asset_id = transcript_asset.id
        self._sync_primary_asset_refs(
            item,
            preferred_text_asset_id=transcript_asset.id if transcript_asset else None,
            preferred_audio_asset_id=audio_asset.id if audio_asset else None,
        )
        return item.id

    def get_event_artifacts(self, event_id: str) -> dict:
        """Return the latest workspace-backed artifacts for a calendar event."""
        return self.get_event_artifacts_map([event_id]).get(
            event_id,
            self._empty_artifacts_payload(),
        )

    def get_event_item_id(self, event_id: str) -> Optional[str]:
        """Return the latest workspace item identifier for an event."""
        item = self._get_latest_item_for_event(event_id)
        return item.id if item is not None else None

    def get_item_id_by_task_id(self, task_id: str) -> Optional[str]:
        """Return the latest workspace item identifier for a transcription task."""
        item = self._get_item_by_source_task_id(task_id)
        return item.id if item is not None else None

    def find_item_id_by_asset_path(self, file_path: Optional[str]) -> Optional[str]:
        """Resolve a workspace item identifier from an asset file path."""
        if not file_path:
            return None
        normalized_path = str(Path(file_path).expanduser())
        rows = self.db.execute(
            """
            SELECT wi.id
            FROM workspace_assets AS wa
            JOIN workspace_items AS wi ON wi.id = wa.item_id
            WHERE wa.file_path = ?
            ORDER BY wi.updated_at DESC
            LIMIT 1
            """,
            (normalized_path,),
        )
        if not rows:
            return None
        return rows[0]["id"]

    def get_event_artifacts_map(self, event_ids: List[str]) -> dict[str, dict]:
        """Return latest workspace-backed artifacts for multiple calendar events."""
        unique_event_ids = [event_id for event_id in dict.fromkeys(event_ids) if event_id]
        if not unique_event_ids:
            return {}

        placeholders = ", ".join(["?"] * len(unique_event_ids))
        rows = self.db.execute(
            "SELECT * FROM workspace_items WHERE source_event_id IN (" + placeholders + ") ORDER BY updated_at DESC",
            tuple(unique_event_ids),
        )

        latest_items: dict[str, WorkspaceItem] = {}
        for row in rows:
            item = WorkspaceItem.from_db_row(row)
            if item.source_event_id and item.source_event_id not in latest_items:
                latest_items[item.source_event_id] = item

        item_ids = [item.id for item in latest_items.values()]
        assets_by_item = self._get_assets_for_item_ids(item_ids)

        artifacts_map: dict[str, dict] = {}
        for event_id in unique_event_ids:
            item = latest_items.get(event_id)
            if item is None:
                artifacts_map[event_id] = self._empty_artifacts_payload()
                continue
            artifacts_map[event_id] = self._build_artifacts_from_assets(assets_by_item.get(item.id, []))

        return artifacts_map

    def get_event_asset_path(self, event_id: str, asset_role: str) -> Optional[str]:
        """Resolve a workspace asset path for a calendar event."""
        item = self._get_latest_item_for_event(event_id)
        if item is None:
            return None
        assets = WorkspaceAsset.get_by_item_and_role(self.db, item.id, asset_role)
        if not assets:
            return None
        return assets[-1].file_path

    def read_event_text_asset(self, event_id: str, asset_role: str) -> str:
        """Read text content for an event-scoped workspace asset."""
        item = self._get_latest_item_for_event(event_id)
        if item is None:
            return ""
        assets = WorkspaceAsset.get_by_item_and_role(self.db, item.id, asset_role)
        if not assets:
            return ""
        return self.read_asset_text(assets[-1])

    def has_event_asset_role(self, event_id: str, asset_role: str) -> bool:
        """Return whether an event currently has a workspace asset for role."""
        return bool(self.get_event_asset_path(event_id, asset_role))

    def publish_event_text_asset(
        self,
        event_id: str,
        asset_role: str,
        file_path: str,
        *,
        title: Optional[str] = None,
    ) -> Optional[str]:
        """Upsert a text asset for an event-scoped workspace item."""
        if not event_id or not file_path:
            return None
        item = self._get_latest_item_for_event(event_id)
        if item is None:
            folder_id = self.resolve_default_folder_id(event_id=event_id)
            item = WorkspaceItem(
                title=title or Path(file_path).stem or asset_role,
                item_type="recording",
                folder_id=folder_id,
                source_kind="ai_generated",
                source_event_id=event_id,
                status="completed",
            )
            item.title = self._build_unique_entry_name(item.title, container_id=folder_id)
        item.save(self.db)
        asset = self._upsert_text_asset(item, asset_role, file_path)
        if asset is None:
            return None
        self._sync_primary_asset_refs(
            item,
            preferred_text_asset_id=asset.id if asset_role == "transcript" else None,
        )
        return asset.id

    def remove_event_asset_role(self, event_id: str, asset_role: str) -> bool:
        """Remove workspace asset rows for a given event and role."""
        item = self._get_latest_item_for_event(event_id)
        if item is None:
            return False
        removed = False
        for asset in WorkspaceAsset.get_by_item_and_role(self.db, item.id, asset_role):
            asset.delete(self.db)
            removed = True
        if removed:
            self._sync_primary_asset_refs(item)
        return removed

    def get_event_cleanup_summary(self, event_id: str) -> dict:
        """Summarize workspace items/assets linked to an event for delete confirmation."""
        items = self._get_items_for_event(event_id)
        assets = []
        for item in items:
            assets.extend(WorkspaceAsset.get_by_item_id(self.db, item.id))

        asset_roles = sorted({asset.asset_role for asset in assets if asset.asset_role})
        return {
            "event_id": event_id,
            "has_workspace_assets": bool(assets),
            "linked_item_count": len(items),
            "linked_asset_count": len(assets),
            "asset_roles": asset_roles,
        }

    def delete_event_items(self, event_id: str, *, delete_files: bool = True) -> int:
        """Delete workspace items and assets linked to an event."""
        removed_count = 0
        for item in self._get_items_for_event(event_id):
            for asset in WorkspaceAsset.get_by_item_id(self.db, item.id):
                if delete_files:
                    self._delete_asset_file(asset)
                asset.delete(self.db)
            item.delete(self.db)
            removed_count += 1
        return removed_count

    def detach_event_items(self, event_id: str) -> int:
        """Preserve workspace items while removing their event linkage."""
        detached_count = 0
        for item in self._get_items_for_event(event_id):
            if item.source_event_id != event_id:
                continue
            item.source_event_id = None
            item.status = "orphaned"
            item.save(self.db)
            detached_count += 1
        return detached_count

    def _resolve_transcription_item(
        self,
        task,
        *,
        event_id: Optional[str],
        replace_existing: bool,
    ) -> WorkspaceItem:
        if replace_existing and event_id:
            existing = self._get_latest_item_for_event(event_id)
            if existing is not None:
                return existing

        task_id = getattr(task, "id", None)
        if task_id:
            existing = self._get_item_by_source_task_id(task_id)
            if existing is not None:
                return existing

        title = Path(getattr(task, "file_path", "") or getattr(task, "file_name", "transcript")).stem
        return WorkspaceItem(
            title=title or getattr(task, "file_name", "transcript"),
            item_type="recording",
        )

    def _resolve_recording_item(self, recording_result: dict, *, event_id: Optional[str]) -> WorkspaceItem:
        if event_id:
            existing = self._get_latest_item_for_event(event_id)
            if existing is not None:
                return existing

        recording_path = Path(recording_result.get("recording_path") or "recording")
        title = recording_path.stem
        if not title and recording_result.get("start_time"):
            title = f"recording_{recording_result['start_time']}"
        return WorkspaceItem(title=title or "recording", item_type="recording")

    def _ensure_system_root_folder(self, *, name: str) -> WorkspaceFolder:
        """Return or create a singleton top-level system root folder."""
        return self._ensure_special_folder(
            name=name,
            folder_kind=WORKSPACE_FOLDER_KIND_SYSTEM_ROOT,
        )

    def _ensure_special_folder(self, *, name: str, folder_kind: str) -> WorkspaceFolder:
        """Return or create a singleton top-level folder for system-owned content."""
        for folder in self._list_folders_raw():
            if (
                folder.folder_kind == folder_kind
                and folder.name == name
                and folder.parent_id is None
                and folder.source_event_id is None
            ):
                return folder

        folder = WorkspaceFolder(
            name=name,
            parent_id=None,
            folder_kind=folder_kind,
        )
        folder.save(self.db)
        return folder

    def _list_folders_raw(self) -> List[WorkspaceFolder]:
        """List folders without triggering structure normalization."""
        return WorkspaceFolder.get_all(self.db)

    def _resolve_event_folder_name(self, event_id: str) -> str:
        """Build a stable folder label for an event-backed workspace group."""
        event_rows = self.db.execute(
            "SELECT title FROM calendar_events WHERE id = ? LIMIT 1",
            (event_id,),
        )
        if event_rows:
            title = (event_rows[0]["title"] or "").strip()
            if title:
                return self._build_unique_entry_name(
                    title,
                    container_id=self.ensure_event_root_folder().id,
                )
        return self._build_unique_entry_name(
            f"事件 {event_id}",
            container_id=self.ensure_event_root_folder().id,
        )

    @staticmethod
    def _normalize_entry_name(name: str) -> str:
        return str(name or "").strip()

    def _build_unique_entry_name(
        self,
        preferred_name: str,
        *,
        container_id: Optional[str],
        exclude_item_id: Optional[str] = None,
        exclude_folder_id: Optional[str] = None,
    ) -> str:
        base_name = self._normalize_entry_name(preferred_name) or "Untitled"
        existing_names = self._list_entry_names(
            container_id,
            exclude_item_id=exclude_item_id,
            exclude_folder_id=exclude_folder_id,
        )
        lower_names = {name.lower() for name in existing_names}
        if base_name.lower() not in lower_names:
            return base_name
        suffix = 2
        while True:
            candidate = f"{base_name} {suffix}"
            if candidate.lower() not in lower_names:
                return candidate
            suffix += 1

    def _ensure_entry_name_available(
        self,
        name: str,
        *,
        container_id: Optional[str],
        exclude_item_id: Optional[str] = None,
        exclude_folder_id: Optional[str] = None,
    ) -> None:
        normalized_name = self._normalize_entry_name(name)
        if not normalized_name:
            raise WorkspaceValidationError("empty_name")
        existing_names = self._list_entry_names(
            container_id,
            exclude_item_id=exclude_item_id,
            exclude_folder_id=exclude_folder_id,
        )
        if normalized_name.lower() in {existing_name.lower() for existing_name in existing_names}:
            raise WorkspaceValidationError("duplicate_name")

    @staticmethod
    def _folder_accepts_direct_items(folder: WorkspaceFolder) -> bool:
        folder_kind = getattr(folder, "folder_kind", "") or ""
        return folder_kind in {
            WORKSPACE_FOLDER_KIND_USER,
            WORKSPACE_FOLDER_KIND_INBOX,
        }

    def _cleanup_empty_folder(self, folder_id: Optional[str]) -> None:
        if not folder_id:
            return
        folder = self.get_folder(folder_id)
        if folder is None:
            return
        if getattr(folder, "folder_kind", "") != WORKSPACE_FOLDER_KIND_EVENT:
            return
        has_child_folders = any(candidate.parent_id == folder.id for candidate in self._list_folders_raw())
        has_items = bool(
            self.db.execute(
                "SELECT id FROM workspace_items WHERE folder_id = ? LIMIT 1",
                (folder.id,),
            )
        )
        if has_child_folders or has_items:
            return
        folder.delete(self.db)

    def _list_entry_names(
        self,
        container_id: Optional[str],
        *,
        exclude_item_id: Optional[str] = None,
        exclude_folder_id: Optional[str] = None,
    ) -> list[str]:
        item_rows = self.db.execute(
            """
            SELECT title AS name
            FROM workspace_items
            WHERE ((folder_id = ?) OR (folder_id IS NULL AND ? IS NULL))
              AND (? IS NULL OR id != ?)
            """,
            (container_id, container_id, exclude_item_id, exclude_item_id),
        )
        folder_rows = self.db.execute(
            """
            SELECT name
            FROM workspace_folders
            WHERE ((parent_id = ?) OR (parent_id IS NULL AND ? IS NULL))
              AND (? IS NULL OR id != ?)
            """,
            (container_id, container_id, exclude_folder_id, exclude_folder_id),
        )
        names = [str(row["name"] or "").strip() for row in item_rows + folder_rows]
        return [name for name in names if name]

    def _get_item_by_source_task_id(self, task_id: str) -> Optional[WorkspaceItem]:
        rows = self.db.execute(
            "SELECT * FROM workspace_items WHERE source_task_id = ? ORDER BY updated_at DESC",
            (task_id,),
        )
        if rows:
            return WorkspaceItem.from_db_row(rows[0])
        return None

    def _get_latest_item_for_event(self, event_id: str) -> Optional[WorkspaceItem]:
        rows = self.db.execute(
            "SELECT * FROM workspace_items WHERE source_event_id = ? ORDER BY updated_at DESC",
            (event_id,),
        )
        if rows:
            return WorkspaceItem.from_db_row(rows[0])
        return None

    def _get_items_for_event(self, event_id: str) -> List[WorkspaceItem]:
        rows = self.db.execute(
            "SELECT * FROM workspace_items WHERE source_event_id = ? ORDER BY updated_at DESC",
            (event_id,),
        )
        return [WorkspaceItem.from_db_row(row) for row in rows]

    def _get_assets_for_item_ids(self, item_ids: List[str]) -> dict[str, List[WorkspaceAsset]]:
        if not item_ids:
            return {}
        placeholders = ", ".join(["?"] * len(item_ids))
        rows = self.db.execute(
            "SELECT * FROM workspace_assets WHERE item_id IN (" + placeholders + ") ORDER BY created_at",
            tuple(item_ids),
        )
        assets_by_item: dict[str, List[WorkspaceAsset]] = {}
        for row in rows:
            asset = WorkspaceAsset.from_db_row(row)
            assets_by_item.setdefault(asset.item_id, []).append(asset)
        return assets_by_item

    def _get_event_titles(self, event_ids: List[str]) -> dict[str, str]:
        unique_event_ids = [event_id for event_id in dict.fromkeys(event_ids) if event_id]
        if not unique_event_ids:
            return {}
        placeholders = ", ".join(["?"] * len(unique_event_ids))
        rows = self.db.execute(
            "SELECT id, title FROM calendar_events WHERE id IN (" + placeholders + ")",
            tuple(unique_event_ids),
        )
        return {row["id"]: (row["title"] or "").strip() for row in rows}

    def _get_task_source_map(self, task_ids: List[str]) -> dict[str, dict]:
        unique_task_ids = [task_id for task_id in dict.fromkeys(task_ids) if task_id]
        if not unique_task_ids:
            return {}
        placeholders = ", ".join(["?"] * len(unique_task_ids))
        rows = self.db.execute(
            "SELECT id, file_name, file_path FROM transcription_tasks WHERE id IN ("
            + placeholders
            + ")",
            tuple(unique_task_ids),
        )
        return {
            row["id"]: {
                "file_name": row["file_name"],
                "file_path": row["file_path"],
            }
            for row in rows
        }

    def _resolve_text_asset_path(
        self,
        item: WorkspaceItem,
        asset_role: str,
        *,
        filename: Optional[str] = None,
    ) -> Path:
        return self.vault_layout.text_asset_path(
            item,
            asset_role=asset_role,
            folders_by_id=self._folder_lookup(),
            filename=filename,
        )

    def _resolve_attachment_asset_path(
        self,
        item: WorkspaceItem,
        asset_role: str,
        source_filename: str,
    ) -> Path:
        return self.vault_layout.file_asset_path(
            item,
            asset_role=asset_role,
            original_name=source_filename,
            folders_by_id=self._folder_lookup(),
        )

    @staticmethod
    def _asset_has_readable_text(asset: WorkspaceAsset) -> bool:
        if asset.asset_role in TEXT_ASSET_ROLE_PRIORITY:
            return True
        content_type = str(getattr(asset, "content_type", "") or "").lower()
        if content_type.startswith("text/"):
            return True
        suffix = Path(str(getattr(asset, "file_path", "") or "")).suffix.lower()
        return suffix in {".md", ".txt", ".srt"}

    def _write_text_file(self, target_path: Path, text_content: str) -> None:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(text_content, encoding="utf-8")

    def _delete_owned_file(self, file_path: Optional[str]) -> None:
        if not file_path:
            return
        path = Path(file_path).expanduser()
        if not self.vault_layout.contains_path(path):
            return
        if path.exists() and path.is_file():
            self.file_manager.delete_file(str(path))

    def _sync_item_asset_paths(self, item: WorkspaceItem) -> None:
        stale_directories: list[Path] = []
        for asset in WorkspaceAsset.get_by_item_id(self.db, item.id):
            previous_path = Path(asset.file_path).expanduser() if asset.file_path else None
            if self._asset_has_readable_text(asset):
                target_path = self._resolve_text_asset_path(
                    item,
                    asset.asset_role,
                    filename=self._preferred_text_asset_filename(asset),
                )
                if previous_path and previous_path.exists():
                    if previous_path != target_path:
                        self.file_manager.move_file(str(previous_path), str(target_path), overwrite=True)
                        stale_directories.append(previous_path.parent)
                else:
                    self._write_text_file(target_path, self.read_asset_text(asset))
                asset.file_path = str(target_path)
                asset.text_content = None
                asset.content_type = self._guess_content_type(target_path)
                asset.metadata_json = json.dumps({"size_bytes": target_path.stat().st_size})
                asset.save(self.db)
                continue

            if previous_path is None:
                continue
            target_path = self._resolve_attachment_asset_path(
                item,
                asset.asset_role,
                previous_path.name,
            )
            if previous_path.exists() and previous_path != target_path:
                self.file_manager.move_file(str(previous_path), str(target_path), overwrite=True)
                stale_directories.append(previous_path.parent)
            elif not previous_path.exists():
                continue
            asset.file_path = str(target_path)
            asset.content_type = self._guess_content_type(target_path)
            asset.metadata_json = json.dumps({"size_bytes": target_path.stat().st_size})
            asset.save(self.db)

        self._prune_empty_vault_directories(stale_directories)

    def _sync_folder_tree_asset_paths(self, folder_id: str) -> None:
        for item in self._list_items_in_folder_subtree(folder_id):
            self._sync_item_asset_paths(item)

    def _list_items_in_folder_subtree(self, folder_id: str) -> list[WorkspaceItem]:
        subtree_folder_ids = self._folder_subtree_ids(folder_id)
        if not subtree_folder_ids:
            return []
        placeholders = ", ".join(["?"] * len(subtree_folder_ids))
        rows = self.db.execute(
            "SELECT * FROM workspace_items WHERE folder_id IN (" + placeholders + ") ORDER BY updated_at DESC",
            tuple(subtree_folder_ids),
        )
        return [WorkspaceItem.from_db_row(row) for row in rows]

    def _folder_subtree_ids(self, folder_id: str) -> list[str]:
        folders = self._list_folders_raw()
        child_map: dict[str, list[str]] = {}
        for folder in folders:
            if folder.parent_id:
                child_map.setdefault(folder.parent_id, []).append(folder.id)

        queue = [folder_id]
        ordered_ids: list[str] = []
        while queue:
            current_id = queue.pop(0)
            ordered_ids.append(current_id)
            queue.extend(child_map.get(current_id, []))
        return ordered_ids

    def _prune_empty_vault_directories(self, directories: list[Path]) -> None:
        seen: set[Path] = set()
        vault_root = self.vault_layout.vault_root.resolve(strict=False)
        for directory in directories:
            current = directory.resolve(strict=False)
            if not current.is_relative_to(vault_root):
                continue
            while current not in seen and current != vault_root:
                seen.add(current)
                if not current.exists() or not current.is_dir():
                    break
                try:
                    next(current.iterdir())
                except StopIteration:
                    current.rmdir()
                    current = current.parent.resolve(strict=False)
                    continue
                break

    def _folder_lookup(self) -> dict[str, WorkspaceFolder]:
        return {folder.id: folder for folder in self._list_folders_raw()}

    @staticmethod
    def _preferred_text_asset_filename(asset: WorkspaceAsset) -> Optional[str]:
        if asset.asset_role == "document_text" or not asset.file_path:
            return None
        return Path(asset.file_path).name

    def _resolve_original_file_name(
        self,
        item: WorkspaceItem,
        assets: List[WorkspaceAsset],
        *,
        task_source: Optional[dict] = None,
    ) -> str:
        if task_source:
            file_name = str(task_source.get("file_name") or "").strip()
            if file_name:
                return file_name
            file_path = str(task_source.get("file_path") or "").strip()
            if file_path:
                return Path(file_path).name
        for preferred_role in ("audio", "document_text", "transcript", "translation"):
            asset = next((candidate for candidate in assets if candidate.asset_role == preferred_role), None)
            if asset is not None and asset.file_path:
                return Path(asset.file_path).name
        return ""

    def _upsert_file_asset(
        self, item: WorkspaceItem, asset_role: str, file_path: Optional[str]
    ) -> Optional[WorkspaceAsset]:
        if not file_path:
            return None
        source_path = Path(file_path).expanduser()
        if not source_path.exists():
            return None
        target_path = self._resolve_attachment_asset_path(item, asset_role, source_path.name)
        if source_path != target_path:
            self.file_manager.copy_file(str(source_path), str(target_path), overwrite=True)
        return self._save_asset(
            item,
            asset_role,
            file_path=str(target_path),
            text_content=None,
            metadata_json=json.dumps({"size_bytes": target_path.stat().st_size}),
        )

    def _upsert_text_asset(
        self, item: WorkspaceItem, asset_role: str, file_path: Optional[str]
    ) -> Optional[WorkspaceAsset]:
        if not file_path:
            return None
        source_path = Path(file_path).expanduser()
        if not source_path.exists():
            return None
        text_content = source_path.read_text(encoding="utf-8")
        target_path = self._resolve_text_asset_path(item, asset_role)
        self._write_text_file(target_path, text_content)
        return self._save_asset(
            item,
            asset_role,
            file_path=str(target_path),
            text_content=None,
            metadata_json=json.dumps({"size_bytes": target_path.stat().st_size}),
        )

    def _save_asset(
        self,
        item: WorkspaceItem,
        asset_role: str,
        *,
        file_path: str,
        text_content: Optional[str],
        metadata_json: Optional[str] = None,
    ) -> WorkspaceAsset:
        existing_assets = WorkspaceAsset.get_by_item_and_role(self.db, item.id, asset_role)
        asset = existing_assets[-1] if existing_assets else WorkspaceAsset(item_id=item.id, asset_role=asset_role)
        previous_path = str(asset.file_path or "").strip()
        asset.file_path = file_path
        asset.text_content = None if asset.asset_role in TEXT_ASSET_ROLE_PRIORITY else text_content
        asset.metadata_json = metadata_json
        asset.content_type = self._guess_content_type(Path(file_path))
        asset.save(self.db)
        if previous_path and previous_path != file_path:
            self._delete_owned_file(previous_path)
        return asset

    def _sync_primary_asset_refs(
        self,
        item: WorkspaceItem,
        *,
        preferred_text_asset_id: Optional[str] = None,
        preferred_audio_asset_id: Optional[str] = None,
    ) -> None:
        assets = WorkspaceAsset.get_by_item_id(self.db, item.id)
        item.primary_text_asset_id = self._select_primary_text_asset_id(
            assets,
            preferred_asset_id=preferred_text_asset_id or item.primary_text_asset_id,
        )
        item.primary_audio_asset_id = self._select_primary_audio_asset_id(
            assets,
            preferred_asset_id=preferred_audio_asset_id or item.primary_audio_asset_id,
        )
        item.save(self.db)

    def _select_primary_text_asset_id(
        self,
        assets: List[WorkspaceAsset],
        *,
        preferred_asset_id: Optional[str] = None,
    ) -> Optional[str]:
        if preferred_asset_id and any(
            asset.id == preferred_asset_id and asset.asset_role in TEXT_ASSET_ROLE_PRIORITY
            for asset in assets
        ):
            return preferred_asset_id

        ranked_assets = [
            asset
            for asset in assets
            if asset.asset_role in TEXT_ASSET_ROLE_PRIORITY
        ]
        if not ranked_assets:
            return None
        ranked_assets.sort(
            key=lambda asset: (
                TEXT_ASSET_ROLE_PRIORITY.get(asset.asset_role, 999),
                asset.created_at or "",
            )
        )
        return ranked_assets[0].id

    def _select_primary_audio_asset_id(
        self,
        assets: List[WorkspaceAsset],
        *,
        preferred_asset_id: Optional[str] = None,
    ) -> Optional[str]:
        if preferred_asset_id and any(
            asset.id == preferred_asset_id and asset.asset_role == "audio" for asset in assets
        ):
            return preferred_asset_id

        audio_assets = [asset for asset in assets if asset.asset_role == "audio"]
        if not audio_assets:
            return None
        return audio_assets[-1].id

    def _delete_asset_file(self, asset: WorkspaceAsset) -> None:
        if not asset.file_path:
            return
        try:
            if self.file_manager:
                self.file_manager.delete_file(asset.file_path)
                return
            path = Path(asset.file_path).expanduser()
            if path.exists():
                path.unlink()
        except FileNotFoundError:
            return

    def _build_artifacts_from_assets(self, assets: List[WorkspaceAsset]) -> dict:
        recording = None
        transcript = None
        translation = None
        for asset in assets:
            if asset.asset_role == "audio":
                recording = asset.file_path
            elif asset.asset_role == "transcript":
                transcript = asset.file_path
            elif asset.asset_role == "translation":
                translation = asset.file_path

        return {
            "recording": recording,
            "transcript": transcript,
            "translation": translation,
            "attachments": [
                {
                    "id": asset.id,
                    "type": asset.asset_role,
                    "path": asset.file_path,
                    "size": self._extract_size(asset.metadata_json),
                    "created_at": asset.created_at,
                    "text_content": self.read_asset_text(asset) if self._asset_has_readable_text(asset) else None,
                }
                for asset in assets
            ],
        }

    def _guess_content_type(self, path: Path) -> str:
        suffix = path.suffix.lower()
        if suffix == ".wav":
            return "audio/wav"
        if suffix == ".mp3":
            return "audio/mpeg"
        if suffix == ".md":
            return "text/markdown"
        if suffix == ".srt":
            return "application/x-subrip"
        if suffix == ".txt":
            return "text/plain"
        if suffix == ".pdf":
            return "application/pdf"
        if suffix == ".docx":
            return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        guessed, _ = mimetypes.guess_type(str(path))
        return guessed or "application/octet-stream"

    def _extract_size(self, metadata_json: Optional[str]) -> Optional[int]:
        if not metadata_json:
            return None
        try:
            metadata = json.loads(metadata_json)
        except json.JSONDecodeError:
            return None
        size = metadata.get("size_bytes")
        return int(size) if isinstance(size, (int, float)) else None

    def _empty_artifacts_payload(self) -> dict:
        return {"recording": None, "transcript": None, "translation": None, "attachments": []}
