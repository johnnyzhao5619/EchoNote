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
Real-time recording widget.

This module implements the main UI for real-time recording, including audio input selection,
gain adjustment, language selection, and transcription/translation display.
"""

import asyncio
import logging
import threading
from concurrent.futures import Future, TimeoutError
from typing import Any, Dict, Optional

from PySide6.QtCore import QObject, Qt, QThread, QTimer, Signal, Slot
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPlainTextEdit,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from ui.base_widgets import (
    BaseWidget,
    connect_button_with_callback,
    create_button,
    create_hbox,
    create_secondary_button,
)
from ui.common.notification import get_notification_manager
from utils.i18n import LANGUAGE_OPTION_KEYS

logger = logging.getLogger(__name__)


class AsyncWorker(QThread):
    """Worker thread for running asyncio loops."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.loop = None
        self._loop_ready = threading.Event()

    def run(self):
        """Run the event loop."""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self._loop_ready.set()
        self.loop.run_forever()
        self._loop_ready.clear()

    def wait_until_ready(self, timeout: float = 2.0) -> bool:
        """Block until the worker loop is initialized."""
        return self._loop_ready.wait(timeout)

    def stop(self):
        """Stop the event loop and wait for the thread to exit."""
        if self.loop and self.loop.is_running():
            self.loop.call_soon_threadsafe(self.loop.stop)
        self.wait()

    def submit(self, coro):
        """Submit a coroutine to run on the loop."""
        if self.loop:
            return asyncio.run_coroutine_threadsafe(coro, self.loop)
        return None


class RealtimeRecorderSignals(QObject):
    """Qt Signal wrapper for RealtimeRecorder callbacks."""

    transcription_updated = Signal(str)
    translation_updated = Signal(str)
    error_occurred = Signal(str)
    status_changed = Signal(bool, float)
    audio_data_available = Signal(object)  # np.ndarray
    recording_started = Signal()
    recording_stopped = Signal()
    recording_succeeded = Signal(dict)
    marker_added = Signal(object)


