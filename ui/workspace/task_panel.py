# SPDX-License-Identifier: Apache-2.0
"""Workspace task queue panel."""

from __future__ import annotations

import logging
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Optional

from engines.speech.base import AUDIO_VIDEO_SUFFIXES
from core.qt_imports import (
    QFileDialog,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
    Qt,
    Signal,
)
from data.database.models import TranscriptionTask
from ui.base_widgets import BaseWidget, create_button, create_primary_button
from ui.batch_transcribe.task_item import TaskItem
from ui.common.translation_task_options import prompt_event_translation_languages
from ui.constants import ROLE_WORKSPACE_PLACEHOLDER, ROLE_WORKSPACE_TASK_SUMMARY

logger = logging.getLogger("echonote.ui.workspace.task_panel")

_TASK_MODE_TRANSCRIPTION = "transcription"
_TASK_MODE_TRANSLATION = "translation"
_TEXT_TRANSLATION_SUFFIXES = (".txt", ".md")
_TASK_FILTER_ALL = "all"
_TASK_FILTER_PENDING = "pending"
_TASK_FILTER_COMPLETED = "completed"


class _PasteTranslationDialog(QDialog):
    """Collect pasted text content for a new translation task."""

    def __init__(self, i18n, parent=None):
        super().__init__(parent)
        self.i18n = i18n
        self.setWindowTitle(self.i18n.t("batch_transcribe.paste_dialog_title"))
        self.setMinimumWidth(520)
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)

        form_layout = QFormLayout()
        self.file_name_edit = QLineEdit("pasted_text.txt")
        form_layout.addRow(
            self.i18n.t("batch_transcribe.paste_filename_label"),
            self.file_name_edit,
        )
        layout.addLayout(form_layout)

        self.text_edit = QPlainTextEdit()
        self.text_edit.setPlaceholderText(self.i18n.t("batch_transcribe.paste_text_placeholder"))
        self.text_edit.setMinimumHeight(220)
        layout.addWidget(self.text_edit, 1)

        action_layout = QHBoxLayout()
        action_layout.addStretch()

        cancel_button = create_button(self.i18n.t("common.cancel"))
        cancel_button.clicked.connect(self.reject)
        action_layout.addWidget(cancel_button)

        confirm_button = create_primary_button(self.i18n.t("common.ok"))
        confirm_button.clicked.connect(self.accept)
        action_layout.addWidget(confirm_button)

        layout.addLayout(action_layout)

    def get_payload(self) -> Optional[dict[str, str]]:
        text = self.text_edit.toPlainText().strip()
        if not text:
            return None
        return {
            "file_name": self.file_name_edit.text().strip() or "pasted_text.txt",
            "text": text,
        }


