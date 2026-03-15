# SPDX-License-Identifier: Apache-2.0
"""Expanded recording session controls for the shell dock."""

from __future__ import annotations

from core.qt_imports import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from ui.base_widgets import BaseWidget
from ui.constants import (
    REALTIME_CONSOLE_SECTION_MARGINS,
    REALTIME_CONSOLE_SECTION_SPACING,
    ROLE_REALTIME_CONSOLE_SECTION,
    ROLE_REALTIME_CONSOLE_SECTION_TITLE,
    ROLE_REALTIME_DURATION,
    ROLE_REALTIME_FIELD_CONTROL,
    ROLE_REALTIME_FLOATING_TOGGLE,
    ROLE_REALTIME_MARKER_ACTION,
    ROLE_REALTIME_RECORD_ACTION,
)

_DEFAULT_LANGUAGE_ITEMS = ("auto", "en", "zh", "fr")


def format_recording_status(i18n, *, is_recording: bool, busy: bool = False) -> str:
    """Map recorder state to localized session summary copy."""
    if busy:
        return i18n.t("workspace.recording_busy")
    key = "workspace.recording_active" if is_recording else "workspace.recording_idle"
    return i18n.t(key)


def format_recording_input_source(i18n, input_device_name) -> str:
    """Map recorder input names to user-facing summary copy."""
    if input_device_name in (None, "", "default"):
        return i18n.t("workspace.recording_console.default_input_source")
    return str(input_device_name)


def format_recording_target_language(i18n, language_code) -> str:
    """Map target language codes to localized summary copy."""
    normalized_code = str(language_code or "en")
    key = f"workspace.recording_console.target_language_{normalized_code}"
    translated = i18n.t(key)
    if translated != key:
        return translated
    return normalized_code


