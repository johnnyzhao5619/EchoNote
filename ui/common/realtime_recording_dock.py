# SPDX-License-Identifier: Apache-2.0
"""Persistent recording dock shown at the application shell level."""

from __future__ import annotations

import asyncio
import inspect
import threading
from typing import Any

from core.qt_imports import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget, Signal
from ui.base_widgets import BaseWidget
from ui.constants import (
    APP_RECORDING_DOCK_MARGINS,
    APP_RECORDING_DOCK_MIN_HEIGHT,
    PAGE_DENSE_SPACING,
    ROLE_REALTIME_RECORDING_DOCK,
)
from ui.workspace.recording_session_panel import WorkspaceRecordingSessionPanel


class _CompactRecordingPanel(QWidget):
    """Always-visible compact transport controls."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(PAGE_DENSE_SPACING)

        self.start_button = QPushButton(self)
        layout.addWidget(self.start_button)

        self.stop_button = QPushButton(self)
        layout.addWidget(self.stop_button)

        self.status_label = QLabel(self)
        layout.addWidget(self.status_label)

        self.duration_label = QLabel(self)
        layout.addWidget(self.duration_label)

        self.target_label = QLabel(self)
        layout.addWidget(self.target_label)

        layout.addStretch()


class RealtimeRecordingDock(BaseWidget):
    """Shell-level recording dock with reserved space for future task drawer content."""

    workspace_item_requested = Signal(str)
    realtime_settings_requested = Signal()
    _start_completed = Signal(object)
    _stop_completed = Signal(object)
    _operation_failed = Signal(str)

    def __init__(self, realtime_recorder, i18n, *, settings_manager=None, parent=None):
        super().__init__(i18n, parent)
        self.realtime_recorder = realtime_recorder
        self.settings_manager = settings_manager
        self._expanded = False
        self._task_drawer_widget: QWidget | None = None
        self._busy = False
        self._recording_active = bool(getattr(realtime_recorder, "is_recording", False))
        self._init_ui()
        self._start_completed.connect(self._handle_start_completed)
        self._stop_completed.connect(self._handle_stop_completed)
        self._operation_failed.connect(self._handle_operation_failed)
        self.update_translations()
        self.refresh_status()

    def _init_ui(self) -> None:
        self.setProperty("role", ROLE_REALTIME_RECORDING_DOCK)
        self.setMinimumHeight(APP_RECORDING_DOCK_MIN_HEIGHT)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(*APP_RECORDING_DOCK_MARGINS)
        layout.setSpacing(PAGE_DENSE_SPACING)

        self.task_drawer_host = QWidget(self)
        self.task_drawer_host.hide()
        self.task_drawer_layout = QVBoxLayout(self.task_drawer_host)
        self.task_drawer_layout.setContentsMargins(0, 0, 0, 0)
        self.task_drawer_layout.setSpacing(PAGE_DENSE_SPACING)
        layout.addWidget(self.task_drawer_host)

        self.compact_panel = _CompactRecordingPanel(self)
        self.compact_panel.start_button.clicked.connect(self._on_quick_start_clicked)
        self.compact_panel.stop_button.clicked.connect(self._on_stop_clicked)

        self.expand_button = QPushButton(self.compact_panel)
        self.expand_button.clicked.connect(lambda: self.set_expanded(not self._expanded))
        self.expand_button.show()
        self.compact_panel.layout().addWidget(self.expand_button)

        layout.addWidget(self.compact_panel)

        self.full_panel = WorkspaceRecordingSessionPanel(
            self.realtime_recorder,
            self.i18n,
            settings_manager=self.settings_manager,
            parent=self,
        )
        self.full_panel.start_button.clicked.connect(self._on_full_start_clicked)
        self.full_panel.stop_button.clicked.connect(self._on_stop_clicked)
        self.full_panel.more_settings_button.clicked.connect(self.realtime_settings_requested.emit)
        self.full_panel.hide()
        layout.addWidget(self.full_panel)

    def update_translations(self) -> None:
        self.compact_panel.start_button.setText(self.i18n.t("workspace.record_button"))
        self.compact_panel.stop_button.setText(self.i18n.t("workspace.stop_button"))
        self.compact_panel.status_label.setText(self._status_text())
        self.compact_panel.duration_label.setText("00:00")
        self.compact_panel.target_label.setText("")
        self.expand_button.setText(self.i18n.t("common.more"))
        self.full_panel.update_translations()

    def set_task_drawer_widget(self, widget: QWidget | None) -> None:
        """Attach a widget above the dock for future task-drawer reuse."""
        if self._task_drawer_widget is widget:
            return

        if self._task_drawer_widget is not None:
            self.task_drawer_layout.removeWidget(self._task_drawer_widget)
            self._task_drawer_widget.setParent(None)

        self._task_drawer_widget = widget
        if widget is None:
            self.task_drawer_host.hide()
            return

        self.task_drawer_layout.addWidget(widget)
        self.task_drawer_host.show()

    def set_expanded(self, expanded: bool) -> None:
        """Toggle future full-panel visibility without duplicating dock state."""
        self._expanded = bool(expanded)
        self.full_panel.setVisible(self._expanded)

    def refresh_status(self) -> None:
        """Refresh the compact status text from the shared recorder state."""
        self._recording_active = bool(getattr(self.realtime_recorder, "is_recording", False))
        self.compact_panel.status_label.setText(self._status_text())
        status_getter = getattr(self.realtime_recorder, "get_recording_status", None)
        if callable(status_getter):
            loaded_status = status_getter()
            status = loaded_status if isinstance(loaded_status, dict) else {}
            duration = float(status.get("duration", 0.0) or 0.0)
            minutes = int(duration // 60)
            seconds = int(duration % 60)
            self.compact_panel.duration_label.setText(f"{minutes:02d}:{seconds:02d}")
            self.compact_panel.target_label.setText(str(status.get("input_device_name") or "default"))
        self.full_panel.sync_from_recorder()
        self._sync_controls()

    def _status_text(self) -> str:
        is_recording = bool(getattr(self.realtime_recorder, "is_recording", False))
        key = "workspace.recording_active" if is_recording else "workspace.recording_idle"
        return self.i18n.t(key)

    def build_realtime_session_options(self, *, quick_start: bool = False) -> dict:
        """Build session options from shared defaults and optional full-panel overrides."""
        settings_defaults = self._load_session_defaults()
        if quick_start:
            return settings_defaults
        options = dict(settings_defaults)
        options.update(self.full_panel.collect_session_options())
        return options

    def _resolve_input_source(self, *, quick_start: bool = False):
        if quick_start:
            source = self._load_session_defaults().get("default_input_source")
        else:
            source = self.full_panel.selected_input_source()
        if source in (None, "", "default"):
            return None
        try:
            return int(source)
        except (TypeError, ValueError):
            return source

    def _load_session_defaults(self) -> dict:
        if callable(getattr(self.settings_manager, "get_realtime_session_defaults", None)):
            loaded = self.settings_manager.get_realtime_session_defaults()
            if isinstance(loaded, dict):
                return dict(loaded)
        return {}

    def _on_quick_start_clicked(self) -> None:
        self._run_recorder_call(
            "start_recording",
            input_source=self._resolve_input_source(quick_start=True),
            options=self.build_realtime_session_options(quick_start=True),
        )

    def _on_full_start_clicked(self) -> None:
        self._run_recorder_call(
            "start_recording",
            input_source=self._resolve_input_source(quick_start=False),
            options=self.build_realtime_session_options(quick_start=False),
        )

    def _on_stop_clicked(self) -> None:
        self._run_recorder_call("stop_recording")

    def _run_recorder_call(self, method_name: str, **kwargs) -> None:
        method = getattr(self.realtime_recorder, method_name, None)
        if not callable(method):
            return
        try:
            result = method(**kwargs) if kwargs else method()
        except Exception as exc:  # noqa: BLE001
            self._operation_failed.emit(str(exc))
            return

        self._busy = True
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
        self.refresh_status()

    def _handle_stop_completed(self, result: Any) -> None:
        self._busy = False
        self._recording_active = False
        self.refresh_status()
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
        self._sync_controls()

    def _sync_controls(self) -> None:
        start_enabled = not self._busy and not self._recording_active
        stop_enabled = not self._busy and self._recording_active
        self.compact_panel.start_button.setEnabled(start_enabled)
        self.compact_panel.stop_button.setEnabled(stop_enabled)
        self.full_panel.start_button.setEnabled(start_enabled)
        self.full_panel.stop_button.setEnabled(stop_enabled)
