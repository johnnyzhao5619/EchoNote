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
    QHBoxLayout,
    QLabel,
    QMouseEvent,
    QPoint,
    Qt,
    QVBoxLayout,
    Signal,
)
from ui.base_widgets import connect_button_with_callback, create_button, create_hbox
from ui.constants import (
    ROLE_DIALOG_SECONDARY_ACTION,
    ROLE_REALTIME_FLOATING_OVERLAY,
    ROLE_REALTIME_FLOATING_STATUS,
    ROLE_REALTIME_FLOATING_TITLE,
)
from utils.i18n import I18nQtManager

DEFAULT_DURATION = "00:00:00"
MAX_PREVIEW_LENGTH = 260


class RealtimeFloatingOverlay(QDialog):
    """Always-on-top floating window for compact runtime visibility."""

    show_main_window_requested = Signal()
    overlay_closed = Signal()

    def __init__(self, i18n: I18nQtManager, parent=None):
        super().__init__(parent)
        self.i18n = i18n
        self._drag_offset: Optional[QPoint] = None
        self._is_recording = False
        self._duration_text = DEFAULT_DURATION
        self._transcript_preview = ""
        self._translation_preview = ""

        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setWindowModality(Qt.WindowModality.NonModal)
        self.setMinimumWidth(360)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        self.setProperty("role", ROLE_REALTIME_FLOATING_OVERLAY)

        self._setup_ui()
        self.update_translations()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        header = create_hbox(spacing=8)
        self.title_label = QLabel()
        self.title_label.setProperty("role", ROLE_REALTIME_FLOATING_TITLE)
        header.addWidget(self.title_label)

        header.addStretch()

        self.status_label = QLabel()
        self.status_label.setProperty("role", ROLE_REALTIME_FLOATING_STATUS)
        self.status_label.setProperty("state", "ready")
        header.addWidget(self.status_label)

        self.close_button = create_button("x")
        self.close_button.setProperty("role", ROLE_DIALOG_SECONDARY_ACTION)
        self.close_button.setFixedWidth(28)
        connect_button_with_callback(self.close_button, self._on_close_clicked)
        header.addWidget(self.close_button)

        layout.addLayout(header)

        self.duration_label = QLabel()
        layout.addWidget(self.duration_label)

        self.transcript_title_label = QLabel()
        layout.addWidget(self.transcript_title_label)
        self.transcript_preview_label = QLabel()
        self.transcript_preview_label.setWordWrap(True)
        layout.addWidget(self.transcript_preview_label)

        self.translation_title_label = QLabel()
        layout.addWidget(self.translation_title_label)
        self.translation_preview_label = QLabel()
        self.translation_preview_label.setWordWrap(True)
        layout.addWidget(self.translation_preview_label)

        action_layout = QHBoxLayout()
        action_layout.addStretch()
        self.show_main_button = create_button("")
        connect_button_with_callback(self.show_main_button, self.show_main_window_requested.emit)
        action_layout.addWidget(self.show_main_button)
        layout.addLayout(action_layout)

    def update_runtime_state(self, *, is_recording: bool, duration_text: Optional[str] = None) -> None:
        """Update recording status badge and duration text."""
        self._is_recording = bool(is_recording)
        self._duration_text = duration_text or self._duration_text or DEFAULT_DURATION

        self.status_label.setProperty("state", "recording" if self._is_recording else "ready")
        self.status_label.setText(
            self.i18n.t(
                "realtime_record.floating_status_recording"
                if self._is_recording
                else "realtime_record.floating_status_ready"
            )
        )
        style = self.status_label.style()
        if style is not None:
            style.unpolish(self.status_label)
            style.polish(self.status_label)
        self.status_label.update()
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
        self.update_runtime_state(is_recording=self._is_recording, duration_text=self._duration_text)
        self.update_preview_text()

    @staticmethod
    def _trim_preview_text(text: str) -> str:
        normalized = " ".join((text or "").strip().split())
        if len(normalized) <= MAX_PREVIEW_LENGTH:
            return normalized
        return normalized[: MAX_PREVIEW_LENGTH - 1] + "..."

    def _on_close_clicked(self) -> None:
        self.hide()
        self.overlay_closed.emit()

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
