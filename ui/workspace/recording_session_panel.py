# SPDX-License-Identifier: Apache-2.0
"""Compact recording settings panel used by the shell-level dock popup."""

from __future__ import annotations

from core.qt_imports import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from ui.base_widgets import BaseWidget
from ui.common.secondary_transcribe_dialog import (
    list_downloaded_transcription_models,
    resolve_preferred_downloaded_transcription_model,
)
from ui.constants import (
    REALTIME_CONSOLE_SECTION_MARGINS,
    REALTIME_CONSOLE_SECTION_SPACING,
    ROLE_REALTIME_CONSOLE_SECTION,
    ROLE_REALTIME_CONSOLE_SECTION_TITLE,
    ROLE_REALTIME_FIELD_CONTROL,
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
    """Lightweight settings form for the compact recording dock."""

    def __init__(
        self,
        realtime_recorder,
        i18n,
        *,
        settings_manager=None,
        model_manager=None,
        parent=None,
    ):
        super().__init__(i18n, parent)
        self.realtime_recorder = realtime_recorder
        self.settings_manager = settings_manager
        self.model_manager = model_manager
        self._floating_window_enabled = False
        self._init_ui()
        self.load_defaults()

    def _init_ui(self) -> None:
        self.setProperty("role", ROLE_REALTIME_CONSOLE_SECTION)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(*REALTIME_CONSOLE_SECTION_MARGINS)
        layout.setSpacing(REALTIME_CONSOLE_SECTION_SPACING)

        self.title_label = QLabel(self)
        self.title_label.setProperty("role", ROLE_REALTIME_CONSOLE_SECTION_TITLE)
        layout.addWidget(self.title_label)

        self.input_section_label = QLabel(self)
        layout.addWidget(self.input_section_label)

        input_form = QGridLayout()
        input_form.setHorizontalSpacing(REALTIME_CONSOLE_SECTION_SPACING)
        input_form.setVerticalSpacing(REALTIME_CONSOLE_SECTION_SPACING)

        self.input_source_label = QLabel(self)
        input_form.addWidget(self.input_source_label, 0, 0)
        self.input_source_combo = QComboBox(self)
        self.input_source_combo.setProperty("role", ROLE_REALTIME_FIELD_CONTROL)
        input_form.addWidget(self.input_source_combo, 0, 1)

        self.gain_label = QLabel(self)
        input_form.addWidget(self.gain_label, 0, 2)
        self.gain_spin = QDoubleSpinBox(self)
        self.gain_spin.setRange(0.1, 4.0)
        self.gain_spin.setSingleStep(0.1)
        self.gain_spin.setProperty("role", ROLE_REALTIME_FIELD_CONTROL)
        input_form.addWidget(self.gain_spin, 0, 3)
        layout.addLayout(input_form)

        self.realtime_section_label = QLabel(self)
        layout.addWidget(self.realtime_section_label)

        processing_form = QGridLayout()
        processing_form.setHorizontalSpacing(REALTIME_CONSOLE_SECTION_SPACING)
        processing_form.setVerticalSpacing(REALTIME_CONSOLE_SECTION_SPACING)

        self.translation_language_label = QLabel(self)
        processing_form.addWidget(self.translation_language_label, 0, 0)
        self.translation_language_combo = QComboBox(self)
        self.translation_language_combo.setProperty("role", ROLE_REALTIME_FIELD_CONTROL)
        for language in _DEFAULT_LANGUAGE_ITEMS:
            self.translation_language_combo.addItem(language, language)
        processing_form.addWidget(self.translation_language_combo, 0, 1)

        self.realtime_model_label = QLabel(self)
        processing_form.addWidget(self.realtime_model_label, 1, 0)
        self.model_combo = QComboBox(self)
        self.model_combo.setProperty("role", ROLE_REALTIME_FIELD_CONTROL)
        processing_form.addWidget(self.model_combo, 1, 1)

        live_toggle_row = QHBoxLayout()
        live_toggle_row.setContentsMargins(0, 0, 0, 0)
        live_toggle_row.setSpacing(REALTIME_CONSOLE_SECTION_SPACING)

        self.transcribe_check = QCheckBox(self)
        live_toggle_row.addWidget(self.transcribe_check)

        self.translate_check = QCheckBox(self)
        live_toggle_row.addWidget(self.translate_check)

        live_toggle_row.addStretch()
        processing_form.addLayout(live_toggle_row, 2, 0, 1, 2)
        layout.addLayout(processing_form)

        self.recording_output_section_label = QLabel(self)
        layout.addWidget(self.recording_output_section_label)

        output_form = QGridLayout()
        output_form.setHorizontalSpacing(REALTIME_CONSOLE_SECTION_SPACING)
        output_form.setVerticalSpacing(REALTIME_CONSOLE_SECTION_SPACING)

        self.save_recording_check = QCheckBox(self)
        output_form.addWidget(self.save_recording_check, 0, 0)

        self.save_transcript_check = QCheckBox(self)
        output_form.addWidget(self.save_transcript_check, 0, 1)

        self.create_calendar_event_check = QCheckBox(self)
        output_form.addWidget(self.create_calendar_event_check, 0, 2)

        self.more_settings_button = QPushButton(self)
        output_form.addWidget(self.more_settings_button, 0, 3)

        layout.addLayout(output_form)

        self.secondary_section_label = QLabel(self)
        layout.addWidget(self.secondary_section_label)

        secondary_form = QGridLayout()
        secondary_form.setHorizontalSpacing(REALTIME_CONSOLE_SECTION_SPACING)
        secondary_form.setVerticalSpacing(REALTIME_CONSOLE_SECTION_SPACING)

        self.auto_secondary_check = QCheckBox(self)
        secondary_form.addWidget(self.auto_secondary_check, 0, 0, 1, 2)

        self.secondary_model_label = QLabel(self)
        secondary_form.addWidget(self.secondary_model_label, 1, 0)
        self.secondary_model_combo = QComboBox(self)
        self.secondary_model_combo.setProperty("role", ROLE_REALTIME_FIELD_CONTROL)
        secondary_form.addWidget(self.secondary_model_combo, 1, 1)

        layout.addLayout(secondary_form)
        self.refresh_input_sources()
        self.refresh_transcription_models()
        self.update_translations()

    def update_translations(self) -> None:
        self.title_label.setText(self.i18n.t("workspace.recording_console.session_options_title"))
        self.input_section_label.setText(self.i18n.t("workspace.recording_console.input_section"))
        self.realtime_section_label.setText(
            self.i18n.t("workspace.recording_console.realtime_processing_section")
        )
        self.recording_output_section_label.setText(
            self.i18n.t("workspace.recording_console.recording_output_section")
        )
        self.secondary_section_label.setText(
            self.i18n.t("workspace.recording_console.secondary_processing_section")
        )
        self.input_source_label.setText(self.i18n.t("settings.realtime.audio_input"))
        self.gain_label.setText(self.i18n.t("settings.realtime.gain_level"))
        self.translation_language_label.setText(
            self.i18n.t("workspace.recording_console.translation_target_language_label")
        )
        self.realtime_model_label.setText(
            self.i18n.t("workspace.recording_console.realtime_transcription_model_label")
        )
        self.secondary_model_label.setText(
            self.i18n.t("workspace.recording_console.secondary_default_model_label")
        )
        self.transcribe_check.setText(self.i18n.t("workspace.recording_console.enable_transcription"))
        self.translate_check.setText(self.i18n.t("workspace.recording_console.enable_translation"))
        self.save_recording_check.setText(self.i18n.t("settings.realtime.auto_save"))
        self.save_transcript_check.setText(self.i18n.t("settings.realtime.save_transcript"))
        self.create_calendar_event_check.setText(
            self.i18n.t("settings.realtime.create_calendar_event")
        )
        self.auto_secondary_check.setText(
            self.i18n.t("workspace.recording_console.auto_secondary_processing")
        )
        self.more_settings_button.setText(self.i18n.t("settings.title"))
        if self.input_source_combo.count() > 0:
            self.input_source_combo.setItemText(
                0, self.i18n.t("workspace.recording_console.default_input_source")
            )
        if self.model_combo.count() > 0 and not self.model_combo.isEnabled():
            self.model_combo.setItemText(0, self.i18n.t("realtime_record.no_models_available"))
        if self.secondary_model_combo.count() > 0 and not self.secondary_model_combo.isEnabled():
            self.secondary_model_combo.setItemText(
                0,
                self.i18n.t("realtime_record.no_models_available"),
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
        self._floating_window_enabled = bool(preferences.get("floating_window_enabled", False))
        self.auto_secondary_check.setChecked(bool(preferences.get("auto_secondary_processing", False)))

        default_input_source = preferences.get("default_input_source")
        if default_input_source in (None, "", "default"):
            selected_index = self.input_source_combo.findData(None)
        else:
            selected_index = self.input_source_combo.findData(default_input_source)
        if selected_index >= 0:
            self.input_source_combo.setCurrentIndex(selected_index)

        target_language = (
            preferences.get("target_language")
            or preferences.get("translation_target_lang")
            or "en"
        )
        target_index = self.translation_language_combo.findData(target_language)
        if target_index >= 0:
            self.translation_language_combo.setCurrentIndex(target_index)

        configured_model_name = str(preferences.get("transcription_model_name") or "").strip()
        if not configured_model_name and callable(getattr(self.settings_manager, "get_setting", None)):
            configured_model_name = str(
                self.settings_manager.get_setting("transcription.faster_whisper.model_size") or ""
            ).strip()
        self._select_transcription_model(configured_model_name)

        configured_secondary_model_name = ""
        if callable(getattr(self.settings_manager, "get_setting", None)):
            configured_secondary_model_name = str(
                self.settings_manager.get_setting("transcription.secondary_model_size") or ""
            ).strip()
        if not configured_secondary_model_name:
            configured_secondary_model_name = configured_model_name
        self._select_secondary_transcription_model(configured_secondary_model_name)

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

    def refresh_transcription_models(self) -> None:
        """Reload downloaded transcription models for quick session switching."""
        selected_model = self.selected_transcription_model_name()
        selected_secondary_model = self.selected_secondary_model_name()
        self.model_combo.clear()
        self.secondary_model_combo.clear()

        downloaded_models = list_downloaded_transcription_models(self.model_manager)
        if not downloaded_models:
            self.model_combo.addItem(self.i18n.t("realtime_record.no_models_available"), None)
            self.model_combo.setEnabled(False)
            self.secondary_model_combo.addItem(
                self.i18n.t("realtime_record.no_models_available"),
                None,
            )
            self.secondary_model_combo.setEnabled(False)
            return

        self.model_combo.setEnabled(True)
        self.secondary_model_combo.setEnabled(True)
        for model in downloaded_models:
            self.model_combo.addItem(model.name, model)
            self.secondary_model_combo.addItem(model.name, model)
        self._select_transcription_model(selected_model)
        self._select_secondary_transcription_model(selected_secondary_model)

    def _select_transcription_model(self, preferred_name: str) -> None:
        self._select_model_combo(self.model_combo, preferred_name)

    def _select_secondary_transcription_model(self, preferred_name: str) -> None:
        self._select_model_combo(self.secondary_model_combo, preferred_name)

    def _select_model_combo(self, combo: QComboBox, preferred_name: str) -> None:
        if not combo.isEnabled():
            return
        if preferred_name:
            preferred_index = combo.findText(preferred_name)
            if preferred_index >= 0:
                combo.setCurrentIndex(preferred_index)
                return
        fallback = resolve_preferred_downloaded_transcription_model(
            self.model_manager,
            preferred_names=(preferred_name,),
        )
        if fallback is None:
            return
        fallback_index = combo.findText(fallback["model_name"])
        if fallback_index >= 0:
            combo.setCurrentIndex(fallback_index)

    def selected_input_source(self):
        """Return the selected device index or ``None`` for the default source."""
        return self.input_source_combo.currentData()

    def selected_target_language(self) -> str:
        """Return the selected target language code for summary rendering."""
        return self.translation_language_combo.currentData() or "en"

    def selected_transcription_model_name(self) -> str:
        return self._selected_model_name(self.model_combo)

    def selected_transcription_model_path(self) -> str:
        return self._selected_model_path(self.model_combo)

    def selected_secondary_model_name(self) -> str:
        return self._selected_model_name(self.secondary_model_combo)

    def selected_secondary_model_path(self) -> str:
        return self._selected_model_path(self.secondary_model_combo)

    @staticmethod
    def _selected_model_name(combo: QComboBox) -> str:
        model_info = combo.currentData()
        return str(getattr(model_info, "name", "") or "").strip()

    @staticmethod
    def _selected_model_path(combo: QComboBox) -> str:
        model_info = combo.currentData()
        return str(getattr(model_info, "local_path", "") or "").strip()

    def transcription_enabled(self) -> bool:
        return self.transcribe_check.isChecked()

    def translation_enabled(self) -> bool:
        return self.translate_check.isChecked()

    def floating_window_enabled(self) -> bool:
        return bool(self._floating_window_enabled)

    def set_floating_window_enabled(self, enabled: bool) -> None:
        self._floating_window_enabled = bool(enabled)

    def auto_secondary_processing_enabled(self) -> bool:
        return self.auto_secondary_check.isChecked()

    def collect_session_options(self) -> dict:
        """Build runtime session options from the current panel state."""
        target_language = self.selected_target_language()
        return {
            "default_gain": float(self.gain_spin.value()),
            "enable_transcription": self.transcribe_check.isChecked(),
            "enable_translation": self.translate_check.isChecked(),
            "model_name": self.selected_transcription_model_name(),
            "model_path": self.selected_transcription_model_path(),
            "secondary_model_name": self.selected_secondary_model_name(),
            "secondary_model_path": self.selected_secondary_model_path(),
            "target_language": target_language,
            "translation_target_lang": target_language,
            "save_recording": self.save_recording_check.isChecked(),
            "save_transcript": self.save_transcript_check.isChecked(),
            "create_calendar_event": self.create_calendar_event_check.isChecked(),
            "floating_window_enabled": self.floating_window_enabled(),
            "auto_secondary_processing": self.auto_secondary_processing_enabled(),
        }