class WorkspaceRecordingSessionPanel(BaseWidget):
    """Full recording session panel sharing the main recorder instance."""

    def __init__(self, realtime_recorder, i18n, *, settings_manager=None, parent=None):
        super().__init__(i18n, parent)
        self.realtime_recorder = realtime_recorder
        self.settings_manager = settings_manager
        self._init_ui()
        self.load_defaults()
        self.sync_from_recorder()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(REALTIME_CONSOLE_SECTION_SPACING)

        (
            self.session_summary_section,
            self.session_summary_title_label,
            session_summary_layout,
        ) = self._build_section()
        self.summary_status_label = QLabel(self.session_summary_section)
        session_summary_layout.addWidget(self.summary_status_label)

        summary_meta_layout = QHBoxLayout()
        self.summary_duration_label = QLabel(self.session_summary_section)
        self.summary_duration_label.setProperty("role", ROLE_REALTIME_DURATION)
        summary_meta_layout.addWidget(self.summary_duration_label)

        self.summary_input_label = QLabel(self.session_summary_section)
        summary_meta_layout.addWidget(self.summary_input_label)

        self.summary_target_label = QLabel(self.session_summary_section)
        summary_meta_layout.addWidget(self.summary_target_label)
        summary_meta_layout.addStretch()
        session_summary_layout.addLayout(summary_meta_layout)

        self.start_button = QPushButton(self.session_summary_section)
        self.start_button.setProperty("role", ROLE_REALTIME_RECORD_ACTION)
        summary_action_layout = QHBoxLayout()
        summary_action_layout.addWidget(self.start_button)
        summary_action_layout.addStretch()
        session_summary_layout.addLayout(summary_action_layout)
        layout.addWidget(self.session_summary_section)

        self.capture_section, self.capture_title_label, capture_layout = self._build_section()
        self.capture_form_layout = QGridLayout()
        self.capture_form_layout.setHorizontalSpacing(REALTIME_CONSOLE_SECTION_SPACING)
        self.capture_form_layout.setVerticalSpacing(REALTIME_CONSOLE_SECTION_SPACING)
        self.input_source_label = QLabel(self.capture_section)
        self.capture_form_layout.addWidget(self.input_source_label, 0, 0)

        self.input_source_combo = QComboBox(self.capture_section)
        self.input_source_combo.setProperty("role", ROLE_REALTIME_FIELD_CONTROL)
        self.capture_form_layout.addWidget(self.input_source_combo, 0, 1)

        self.gain_label = QLabel(self.capture_section)
        self.capture_form_layout.addWidget(self.gain_label, 1, 0)

        self.gain_spin = QDoubleSpinBox(self.capture_section)
        self.gain_spin.setRange(0.1, 4.0)
        self.gain_spin.setSingleStep(0.1)
        self.gain_spin.setProperty("role", ROLE_REALTIME_FIELD_CONTROL)
        self.capture_form_layout.addWidget(self.gain_spin, 1, 1)

        self.floating_button = QPushButton(self.capture_section)
        self.floating_button.setCheckable(True)
        self.floating_button.setProperty("role", ROLE_REALTIME_FLOATING_TOGGLE)
        self.capture_form_layout.addWidget(self.floating_button, 2, 0, 1, 2)
        capture_layout.addLayout(self.capture_form_layout)
        layout.addWidget(self.capture_section)

        self.processing_section, self.processing_title_label, processing_layout = self._build_section()
        self.processing_form_layout = QGridLayout()
        self.processing_form_layout.setHorizontalSpacing(REALTIME_CONSOLE_SECTION_SPACING)
        self.processing_form_layout.setVerticalSpacing(REALTIME_CONSOLE_SECTION_SPACING)
        self.transcribe_check = QCheckBox(self.processing_section)
        self.processing_form_layout.addWidget(self.transcribe_check, 0, 0, 1, 2)

        self.translate_check = QCheckBox(self.processing_section)
        self.processing_form_layout.addWidget(self.translate_check, 1, 0, 1, 2)

        self.translation_language_label = QLabel(self.processing_section)
        self.processing_form_layout.addWidget(self.translation_language_label, 2, 0)

        self.translation_language_combo = QComboBox(self.processing_section)
        self.translation_language_combo.setProperty("role", ROLE_REALTIME_FIELD_CONTROL)
        for language in _DEFAULT_LANGUAGE_ITEMS:
            self.translation_language_combo.addItem(language, language)
        self.processing_form_layout.addWidget(self.translation_language_combo, 2, 1)
        processing_layout.addLayout(self.processing_form_layout)
        layout.addWidget(self.processing_section)

        self.output_section, self.output_title_label, output_layout = self._build_section()
        self.output_form_layout = QGridLayout()
        self.output_form_layout.setHorizontalSpacing(REALTIME_CONSOLE_SECTION_SPACING)
        self.output_form_layout.setVerticalSpacing(REALTIME_CONSOLE_SECTION_SPACING)
        self.save_recording_check = QCheckBox(self.output_section)
        self.output_form_layout.addWidget(self.save_recording_check, 0, 0, 1, 2)

        self.save_transcript_check = QCheckBox(self.output_section)
        self.output_form_layout.addWidget(self.save_transcript_check, 1, 0, 1, 2)

        self.create_calendar_event_check = QCheckBox(self.output_section)
        self.output_form_layout.addWidget(self.create_calendar_event_check, 2, 0, 1, 2)

        self.more_settings_button = QPushButton(self.output_section)
        self.output_form_layout.addWidget(self.more_settings_button, 3, 0, 1, 2)
        output_layout.addLayout(self.output_form_layout)
        layout.addWidget(self.output_section)

        self.live_results_section, self.live_results_title_label, live_results_layout = self._build_section()
        marker_layout = QHBoxLayout()
        self.marker_button = QPushButton(self.live_results_section)
        self.marker_button.setProperty("role", ROLE_REALTIME_MARKER_ACTION)
        self.marker_button.clicked.connect(self._on_add_marker)
        marker_layout.addWidget(self.marker_button)

        self.marker_list_label = QLabel(self.live_results_section)
        marker_layout.addWidget(self.marker_list_label)
        marker_layout.addStretch()
        live_results_layout.addLayout(marker_layout)

        self.transcript_preview = QPlainTextEdit(self.live_results_section)
        self.transcript_preview.setReadOnly(True)
        live_results_layout.addWidget(self.transcript_preview)

        self.translation_preview = QPlainTextEdit(self.live_results_section)
        self.translation_preview.setReadOnly(True)
        live_results_layout.addWidget(self.translation_preview)
        layout.addWidget(self.live_results_section)

        self.refresh_input_sources()
        self.update_translations()

    def _build_section(self) -> tuple[QWidget, QLabel, QVBoxLayout]:
        """Create a reusable section shell for the recording console."""
        section = QWidget(self)
        section.setProperty("role", ROLE_REALTIME_CONSOLE_SECTION)
        section_layout = QVBoxLayout(section)
        section_layout.setContentsMargins(*REALTIME_CONSOLE_SECTION_MARGINS)
        section_layout.setSpacing(REALTIME_CONSOLE_SECTION_SPACING)

        title_label = QLabel(section)
        title_label.setProperty("role", ROLE_REALTIME_CONSOLE_SECTION_TITLE)
        section_layout.addWidget(title_label)
        return section, title_label, section_layout

    def update_translations(self) -> None:
        self.session_summary_title_label.setText(
            self.i18n.t("workspace.recording_console.section_summary")
        )
        self.capture_title_label.setText(
            self.i18n.t("workspace.recording_console.section_capture")
        )
        self.processing_title_label.setText(
            self.i18n.t("workspace.recording_console.section_processing")
        )
        self.output_title_label.setText(
            self.i18n.t("workspace.recording_console.section_output")
        )
        self.live_results_title_label.setText(
            self.i18n.t("workspace.recording_console.section_live_results")
        )

        self.input_source_label.setText(self.i18n.t("settings.realtime.audio_input"))
        self.gain_label.setText(self.i18n.t("settings.realtime.gain_level"))
        self.transcribe_check.setText(self.i18n.t("workspace.record_button"))
        self.translate_check.setText(self.i18n.t("settings.translation.title"))
        self.translation_language_label.setText(self.i18n.t("settings.translation.target_language"))
        self.save_recording_check.setText(self.i18n.t("settings.realtime.auto_save"))
        self.save_transcript_check.setText(self.i18n.t("settings.realtime.save_transcript"))
        self.create_calendar_event_check.setText(
            self.i18n.t("settings.realtime.create_calendar_event")
        )
        self.start_button.setText(self.i18n.t("workspace.recording_console.apply_and_record"))
        self.marker_button.setText(self.i18n.t("workspace.add_marker"))
        self.floating_button.setText(self.i18n.t("settings.realtime.floating_window"))
        self.more_settings_button.setText(self.i18n.t("settings.title"))
        self.summary_status_label.setText(format_recording_status(self.i18n, is_recording=False))
        if self.input_source_combo.count() > 0:
            self.input_source_combo.setItemText(
                0,
                self.i18n.t("workspace.recording_console.default_input_source"),
            )

    def load_defaults(self) -> None:
        """Populate session controls from shared settings defaults."""
        preferences = {}
        if callable(getattr(self.settings_manager, "get_realtime_session_defaults", None)):
            preferences = self.settings_manager.get_realtime_session_defaults()
        elif callable(getattr(self.settings_manager, "get_realtime_preferences", None)):
            preferences = dict(self.settings_manager.get_realtime_preferences())

        self.gain_spin.setValue(float(preferences.get("default_gain", 1.0)))
        self.transcribe_check.setChecked(bool(preferences.get("enable_transcription", True)))
        self.translate_check.setChecked(bool(preferences.get("enable_translation", False)))
        self.save_recording_check.setChecked(bool(preferences.get("auto_save", True)))
        self.save_transcript_check.setChecked(bool(preferences.get("save_transcript", True)))
        self.create_calendar_event_check.setChecked(
            bool(preferences.get("create_calendar_event", True))
        )
        self.floating_button.setChecked(bool(preferences.get("floating_window_enabled", False)))

        default_input_source = preferences.get("default_input_source")
        if default_input_source in (None, "", "default"):
            selected_index = self.input_source_combo.findData(None)
        else:
            selected_index = self.input_source_combo.findData(default_input_source)
        if selected_index >= 0:
            self.input_source_combo.setCurrentIndex(selected_index)

        target_language = preferences.get("translation_target_lang", "en")
        target_index = self.translation_language_combo.findData(target_language)
        if target_index >= 0:
            self.translation_language_combo.setCurrentIndex(target_index)

    def refresh_input_sources(self) -> None:
        """Reload input devices from the shared recorder."""
        current_source = self.input_source_combo.currentData()
        self.input_source_combo.clear()
        self.input_source_combo.addItem(
            self.i18n.t("workspace.recording_console.default_input_source"),
            None,
        )

        input_sources = []
        if callable(getattr(self.realtime_recorder, "list_input_sources", None)):
            loaded_sources = self.realtime_recorder.list_input_sources()
            if isinstance(loaded_sources, (list, tuple)):
                input_sources = list(loaded_sources)

        for source in input_sources:
            index = source.get("index")
            name = source.get("name") or str(index)
            self.input_source_combo.addItem(name, index)

        selected_index = self.input_source_combo.findData(current_source)
        if selected_index >= 0:
            self.input_source_combo.setCurrentIndex(selected_index)

    def selected_input_source(self):
        """Return the selected device index or ``None`` for the default source."""
        return self.input_source_combo.currentData()

    def selected_target_language(self) -> str:
        """Return the selected target language code for summary rendering."""
        return self.translation_language_combo.currentData() or "en"

    def collect_session_options(self) -> dict:
        """Build runtime session options from the current full-panel state."""
        return {
            "default_gain": float(self.gain_spin.value()),
            "enable_transcription": self.transcribe_check.isChecked(),
            "enable_translation": self.translate_check.isChecked(),
            "translation_target_lang": self.translation_language_combo.currentData() or "en",
            "save_recording": self.save_recording_check.isChecked(),
            "save_transcript": self.save_transcript_check.isChecked(),
            "create_calendar_event": self.create_calendar_event_check.isChecked(),
            "floating_window_enabled": self.floating_button.isChecked(),
        }

    def sync_from_recorder(self, *, busy: bool = False) -> None:
        """Refresh preview text and marker count from the recorder."""
        status = {}
        status_getter = getattr(self.realtime_recorder, "get_recording_status", None)
        if callable(status_getter):
            loaded_status = status_getter()
            if isinstance(loaded_status, dict):
                status = loaded_status

        duration = float(status.get("duration", 0.0) or 0.0)
        minutes = int(duration // 60)
        seconds = int(duration % 60)
        self.summary_duration_label.setText(f"{minutes:02d}:{seconds:02d}")
        self.summary_input_label.setText(format_recording_input_source(self.i18n, status.get("input_device_name")))
        self.summary_target_label.setText(
            format_recording_target_language(self.i18n, self.selected_target_language())
        )
        is_recording = bool(getattr(self.realtime_recorder, "is_recording", False))
        self.summary_status_label.setText(
            format_recording_status(self.i18n, is_recording=is_recording, busy=busy)
        )

        transcription_getter = getattr(self.realtime_recorder, "get_accumulated_transcription", None)
        if callable(transcription_getter):
            loaded_text = transcription_getter()
            self.transcript_preview.setPlainText(loaded_text if isinstance(loaded_text, str) else "")

        translation_getter = getattr(self.realtime_recorder, "get_accumulated_translation", None)
        if callable(translation_getter):
            loaded_text = translation_getter()
            self.translation_preview.setPlainText(loaded_text if isinstance(loaded_text, str) else "")

        markers_getter = getattr(self.realtime_recorder, "get_markers", None)
        if callable(markers_getter):
            loaded_markers = markers_getter()
            marker_count = len(loaded_markers) if isinstance(loaded_markers, (list, tuple)) else 0
            self.marker_list_label.setText(str(marker_count))
        else:
            self.marker_list_label.setText("0")

    def _on_add_marker(self) -> None:
        add_marker = getattr(self.realtime_recorder, "add_marker", None)
        if callable(add_marker):
            add_marker()
            self.sync_from_recorder()
