# SPDX-License-Identifier: Apache-2.0
"""Workspace-native realtime recording controls."""

from __future__ import annotations

import asyncio
import inspect
import threading
from typing import Any

from core.qt_imports import QLabel, QHBoxLayout, QVBoxLayout, Signal
from ui.base_widgets import BaseWidget, create_button, create_primary_button
from ui.constants import ROLE_WORKSPACE_PLACEHOLDER


class WorkspaceRecordingControlPanel(BaseWidget):
    """Provide the primary realtime recording controls inside workspace."""

    workspace_item_requested = Signal(str)
    _start_completed = Signal(object)
    _stop_completed = Signal(object)
    _operation_failed = Signal(str)

    def __init__(self, realtime_recorder, i18n, parent=None):
        super().__init__(i18n, parent)
        self.realtime_recorder = realtime_recorder
        self._busy = False
        self._recording_active = bool(getattr(realtime_recorder, "is_recording", False))
        self._status_key = "workspace.recording_idle"
        self._init_ui()
        self._start_completed.connect(self._handle_start_completed)
        self._stop_completed.connect(self._handle_stop_completed)
        self._operation_failed.connect(self._handle_operation_failed)
        self._sync_controls()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)

        self.title_label = QLabel(self.i18n.t("workspace.recording_controls_title"))
        layout.addWidget(self.title_label)

        self.status_label = QLabel(self.i18n.t(self._status_key))
        self.status_label.setProperty("role", ROLE_WORKSPACE_PLACEHOLDER)
        layout.addWidget(self.status_label)

        action_layout = QHBoxLayout()
        self.record_button = create_primary_button(self.i18n.t("workspace.record_button"))
        self.record_button.clicked.connect(self._on_start_clicked)
        action_layout.addWidget(self.record_button)

        self.stop_button = create_button(self.i18n.t("workspace.stop_button"))
        self.stop_button.clicked.connect(self._on_stop_clicked)
        action_layout.addWidget(self.stop_button)

        action_layout.addStretch()
        layout.addLayout(action_layout)

    def update_translations(self) -> None:
        self.title_label.setText(self.i18n.t("workspace.recording_controls_title"))
        self.record_button.setText(self.i18n.t("workspace.record_button"))
        self.stop_button.setText(self.i18n.t("workspace.stop_button"))
        self.status_label.setText(self.i18n.t(self._status_key))

    def _on_start_clicked(self) -> None:
        self._run_recorder_call("start_recording")

    def _on_stop_clicked(self) -> None:
        self._run_recorder_call("stop_recording")

    def _run_recorder_call(self, method_name: str) -> None:
        method = getattr(self.realtime_recorder, method_name, None)
        if not callable(method):
            return

        try:
            result = method()
        except Exception as exc:  # noqa: BLE001
            self._operation_failed.emit(str(exc))
            return

        self._busy = True
        self._status_key = "workspace.recording_busy"
        self._sync_controls()

        if inspect.isawaitable(result):
            thread = threading.Thread(
                target=self._await_result,
                args=(method_name, result),
                daemon=True,
            )
            thread.start()
            return

        self._emit_completion(method_name, result)

    def _await_result(self, method_name: str, awaitable: Any) -> None:
        try:
            result = asyncio.run(awaitable)
        except Exception as exc:  # noqa: BLE001
            self._operation_failed.emit(str(exc))
            return
        self._emit_completion(method_name, result)

    def _emit_completion(self, method_name: str, result: Any) -> None:
        if method_name == "start_recording":
            self._start_completed.emit(result)
            return
        self._stop_completed.emit(result)

    def _handle_start_completed(self, _result: Any) -> None:
        self._busy = False
        self._recording_active = True
        self._status_key = "workspace.recording_active"
        self._sync_controls()

    def _handle_stop_completed(self, result: Any) -> None:
        self._busy = False
        self._recording_active = False
        self._status_key = "workspace.recording_idle"
        self._sync_controls()

        item_id = None
        if isinstance(result, dict):
            item_id = result.get("workspace_item_id")
        if not item_id:
            item_id = getattr(self.realtime_recorder, "last_workspace_item_id", None)
        if item_id:
            self.workspace_item_requested.emit(item_id)

    def _handle_operation_failed(self, _message: str) -> None:
        self._busy = False
        self._recording_active = bool(getattr(self.realtime_recorder, "is_recording", False))
        self._status_key = "workspace.recording_error"
        self._sync_controls()

    def _sync_controls(self) -> None:
        self.status_label.setText(self.i18n.t(self._status_key))
        self.record_button.setEnabled(not self._busy and not self._recording_active)
        self.stop_button.setEnabled(not self._busy and self._recording_active)
