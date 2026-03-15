# SPDX-License-Identifier: Apache-2.0
"""Workspace domain manager."""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional

from data.database.models import WorkspaceAsset, WorkspaceItem
from data.storage.file_manager import FileManager

from core.workspace.document_parser import DocumentParser
from core.workspace.import_service import WorkspaceImportService


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
        self.import_service = import_service or WorkspaceImportService(
            db_connection,
            file_manager,
            document_parser=self.document_parser,
        )

    def set_settings_manager(self, settings_manager) -> None:
        """Attach settings manager after workspace manager initialization."""
        self.settings_manager = settings_manager

    def set_model_manager(self, model_manager) -> None:
        """Attach model manager after workspace manager initialization."""
        self.model_manager = model_manager

    def import_document(self, file_path: str) -> str:
        """Import a document into the unified workspace store."""
        item = self.import_service.import_document(file_path)
        return item.id

    def get_item(self, item_id: str) -> Optional[WorkspaceItem]:
        """Fetch a workspace item by ID."""
        return WorkspaceItem.get_by_id(self.db, item_id)

    def list_items(self, item_type: Optional[str] = None) -> List[WorkspaceItem]:
        """List workspace items."""
        return WorkspaceItem.get_all(self.db, item_type=item_type)

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

    def read_asset_text(self, asset: WorkspaceAsset | None) -> str:
        """Read text content from a workspace asset."""
        if asset is None:
            return ""
        if asset.text_content:
            return asset.text_content
        if asset.file_path:
            asset_path = Path(asset.file_path).expanduser()
            if asset_path.exists():
                return asset_path.read_text(encoding="utf-8")
        return ""

    def update_text_asset(self, asset_id: str, text_content: str) -> WorkspaceAsset:
        """Update an existing text asset in place and persist file changes."""
        asset = WorkspaceAsset.get_by_id(self.db, asset_id)
        if asset is None:
            raise ValueError(f"Unknown workspace asset: {asset_id}")

        target_path: Optional[Path] = None
        if asset.file_path:
            target_path = Path(asset.file_path).expanduser()
        elif asset.item_id:
            item = self.get_item(asset.item_id)
            if item is None:
                raise ValueError(f"Unknown workspace item for asset: {asset_id}")
            target_path = self.file_manager.get_workspace_path(item.id, "edited", f"{asset.asset_role}.md")

        if target_path is None:
            raise ValueError(f"Workspace asset is missing a writable path: {asset_id}")

        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(text_content, encoding="utf-8")

        asset.file_path = str(target_path)
        asset.text_content = text_content
        asset.content_type = self._guess_content_type(target_path)
        asset.metadata_json = json.dumps({"size_bytes": target_path.stat().st_size})
        asset.save(self.db)
        return asset

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

        target_subdirectory = str(Path("Workspace") / item_id / subfolder)
        target_filename = filename or f"{asset_role}.md"
        file_path = self.file_manager.save_text_file(
            text_content,
            target_filename,
            subdirectory=target_subdirectory,
            overwrite=True,
        )
        return self._save_asset(
            item,
            asset_role,
            file_path=file_path,
            text_content=text_content,
        )

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
        item = self._resolve_transcription_item(task, event_id=event_id, replace_existing=replace_existing)
        item.item_type = "recording"
        item.source_kind = "batch_transcription"
        item.source_task_id = getattr(task, "id", None)
        item.source_event_id = event_id or item.source_event_id
        item.status = getattr(task, "status", "completed") or "completed"
        item.save(self.db)

        audio_asset = self._upsert_file_asset(item, "audio", getattr(task, "file_path", None))
        transcript_asset = self._upsert_text_asset(item, "transcript", transcript_path)
        self._upsert_text_asset(item, "translation", translation_path)

        if audio_asset is not None:
            item.primary_audio_asset_id = audio_asset.id
        if transcript_asset is not None:
            item.primary_text_asset_id = transcript_asset.id
        item.save(self.db)
        return item.id

    def publish_recording_session(self, recording_result: dict) -> str:
        """Publish a realtime recording session and its artifacts to workspace."""
        event_id = recording_result.get("event_id")
        item = self._resolve_recording_item(recording_result, event_id=event_id)
        item.item_type = "recording"
        item.source_kind = "realtime_recording"
        item.source_event_id = event_id or item.source_event_id
        item.status = "completed"
        item.save(self.db)

        audio_asset = self._upsert_file_asset(item, "audio", recording_result.get("recording_path"))
        transcript_asset = self._upsert_text_asset(item, "transcript", recording_result.get("transcript_path"))
        self._upsert_text_asset(item, "translation", recording_result.get("translation_path"))
        self._upsert_text_asset(item, "outline", recording_result.get("markers_path"))

        if audio_asset is not None:
            item.primary_audio_asset_id = audio_asset.id
        if transcript_asset is not None:
            item.primary_text_asset_id = transcript_asset.id
        item.save(self.db)
        return item.id

    def get_event_artifacts(self, event_id: str) -> dict:
        """Return the latest workspace-backed artifacts for a calendar event."""
        return self.get_event_artifacts_map([event_id]).get(
            event_id,
            self._empty_artifacts_payload(),
        )

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
        asset = assets[-1]
        if asset.text_content:
            return asset.text_content
        if asset.file_path:
            asset_path = Path(asset.file_path).expanduser()
            if asset_path.exists():
                return asset_path.read_text(encoding="utf-8")
        return ""

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
            item = WorkspaceItem(
                title=title or Path(file_path).stem or asset_role,
                item_type="recording",
                source_kind="ai_generated",
                source_event_id=event_id,
                status="completed",
            )
        item.save(self.db)
        asset = self._upsert_text_asset(item, asset_role, file_path)
        if asset is None:
            return None
        if asset_role == "transcript":
            item.primary_text_asset_id = asset.id
        item.save(self.db)
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
        return removed

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

    def _upsert_file_asset(
        self, item: WorkspaceItem, asset_role: str, file_path: Optional[str]
    ) -> Optional[WorkspaceAsset]:
        if not file_path:
            return None
        source_path = Path(file_path).expanduser()
        if not source_path.exists():
            return None
        return self._save_asset(
            item,
            asset_role,
            file_path=str(source_path),
            text_content=None,
            metadata_json=json.dumps({"size_bytes": source_path.stat().st_size}),
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
        return self._save_asset(
            item,
            asset_role,
            file_path=str(source_path),
            text_content=text_content,
            metadata_json=json.dumps({"size_bytes": source_path.stat().st_size}),
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
        asset.file_path = file_path
        asset.text_content = text_content
        asset.metadata_json = metadata_json
        asset.content_type = self._guess_content_type(Path(file_path))
        asset.save(self.db)
        return asset

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
                    "text_content": asset.text_content,
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
        return "text/plain"

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
