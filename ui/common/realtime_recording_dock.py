# SPDX-License-Identifier: Apache-2.0
"""Persistent compact recording dock shown at the application shell level."""

from __future__ import annotations

import asyncio
import concurrent.futures
import inspect
import threading
from typing import Any

from core.qt_imports import (
    QDialog,
    QHBoxLayout,
    QIcon,
    QLabel,
    QPoint,
    QPushButton,
    QSize,
    QTimer,
    QToolButton,
    QVBoxLayout,
    QWidget,
    QPixmap,
    Qt,
    Signal,
)
from ui.base_widgets import BaseWidget
from ui.common.secondary_transcribe_dialog import select_secondary_transcribe_model
from ui.common.secondary_transcribe_dialog import (
    resolve_preferred_downloaded_transcription_model,
)
from ui.constants import (
    APP_RECORDING_DOCK_MARGINS,
    APP_RECORDING_DOCK_MIN_HEIGHT,
    PAGE_DENSE_SPACING,
    ROLE_REALTIME_DURATION,
    ROLE_REALTIME_FLOATING_TOGGLE,
    ROLE_REALTIME_ICON_ACTION,
    ROLE_REALTIME_RECORD_ACTION,
    ROLE_REALTIME_RECORDING_DOCK,
    ROLE_REALTIME_SUMMARY_GROUP,
)
from ui.realtime_record.floating_overlay import RealtimeFloatingOverlay
from ui.workspace.recording_session_panel import (
    WorkspaceRecordingSessionPanel,
    format_recording_input_source,
    format_recording_status,
    format_recording_target_language,
)

_REFRESH_INTERVAL_MS = 400
_DOCK_ICON_SIZE = 16
_DOCK_ICON_BUTTON_SIZE = 30
_POPUP_OFFSET_Y = 8
_RECORDER_LOOP_JOIN_TIMEOUT_SECONDS = 2.0
_DOCK_ACTION_SVGS = {
    "settings": """
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path d="M6.4 1.5h3.2l.52 1.67c.28.09.55.2.82.34l1.62-.72 2.26 2.26-.72 1.62c.14.27.25.54.34.82l1.67.52v3.2l-1.67.52c-.09.28-.2.55-.34.82l.72 1.62-2.26 2.26-1.62-.72a5.2 5.2 0 0 1-.82.34L9.6 14.5H6.4l-.52-1.67a5.2 5.2 0 0 1-.82-.34l-1.62.72-2.26-2.26.72-1.62a5.2 5.2 0 0 1-.34-.82L.5 9.9V6.7l1.67-.52c.09-.28.2-.55.34-.82l-.72-1.62 2.26-2.26 1.62.72c.27-.14.54-.25.82-.34L6.4 1.5Z" stroke="{color}" stroke-width="1.2" stroke-linejoin="round"/>
            <circle cx="8" cy="8.3" r="2.1" stroke="{color}" stroke-width="1.2"/>
        </svg>
    """,
    "overlay": """
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16" fill="none">
            <rect x="2" y="3" width="12" height="8.5" rx="2" stroke="{color}" stroke-width="1.2"/>
            <path d="M5 13h6" stroke="{color}" stroke-width="1.2" stroke-linecap="round"/>
            <circle cx="11.5" cy="7.25" r="1.2" fill="{color}"/>
        </svg>
    """,
    "document": """
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path d="M4 1.8h5.2L12.5 5v8.7c0 .83-.67 1.5-1.5 1.5H4c-.83 0-1.5-.67-1.5-1.5V3.3c0-.83.67-1.5 1.5-1.5Z" stroke="{color}" stroke-width="1.2" stroke-linejoin="round"/>
            <path d="M9.2 1.8V5h3.3" stroke="{color}" stroke-width="1.2" stroke-linejoin="round"/>
            <path d="M5.4 8h5.2M5.4 10.6h5.2" stroke="{color}" stroke-width="1.2" stroke-linecap="round"/>
        </svg>
    """,
    "spark": """
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path d="M8 1.5l1.37 3.43L12.8 6.3l-3.43 1.37L8 11.1 6.63 7.67 3.2 6.3l3.43-1.37L8 1.5Z" stroke="{color}" stroke-width="1.2" stroke-linejoin="round"/>
            <path d="M12.2 10.2l.63 1.58 1.57.63-1.57.62-.63 1.58-.62-1.58-1.58-.62 1.58-.63.62-1.58Z" fill="{color}"/>
        </svg>
    """,
    "transcript": """
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path d="M3 3.5h10v6.8a1 1 0 0 1-1 1H7.4l-2.9 2V11.3H4a1 1 0 0 1-1-1V3.5Z" stroke="{color}" stroke-width="1.2" stroke-linejoin="round"/>
            <path d="M5.2 6h5.6M5.2 8.2h4.1" stroke="{color}" stroke-width="1.2" stroke-linecap="round"/>
        </svg>
    """,
    "translation": """
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path d="M2.5 4.5h7" stroke="{color}" stroke-width="1.2" stroke-linecap="round"/>
            <path d="M7.5 2.5L9.5 4.5L7.5 6.5" stroke="{color}" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M13.5 11.5h-7" stroke="{color}" stroke-width="1.2" stroke-linecap="round"/>
            <path d="M8.5 9.5L6.5 11.5L8.5 13.5" stroke="{color}" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
    """,
    "auto-secondary": """
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path d="M8 2.2a5.8 5.8 0 1 1-4.1 1.7" stroke="{color}" stroke-width="1.2" stroke-linecap="round"/>
            <path d="M2.3 2.6h3v3" stroke="{color}" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M8 5.1l.88 2.22 2.22.88-2.22.89L8 11.32l-.88-2.22-2.22-.89 2.22-.88L8 5.1Z" fill="{color}"/>
        </svg>
    """,
}


