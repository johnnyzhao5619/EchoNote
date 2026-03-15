# SPDX-License-Identifier: Apache-2.0
"""Persistent recording dock shown at the application shell level."""

from __future__ import annotations

import asyncio
import inspect
import threading
from typing import Any

from core.qt_imports import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
    Qt,
    Signal,
)
from ui.base_widgets import BaseWidget
from ui.constants import (
    APP_RECORDING_DOCK_MARGINS,
    APP_RECORDING_DOCK_MIN_HEIGHT,
    PAGE_DENSE_SPACING,
    ROLE_REALTIME_DURATION,
    ROLE_REALTIME_RECORD_ACTION,
    ROLE_REALTIME_RECORDING_DOCK,
    ROLE_REALTIME_SUMMARY_GROUP,
)
from ui.workspace.recording_session_panel import (
    WorkspaceRecordingSessionPanel,
    format_recording_input_source,
    format_recording_status,
    format_recording_target_language,
)


class _CompactRecordingPanel(QWidget):
    """Always-visible compact transport controls."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(PAGE_DENSE_SPACING)

        self.start_button = QPushButton(self)
        self.start_button.setProperty("role", ROLE_REALTIME_RECORD_ACTION)
        layout.addWidget(self.start_button)

        self.stop_button = QPushButton(self)
        layout.addWidget(self.stop_button)

        self.summary_group = QWidget(self)
        self.summary_group.setProperty("role", ROLE_REALTIME_SUMMARY_GROUP)
        summary_layout = QVBoxLayout(self.summary_group)
        summary_layout.setContentsMargins(0, 0, 0, 0)
        summary_layout.setSpacing(PAGE_DENSE_SPACING)

        self.status_label = QLabel(self.summary_group)
        summary_layout.addWidget(self.status_label)

        summary_meta_layout = QHBoxLayout()
        summary_meta_layout.setContentsMargins(0, 0, 0, 0)
        summary_meta_layout.setSpacing(PAGE_DENSE_SPACING)

        self.duration_label = QLabel(self.summary_group)
        self.duration_label.setProperty("role", ROLE_REALTIME_DURATION)
        summary_meta_layout.addWidget(self.duration_label)

        self.input_label = QLabel(self.summary_group)
        summary_meta_layout.addWidget(self.input_label)

        self.target_label = QLabel(self.summary_group)
        summary_meta_layout.addWidget(self.target_label)
        summary_meta_layout.addStretch()
        summary_layout.addLayout(summary_meta_layout)
        layout.addWidget(self.summary_group, 1)

        layout.addStretch()


class RealtimeRecordingDock(BaseWidget):
    """Shell-level recording dock for compact and expanded recording controls."""

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
        self.full_panel.more_settings_button.clicked.connect(self.realtime_settings_requested.emit)
        self.full_panel_scroll_area = QScrollArea(self)
        self.full_panel_scroll_area.setWidgetResizable(True)
        self.full_panel_scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.full_panel_scroll_area.setWidget(self.full_panel)
        self.full_panel_scroll_area.hide()
        layout.addWidget(self.full_panel_scroll_area)

    def update_translations(self) -> None:
        self.compact_panel.start_button.setText(self.i18n.t("workspace.record_button"))
        self.compact_panel.stop_button.setText(self.i18n.t("workspace.stop_button"))
        self.expand_button.setText(self.i18n.t("common.more"))
        self.full_panel.update_translations()
        self.refresh_status()

    def set_expanded(self, expanded: bool) -> None:
        """Toggle future full-panel visibility without duplicating dock state."""
        self._expanded = bool(expanded)
        self.full_panel_scroll_area.setVisible(self._expanded)

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
            self.compact_panel.input_label.setText(
                format_recording_input_source(self.i18n, status.get("input_device_name"))
            )
        else:
            self.compact_panel.duration_label.setText("00:00")
            self.compact_panel.input_label.setText(
                format_recording_input_source(self.i18n, "default")
            )
        self.compact_panel.status_label.setText(self._status_text())
        self.compact_panel.target_label.setText(
            format_recording_target_language(self.i18n, self.full_panel.selected_target_language())
        )
        self.full_panel.sync_from_recorder(busy=self._busy)
        self._sync_controls()

    def _status_text(self) -> str:
        is_recording = bool(getattr(self.realtime_recorder, "is_recording", False))
        return format_recording_status(self.i18n, is_recording=is_recording, busy=self._busy)

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
        self.refresh_status()
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
        self.refresh_status()

    def _sync_controls(self) -> None:
        start_enabled = not self._busy and not self._recording_active
        stop_enabled = not self._busy and self._recording_active
        self.compact_panel.start_button.setEnabled(start_enabled)
        self.compact_panel.stop_button.setEnabled(stop_enabled)
        self.full_panel.start_button.setEnabled(start_enabled)
