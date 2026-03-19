# SPDX-License-Identifier: Apache-2.0
"""Workspace vault path planning for tree-aligned files and folders."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping, Optional

from data.database.models import WorkspaceFolder, WorkspaceItem

FOLDER_KIND_INBOX = "inbox"
TEXT_ROLE_FILE_NAMES = {
    "transcript": "Transcript.md",
    "translation": "Translation.md",
    "summary": "Summary.md",
    "meeting_brief": "Meeting Brief.md",
    "decisions": "Decisions.md",
    "action_items": "Action Items.md",
    "next_steps": "Next Steps.md",
    "outline": "Outline.md",
}


class WorkspaceVaultLayout:
    """Resolve canonical file-system paths for workspace folders and assets."""

    def __init__(self, vault_root: str | Path):
        self.vault_root = Path(vault_root).expanduser()

    def folder_path(
        self,
        folder: Optional[WorkspaceFolder],
        *,
        folders_by_id: Mapping[str, WorkspaceFolder],
    ) -> Path:
        """Return the vault directory for a workspace folder."""
        if folder is None:
            return self.vault_root / "工作台条目"
        if folder.folder_kind == "inbox":
            return self.vault_root / "工作台条目"
        if folder.folder_kind == "batch_task":
            return self.vault_root / "批量任务"
        if folder.parent_id:
            parent = folders_by_id.get(folder.parent_id)
            return self.folder_path(parent, folders_by_id=folders_by_id) / self._segment(folder.name)
        if folder.folder_kind == "user":
            return self.vault_root / "工作台条目" / self._segment(folder.name)
        return self.vault_root / self._segment(folder.name or "工作台条目")

    def document_text_path(
        self,
        item: WorkspaceItem,
        *,
        folders_by_id: Mapping[str, WorkspaceFolder],
    ) -> Path:
        """Return the canonical markdown file path for a note-like item."""
        folder = folders_by_id.get(item.folder_id) if item.folder_id else None
        return self.folder_path(folder, folders_by_id=folders_by_id) / self._document_filename(item)

    def item_asset_directory(
        self,
        item: WorkspaceItem,
        *,
        folders_by_id: Mapping[str, WorkspaceFolder],
    ) -> Path:
        """Return the support directory for multi-asset workspace items."""
        folder = folders_by_id.get(item.folder_id) if item.folder_id else None
        if folder is not None and folder.folder_kind == "event" and self._segment(folder.name) == self._segment(item.title or item.id):
            return self.folder_path(folder, folders_by_id=folders_by_id)
        return self.folder_path(folder, folders_by_id=folders_by_id) / self._segment(item.title or item.id)

    def text_asset_path(
        self,
        item: WorkspaceItem,
        asset_role: str,
        *,
        folders_by_id: Mapping[str, WorkspaceFolder],
        filename: Optional[str] = None,
    ) -> Path:
        """Return the canonical markdown path for a text asset role."""
        if asset_role == "document_text":
            return self.document_text_path(item, folders_by_id=folders_by_id)
        asset_filename = filename or TEXT_ROLE_FILE_NAMES.get(asset_role, f"{asset_role}.md")
        asset_name = Path(asset_filename).name
        if not asset_name.lower().endswith(".md"):
            asset_name = f"{Path(asset_name).stem}.md"
        return self.item_asset_directory(item, folders_by_id=folders_by_id) / asset_name

    def file_asset_path(
        self,
        item: WorkspaceItem,
        asset_role: str,
        original_name: str,
        *,
        folders_by_id: Mapping[str, WorkspaceFolder],
    ) -> Path:
        """Return the canonical path for copied non-text assets owned by the vault."""
        safe_name = Path(original_name or asset_role).name or asset_role
        if asset_role == "source_document":
            folder = folders_by_id.get(item.folder_id) if item.folder_id else None
            source_dir = self.folder_path(folder, folders_by_id=folders_by_id) / f"{self._segment(item.title or item.id)}.assets"
            return source_dir / safe_name
        return self.item_asset_directory(item, folders_by_id=folders_by_id) / safe_name

    def contains_path(self, file_path: str | Path) -> bool:
        """Return whether a path belongs to the active vault root."""
        try:
            return Path(file_path).expanduser().resolve().is_relative_to(self.vault_root.resolve())
        except FileNotFoundError:
            return Path(file_path).expanduser().resolve(strict=False).is_relative_to(
                self.vault_root.resolve(strict=False)
            )

    @staticmethod
    def _segment(name: str) -> str:
        value = str(name or "").strip()
        return value or "Untitled"

    def _document_filename(self, item: WorkspaceItem) -> str:
        return f"{self._segment(item.title or item.id)}.md"