def _build_svg_icon(icon_name: str, color: str) -> QIcon:
    svg_markup = _DOCK_ACTION_SVGS[icon_name].format(color=color)
    pixmap = QPixmap(_DOCK_ICON_SIZE, _DOCK_ICON_SIZE)
    if not pixmap.loadFromData(svg_markup.encode("utf-8"), "SVG"):
        return QIcon()
    return QIcon(pixmap)


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
        summary_layout.setSpacing(1)

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

        self.open_document_button = self._create_icon_button(
            role=ROLE_REALTIME_ICON_ACTION,
            checkable=False,
        )
        layout.addWidget(self.open_document_button)

        self.secondary_button = self._create_icon_button(
            role=ROLE_REALTIME_ICON_ACTION,
            checkable=False,
        )
        layout.addWidget(self.secondary_button)

        self.auto_secondary_button = self._create_icon_button(
            role=ROLE_REALTIME_ICON_ACTION,
            checkable=True,
        )
        layout.addWidget(self.auto_secondary_button)

        self.transcription_button = self._create_icon_button(
            role=ROLE_REALTIME_ICON_ACTION,
            checkable=True,
        )
        layout.addWidget(self.transcription_button)

        self.translation_button = self._create_icon_button(
            role=ROLE_REALTIME_ICON_ACTION,
            checkable=True,
        )
        layout.addWidget(self.translation_button)

        self.overlay_button = self._create_icon_button(
            role=ROLE_REALTIME_FLOATING_TOGGLE,
            checkable=True,
        )
        layout.addWidget(self.overlay_button)

        self.settings_button = self._create_icon_button(
            role=ROLE_REALTIME_ICON_ACTION,
            checkable=False,
        )
        layout.addWidget(self.settings_button)

    def _create_icon_button(self, *, role: str, checkable: bool) -> QToolButton:
        button = QToolButton(self)
        button.setProperty("role", role)
        button.setCheckable(checkable)
        button.setAutoRaise(False)
        button.setFixedSize(_DOCK_ICON_BUTTON_SIZE, _DOCK_ICON_BUTTON_SIZE)
        button.setIconSize(QSize(_DOCK_ICON_SIZE, _DOCK_ICON_SIZE))
        return button


