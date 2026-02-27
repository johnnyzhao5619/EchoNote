# SPDX-License-Identifier: Apache-2.0
#
# Copyright (c) 2024-2025 EchoNote Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Floating overlay window for realtime transcription/translation status."""

from __future__ import annotations

from typing import Optional

from core.qt_imports import (
    QDialog,
    QEvent,
    QHBoxLayout,
    QLabel,
    QMouseEvent,
    QPoint,
    QSizePolicy,
    Qt,
    QVBoxLayout,
    Signal,
)
from ui.base_widgets import connect_button_with_callback, create_button, create_hbox
from ui.common.style_utils import set_widget_state
from ui.constants import (
    REALTIME_FLOATING_CONTENT_MARGINS,
    REALTIME_FLOATING_HEADER_SPACING,
    REALTIME_FLOATING_LAYOUT_SPACING,
    REALTIME_FLOATING_MIN_WIDTH,
    REALTIME_FLOATING_PREVIEW_MIN_HEIGHT,
    ROLE_REALTIME_FLOATING_ACTION,
    ROLE_REALTIME_FLOATING_CLOSE,
    ROLE_REALTIME_FLOATING_META,
    ROLE_REALTIME_FLOATING_OVERLAY,
    ROLE_REALTIME_FLOATING_PREVIEW,
    ROLE_REALTIME_FLOATING_SECTION_TITLE,
    ROLE_REALTIME_FLOATING_STATUS,
    ROLE_REALTIME_FLOATING_TITLE,
)
from utils.i18n import I18nQtManager

DEFAULT_DURATION = "00:00:00"
MAX_PREVIEW_LENGTH = 260
ACTIVE_WINDOW_OPACITY = 1.0
IDLE_WINDOW_OPACITY = 0.82


