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
Realtime recording settings page.

Provides UI for configuring real-time transcription and recording settings.
"""

import logging
import shutil
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from core.qt_imports import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QLabel,
    QLineEdit,
    QSlider,
    QSpinBox,
    Qt,
    QVBoxLayout,
)
from ui.base_widgets import (
    create_button,
    create_hbox,
    create_vbox,
)

from config.constants import (
    RECORDING_FORMAT_MP3,
    RECORDING_FORMAT_WAV,
    SUPPORTED_REALTIME_TRANSLATION_ENGINES,
    SUPPORTED_RECORDING_FORMATS,
    TRANSLATION_ENGINE_NONE,
    TRANSLATION_ENGINE_OPUS_MT,
)
from ui.constants import (
    GAIN_SLIDER_DEFAULT,
    GAIN_SLIDER_DIVISOR,
    GAIN_SLIDER_MAX,
    GAIN_SLIDER_MIN,
    GAIN_SLIDER_TICK_INTERVAL,
    ROLE_DEVICE_INFO,
    ROLE_FFMPEG_STATUS,
    SETTINGS_GAIN_VALUE_LABEL_MIN_WIDTH,
    STANDARD_LABEL_WIDTH,
    format_gain_display,
)
from ui.settings.base_page import BaseSettingsPage
from utils.i18n import I18nQtManager

logger = logging.getLogger("echonote.ui.settings.realtime")

VAD_THRESHOLD_MIN = 0.0
VAD_THRESHOLD_MAX = 1.0
VAD_THRESHOLD_STEP = 0.05
SILENCE_DURATION_MS_MIN = 0
SILENCE_DURATION_MS_MAX = 60000
SILENCE_DURATION_MS_STEP = 100
MIN_AUDIO_DURATION_SEC_MIN = 0.1
MIN_AUDIO_DURATION_SEC_MAX = 300.0
MIN_AUDIO_DURATION_SEC_STEP = 0.1


class RealtimeSettingsPage(BaseSettingsPage):
    """Settings page for real-time recording configuration."""

    def __init__(
        self,
        settings_manager,
        i18n: I18nQtManager,
        managers: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize realtime settings page.

        Args:
            settings_manager: SettingsManager instance
            i18n: Internationalization manager
            managers: Runtime managers dictionary
        """
        super().__init__(settings_manager, i18n)
        self.managers = managers or {}
        self.audio_capture = self.managers.get("audio_capture")
        self._loopback_checker = None
        self._mp3_supported = self._detect_mp3_support()

        # Setup UI
        self.setup_ui()

        logger.debug("Realtime settings page initialized")

    def setup_ui(self):
        """Set up the realtime settings UI."""
        # Audio input section
        self.audio_input_title = self.add_section_title(
            self.i18n.t("settings.realtime.audio_input")
        )

        # Default input source
        source_layout = create_hbox()
        self.source_label = QLabel(self.i18n.t("settings.realtime.input_source"))
        self.source_label.setMinimumWidth(STANDARD_LABEL_WIDTH)
        self.source_combo = QComboBox()
        self.source_combo.addItems([self.i18n.t("settings.realtime.default_device")])
        self.source_combo.currentTextChanged.connect(self._emit_changed)
        source_layout.addWidget(self.source_label)
        source_layout.addWidget(self.source_combo)
        source_layout.addStretch()
        self.content_layout.addLayout(source_layout)

        # Gain level
        gain_layout = create_vbox()
        self.gain_label = QLabel(self.i18n.t("settings.realtime.gain_level"))
        gain_layout.addWidget(self.gain_label)

        gain_slider_layout = create_hbox()
        self.gain_slider = QSlider(Qt.Orientation.Horizontal)
        # Gain slider range: 0.1x to 2.0x (multiplied by 100 for integer slider)
        self.gain_slider.setMinimum(GAIN_SLIDER_MIN)
        self.gain_slider.setMaximum(GAIN_SLIDER_MAX)
        self.gain_slider.setValue(GAIN_SLIDER_DEFAULT)
        self.gain_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.gain_slider.setTickInterval(GAIN_SLIDER_TICK_INTERVAL)
        self.gain_slider.valueChanged.connect(self._on_gain_changed)

        self.gain_value_label = QLabel(
            format_gain_display(GAIN_SLIDER_DEFAULT / GAIN_SLIDER_DIVISOR)
        )
        self.gain_value_label.setMinimumWidth(SETTINGS_GAIN_VALUE_LABEL_MIN_WIDTH)

        self.gain_min_label = QLabel(format_gain_display(GAIN_SLIDER_MIN / GAIN_SLIDER_DIVISOR))
        self.gain_max_label = QLabel(format_gain_display(GAIN_SLIDER_MAX / GAIN_SLIDER_DIVISOR))
        gain_slider_layout.addWidget(self.gain_min_label)
        gain_slider_layout.addWidget(self.gain_slider, stretch=1)
        gain_slider_layout.addWidget(self.gain_max_label)
        gain_slider_layout.addWidget(self.gain_value_label)

        gain_layout.addLayout(gain_slider_layout)
        self.content_layout.addLayout(gain_layout)

        # Loopback status and setup entry (for system audio / meeting capture).
        loopback_status_layout = create_hbox()
        self.loopback_status_label = QLabel(self.i18n.t("settings.realtime.loopback_status"))
        self.loopback_status_label.setMinimumWidth(STANDARD_LABEL_WIDTH)

        self.loopback_status_text = QLabel()
        self.loopback_status_text.setProperty("role", ROLE_FFMPEG_STATUS)
        self.loopback_status_text.setProperty("state", "missing")

        self.loopback_setup_btn = create_button(
            self.i18n.t("settings.realtime.loopback_view_guide")
        )
        self.loopback_setup_btn.clicked.connect(self._on_show_loopback_guide)

        loopback_status_layout.addWidget(self.loopback_status_label)
        loopback_status_layout.addWidget(self.loopback_status_text)
        loopback_status_layout.addWidget(self.loopback_setup_btn)
        loopback_status_layout.addStretch()
        self.content_layout.addLayout(loopback_status_layout)

        self.loopback_info_label = QLabel()
        self.loopback_info_label.setWordWrap(True)
        self.loopback_info_label.setProperty("role", ROLE_DEVICE_INFO)
        self.content_layout.addWidget(self.loopback_info_label)
        self._refresh_loopback_status()

        self.add_section_spacing()

        # Recording settings section
        self.recording_title = self.add_section_title(self.i18n.t("settings.realtime.recording"))

        # Recording format
        format_layout = create_hbox()
        self.format_label = QLabel(self.i18n.t("settings.realtime.recording_format"))
        self.format_label.setMinimumWidth(STANDARD_LABEL_WIDTH)
        self.format_combo = QComboBox()
        self.format_combo.addItems(SUPPORTED_RECORDING_FORMATS)
        if not self._mp3_supported:
            index = self.format_combo.findText(RECORDING_FORMAT_MP3)
            if index >= 0:
                model = self.format_combo.model()
                model.setData(model.index(index, 0), False, Qt.ItemDataRole.EnabledRole)
            self.format_combo.setCurrentText(RECORDING_FORMAT_WAV)
            self.format_combo.setToolTip(self.i18n.t("settings.realtime.mp3_requires_ffmpeg"))
        else:
            self.format_combo.setToolTip(self.i18n.t("settings.realtime.mp3_enabled_ffmpeg"))
        self.format_combo.currentTextChanged.connect(self._emit_changed)
        format_layout.addWidget(self.format_label)
        format_layout.addWidget(self.format_combo)
        format_layout.addStretch()
        self.content_layout.addLayout(format_layout)

        self.format_hint_label = QLabel()
        self.format_hint_label.setWordWrap(True)
        self.format_hint_label.setProperty("role", ROLE_DEVICE_INFO)
        self._update_format_hint_text()
        self.content_layout.addWidget(self.format_hint_label)

        # Recording save path
        path_layout = create_hbox()
        self.path_label = QLabel(self.i18n.t("settings.realtime.recording_path"))
        self.path_label.setMinimumWidth(STANDARD_LABEL_WIDTH)
        self.path_edit = QLineEdit()
        self.path_edit.textChanged.connect(self._emit_changed)
        self.browse_button = create_button(self.i18n.t("settings.realtime.browse"))
        self.browse_button.clicked.connect(self._on_browse_clicked)
        path_layout.addWidget(self.path_label)
        path_layout.addWidget(self.path_edit, stretch=1)
        path_layout.addWidget(self.browse_button)
        self.content_layout.addLayout(path_layout)

        # Auto-save preference
        self.auto_save_check = QCheckBox(self.i18n.t("settings.realtime.auto_save"))
        self.auto_save_check.stateChanged.connect(self._emit_changed)
        self.content_layout.addWidget(self.auto_save_check)

        self.add_section_spacing()

        # Translation settings section
        self.translation_title = self.add_section_title(
            self.i18n.t("settings.realtime.translation")
        )

        # Translation engine
        translation_layout = create_hbox()
        self.translation_label = QLabel(self.i18n.t("settings.realtime.translation_engine"))
        self.translation_label.setMinimumWidth(STANDARD_LABEL_WIDTH)
        self.translation_combo = QComboBox()
        self._populate_translation_options()
        self.translation_combo.currentIndexChanged.connect(self._on_translation_engine_changed)
        self.translation_combo.currentTextChanged.connect(self._emit_changed)
        translation_layout.addWidget(self.translation_label)
        translation_layout.addWidget(self.translation_combo)
        translation_layout.addStretch()
        self.content_layout.addLayout(translation_layout)

        self.floating_window_check = QCheckBox(
            self.i18n.t("settings.realtime.floating_window_enabled")
        )
        self.floating_window_check.stateChanged.connect(self._on_floating_window_toggled)
        self.floating_window_check.stateChanged.connect(self._emit_changed)
        self.content_layout.addWidget(self.floating_window_check)

        self.hide_main_window_check = QCheckBox(
            self.i18n.t("settings.realtime.hide_main_window_when_floating")
        )
        self.hide_main_window_check.stateChanged.connect(self._emit_changed)
        self.content_layout.addWidget(self.hide_main_window_check)

        self.floating_window_always_on_top_check = QCheckBox(
            self.i18n.t("settings.realtime.floating_window_always_on_top")
        )
        self.floating_window_always_on_top_check.stateChanged.connect(self._emit_changed)
        self.content_layout.addWidget(self.floating_window_always_on_top_check)

        # Opus-MT: language pair selection (visible only when Opus-MT is selected)
        self._opus_mt_section = create_vbox()

        src_tgt_layout = create_hbox()
        self.translation_source_label = QLabel(self.i18n.t("settings.realtime.source_language"))
        self.translation_source_label.setMinimumWidth(STANDARD_LABEL_WIDTH)
        self.translation_source_combo = QComboBox()
        self.translation_target_label = QLabel(self.i18n.t("settings.realtime.target_language"))
        self.translation_target_combo = QComboBox()
        src_tgt_layout.addWidget(self.translation_source_label)
        src_tgt_layout.addWidget(self.translation_source_combo)
        src_tgt_layout.addWidget(self.translation_target_label)
        src_tgt_layout.addWidget(self.translation_target_combo)
        src_tgt_layout.addStretch()
        self._opus_mt_section.addLayout(src_tgt_layout)

        self.opus_mt_status_label = QLabel()
        self.opus_mt_status_label.setProperty("role", ROLE_DEVICE_INFO)
        self.opus_mt_status_label.setWordWrap(True)
        self._opus_mt_section.addWidget(self.opus_mt_status_label)

        self._populate_opus_mt_language_options()
        self.translation_source_combo.currentIndexChanged.connect(self._on_opus_mt_source_changed)
        self.translation_source_combo.currentIndexChanged.connect(self._emit_changed)
        self.translation_target_combo.currentIndexChanged.connect(self._update_opus_mt_status)
        self.translation_target_combo.currentIndexChanged.connect(self._emit_changed)

        self.content_layout.addLayout(self._opus_mt_section)
        self._opus_mt_section.setEnabled(False)
        # hide all widgets in the section initially
        for i in range(self._opus_mt_section.count()):
            item = self._opus_mt_section.itemAt(i)
            if item and item.widget():
                item.widget().setVisible(False)
        self._on_floating_window_toggled(self.floating_window_check.checkState().value)

        self.add_section_spacing()

        # Processing settings section
        self.processing_title = self.add_section_title(self.i18n.t("settings.realtime.processing"))

        self.save_transcript_check = QCheckBox(self.i18n.t("settings.realtime.save_transcript"))
        self.save_transcript_check.stateChanged.connect(self._emit_changed)
        self.content_layout.addWidget(self.save_transcript_check)

        self.create_calendar_event_check = QCheckBox(
            self.i18n.t("settings.realtime.create_calendar_event")
        )
        self.create_calendar_event_check.stateChanged.connect(self._emit_changed)
        self.content_layout.addWidget(self.create_calendar_event_check)

        vad_layout = create_hbox()
        self.vad_threshold_label = QLabel(self.i18n.t("settings.realtime.vad_threshold"))
        self.vad_threshold_label.setMinimumWidth(STANDARD_LABEL_WIDTH)
        self.vad_threshold_spin = QDoubleSpinBox()
        self.vad_threshold_spin.setRange(VAD_THRESHOLD_MIN, VAD_THRESHOLD_MAX)
        self.vad_threshold_spin.setSingleStep(VAD_THRESHOLD_STEP)
        self.vad_threshold_spin.setDecimals(2)
        self.vad_threshold_spin.valueChanged.connect(self._emit_changed)
        vad_layout.addWidget(self.vad_threshold_label)
        vad_layout.addWidget(self.vad_threshold_spin)
        vad_layout.addStretch()
        self.content_layout.addLayout(vad_layout)

        silence_layout = create_hbox()
        self.silence_duration_label = QLabel(self.i18n.t("settings.realtime.silence_duration_ms"))
        self.silence_duration_label.setMinimumWidth(STANDARD_LABEL_WIDTH)
        self.silence_duration_spin = QSpinBox()
        self.silence_duration_spin.setRange(SILENCE_DURATION_MS_MIN, SILENCE_DURATION_MS_MAX)
        self.silence_duration_spin.setSingleStep(SILENCE_DURATION_MS_STEP)
        self.silence_duration_spin.valueChanged.connect(self._emit_changed)
        silence_layout.addWidget(self.silence_duration_label)
        silence_layout.addWidget(self.silence_duration_spin)
        silence_layout.addStretch()
        self.content_layout.addLayout(silence_layout)

        min_audio_layout = create_hbox()
        self.min_audio_duration_label = QLabel(self.i18n.t("settings.realtime.min_audio_duration"))
        self.min_audio_duration_label.setMinimumWidth(STANDARD_LABEL_WIDTH)
        self.min_audio_duration_spin = QDoubleSpinBox()
        self.min_audio_duration_spin.setRange(
            MIN_AUDIO_DURATION_SEC_MIN, MIN_AUDIO_DURATION_SEC_MAX
        )
        self.min_audio_duration_spin.setSingleStep(MIN_AUDIO_DURATION_SEC_STEP)
        self.min_audio_duration_spin.setDecimals(1)
        self.min_audio_duration_spin.valueChanged.connect(self._emit_changed)
        min_audio_layout.addWidget(self.min_audio_duration_label)
        min_audio_layout.addWidget(self.min_audio_duration_spin)
        min_audio_layout.addStretch()
        self.content_layout.addLayout(min_audio_layout)

        self._update_spinbox_suffixes()

        # Add stretch at the end
        self.content_layout.addStretch()

    def _on_gain_changed(self, value: int):
        """
        Handle gain slider change.

        Args:
            value: Slider value (10-200)
        """
        gain = value / GAIN_SLIDER_DIVISOR
        self.gain_value_label.setText(format_gain_display(gain))
        self._emit_changed()

    def _on_browse_clicked(self):
        """Handle browse button click."""
        current_path = self.path_edit.text()
        if not current_path:
            current_path = str(Path.home() / "Documents" / "EchoNote" / "Recordings")

        directory = QFileDialog.getExistingDirectory(
            self, self.i18n.t("settings.realtime.select_directory"), current_path
        )

        if directory:
            self.path_edit.setText(directory)

    def _get_loopback_checker(self):
        """Return cached loopback checker bound to current audio backend."""
        from utils.loopback_checker import get_loopback_checker

        if self._loopback_checker is None:
            self._loopback_checker = get_loopback_checker(self.audio_capture)
        else:
            self._loopback_checker.set_audio_capture(self.audio_capture)
        return self._loopback_checker

    def _set_status_state(self, state: str) -> None:
        """Apply semantic status state for theme-aware label colors."""
        self.loopback_status_text.setProperty("state", state)
        style = self.loopback_status_text.style()
        if style is not None:
            style.unpolish(self.loopback_status_text)
            style.polish(self.loopback_status_text)
        self.loopback_status_text.update()

    def _refresh_loopback_status(self) -> None:
        """Refresh loopback availability status and details."""
        if not hasattr(self, "loopback_status_text") or not hasattr(self, "loopback_info_label"):
            return

        checker = self._get_loopback_checker()
        loopback_devices = checker.get_loopback_devices()
        if loopback_devices:
            device_names = ", ".join(
                str(device.get("name", "")).strip() for device in loopback_devices if device
            )
            self.loopback_status_text.setText(self.i18n.t("settings.realtime.loopback_installed"))
            self._set_status_state("available")
            self.loopback_info_label.setText(
                self.i18n.t(
                    "settings.realtime.loopback_detected_devices",
                    devices=device_names or self.i18n.t("settings.realtime.default_device"),
                )
            )
            return

        if checker.is_loopback_available():
            self.loopback_status_text.setText(self.i18n.t("settings.realtime.loopback_not_ready"))
            self._set_status_state("missing")
            self.loopback_info_label.setText(
                self.i18n.t("settings.realtime.loopback_restart_required_hint")
            )
            return

        self.loopback_status_text.setText(self.i18n.t("settings.realtime.loopback_not_installed"))
        self._set_status_state("missing")
        self.loopback_info_label.setText(self.i18n.t("settings.realtime.loopback_missing_hint"))

    def _on_show_loopback_guide(self) -> None:
        """Show loopback setup dialog and refresh status after closing."""
        from ui.dialogs.loopback_install_dialog import LoopbackInstallDialog

        checker = self._get_loopback_checker()
        title, instructions = checker.get_installation_instructions(self.i18n)
        dialog = LoopbackInstallDialog(title, instructions, self.i18n, self)
        dialog.exec()
        self._refresh_loopback_status()

    def load_settings(self):
        """Load realtime settings into UI."""
        try:
            # Input source
            input_source = self.settings_manager.get_setting("realtime.default_input_source")
            if input_source:
                self.source_combo.setCurrentIndex(0)

            # Gain level
            gain = self.settings_manager.get_setting("realtime.default_gain")
            if gain is not None:
                self.gain_slider.setValue(int(gain * GAIN_SLIDER_DIVISOR))

            # Recording format
            recording_format = self.settings_manager.get_setting("realtime.recording_format")
            if recording_format:
                if recording_format == RECORDING_FORMAT_MP3 and not self._mp3_supported:
                    logger.warning(
                        "MP3 format selected in settings but FFmpeg is unavailable. "
                        "Falling back to WAV in UI."
                    )
                    self.format_combo.setCurrentText(RECORDING_FORMAT_WAV)
                else:
                    index = self.format_combo.findText(recording_format)
                    if index >= 0:
                        self.format_combo.setCurrentIndex(index)

            # Recording save path
            save_path = self.settings_manager.get_setting("realtime.recording_save_path")
            if save_path:
                expanded_path = Path(save_path).expanduser()
                self.path_edit.setText(str(expanded_path))

            # Auto-save (if this setting exists)
            auto_save = self.settings_manager.get_setting("realtime.auto_save")
            if auto_save is not None:
                self.auto_save_check.setChecked(auto_save)

            translation_engine = self.settings_manager.get_setting("realtime.translation_engine")
            translation_preferences = {}
            if hasattr(self.settings_manager, "get_realtime_translation_preferences"):
                translation_preferences = self.settings_manager.get_realtime_translation_preferences()

            selected_engine = (
                translation_preferences.get("translation_engine", translation_engine)
                if isinstance(translation_preferences, dict)
                else translation_engine
            )
            if selected_engine in SUPPORTED_REALTIME_TRANSLATION_ENGINES:
                index = self.translation_combo.findData(selected_engine)
                if index >= 0:
                    self.translation_combo.setCurrentIndex(index)

            source_lang = (
                translation_preferences.get("translation_source_lang")
                if isinstance(translation_preferences, dict)
                else None
            ) or self.settings_manager.get_setting("realtime.translation_source_lang")
            if source_lang:
                index = self.translation_source_combo.findData(source_lang)
                if index >= 0:
                    self.translation_source_combo.setCurrentIndex(index)

            target_lang = (
                translation_preferences.get("translation_target_lang")
                if isinstance(translation_preferences, dict)
                else None
            ) or self.settings_manager.get_setting("realtime.translation_target_lang")
            if target_lang:
                index = self.translation_target_combo.findData(target_lang)
                if index >= 0:
                    self.translation_target_combo.setCurrentIndex(index)

            floating_enabled = (
                translation_preferences.get("floating_window_enabled")
                if isinstance(translation_preferences, dict)
                else None
            )
            if floating_enabled is None:
                floating_enabled = self.settings_manager.get_setting(
                    "realtime.floating_window_enabled"
                )
            self.floating_window_check.setChecked(bool(floating_enabled))

            hide_main = (
                translation_preferences.get("hide_main_window_when_floating")
                if isinstance(translation_preferences, dict)
                else None
            )
            if hide_main is None:
                hide_main = self.settings_manager.get_setting(
                    "realtime.hide_main_window_when_floating"
                )
            self.hide_main_window_check.setChecked(bool(hide_main))
            always_on_top = (
                translation_preferences.get("floating_window_always_on_top")
                if isinstance(translation_preferences, dict)
                else None
            )
            if always_on_top is None:
                always_on_top = self.settings_manager.get_setting(
                    "realtime.floating_window_always_on_top"
                )
            if always_on_top is None:
                always_on_top = True
            self.floating_window_always_on_top_check.setChecked(bool(always_on_top))
            self._on_floating_window_toggled(self.floating_window_check.checkState().value)

            save_transcript = self.settings_manager.get_setting("realtime.save_transcript")
            if save_transcript is not None:
                self.save_transcript_check.setChecked(bool(save_transcript))

            create_calendar_event = self.settings_manager.get_setting(
                "realtime.create_calendar_event"
            )
            if create_calendar_event is not None:
                self.create_calendar_event_check.setChecked(bool(create_calendar_event))

            vad_threshold = self.settings_manager.get_setting("realtime.vad_threshold")
            if isinstance(vad_threshold, (int, float)):
                self.vad_threshold_spin.setValue(float(vad_threshold))

            silence_duration_ms = self.settings_manager.get_setting("realtime.silence_duration_ms")
            if isinstance(silence_duration_ms, int):
                self.silence_duration_spin.setValue(silence_duration_ms)

            min_audio_duration = self.settings_manager.get_setting("realtime.min_audio_duration")
            if isinstance(min_audio_duration, (int, float)):
                self.min_audio_duration_spin.setValue(float(min_audio_duration))

            self._refresh_loopback_status()
            logger.debug("Realtime settings loaded")

        except Exception as e:
            logger.error(f"Error loading realtime settings: {e}")

    def save_settings(self):
        """Save realtime settings from UI."""
        try:
            # Input source
            self._set_setting_or_raise("realtime.default_input_source", "default")

            # Gain level
            gain = self.gain_slider.value() / GAIN_SLIDER_DIVISOR
            self._set_setting_or_raise("realtime.default_gain", gain)

            # Recording format
            self._set_setting_or_raise("realtime.recording_format", self._get_selected_format())

            # Recording save path
            self._set_setting_or_raise("realtime.recording_save_path", self.path_edit.text())

            # Auto-save
            self._set_setting_or_raise("realtime.auto_save", self.auto_save_check.isChecked())

            translation_engine = self.translation_combo.currentData()
            if translation_engine is None:
                translation_engine = TRANSLATION_ENGINE_NONE
            self._set_setting_or_raise("realtime.translation_engine", translation_engine)

            source_lang = self.translation_source_combo.currentData() or "auto"
            target_lang = self.translation_target_combo.currentData() or "en"
            self._set_setting_or_raise("realtime.translation_source_lang", source_lang)
            self._set_setting_or_raise("realtime.translation_target_lang", target_lang)
            self._set_setting_or_raise(
                "realtime.floating_window_enabled", self.floating_window_check.isChecked()
            )
            self._set_setting_or_raise(
                "realtime.hide_main_window_when_floating",
                self.hide_main_window_check.isChecked(),
            )
            self._set_setting_or_raise(
                "realtime.floating_window_always_on_top",
                self.floating_window_always_on_top_check.isChecked(),
            )

            self._set_setting_or_raise(
                "realtime.save_transcript", self.save_transcript_check.isChecked()
            )
            self._set_setting_or_raise(
                "realtime.create_calendar_event", self.create_calendar_event_check.isChecked()
            )
            self._set_setting_or_raise("realtime.vad_threshold", self.vad_threshold_spin.value())
            self._set_setting_or_raise(
                "realtime.silence_duration_ms", self.silence_duration_spin.value()
            )
            self._set_setting_or_raise(
                "realtime.min_audio_duration", self.min_audio_duration_spin.value()
            )

            logger.debug("Realtime settings saved")

        except Exception as e:
            logger.error(f"Error saving realtime settings: {e}")
            raise

    def validate_settings(self) -> Tuple[bool, str]:
        """
        Validate realtime settings.

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Validate save path
        save_path = self.path_edit.text()
        if not save_path or not save_path.strip():
            return False, self.i18n.t("settings.realtime.error.empty_path")

        # Check if path is valid
        try:
            path = Path(save_path).expanduser()
            if not path.exists():
                path.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            return False, self.i18n.t("settings.realtime.error.invalid_path", error=str(e))

        return True, ""

    def update_translations(self):
        """Update UI text after language change."""
        # Update section titles
        if hasattr(self, "audio_input_title"):
            self.audio_input_title.setText(self.i18n.t("settings.realtime.audio_input"))
        if hasattr(self, "recording_title"):
            self.recording_title.setText(self.i18n.t("settings.realtime.recording"))
        if hasattr(self, "translation_title"):
            self.translation_title.setText(self.i18n.t("settings.realtime.translation"))
        if hasattr(self, "processing_title"):
            self.processing_title.setText(self.i18n.t("settings.realtime.processing"))

        # Update labels
        if hasattr(self, "source_label"):
            self.source_label.setText(self.i18n.t("settings.realtime.input_source"))
        if hasattr(self, "gain_label"):
            self.gain_label.setText(self.i18n.t("settings.realtime.gain_level"))
        if hasattr(self, "format_label"):
            self.format_label.setText(self.i18n.t("settings.realtime.recording_format"))
        if hasattr(self, "path_label"):
            self.path_label.setText(self.i18n.t("settings.realtime.recording_path"))
        if hasattr(self, "translation_label"):
            self.translation_label.setText(self.i18n.t("settings.realtime.translation_engine"))
        if hasattr(self, "floating_window_check"):
            self.floating_window_check.setText(
                self.i18n.t("settings.realtime.floating_window_enabled")
            )
        if hasattr(self, "hide_main_window_check"):
            self.hide_main_window_check.setText(
                self.i18n.t("settings.realtime.hide_main_window_when_floating")
            )
        if hasattr(self, "floating_window_always_on_top_check"):
            self.floating_window_always_on_top_check.setText(
                self.i18n.t("settings.realtime.floating_window_always_on_top")
            )
        if hasattr(self, "loopback_status_label"):
            self.loopback_status_label.setText(self.i18n.t("settings.realtime.loopback_status"))
        if hasattr(self, "vad_threshold_label"):
            self.vad_threshold_label.setText(self.i18n.t("settings.realtime.vad_threshold"))
        if hasattr(self, "silence_duration_label"):
            self.silence_duration_label.setText(
                self.i18n.t("settings.realtime.silence_duration_ms")
            )
        if hasattr(self, "min_audio_duration_label"):
            self.min_audio_duration_label.setText(
                self.i18n.t("settings.realtime.min_audio_duration")
            )

        # Update buttons
        if hasattr(self, "browse_button"):
            self.browse_button.setText(self.i18n.t("settings.realtime.browse"))
        if hasattr(self, "loopback_setup_btn"):
            self.loopback_setup_btn.setText(self.i18n.t("settings.realtime.loopback_view_guide"))

        # Update checkbox
        if hasattr(self, "auto_save_check"):
            self.auto_save_check.setText(self.i18n.t("settings.realtime.auto_save"))
        if hasattr(self, "save_transcript_check"):
            self.save_transcript_check.setText(self.i18n.t("settings.realtime.save_transcript"))
        if hasattr(self, "create_calendar_event_check"):
            self.create_calendar_event_check.setText(
                self.i18n.t("settings.realtime.create_calendar_event")
            )

        if hasattr(self, "format_hint_label"):
            self._update_format_hint_text()
        self._refresh_loopback_status()
        self._update_spinbox_suffixes()

        if hasattr(self, "format_combo"):
            if not self._mp3_supported:
                self.format_combo.setToolTip(self.i18n.t("settings.realtime.mp3_requires_ffmpeg"))
            else:
                self.format_combo.setToolTip(self.i18n.t("settings.realtime.mp3_enabled_ffmpeg"))

        # Update combo box options
        if hasattr(self, "source_combo"):
            current_index = self.source_combo.currentIndex()
            self.source_combo.blockSignals(True)
            self.source_combo.clear()
            self.source_combo.addItems([self.i18n.t("settings.realtime.default_device")])
            self.source_combo.setCurrentIndex(current_index)
            self.source_combo.blockSignals(False)

        if hasattr(self, "translation_combo"):
            current_engine = self.translation_combo.currentData()
            self.translation_combo.blockSignals(True)
            self._populate_translation_options()
            if current_engine is not None:
                index = self.translation_combo.findData(current_engine)
                if index >= 0:
                    self.translation_combo.setCurrentIndex(index)
            self.translation_combo.blockSignals(False)

        if hasattr(self, "translation_source_label"):
            self.translation_source_label.setText(self.i18n.t("settings.realtime.source_language"))
        if hasattr(self, "translation_target_label"):
            self.translation_target_label.setText(self.i18n.t("settings.realtime.target_language"))
        if hasattr(self, "opus_mt_status_label"):
            self._update_opus_mt_status()
        if hasattr(self, "floating_window_check"):
            self._on_floating_window_toggled(self.floating_window_check.checkState().value)

    def _update_spinbox_suffixes(self) -> None:
        """Update localized unit suffixes for numeric controls."""
        if hasattr(self, "silence_duration_spin"):
            self.silence_duration_spin.setSuffix(
                f" {self.i18n.t('settings.realtime.milliseconds_short')}"
            )
        if hasattr(self, "min_audio_duration_spin"):
            self.min_audio_duration_spin.setSuffix(
                f" {self.i18n.t('settings.realtime.seconds_short')}"
            )

    def _populate_translation_options(self) -> None:
        """从 SUPPORTED_REALTIME_TRANSLATION_ENGINES 动态生成翻译引擎下拉选项，避免硬编码。"""
        if not hasattr(self, "translation_combo"):
            return
        self.translation_combo.clear()
        for engine in SUPPORTED_REALTIME_TRANSLATION_ENGINES:
            # i18n key 规则：settings.realtime.engine_<engine_id>
            label = self.i18n.t(f"settings.realtime.engine_{engine}")
            self.translation_combo.addItem(label, engine)

    def _populate_opus_mt_language_options(self) -> None:
        """从 TranslationModelRegistry 读取语言对，填充源/目标语言下拉框。"""
        from core.models.translation_registry import get_translation_registry

        registry = get_translation_registry()
        sources = registry.get_available_sources()

        self.translation_source_combo.blockSignals(True)
        self.translation_source_combo.clear()
        self.translation_source_combo.addItem(self.i18n.t("settings.realtime.auto_detect"), "auto")
        for lang in sources:
            self.translation_source_combo.addItem(lang, lang)
        self.translation_source_combo.blockSignals(False)

        self._refresh_target_options()

    def _refresh_target_options(self) -> None:
        """根据当前源语言刷新目标语言选项。"""
        from core.models.translation_registry import get_translation_registry

        registry = get_translation_registry()
        source = self.translation_source_combo.currentData()
        targets = registry.get_available_targets(source if source != "auto" else None)

        self.translation_target_combo.blockSignals(True)
        current_target = self.translation_target_combo.currentData()
        self.translation_target_combo.clear()
        for lang in targets:
            self.translation_target_combo.addItem(lang, lang)
        # 恢复之前的目标语言选择
        idx = self.translation_target_combo.findData(current_target)
        if idx >= 0:
            self.translation_target_combo.setCurrentIndex(idx)
        self.translation_target_combo.blockSignals(False)
        self._update_opus_mt_status()

    def _on_opus_mt_source_changed(self) -> None:
        self._refresh_target_options()

    def _update_opus_mt_status(self) -> None:
        """显示当前语言对的模型下载状态。"""
        if not hasattr(self, "opus_mt_status_label"):
            return
        source = self.translation_source_combo.currentData() or "auto"
        target = self.translation_target_combo.currentData() or "en"

        # 通过 managers 获取 model_manager（如果有）
        model_manager = self.managers.get("model_manager") if hasattr(self, "managers") else None
        if not model_manager:
            return

        # 使用管理器统一的逻辑查找最佳模型
        model_info = model_manager.get_best_translation_model(
            source, target, auto_detect=(source == "auto")
        )

        if model_info and model_info.is_downloaded:
            self.opus_mt_status_label.setText(
                self.i18n.t("settings.realtime.opus_mt_ready", model=model_info.model_id)
            )
        elif model_info:
            self.opus_mt_status_label.setText(
                self.i18n.t("settings.realtime.opus_mt_not_downloaded", model=model_info.model_id)
            )
        else:
            self.opus_mt_status_label.setText(self.i18n.t("settings.realtime.opus_mt_unavailable"))

    def _on_translation_engine_changed(self) -> None:
        """切换翻译引擎时显示/隐藏 Opus-MT 语言配置区域。"""
        engine = self.translation_combo.currentData()
        is_opus = engine == TRANSLATION_ENGINE_OPUS_MT
        if hasattr(self, "_opus_mt_section"):
            self._opus_mt_section.setEnabled(is_opus)
            for i in range(self._opus_mt_section.count()):
                item = self._opus_mt_section.itemAt(i)
                if item and item.widget():
                    item.widget().setVisible(is_opus)
        if is_opus:
            self._update_opus_mt_status()

    def _on_floating_window_toggled(self, state: int) -> None:
        """Enable hide-main option only when floating mode is enabled."""
        enabled = bool(state)
        self.hide_main_window_check.setEnabled(enabled)
        self.floating_window_always_on_top_check.setEnabled(enabled)
        if not enabled:
            self.hide_main_window_check.setChecked(False)

    def _detect_mp3_support(self) -> bool:
        try:
            from utils.ffmpeg_checker import get_ffmpeg_checker
        except Exception:  # noqa: BLE001
            fallback_available = shutil.which("ffmpeg") is not None
            logger.debug(
                "FFmpeg checker unavailable when building realtime settings page. "
                "Fallback detection: %s",
                fallback_available,
            )
            return fallback_available

        checker = get_ffmpeg_checker()
        available = checker.is_ffmpeg_available()
        logger.debug("MP3 support in settings UI: %s", available)
        return available

    def _update_format_hint_text(self):
        if not hasattr(self, "format_hint_label"):
            return
        if self._mp3_supported:
            self.format_hint_label.setText(self.i18n.t("settings.realtime.mp3_enabled_ffmpeg"))
        else:
            self.format_hint_label.setText(self.i18n.t("settings.realtime.mp3_requires_ffmpeg"))

    def _get_selected_format(self) -> str:
        current = self.format_combo.currentText()
        if current == RECORDING_FORMAT_MP3 and not self._mp3_supported:
            return RECORDING_FORMAT_WAV
        return current