class WorkspaceTaskPanel(BaseWidget):
    """Shared batch-task panel hosted by the shell-level workspace task window."""

    workspace_refresh_requested = Signal()
    workspace_item_requested = Signal(str)

    def __init__(
        self,
        transcription_manager,
        i18n,
        *,
        settings_manager=None,
        workspace_manager=None,
        parent=None,
    ):
        super().__init__(i18n, parent)
        self.transcription_manager = transcription_manager
        self.settings_manager = settings_manager
        self.workspace_manager = workspace_manager
        self.task_items: list[TaskItem] = []
        self._init_ui()
        self._attach_listener()
        self.refresh_tasks()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        self._build_header(layout)
        self._build_summary(layout)

        self.task_count_label = QLabel()
        layout.addWidget(self.task_count_label)

        self.empty_label = QLabel(self.i18n.t("workspace.no_tasks"))
        self.empty_label.setProperty("role", ROLE_WORKSPACE_PLACEHOLDER)
        layout.addWidget(self.empty_label)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.task_container = QWidget()
        self.task_layout = QVBoxLayout(self.task_container)
        self.task_layout.setContentsMargins(0, 0, 0, 0)
        self.task_layout.setSpacing(8)
        self.task_layout.addStretch()
        self.scroll_area.setWidget(self.task_container)
        layout.addWidget(self.scroll_area, 1)
        self.task_filter_tabs.currentChanged.connect(lambda _index: self.refresh_tasks())

        self._update_mode_controls()
        self.update_translations()

    def _build_summary(self, layout: QVBoxLayout) -> None:
        """Build the task backlog summary strip shown above the queue."""
        self.summary_section = QWidget(self)
        self.summary_section.setProperty("role", ROLE_WORKSPACE_TASK_SUMMARY)
        summary_layout = QHBoxLayout(self.summary_section)
        summary_layout.setContentsMargins(0, 0, 0, 0)

        (
            total_widget,
            self.summary_total_value_label,
            self.summary_total_caption_label,
        ) = self._build_summary_metric()
        summary_layout.addWidget(total_widget)

        (
            active_widget,
            self.summary_active_value_label,
            self.summary_active_caption_label,
        ) = self._build_summary_metric()
        summary_layout.addWidget(active_widget)

        (
            failed_widget,
            self.summary_failed_value_label,
            self.summary_failed_caption_label,
        ) = self._build_summary_metric()
        summary_layout.addWidget(failed_widget)
        layout.addWidget(self.summary_section)

    def _build_summary_metric(self) -> tuple[QWidget, QLabel, QLabel]:
        """Create one summary metric card with value and caption labels."""
        metric_widget = QWidget(self.summary_section)
        metric_layout = QVBoxLayout(metric_widget)
        metric_layout.setContentsMargins(0, 0, 0, 0)
        metric_layout.setSpacing(2)

        value_label = QLabel("0", metric_widget)
        caption_label = QLabel(metric_widget)
        metric_layout.addWidget(value_label)
        metric_layout.addWidget(caption_label)
        return metric_widget, value_label, caption_label

    def _build_header(self, layout: QVBoxLayout) -> None:
        """Build the task utility header with creation and queue-filter layers."""
        self.creation_section = QWidget(self)
        creation_layout = QVBoxLayout(self.creation_section)
        creation_layout.setContentsMargins(0, 0, 0, 0)

        self.title_label = QLabel(self.i18n.t("workspace.task_queue_title"))
        creation_layout.addWidget(self.title_label)

        mode_layout = QHBoxLayout()
        self.mode_label = QLabel(self.i18n.t("workspace.task_mode_label"))
        mode_layout.addWidget(self.mode_label)

        self.mode_combo = QComboBox()
        self.mode_combo.addItem(
            self.i18n.t("batch_transcribe.mode_transcription"),
            _TASK_MODE_TRANSCRIPTION,
        )
        self.mode_combo.addItem(
            self.i18n.t("batch_transcribe.mode_translation"),
            _TASK_MODE_TRANSLATION,
        )
        self.mode_combo.currentIndexChanged.connect(self._update_mode_controls)
        mode_layout.addWidget(self.mode_combo)
        mode_layout.addStretch()
        creation_layout.addLayout(mode_layout)

        action_layout = QHBoxLayout()
        self.import_file_button = create_primary_button(self.i18n.t("batch_transcribe.import_file"))
        self.import_file_button.clicked.connect(self._on_import_file)
        action_layout.addWidget(self.import_file_button)

        self.import_folder_button = create_button(self.i18n.t("batch_transcribe.import_folder"))
        self.import_folder_button.clicked.connect(self._on_import_folder)
        action_layout.addWidget(self.import_folder_button)

        self.paste_text_button = create_button(self.i18n.t("batch_transcribe.paste_text"))
        self.paste_text_button.clicked.connect(self._on_paste_text)
        action_layout.addWidget(self.paste_text_button)
        action_layout.addStretch()
        creation_layout.addLayout(action_layout)
        layout.addWidget(self.creation_section)

        self.queue_filter_section = QWidget(self)
        queue_layout = QHBoxLayout(self.queue_filter_section)
        queue_layout.setContentsMargins(0, 0, 0, 0)

        self.task_filter_tabs = QTabWidget(self.queue_filter_section)
        self.task_filter_tabs.setDocumentMode(True)
        self.task_filter_tabs.setMaximumHeight(40)
        self._task_filter_order = [
            _TASK_FILTER_ALL,
            _TASK_FILTER_PENDING,
            _TASK_FILTER_COMPLETED,
        ]
        for _ in self._task_filter_order:
            self.task_filter_tabs.addTab(QWidget(), "")
        queue_layout.addWidget(self.task_filter_tabs, 1)

        self.refresh_button = create_button(self.i18n.t("common.refresh"))
        self.refresh_button.clicked.connect(self.refresh_tasks)
        queue_layout.addWidget(self.refresh_button)
        layout.addWidget(self.queue_filter_section)

    def update_translations(self) -> None:
        self.title_label.setText(self.i18n.t("workspace.task_queue_title"))
        self.mode_label.setText(self.i18n.t("workspace.task_mode_label"))
        self.import_file_button.setText(self.i18n.t("batch_transcribe.import_file"))
        self.import_folder_button.setText(self.i18n.t("batch_transcribe.import_folder"))
        self.paste_text_button.setText(self.i18n.t("batch_transcribe.paste_text"))
        self.refresh_button.setText(self.i18n.t("common.refresh"))
        self.empty_label.setText(self.i18n.t("workspace.no_tasks"))
        self.summary_total_caption_label.setText(self.i18n.t("workspace.task_summary_total"))
        self.summary_active_caption_label.setText(self.i18n.t("workspace.task_summary_active"))
        self.summary_failed_caption_label.setText(self.i18n.t("workspace.task_summary_failed"))

        if self.mode_combo.count() >= 2:
            self.mode_combo.setItemText(0, self.i18n.t("batch_transcribe.mode_transcription"))
            self.mode_combo.setItemText(1, self.i18n.t("batch_transcribe.mode_translation"))
        if self.task_filter_tabs.count() >= 3:
            self.task_filter_tabs.setTabText(0, self.i18n.t("workspace.collection_all"))
            self.task_filter_tabs.setTabText(1, self.i18n.t("batch_transcribe.status.pending"))
            self.task_filter_tabs.setTabText(2, self.i18n.t("batch_transcribe.status.completed"))

        self._update_task_count_label()

    def task_count(self) -> int:
        return len(self.task_items)

    def refresh_tasks(self) -> None:
        all_tasks = []
        if self.transcription_manager is not None:
            all_tasks = list(self.transcription_manager.get_all_tasks() or [])
        self._update_summary_labels(all_tasks)
        tasks = self._filter_tasks(all_tasks)

        for item in self.task_items:
            self.task_layout.removeWidget(item)
            item.deleteLater()
        self.task_items.clear()

        paused = self._is_processing_paused()
        for task_data in tasks:
            item = TaskItem(task_data, self.i18n, self)
            item.set_processing_paused(paused)
            item.start_clicked.connect(self._on_start_processing_requested)
            item.pause_clicked.connect(self._on_pause_resume_requested)
            item.cancel_clicked.connect(self._on_cancel_task_requested)
            item.delete_clicked.connect(self._on_delete_task_requested)
            item.view_clicked.connect(self._on_view_task_requested)
            item.export_clicked.connect(self._on_export_task_requested)
            item.retry_clicked.connect(self._on_retry_task_requested)
            self.task_layout.insertWidget(self.task_layout.count() - 1, item)
            self.task_items.append(item)

        has_tasks = bool(tasks)
        self.empty_label.setVisible(not has_tasks)
        self.scroll_area.setVisible(has_tasks)
        self._update_task_count_label()

    def _attach_listener(self) -> None:
        if self.transcription_manager is None:
            return
        add_listener = getattr(self.transcription_manager, "add_listener", None)
        if callable(add_listener):
            add_listener(self._on_task_event)

    def _detach_listener(self) -> None:
        if self.transcription_manager is None:
            return
        remove_listener = getattr(self.transcription_manager, "remove_listener", None)
        if callable(remove_listener):
            remove_listener(self._on_task_event)

    def closeEvent(self, event) -> None:  # noqa: N802
        self._detach_listener()
        super().closeEvent(event)

    def _on_task_event(self, event_type: str, _data: dict[str, Any]) -> None:
        if event_type not in {
            "task_added",
            "task_updated",
            "task_deleted",
            "task_completed",
            "task_failed",
            "task_cancelled",
            "processing_paused",
            "processing_resumed",
        }:
            return

        self.refresh_tasks()
        if event_type == "task_completed":
            self.workspace_refresh_requested.emit()

    def _update_mode_controls(self) -> None:
        is_translation_mode = self._current_task_mode() == _TASK_MODE_TRANSLATION
        self.paste_text_button.setEnabled(is_translation_mode)

    def _update_task_count_label(self) -> None:
        self.task_count_label.setText(
            self.i18n.t("batch_transcribe.tasks_count", count=self.task_count())
        )

    def _update_summary_labels(self, tasks: list[dict[str, Any]]) -> None:
        """Refresh summary metrics from the full task backlog."""
        active_statuses = {"pending", "processing"}
        total_count = len(tasks)
        active_count = sum(1 for task in tasks if task.get("status") in active_statuses)
        failed_count = sum(1 for task in tasks if task.get("status") == "failed")

        self.summary_total_value_label.setText(str(total_count))
        self.summary_active_value_label.setText(str(active_count))
        self.summary_failed_value_label.setText(str(failed_count))

    def _current_task_mode(self) -> str:
        return self.mode_combo.currentData() or _TASK_MODE_TRANSCRIPTION

    def _current_task_filter(self) -> str:
        index = self.task_filter_tabs.currentIndex()
        if 0 <= index < len(self._task_filter_order):
            return self._task_filter_order[index]
        return _TASK_FILTER_ALL

    def _filter_tasks(self, tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        active_filter = self._current_task_filter()
        if active_filter == _TASK_FILTER_ALL:
            return tasks
        if active_filter == _TASK_FILTER_PENDING:
            return [task for task in tasks if task.get("status") in {"pending", "processing"}]
        return [task for task in tasks if task.get("status") == "completed"]

    def _build_import_file_filter(self) -> str:
        extensions = sorted(AUDIO_VIDEO_SUFFIXES)
        if self._current_task_mode() == _TASK_MODE_TRANSLATION:
            extensions.extend(_TEXT_TRANSLATION_SUFFIXES)
        unique_extensions = sorted(set(extensions))
        patterns = " ".join(f"*{suffix}" for suffix in unique_extensions)
        return f"Supported Files ({patterns});;All Files (*)"

    def _resolve_translation_task_options(self) -> Optional[dict[str, Any]]:
        if getattr(self.transcription_manager, "translation_engine", None) is None:
            self.show_warning(
                self.i18n.t("common.warning"),
                self.i18n.t("batch_transcribe.translation_not_available"),
            )
            return None

        languages = prompt_event_translation_languages(
            parent=self,
            i18n=self.i18n,
            settings_manager=self.settings_manager,
        )
        if languages is None:
            return None
        return languages

    def _on_import_file(self) -> None:
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            self.i18n.t("batch_transcribe.import_file"),
            "",
            self._build_import_file_filter(),
        )
        if not file_paths:
            return

        try:
            if self._current_task_mode() == _TASK_MODE_TRANSLATION:
                options = self._resolve_translation_task_options()
                if options is None:
                    return
                for file_path in file_paths:
                    output_format = "md" if file_path.lower().endswith(".md") else "txt"
                    self.transcription_manager.add_translation_task(
                        file_path,
                        options={**options, "output_format": output_format},
                    )
            else:
                for file_path in file_paths:
                    self.transcription_manager.add_task(file_path)
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to import workspace task files: %s", exc, exc_info=True)
            self.show_error(
                self.i18n.t("common.error"),
                self.i18n.t("batch_transcribe.add_task_failed", error=str(exc)),
            )

    def _on_import_folder(self) -> None:
        folder_path = QFileDialog.getExistingDirectory(
            self,
            self.i18n.t("batch_transcribe.import_folder"),
            "",
        )
        if not folder_path:
            return

        try:
            if self._current_task_mode() == _TASK_MODE_TRANSLATION:
                options = self._resolve_translation_task_options()
                if options is None:
                    return
                self.transcription_manager.add_translation_tasks_from_folder(
                    folder_path,
                    options=options,
                )
            else:
                self.transcription_manager.add_tasks_from_folder(folder_path)
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to import workspace task folder: %s", exc, exc_info=True)
            self.show_error(
                self.i18n.t("common.error"),
                self.i18n.t("batch_transcribe.add_task_failed", error=str(exc)),
            )

    def _on_paste_text(self) -> None:
        if self._current_task_mode() != _TASK_MODE_TRANSLATION:
            return

        options = self._resolve_translation_task_options()
        if options is None:
            return

        dialog = _PasteTranslationDialog(self.i18n, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        payload = dialog.get_payload()
        if payload is None:
            self.show_warning(
                self.i18n.t("common.warning"),
                self.i18n.t("batch_transcribe.paste_text_empty"),
            )
            return

        try:
            file_name = payload["file_name"]
            output_format = "md" if file_name.lower().endswith(".md") else "txt"
            self.transcription_manager.add_translation_text_task(
                payload["text"],
                file_name=file_name,
                options={**options, "output_format": output_format},
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to create pasted translation task: %s", exc, exc_info=True)
            self.show_error(
                self.i18n.t("common.error"),
                self.i18n.t("batch_transcribe.add_task_failed", error=str(exc)),
            )

    def _on_start_processing_requested(self, _task_id: str) -> None:
        if callable(getattr(self.transcription_manager, "start_processing", None)):
            self.transcription_manager.start_processing()
            self.refresh_tasks()

    def _on_pause_resume_requested(self, _task_id: str) -> None:
        if self._is_processing_paused():
            action = getattr(self.transcription_manager, "resume_processing", None)
        else:
            action = getattr(self.transcription_manager, "pause_processing", None)
        if callable(action):
            action()
            self.refresh_tasks()

    def _on_cancel_task_requested(self, task_id: str) -> None:
        cancel_task = getattr(self.transcription_manager, "cancel_task", None)
        if callable(cancel_task):
            cancel_task(task_id)
            self.refresh_tasks()

    def _on_delete_task_requested(self, task_id: str) -> None:
        if not self.show_question(
            self.i18n.t("common.warning"),
            self.i18n.t("batch_transcribe.confirm_delete_task"),
        ):
            return

        delete_task = getattr(self.transcription_manager, "delete_task", None)
        if not callable(delete_task):
            return

        if delete_task(task_id):
            self.refresh_tasks()
            return

        self.show_warning(
            self.i18n.t("common.warning"),
            self.i18n.t("batch_transcribe.delete_processing_not_allowed"),
        )

    def _on_view_task_requested(self, task_id: str) -> None:
        item_id = self._resolve_or_publish_workspace_item_id(task_id)
        if item_id:
            self.workspace_item_requested.emit(item_id)
            return
        self.show_warning(
            self.i18n.t("common.warning"),
            self.i18n.t("workspace.no_workspace_item"),
        )

    def _on_export_task_requested(self, task_id: str) -> None:
        get_task_status = getattr(self.transcription_manager, "get_task_status", None)
        export_result = getattr(self.transcription_manager, "export_result", None)
        if not callable(get_task_status) or not callable(export_result):
            return

        task_data = get_task_status(task_id)
        if not task_data:
            return

        output_format = task_data.get("output_format") or "txt"
        default_name = f"{Path(task_data.get('file_name') or task_id).stem}.{output_format}"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            self.i18n.t("viewer.export_dialog_title"),
            default_name,
            f"{output_format.upper()} (*.{output_format})",
        )
        if not file_path:
            return

        try:
            export_result(task_id, output_format, file_path)
            self.show_info(
                self.i18n.t("common.success"),
                self.i18n.t("batch_transcribe.export_success", path=file_path),
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to export workspace task %s: %s", task_id, exc, exc_info=True)
            self.show_error(self.i18n.t("common.error"), str(exc))

    def _on_retry_task_requested(self, task_id: str) -> None:
        if callable(getattr(self.transcription_manager, "start_processing", None)):
            self.transcription_manager.start_processing()

        retry_task = getattr(self.transcription_manager, "retry_task", None)
        if callable(retry_task) and retry_task(task_id):
            self.refresh_tasks()
            return

        self.show_warning(
            self.i18n.t("common.warning"),
            self.i18n.t("errors.unknown_error"),
        )

    def _is_processing_paused(self) -> bool:
        is_paused = getattr(self.transcription_manager, "is_paused", None)
        if callable(is_paused):
            try:
                return bool(is_paused())
            except Exception:  # pragma: no cover - defensive
                logger.debug("Failed to read transcription processing pause state", exc_info=True)
        return False

    def _resolve_workspace_item_id(self, task_id: str) -> Optional[str]:
        if self.workspace_manager is None:
            return None

        resolver = getattr(self.workspace_manager, "get_item_id_by_task_id", None)
        if callable(resolver):
            item_id = resolver(task_id)
            if item_id:
                return item_id

        get_task_status = getattr(self.transcription_manager, "get_task_status", None)
        if not callable(get_task_status):
            return None
        task_data = get_task_status(task_id) or {}
        for path_key in ("output_path", "file_path"):
            item_id = self.workspace_manager.find_item_id_by_asset_path(task_data.get(path_key))
            if item_id:
                return item_id
        return None

    def _resolve_or_publish_workspace_item_id(self, task_id: str) -> Optional[str]:
        item_id = self._resolve_workspace_item_id(task_id)
        if item_id:
            return item_id

        if self.workspace_manager is None:
            return None

        task = self._load_publisheable_task(task_id)
        if task is None:
            return None

        task_kind = self._resolve_task_kind(task)
        publish_task = task
        transcript_path = None
        translation_path = None

        if task_kind == _TASK_MODE_TRANSLATION:
            publish_task = SimpleNamespace(
                id=getattr(task, "id", None),
                file_path=None,
                file_name=getattr(task, "file_name", ""),
                status=getattr(task, "status", "completed"),
            )
            if str(getattr(task, "file_path", "")).lower().endswith(_TEXT_TRANSLATION_SUFFIXES):
                transcript_path = getattr(task, "file_path", None)
            translation_path = getattr(task, "output_path", None)
        else:
            transcript_path = getattr(task, "output_path", None)

        publisher = getattr(self.workspace_manager, "publish_transcription_task", None)
        if not callable(publisher):
            return None

        item_id = publisher(
            publish_task,
            transcript_path=transcript_path,
            translation_path=translation_path,
        )
        if item_id:
            self.workspace_refresh_requested.emit()
        return item_id

    def _load_publisheable_task(self, task_id: str) -> Optional[TranscriptionTask]:
        if self.workspace_manager is None or not hasattr(self.workspace_manager, "db"):
            return None

        task = TranscriptionTask.get_by_id(self.workspace_manager.db, task_id)
        if task is not None:
            if task.status != "completed":
                return None
            return task

        get_task_status = getattr(self.transcription_manager, "get_task_status", None)
        if not callable(get_task_status):
            return None

        task_data = get_task_status(task_id) or {}
        if task_data.get("status") != "completed":
            return None

        return TranscriptionTask(
            id=task_data.get("id") or task_id,
            file_path=task_data.get("file_path") or "",
            file_name=task_data.get("file_name") or "",
            file_size=task_data.get("file_size"),
            audio_duration=task_data.get("audio_duration"),
            status=task_data.get("status") or "completed",
            progress=float(task_data.get("progress") or 0.0),
            language=task_data.get("language"),
            engine=task_data.get("engine") or "",
            output_format=task_data.get("output_format"),
            output_path=task_data.get("output_path"),
            error_message=task_data.get("error_message"),
            created_at=task_data.get("created_at") or "",
            started_at=task_data.get("started_at"),
            completed_at=task_data.get("completed_at"),
        )

    def _resolve_task_kind(self, task: TranscriptionTask) -> str:
        if getattr(task, "engine", None) == "translation":
            return _TASK_MODE_TRANSLATION
        get_task_status = getattr(self.transcription_manager, "get_task_status", None)
        if callable(get_task_status):
            task_data = get_task_status(getattr(task, "id", "")) or {}
            if task_data.get("task_kind") == _TASK_MODE_TRANSLATION:
                return _TASK_MODE_TRANSLATION
        return _TASK_MODE_TRANSCRIPTION
