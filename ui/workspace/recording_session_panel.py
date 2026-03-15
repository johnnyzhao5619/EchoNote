# SPDX-License-Identifier: Apache-2.0
"""Expanded recording session controls for the shell dock."""

from __future__ import annotations

from core.qt_imports import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)
from ui.base_widgets import BaseWidget

_DEFAULT_LANGUAGE_ITEMS = ("auto", "en", "zh", "fr")


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

        self.input_source_label = QLabel(self)
        layout.addWidget(self.input_source_label)

        self.input_source_combo = QComboBox(self)
        layout.addWidget(self.input_source_combo)

        self.gain_label = QLabel(self)
        layout.addWidget(self.gain_label)

        self.gain_spin = QDoubleSpinBox(self)
        self.gain_spin.setRange(0.1, 4.0)
        self.gain_spin.setSingleStep(0.1)
        layout.addWidget(self.gain_spin)

        self.transcribe_check = QCheckBox(self)
        layout.addWidget(self.transcribe_check)

        self.translate_check = QCheckBox(self)
        layout.addWidget(self.translate_check)

        self.translation_language_combo = QComboBox(self)
        for language in _DEFAULT_LANGUAGE_ITEMS:
            self.translation_language_combo.addItem(language, language)
        layout.addWidget(self.translation_language_combo)

        self.save_recording_check = QCheckBox(self)
        layout.addWidget(self.save_recording_check)

        self.save_transcript_check = QCheckBox(self)
        layout.addWidget(self.save_transcript_check)

        self.create_calendar_event_check = QCheckBox(self)
        layout.addWidget(self.create_calendar_event_check)

        self.start_button = QPushButton(self)
        layout.addWidget(self.start_button)

        self.stop_button = QPushButton(self)
        layout.addWidget(self.stop_button)

        self.marker_button = QPushButton(self)
        self.marker_button.clicked.connect(self._on_add_marker)
        layout.addWidget(self.marker_button)

        self.marker_list_label = QLabel(self)
        layout.addWidget(self.marker_list_label)

        self.floating_button = QPushButton(self)
        layout.addWidget(self.floating_button)

        self.more_settings_button = QPushButton(self)
        layout.addWidget(self.more_settings_button)

        self.transcript_preview = QPlainTextEdit(self)
        self.transcript_preview.setReadOnly(True)
        layout.addWidget(self.transcript_preview)

        self.translation_preview = QPlainTextEdit(self)
        self.translation_preview.setReadOnly(True)
        layout.addWidget(self.translation_preview)

        self.refresh_input_sources()
        self.update_translations()

    def update_translations(self) -> None:
        self.input_source_label.setText(self.i18n.t("settings.realtime.audio_input"))
        self.gain_label.setText(self.i18n.t("settings.realtime.gain_level"))
        self.transcribe_check.setText(self.i18n.t("workspace.record_button"))
        self.translate_check.setText(self.i18n.t("settings.translation.title"))
        self.save_recording_check.setText(self.i18n.t("settings.realtime.auto_save"))
        self.save_transcript_check.setText(self.i18n.t("settings.realtime.save_transcript"))
        self.create_calendar_event_check.setText(
            self.i18n.t("settings.realtime.create_calendar_event")
        )
        self.start_button.setText(self.i18n.t("workspace.record_button"))
        self.stop_button.setText(self.i18n.t("workspace.stop_button"))
        self.marker_button.setText(self.i18n.t("workspace.add_marker"))
        self.floating_button.setText(self.i18n.t("settings.realtime.floating_window"))
        self.more_settings_button.setText(self.i18n.t("settings.title"))

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

        target_language = preferences.get("translation_target_lang", "en")
        target_index = self.translation_language_combo.findData(target_language)
        if target_index >= 0:
            self.translation_language_combo.setCurrentIndex(target_index)

    def refresh_input_sources(self) -> None:
        """Reload input devices from the shared recorder."""
        current_source = self.input_source_combo.currentData()
        self.input_source_combo.clear()
        self.input_source_combo.addItem("default", None)

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
            "floating_window_enabled": False,
        }

    def sync_from_recorder(self) -> None:
        """Refresh preview text and marker count from the recorder."""
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
