# SPDX-License-Identifier: Apache-2.0
"""Workspace import orchestration."""

from __future__ import annotations

import json
import mimetypes
from pathlib import Path
from typing import Optional

from data.database.models import WorkspaceAsset, WorkspaceFolder, WorkspaceItem
from data.storage.file_manager import FileManager

from core.workspace.document_parser import DocumentParser
from core.workspace.vault_layout import WorkspaceVaultLayout


class WorkspaceImportService:
    """Import external documents into the unified workspace store."""

    def __init__(
        self,
        db_connection,
        file_manager: FileManager,
        document_parser: Optional[DocumentParser] = None,
        vault_layout: Optional[WorkspaceVaultLayout] = None,
    ):
        self.db = db_connection
        self.file_manager = file_manager
        self.document_parser = document_parser or DocumentParser()
        self.vault_layout = vault_layout or WorkspaceVaultLayout(self.file_manager.workspace_dir)

    def import_document(self, item: WorkspaceItem, file_path: str) -> WorkspaceItem:
        """Import a document into an existing workspace item."""
        source_path = Path(file_path).expanduser().resolve()
        extracted_text = self.document_parser.extract_text(str(source_path))

        source_asset = self._create_source_asset(item, source_path)
        text_asset = self._create_text_asset(item, source_path, extracted_text)

        item.primary_text_asset_id = text_asset.id
        item.save(self.db)

        return item

    def _create_source_asset(self, item: WorkspaceItem, source_path: Path) -> WorkspaceAsset:
        target_path = self.vault_layout.file_asset_path(
            item,
            asset_role="source_document",
            original_name=source_path.name,
            folders_by_id=self._folder_lookup(),
        )
        target_path.parent.mkdir(parents=True, exist_ok=True)
        copied_source_path = self.file_manager.copy_file(
            str(source_path),
            str(target_path),
            overwrite=True,
        )

        asset = WorkspaceAsset(
            item_id=item.id,
            asset_role="source_document",
            file_path=copied_source_path,
            content_type=self._guess_content_type(source_path),
            metadata_json=json.dumps(
                {
                    "original_name": source_path.name,
                    "original_suffix": source_path.suffix.lower(),
                },
                ensure_ascii=False,
            ),
        )
        asset.save(self.db)
        return asset

    def _create_text_asset(
        self, item: WorkspaceItem, source_path: Path, extracted_text: str
    ) -> WorkspaceAsset:
        text_path = self.vault_layout.text_asset_path(
            item,
            asset_role="document_text",
            folders_by_id=self._folder_lookup(),
        )
        text_path.parent.mkdir(parents=True, exist_ok=True)
        text_path.write_text(extracted_text, encoding="utf-8")

        asset = WorkspaceAsset(
            item_id=item.id,
            asset_role="document_text",
            file_path=str(text_path),
            content_type=self._guess_content_type(text_path),
        )
        asset.save(self.db)
        return asset

    def _folder_lookup(self) -> dict[str, WorkspaceFolder]:
        return {folder.id: folder for folder in WorkspaceFolder.get_all(self.db)}

    def _guess_content_type(self, path: Path) -> str:
        explicit_types = {
            ".md": "text/markdown",
            ".srt": "application/x-subrip",
            ".txt": "text/plain",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".pdf": "application/pdf",
        }
        content_type = explicit_types.get(path.suffix.lower())
        if content_type:
            return content_type
        guessed, _ = mimetypes.guess_type(str(path))
        return guessed or "application/octet-stream"