class RealtimeFloatingOverlay(QDialog):
    """Always-on-top floating window for compact runtime visibility."""

    show_main_window_requested = Signal()
    overlay_closed = Signal()
    always_on_top_changed = Signal(bool)

    def __init__(self, i18n: I18nQtManager, parent=None):
        super().__init__(parent)
        self.i18n = i18n
        self._drag_offset: Optional[QPoint] = None
        self._is_recording = False
        self._duration_text = DEFAULT_DURATION
        self._transcript_preview = ""
        self._translation_preview = ""
        self._always_on_top = True
        self._hovered = False

        self._apply_window_flags()
        self.setWindowModality(Qt.WindowModality.NonModal)
        self.setMinimumWidth(REALTIME_FLOATING_MIN_WIDTH)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        self.setProperty("role", ROLE_REALTIME_FLOATING_OVERLAY)
        self.setWindowOpacity(IDLE_WINDOW_OPACITY)

        self._setup_ui()
        self.update_translations()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(*REALTIME_FLOATING_CONTENT_MARGINS)
        layout.setSpacing(REALTIME_FLOATING_LAYOUT_SPACING)

        header = create_hbox(spacing=REALTIME_FLOATING_HEADER_SPACING)
        self.title_label = QLabel()
        self.title_label.setProperty("role", ROLE_REALTIME_FLOATING_TITLE)
        header.addWidget(self.title_label)

        header.addStretch()

        self.status_label = QLabel()
        self.status_label.setProperty("role", ROLE_REALTIME_FLOATING_STATUS)
        set_widget_state(self.status_label, "ready")
        header.addWidget(self.status_label)

        self.close_button = create_button("×")
        self.close_button.setProperty("role", ROLE_REALTIME_FLOATING_CLOSE)
        self.close_button.setFixedSize(34, 28)
        connect_button_with_callback(self.close_button, self._on_close_clicked)
        header.addWidget(self.close_button)

        layout.addLayout(header)

        self.duration_label = QLabel()
        self.duration_label.setProperty("role", ROLE_REALTIME_FLOATING_META)
        self.duration_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        layout.addWidget(self.duration_label)

        self.transcript_title_label = QLabel()
        self.transcript_title_label.setProperty("role", ROLE_REALTIME_FLOATING_SECTION_TITLE)
        self.transcript_title_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        layout.addWidget(self.transcript_title_label)

        self.transcript_preview_label = QLabel()
        self.transcript_preview_label.setProperty("role", ROLE_REALTIME_FLOATING_PREVIEW)
        self.transcript_preview_label.setWordWrap(True)
        self.transcript_preview_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.transcript_preview_label.setMinimumHeight(REALTIME_FLOATING_PREVIEW_MIN_HEIGHT)
        self.transcript_preview_label.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding
        )
        layout.addWidget(self.transcript_preview_label, stretch=1)

        self.translation_title_label = QLabel()
        self.translation_title_label.setProperty("role", ROLE_REALTIME_FLOATING_SECTION_TITLE)
        self.translation_title_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        layout.addWidget(self.translation_title_label)

        self.translation_preview_label = QLabel()
        self.translation_preview_label.setProperty("role", ROLE_REALTIME_FLOATING_PREVIEW)
        self.translation_preview_label.setWordWrap(True)
        self.translation_preview_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.translation_preview_label.setMinimumHeight(REALTIME_FLOATING_PREVIEW_MIN_HEIGHT)
        self.translation_preview_label.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding
        )
        layout.addWidget(self.translation_preview_label, stretch=1)

        action_layout = QHBoxLayout()
        self.pin_top_button = create_button("")
        self.pin_top_button.setProperty("role", ROLE_REALTIME_FLOATING_ACTION)
        connect_button_with_callback(self.pin_top_button, self._on_pin_top_clicked)
        action_layout.addWidget(self.pin_top_button)

        action_layout.addStretch(1)
        self.show_main_button = create_button("")
        self.show_main_button.setProperty("role", ROLE_REALTIME_FLOATING_ACTION)
        connect_button_with_callback(self.show_main_button, self.show_main_window_requested.emit)
        action_layout.addWidget(self.show_main_button)
        layout.addLayout(action_layout)

    def _apply_window_flags(self) -> None:
        flags = Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint
        if self._always_on_top:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)

    def set_always_on_top(self, always_on_top: bool) -> None:
        new_value = bool(always_on_top)
        if self._always_on_top == new_value:
            return
        was_visible = self.isVisible()
        self._always_on_top = new_value
        self._apply_window_flags()
        if was_visible:
            self.show()
            self.raise_()
        self._update_pin_top_button_state()

    def update_runtime_state(self, *, is_recording: bool, duration_text: Optional[str] = None) -> None:
        """Update recording status badge and duration text."""
        self._is_recording = bool(is_recording)
        self._duration_text = duration_text or self._duration_text or DEFAULT_DURATION

        set_widget_state(self.status_label, "recording" if self._is_recording else "ready")
        self.status_label.setText(
            self.i18n.t(
                "realtime_record.floating_status_recording"
                if self._is_recording
                else "realtime_record.floating_status_ready"
            )
        )
        self.duration_label.setText(
            self.i18n.t("realtime_record.recording_duration") + f": {self._duration_text}"
        )

    def update_preview_text(self, *, transcript: str = "", translation: str = "") -> None:
        """Update transcript/translation preview snippets."""
        if transcript:
            self._transcript_preview = self._trim_preview_text(transcript)
        if translation:
            self._translation_preview = self._trim_preview_text(translation)

        self.transcript_preview_label.setText(
            self._transcript_preview or self.i18n.t("realtime_record.floating_no_transcript")
        )
        self.translation_preview_label.setText(
            self._translation_preview or self.i18n.t("realtime_record.floating_no_translation")
        )

    def clear_preview(self) -> None:
        """Clear text previews for a new recording session."""
        self._transcript_preview = ""
        self._translation_preview = ""
        self.update_preview_text()

    def update_translations(self) -> None:
        """Refresh i18n text labels."""
        self.title_label.setText(self.i18n.t("realtime_record.floating_window_title"))
        self.close_button.setToolTip(self.i18n.t("realtime_record.floating_close"))
        self.transcript_title_label.setText(self.i18n.t("realtime_record.floating_transcript_preview"))
        self.translation_title_label.setText(
            self.i18n.t("realtime_record.floating_translation_preview")
        )
        self.show_main_button.setText(self.i18n.t("realtime_record.floating_show_main_window"))
        self._update_pin_top_button_state()
        self.update_runtime_state(is_recording=self._is_recording, duration_text=self._duration_text)
        self.update_preview_text()

    def _update_pin_top_button_state(self) -> None:
        self.pin_top_button.setText(
            self.i18n.t(
                "realtime_record.floating_pin_top_on"
                if self._always_on_top
                else "realtime_record.floating_pin_top_off"
            )
        )
        set_widget_state(self.pin_top_button, "active" if self._always_on_top else "inactive")

    def _on_pin_top_clicked(self) -> None:
        new_value = not self._always_on_top
        self.set_always_on_top(new_value)
        self.always_on_top_changed.emit(new_value)

    @staticmethod
    def _trim_preview_text(text: str) -> str:
        normalized = " ".join((text or "").strip().split())
        if len(normalized) <= MAX_PREVIEW_LENGTH:
            return normalized
        # Show the most recent content (tail) so the preview stays current.
        return "..." + normalized[-(MAX_PREVIEW_LENGTH - 3):]

    def _on_close_clicked(self) -> None:
        self.hide()
        self.overlay_closed.emit()

    def event(self, event: QEvent) -> bool:
        if event.type() == QEvent.Type.Enter:
            if not self._hovered:
                self._hovered = True
                self.setWindowOpacity(ACTIVE_WINDOW_OPACITY)
        elif event.type() == QEvent.Type.Leave:
            if self._hovered:
                self._hovered = False
                self.setWindowOpacity(IDLE_WINDOW_OPACITY)
        return super().event(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._drag_offset = None
        super().mouseReleaseEvent(event)