class RealtimeRecordingDock(BaseWidget):
    """Shell-level recording dock for compact transport and popup settings."""

    workspace_item_requested = Signal(str)
    realtime_settings_requested = Signal()
    _start_completed = Signal(object)
    _stop_completed = Signal(object)
    _operation_failed = Signal(str)
    _transcription_preview_received = Signal(str)
    _translation_preview_received = Signal(str)
    _recorder_error_received = Signal(str)

    def __init__(
        self,
        realtime_recorder,
        i18n,
        *,
        settings_manager=None,
        transcription_manager=None,
        model_manager=None,
        parent=None,
    ):
        super().__init__(i18n, parent)
        self.realtime_recorder = realtime_recorder
        self.settings_manager = settings_manager
        self.transcription_manager = transcription_manager
        self.model_manager = model_manager
        self._busy = False
        self._recording_active = bool(getattr(realtime_recorder, "is_recording", False))
        self._latest_session_result: dict = {}
        self._recorder_loop: asyncio.AbstractEventLoop | None = None
        self._recorder_thread: threading.Thread | None = None
        self._previous_recorder_callbacks: dict[str, Any] = {}
        self._init_ui()
        self._start_completed.connect(self._handle_start_completed)
        self._stop_completed.connect(self._handle_stop_completed)
        self._operation_failed.connect(self._handle_operation_failed)
        self._transcription_preview_received.connect(self._handle_transcription_preview)
        self._translation_preview_received.connect(self._handle_translation_preview)
        self._recorder_error_received.connect(self._handle_recorder_error)
        self._install_recorder_callbacks()
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._on_refresh_tick)
        self._refresh_timer.start(_REFRESH_INTERVAL_MS)
        self.update_translations()
        self.refresh_status()

    def _install_recorder_callbacks(self) -> None:
        setter = getattr(self.realtime_recorder, "set_callbacks", None)
        if not callable(setter):
            return

        self._previous_recorder_callbacks = {
            "on_transcription": getattr(self.realtime_recorder, "on_transcription_update", None),
            "on_translation": getattr(self.realtime_recorder, "on_translation_update", None),
            "on_error": getattr(self.realtime_recorder, "on_error", None),
            "on_audio_data": getattr(self.realtime_recorder, "on_audio_data", None),
            "on_marker": getattr(self.realtime_recorder, "on_marker_added", None),
        }

        def _transcription_callback(text: str) -> None:
            self._transcription_preview_received.emit(str(text or ""))
            previous = self._previous_recorder_callbacks.get("on_transcription")
            if callable(previous):
                previous(text)

        def _translation_callback(text: str) -> None:
            self._translation_preview_received.emit(str(text or ""))
            previous = self._previous_recorder_callbacks.get("on_translation")
            if callable(previous):
                previous(text)

        def _error_callback(message: str) -> None:
            self._recorder_error_received.emit(str(message or ""))
            previous = self._previous_recorder_callbacks.get("on_error")
            if callable(previous):
                previous(message)

        setter(
            on_transcription=_transcription_callback,
            on_translation=_translation_callback,
            on_error=_error_callback,
            on_audio_data=self._previous_recorder_callbacks.get("on_audio_data"),
            on_marker=self._previous_recorder_callbacks.get("on_marker"),
        )

    def _init_ui(self) -> None:
        self.setProperty("role", ROLE_REALTIME_RECORDING_DOCK)
        self.setMinimumHeight(APP_RECORDING_DOCK_MIN_HEIGHT)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(*APP_RECORDING_DOCK_MARGINS)
        layout.setSpacing(0)

        self.compact_panel = _CompactRecordingPanel(self)
        self.compact_panel.start_button.clicked.connect(self._on_start_clicked)
        self.compact_panel.stop_button.clicked.connect(self._on_stop_clicked)
        self.compact_panel.open_document_button.clicked.connect(self._open_latest_workspace_item)
        self.compact_panel.secondary_button.clicked.connect(self._on_secondary_transcription_requested)
        self.compact_panel.auto_secondary_button.toggled.connect(self._on_auto_secondary_toggled)
        self.compact_panel.transcription_button.toggled.connect(self._on_transcription_toggled)
        self.compact_panel.translation_button.toggled.connect(self._on_translation_toggled)
        self.compact_panel.overlay_button.toggled.connect(self._on_overlay_toggled)
        self.compact_panel.settings_button.clicked.connect(self._toggle_settings_popup)
        layout.addWidget(self.compact_panel)

        self.settings_popup = QDialog(
            self,
            Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint,
        )
        self.settings_popup.setModal(False)
        popup_layout = QVBoxLayout(self.settings_popup)
        popup_layout.setContentsMargins(0, 0, 0, 0)
        popup_layout.setSpacing(0)
        self.settings_panel = WorkspaceRecordingSessionPanel(
            self.realtime_recorder,
            self.i18n,
            settings_manager=self.settings_manager,
            model_manager=self.model_manager,
            parent=self.settings_popup,
        )
        self.settings_panel.more_settings_button.clicked.connect(self._on_more_settings_clicked)
        self.settings_panel.transcribe_check.toggled.connect(self._on_settings_transcription_changed)
        self.settings_panel.translate_check.toggled.connect(self._on_settings_translation_changed)
        self.settings_panel.auto_secondary_check.toggled.connect(
            self._on_settings_auto_secondary_changed
        )
        self.settings_panel.model_combo.currentTextChanged.connect(
            self._on_settings_transcription_model_changed
        )
        self.settings_panel.secondary_model_combo.currentTextChanged.connect(
            self._on_settings_secondary_model_changed
        )
        popup_layout.addWidget(self.settings_panel)

        self.floating_overlay = RealtimeFloatingOverlay(self.i18n, parent=self)
        self.floating_overlay.show_main_window_requested.connect(self._show_main_window)
        self.floating_overlay.overlay_closed.connect(self._handle_overlay_closed)
        self.floating_overlay.always_on_top_changed.connect(self._store_overlay_pin_preference)
        self.compact_panel.overlay_button.blockSignals(True)
        self.compact_panel.overlay_button.setChecked(self.settings_panel.floating_window_enabled())
        self.compact_panel.overlay_button.blockSignals(False)
        self._sync_auto_secondary_button()
        self._sync_processing_toggle_buttons()

    def update_translations(self) -> None:
        self.compact_panel.stop_button.setText(self.i18n.t("workspace.stop_button"))

        self._sync_icon_button(
            self.compact_panel.settings_button,
            icon_name="settings",
            tooltip=self.i18n.t("workspace.recording_console.settings_tooltip"),
        )
        self._sync_icon_button(
            self.compact_panel.open_document_button,
            icon_name="document",
            tooltip=self.i18n.t("workspace.recording_console.open_latest_document_tooltip"),
        )
        self._sync_icon_button(
            self.compact_panel.secondary_button,
            icon_name="spark",
            tooltip=self.i18n.t("workspace.recording_console.secondary_process_tooltip"),
        )
        self._sync_auto_secondary_button()
        self._sync_processing_buttons()
        self._sync_overlay_button()

        self.settings_panel.update_translations()
        self.floating_overlay.update_translations()
        self.refresh_status()

    def _sync_record_button(self) -> None:
        is_recording_now = bool(getattr(self.realtime_recorder, "is_recording", False))
        if is_recording_now or self._recording_active:
            text_key = "workspace.record_button_active"
        elif self._busy:
            text_key = "workspace.record_button_busy"
        else:
            text_key = "workspace.record_button"
        self.compact_panel.start_button.setText(self.i18n.t(text_key))
        self.compact_panel.start_button.setProperty("recording", is_recording_now or self._recording_active)
        self.compact_panel.start_button.style().unpolish(self.compact_panel.start_button)
        self.compact_panel.start_button.style().polish(self.compact_panel.start_button)

    def _sync_auto_secondary_button(self) -> None:
        checked = self.compact_panel.auto_secondary_button.isChecked()
        tooltip_key = (
            "workspace.recording_console.disable_auto_secondary_tooltip"
            if checked
            else "workspace.recording_console.enable_auto_secondary_tooltip"
        )
        self._sync_icon_button(
            self.compact_panel.auto_secondary_button,
            icon_name="auto-secondary",
            tooltip=self.i18n.t(tooltip_key),
            color=(
                self.compact_panel.auto_secondary_button.palette()
                .highlightedText()
                .color()
                .name()
                if checked
                else None
            ),
        )

    def _sync_icon_button(
        self,
        button: QToolButton,
        *,
        icon_name: str,
        tooltip: str,
        color: str | None = None,
    ) -> None:
        resolved_color = color or button.palette().buttonText().color().name()
        button.setIcon(_build_svg_icon(icon_name, resolved_color))
        button.setToolTip(tooltip)
        button.setAccessibleName(tooltip)

    def _sync_overlay_button(self) -> None:
        checked = self.compact_panel.overlay_button.isChecked()
        tooltip_key = (
            "workspace.recording_console.hide_overlay_tooltip"
            if checked
            else "workspace.recording_console.show_overlay_tooltip"
        )
        self._sync_icon_button(
            self.compact_panel.overlay_button,
            icon_name="overlay",
            tooltip=self.i18n.t(tooltip_key),
            color=(
                self.compact_panel.overlay_button.palette().highlightedText().color().name()
                if checked
                else None
            ),
        )

    def _sync_processing_buttons(self) -> None:
        transcription_checked = self.compact_panel.transcription_button.isChecked()
        translation_checked = self.compact_panel.translation_button.isChecked()
        self._sync_icon_button(
            self.compact_panel.transcription_button,
            icon_name="transcript",
            tooltip=self.i18n.t(
                "workspace.recording_console.disable_transcription_tooltip"
                if transcription_checked
                else "workspace.recording_console.enable_transcription_tooltip"
            ),
            color=(
                self.compact_panel.transcription_button.palette()
                .highlightedText()
                .color()
                .name()
                if transcription_checked
                else None
            ),
        )
        self._sync_icon_button(
            self.compact_panel.translation_button,
            icon_name="translation",
            tooltip=self.i18n.t(
                "workspace.recording_console.disable_translation_tooltip"
                if translation_checked
                else "workspace.recording_console.enable_translation_tooltip"
            ),
            color=(
                self.compact_panel.translation_button.palette()
                .highlightedText()
                .color()
                .name()
                if translation_checked
                else None
            ),
        )

    def _sync_processing_toggle_buttons(self) -> None:
        self.compact_panel.transcription_button.blockSignals(True)
        self.compact_panel.translation_button.blockSignals(True)
        self.compact_panel.transcription_button.setChecked(self.settings_panel.transcription_enabled())
        self.compact_panel.translation_button.setChecked(self.settings_panel.translation_enabled())
        self.compact_panel.translation_button.setEnabled(self.settings_panel.transcription_enabled())
        self.compact_panel.transcription_button.blockSignals(False)
        self.compact_panel.translation_button.blockSignals(False)
        self._sync_processing_buttons()
        self.compact_panel.auto_secondary_button.blockSignals(True)
        self.compact_panel.auto_secondary_button.setChecked(
            self.settings_panel.auto_secondary_processing_enabled()
        )
        self.compact_panel.auto_secondary_button.blockSignals(False)
        self._sync_auto_secondary_button()

    def refresh_status(self) -> None:
        """Refresh compact session summary from shared recorder state."""
        is_recording_now = bool(getattr(self.realtime_recorder, "is_recording", False))
        self._recording_active = is_recording_now or (self._recording_active and self._busy)
        status_getter = getattr(self.realtime_recorder, "get_recording_status", None)
        status = {}
        if callable(status_getter):
            loaded_status = status_getter()
            status = loaded_status if isinstance(loaded_status, dict) else {}

        duration = float(status.get("duration", 0.0) or 0.0)
        minutes = int(duration // 60)
        seconds = int(duration % 60)
        self.compact_panel.duration_label.setText(f"{minutes:02d}:{seconds:02d}")

        input_text = format_recording_input_source(self.i18n, status.get("input_device_name"))
        self.compact_panel.input_label.setText(input_text)
        self.compact_panel.input_label.setToolTip(input_text)

        target_text = self._processing_mode_text()
        self.compact_panel.target_label.setText(target_text)
        self.compact_panel.target_label.setToolTip(target_text)

        self.compact_panel.status_label.setText(self._status_text())
        self._sync_record_button()
        self._sync_controls()
        self._sync_floating_overlay(status)

    def _status_text(self) -> str:
        is_recording = bool(getattr(self.realtime_recorder, "is_recording", False))
        return format_recording_status(self.i18n, is_recording=is_recording, busy=self._busy)

    def _processing_mode_text(self) -> str:
        if not self.settings_panel.transcription_enabled():
            return self.i18n.t("workspace.recording_console.mode_record_only")
        if not self.settings_panel.translation_enabled():
            return self.i18n.t("workspace.recording_console.mode_transcription_only")
        language = format_recording_target_language(self.i18n, self.settings_panel.selected_target_language())
        return self.i18n.t(
            "workspace.recording_console.mode_translation_target",
            language=language,
        )

    def build_realtime_session_options(self) -> dict:
        """Build session options from shared defaults and popup overrides."""
        options = self._load_session_defaults()
        options.update(self.settings_panel.collect_session_options())
        target_language = options.get("target_language") or options.get("translation_target_lang", "en")
        options["target_language"] = target_language
        options["translation_target_lang"] = target_language
        return options

    def _resolve_input_source(self):
        source = self.settings_panel.selected_input_source()
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

    def _on_start_clicked(self) -> None:
        self._latest_session_result = {}
        self.settings_popup.hide()
        self._run_recorder_call(
            "start_recording",
            input_source=self._resolve_input_source(),
            options=self.build_realtime_session_options(),
        )

    def _on_stop_clicked(self) -> None:
        self.settings_popup.hide()
        self._run_recorder_call("stop_recording")

    def _run_recorder_call(self, method_name: str, **kwargs) -> None:
        method = getattr(self.realtime_recorder, method_name, None)
        if not callable(method):
            return
        if method_name == "start_recording":
            kwargs["event_loop"] = self._ensure_recorder_loop()
        try:
            result = method(**kwargs) if kwargs else method()
        except Exception as exc:  # noqa: BLE001
            self._operation_failed.emit(str(exc))
            return

        self._busy = True
        if method_name == "start_recording":
            self._recording_active = True
        self.refresh_status()
        if inspect.isawaitable(result):
            self._submit_recorder_awaitable(method_name, result)
            return
        self._emit_completion(method_name, result)

    def _submit_recorder_awaitable(self, method_name: str, awaitable: Any) -> None:
        loop = self._ensure_recorder_loop()
        future = asyncio.run_coroutine_threadsafe(awaitable, loop)
        future.add_done_callback(
            lambda completed_future, current_method=method_name: self._handle_async_completion(
                current_method,
                completed_future,
            )
        )
        if method_name == "start_recording":
            self._schedule_start_state_probe()

    def _schedule_start_state_probe(self) -> None:
        def _probe() -> None:
            if not self._busy:
                return
            if bool(getattr(self.realtime_recorder, "is_recording", False)):
                self._busy = False
                self._recording_active = True
                self.refresh_status()
                return
            QTimer.singleShot(25, _probe)

        QTimer.singleShot(0, _probe)

    def _handle_async_completion(
        self,
        method_name: str,
        future: concurrent.futures.Future,
    ) -> None:
        try:
            result = future.result()
        except (asyncio.CancelledError, concurrent.futures.CancelledError):
            self._operation_failed.emit("cancelled")
            return
        except BaseException as exc:  # noqa: BLE001
            self._operation_failed.emit(str(exc))
            return
        self._emit_completion(method_name, result)

    def _ensure_recorder_loop(self) -> asyncio.AbstractEventLoop:
        loop = self._recorder_loop
        thread = self._recorder_thread
        if loop is not None and not loop.is_closed() and thread is not None and thread.is_alive():
            return loop

        ready = threading.Event()

        def _run_loop() -> None:
            recorder_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(recorder_loop)
            self._recorder_loop = recorder_loop
            ready.set()
            recorder_loop.run_forever()
            pending_tasks = [task for task in asyncio.all_tasks(recorder_loop) if not task.done()]
            for task in pending_tasks:
                task.cancel()
            if pending_tasks:
                recorder_loop.run_until_complete(
                    asyncio.gather(*pending_tasks, return_exceptions=True)
                )
            recorder_loop.close()
            if self._recorder_loop is recorder_loop:
                self._recorder_loop = None

        self._recorder_thread = threading.Thread(target=_run_loop, daemon=True)
        self._recorder_thread.start()
        ready.wait()
        if self._recorder_loop is None:
            raise RuntimeError("Failed to initialize recorder event loop")
        return self._recorder_loop

    def _emit_completion(self, method_name: str, result: Any) -> None:
        if method_name == "start_recording":
            self._start_completed.emit(result)
            return
        self._stop_completed.emit(result)

    def _handle_start_completed(self, _result: Any) -> None:
        self._busy = False
        self._recording_active = True
        self._show_floating_overlay_if_enabled()
        self.refresh_status()

    def _handle_stop_completed(self, result: Any) -> None:
        self._busy = False
        self._recording_active = False
        self._latest_session_result = result if isinstance(result, dict) else {}
        self._hide_floating_overlay()
        self._show_main_window()
        self.refresh_status()
        item_id = None
        if isinstance(result, dict):
            item_id = result.get("workspace_item_id")
        if not item_id:
            item_id = getattr(self.realtime_recorder, "last_workspace_item_id", None)
        if item_id:
            self.workspace_item_requested.emit(item_id)
        if self.settings_panel.auto_secondary_processing_enabled():
            self._queue_secondary_processing(auto_trigger=True)

    def _handle_operation_failed(self, _message: str) -> None:
        self._busy = False
        self._recording_active = bool(getattr(self.realtime_recorder, "is_recording", False))
        self._hide_floating_overlay()
        self.refresh_status()

    def _handle_transcription_preview(self, text: str) -> None:
        if not text.strip():
            return
        self.floating_overlay.update_preview_text(transcript=text)

    def _handle_translation_preview(self, text: str) -> None:
        if not text.strip():
            return
        self.floating_overlay.update_preview_text(translation=text)

    def _handle_recorder_error(self, _message: str) -> None:
        self.refresh_status()

    def _sync_controls(self) -> None:
        start_enabled = not self._busy and not self._recording_active
        stop_enabled = not self._busy and self._recording_active
        self.compact_panel.start_button.setEnabled(start_enabled)
        self.compact_panel.stop_button.setEnabled(stop_enabled)
        self.compact_panel.settings_button.setEnabled(not self._busy and not self._recording_active)
        self.compact_panel.open_document_button.setEnabled(bool(self._latest_workspace_item_id()))
        self.compact_panel.secondary_button.setEnabled(
            not self._recording_active and bool(self._latest_recording_path())
        )
        self.compact_panel.auto_secondary_button.setEnabled(not self._recording_active)
        self.compact_panel.transcription_button.setEnabled(not self._recording_active)
        self.compact_panel.translation_button.setEnabled(
            not self._recording_active and self.settings_panel.transcription_enabled()
        )

    def _on_refresh_tick(self) -> None:
        if not self.isVisible():
            return
        self.refresh_status()

    def _sync_floating_overlay(self, status: dict) -> None:
        overlay_should_show = self._recording_active and self._should_use_floating_overlay()
        if overlay_should_show and not self.floating_overlay.isVisible():
            self.floating_overlay.show()
            self.floating_overlay.raise_()

        if not overlay_should_show:
            self.floating_overlay.hide()
            return

        duration = float(status.get("duration", 0.0) or 0.0)
        total_seconds = int(duration)
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        self.floating_overlay.update_runtime_state(
            is_recording=self._recording_active or self._busy,
            duration_text=f"{hours:02d}:{minutes:02d}:{seconds:02d}",
        )
        transcription_getter = getattr(self.realtime_recorder, "get_accumulated_transcription", None)
        translation_getter = getattr(self.realtime_recorder, "get_accumulated_translation", None)
        transcript_text = transcription_getter() if callable(transcription_getter) else ""
        translation_text = translation_getter() if callable(translation_getter) else ""
        self.floating_overlay.update_preview_text(
            transcript=transcript_text if isinstance(transcript_text, str) else "",
            translation=translation_text if isinstance(translation_text, str) else "",
        )

    def _show_floating_overlay_if_enabled(self) -> None:
        if not self._should_use_floating_overlay():
            self._hide_floating_overlay()
            return
        self.floating_overlay.clear_preview()
        self.floating_overlay.set_always_on_top(self._floating_window_always_on_top())
        self.floating_overlay.show()
        self.floating_overlay.raise_()
        if self._hide_main_window_when_floating():
            main_window = self._main_window()
            if main_window is not None:
                main_window.hide()

    def _hide_floating_overlay(self) -> None:
        self.floating_overlay.hide()

    def _handle_overlay_closed(self) -> None:
        self.compact_panel.overlay_button.setChecked(False)

    def _show_main_window(self) -> None:
        main_window = self._main_window()
        if main_window is None:
            return
        main_window.showNormal()
        main_window.raise_()
        main_window.activateWindow()

    def _main_window(self):
        window = self.window()
        return window if window is not self else None

    def _should_use_floating_overlay(self) -> bool:
        current_options = getattr(self.realtime_recorder, "current_options", None)
        if isinstance(current_options, dict) and current_options:
            return bool(current_options.get("floating_window_enabled"))
        return bool(self.settings_panel.floating_window_enabled())

    def _hide_main_window_when_floating(self) -> bool:
        if callable(getattr(self.settings_manager, "get_setting", None)):
            return bool(self.settings_manager.get_setting("realtime.hide_main_window_when_floating"))
        return False

    def _floating_window_always_on_top(self) -> bool:
        if callable(getattr(self.settings_manager, "get_setting", None)):
            return bool(self.settings_manager.get_setting("realtime.floating_window_always_on_top"))
        return True

    def _store_overlay_pin_preference(self, _always_on_top: bool) -> None:
        """Keep overlay interaction local; persistent settings remain on the settings page."""

    def _shutdown_recorder_loop(self) -> None:
        loop = self._recorder_loop
        thread = self._recorder_thread
        if loop is None:
            return
        if not loop.is_closed():
            loop.call_soon_threadsafe(loop.stop)
        if thread is not None and thread.is_alive():
            thread.join(timeout=_RECORDER_LOOP_JOIN_TIMEOUT_SECONDS)
        self._recorder_thread = None
        self._recorder_loop = None

    def closeEvent(self, event) -> None:  # noqa: N802
        self._refresh_timer.stop()
        setter = getattr(self.realtime_recorder, "set_callbacks", None)
        if callable(setter) and self._previous_recorder_callbacks:
            setter(
                on_transcription=self._previous_recorder_callbacks.get("on_transcription"),
                on_translation=self._previous_recorder_callbacks.get("on_translation"),
                on_error=self._previous_recorder_callbacks.get("on_error"),
                on_audio_data=self._previous_recorder_callbacks.get("on_audio_data"),
                on_marker=self._previous_recorder_callbacks.get("on_marker"),
            )
        self._shutdown_recorder_loop()
        super().closeEvent(event)

    def _toggle_settings_popup(self) -> None:
        if self.settings_popup.isVisible():
            self.settings_popup.hide()
            return
        self.settings_panel.refresh_input_sources()
        self.settings_panel.refresh_transcription_models()
        self.settings_popup.adjustSize()
        origin = self.compact_panel.settings_button.mapToGlobal(QPoint(0, 0))
        popup_width = self.settings_popup.sizeHint().width()
        popup_height = self.settings_popup.sizeHint().height()
        x = max(8, origin.x() + self.compact_panel.settings_button.width() - popup_width)
        y = origin.y() - popup_height - _POPUP_OFFSET_Y
        if y < 8:
            y = origin.y() + self.compact_panel.settings_button.height() + _POPUP_OFFSET_Y
        self.settings_popup.move(x, y)
        self.settings_popup.show()
        self.settings_popup.raise_()

    def _on_more_settings_clicked(self) -> None:
        self.settings_popup.hide()
        self.realtime_settings_requested.emit()

    def _on_overlay_toggled(self, checked: bool) -> None:
        self.settings_panel.set_floating_window_enabled(checked)
        current_options = getattr(self.realtime_recorder, "current_options", None)
        if isinstance(current_options, dict):
            current_options["floating_window_enabled"] = bool(checked)
        self._sync_overlay_button()
        if checked and self._recording_active:
            self._show_floating_overlay_if_enabled()
            self.refresh_status()
            return
        if not checked:
            self._hide_floating_overlay()

    def _open_latest_workspace_item(self) -> None:
        item_id = self._latest_workspace_item_id()
        if item_id:
            self.workspace_item_requested.emit(item_id)

    def _latest_workspace_item_id(self) -> str:
        item_id = self._coerce_result_text(self._latest_session_result.get("workspace_item_id"))
        if item_id:
            return item_id
        result = getattr(self.realtime_recorder, "last_session_result", None)
        if isinstance(result, dict):
            item_id = self._coerce_result_text(result.get("workspace_item_id"))
            if item_id:
                return item_id
        return self._coerce_result_text(getattr(self.realtime_recorder, "last_workspace_item_id", ""))

    def _latest_recording_path(self) -> str:
        recording_path = self._coerce_result_text(self._latest_session_result.get("recording_path"))
        if recording_path:
            return recording_path
        result = getattr(self.realtime_recorder, "last_session_result", None)
        if isinstance(result, dict):
            return self._coerce_result_text(result.get("recording_path"))
        return ""

    @staticmethod
    def _coerce_result_text(value: Any) -> str:
        if not isinstance(value, str):
            return ""
        return value.strip()

    def _on_transcription_toggled(self, checked: bool) -> None:
        self.settings_panel.transcribe_check.blockSignals(True)
        self.settings_panel.transcribe_check.setChecked(bool(checked))
        self.settings_panel.transcribe_check.blockSignals(False)
        if not checked:
            self.compact_panel.translation_button.setChecked(False)
            self.settings_panel.translate_check.blockSignals(True)
            self.settings_panel.translate_check.setChecked(False)
            self.settings_panel.translate_check.blockSignals(False)
        self._sync_processing_toggle_buttons()
        self.refresh_status()

    def _on_translation_toggled(self, checked: bool) -> None:
        if checked and not self.settings_panel.transcription_enabled():
            self.compact_panel.transcription_button.setChecked(True)
        self.settings_panel.translate_check.blockSignals(True)
        self.settings_panel.translate_check.setChecked(bool(checked))
        self.settings_panel.translate_check.blockSignals(False)
        self._sync_processing_toggle_buttons()
        self.refresh_status()

    def _on_auto_secondary_toggled(self, checked: bool) -> None:
        self.settings_panel.auto_secondary_check.blockSignals(True)
        self.settings_panel.auto_secondary_check.setChecked(bool(checked))
        self.settings_panel.auto_secondary_check.blockSignals(False)
        self._store_session_preference("realtime.auto_secondary_processing", bool(checked))
        self._sync_auto_secondary_button()
        self.refresh_status()

    def _on_settings_transcription_changed(self, checked: bool) -> None:
        if not checked and self.settings_panel.translate_check.isChecked():
            self.settings_panel.translate_check.blockSignals(True)
            self.settings_panel.translate_check.setChecked(False)
            self.settings_panel.translate_check.blockSignals(False)
        self._sync_processing_toggle_buttons()
        self.refresh_status()

    def _on_settings_translation_changed(self, checked: bool) -> None:
        if checked and not self.settings_panel.transcribe_check.isChecked():
            self.settings_panel.transcribe_check.blockSignals(True)
            self.settings_panel.transcribe_check.setChecked(True)
            self.settings_panel.transcribe_check.blockSignals(False)
        self._sync_processing_toggle_buttons()
        self.refresh_status()

    def _on_settings_auto_secondary_changed(self, checked: bool) -> None:
        self.compact_panel.auto_secondary_button.blockSignals(True)
        self.compact_panel.auto_secondary_button.setChecked(bool(checked))
        self.compact_panel.auto_secondary_button.blockSignals(False)
        self._store_session_preference("realtime.auto_secondary_processing", bool(checked))
        self._sync_auto_secondary_button()
        self.refresh_status()

    def _on_settings_transcription_model_changed(self, model_name: str) -> None:
        normalized_model_name = self.settings_panel.selected_transcription_model_name() or str(
            model_name or ""
        ).strip()
        if not self.settings_panel.model_combo.isEnabled():
            normalized_model_name = ""
        self._store_session_preference("realtime.transcription_model_name", normalized_model_name)

    def _on_settings_secondary_model_changed(self, model_name: str) -> None:
        normalized_model_name = self.settings_panel.selected_secondary_model_name() or str(
            model_name or ""
        ).strip()
        if not self.settings_panel.secondary_model_combo.isEnabled():
            normalized_model_name = ""
        self._store_session_preference("transcription.secondary_model_size", normalized_model_name)

    def _on_secondary_transcription_requested(self) -> None:
        self._queue_secondary_processing(auto_trigger=False)

    def _queue_secondary_processing(self, *, auto_trigger: bool) -> None:
        result = self._latest_session_result or getattr(self.realtime_recorder, "last_session_result", None)
        if not isinstance(result, dict) or self.transcription_manager is None:
            return

        recording_path = str(result.get("recording_path") or "").strip()
        if not recording_path:
            return

        default_model = self._resolve_default_secondary_model(result=result)
        preferred_model_name = default_model.get("model_name", "") if default_model else ""
        selected_model = select_secondary_transcribe_model(
            parent=self,
            i18n=self.i18n,
            model_manager=self.model_manager,
            settings_manager=self.settings_manager,
            preferred_model_name=preferred_model_name,
        )
        if not selected_model:
            return

        options = self._build_secondary_processing_options(result, selected_model)
        try:
            self.transcription_manager.add_task(recording_path, options=options)
        except Exception as exc:  # noqa: BLE001
            self._operation_failed.emit(str(exc))

    def _build_secondary_processing_options(
        self,
        result: dict[str, Any],
        selected_model: dict[str, str],
    ) -> dict[str, Any]:
        options: dict[str, Any] = {
            "replace_realtime": True,
            "model_name": selected_model["model_name"],
            "model_path": selected_model.get("model_path", ""),
        }
        event_id = result.get("event_id")
        if event_id:
            options["event_id"] = event_id

        session_options = result.get("session_options") or {}
        if isinstance(session_options, dict):
            language = session_options.get("language")
            if language:
                options["language"] = language
            enable_translation = bool(session_options.get("enable_translation", False))
            options["enable_translation"] = enable_translation
            target_language = session_options.get("target_language") or session_options.get(
                "translation_target_lang"
            )
            if target_language:
                options["translation_target_lang"] = target_language
        return options

    def _resolve_default_secondary_model(self, *, result: dict[str, Any] | None = None) -> dict[str, str] | None:
        preferred_names: list[str] = []
        session_options = result.get("session_options") if isinstance(result, dict) else None
        if isinstance(session_options, dict):
            session_secondary_model_name = str(
                session_options.get("secondary_model_name") or ""
            ).strip()
            if session_secondary_model_name:
                preferred_names.append(session_secondary_model_name)
            session_model_name = str(session_options.get("model_name") or "").strip()
            if session_model_name:
                preferred_names.append(session_model_name)
        if callable(getattr(self.settings_manager, "get_setting", None)):
            configured_session_model = self.settings_manager.get_setting(
                "realtime.transcription_model_name"
            )
            configured_secondary = self.settings_manager.get_setting(
                "transcription.secondary_model_size"
            )
            configured_primary = self.settings_manager.get_setting(
                "transcription.faster_whisper.model_size"
            )
            for candidate in (
                configured_session_model,
                configured_secondary,
                configured_primary,
            ):
                normalized = str(candidate or "").strip()
                if normalized:
                    preferred_names.append(normalized)
        preferred_names.append("base")
        return resolve_preferred_downloaded_transcription_model(
            self.model_manager,
            preferred_names=preferred_names,
        )

    def _store_session_preference(self, key: str, value: Any) -> None:
        setter = getattr(self.settings_manager, "set_setting", None)
        if callable(setter):
            setter(key, value)