class RealtimeRecordWidget(BaseWidget):
    """Main widget for real-time recording."""

    LANGUAGE_OPTIONS = LANGUAGE_OPTION_KEYS

    def __init__(
        self,
        recorder,
        audio_capture,
        i18n_manager,
        settings_manager: Optional[object] = None,
        model_manager=None,
        parent=None,
    ):
        super().__init__(i18n_manager, parent)
        self.recorder = recorder
        self.audio_capture = audio_capture
        self._audio_available = audio_capture is not None
        self.settings_manager = settings_manager
        self.model_manager = model_manager

        # Signals
        self.signals = RealtimeRecorderSignals()
        self._markers = []

        # Async Worker
        self._worker = AsyncWorker(self)
        self._worker.start()
        self._worker.wait_until_ready()
        self._async_thread = self._worker  # Backward-compatible alias for tests/utilities
        self._async_loop = self._worker.loop
        self._pending_futures = set()
        self._future_lock = threading.Lock()
        self._cleanup_in_progress = False
        self._cleanup_done = False

        # Buffers
        self._transcription_buffer = []
        self._translation_buffer = []
        self._buffer_lock = threading.Lock()

        # Preferences
        self._recording_format = "wav"
        self._auto_save_enabled = True
        self._default_input_source = "default"
        self._default_gain = 1.0
        self._vad_threshold = 0.5
        self._silence_duration_ms = 2000
        self._min_audio_duration = 3.0
        self._save_transcript_enabled = True
        self._create_calendar_event_enabled = True
        self._refresh_recording_preferences()

        # Notification Manager
        try:
            self._notification_manager = get_notification_manager()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Notification manager unavailable: %s", exc, exc_info=True)
            self._notification_manager = None

        # Connect model manager signals if available
        if self.model_manager:
            self.model_manager.models_updated.connect(self._update_model_list)

        if self.settings_manager and hasattr(self.settings_manager, "setting_changed"):
            try:
                self.settings_manager.setting_changed.connect(self._on_settings_changed)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to connect to settings_manager.setting_changed: %s", exc)

        # Set callbacks
        self.recorder.set_callbacks(
            on_transcription=self._on_transcription,
            on_translation=self._on_translation,
            on_error=self._on_error,
            on_audio_data=self._on_audio_data,
            on_marker=self._on_marker,
        )

        # Connect signals
        self.signals.transcription_updated.connect(
            self._update_transcription_display, Qt.ConnectionType.QueuedConnection
        )
        self.signals.translation_updated.connect(
            self._update_translation_display, Qt.ConnectionType.QueuedConnection
        )
        self.signals.error_occurred.connect(self._show_error, Qt.ConnectionType.QueuedConnection)
        self.signals.status_changed.connect(
            self._update_status_display, Qt.ConnectionType.QueuedConnection
        )
        self.signals.recording_started.connect(
            self._on_recording_started, Qt.ConnectionType.QueuedConnection
        )
        self.signals.recording_stopped.connect(
            self._on_recording_stopped, Qt.ConnectionType.QueuedConnection
        )
        self.signals.recording_succeeded.connect(
            self._on_recording_succeeded, Qt.ConnectionType.QueuedConnection
        )
        self.signals.marker_added.connect(
            self._append_marker_item, Qt.ConnectionType.QueuedConnection
        )

        # Status Update Timer
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self._update_status)

        # Initialize UI
        self.setup_ui()
        self._apply_recording_preferences_to_controls()

        # Connect language change signal
        self.i18n.language_changed.connect(self._update_ui_text)

        logger.info(self.i18n.t("logging.realtime_record.widget_initialized"))

    def _refresh_recording_preferences(self) -> None:
        """Load recording preferences from settings."""
        if self.settings_manager and hasattr(self.settings_manager, "get_realtime_preferences"):
            try:
                preferences = self.settings_manager.get_realtime_preferences()
                self._recording_format = preferences.get("recording_format", "wav")
                self._auto_save_enabled = bool(preferences.get("auto_save", True))
                self._default_input_source = str(
                    preferences.get("default_input_source", "default")
                ).lower()
                if self._default_input_source != "default":
                    self._default_input_source = "default"

                gain = preferences.get("default_gain", 1.0)
                try:
                    self._default_gain = float(gain)
                except (TypeError, ValueError):
                    self._default_gain = 1.0
                self._default_gain = max(0.1, min(2.0, self._default_gain))

                vad_threshold = preferences.get("vad_threshold", 0.5)
                try:
                    self._vad_threshold = float(vad_threshold)
                except (TypeError, ValueError):
                    self._vad_threshold = 0.5
                self._vad_threshold = max(0.0, min(1.0, self._vad_threshold))

                silence_duration_ms = preferences.get("silence_duration_ms", 2000)
                try:
                    self._silence_duration_ms = int(silence_duration_ms)
                except (TypeError, ValueError):
                    self._silence_duration_ms = 2000
                self._silence_duration_ms = max(0, self._silence_duration_ms)

                min_audio_duration = preferences.get("min_audio_duration", 3.0)
                try:
                    self._min_audio_duration = float(min_audio_duration)
                except (TypeError, ValueError):
                    self._min_audio_duration = 3.0
                self._min_audio_duration = max(0.1, self._min_audio_duration)

                self._save_transcript_enabled = bool(preferences.get("save_transcript", True))
                self._create_calendar_event_enabled = bool(
                    preferences.get("create_calendar_event", True)
                )
                return
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to refresh realtime preferences: %s", exc, exc_info=True)

        # Fallback defaults
        self._recording_format = "wav"
        self._auto_save_enabled = True
        self._default_input_source = "default"
        self._default_gain = 1.0
        self._vad_threshold = 0.5
        self._silence_duration_ms = 2000
        self._min_audio_duration = 3.0
        self._save_transcript_enabled = True
        self._create_calendar_event_enabled = True

    @Slot(str, object)
    def _on_settings_changed(self, key: str, _value: object) -> None:
        """Handle settings changes."""
        if key.startswith("realtime."):
            self._refresh_recording_preferences()
            self._apply_recording_preferences_to_controls()

    def _apply_recording_preferences_to_controls(self) -> None:
        """Apply preferences to UI controls."""
        gain_slider = getattr(self, "gain_slider", None)
        if gain_slider is not None:
            slider_value = int(round(self._default_gain * 100))
            slider_value = max(gain_slider.minimum(), min(gain_slider.maximum(), slider_value))
            gain_slider.setValue(slider_value)

        if self.audio_capture is not None and hasattr(self.audio_capture, "set_gain"):
            try:
                self.audio_capture.set_gain(self._default_gain)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to apply default gain: %s", exc)

        if self._default_input_source == "default" and hasattr(self, "input_combo"):
            default_device = None
            if self.audio_capture is not None and hasattr(
                self.audio_capture, "get_default_input_device"
            ):
                try:
                    default_device = self.audio_capture.get_default_input_device()
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Failed to get default input device: %s", exc)

            if isinstance(default_device, dict):
                default_index = default_device.get("index")
                if default_index is not None:
                    combo_index = self.input_combo.findData(default_index)
                    if combo_index >= 0:
                        self.input_combo.setCurrentIndex(combo_index)

    def setup_ui(self):
        """Initialize the UI layout."""
        from PySide6.QtWidgets import QTabWidget

        main_layout = QVBoxLayout(self)

        # Header
        header = self._create_header_section()
        main_layout.addWidget(header)

        # Tabs
        self.tab_widget = QTabWidget()
        self.tab_widget.setObjectName("main_tabs")

        # Recording Tab
        recording_tab = self._create_recording_tab()
        self.tab_widget.addTab(
            recording_tab, "🎙 " + self.i18n.t("realtime_record.recording_control")
        )

        # Transcription Tab
        transcription_tab = self._create_transcription_tab()
        self.tab_widget.addTab(
            transcription_tab, "📝 " + self.i18n.t("realtime_record.transcription")
        )

        # Translation Tab
        translation_tab = self._create_translation_tab()
        self.tab_widget.addTab(translation_tab, "🌐 " + self.i18n.t("realtime_record.translation"))

        # Markers Tab
        markers_tab = self._create_markers_tab()
        self.tab_widget.addTab(markers_tab, "📌 " + self.i18n.t("realtime_record.markers"))

        main_layout.addWidget(self.tab_widget, stretch=1)

        # Update model list
        if self.model_manager:
            self._update_model_list()

        # Update UI text and audio availability
        self._update_ui_text()
        self._update_audio_availability()

    def _create_recording_tab(self) -> QWidget:
        """Create recording control tab."""
        tab = QWidget()
        tab.setObjectName("recording_tab")
        layout = QVBoxLayout(tab)

        # Settings
        settings = self._create_settings_section()
        layout.addWidget(settings)

        # Visualizer
        visualizer = self._create_visualizer_section()
        layout.addWidget(visualizer)

        # Status
        status_section = self._create_status_section()
        layout.addWidget(status_section)

        layout.addStretch()
        return tab

    def _create_transcription_tab(self) -> QWidget:
        """Create transcription results tab."""
        tab = QWidget()
        tab.setObjectName("transcription_tab")
        layout = QVBoxLayout(tab)

        # Toolbar
        toolbar = self._create_text_toolbar("transcription")
        layout.addWidget(toolbar)

        # Text Area
        self.transcription_text = QPlainTextEdit()
        self.transcription_text.setObjectName("transcription_text")
        self.transcription_text.setReadOnly(True)
        self.transcription_text.setUndoRedoEnabled(False)
        layout.addWidget(self.transcription_text)

        return tab

    def _create_translation_tab(self) -> QWidget:
        """Create translation results tab."""
        tab = QWidget()
        tab.setObjectName("translation_tab")
        layout = QVBoxLayout(tab)

        # Toolbar
        toolbar = self._create_text_toolbar("translation")
        layout.addWidget(toolbar)

        # Text Area
        self.translation_text = QPlainTextEdit()
        self.translation_text.setObjectName("translation_text")
        self.translation_text.setReadOnly(True)
        self.translation_text.setUndoRedoEnabled(False)

        if not self.recorder.translation_engine:
            self.translation_text.setPlaceholderText(
                self.i18n.t("realtime_record.translation_not_available")
            )

        layout.addWidget(self.translation_text)
        return tab

    def _create_markers_tab(self) -> QWidget:
        """Create time markers tab."""
        tab = QWidget()
        tab.setObjectName("markers_tab")
        layout = QVBoxLayout(tab)

        # Toolbar
        toolbar = QWidget()
        toolbar.setObjectName("markers_toolbar")
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.addStretch()

        # Clear Button
        clear_btn = create_button(self.i18n.t("realtime_record.clear_markers"))
        clear_btn = create_secondary_button(clear_btn.text())
        clear_btn.setObjectName("clear_markers_button")
        self.clear_markers_button = clear_btn
        connect_button_with_callback(clear_btn, self._reset_markers_ui)
        toolbar_layout.addWidget(clear_btn)
        layout.addWidget(toolbar)

        # Markers List
        self.markers_list = QListWidget()
        self.markers_list.setObjectName("markers_list")
        self.markers_list.setAlternatingRowColors(True)
        self.markers_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.markers_list.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        layout.addWidget(self.markers_list)

        return tab

    def _create_text_toolbar(self, text_type: str) -> QWidget:
        """Create text toolbar."""
        toolbar = QWidget()
        toolbar.setObjectName("text_toolbar")
        layout = QHBoxLayout(toolbar)

        # Word Count
        word_count_label = QLabel("0 " + self.i18n.t("common.words"))
        word_count_label.setObjectName("word_count_label")
        layout.addWidget(word_count_label)

        if text_type == "transcription":
            self.transcription_word_count = word_count_label
        else:
            self.translation_word_count = word_count_label

        layout.addStretch()

        # Copy Button
        copy_btn = create_button("📋 " + self.i18n.t("common.copy"))
        copy_btn = create_secondary_button(copy_btn.text())
        copy_btn.clicked.connect(lambda: self._copy_text(text_type))
        layout.addWidget(copy_btn)

        # Export Button
        export_btn = create_button("📥 " + self.i18n.t("realtime_record.export_" + text_type))
        export_btn = create_secondary_button(export_btn.text())
        if text_type == "transcription":
            connect_button_with_callback(export_btn, self._export_transcription)
            self.export_transcription_button = export_btn
        else:
            connect_button_with_callback(export_btn, self._export_translation)
            self.export_translation_button = export_btn
        layout.addWidget(export_btn)

        return toolbar

    def _create_status_section(self) -> QWidget:
        """Create status feedback section."""
        section = QWidget()
        section.setObjectName("status_section")
        layout = QVBoxLayout(section)

        # Feedback Label
        self.feedback_label = QLabel()
        self.feedback_label.setObjectName("feedback_label")
        self.feedback_label.setWordWrap(True)
        self.feedback_label.setVisible(False)
        layout.addWidget(self.feedback_label)

        # Status Bar
        status_bar = QWidget()
        status_bar.setObjectName("status_bar")
        status_layout = QHBoxLayout(status_bar)

        self.status_indicator = QLabel("●")
        self.status_indicator.setObjectName("status_indicator")
        status_layout.addWidget(self.status_indicator)

        self.status_text_label = QLabel(self.i18n.t("realtime_record.status_ready"))
        self.status_text_label.setObjectName("status_text")
        status_layout.addWidget(self.status_text_label)

        status_layout.addStretch()
        layout.addWidget(status_bar)

        return section

    def _copy_text(self, text_type: str):
        """Copy text to clipboard."""
        from PySide6.QtWidgets import QApplication

        if text_type == "transcription":
            text = self.transcription_text.toPlainText()
        else:
            text = self.translation_text.toPlainText()

        if text:
            clipboard = QApplication.clipboard()
            clipboard.setText(text)
            if hasattr(self, "feedback_label"):
                self.feedback_label.setText(self.i18n.t("common.copied"))
                self.feedback_label.setProperty("state", "success")
                self.feedback_label.setVisible(True)
                self.feedback_label.style().unpolish(self.feedback_label)
                self.feedback_label.style().polish(self.feedback_label)
                QTimer.singleShot(3000, lambda: self.feedback_label.setVisible(False))

    def _create_header_section(self) -> QWidget:
        """Create header section with title and controls."""
        container = QWidget()
        container.setObjectName("header_section")
        layout = QHBoxLayout(container)

        self.title_label = QLabel(self.i18n.t("realtime_record.title"))
        self.title_label.setObjectName("page_title")
        layout.addWidget(self.title_label)
        layout.addStretch()

        self.duration_value_label = QLabel("00:00:00")
        self.duration_value_label.setObjectName("duration_display")
        layout.addWidget(self.duration_value_label)

        self.add_marker_button = create_secondary_button(self.i18n.t("realtime_record.add_marker"))
        self.add_marker_button.setMinimumHeight(36)
        self.add_marker_button.setMinimumWidth(100)
        self.add_marker_button.setEnabled(False)
        self.add_marker_button.clicked.connect(self._add_marker)
        layout.addWidget(self.add_marker_button)

        self.record_button = QPushButton()
        self.record_button.setObjectName("record_button")
        self.record_button.setMinimumHeight(36)
        self.record_button.setMinimumWidth(120)
        connect_button_with_callback(self.record_button, self._toggle_recording)
        layout.addWidget(self.record_button)

        return container

    def _create_settings_section(self) -> QWidget:
        """Create settings control section."""
        from PySide6.QtWidgets import QFormLayout, QFrame

        container = QFrame()
        container.setObjectName("settings_frame")
        form = QFormLayout(container)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        # Row 1: Device and Gain
        row1 = create_hbox(spacing=24)
        device_container = QWidget()
        device_layout = QHBoxLayout(device_container)
        device_label = QLabel(self.i18n.t("realtime_record.audio_input") + ":")
        device_label.setObjectName("form_label")
        device_label.setMinimumWidth(100)
        device_layout.addWidget(device_label)
        self.input_combo = QComboBox()
        self.input_combo.setObjectName("form_combo")
        self.input_combo.setMinimumWidth(200)
        self._populate_input_devices()
        device_layout.addWidget(self.input_combo)
        row1.addWidget(device_container)

        gain_container = QWidget()
        gain_layout = QHBoxLayout(gain_container)
        gain_label = QLabel(self.i18n.t("realtime_record.gain") + ":")
        gain_label.setObjectName("form_label")
        gain_label.setMinimumWidth(80)
        gain_layout.addWidget(gain_label)
        self.gain_slider = QSlider(Qt.Orientation.Horizontal)
        self.gain_slider.setObjectName("form_slider")
        self.gain_slider.setMinimum(10)
        self.gain_slider.setMaximum(200)
        self.gain_slider.setValue(100)
        self.gain_slider.setMinimumWidth(150)
        self.gain_slider.setMaximumWidth(200)
        self.gain_slider.valueChanged.connect(self._on_gain_changed)
        gain_layout.addWidget(self.gain_slider)
        self.gain_value_label = QLabel("1.0x")
        self.gain_value_label.setObjectName("form_value")
        self.gain_value_label.setMinimumWidth(40)
        gain_layout.addWidget(self.gain_value_label)
        row1.addWidget(gain_container)
        row1.addStretch()
        form.addRow(row1)

        # Row 2: Model and Language
        row2 = create_hbox(spacing=24)
        if self.model_manager:
            model_container = QWidget()
            model_layout = QHBoxLayout(model_container)
            model_label = QLabel(self.i18n.t("realtime_record.model") + ":")
            model_label.setObjectName("form_label")
            model_label.setMinimumWidth(100)
            model_layout.addWidget(model_label)
            self.model_combo = QComboBox()
            self.model_combo.setObjectName("form_combo")
            self.model_combo.setMinimumWidth(200)
            model_layout.addWidget(self.model_combo)
            row2.addWidget(model_container)

        source_container = QWidget()
        source_layout = QHBoxLayout(source_container)
        source_label = QLabel(self.i18n.t("realtime_record.source_language") + ":")
        source_label.setObjectName("form_label")
        source_label.setMinimumWidth(80)
        source_layout.addWidget(source_label)
        self.source_lang_combo = QComboBox()
        self.source_lang_combo.setObjectName("form_combo")
        self.source_lang_combo.setMinimumWidth(150)
        for code, label_key in self.LANGUAGE_OPTIONS:
            self.source_lang_combo.addItem(self.i18n.t(label_key), code)
        source_layout.addWidget(self.source_lang_combo)
        row2.addWidget(source_container)
        row2.addStretch()
        form.addRow(row2)

        # Row 3: Translation
        row3 = create_hbox(spacing=24)
        self.enable_translation_checkbox = QCheckBox(
            self.i18n.t("realtime_record.enable_translation")
        )
        self.enable_translation_checkbox.setObjectName("enable_translation_checkbox")
        self.enable_translation_checkbox.stateChanged.connect(self._on_translation_toggled)

        if not self.recorder.translation_engine:
            tooltip = self.i18n.t("realtime_record.translation_disabled_tooltip")
            self.enable_translation_checkbox.setEnabled(False)
            self.enable_translation_checkbox.setToolTip(tooltip)

        row3.addWidget(self.enable_translation_checkbox)
        row3.addSpacing(16)

        target_container = QWidget()
        target_layout = QHBoxLayout(target_container)
        target_label = QLabel(self.i18n.t("realtime_record.target_language") + ":")
        target_label.setObjectName("form_label")
        target_label.setMinimumWidth(80)
        target_layout.addWidget(target_label)
        self.target_lang_combo = QComboBox()
        self.target_lang_combo.setObjectName("form_combo")
        self.target_lang_combo.setMinimumWidth(150)
        self.target_lang_combo.setEnabled(False)
        for code, label_key in self.LANGUAGE_OPTIONS:
            self.target_lang_combo.addItem(self.i18n.t(label_key), code)
        target_layout.addWidget(self.target_lang_combo)

        if not self.recorder.translation_engine:
            tooltip = self.i18n.t("realtime_record.translation_disabled_tooltip")
            self.target_lang_combo.setToolTip(tooltip)

        row3.addWidget(target_container)
        row3.addStretch()
        form.addRow(row3)

        return container

    def _create_visualizer_section(self) -> QWidget:
        """Create audio visualizer section."""
        from ui.realtime_record.audio_visualizer import AudioVisualizer

        container = QWidget()
        container.setObjectName("visualizer_section")
        layout = QVBoxLayout(container)

        self.audio_visualizer = AudioVisualizer(parent=self, i18n=self.i18n)
        self.audio_visualizer.setMinimumHeight(60)
        self.audio_visualizer.setMaximumHeight(80)
        self.signals.audio_data_available.connect(
            self.audio_visualizer.update_audio_data, Qt.ConnectionType.QueuedConnection
        )
        layout.addWidget(self.audio_visualizer)

        self.audio_unavailable_label = QLabel()
        self.audio_unavailable_label.setObjectName("warning_label")
        self.audio_unavailable_label.setWordWrap(True)
        self.audio_unavailable_label.setVisible(False)
        layout.addWidget(self.audio_unavailable_label)

        return container

    def _populate_input_devices(self):
        """Populate audio input devices combo box."""
        if self.audio_capture is None:
            self.input_combo.clear()
            self.input_combo.addItem(self.i18n.t("realtime_record.audio_unavailable_short"), None)
            return

        try:
            devices = self.audio_capture.get_input_devices()
            self.input_combo.clear()

            if not devices:
                self.input_combo.addItem(self.i18n.t("realtime_record.no_input_devices"), None)
                return

            for device in devices:
                self.input_combo.addItem(device["name"], device["index"])

            logger.info(f"Populated {len(devices)} input devices")
        except Exception as e:
            logger.error(f"Failed to populate input devices: {e}")
            self.input_combo.addItem(
                self.i18n.t("ui_strings.realtime_record.error_loading_devices"), None
            )

    def _update_audio_availability(self):
        """Update UI based on audio availability."""
        if hasattr(self.recorder, "audio_capture"):
            self.audio_capture = self.recorder.audio_capture

        previous_state = getattr(self, "_audio_available", False)
        available = False
        if hasattr(self.recorder, "audio_input_available"):
            try:
                available = bool(self.recorder.audio_input_available())
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to check audio availability: %s", exc)
        elif self.audio_capture is not None:
            available = True

        self._audio_available = available
        tooltip = self.i18n.t("realtime_record.audio_unavailable_tooltip")
        guide_text = self.i18n.t(
            "realtime_record.audio_unavailable_message", command="pip install pyaudio"
        )
        short_text = self.i18n.t("realtime_record.audio_unavailable_short")

        if getattr(self, "record_button", None):
            self.record_button.setEnabled(self._audio_available)
            self.record_button.setToolTip("" if self._audio_available else tooltip)

        if getattr(self, "add_marker_button", None):
            self.add_marker_button.setEnabled(self._audio_available and self.recorder.is_recording)
            self.add_marker_button.setToolTip("" if self._audio_available else tooltip)

        for widget_name in ("input_combo", "gain_slider", "gain_value_label", "audio_visualizer"):
            widget = getattr(self, widget_name, None)
            if widget:
                widget.setEnabled(self._audio_available)

        if hasattr(self, "audio_unavailable_label"):
            if self._audio_available:
                self.audio_unavailable_label.setVisible(False)
                self.audio_unavailable_label.clear()
            else:
                self.audio_unavailable_label.setText(guide_text)
                self.audio_unavailable_label.setVisible(True)

        if not self._audio_available and hasattr(self, "input_combo"):
            self.input_combo.clear()
            self.input_combo.addItem(short_text, None)
        elif self._audio_available and not previous_state:
            self._populate_input_devices()

    def _update_model_list(self):
        """Update model combo box."""
        if not self.model_manager or not hasattr(self, "model_combo"):
            return

        try:
            current_model = self.model_combo.currentText()
            self.model_combo.clear()
            downloaded_models = self.model_manager.get_downloaded_models()

            if not downloaded_models:
                self.model_combo.addItem(self.i18n.t("realtime_record.no_models_available"), None)
                self.model_combo.setEnabled(False)
                self._show_download_guide()
                logger.warning(self.i18n.t("logging.realtime_record.no_models_downloaded"))
            else:
                self.model_combo.setEnabled(True)
                if hasattr(self, "_download_guide_widget"):
                    self._download_guide_widget.hide()

                for model in downloaded_models:
                    self.model_combo.addItem(model.name, model.name)

                if current_model:
                    index = self.model_combo.findText(current_model)
                    if index >= 0:
                        self.model_combo.setCurrentIndex(index)
                else:
                    if self.settings_manager:
                        configured_model = self.settings_manager.get_setting(
                            "transcription.faster_whisper.model_size"
                        )
                        if configured_model:
                            index = self.model_combo.findText(configured_model)
                            if index >= 0:
                                self.model_combo.setCurrentIndex(index)

                logger.info(f"Updated model list: {len(downloaded_models)} models")
        except Exception as e:
            logger.error(f"Failed to update model list: {e}")

    def _show_download_guide(self):
        """Show download guide when no models are available."""
        if hasattr(self, "_download_guide_widget"):
            self._download_guide_widget.show()
            return

        from PySide6.QtWidgets import QFrame, QLabel

        guide_widget = QFrame()
        guide_widget.setObjectName("download_guide")
        guide_widget.setFrameStyle(QFrame.Shape.StyledPanel)
        guide_layout = QHBoxLayout(guide_widget)

        warning_label = QLabel("⚠️")
        warning_label.setProperty("role", "warning-large")
        guide_layout.addWidget(warning_label)

        message_label = QLabel(self.i18n.t("realtime_record.no_models_message"))
        message_label.setWordWrap(True)
        guide_layout.addWidget(message_label, 1)

        download_button = create_button(self.i18n.t("realtime_record.go_to_download"))
        connect_button_with_callback(download_button, self._navigate_to_model_management)
        guide_layout.addWidget(download_button)

        settings_frame = self.findChild(QWidget, "settings_frame")
        if settings_frame and settings_frame.parentWidget():
            parent_layout = settings_frame.parentWidget().layout()
            if parent_layout:
                insert_at = -1
                for i in range(parent_layout.count()):
                    if parent_layout.itemAt(i).widget() == settings_frame:
                        insert_at = i + 1
                        break
                if insert_at >= 0:
                    parent_layout.insertWidget(insert_at, guide_widget)

        self._download_guide_widget = guide_widget
        logger.info(self.i18n.t("logging.realtime_record.download_guide_displayed"))

    def _navigate_to_model_management(self):
        """Navigate to model management page."""
        try:
            main_window = self.window()
            if hasattr(main_window, "switch_page"):
                main_window.switch_page("settings")
                settings_widget = getattr(main_window, "pages", {}).get("settings")
                if settings_widget and hasattr(settings_widget, "show_page"):
                    settings_widget.show_page("model_management")
        except Exception as e:
            logger.error(f"Failed to navigate to model management: {e}")

    def _update_ui_text(self):
        """Update UI text on language change."""
        if hasattr(self, "title_label"):
            self.title_label.setText(self.i18n.t("realtime_record.title"))

        self._update_button_texts()
        self._update_form_labels()
        self._update_language_combos()
        self._update_panel_titles()
        self._update_tab_titles()
        self._update_status_texts()
        self._update_placeholders()
        self._update_audio_availability()

    def _update_button_texts(self):
        if hasattr(self, "record_button"):
            if self.recorder.is_recording:
                self.record_button.setText(self.i18n.t("realtime_record.stop_recording"))
            else:
                self.record_button.setText(self.i18n.t("realtime_record.start_recording"))

        if hasattr(self, "add_marker_button"):
            self.add_marker_button.setText(self.i18n.t("realtime_record.add_marker"))

    def _update_form_labels(self):
        label_map = {
            "form_label": {
                "audio": "realtime_record.audio_input",
                "gain": "realtime_record.gain",
                "model": "realtime_record.model",
                "source": "realtime_record.source_language",
                "target": "realtime_record.target_language",
            }
        }
        for object_name, keywords in label_map.items():
            labels = self.findChildren(QLabel, object_name)
            for label in labels:
                text = label.text().lower().replace(":", "")
                for keyword, i18n_key in keywords.items():
                    if keyword in text:
                        label.setText(self.i18n.t(i18n_key) + ":")
                        break
        if hasattr(self, "enable_translation_checkbox"):
            self.enable_translation_checkbox.setText(
                self.i18n.t("realtime_record.enable_translation")
            )
            if not self.recorder.translation_engine:
                self.enable_translation_checkbox.setToolTip(
                    self.i18n.t("realtime_record.translation_disabled_tooltip")
                )

    def _update_language_combos(self):
        for combo_attr in ["source_lang_combo", "target_lang_combo"]:
            if hasattr(self, combo_attr):
                combo = getattr(self, combo_attr)
                for index, (_, label_key) in enumerate(self.LANGUAGE_OPTIONS):
                    if index < combo.count():
                        combo.setItemText(index, self.i18n.t(label_key))

    def _update_panel_titles(self):
        panel_titles = self.findChildren(QLabel, "panel_title")
        title_map = {
            "transcription": "realtime_record.transcription_text",
            "translation": "realtime_record.translation_text",
            "marker": "realtime_record.markers",
        }
        for label in panel_titles:
            text = label.text().lower()
            for keyword, i18n_key in title_map.items():
                if keyword in text:
                    label.setText(self.i18n.t(i18n_key))
                    break
        if hasattr(self, "export_transcription_button"):
            self.export_transcription_button.setToolTip(
                self.i18n.t("realtime_record.export_transcription")
            )
        if hasattr(self, "export_translation_button"):
            self.export_translation_button.setToolTip(
                self.i18n.t("realtime_record.export_translation")
            )

    def _update_tab_titles(self):
        if hasattr(self, "tab_widget"):
            self.tab_widget.setTabText(0, "🎙 " + self.i18n.t("realtime_record.recording_control"))
            self.tab_widget.setTabText(1, "📝 " + self.i18n.t("realtime_record.transcription"))
            self.tab_widget.setTabText(2, "🌐 " + self.i18n.t("realtime_record.translation"))
            self.tab_widget.setTabText(3, "📌 " + self.i18n.t("realtime_record.markers"))

    def _update_status_texts(self):
        if hasattr(self, "status_text_label"):
            if self.recorder.is_recording:
                self.status_text_label.setText(self.i18n.t("realtime_record.status_recording"))
            else:
                self.status_text_label.setText(self.i18n.t("realtime_record.status_ready"))

    def _update_placeholders(self):
        if hasattr(self, "translation_text") and not self.recorder.translation_engine:
            self.translation_text.setPlaceholderText(
                self.i18n.t("realtime_record.translation_not_available")
            )
        if hasattr(self, "markers_list") and hasattr(self.markers_list, "setPlaceholderText"):
            self.markers_list.setPlaceholderText(self.i18n.t("realtime_record.markers_placeholder"))
            self._refresh_markers_list()
        if hasattr(self, "clear_markers_button"):
            self.clear_markers_button.setText(self.i18n.t("realtime_record.clear_markers"))

    @staticmethod
    def _count_words(text: str) -> int:
        stripped = (text or "").strip()
        if not stripped:
            return 0
        return len(stripped.split())

    def _set_word_count_label(self, label: QLabel, text: str) -> None:
        label.setText(f"{self._count_words(text)} {self.i18n.t('common.words')}")

    def _update_word_count_labels(self) -> None:
        if hasattr(self, "transcription_word_count") and hasattr(self, "transcription_text"):
            self._set_word_count_label(
                self.transcription_word_count, self.transcription_text.toPlainText()
            )
        if hasattr(self, "translation_word_count") and hasattr(self, "translation_text"):
            self._set_word_count_label(self.translation_word_count, self.translation_text.toPlainText())

    def _on_transcription(self, text: str):
        self.signals.transcription_updated.emit(text)

    def _on_translation(self, text: str):
        self.signals.translation_updated.emit(text)

    def _on_error(self, error: str):
        self.signals.error_occurred.emit(error)

    def _on_audio_data(self, audio_chunk):
        self.signals.audio_data_available.emit(audio_chunk)

    def _on_marker(self, marker):
        self.signals.marker_added.emit(marker)

    @Slot(str)
    def _update_transcription_display(self, text: str):
        try:
            with self._buffer_lock:
                self._transcription_buffer.append(text)
            self.transcription_text.blockSignals(True)
            if self.transcription_text.document().isEmpty():
                self.transcription_text.setPlainText(text)
            else:
                self.transcription_text.appendPlainText(text)
            self.transcription_text.blockSignals(False)
            self._set_word_count_label(
                self.transcription_word_count, self.transcription_text.toPlainText()
            )
            scrollbar = self.transcription_text.verticalScrollBar()
            if scrollbar:
                scrollbar.setValue(scrollbar.maximum())
        except Exception as e:
            logger.error(f"Error updating transcription display: {e}")

    @Slot(str)
    def _update_translation_display(self, text: str):
        try:
            with self._buffer_lock:
                self._translation_buffer.append(text)
            self.translation_text.blockSignals(True)
            if self.translation_text.document().isEmpty():
                self.translation_text.setPlainText(text)
            else:
                self.translation_text.appendPlainText(text)
            self.translation_text.blockSignals(False)
            self._set_word_count_label(self.translation_word_count, self.translation_text.toPlainText())
            scrollbar = self.translation_text.verticalScrollBar()
            if scrollbar:
                scrollbar.setValue(scrollbar.maximum())
        except Exception as e:
            logger.error(f"Error updating translation display: {e}")

    @Slot(object)
    def _append_marker_item(self, marker):
        if not marker or not hasattr(self, "markers_list"):
            return
        self._markers.append(marker)
        text = self._format_marker_entry(marker)
        self.markers_list.addItem(text)
        self.markers_list.scrollToBottom()

    def _refresh_markers_list(self):
        if not hasattr(self, "markers_list"):
            return
        self.markers_list.blockSignals(True)
        self.markers_list.clear()
        for marker in self._markers:
            self.markers_list.addItem(self._format_marker_entry(marker))
        self.markers_list.blockSignals(False)
        if self._markers:
            self.markers_list.scrollToBottom()

    def _format_marker_entry(self, marker) -> str:
        index = marker.get("index", len(self._markers))
        timestamp = self._format_marker_timestamp(marker.get("offset", 0.0))
        label = marker.get("label") or ""
        if label:
            return self.i18n.t(
                "realtime_record.marker_item_with_label",
                number=index,
                timestamp=timestamp,
                label=label,
            )
        return self.i18n.t("realtime_record.marker_item", number=index, timestamp=timestamp)

    @staticmethod
    def _format_marker_timestamp(seconds: float) -> str:
        total_msg = int(round(seconds * 1000))
        hours, remainder = divmod(total_msg, 3_600_000)
        minutes, remainder = divmod(remainder, 60_000)
        seconds_fraction = remainder / 1000.0
        if hours:
            return f"{hours:02d}:{minutes:02d}:{seconds_fraction:06.3f}"
        return f"{minutes:02d}:{seconds_fraction:06.3f}"

    @staticmethod
    def _format_duration_hhmmss(duration: float) -> str:
        total_seconds = max(int(duration), 0)
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def _update_status_message(self, message: str, level: str) -> None:
        if not hasattr(self, "feedback_label") or self.feedback_label is None:
            return
        if not message:
            self.feedback_label.clear()
            self.feedback_label.setVisible(False)
            return
        self.feedback_label.setProperty("role", "feedback")
        self.feedback_label.setProperty("state", level)
        self.feedback_label.setText(message)
        self.feedback_label.setVisible(True)
        self.feedback_label.style().unpolish(self.feedback_label)
        self.feedback_label.style().polish(self.feedback_label)

    @Slot(str)
    def _show_error(self, error: str):
        error_detail = error or self.i18n.t("errors.unknown_error")
        logger.error("Recording error: %s", error_detail)

        prefix = self.i18n.t("realtime_record.feedback.error_prefix")
        label_message = f"{prefix}: {error_detail}"
        self._update_status_message(label_message, "error")

        if self._notification_manager is not None:
            try:
                title = self.i18n.t("notifications.recording_failed")
                self._notification_manager.send_error(title, error_detail)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to send error notification: %s", exc, exc_info=True)

    @Slot(bool, float)
    def _update_status_display(self, is_recording: bool, duration: float):
        self.duration_value_label.setText(self._format_duration_hhmmss(duration))

    @Slot()
    def _on_recording_started(self):
        logger.info(self.i18n.t("logging.realtime_record.updating_ui_recording_started"))
        self.record_button.setText(self.i18n.t("realtime_record.stop_recording"))
        self.record_button.setProperty("recording", True)
        self.record_button.style().unpolish(self.record_button)
        self.record_button.style().polish(self.record_button)
        self.status_timer.start(100)
        if hasattr(self, "add_marker_button"):
            self.add_marker_button.setEnabled(True)
            self.add_marker_button.setToolTip("")
        if hasattr(self, "status_indicator"):
            self.status_indicator.setProperty("state", "recording")
            self.status_indicator.style().unpolish(self.status_indicator)
            self.status_indicator.style().polish(self.status_indicator)
        if hasattr(self, "status_text_label"):
            self.status_text_label.setText(self.i18n.t("realtime_record.status_recording"))

    @Slot()
    def _on_recording_stopped(self):
        logger.info(self.i18n.t("logging.realtime_record.updating_ui_recording_stopped"))
        self.record_button.setText(self.i18n.t("realtime_record.start_recording"))
        self.record_button.setProperty("recording", False)
        self.record_button.style().unpolish(self.record_button)
        self.record_button.style().polish(self.record_button)
        self.status_timer.stop()
        if hasattr(self, "add_marker_button"):
            self.add_marker_button.setEnabled(False)
        if hasattr(self, "status_indicator"):
            self.status_indicator.setProperty("state", "ready")
            self.status_indicator.style().unpolish(self.status_indicator)
            self.status_indicator.style().polish(self.status_indicator)
        if hasattr(self, "status_text_label"):
            self.status_text_label.setText(self.i18n.t("realtime_record.status_ready"))

    @Slot()
    def _update_status(self):
        if not self.recorder.is_recording:
            return
        status = self.recorder.get_recording_status()
        self.signals.status_changed.emit(
            status.get("is_recording", False), status.get("duration", 0.0)
        )

    def _reset_markers_ui(self):
        self._markers.clear()
        if hasattr(self, "markers_list"):
            self.markers_list.clear()
        if hasattr(self.recorder, "clear_markers"):
            try:
                self.recorder.clear_markers()
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to clear recorder markers: %s", exc)

    def _on_gain_changed(self, value: int):
        gain = value / 100.0
        self.gain_value_label.setText(f"{gain:.1f}x")
        if self.audio_capture is not None:
            self.audio_capture.set_gain(gain)

    def _on_translation_toggled(self, state: int):
        enabled = state == Qt.CheckState.Checked.value
        if self.recorder.translation_engine:
            self.target_lang_combo.setEnabled(enabled)
        else:
            self.target_lang_combo.setEnabled(False)

    def _add_marker(self):
        if not self.recorder.is_recording:
            warning = self.i18n.t("realtime_record.marker_unavailable")
            logger.warning("Cannot add marker: %s", warning)
            self.signals.error_occurred.emit(warning)
            return

        marker = self.recorder.add_marker()
        if marker is None:
            warning = self.i18n.t("realtime_record.marker_failed")
            logger.error("Recorder rejected marker: %s", warning)
            self.signals.error_occurred.emit(warning)

    def _toggle_recording(self):
        if not self._audio_available:
            warning = self.i18n.t("realtime_record.audio_unavailable_tooltip")
            logger.warning("Realtime recording unavailable: %s", warning)
            self.signals.error_occurred.emit(warning)
            return

        if not self.recorder.is_recording:
            start_request = self._prepare_start_request()
            if start_request is None:
                return
            self._clear_session_ui()
            self._submit_worker_task(self._start_recording(start_request))
        else:
            self._submit_worker_task(self._stop_recording())

    def _prepare_start_request(self) -> Optional[Dict[str, Any]]:
        """Collect and validate recording parameters on the UI thread."""
        self._refresh_recording_preferences()

        device_index = self.input_combo.currentData()
        source_lang = self.source_lang_combo.currentData()
        enable_translation = self.enable_translation_checkbox.isChecked()
        target_lang = self.target_lang_combo.currentData()

        options: Dict[str, Any] = {
            "language": source_lang,
            "enable_translation": enable_translation,
            "target_language": target_lang,
            "recording_format": self._recording_format,
            "save_recording": self._auto_save_enabled,
            "save_transcript": self._save_transcript_enabled,
            "create_calendar_event": self._create_calendar_event_enabled,
            "vad_threshold": self._vad_threshold,
            "silence_duration_ms": self._silence_duration_ms,
            "min_audio_duration": self._min_audio_duration,
        }

        if self.model_manager and hasattr(self, "model_combo"):
            selected_model = self.model_combo.currentData()
            if not selected_model:
                error_msg = self.i18n.t("realtime_record.no_model_selected")
                self.signals.error_occurred.emit(error_msg)
                return None

            model_info = self.model_manager.get_model(selected_model)
            if not model_info or not model_info.is_downloaded:
                error_msg = self.i18n.t("realtime_record.model_not_downloaded")
                self.signals.error_occurred.emit(error_msg)
                return None

            options["model_name"] = selected_model
            options["model_path"] = model_info.local_path

        return {
            "device_index": device_index,
            "options": options,
        }

    def _clear_session_ui(self) -> None:
        """Reset visual state before starting a new recording session."""
        with self._buffer_lock:
            self._transcription_buffer.clear()
            self._translation_buffer.clear()

        if hasattr(self, "transcription_text"):
            self.transcription_text.clear()
        if hasattr(self, "translation_text"):
            self.translation_text.clear()
        self._update_word_count_labels()
        if hasattr(self, "audio_visualizer"):
            self.audio_visualizer.clear()
        self._reset_markers_ui()
        self._update_status_message("", "success")

    def _submit_worker_task(self, coro) -> None:
        """Submit coroutine to worker loop and track lifecycle."""
        future = self._worker.submit(coro)
        self._async_loop = self._worker.loop
        if future is None:
            coro.close()
            self.signals.error_occurred.emit(self.i18n.t("errors.unknown_error"))
            return

        with self._future_lock:
            self._pending_futures.add(future)

        def _on_done(done_future: Future):
            with self._future_lock:
                self._pending_futures.discard(done_future)

            if done_future.cancelled():
                return

            exception = done_future.exception()
            if exception is not None:
                logger.error("Worker coroutine failed: %s", exception, exc_info=True)

        future.add_done_callback(_on_done)

    async def _start_recording(self, start_request: Dict[str, Any]):
        try:
            device_index = start_request.get("device_index")
            options = start_request.get("options", {})

            # Pass the worker's loop to recorder
            await self.recorder.start_recording(
                input_source=device_index, options=options, event_loop=self._worker.loop
            )

            self.signals.recording_started.emit()
            logger.info(self.i18n.t("logging.realtime_record.recording_started"))

        except Exception as e:
            error_message = self.i18n.t("realtime_record.start_failed", error=str(e))
            logger.error(error_message, exc_info=True)
            self.signals.error_occurred.emit(error_message)

    async def _stop_recording(self):
        try:
            result = await self.recorder.stop_recording()
            self.signals.recording_stopped.emit()
            logger.info(f"Recording stopped: {result}")
            self.signals.recording_succeeded.emit(result or {})
        except Exception as e:
            error_message = self.i18n.t("realtime_record.stop_failed", error=str(e))
            logger.error(error_message, exc_info=True)
            self.signals.error_occurred.emit(error_message)

    @Slot(dict)
    def _on_recording_succeeded(self, result: Dict):
        if not isinstance(result, dict):
            result = {}
        duration_seconds = float(result.get("duration") or 0.0)
        duration_text = self._format_duration_hhmmss(duration_seconds)
        save_path = (
            result.get("recording_path")
            or result.get("transcript_path")
            or result.get("translation_path")
            or ""
        )
        success_prefix = self.i18n.t("realtime_record.feedback.success_prefix")
        if save_path:
            detail = self.i18n.t(
                "realtime_record.feedback.success_detail_with_path",
                duration=duration_text,
                path=save_path,
            )
        else:
            detail = self.i18n.t("realtime_record.feedback.success_detail", duration=duration_text)

        label_message = f"{success_prefix}: {detail}"
        self._update_status_message(label_message, "success")

        if self._notification_manager is not None:
            try:
                title = self.i18n.t("notifications.recording_saved")
                self._notification_manager.send_success(title, detail)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to send success notification: %s", exc, exc_info=True)

    def _export_transcription(self):
        from PySide6.QtWidgets import QFileDialog

        text = self.recorder.get_accumulated_transcription()
        if not text:
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            self.i18n.t("realtime_record.export_transcription_title"),
            "",
            self.i18n.t("realtime_record.export_file_filter"),
        )
        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(text)
                logger.info(f"Transcription exported to {file_path}")
            except Exception as e:
                logger.error(f"Failed to export transcription: {e}")
                self._show_error(self.i18n.t("realtime_record.export_failed", error=str(e)))

    def _export_translation(self):
        from PySide6.QtWidgets import QFileDialog

        text = self.recorder.get_accumulated_translation()
        if not text:
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            self.i18n.t("realtime_record.export_translation_title"),
            "",
            self.i18n.t("realtime_record.export_file_filter"),
        )
        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(text)
                logger.info(f"Translation exported to {file_path}")
            except Exception as e:
                logger.error(f"Failed to export translation: {e}")
                self._show_error(self.i18n.t("realtime_record.export_failed", error=str(e)))

    def _cleanup_resources(self):
        """Cleanup resources before closing."""
        if self._cleanup_done or self._cleanup_in_progress:
            return

        self._cleanup_in_progress = True
        try:
            if hasattr(self, "status_timer") and self.status_timer:
                self.status_timer.stop()

            worker_loop = getattr(self._worker, "loop", None)
            if (
                worker_loop is not None
                and worker_loop.is_running()
                and getattr(self.recorder, "is_recording", False)
            ):
                try:
                    stop_future = asyncio.run_coroutine_threadsafe(
                        self.recorder.stop_recording(), worker_loop
                    )
                    with self._future_lock:
                        self._pending_futures.add(stop_future)
                    stop_result = stop_future.result(timeout=10.0)
                    if isinstance(stop_result, dict):
                        self.signals.recording_stopped.emit()
                        self.signals.recording_succeeded.emit(stop_result)
                except TimeoutError:
                    logger.warning("Timed out while stopping active recording during cleanup")
                except Exception as exc:  # noqa: BLE001
                    logger.error("Failed to stop recording during cleanup: %s", exc, exc_info=True)

            with self._future_lock:
                pending = list(self._pending_futures)

            for future in pending:
                if not future.done():
                    future.cancel()

            for future in pending:
                try:
                    future.result(timeout=1.0)
                except Exception:
                    pass

            with self._future_lock:
                self._pending_futures.clear()

            if hasattr(self, "_worker") and self._worker:
                self._worker.stop()
                self._async_loop = None

            self._cleanup_done = True
        finally:
            self._cleanup_in_progress = False

    def closeEvent(self, event):
        self._cleanup_resources()
        super().closeEvent(event)

    def deleteLater(self):
        self._cleanup_resources()
        super().deleteLater()
