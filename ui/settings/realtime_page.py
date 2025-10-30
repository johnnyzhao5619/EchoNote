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
from typing import Tuple

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSlider,
    QVBoxLayout,
)

from ui.base_widgets import create_hbox, create_vbox, create_button
from ui.settings.base_page import BaseSettingsPage
from utils.i18n import I18nQtManager

logger = logging.getLogger("echonote.ui.settings.realtime")


class RealtimeSettingsPage(BaseSettingsPage):
    """Settings page for real-time recording configuration."""

    def __init__(self, settings_manager, i18n: I18nQtManager):
        """
        Initialize realtime settings page.

        Args:
            settings_manager: SettingsManager instance
            i18n: Internationalization manager
        """
        super().__init__(settings_manager, i18n)
        self._mp3_supported = self._detect_mp3_support()

        # Setup UI
        self.setup_ui()

        logger.debug("Realtime settings page initialized")

    def setup_ui(self):
        """Set up the realtime settings UI."""
        # Audio input section
        from PySide6.QtGui import QFont

        font = QFont()
        font.setPointSize(12)
        font.setBold(True)

        self.audio_input_title = QLabel(self.i18n.t("settings.realtime.audio_input"))
        self.audio_input_title.setFont(font)
        self.content_layout.addWidget(self.audio_input_title)

        # Default input source
        source_layout = create_hbox()
        self.source_label = QLabel(self.i18n.t("settings.realtime.input_source"))
        self.source_label.setMinimumWidth(200)
        self.source_combo = QComboBox()
        self.source_combo.addItems(
            [
                self.i18n.t("settings.realtime.default_device"),
                self.i18n.t("settings.realtime.system_audio"),
            ]
        )
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
        self.gain_slider.setMinimum(10)  # 0.1 * 100
        self.gain_slider.setMaximum(200)  # 2.0 * 100
        self.gain_slider.setValue(100)  # 1.0 * 100
        self.gain_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.gain_slider.setTickInterval(10)
        self.gain_slider.valueChanged.connect(self._on_gain_changed)

        self.gain_value_label = QLabel("1.0x")
        self.gain_value_label.setMinimumWidth(50)

        self.gain_min_label = QLabel("0.1x")
        self.gain_max_label = QLabel("2.0x")
        gain_slider_layout.addWidget(self.gain_min_label)
        gain_slider_layout.addWidget(self.gain_slider, stretch=1)
        gain_slider_layout.addWidget(self.gain_max_label)
        gain_slider_layout.addWidget(self.gain_value_label)

        gain_layout.addLayout(gain_slider_layout)
        self.content_layout.addLayout(gain_layout)

        self.add_spacing(20)

        # Recording settings section
        self.recording_title = QLabel(self.i18n.t("settings.realtime.recording"))
        self.recording_title.setFont(font)
        self.content_layout.addWidget(self.recording_title)

        # Recording format
        format_layout = create_hbox()
        self.format_label = QLabel(self.i18n.t("settings.realtime.recording_format"))
        self.format_label.setMinimumWidth(200)
        self.format_combo = QComboBox()
        self.format_combo.addItems(["wav", "mp3"])
        if not self._mp3_supported:
            index = self.format_combo.findText("mp3")
            if index >= 0:
                model = self.format_combo.model()
                model.setData(model.index(index, 0), False, Qt.ItemDataRole.EnabledRole)
            self.format_combo.setCurrentText("wav")
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
        self.format_hint_label.setProperty("role", "device-info")
        self._update_format_hint_text()
        self.content_layout.addWidget(self.format_hint_label)

        # Recording save path
        path_layout = create_hbox()
        self.path_label = QLabel(self.i18n.t("settings.realtime.recording_path"))
        self.path_label.setMinimumWidth(200)
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

        self.add_spacing(20)

        # Translation settings section
        self.translation_title = QLabel(self.i18n.t("settings.realtime.translation"))
        self.translation_title.setFont(font)
        self.content_layout.addWidget(self.translation_title)

        # Translation engine
        translation_layout = create_hbox()
        self.translation_label = QLabel(self.i18n.t("settings.realtime.translation_engine"))
        self.translation_label.setMinimumWidth(200)
        self.translation_combo = QComboBox()
        self.translation_combo.addItems(
            [self.i18n.t("settings.realtime.no_translation"), "Google Translate"]
        )
        self.translation_combo.currentTextChanged.connect(self._emit_changed)
        translation_layout.addWidget(self.translation_label)
        translation_layout.addWidget(self.translation_combo)
        translation_layout.addStretch()
        self.content_layout.addLayout(translation_layout)

        # Add stretch at the end
        self.content_layout.addStretch()

    def _on_gain_changed(self, value: int):
        """
        Handle gain slider change.

        Args:
            value: Slider value (10-200)
        """
        gain = value / 100.0
        self.gain_value_label.setText(f"{gain:.1f}x")
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

    def load_settings(self):
        """Load realtime settings into UI."""
        try:
            # Input source
            input_source = self.settings_manager.get_setting("realtime.default_input_source")
            if input_source:
                # Map internal value to display text
                if input_source == "default":
                    index = 0
                else:
                    index = 1
                self.source_combo.setCurrentIndex(index)

            # Gain level
            gain = self.settings_manager.get_setting("realtime.default_gain")
            if gain:
                self.gain_slider.setValue(int(gain * 100))

            # Recording format
            recording_format = self.settings_manager.get_setting("realtime.recording_format")
            if recording_format:
                if recording_format == "mp3" and not self._mp3_supported:
                    logger.warning(
                        "MP3 format selected in settings but FFmpeg is unavailable. "
                        "Falling back to WAV in UI."
                    )
                    self.format_combo.setCurrentText("wav")
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

            logger.debug("Realtime settings loaded")

        except Exception as e:
            logger.error(f"Error loading realtime settings: {e}")

    def save_settings(self):
        """Save realtime settings from UI."""
        try:
            # Input source
            source_index = self.source_combo.currentIndex()
            source_value = "default" if source_index == 0 else "system"
            self.settings_manager.set_setting("realtime.default_input_source", source_value)

            # Gain level
            gain = self.gain_slider.value() / 100.0
            self.settings_manager.set_setting("realtime.default_gain", gain)

            # Recording format
            self.settings_manager.set_setting(
                "realtime.recording_format", self._get_selected_format()
            )

            # Recording save path
            self.settings_manager.set_setting("realtime.recording_save_path", self.path_edit.text())

            # Auto-save
            self.settings_manager.set_setting(
                "realtime.auto_save", self.auto_save_check.isChecked()
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

        # Update buttons
        if hasattr(self, "browse_button"):
            self.browse_button.setText(self.i18n.t("settings.realtime.browse"))

        # Update checkbox
        if hasattr(self, "auto_save_check"):
            self.auto_save_check.setText(self.i18n.t("settings.realtime.auto_save"))

        if hasattr(self, "format_hint_label"):
            self._update_format_hint_text()

        if hasattr(self, "format_combo"):
            if not self._mp3_supported:
                self.format_combo.setToolTip(self.i18n.t("settings.realtime.mp3_requires_ffmpeg"))
            else:
                self.format_combo.setToolTip(self.i18n.t("settings.realtime.mp3_enabled_ffmpeg"))

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
        if current == "mp3" and not self._mp3_supported:
            return "wav"
        return current
