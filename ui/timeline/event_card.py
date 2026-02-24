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

from core.qt_imports import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
    Signal,
)

from config.constants import (
    CALENDAR_API_TIMEOUT_SECONDS,
    OUTLOOK_CALENDAR_MAX_PAGE_SIZE,
)
from ui.base_widgets import (
    BaseEventCard,
    create_button,
    create_hbox,
    create_vbox,
    create_danger_button,
)
from ui.constants import (
    PAGE_DENSE_SPACING,
    ROLE_CURRENT_TIME,
    ROLE_CURRENT_TIME_LINE,
    ROLE_EVENT_DESCRIPTION,
    ROLE_EVENT_INDICATOR,
    ROLE_EVENT_META,
    ROLE_EVENT_TITLE,
    ROLE_EVENT_TYPE_BADGE,
    ROLE_NO_ARTIFACTS,
    ROLE_TIMELINE_RECORDING_ACTION,
    ROLE_TIMELINE_SECONDARY_TRANSCRIBE_ACTION,
    ROLE_TIMELINE_TRANSCRIPT_ACTION,
    ROLE_TIMELINE_TRANSLATION_ACTION,
    TIMELINE_CURRENT_TIME_LINE_HEIGHT,
    TIMELINE_TRANSLATION_COMBO_MIN_WIDTH,
    ZERO_MARGINS,
)
from utils.i18n import LANGUAGE_OPTION_KEYS, I18nQtManager
from utils.time_utils import format_localized_datetime, to_local_datetime

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
        left_line.setProperty("role", ROLE_CURRENT_TIME_LINE)
        left_line.setFixedHeight(TIMELINE_CURRENT_TIME_LINE_HEIGHT)
        layout.addWidget(left_line, stretch=1)

        # Label
        label = QLabel(self.i18n.t("timeline.current_time"))
        label.setProperty("role", ROLE_CURRENT_TIME)
        layout.addWidget(label)

        # Right line (red dashed)
        right_line = QFrame()
        right_line.setFrameShape(QFrame.Shape.HLine)
        right_line.setFrameShadow(QFrame.Shadow.Plain)
        right_line.setProperty("role", ROLE_CURRENT_TIME_LINE)
        right_line.setFixedHeight(TIMELINE_CURRENT_TIME_LINE_HEIGHT)
        layout.addWidget(right_line, stretch=1)

    def update_translations(self):
        """Update text when language changes."""
        # Find label and update
        for child in self.children():
            if isinstance(child, QLabel):
                child.setText(self.i18n.t("timeline.current_time"))
                break


