# SPDX-License-Identifier: Apache-2.0
"""Workspace task queue panel."""

from __future__ import annotations

import logging
from pathlib import Path
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
    QVBoxLayout,
    QWidget,
    Qt,
    Signal,
)
from ui.base_widgets import BaseWidget, create_button, create_primary_button
from ui.batch_transcribe.task_item import TaskItem
from ui.batch_transcribe.transcript_viewer import TranscriptViewerDialog
from ui.common.translation_task_options import prompt_event_translation_languages
from ui.constants import ROLE_WORKSPACE_PLACEHOLDER

logger = logging.getLogger("echonote.ui.workspace.task_panel")

_TASK_MODE_TRANSCRIPTION = "transcription"
_TASK_MODE_TRANSLATION = "translation"
_TEXT_TRANSLATION_SUFFIXES = (".txt", ".md")


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
    """Workspace-native task queue panel for batch transcription and translation."""

    workspace_refresh_requested = Signal()

    def __init__(self, transcription_manager, i18n, *, settings_manager=None, parent=None):
        super().__init__(i18n, parent)
        self.transcription_manager = transcription_manager
        self.settings_manager = settings_manager
        self.task_items: list[TaskItem] = []
        self._viewer_dialogs: dict[str, TranscriptViewerDialog] = {}
        self._init_ui()
        self._attach_listener()
        self.refresh_tasks()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)

        self.title_label = QLabel(self.i18n.t("workspace.task_queue_title"))
        layout.addWidget(self.title_label)

        control_layout = QHBoxLayout()
        self.mode_label = QLabel(self.i18n.t("workspace.task_mode_label"))
        control_layout.addWidget(self.mode_label)

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
        control_layout.addWidget(self.mode_combo)
        control_layout.addStretch()
        layout.addLayout(control_layout)

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

        self.refresh_button = create_button(self.i18n.t("common.refresh"))
        self.refresh_button.clicked.connect(self.refresh_tasks)
        action_layout.addWidget(self.refresh_button)
        layout.addLayout(action_layout)

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

        self._update_mode_controls()
        self.update_translations()

    def update_translations(self) -> None:
        self.title_label.setText(self.i18n.t("workspace.task_queue_title"))
        self.mode_label.setText(self.i18n.t("workspace.task_mode_label"))
        self.import_file_button.setText(self.i18n.t("batch_transcribe.import_file"))
        self.import_folder_button.setText(self.i18n.t("batch_transcribe.import_folder"))
        self.paste_text_button.setText(self.i18n.t("batch_transcribe.paste_text"))
        self.refresh_button.setText(self.i18n.t("common.refresh"))
        self.empty_label.setText(self.i18n.t("workspace.no_tasks"))

        if self.mode_combo.count() >= 2:
            self.mode_combo.setItemText(0, self.i18n.t("batch_transcribe.mode_transcription"))
            self.mode_combo.setItemText(1, self.i18n.t("batch_transcribe.mode_translation"))

        self._update_task_count_label()

    def task_count(self) -> int:
        return len(self.task_items)

    def refresh_tasks(self) -> None:
        tasks = []
        if self.transcription_manager is not None:
            tasks = list(self.transcription_manager.get_all_tasks() or [])

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

    def _current_task_mode(self) -> str:
        return self.mode_combo.currentData() or _TASK_MODE_TRANSCRIPTION

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
        dialog = self._viewer_dialogs.get(task_id)
        if dialog is None:
            dialog = TranscriptViewerDialog(
                task_id=task_id,
                transcription_manager=self.transcription_manager,
                db_connection=self.transcription_manager.db,
                i18n=self.i18n,
                settings_manager=self.settings_manager,
                parent=self,
            )
            self._viewer_dialogs[task_id] = dialog
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

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
