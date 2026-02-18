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
"""
Event card components for timeline view.

Displays event information with different layouts for past and future events.
"""

import logging
from typing import Any, Dict, Optional

from PySide6.QtCore import Signal

# QColor, QPalette imports removed - using semantic styling instead
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.timeline.manager import to_local_naive
from ui.base_widgets import create_button, create_hbox, create_vbox
from ui.constants import TIMELINE_CURRENT_TIME_LINE_HEIGHT, TIMELINE_TRANSLATION_COMBO_MIN_WIDTH
from utils.i18n import LANGUAGE_OPTION_KEYS, I18nQtManager

logger = logging.getLogger("echonote.ui.timeline.event_card")


class CurrentTimeIndicator(QFrame):
    """Visual indicator for current time in timeline."""

    def __init__(self, i18n: I18nQtManager, parent: Optional[QWidget] = None):
        """
        Initialize current time indicator.

        Args:
            i18n: Internationalization manager
            parent: Parent widget
        """
        super().__init__(parent)
        self.i18n = i18n
        self.setup_ui()

    def setup_ui(self):
        """Set up the indicator UI."""
        layout = QHBoxLayout(self)

        # Left line (red dashed)
        left_line = QFrame()
        left_line.setFrameShape(QFrame.Shape.HLine)
        left_line.setFrameShadow(QFrame.Shadow.Plain)
        left_line.setProperty("role", "current-time-line")
        left_line.setFixedHeight(TIMELINE_CURRENT_TIME_LINE_HEIGHT)
        layout.addWidget(left_line, stretch=1)

        # Label
        label = QLabel(self.i18n.t("timeline.current_time"))
        label.setProperty("role", "current-time")
        layout.addWidget(label)

        # Right line (red dashed)
        right_line = QFrame()
        right_line.setFrameShape(QFrame.Shape.HLine)
        right_line.setFrameShadow(QFrame.Shadow.Plain)
        right_line.setProperty("role", "current-time-line")
        right_line.setFixedHeight(TIMELINE_CURRENT_TIME_LINE_HEIGHT)
        layout.addWidget(right_line, stretch=1)

    def update_translations(self):
        """Update text when language changes."""
        # Find label and update
        for child in self.children():
            if isinstance(child, QLabel):
                child.setText(self.i18n.t("timeline.current_time"))
                break


