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
Transcription settings page.

Provides UI for configuring batch transcription settings.
"""

import logging
from pathlib import Path
from typing import Any, Dict, Tuple

from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from core.models.registry import get_default_model_names
from ui.base_widgets import create_button, create_hbox, create_vbox
from ui.settings.base_page import BaseSettingsPage
from utils.i18n import I18nQtManager

logger = logging.getLogger("echonote.ui.settings.transcription")


class TranscriptionSettingsPage(BaseSettingsPage):
    """Settings page for transcription configuration."""

    def __init__(self, settings_manager, i18n: I18nQtManager, managers: Dict[str, Any]):
        """
        Initialize transcription settings page.

        Args:
            settings_manager: SettingsManager instance
            i18n: Internationalization manager
            managers: Dictionary of other managers
        """
        super().__init__(settings_manager, i18n)
        self.managers = managers

        # Get model_manager from managers dictionary
        self.model_manager = managers.get("model_manager")

        # Setup UI
        self.setup_ui()

        # Connect model_manager signals if available
        if self.model_manager:
            self.model_manager.models_updated.connect(self._update_model_list)
            logger.debug("Connected to model_manager.models_updated signal")

        logger.debug("Transcription settings page initialized")

    def setup_ui(self):
        """Set up the transcription settings UI."""
        # General settings section
        self.general_title = QLabel(self.i18n.t("settings.transcription.general"))
        from PySide6.QtGui import QFont

        font = QFont()
        font.setPointSize(12)
        font.setBold(True)
        self.general_title.setFont(font)
        self.content_layout.addWidget(self.general_title)

        # Default output format
        format_layout = create_hbox()
        self.format_label = QLabel(self.i18n.t("settings.transcription.output_format"))
        self.format_label.setMinimumWidth(200)
        self.format_combo = QComboBox()
        self.format_combo.addItems(["txt", "srt", "md"])
        self.format_combo.currentTextChanged.connect(self._emit_changed)
        format_layout.addWidget(self.format_label)
        format_layout.addWidget(self.format_combo)
        format_layout.addStretch()
        self.content_layout.addLayout(format_layout)

        # Concurrent tasks
        concurrent_layout = create_hbox()
        self.concurrent_label = QLabel(self.i18n.t("settings.transcription.concurrent_tasks"))
        self.concurrent_label.setMinimumWidth(200)
        self.concurrent_spin = QSpinBox()
        self.concurrent_spin.setMinimum(1)
        self.concurrent_spin.setMaximum(5)
        self.concurrent_spin.setValue(2)
        self.concurrent_spin.valueChanged.connect(self._emit_changed)
        concurrent_layout.addWidget(self.concurrent_label)
        concurrent_layout.addWidget(self.concurrent_spin)
        concurrent_layout.addStretch()
        self.content_layout.addLayout(concurrent_layout)

        self.add_spacing(20)

        # FFmpeg status section
        self.ffmpeg_title = QLabel(self.i18n.t("settings.transcription.ffmpeg_status"))
        self.ffmpeg_title.setFont(font)
        self.content_layout.addWidget(self.ffmpeg_title)

        # FFmpeg status display
        ffmpeg_status_layout = create_hbox()
        self.ffmpeg_status_label = QLabel(self.i18n.t("ffmpeg.ffmpeg_label"))
        self.ffmpeg_status_label.setMinimumWidth(200)

        # Check FFmpeg availability
        from utils.ffmpeg_checker import get_ffmpeg_checker

        ffmpeg_checker = get_ffmpeg_checker()

        self.ffmpeg_status_text = QLabel()
        if ffmpeg_checker.is_ffmpeg_available() and ffmpeg_checker.is_ffprobe_available():
            self.ffmpeg_status_text.setText(self.i18n.t("settings.transcription.ffmpeg_installed"))
            self.ffmpeg_status_text.setProperty("role", "ffmpeg-status")
            self.ffmpeg_status_text.setProperty("state", "success")
        else:
            self.ffmpeg_status_text.setText(
                self.i18n.t("settings.transcription.ffmpeg_not_installed")
            )
            self.ffmpeg_status_text.setProperty("role", "ffmpeg-status")
            self.ffmpeg_status_text.setProperty("state", "missing")

        ffmpeg_status_layout.addWidget(self.ffmpeg_status_label)
        ffmpeg_status_layout.addWidget(self.ffmpeg_status_text)

        # Installation guide button
        self.ffmpeg_install_btn = create_button(
            self.i18n.t("settings.transcription.ffmpeg_view_guide")
        )
        self.ffmpeg_install_btn.clicked.connect(self._on_show_ffmpeg_guide)
        ffmpeg_status_layout.addWidget(self.ffmpeg_install_btn)

        ffmpeg_status_layout.addStretch()
        self.content_layout.addLayout(ffmpeg_status_layout)

        # FFmpeg info
        self.ffmpeg_info = QLabel(self.i18n.t("settings.transcription.ffmpeg_info"))
        self.ffmpeg_info.setWordWrap(True)
        self.ffmpeg_info.setProperty("role", "device-info")
        self.content_layout.addWidget(self.ffmpeg_info)

        self.add_spacing(20)

        # Default save path
        path_layout = create_hbox()
        self.path_label = QLabel(self.i18n.t("settings.transcription.save_path"))
        self.path_label.setMinimumWidth(200)
        self.path_edit = QLineEdit()
        self.path_edit.textChanged.connect(self._emit_changed)
        self.browse_button = create_button(self.i18n.t("settings.transcription.browse"))
        self.browse_button.clicked.connect(self._on_browse_clicked)
        path_layout.addWidget(self.path_label)
        path_layout.addWidget(self.path_edit, stretch=1)
        path_layout.addWidget(self.browse_button)
        self.content_layout.addLayout(path_layout)

        self.add_spacing(20)

        # Engine settings section
        self.engine_title = QLabel(self.i18n.t("settings.transcription.engine"))
        self.engine_title.setFont(font)
        self.content_layout.addWidget(self.engine_title)

        # Engine selection
        engine_layout = create_hbox()
        self.engine_label = QLabel(self.i18n.t("settings.transcription.engine_select"))
        self.engine_label.setMinimumWidth(200)
        self.engine_combo = QComboBox()
        self.engine_combo.addItems(["faster-whisper", "openai", "google", "azure"])
        self.engine_combo.currentTextChanged.connect(self._on_engine_changed)
        engine_layout.addWidget(self.engine_label)
        engine_layout.addWidget(self.engine_combo)
        engine_layout.addStretch()
        self.content_layout.addLayout(engine_layout)

        # Engine-specific configuration
        self._create_engine_configs()

        # Add stretch at the end
        self.content_layout.addStretch()

    def _create_engine_configs(self):
        """Create engine-specific configuration sections."""
        # Faster-Whisper configuration
        self.whisper_group = QGroupBox(self.i18n.t("settings.transcription.whisper_config"))
        whisper_layout = QFormLayout()

        # Model size
        self.model_size_combo = QComboBox()
        self.model_size_combo.addItems(list(get_default_model_names()))
        self.model_size_combo.currentTextChanged.connect(self._emit_changed)
        self.model_size_label = QLabel(self.i18n.t("settings.transcription.model_size"))
        whisper_layout.addRow(self.model_size_label, self.model_size_combo)

        # Device
        self.device_combo = QComboBox()
        self._populate_device_options()
        self.device_combo.currentTextChanged.connect(self._emit_changed)
        self.device_label = QLabel(self.i18n.t("settings.transcription.device"))

        # Add device info label
        device_layout = create_vbox()
        device_layout.addWidget(self.device_combo)
        self.device_info_label = QLabel()
        self.device_info_label.setProperty("role", "device-info")
        self.device_info_label.setWordWrap(True)
        device_layout.addWidget(self.device_info_label)

        whisper_layout.addRow(self.device_label, device_layout)

        # Update device info when selection changes
        self.device_combo.currentTextChanged.connect(self._update_device_info)

        # Compute type
        self.compute_type_combo = QComboBox()
        self.compute_type_combo.addItems(["int8", "float16", "float32"])
        self.compute_type_combo.currentTextChanged.connect(self._emit_changed)
        self.compute_type_label = QLabel(self.i18n.t("settings.transcription.compute_type"))
        whisper_layout.addRow(self.compute_type_label, self.compute_type_combo)

        self.whisper_group.setLayout(whisper_layout)
        self.content_layout.addWidget(self.whisper_group)

        # Cloud engine configuration (will be shown/hidden based on selection)
        self.cloud_group = QGroupBox(self.i18n.t("settings.transcription.cloud_config"))
        cloud_layout = create_vbox()

        # Note about API keys
        self.note_label = QLabel(self.i18n.t("settings.transcription.api_key_note"))
        self.note_label.setWordWrap(True)
        self.note_label.setProperty("role", "auto-start-desc")
        cloud_layout.addWidget(self.note_label)

        # API Key configuration section
        self._create_api_key_section(cloud_layout)

        # Add refresh button for usage statistics
        refresh_layout = create_hbox()
        refresh_layout.addStretch()
        self.refresh_usage_button = create_button(
            self.i18n.t("settings.transcription.refresh_usage")
        )
        self.refresh_usage_button.clicked.connect(self._load_usage_statistics)
        refresh_layout.addWidget(self.refresh_usage_button)
        cloud_layout.addLayout(refresh_layout)

        self.cloud_group.setLayout(cloud_layout)
        self.cloud_group.setVisible(False)
        self.content_layout.addWidget(self.cloud_group)

    def _update_model_list(self):
        """Update model_size_combo with downloaded models from ModelManager."""
        if not self.model_manager:
            logger.debug("No model_manager available, skipping model list update")
            return

        # Save current selection
        current_model = self.model_size_combo.currentText()

        # Clear existing items
        self.model_size_combo.clear()

        # Get downloaded models
        downloaded_models = self.model_manager.get_downloaded_models()

        if not downloaded_models:
            # No models downloaded
            self.model_size_combo.addItem(
                self.i18n.t("settings.transcription.please_download_model")
            )
            self.model_size_combo.setEnabled(False)
            logger.info(
                self.i18n.t(
                    "logging.settings.transcription_page.no_models_downloaded_selector_disabled"
                )
            )
        else:
            # Add downloaded models
            self.model_size_combo.setEnabled(True)
            for model in downloaded_models:
                self.model_size_combo.addItem(model.name)

            # Try to restore previous selection
            index = self.model_size_combo.findText(current_model)
            if index >= 0:
                self.model_size_combo.setCurrentIndex(index)
                logger.debug(f"Restored model selection: {current_model}")
            else:
                # Previous selection not available, try to select configured model
                configured_model = (
                    self.settings_manager.get_setting("transcription.faster_whisper.model_size")
                    or "base"
                )

                default_index = self.model_size_combo.findText(configured_model)
                if default_index >= 0:
                    self.model_size_combo.setCurrentIndex(default_index)
                    logger.info(f"Selected configured model: {configured_model}")
                else:
                    # Default not available, select first model
                    if self.model_size_combo.count() > 0:
                        self.model_size_combo.setCurrentIndex(0)
                        logger.info(
                            f"Selected first available model: "
                            f"{self.model_size_combo.currentText()}"
                        )

            logger.info(f"Updated model list with {len(downloaded_models)} models")

    def _create_api_key_section(self, parent_layout: QVBoxLayout):
        """
        Create API key configuration section.

        Args:
            parent_layout: Parent layout to add widgets to
        """
        from PySide6.QtWidgets import QFormLayout, QGroupBox, QPushButton

        # OpenAI API Key
        self.openai_group = QGroupBox(self.i18n.t("settings.transcription.cloud_api_openai"))
        openai_layout = QFormLayout()

        self.openai_key_edit = QLineEdit()
        self.openai_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.openai_key_edit.setPlaceholderText(
            self.i18n.t("settings.transcription.api_key_placeholder")
        )
        self.openai_key_edit.textChanged.connect(self._emit_changed)

        key_layout = create_hbox()
        key_layout.addWidget(self.openai_key_edit)

        self.openai_show_button = create_button("👁")
        self.openai_show_button.setMaximumWidth(40)
        self.openai_show_button.setCheckable(True)
        self.openai_show_button.clicked.connect(
            lambda: self._toggle_password_visibility(self.openai_key_edit, self.openai_show_button)
        )
        key_layout.addWidget(self.openai_show_button)

        self.openai_test_button = create_button(
            self.i18n.t("settings.transcription.test_connection")
        )
        self.openai_test_button.clicked.connect(lambda: self._test_api_key("openai"))
        key_layout.addWidget(self.openai_test_button)

        self.openai_api_key_label = QLabel(self.i18n.t("settings.transcription.api_key_label"))
        openai_layout.addRow(self.openai_api_key_label, key_layout)

        # Usage statistics
        self.openai_usage_label = QLabel(self.i18n.t("settings.transcription.no_usage_data"))
        self.openai_usage_label.setProperty("role", "time-display")
        self.openai_monthly_usage_label = QLabel(
            self.i18n.t("settings.transcription.monthly_usage")
        )
        openai_layout.addRow(self.openai_monthly_usage_label, self.openai_usage_label)

        self.openai_group.setLayout(openai_layout)
        parent_layout.addWidget(self.openai_group)

        # Google API Key
        self.google_group = QGroupBox(self.i18n.t("settings.transcription.cloud_api_google"))
        google_layout = QFormLayout()

        self.google_key_edit = QLineEdit()
        self.google_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.google_key_edit.textChanged.connect(self._emit_changed)

        google_key_layout = create_hbox()
        google_key_layout.addWidget(self.google_key_edit)

        self.google_show_button = create_button("👁")
        self.google_show_button.setMaximumWidth(40)
        self.google_show_button.setCheckable(True)
        self.google_show_button.clicked.connect(
            lambda: self._toggle_password_visibility(self.google_key_edit, self.google_show_button)
        )
        google_key_layout.addWidget(self.google_show_button)

        self.google_test_button = create_button(
            self.i18n.t("settings.transcription.test_connection")
        )
        self.google_test_button.clicked.connect(lambda: self._test_api_key("google"))
        google_key_layout.addWidget(self.google_test_button)

        self.google_api_key_label = QLabel(self.i18n.t("settings.transcription.api_key_label"))
        google_layout.addRow(self.google_api_key_label, google_key_layout)

        self.google_usage_label = QLabel(self.i18n.t("settings.transcription.no_usage_data"))
        self.google_usage_label.setProperty("role", "time-display")
        self.google_monthly_usage_label = QLabel(
            self.i18n.t("settings.transcription.monthly_usage")
        )
        google_layout.addRow(self.google_monthly_usage_label, self.google_usage_label)

        self.google_group.setLayout(google_layout)
        parent_layout.addWidget(self.google_group)

        # Azure API Key
        self.azure_group = QGroupBox(self.i18n.t("settings.transcription.cloud_api_azure"))
        azure_layout = QFormLayout()

        self.azure_key_edit = QLineEdit()
        self.azure_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.azure_key_edit.textChanged.connect(self._emit_changed)

        azure_key_layout = create_hbox()
        azure_key_layout.addWidget(self.azure_key_edit)

        self.azure_show_button = create_button("👁")
        self.azure_show_button.setMaximumWidth(40)
        self.azure_show_button.setCheckable(True)
        self.azure_show_button.clicked.connect(
            lambda: self._toggle_password_visibility(self.azure_key_edit, self.azure_show_button)
        )
        azure_key_layout.addWidget(self.azure_show_button)

        self.azure_test_button = create_button(
            self.i18n.t("settings.transcription.test_connection")
        )
        self.azure_test_button.clicked.connect(lambda: self._test_api_key("azure"))
        azure_key_layout.addWidget(self.azure_test_button)

        self.azure_api_key_label = QLabel(self.i18n.t("settings.transcription.api_key_label"))
        azure_layout.addRow(self.azure_api_key_label, azure_key_layout)

        # Azure region
        self.azure_region_edit = QLineEdit()
        self.azure_region_edit.setPlaceholderText(
            self.i18n.t("settings.transcription.azure_region_placeholder")
        )
        self.azure_region_edit.textChanged.connect(self._emit_changed)
        self.azure_region_label = QLabel(self.i18n.t("settings.transcription.azure_region_label"))
        azure_layout.addRow(self.azure_region_label, self.azure_region_edit)

        self.azure_usage_label = QLabel(self.i18n.t("settings.transcription.no_usage_data"))
        self.azure_usage_label.setProperty("role", "time-display")
        self.azure_monthly_usage_label = QLabel(self.i18n.t("settings.transcription.monthly_usage"))
        azure_layout.addRow(self.azure_monthly_usage_label, self.azure_usage_label)

        self.azure_group.setLayout(azure_layout)
        parent_layout.addWidget(self.azure_group)

    def _toggle_password_visibility(self, line_edit: QLineEdit, button: QPushButton):
        """
        Toggle password visibility for API key input.

        Args:
            line_edit: Line edit widget
            button: Show/hide button
        """
        if button.isChecked():
            line_edit.setEchoMode(QLineEdit.EchoMode.Normal)
        else:
            line_edit.setEchoMode(QLineEdit.EchoMode.Password)

    def _test_api_key(self, provider: str):
        """
        Test API key connection.

        Args:
            provider: Provider name (openai/google/azure)
        """
        import asyncio

        from PySide6.QtWidgets import QApplication, QMessageBox

        # Get API key
        if provider == "openai":
            api_key = self.openai_key_edit.text()
            test_button = self.openai_test_button
        elif provider == "google":
            api_key = self.google_key_edit.text()
            test_button = self.google_test_button
        elif provider == "azure":
            api_key = self.azure_key_edit.text()
            test_button = self.azure_test_button
        else:
            return

        if not api_key or not api_key.strip():
            self.show_warning(
                self.i18n.t("settings.transcription.test_failed"),
                self.i18n.t("settings.transcription.empty_api_key"),
            )
            return

        # Disable button during test
        test_button.setEnabled(False)
        test_button.setText(self.i18n.t("settings.transcription.testing"))
        QApplication.processEvents()

        # Run validation in a separate thread to avoid blocking UI
        try:
            from engines.speech.api_validator import APIKeyValidator

            # Create event loop for async validation
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                if provider == "openai":
                    is_valid, message = loop.run_until_complete(
                        APIKeyValidator.validate_openai_key(api_key)
                    )
                elif provider == "google":
                    is_valid, message = loop.run_until_complete(
                        APIKeyValidator.validate_google_key(api_key)
                    )
                elif provider == "azure":
                    region = self.azure_region_edit.text().strip()
                    if not region:
                        self.show_warning(
                            self.i18n.t("settings.transcription.test_failed"),
                            self.i18n.t("settings.transcription.empty_region"),
                        )
                        return
                    is_valid, message = loop.run_until_complete(
                        APIKeyValidator.validate_azure_key(api_key, region)
                    )
                else:
                    is_valid = False
                    message = self.i18n.t("settings.transcription.unknown_provider")

                # Show result
                if is_valid:
                    self.show_info(
                        self.i18n.t("settings.transcription.test_success"),
                        self.i18n.t("settings.transcription.test_success_message", message=message),
                    )
                    logger.info(f"{provider} API key validation successful")
                else:
                    self.show_warning(
                        self.i18n.t("settings.transcription.test_failed"),
                        self.i18n.t("settings.transcription.test_failed_message", message=message),
                    )
                    logger.warning(f"{provider} API key validation failed: {message}")

            finally:
                loop.close()

        except Exception as e:
            logger.error(f"Error testing {provider} API key: {e}")
            self.show_error(
                self.i18n.t("settings.transcription.test_error"),
                self.i18n.t("settings.transcription.test_error_message", error=str(e)),
            )
        finally:
            # Re-enable button
            test_button.setEnabled(True)
            test_button.setText(self.i18n.t("settings.transcription.test_connection"))

    def _load_usage_statistics(self):
        """Load and display API usage statistics."""
        # Check if usage tracker is available
        if "usage_tracker" not in self.managers:
            logger.debug("No usage_tracker available, skipping usage statistics")
            return

        usage_tracker = self.managers["usage_tracker"]

        try:
            from datetime import datetime

            now = datetime.now()

            # Get monthly usage for each provider
            for provider, label in [
                ("openai", self.openai_usage_label),
                ("google", self.google_usage_label),
                ("azure", self.azure_usage_label),
            ]:
                usage = usage_tracker.get_monthly_usage(
                    engine=provider, year=now.year, month=now.month
                )

                if usage and usage.get("usage_count", 0) > 0:
                    duration_minutes = usage.get("total_duration_minutes", 0)
                    cost = usage.get("total_cost", 0)
                    count = usage.get("usage_count", 0)

                    # Format usage text
                    usage_text = f"{count} calls, {duration_minutes:.1f} min, " f"${cost:.2f}"
                    label.setText(usage_text)
                    label.setProperty("role", "usage-stats")
                else:
                    label.setText(self.i18n.t("settings.transcription.no_usage_data"))
                    label.setProperty("role", "time-display")

            logger.debug("Usage statistics loaded successfully")

        except Exception as e:
            logger.error(f"Error loading usage statistics: {e}")

    def _on_engine_changed(self, engine: str):
        """
        Handle engine selection change.

        Args:
            engine: Selected engine name
        """
        # Show/hide engine-specific configs
        is_whisper = engine == "faster-whisper"
        is_cloud = engine in ["openai", "google", "azure"]

        self.whisper_group.setVisible(is_whisper)
        self.cloud_group.setVisible(is_cloud)

        self._emit_changed()

    def _populate_device_options(self):
        """Populate device combo box with available options."""
        from utils.gpu_detector import GPUDetector

        # Get available device options
        device_options = GPUDetector.get_available_device_options()

        # Clear existing items
        self.device_combo.clear()

        # Add options
        for device_id, display_name in device_options:
            self.device_combo.addItem(display_name, device_id)

        logger.debug(f"Populated device options: {device_options}")

    def _update_device_info(self):
        """Update device information label based on selection."""
        from utils.gpu_detector import GPUDetector

        # Get selected device ID
        device_id = self.device_combo.currentData()

        if device_id == "auto":
            # Show recommended device
            recommended_device, recommended_compute = GPUDetector.get_recommended_device()
            device_name = GPUDetector.get_device_display_name(recommended_device, self.i18n)
            info_text = self.i18n.t(
                "settings.transcription.will_automatically_use",
                device_name=device_name,
                compute_type=recommended_compute,
            )
            self.device_info_label.setText(info_text)
        elif device_id == "cuda":
            self.device_info_label.setText(self.i18n.t("settings.transcription.gpu_acceleration"))
        elif device_id == "cpu":
            # Check if CoreML is available
            devices = GPUDetector.detect_available_devices()
            if devices["coreml"]:
                self.device_info_label.setText(
                    self.i18n.t("settings.transcription.device_info_cpu")
                )
            else:
                self.device_info_label.setText(self.i18n.t("settings.transcription.cpu_mode"))
        else:
            self.device_info_label.setText("")

    def _on_show_ffmpeg_guide(self):
        """Show FFmpeg installation guide dialog."""
        from ui.dialogs.ffmpeg_install_dialog import FFmpegInstallDialog
        from utils.ffmpeg_checker import get_ffmpeg_checker

        ffmpeg_checker = get_ffmpeg_checker()
        title, instructions = ffmpeg_checker.get_installation_instructions(self.i18n)

        dialog = FFmpegInstallDialog(title, instructions, self.i18n, self)
        dialog.exec()

        # Refresh status after dialog closes
        if ffmpeg_checker.is_ffmpeg_available() and ffmpeg_checker.is_ffprobe_available():
            self.ffmpeg_status_text.setText(self.i18n.t("settings.transcription.ffmpeg_installed"))
            self.ffmpeg_status_text.setProperty("role", "ffmpeg-status")
            self.ffmpeg_status_text.setProperty("state", "success")
        else:
            self.ffmpeg_status_text.setText(
                self.i18n.t("settings.transcription.ffmpeg_not_installed")
            )
            self.ffmpeg_status_text.setProperty("role", "ffmpeg-status")
            self.ffmpeg_status_text.setProperty("state", "missing")

        logger.info(self.i18n.t("logging.settings.transcription_page.showed_ffmpeg_guide"))

    def _on_browse_clicked(self):
        """Handle browse button click."""
        current_path = self.path_edit.text()
        if not current_path:
            current_path = str(Path.home() / "Documents" / "EchoNote" / "Transcripts")

        directory = QFileDialog.getExistingDirectory(
            self, self.i18n.t("settings.transcription.select_directory"), current_path
        )

        if directory:
            self.path_edit.setText(directory)

    def load_settings(self):
        """Load transcription settings into UI."""
        try:
            # General settings
            output_format = self.settings_manager.get_setting("transcription.default_output_format")
            if output_format:
                index = self.format_combo.findText(output_format)
                if index >= 0:
                    self.format_combo.setCurrentIndex(index)

            concurrent_tasks = self.settings_manager.get_setting(
                "transcription.max_concurrent_tasks"
            )
            if concurrent_tasks:
                self.concurrent_spin.setValue(concurrent_tasks)

            save_path = self.settings_manager.get_setting("transcription.default_save_path")
            if save_path:
                # Expand user path
                expanded_path = Path(save_path).expanduser()
                self.path_edit.setText(str(expanded_path))

            # Engine settings
            engine = self.settings_manager.get_setting("transcription.default_engine")
            if engine:
                index = self.engine_combo.findText(engine)
                if index >= 0:
                    self.engine_combo.setCurrentIndex(index)

            # Faster-Whisper settings
            whisper_settings = self.settings_manager.get_setting("transcription.faster_whisper")

            # Update model list from ModelManager (if available)
            if self.model_manager:
                self._update_model_list()

            if whisper_settings:
                model_size = whisper_settings.get("model_size", "base")

                # Try to select the configured model
                # (if ModelManager is used, _update_model_list already populated
                # the list with downloaded models only)
                index = self.model_size_combo.findText(model_size)
                if index >= 0:
                    self.model_size_combo.setCurrentIndex(index)

                # Load device setting (use 'auto' as default)
                device = whisper_settings.get("device", "auto")
                # Find by data (device_id) not by text
                for i in range(self.device_combo.count()):
                    if self.device_combo.itemData(i) == device:
                        self.device_combo.setCurrentIndex(i)
                        break

                # Update device info after loading
                self._update_device_info()

                compute_type = whisper_settings.get("compute_type", "int8")
                index = self.compute_type_combo.findText(compute_type)
                if index >= 0:
                    self.compute_type_combo.setCurrentIndex(index)

            # Load API keys (if security manager is available)
            self._load_api_keys()

            # Load usage statistics
            self._load_usage_statistics()

            logger.debug("Transcription settings loaded")

        except Exception as e:
            logger.error(f"Error loading transcription settings: {e}")

    def _load_api_keys(self):
        """Load encrypted API keys."""
        if "secrets_manager" not in self.managers:
            logger.warning(
                self.i18n.t(
                    "logging.settings.transcription_page.no_secrets_manager_skipping_api_key_loading"
                )
            )
            return

        secrets_manager = self.managers["secrets_manager"]

        try:
            # Load API keys from encrypted storage
            openai_key = secrets_manager.get_api_key("openai")
            if openai_key:
                self.openai_key_edit.setText(openai_key)

            google_key = secrets_manager.get_api_key("google")
            if google_key:
                self.google_key_edit.setText(google_key)

            azure_key = secrets_manager.get_api_key("azure")
            if azure_key:
                self.azure_key_edit.setText(azure_key)

            azure_region = secrets_manager.get_secret("azure_region")
            if azure_region:
                self.azure_region_edit.setText(azure_region)

            logger.debug("API keys loaded successfully")

        except Exception as e:
            logger.error(f"Error loading API keys: {e}")

    def save_settings(self):
        """Save transcription settings from UI."""
        try:
            # General settings
            self.settings_manager.set_setting(
                "transcription.default_output_format", self.format_combo.currentText()
            )

            # Update max concurrent tasks
            new_max_concurrent = self.concurrent_spin.value()
            self.settings_manager.set_setting(
                "transcription.max_concurrent_tasks", new_max_concurrent
            )

            # Update transcription manager if available
            if "transcription_manager" in self.managers:
                try:
                    self.managers["transcription_manager"].update_max_concurrent(new_max_concurrent)
                    logger.info(
                        f"Updated transcription manager max_concurrent to " f"{new_max_concurrent}"
                    )
                except Exception as e:
                    logger.error(f"Failed to update transcription manager " f"max_concurrent: {e}")

            self.settings_manager.set_setting(
                "transcription.default_save_path", self.path_edit.text()
            )

            # Engine settings
            selected_engine = self.engine_combo.currentText()
            self.settings_manager.set_setting(
                "transcription.default_engine", selected_engine
            )

            # Faster-Whisper settings
            self.settings_manager.set_setting(
                "transcription.faster_whisper.model_size", self.model_size_combo.currentText()
            )

            # Save device using the data (device_id) not the display text
            device_id = self.device_combo.currentData()
            self.settings_manager.set_setting(
                "transcription.faster_whisper.device", device_id if device_id else "auto"
            )

            self.settings_manager.set_setting(
                "transcription.faster_whisper.compute_type", self.compute_type_combo.currentText()
            )

            if "transcription_manager" in self.managers:
                try:
                    reloaded = self.managers["transcription_manager"].reload_engine()
                    if reloaded:
                        logger.info(f"Reloaded transcription engine after selecting {selected_engine}")
                    else:
                        self.show_warning(
                            self.i18n.t("settings.transcription.engine_reload_warning_title"),
                            self.i18n.t(
                                "settings.transcription.engine_reload_warning_message",
                                engine=selected_engine,
                            ),
                        )
                except Exception as e:
                    logger.error(f"Failed to reload transcription engine: {e}")
                    self.show_warning(
                        self.i18n.t("settings.transcription.engine_reload_warning_title"),
                        self.i18n.t(
                            "settings.transcription.engine_reload_failed_message",
                            engine=selected_engine,
                            error=str(e),
                        ),
                    )

            # Save API keys (encrypted)
            self._save_api_keys()

            logger.debug("Transcription settings saved")

        except Exception as e:
            logger.error(f"Error saving transcription settings: {e}")
            raise

    def _save_api_keys(self):
        """Save API keys with encryption."""
        if "secrets_manager" not in self.managers:
            logger.warning(
                self.i18n.t(
                    "logging.settings.transcription_page.no_secrets_manager_skipping_api_key_saving"
                )
            )
            return

        secrets_manager = self.managers["secrets_manager"]

        try:
            # Save OpenAI API key
            openai_key = self.openai_key_edit.text().strip()
            if openai_key:
                secrets_manager.set_api_key("openai", openai_key)
            else:
                secrets_manager.delete_api_key("openai")

            # Save Google API key
            google_key = self.google_key_edit.text().strip()
            if google_key:
                secrets_manager.set_api_key("google", google_key)
            else:
                secrets_manager.delete_api_key("google")

            # Save Azure API key
            azure_key = self.azure_key_edit.text().strip()
            if azure_key:
                secrets_manager.set_api_key("azure", azure_key)
            else:
                secrets_manager.delete_api_key("azure")

            # Save Azure region
            azure_region = self.azure_region_edit.text().strip()
            if azure_region:
                secrets_manager.set_secret("azure_region", azure_region)
            else:
                secrets_manager.delete_secret("azure_region")

            logger.info(self.i18n.t("logging.settings.transcription_page.api_keys_encrypted_saved"))

            # Emit signal to notify that API keys have been updated
            # This will trigger engine reloading
            self.settings_manager.api_keys_updated.emit()
            logger.info(
                self.i18n.t("logging.settings.transcription_page.api_keys_updated_signal_emitted")
            )

        except Exception as e:
            logger.error(f"Error saving API keys: {e}")
            raise

    def validate_settings(self) -> Tuple[bool, str]:
        """
        Validate transcription settings.

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Validate save path
        save_path = self.path_edit.text()
        if not save_path or not save_path.strip():
            return False, self.i18n.t("settings.transcription.error.empty_path")

        # Check if path is valid (can be created)
        try:
            path = Path(save_path).expanduser()
            if not path.exists():
                # Try to create it
                path.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            return False, self.i18n.t("settings.transcription.error.invalid_path", error=str(e))

        return True, ""

    def update_translations(self):
        """Update UI text after language change."""
        # Update section titles
        if hasattr(self, "general_title"):
            self.general_title.setText(self.i18n.t("settings.transcription.general"))
        if hasattr(self, "ffmpeg_title"):
            self.ffmpeg_title.setText(self.i18n.t("settings.transcription.ffmpeg_status"))
        if hasattr(self, "engine_title"):
            self.engine_title.setText(self.i18n.t("settings.transcription.engine"))

        # Update labels
        if hasattr(self, "format_label"):
            self.format_label.setText(self.i18n.t("settings.transcription.output_format"))
        if hasattr(self, "concurrent_label"):
            self.concurrent_label.setText(self.i18n.t("settings.transcription.concurrent_tasks"))
        if hasattr(self, "ffmpeg_status_label"):
            self.ffmpeg_status_label.setText(self.i18n.t("ffmpeg.ffmpeg_label"))
        if hasattr(self, "path_label"):
            self.path_label.setText(self.i18n.t("settings.transcription.save_path"))
        if hasattr(self, "engine_label"):
            self.engine_label.setText(self.i18n.t("settings.transcription.engine_select"))

        # Update Whisper config labels
        if hasattr(self, "model_size_label"):
            self.model_size_label.setText(self.i18n.t("settings.transcription.model_size"))
        if hasattr(self, "device_label"):
            self.device_label.setText(self.i18n.t("settings.transcription.device"))
        if hasattr(self, "compute_type_label"):
            self.compute_type_label.setText(self.i18n.t("settings.transcription.compute_type"))

        # Update buttons
        if hasattr(self, "browse_button"):
            self.browse_button.setText(self.i18n.t("settings.transcription.browse"))
        if hasattr(self, "ffmpeg_install_btn"):
            self.ffmpeg_install_btn.setText(self.i18n.t("settings.transcription.ffmpeg_view_guide"))

        # Update FFmpeg info
        if hasattr(self, "ffmpeg_info"):
            self.ffmpeg_info.setText(self.i18n.t("settings.transcription.ffmpeg_info"))

        # Update FFmpeg status text
        if hasattr(self, "ffmpeg_status_text"):
            from utils.ffmpeg_checker import get_ffmpeg_checker

            ffmpeg_checker = get_ffmpeg_checker()
            if ffmpeg_checker.is_ffmpeg_available() and ffmpeg_checker.is_ffprobe_available():
                self.ffmpeg_status_text.setText(
                    self.i18n.t("settings.transcription.ffmpeg_installed")
                )
            else:
                self.ffmpeg_status_text.setText(
                    self.i18n.t("settings.transcription.ffmpeg_not_installed")
                )

        # Update group boxes
        if hasattr(self, "whisper_group"):
            self.whisper_group.setTitle(self.i18n.t("settings.transcription.whisper_config"))
        if hasattr(self, "cloud_group"):
            self.cloud_group.setTitle(self.i18n.t("settings.transcription.cloud_config"))

        # Update cloud API group boxes
        if hasattr(self, "openai_group"):
            self.openai_group.setTitle(self.i18n.t("settings.transcription.cloud_api_openai"))
        if hasattr(self, "google_group"):
            self.google_group.setTitle(self.i18n.t("settings.transcription.cloud_api_google"))
        if hasattr(self, "azure_group"):
            self.azure_group.setTitle(self.i18n.t("settings.transcription.cloud_api_azure"))

        # Update API key labels
        if hasattr(self, "openai_api_key_label"):
            self.openai_api_key_label.setText(self.i18n.t("settings.transcription.api_key_label"))
        if hasattr(self, "google_api_key_label"):
            self.google_api_key_label.setText(self.i18n.t("settings.transcription.api_key_label"))
        if hasattr(self, "azure_api_key_label"):
            self.azure_api_key_label.setText(self.i18n.t("settings.transcription.api_key_label"))
        if hasattr(self, "azure_region_label"):
            self.azure_region_label.setText(
                self.i18n.t("settings.transcription.azure_region_label")
            )

        # Update monthly usage labels
        if hasattr(self, "openai_monthly_usage_label"):
            self.openai_monthly_usage_label.setText(
                self.i18n.t("settings.transcription.monthly_usage")
            )
        if hasattr(self, "google_monthly_usage_label"):
            self.google_monthly_usage_label.setText(
                self.i18n.t("settings.transcription.monthly_usage")
            )
        if hasattr(self, "azure_monthly_usage_label"):
            self.azure_monthly_usage_label.setText(
                self.i18n.t("settings.transcription.monthly_usage")
            )

        # Update test buttons
        if hasattr(self, "openai_test_button"):
            self.openai_test_button.setText(self.i18n.t("settings.transcription.test_connection"))
        if hasattr(self, "google_test_button"):
            self.google_test_button.setText(self.i18n.t("settings.transcription.test_connection"))
        if hasattr(self, "azure_test_button"):
            self.azure_test_button.setText(self.i18n.t("settings.transcription.test_connection"))

        # Update usage labels (only if showing "no usage data")
        if hasattr(self, "openai_usage_label"):
            current_text = self.openai_usage_label.text()
            # Check if it's the "no usage data" message in any language
            if "usage" not in current_text.lower() or "minutes" not in current_text.lower():
                self.openai_usage_label.setText(self.i18n.t("settings.transcription.no_usage_data"))
        if hasattr(self, "google_usage_label"):
            current_text = self.google_usage_label.text()
            if "usage" not in current_text.lower() or "minutes" not in current_text.lower():
                self.google_usage_label.setText(self.i18n.t("settings.transcription.no_usage_data"))
        if hasattr(self, "azure_usage_label"):
            current_text = self.azure_usage_label.text()
            if "usage" not in current_text.lower() or "minutes" not in current_text.lower():
                self.azure_usage_label.setText(self.i18n.t("settings.transcription.no_usage_data"))

        # Update note label
        if hasattr(self, "note_label"):
            self.note_label.setText(self.i18n.t("settings.transcription.api_key_note"))

        # Update placeholder texts
        if hasattr(self, "openai_key_edit"):
            self.openai_key_edit.setPlaceholderText(
                self.i18n.t("settings.transcription.api_key_placeholder")
            )
        if hasattr(self, "azure_region_edit"):
            self.azure_region_edit.setPlaceholderText(
                self.i18n.t("settings.transcription.azure_region_placeholder")
            )

        # Update refresh button
        if hasattr(self, "refresh_usage_button"):
            self.refresh_usage_button.setText(self.i18n.t("settings.transcription.refresh_usage"))
