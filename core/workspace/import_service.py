# SPDX-License-Identifier: Apache-2.0
"""Workspace import orchestration."""

from __future__ import annotations

import json
import mimetypes
from pathlib import Path
from typing import Optional

from data.database.models import WorkspaceAsset, WorkspaceItem
from data.storage.file_manager import FileManager

from core.workspace.document_parser import DocumentParser


class WorkspaceImportService:
    """Import external documents into the unified workspace store."""

    def __init__(
        self,
        db_connection,
        file_manager: FileManager,
        document_parser: Optional[DocumentParser] = None,
    ):
        self.db = db_connection
        self.file_manager = file_manager
        self.document_parser = document_parser or DocumentParser()

    def import_document(self, file_path: str) -> WorkspaceItem:
        """Import a document and create corresponding workspace assets."""
        source_path = Path(file_path).expanduser().resolve()
        extracted_text = self.document_parser.extract_text(str(source_path))

        item = WorkspaceItem(
            title=source_path.stem or source_path.name,
            item_type="document",
            source_kind="manual_import",
        )
        item.save(self.db)

        source_asset = self._create_source_asset(item, source_path)
        text_asset = self._create_text_asset(item, source_path, extracted_text)

        item.primary_text_asset_id = text_asset.id
        item.save(self.db)

        return item

    def _create_source_asset(self, item: WorkspaceItem, source_path: Path) -> WorkspaceAsset:
        source_dir = Path(self.file_manager.get_workspace_path(item.id, "source"))
        self.file_manager.ensure_directory(str(source_dir))
        copied_source_path = self.file_manager.copy_file(
            str(source_path),
            str(source_dir / source_path.name),
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
        text_subdirectory = str(Path("Workspace") / item.id / "text")
        text_filename = self._build_text_filename(source_path)
        text_path = self.file_manager.save_text_file(
            extracted_text,
            text_filename,
            subdirectory=text_subdirectory,
            overwrite=True,
        )

        asset = WorkspaceAsset(
            item_id=item.id,
            asset_role="document_text",
            file_path=text_path,
            content_type=self._guess_content_type(Path(text_filename)),
            text_content=extracted_text,
        )
        asset.save(self.db)
        return asset

    def _build_text_filename(self, source_path: Path) -> str:
        suffix = source_path.suffix.lower()
        if suffix in {".txt", ".md", ".srt"}:
            return source_path.name
        return f"{source_path.stem}.md"

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