class EventCard(QFrame):
    """
    Event card widget for timeline.

    Displays event information with different layouts for past and future events.
    """

    # Signals
    auto_task_changed = Signal(str, dict)  # event_id, config
    view_recording = Signal(str)  # file_path
    view_transcript = Signal(str)  # file_path
    view_translation = Signal(str)  # file_path

    EVENT_TYPE_TRANSLATION_MAP = {
        "event": "timeline.filter_event",
        "task": "timeline.filter_task",
        "appointment": "timeline.filter_appointment",
    }

    SOURCE_TRANSLATION_MAP = {
        "local": "timeline.source_local",
        "google": "timeline.source_google",
        "outlook": "timeline.source_outlook",
    }

    def __init__(
        self,
        event_data: Dict[str, Any],
        is_future: bool,
        i18n: I18nQtManager,
        parent: Optional[QWidget] = None,
    ):
        """
        Initialize event card.

        Args:
            event_data: Event data dictionary containing 'event' and either
                       'artifacts' (past) or 'auto_tasks' (future)
            is_future: True if this is a future event
            i18n: Internationalization manager
            parent: Parent widget
        """
        super().__init__(parent)

        self.event_data = event_data
        self.calendar_event = event_data["event"]
        self.is_future = is_future
        self.i18n = i18n

        self.artifacts = event_data.get("artifacts", {})

        # Badge label references for translation updates
        self.type_badge_label = None
        self.source_badge_label = None
        self.translation_btn = None
        self.translation_checkbox = None
        self.translation_language_label = None
        self.translation_language_combo = None

        # Setup UI
        self.setup_ui()

        logger.debug(f"Event card created: {self.calendar_event.id}")

    def setup_ui(self):
        """Set up the card UI."""
        # Card styling
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setFrameShadow(QFrame.Shadow.Raised)
        self.setObjectName("event_card")
        # Styling is handled by theme files (dark.qss / light.qss)

        # Main layout
        layout = QVBoxLayout(self)

        # Header with title and time
        header_layout = self.create_header()
        layout.addLayout(header_layout)

        # Event details
        details_layout = self.create_details()
        layout.addLayout(details_layout)

        # Actions (different for past/future)
        if self.is_future:
            actions_layout = self.create_future_actions()
        else:
            actions_layout = self.create_past_actions()

        layout.addLayout(actions_layout)

    def create_header(self) -> QVBoxLayout:
        """
        Create card header with title and time.

        Returns:
            Header layout
        """
        header_layout = create_vbox(spacing=5)

        # Title
        title_label = QLabel(self.calendar_event.title)
        title_label.setProperty("role", "event-title")
        title_label.setWordWrap(True)
        header_layout.addWidget(title_label)

        # Time and type
        time_layout = create_hbox()

        # Format time
        start_value = self.calendar_event.start_time
        end_value = self.calendar_event.end_time

        try:
            start_time = to_local_naive(start_value)
            end_time = to_local_naive(end_value)
        except Exception as exc:  # pragma: no cover - defensive log
            logger.warning(
                "Failed to localize event time for %s: %s",
                getattr(self.calendar_event, "id", "<unknown>"),
                exc,
            )
            time_str = f"{start_value} - {end_value}"
        else:
            time_str = f"{start_time.strftime('%Y-%m-%d %H:%M')} - " f"{end_time.strftime('%H:%M')}"

        time_label = QLabel(time_str)
        time_label.setObjectName("time_label")
        time_layout.addWidget(time_label)

        # Event type badge
        type_badge = QLabel(self._get_event_type_badge_text())
        type_badge.setProperty("role", "event-type-badge")
        self.type_badge_label = type_badge
        time_layout.addWidget(type_badge)

        # Source badge - use semantic properties for theming
        source_badge = QLabel(self._get_source_badge_text())
        source_badge.setProperty("role", "event-indicator")
        source_badge.setProperty("source", self.calendar_event.source)
        self.source_badge_label = source_badge
        time_layout.addWidget(source_badge)

        time_layout.addStretch()
        header_layout.addLayout(time_layout)

        return header_layout

    def create_details(self) -> QVBoxLayout:
        """
        Create event details section.

        Returns:
            Details layout
        """
        details_layout = create_vbox(spacing=5)

        # Location
        if self.calendar_event.location:
            location_layout = create_hbox()
            location_icon = QLabel("📍")
            location_layout.addWidget(location_icon)

            location_label = QLabel(self.calendar_event.location)
            location_label.setObjectName("detail_label")
            location_layout.addWidget(location_label)
            location_layout.addStretch()

            details_layout.addLayout(location_layout)

        # Attendees
        if self.calendar_event.attendees:
            attendees_layout = create_hbox()
            attendees_icon = QLabel("👥")
            attendees_layout.addWidget(attendees_icon)

            attendees_text = ", ".join(self.calendar_event.attendees[:3])
            if len(self.calendar_event.attendees) > 3:
                attendees_text += f" +{len(self.calendar_event.attendees) - 3}"

            attendees_label = QLabel(attendees_text)
            attendees_label.setObjectName("detail_label")
            attendees_layout.addWidget(attendees_label)
            attendees_layout.addStretch()

            details_layout.addLayout(attendees_layout)

        # Description (truncated)
        if self.calendar_event.description:
            desc_label = QLabel(self.calendar_event.description[:100])
            if len(self.calendar_event.description) > 100:
                desc_label.setText(desc_label.text() + "...")
            desc_label.setObjectName("description_label")
            desc_label.setProperty("role", "event-description")
            desc_label.setWordWrap(True)
            details_layout.addWidget(desc_label)

        return details_layout

    def create_future_actions(self) -> QHBoxLayout:
        """
        Create actions for future events (auto-task toggles).

        Returns:
            Actions layout
        """
        actions_layout = create_hbox(spacing=15)

        # Get auto-task config
        auto_tasks = self.event_data.get("auto_tasks", {})

        # Transcription toggle
        self.transcription_checkbox = QCheckBox(self.i18n.t("timeline.enable_transcription"))
        self.transcription_checkbox.setChecked(auto_tasks.get("enable_transcription", False))
        self.transcription_checkbox.stateChanged.connect(self._on_auto_task_changed)
        actions_layout.addWidget(self.transcription_checkbox)

        # Recording toggle
        self.recording_checkbox = QCheckBox(self.i18n.t("timeline.enable_recording"))
        self.recording_checkbox.setChecked(auto_tasks.get("enable_recording", False))
        self.recording_checkbox.stateChanged.connect(self._on_auto_task_changed)
        actions_layout.addWidget(self.recording_checkbox)

        # Translation toggle
        self.translation_checkbox = QCheckBox(self.i18n.t("timeline.enable_translation"))
        enable_translation = auto_tasks.get("enable_translation", False)
        self.translation_checkbox.setChecked(enable_translation)
        self.translation_checkbox.stateChanged.connect(self._on_translation_toggled)
        actions_layout.addWidget(self.translation_checkbox)

        # Translation target label and combo
        self.translation_language_label = QLabel(self.i18n.t("timeline.translation_target_label"))
        actions_layout.addWidget(self.translation_language_label)

        self.translation_language_combo = QComboBox()
        self.translation_language_combo.setMinimumWidth(TIMELINE_TRANSLATION_COMBO_MIN_WIDTH)
        self.translation_language_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToContents
        )
        self.translation_language_combo.blockSignals(True)
        for code, label_key in LANGUAGE_OPTION_KEYS:
            self.translation_language_combo.addItem(self.i18n.t(label_key), code)
        target_language = auto_tasks.get("translation_target_language")
        if target_language:
            index = self.translation_language_combo.findData(target_language)
        else:
            index = self.translation_language_combo.findData("en")
        if index != -1:
            self.translation_language_combo.setCurrentIndex(index)
        self.translation_language_combo.blockSignals(False)
        self.translation_language_combo.currentIndexChanged.connect(self._on_auto_task_changed)
        actions_layout.addWidget(self.translation_language_combo)

        self._apply_translation_dependency()

        actions_layout.addStretch()

        return actions_layout

    def create_past_actions(self) -> QHBoxLayout:
        """
        Create actions for past events (view artifacts).

        Returns:
            Actions layout
        """
        actions_layout = create_hbox(spacing=10)

        # Recording button
        has_recording = bool(self.artifacts.get("recording"))
        has_transcript = bool(self.artifacts.get("transcript"))
        has_translation = bool(self.artifacts.get("translation"))

        if has_recording:
            self.recording_btn = create_button("🎵 " + self.i18n.t("timeline.play_recording"))
            self.recording_btn.clicked.connect(self._on_play_recording)
            self.recording_btn.setObjectName("recording_btn")
            # Styling is handled by theme files (dark.qss / light.qss)
            actions_layout.addWidget(self.recording_btn)

        # Transcript button
        if has_transcript:
            self.transcript_btn = create_button("📄 " + self.i18n.t("timeline.view_transcript"))
            self.transcript_btn.clicked.connect(self._on_view_transcript)
            self.transcript_btn.setObjectName("transcript_btn")
            # Styling is handled by theme files (dark.qss / light.qss)
            actions_layout.addWidget(self.transcript_btn)

        if has_translation:
            self.translation_btn = create_button("🌐 " + self.i18n.t("timeline.view_translation"))
            self.translation_btn.clicked.connect(self._on_view_translation)
            self.translation_btn.setObjectName("translation_btn")
            actions_layout.addWidget(self.translation_btn)

        # Show message if no artifacts
        if not (has_recording or has_transcript or has_translation):
            no_artifacts_label = QLabel(self.i18n.t("timeline.no_artifacts"))
            no_artifacts_label.setObjectName("no_artifacts_label")
            no_artifacts_label.setProperty("role", "no-artifacts")
            actions_layout.addWidget(no_artifacts_label)

        actions_layout.addStretch()

        return actions_layout

    def apply_auto_task_config(self, config: Optional[Dict[str, Any]]):
        """Apply an auto-task configuration to the current card."""
        if not self.is_future:
            return

        config = config or {}
        existing_auto_tasks = self.event_data.get("auto_tasks", {}) or {}
        merged_config = dict(existing_auto_tasks)
        merged_config.update(config)
        self.event_data["auto_tasks"] = dict(merged_config)

        def _set_checked(checkbox: Optional[QCheckBox], value: bool):
            if checkbox is None:
                return
            checkbox.blockSignals(True)
            checkbox.setChecked(bool(value))
            checkbox.blockSignals(False)

        enable_transcription = merged_config.get("enable_transcription", False)
        enable_recording = merged_config.get("enable_recording", False)
        enable_translation = merged_config.get("enable_translation", False)
        target_language = merged_config.get("translation_target_language")

        _set_checked(self.transcription_checkbox, enable_transcription)
        _set_checked(self.recording_checkbox, enable_recording)
        _set_checked(self.translation_checkbox, enable_translation)

        if self.translation_language_combo:
            self.translation_language_combo.blockSignals(True)

            if target_language:
                index = self.translation_language_combo.findData(target_language)
            else:
                index = self.translation_language_combo.findData("en")

            if index == -1 and self.translation_language_combo.count() > 0:
                index = 0

            if index != -1:
                self.translation_language_combo.setCurrentIndex(index)

            self.translation_language_combo.blockSignals(False)

        self._apply_translation_dependency()

    def _on_auto_task_changed(self):
        """Handle auto-task configuration change."""
        auto_tasks = self.event_data.get("auto_tasks", {}) or {}
        enable_translation = self._apply_translation_dependency()
        config = {
            "enable_transcription": self.transcription_checkbox.isChecked(),
            "enable_recording": self.recording_checkbox.isChecked(),
            "enable_translation": enable_translation,
            "translation_target_language": None,
        }

        if "transcription_language" in auto_tasks:
            config["transcription_language"] = auto_tasks.get("transcription_language")

        if enable_translation and self.translation_language_combo:
            config["translation_target_language"] = self.translation_language_combo.currentData()

        self.event_data["auto_tasks"] = dict(config)

        logger.debug(f"Auto-task changed for event {self.calendar_event.id}: {config}")
        self.auto_task_changed.emit(self.calendar_event.id, config)

    def _on_translation_toggled(self):
        """Handle enable translation toggle changes."""
        self._apply_translation_dependency()
        self._on_auto_task_changed()

    def _set_translation_controls_enabled(self, enabled: bool):
        """Enable or disable translation target controls."""
        if self.translation_language_label:
            self.translation_language_label.setEnabled(enabled)
        if self.translation_language_combo:
            self.translation_language_combo.setEnabled(enabled)

    def _apply_translation_dependency(self) -> bool:
        """
        Keep translation options consistent with transcription state.

        Returns:
            bool: Whether translation is effectively enabled.
        """
        transcription_enabled = bool(
            self.transcription_checkbox and self.transcription_checkbox.isChecked()
        )

        if self.translation_checkbox:
            self.translation_checkbox.setEnabled(transcription_enabled)
            if not transcription_enabled and self.translation_checkbox.isChecked():
                self.translation_checkbox.blockSignals(True)
                self.translation_checkbox.setChecked(False)
                self.translation_checkbox.blockSignals(False)

        translation_enabled = bool(
            transcription_enabled
            and self.translation_checkbox
            and self.translation_checkbox.isChecked()
        )
        self._set_translation_controls_enabled(translation_enabled)
        return translation_enabled

    def _on_play_recording(self):
        """Handle play recording button click."""
        recording_path = self.artifacts.get("recording")
        if recording_path:
            logger.info(f"Playing recording: {recording_path}")
            self.view_recording.emit(recording_path)

    def _on_view_transcript(self):
        """Handle view transcript button click."""
        transcript_path = self.artifacts.get("transcript")
        if transcript_path:
            logger.info(f"Viewing transcript: {transcript_path}")
            self.view_transcript.emit(transcript_path)

    def _on_view_translation(self):
        """Handle view translation button click."""
        translation_path = self.artifacts.get("translation")
        if translation_path:
            logger.info(f"Viewing translation: {translation_path}")
            self.view_translation.emit(translation_path)

    def update_translations(self):
        """Update UI text when language changes."""
        if getattr(self, "type_badge_label", None):
            self.type_badge_label.setText(self._get_event_type_badge_text())
        if getattr(self, "source_badge_label", None):
            self.source_badge_label.setText(self._get_source_badge_text())

        if self.is_future:
            # Update checkboxes
            if hasattr(self, "transcription_checkbox"):
                self.transcription_checkbox.setText(self.i18n.t("timeline.enable_transcription"))
            if hasattr(self, "recording_checkbox"):
                self.recording_checkbox.setText(self.i18n.t("timeline.enable_recording"))
            if getattr(self, "translation_checkbox", None):
                self.translation_checkbox.setText(self.i18n.t("timeline.enable_translation"))
            if getattr(self, "translation_language_label", None):
                self.translation_language_label.setText(
                    self.i18n.t("timeline.translation_target_label")
                )
            if getattr(self, "translation_language_combo", None):
                current_code = self.translation_language_combo.currentData()
                self.translation_language_combo.blockSignals(True)
                self.translation_language_combo.clear()
                for code, label_key in LANGUAGE_OPTION_KEYS:
                    self.translation_language_combo.addItem(self.i18n.t(label_key), code)
                if current_code is not None:
                    index = self.translation_language_combo.findData(current_code)
                    if index != -1:
                        self.translation_language_combo.setCurrentIndex(index)
                self.translation_language_combo.blockSignals(False)
        else:
            # Update buttons
            if hasattr(self, "recording_btn"):
                self.recording_btn.setText("🎵 " + self.i18n.t("timeline.play_recording"))
            if hasattr(self, "transcript_btn"):
                self.transcript_btn.setText("📄 " + self.i18n.t("timeline.view_transcript"))
            if getattr(self, "translation_btn", None):
                self.translation_btn.setText("🌐 " + self.i18n.t("timeline.view_translation"))

            # Update no artifacts label
            for child in self.findChildren(QLabel):
                if child.objectName() == "no_artifacts_label":
                    child.setText(self.i18n.t("timeline.no_artifacts"))
                    break

    def _get_event_type_badge_text(self) -> str:
        """Return translated text for the event type badge."""
        event_type = getattr(self.calendar_event, "event_type", "") or ""
        translation_key = self.EVENT_TYPE_TRANSLATION_MAP.get(event_type.lower())
        if translation_key:
            return self.i18n.t(translation_key)
        return event_type

    def _get_source_badge_text(self) -> str:
        """Return translated text for the source badge."""
        source = getattr(self.calendar_event, "source", "") or ""
        translation_key = self.SOURCE_TRANSLATION_MAP.get(source.lower())
        if translation_key:
            return self.i18n.t(translation_key)
        return source.capitalize() if source else ""