class EventCard(BaseEventCard):
    """
    Event card widget for timeline.

    Displays event information with different layouts for past and future events.
    """

    # Signals
    auto_task_changed = Signal(str, dict)  # event_id, config
    view_recording = Signal(str, str)  # file_path, event_id
    view_transcript = Signal(str)  # file_path
    view_translation = Signal(str)  # file_path
    translate_transcript_requested = Signal(str, str)  # event_id, transcript_path
    delete_requested = Signal(str)  # event_id
    secondary_transcribe_requested = Signal(str, str)  # event_id, recording_path

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
        super().__init__(event_data["event"], i18n, parent)

        self.event_data = event_data
        self.is_future = is_future

        self.artifacts = event_data.get("artifacts", {})

        # Additional badge/control labels
        self.recording_btn = None
        self.secondary_transcribe_btn = None
        self.view_text_btn = None
        self.translate_btn = None
        self.translation_checkbox = None
        self.recording_checkbox = None
        self.transcription_checkbox = None
        self.translation_language_label = None
        self.translation_language_combo = None
        self.delete_btn = None

        # Setup UI
        self.setup_ui()

        logger.debug(f"Timeline event card created: {self.calendar_event.id}")

    def setup_ui(self):
        """Set up the card UI."""
        self.setup_base_ui()

        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(*ZERO_MARGINS)
        layout.setSpacing(PAGE_DENSE_SPACING)

        # Header with title, time, badges
        self.create_common_header(layout)

        # Event details (Location, Attendees, Description)
        details_layout = self.create_details()
        layout.addLayout(details_layout)

        # Actions (different for past/future)
        if self.is_future:
            actions_layout = self.create_future_actions()
        else:
            actions_layout = self.create_past_actions()

        layout.addLayout(actions_layout)


    def create_details(self) -> QVBoxLayout:
        """
        Create event details section.

        Returns:
            Details layout
        """
        details_layout = create_vbox(spacing=PAGE_DENSE_SPACING)

        # Location
        if self.calendar_event.location:
            location_layout = create_hbox()
            location_label = QLabel(self.calendar_event.location)
            location_label.setObjectName("detail_label")
            location_label.setProperty("role", ROLE_EVENT_META)
            location_layout.addWidget(location_label)
            location_layout.addStretch()

            details_layout.addLayout(location_layout)

        # Attendees
        if self.calendar_event.attendees:
            attendees_layout = create_hbox()
            attendees_text = ", ".join(self.calendar_event.attendees[:3])
            if len(self.calendar_event.attendees) > 3:
                attendees_text += f" +{len(self.calendar_event.attendees) - 3}"

            attendees_label = QLabel(attendees_text)
            attendees_label.setObjectName("detail_label")
            attendees_label.setProperty("role", ROLE_EVENT_META)
            attendees_layout.addWidget(attendees_label)
            attendees_layout.addStretch()

            details_layout.addLayout(attendees_layout)

        # Description (truncated)
        if self.calendar_event.description:
            desc_label = QLabel(self.calendar_event.description[:100])
            if len(self.calendar_event.description) > 100:
                desc_label.setText(desc_label.text() + "...")
            desc_label.setObjectName("description_label")
            desc_label.setProperty("role", ROLE_EVENT_DESCRIPTION)
            desc_label.setWordWrap(True)
            details_layout.addWidget(desc_label)

        return details_layout

    def create_future_actions(self) -> QHBoxLayout:
        """
        Create actions for future events (auto-task toggles).

        Returns:
            Actions layout
        """
        actions_layout = create_hbox(spacing=8)

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

        self._add_delete_action(actions_layout)
        actions_layout.addStretch()

        return actions_layout

    def create_past_actions(self) -> QHBoxLayout:
        """
        Create actions for past events (view artifacts).

        Returns:
            Actions layout
        """
        actions_layout = create_hbox(spacing=8)
        primary_actions = create_hbox(spacing=8)
        danger_actions = create_hbox(spacing=8)

        # Recording button
        has_recording = bool(self.artifacts.get("recording"))
        has_transcript = bool(self.artifacts.get("transcript"))
        has_translation = bool(self.artifacts.get("translation"))

        if has_recording:
            self.recording_btn = create_button(self.i18n.t("timeline.play_recording"))
            self.recording_btn.clicked.connect(self._on_play_recording)
            self.recording_btn.setProperty("role", ROLE_TIMELINE_RECORDING_ACTION)
            primary_actions.addWidget(self.recording_btn)

        if has_transcript:
            self.secondary_transcribe_btn = create_button(self.i18n.t("timeline.secondary_transcribe"))
            self.secondary_transcribe_btn.clicked.connect(self._on_secondary_transcribe)
            self.secondary_transcribe_btn.setProperty(
                "role", ROLE_TIMELINE_SECONDARY_TRANSCRIBE_ACTION
            )
            primary_actions.addWidget(self.secondary_transcribe_btn)

            self.translate_btn = create_button(self.i18n.t("timeline.translate_transcript"))
            self.translate_btn.clicked.connect(self._on_translate_transcript)
            self.translate_btn.setProperty("role", ROLE_TIMELINE_TRANSLATION_ACTION)
            primary_actions.addWidget(self.translate_btn)

        if has_transcript or has_translation:
            self.view_text_btn = create_button(
                self._get_view_text_button_label(
                    has_transcript=has_transcript,
                    has_translation=has_translation,
                )
            )
            self.view_text_btn.clicked.connect(self._on_view_text)
            self.view_text_btn.setProperty("role", ROLE_TIMELINE_TRANSCRIPT_ACTION)
            primary_actions.addWidget(self.view_text_btn)

        # Show message if no artifacts
        if not (has_recording or has_transcript or has_translation):
            no_artifacts_label = QLabel(self.i18n.t("timeline.no_artifacts"))
            no_artifacts_label.setObjectName("no_artifacts_label")
            no_artifacts_label.setProperty("role", ROLE_NO_ARTIFACTS)
            primary_actions.addWidget(no_artifacts_label)

        self._add_delete_action(danger_actions)

        actions_layout.addLayout(primary_actions)
        actions_layout.addStretch()
        actions_layout.addLayout(danger_actions)

        return actions_layout

    def _add_delete_action(self, actions_layout: QHBoxLayout) -> None:
        """Append a delete action button to the card action row."""
        self.delete_btn = create_danger_button(self.i18n.t("common.delete"))
        self.delete_btn.clicked.connect(self._on_delete_clicked)
        actions_layout.addWidget(self.delete_btn)

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
            self.view_recording.emit(recording_path, self.calendar_event.id)

    def _on_view_text(self):
        """Open the most complete text view available for this event."""
        transcript_path = self.artifacts.get("transcript")
        translation_path = self.artifacts.get("translation")

        if transcript_path:
            logger.info("Viewing transcript/translation for event %s", self.calendar_event.id)
            self.view_transcript.emit(transcript_path)
            return
        if translation_path:
            logger.info("Viewing translation for event %s", self.calendar_event.id)
            self.view_translation.emit(translation_path)

    def _get_view_text_button_label(self, *, has_transcript: bool, has_translation: bool) -> str:
        """Return the best-fit view action label based on available artifacts."""
        if has_transcript and has_translation:
            return self.i18n.t("timeline.view_transcript_translation")
        if has_translation:
            return self.i18n.t("timeline.view_translation")
        return self.i18n.t("timeline.view_transcript")

    def _on_secondary_transcribe(self):
        """Handle re-transcription button click."""
        recording_path = self.artifacts.get("recording")
        if recording_path:
            logger.info(f"Requesting secondary transcription for event {self.calendar_event.id}")
            self.secondary_transcribe_requested.emit(self.calendar_event.id, recording_path)

    def _on_translate_transcript(self):
        """Handle manual translation request for transcript content."""
        transcript_path = self.artifacts.get("transcript")
        if transcript_path:
            logger.info("Requesting transcript translation for event %s", self.calendar_event.id)
            self.translate_transcript_requested.emit(self.calendar_event.id, transcript_path)

    def _on_delete_clicked(self):
        """Handle delete action click."""
        self.delete_requested.emit(self.calendar_event.id)

    def update_translations(self):
        """Update UI text when language changes."""
        super().update_translations()

        if self.is_future:
            # Update checkboxes
            if self.transcription_checkbox:
                self.transcription_checkbox.setText(self.i18n.t("timeline.enable_transcription"))
            if self.recording_checkbox:
                self.recording_checkbox.setText(self.i18n.t("timeline.enable_recording"))
            if self.translation_checkbox:
                self.translation_checkbox.setText(self.i18n.t("timeline.enable_translation"))
            if self.translation_language_label:
                self.translation_language_label.setText(
                    self.i18n.t("timeline.translation_target_label")
                )
            if self.translation_language_combo:
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
            if self.recording_btn:
                self.recording_btn.setText(self.i18n.t("timeline.play_recording"))
            if self.view_text_btn:
                self.view_text_btn.setText(
                    self._get_view_text_button_label(
                        has_transcript=bool(self.artifacts.get("transcript")),
                        has_translation=bool(self.artifacts.get("translation")),
                    )
                )
            if self.translate_btn:
                self.translate_btn.setText(self.i18n.t("timeline.translate_transcript"))
            if self.secondary_transcribe_btn:
                self.secondary_transcribe_btn.setText(self.i18n.t("timeline.secondary_transcribe"))

            # Update no artifacts label
            for child in self.findChildren(QLabel):
                if child.objectName() == "no_artifacts_label":
                    child.setText(self.i18n.t("timeline.no_artifacts"))
                    break

        if self.delete_btn:
            self.delete_btn.setText(self.i18n.t("common.delete"))
