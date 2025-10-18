"""
实时录制主界面

实现实时录制的完整 UI，包括音频输入选择、增益调整、语言选择、
转录和翻译文本显示等功能
"""

import logging
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QSlider, QCheckBox, QPushButton, QPlainTextEdit, QGroupBox, QListWidget
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject
import threading

logger = logging.getLogger(__name__)


class RealtimeRecorderSignals(QObject):
    """Qt Signal wrapper for RealtimeRecorder callbacks"""

    # Signal emitted when new transcription text is available
    transcription_updated = pyqtSignal(str)

    # Signal emitted when new translation text is available
    translation_updated = pyqtSignal(str)

    # Signal emitted when an error occurs
    error_occurred = pyqtSignal(str)

    # Signal emitted when recording status changes
    status_changed = pyqtSignal(bool, float)

    # Signal emitted when audio data is available (for visualization)
    audio_data_available = pyqtSignal(object)  # np.ndarray
    
    # Signal emitted when recording starts (for UI update)
    recording_started = pyqtSignal()
    
    # Signal emitted when recording stops (for UI update)
    recording_stopped = pyqtSignal()

    # Signal emitted when a marker is added
    marker_added = pyqtSignal(object)

    def __init__(self):
        super().__init__()


class RealtimeRecordWidget(QWidget):
    """实时录制主界面"""

    def __init__(self, recorder, audio_capture, i18n_manager, model_manager=None, parent=None):
        """
        初始化实时录制界面

        Args:
            recorder: RealtimeRecorder 实例
            audio_capture: AudioCapture 实例
            i18n_manager: I18nQtManager 实例
            model_manager: ModelManager 实例（可选）
            parent: 父窗口
        """
        super().__init__(parent)
        self.recorder = recorder
        self.audio_capture = audio_capture
        self._audio_available = audio_capture is not None
        self.i18n = i18n_manager
        self.model_manager = model_manager

        # 创建信号包装器
        self.signals = RealtimeRecorderSignals()
        self._markers = []

        # 文本缓冲区（用于批量更新）
        self._transcription_buffer = []
        self._translation_buffer = []
        self._buffer_lock = threading.Lock()

        # Connect model manager signals if available
        if self.model_manager:
            self.model_manager.models_updated.connect(self._update_model_list)

        # 设置回调函数
        self.recorder.set_callbacks(
            on_transcription=self._on_transcription,
            on_translation=self._on_translation,
            on_error=self._on_error,
            on_audio_data=self._on_audio_data,
            on_marker=self._on_marker
        )

        # 连接信号到槽（使用 QueuedConnection 确保线程安全）
        self.signals.transcription_updated.connect(
            self._update_transcription_display,
            Qt.ConnectionType.QueuedConnection
        )
        self.signals.translation_updated.connect(
            self._update_translation_display,
            Qt.ConnectionType.QueuedConnection
        )
        self.signals.error_occurred.connect(
            self._show_error,
            Qt.ConnectionType.QueuedConnection
        )
        self.signals.status_changed.connect(
            self._update_status_display,
            Qt.ConnectionType.QueuedConnection
        )
        self.signals.recording_started.connect(
            self._on_recording_started,
            Qt.ConnectionType.QueuedConnection
        )
        self.signals.recording_stopped.connect(
            self._on_recording_stopped,
            Qt.ConnectionType.QueuedConnection
        )
        self.signals.marker_added.connect(
            self._append_marker_item,
            Qt.ConnectionType.QueuedConnection
        )

        # 状态更新定时器
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self._update_status)

        # 创建专用的异步事件循环线程
        self._async_loop = None
        self._async_thread = None
        self._init_async_loop()

        # 初始化 UI
        self._init_ui()

        # 连接语言切换信号
        self.i18n.language_changed.connect(self._update_ui_text)

        logger.info("RealtimeRecordWidget initialized")
    
    def _init_async_loop(self):
        """初始化异步事件循环"""
        import asyncio
        import threading
        
        def run_loop():
            """在独立线程中运行事件循环"""
            self._async_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._async_loop)
            logger.info("Async event loop started")
            self._async_loop.run_forever()
            logger.info("Async event loop stopped")
        
        self._async_thread = threading.Thread(target=run_loop, daemon=True)
        self._async_thread.start()
        
        # 等待事件循环初始化
        import time
        for _ in range(10):
            if self._async_loop is not None:
                break
            time.sleep(0.1)
        
        if self._async_loop is None:
            raise RuntimeError("Failed to initialize async event loop")

    def _init_ui(self):
        """初始化 UI 组件"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # 标题
        self.title_label = QLabel(self.i18n.t("realtime_record.title"))
        self.title_label.setObjectName("page_title")
        layout.addWidget(self.title_label)

        # 音频输入设置组
        audio_group = self._create_audio_input_group()
        layout.addWidget(audio_group)

        # 语言设置组
        language_group = self._create_language_group()
        layout.addWidget(language_group)

        # 录制控制组
        control_group = self._create_control_group()
        layout.addWidget(control_group)

        # 文本显示区域 - 使用水平分割器以避免堆叠
        text_container = self._create_text_display_container()
        layout.addWidget(text_container, stretch=1)

        # 导出按钮组
        export_group = self._create_export_group()
        layout.addWidget(export_group)

        # Update model list if model_manager is available
        if self.model_manager:
            self._update_model_list()

        # 更新 UI 文本
        self._update_ui_text()
        self._update_audio_availability()

    def _create_audio_input_group(self) -> QGroupBox:
        """创建音频输入设置组"""
        group = QGroupBox()
        group.setObjectName("audio_input_group")
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        # 音频输入源和增益控制
        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(15)

        # 音频输入源标签
        input_label = QLabel()
        input_label.setObjectName("input_label")
        controls_layout.addWidget(input_label)

        # 音频输入源下拉框
        self.input_combo = QComboBox()
        self.input_combo.setMinimumWidth(200)
        self.input_combo.setMaximumWidth(300)
        self._populate_input_devices()
        controls_layout.addWidget(self.input_combo)

        controls_layout.addSpacing(30)

        # 增益标签
        gain_label = QLabel()
        gain_label.setObjectName("gain_label")
        controls_layout.addWidget(gain_label)

        # 增益滑块
        self.gain_slider = QSlider(Qt.Orientation.Horizontal)
        self.gain_slider.setMinimum(10)  # 0.1x
        self.gain_slider.setMaximum(200)  # 2.0x
        self.gain_slider.setValue(100)  # 1.0x
        self.gain_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.gain_slider.setTickInterval(10)
        self.gain_slider.setMinimumWidth(150)
        self.gain_slider.setMaximumWidth(250)
        self.gain_slider.valueChanged.connect(self._on_gain_changed)
        controls_layout.addWidget(self.gain_slider)

        # 增益值显示
        self.gain_value_label = QLabel("1.0x")
        self.gain_value_label.setMinimumWidth(50)
        controls_layout.addWidget(self.gain_value_label)

        controls_layout.addStretch()

        layout.addLayout(controls_layout)

        # 音频可视化组件
        from ui.realtime_record.audio_visualizer import AudioVisualizer
        self.audio_visualizer = AudioVisualizer()
        self.audio_visualizer.setMinimumHeight(50)
        self.audio_visualizer.setMaximumHeight(70)
        self.signals.audio_data_available.connect(
            self.audio_visualizer.update_audio_data,
            Qt.ConnectionType.QueuedConnection
        )
        layout.addWidget(self.audio_visualizer)

        self.audio_unavailable_label = QLabel()
        self.audio_unavailable_label.setObjectName("audio_unavailable_label")
        self.audio_unavailable_label.setWordWrap(True)
        self.audio_unavailable_label.setVisible(False)
        layout.addWidget(self.audio_unavailable_label)

        group.setLayout(layout)
        return group

    def _create_language_group(self) -> QGroupBox:
        """创建语言设置组"""
        group = QGroupBox()
        group.setObjectName("language_group")
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(15)

        # Model selection (if model_manager is available)
        if self.model_manager:
            model_label = QLabel()
            model_label.setObjectName("model_label")
            layout.addWidget(model_label)

            self.model_combo = QComboBox()
            self.model_combo.setMinimumWidth(150)
            self.model_combo.setMaximumWidth(200)
            layout.addWidget(self.model_combo)

            layout.addSpacing(20)

        # 源语言标签
        source_lang_label = QLabel()
        source_lang_label.setObjectName("source_lang_label")
        layout.addWidget(source_lang_label)

        # 源语言下拉框
        self.source_lang_combo = QComboBox()
        self.source_lang_combo.setMinimumWidth(120)
        self.source_lang_combo.setMaximumWidth(150)
        self.source_lang_combo.addItem("中文", "zh")
        self.source_lang_combo.addItem("English", "en")
        self.source_lang_combo.addItem("Français", "fr")
        self.source_lang_combo.addItem("日本語", "ja")
        self.source_lang_combo.addItem("한국어", "ko")
        layout.addWidget(self.source_lang_combo)

        layout.addSpacing(20)

        # 启用翻译复选框
        self.enable_translation_checkbox = QCheckBox()
        self.enable_translation_checkbox.setObjectName(
            "enable_translation_checkbox"
        )
        self.enable_translation_checkbox.stateChanged.connect(
            self._on_translation_toggled
        )
        
        # 检查翻译引擎是否可用
        if not self.recorder.translation_engine:
            self.enable_translation_checkbox.setEnabled(False)
            self.enable_translation_checkbox.setToolTip(
                "Translation not available: No API key configured. "
                "Please configure Google Translate API key in Settings."
            )
        
        layout.addWidget(self.enable_translation_checkbox)

        layout.addSpacing(10)

        # 目标语言标签
        target_lang_label = QLabel()
        target_lang_label.setObjectName("target_lang_label")
        layout.addWidget(target_lang_label)

        # 目标语言下拉框
        self.target_lang_combo = QComboBox()
        self.target_lang_combo.setMinimumWidth(120)
        self.target_lang_combo.setMaximumWidth(150)
        self.target_lang_combo.addItem("English", "en")
        self.target_lang_combo.addItem("中文", "zh")
        self.target_lang_combo.addItem("Français", "fr")
        self.target_lang_combo.addItem("日本語", "ja")
        self.target_lang_combo.addItem("한국어", "ko")
        # 默认禁用，只有勾选翻译复选框时才启用
        self.target_lang_combo.setEnabled(False)
        
        # 如果翻译引擎不可用，也禁用目标语言选择
        if not self.recorder.translation_engine:
            self.target_lang_combo.setToolTip(
                "Translation not available: No API key configured"
            )
        
        layout.addWidget(self.target_lang_combo)

        layout.addStretch()

        group.setLayout(layout)
        return group

    def _create_control_group(self) -> QGroupBox:
        """创建录制控制组"""
        group = QGroupBox()
        group.setObjectName("control_group")
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(15)

        # 开始/停止录制按钮
        self.record_button = QPushButton()
        self.record_button.setObjectName("record_button")
        self.record_button.setMinimumHeight(40)
        self.record_button.setMinimumWidth(150)
        self.record_button.clicked.connect(self._toggle_recording)
        layout.addWidget(self.record_button)

        # 添加标记按钮
        self.add_marker_button = QPushButton()
        self.add_marker_button.setObjectName("add_marker_button")
        self.add_marker_button.setMinimumHeight(40)
        self.add_marker_button.setEnabled(False)
        self.add_marker_button.clicked.connect(self._add_marker)
        layout.addWidget(self.add_marker_button)

        layout.addSpacing(30)

        # 录制时长标签
        duration_label = QLabel()
        duration_label.setObjectName("duration_label")
        layout.addWidget(duration_label)

        # 录制时长显示
        self.duration_value_label = QLabel("00:00:00")
        self.duration_value_label.setStyleSheet(
            "font-size: 16px; font-weight: bold;"
        )
        layout.addWidget(self.duration_value_label)

        layout.addStretch()

        group.setLayout(layout)
        return group

    def _create_text_display_container(self) -> QWidget:
        """创建文本显示容器 - 使用水平布局避免堆叠"""
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(15)

        # 转录文本显示组
        transcription_group = QGroupBox()
        transcription_group.setObjectName("transcription_group")
        transcription_layout = QVBoxLayout()
        transcription_layout.setContentsMargins(0, 0, 0, 0)
        transcription_layout.setSpacing(0)

        # 转录文本显示区域 - 使用 QPlainTextEdit 更轻量级
        self.transcription_text = QPlainTextEdit()
        self.transcription_text.setObjectName("transcription_text")
        self.transcription_text.setReadOnly(True)
        self.transcription_text.setMinimumHeight(150)
        # 设置文档选项以避免线程问题
        self.transcription_text.setUndoRedoEnabled(False)
        transcription_layout.addWidget(self.transcription_text)

        transcription_group.setLayout(transcription_layout)
        layout.addWidget(transcription_group, stretch=1)

        # 翻译文本显示组
        translation_group = QGroupBox()
        translation_group.setObjectName("translation_group")
        translation_layout = QVBoxLayout()
        translation_layout.setContentsMargins(0, 0, 0, 0)
        translation_layout.setSpacing(0)

        # 翻译文本显示区域 - 使用 QPlainTextEdit 更轻量级
        self.translation_text = QPlainTextEdit()
        self.translation_text.setObjectName("translation_text")
        self.translation_text.setReadOnly(True)
        self.translation_text.setMinimumHeight(150)
        # 设置文档选项以避免线程问题
        self.translation_text.setUndoRedoEnabled(False)
        translation_layout.addWidget(self.translation_text)

        translation_group.setLayout(translation_layout)
        layout.addWidget(translation_group, stretch=1)

        # 标记列表组
        markers_group = QGroupBox()
        markers_group.setObjectName("markers_group")
        markers_layout = QVBoxLayout()
        markers_layout.setContentsMargins(0, 0, 0, 0)
        markers_layout.setSpacing(0)

        self.markers_list = QListWidget()
        self.markers_list.setObjectName("markers_list")
        self.markers_list.setAlternatingRowColors(True)
        self.markers_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.markers_list.setSelectionMode(
            QListWidget.SelectionMode.NoSelection
        )
        markers_layout.addWidget(self.markers_list)

        markers_group.setLayout(markers_layout)
        layout.addWidget(markers_group, stretch=0)

        return container

    def _create_export_group(self) -> QWidget:
        """创建导出按钮组"""
        widget = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 10, 0, 0)
        layout.setSpacing(10)

        # 导出转录按钮
        self.export_transcription_button = QPushButton()
        self.export_transcription_button.setObjectName(
            "export_transcription_button"
        )
        self.export_transcription_button.clicked.connect(
            self._export_transcription
        )
        layout.addWidget(self.export_transcription_button)

        # 导出翻译按钮
        self.export_translation_button = QPushButton()
        self.export_translation_button.setObjectName(
            "export_translation_button"
        )
        self.export_translation_button.clicked.connect(
            self._export_translation
        )
        layout.addWidget(self.export_translation_button)

        # 保存录音按钮
        self.save_recording_button = QPushButton()
        self.save_recording_button.setObjectName("save_recording_button")
        self.save_recording_button.clicked.connect(self._save_recording)
        layout.addWidget(self.save_recording_button)

        layout.addStretch()

        widget.setLayout(layout)
        return widget

    def _populate_input_devices(self):
        """填充音频输入设备列表"""
        if self.audio_capture is None:
            self.input_combo.clear()
            self.input_combo.addItem(
                self.i18n.t("realtime_record.audio_unavailable_short"),
                None
            )
            return

        try:
            devices = self.audio_capture.get_input_devices()

            self.input_combo.clear()

            if not devices:
                self.input_combo.addItem(
                    self.i18n.t("realtime_record.no_input_devices"),
                    None
                )
                return

            for device in devices:
                self.input_combo.addItem(
                    device['name'],
                    device['index']
                )

            logger.info(f"Populated {len(devices)} input devices")

        except Exception as e:
            logger.error(f"Failed to populate input devices: {e}")
            self.input_combo.addItem("Error loading devices", None)

    def _update_audio_availability(self):
        """根据音频捕获可用性调整 UI 状态"""
        if hasattr(self.recorder, 'audio_capture'):
            self.audio_capture = self.recorder.audio_capture

        previous_state = getattr(self, '_audio_available', False)

        available = False
        if hasattr(self.recorder, 'audio_input_available'):
            try:
                available = bool(self.recorder.audio_input_available())
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to check audio availability: %s", exc)
        elif self.audio_capture is not None:
            available = True

        self._audio_available = available

        tooltip = self.i18n.t("realtime_record.audio_unavailable_tooltip")
        guide_text = self.i18n.t(
            "realtime_record.audio_unavailable_message",
            command="pip install pyaudio"
        )
        short_text = self.i18n.t("realtime_record.audio_unavailable_short")

        record_button = getattr(self, 'record_button', None)
        if record_button:
            record_button.setEnabled(self._audio_available)
            record_button.setToolTip('' if self._audio_available else tooltip)

        add_marker_button = getattr(self, 'add_marker_button', None)
        if add_marker_button:
            add_marker_button.setEnabled(
                self._audio_available and self.recorder.is_recording
            )
            add_marker_button.setToolTip(
                '' if self._audio_available else tooltip
            )

        for widget_name in ('input_combo', 'gain_slider', 'gain_value_label', 'audio_visualizer'):
            widget = getattr(self, widget_name, None)
            if widget:
                widget.setEnabled(self._audio_available)

        if hasattr(self, 'audio_unavailable_label'):
            if self._audio_available:
                self.audio_unavailable_label.setVisible(False)
                self.audio_unavailable_label.clear()
            else:
                self.audio_unavailable_label.setText(guide_text)
                self.audio_unavailable_label.setVisible(True)

        if not self._audio_available and hasattr(self, 'input_combo'):
            self.input_combo.clear()
            self.input_combo.addItem(short_text, None)
        elif self._audio_available and not previous_state:
            # 仅在状态从不可用切换到可用时刷新设备列表
            self._populate_input_devices()

    def _update_model_list(self):
        """Update model combo box with downloaded models."""
        if not self.model_manager or not hasattr(self, 'model_combo'):
            return
        
        try:
            # Save current selection
            current_model = self.model_combo.currentText()
            
            # Clear combo box
            self.model_combo.clear()
            
            # Get downloaded models
            downloaded_models = self.model_manager.get_downloaded_models()
            
            if not downloaded_models:
                # No models available - show guide
                self.model_combo.addItem(
                    self.i18n.t("realtime_record.no_models_available"),
                    None
                )
                self.model_combo.setEnabled(False)
                self._show_download_guide()
                logger.warning("No models downloaded")
            else:
                # Enable combo box
                self.model_combo.setEnabled(True)
                
                # Hide download guide if it exists
                if hasattr(self, '_download_guide_widget'):
                    self._download_guide_widget.hide()
                
                # Add downloaded models
                for model in downloaded_models:
                    self.model_combo.addItem(model.name, model.name)
                
                # Restore previous selection or select default
                if current_model:
                    index = self.model_combo.findText(current_model)
                    if index >= 0:
                        self.model_combo.setCurrentIndex(index)
                else:
                    # Select default model from config or first model
                    default_model = self.model_manager.config.get(
                        "transcription.faster_whisper.default_model"
                    )
                    if default_model:
                        index = self.model_combo.findText(default_model)
                        if index >= 0:
                            self.model_combo.setCurrentIndex(index)
                
                logger.info(f"Updated model list: {len(downloaded_models)} models")
        
        except Exception as e:
            logger.error(f"Failed to update model list: {e}")

    def _show_download_guide(self):
        """Show download guide when no models are available."""
        if hasattr(self, '_download_guide_widget'):
            self._download_guide_widget.show()
            return
        
        # Create download guide widget
        from PyQt6.QtWidgets import QFrame, QLabel, QPushButton
        
        guide_widget = QFrame()
        guide_widget.setObjectName("download_guide")
        guide_widget.setFrameStyle(QFrame.Shape.StyledPanel)
        guide_layout = QHBoxLayout(guide_widget)
        
        # Warning icon and message
        warning_label = QLabel("⚠️")
        warning_label.setStyleSheet("font-size: 20px;")
        guide_layout.addWidget(warning_label)
        
        message_label = QLabel(
            self.i18n.t("realtime_record.no_models_message")
        )
        message_label.setWordWrap(True)
        guide_layout.addWidget(message_label, 1)
        
        # Download button
        download_button = QPushButton(
            self.i18n.t("realtime_record.go_to_download")
        )
        download_button.clicked.connect(self._navigate_to_model_management)
        guide_layout.addWidget(download_button)
        
        # Insert guide widget after language group
        language_group = self.findChild(QGroupBox, "language_group")
        if language_group:
            parent_layout = language_group.parent().layout()
            if parent_layout:
                # Find index of language group
                for i in range(parent_layout.count()):
                    if parent_layout.itemAt(i).widget() == language_group:
                        parent_layout.insertWidget(i + 1, guide_widget)
                        break
        
        self._download_guide_widget = guide_widget
        logger.info("Download guide displayed")

    def _navigate_to_model_management(self):
        """Navigate to model management page in settings."""
        try:
            # Find main window and navigate to settings
            main_window = self.window()
            if hasattr(main_window, 'show_page'):
                main_window.show_page('settings')
                
                # Try to switch to model management page in settings
                settings_widget = main_window.pages.get('settings')
                if settings_widget and hasattr(settings_widget, 'show_page'):
                    settings_widget.show_page('model_management')
                    logger.info("Navigated to model management page")
        except Exception as e:
            logger.error(f"Failed to navigate to model management: {e}")

    def _update_ui_text(self):
        """更新 UI 文本（用于语言切换）"""
        # 标题
        if hasattr(self, 'title_label'):
            self.title_label.setText(self.i18n.t("realtime_record.title"))

        # 音频输入组
        audio_group = self.findChild(QGroupBox, "audio_input_group")
        if audio_group:
            audio_group.setTitle(self.i18n.t("realtime_record.audio_input"))

        input_label = self.findChild(QLabel, "input_label")
        if input_label:
            text = self.i18n.t("realtime_record.audio_input") + ":"
            input_label.setText(text)

        gain_label = self.findChild(QLabel, "gain_label")
        if gain_label:
            gain_label.setText(self.i18n.t("realtime_record.gain") + ":")

        # 语言组
        language_group = self.findChild(QGroupBox, "language_group")
        if language_group:
            language_group.setTitle(self.i18n.t("realtime_record.language_settings"))

        # Model label
        model_label = self.findChild(QLabel, "model_label")
        if model_label:
            model_label.setText(self.i18n.t("realtime_record.model") + ":")

        source_lang_label = self.findChild(QLabel, "source_lang_label")
        if source_lang_label:
            source_lang_label.setText(
                self.i18n.t("realtime_record.source_language") + ":"
            )

        target_lang_label = self.findChild(QLabel, "target_lang_label")
        if target_lang_label:
            target_lang_label.setText(
                self.i18n.t("realtime_record.target_language") + ":"
            )

        enable_translation_checkbox = self.findChild(
            QCheckBox, "enable_translation_checkbox"
        )
        if enable_translation_checkbox:
            text = self.i18n.t("realtime_record.enable_translation")
            enable_translation_checkbox.setText(text)

        # 控制组
        control_group = self.findChild(QGroupBox, "control_group")
        if control_group:
            control_group.setTitle(self.i18n.t("realtime_record.recording_control"))

        record_button = self.findChild(QPushButton, "record_button")
        if record_button:
            if self.recorder.is_recording:
                record_button.setText(
                    self.i18n.t("realtime_record.stop_recording")
                )
            else:
                record_button.setText(
                    self.i18n.t("realtime_record.start_recording")
                )

        add_marker_button = self.findChild(QPushButton, "add_marker_button")
        if add_marker_button:
            add_marker_button.setText(
                self.i18n.t("realtime_record.add_marker")
            )

        duration_label = self.findChild(QLabel, "duration_label")
        if duration_label:
            duration_label.setText(
                self.i18n.t("realtime_record.recording_duration") + ":"
            )

        # 转录组
        transcription_group = self.findChild(QGroupBox, "transcription_group")
        if transcription_group:
            transcription_group.setTitle(
                self.i18n.t("realtime_record.transcription_text")
            )

        # 翻译组
        translation_group = self.findChild(QGroupBox, "translation_group")
        if translation_group:
            translation_group.setTitle(
                self.i18n.t("realtime_record.translation_text")
            )

        markers_group = self.findChild(QGroupBox, "markers_group")
        if markers_group:
            markers_group.setTitle(
                self.i18n.t("realtime_record.markers")
            )

        if hasattr(self, 'markers_list') and hasattr(self.markers_list, 'setPlaceholderText'):
            self.markers_list.setPlaceholderText(
                self.i18n.t("realtime_record.markers_placeholder")
            )
            self._refresh_markers_list()

        # 如果翻译引擎不可用，显示提示信息
        if not self.recorder.translation_engine and hasattr(self, 'translation_text'):
            self.translation_text.setPlaceholderText(
                self.i18n.t("realtime_record.translation_not_available")
            )

        # 导出按钮
        export_transcription_button = self.findChild(
            QPushButton, "export_transcription_button"
        )
        if export_transcription_button:
            export_transcription_button.setText(
                self.i18n.t("realtime_record.export_transcription")
            )

        export_translation_button = self.findChild(
            QPushButton, "export_translation_button"
        )
        if export_translation_button:
            export_translation_button.setText(
                self.i18n.t("realtime_record.export_translation")
            )

        save_recording_button = self.findChild(
            QPushButton, "save_recording_button"
        )
        if save_recording_button:
            save_recording_button.setText(
                self.i18n.t("realtime_record.save_recording")
            )

        # 更新音频可用性提示
        self._update_audio_availability()

    # Callback methods (called from recorder thread)
    def _on_transcription(self, text: str):
        """转录更新回调（线程安全）"""
        self.signals.transcription_updated.emit(text)

    def _on_translation(self, text: str):
        """翻译更新回调（线程安全）"""
        self.signals.translation_updated.emit(text)

    def _on_error(self, error: str):
        """错误回调（线程安全）"""
        self.signals.error_occurred.emit(error)

    def _on_audio_data(self, audio_chunk):
        """音频数据回调（线程安全，用于可视化）"""
        self.signals.audio_data_available.emit(audio_chunk)

    def _on_marker(self, marker):
        """标记创建回调（线程安全）"""
        self.signals.marker_added.emit(marker)

    # Slot methods (called in UI thread)
    def _update_transcription_display(self, text: str):
        """更新转录文本显示（UI 线程）"""
        try:
            # Add to buffer
            with self._buffer_lock:
                self._transcription_buffer.append(text)
            
            # Update display with all buffered text
            with self._buffer_lock:
                all_text = "\n".join(self._transcription_buffer)
            
            # Use blockSignals to prevent document signals during update
            self.transcription_text.blockSignals(True)
            self.transcription_text.setPlainText(all_text)
            self.transcription_text.blockSignals(False)
            
            # Scroll to bottom
            scrollbar = self.transcription_text.verticalScrollBar()
            if scrollbar:
                scrollbar.setValue(scrollbar.maximum())
            
            logger.debug(f"Transcription updated: {text}")
        except Exception as e:
            logger.error(f"Error updating transcription display: {e}")

    def _update_translation_display(self, text: str):
        """更新翻译文本显示（UI 线程）"""
        try:
            # Add to buffer
            with self._buffer_lock:
                self._translation_buffer.append(text)
            
            # Update display with all buffered text
            with self._buffer_lock:
                all_text = "\n".join(self._translation_buffer)
            
            # Use blockSignals to prevent document signals during update
            self.translation_text.blockSignals(True)
            self.translation_text.setPlainText(all_text)
            self.translation_text.blockSignals(False)
            
            # Scroll to bottom
            scrollbar = self.translation_text.verticalScrollBar()
            if scrollbar:
                scrollbar.setValue(scrollbar.maximum())
            
            logger.debug(f"Translation updated: {text}")
        except Exception as e:
            logger.error(f"Error updating translation display: {e}")

    def _append_marker_item(self, marker):
        """在 UI 中追加标记条目。"""
        if not marker or not hasattr(self, 'markers_list'):
            return

        self._markers.append(marker)
        text = self._format_marker_entry(marker)
        self.markers_list.addItem(text)
        self.markers_list.scrollToBottom()

    def _refresh_markers_list(self):
        """根据当前语言刷新标记显示。"""
        if not hasattr(self, 'markers_list'):
            return

        self.markers_list.blockSignals(True)
        self.markers_list.clear()
        for marker in self._markers:
            self.markers_list.addItem(self._format_marker_entry(marker))
        self.markers_list.blockSignals(False)
        if self._markers:
            self.markers_list.scrollToBottom()

    def _format_marker_entry(self, marker) -> str:
        index = marker.get('index', len(self._markers))
        timestamp = self._format_marker_timestamp(marker.get('offset', 0.0))
        label = marker.get('label') or ""

        if label:
            return self.i18n.t(
                "realtime_record.marker_item_with_label",
                number=index,
                timestamp=timestamp,
                label=label
            )

        return self.i18n.t(
            "realtime_record.marker_item",
            number=index,
            timestamp=timestamp
        )

    @staticmethod
    def _format_marker_timestamp(seconds: float) -> str:
        total_milliseconds = int(round(seconds * 1000))
        hours, remainder = divmod(total_milliseconds, 3_600_000)
        minutes, remainder = divmod(remainder, 60_000)
        seconds_fraction = remainder / 1000.0

        if hours:
            return f"{hours:02d}:{minutes:02d}:{seconds_fraction:06.3f}"
        return f"{minutes:02d}:{seconds_fraction:06.3f}"

    def _show_error(self, error: str):
        """显示错误信息（UI 线程）"""
        logger.error(f"Recording error: {error}")
        # TODO: Show error dialog or status message

    def _update_status_display(self, is_recording: bool, duration: float):
        """更新状态显示（UI 线程）"""
        # 更新录制时长
        hours = int(duration // 3600)
        minutes = int((duration % 3600) // 60)
        seconds = int(duration % 60)
        self.duration_value_label.setText(
            f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        )
    
    def _on_recording_started(self):
        """录制开始时的 UI 更新（主线程）"""
        logger.info("Updating UI for recording started")
        self.record_button.setText(
            self.i18n.t("realtime_record.stop_recording")
        )
        self.record_button.setProperty("recording", True)
        self.record_button.style().unpolish(self.record_button)
        self.record_button.style().polish(self.record_button)
        self.status_timer.start(100)
        if hasattr(self, 'add_marker_button'):
            self.add_marker_button.setEnabled(True)
            self.add_marker_button.setToolTip("")

    def _on_recording_stopped(self):
        """录制停止时的 UI 更新（主线程）"""
        logger.info("Updating UI for recording stopped")
        self.record_button.setText(
            self.i18n.t("realtime_record.start_recording")
        )
        self.record_button.setProperty("recording", False)
        self.record_button.style().unpolish(self.record_button)
        self.record_button.style().polish(self.record_button)
        self.status_timer.stop()
        if hasattr(self, 'add_marker_button'):
            self.add_marker_button.setEnabled(False)

    def _update_status(self):
        """定期更新状态"""
        if not self.recorder.is_recording:
            return

        status = self.recorder.get_recording_status()
        # 正确解包字典并发射信号
        self.signals.status_changed.emit(
            status.get('is_recording', False),
            status.get('duration', 0.0)
        )

    # Event handlers
    def _reset_markers_ui(self):
        """清空标记列表显示。"""
        self._markers.clear()
        if hasattr(self, 'markers_list'):
            self.markers_list.clear()

    def _on_gain_changed(self, value: int):
        """增益滑块变化处理"""
        gain = value / 100.0
        self.gain_value_label.setText(f"{gain:.1f}x")
        if self.audio_capture is not None:
            self.audio_capture.set_gain(gain)
        logger.debug(f"Gain changed to {gain}")

    def _on_translation_toggled(self, state: int):
        """翻译复选框切换处理"""
        enabled = state == Qt.CheckState.Checked.value

        # 只有在翻译引擎可用时才启用目标语言选择
        if self.recorder.translation_engine:
            self.target_lang_combo.setEnabled(enabled)
        else:
            self.target_lang_combo.setEnabled(False)

        logger.debug(f"Translation {'enabled' if enabled else 'disabled'}")

    def _add_marker(self):
        """点击按钮添加标记。"""
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
        """切换录制状态"""
        if not self._audio_available:
            warning = self.i18n.t("realtime_record.audio_unavailable_tooltip")
            logger.warning("Realtime recording unavailable: %s", warning)
            self.signals.error_occurred.emit(warning)
            return

        if not self.recorder.is_recording:
            # 开始录制
            self._run_async_task(self._start_recording())
        else:
            # 停止录制
            self._run_async_task(self._stop_recording())
    
    def _run_async_task(self, coro):
        """在专用事件循环中运行异步任务"""
        import asyncio
        
        if self._async_loop is None:
            logger.error("Async event loop not initialized")
            self.signals.error_occurred.emit("Async event loop not initialized")
            return
        
        # 在专用事件循环中调度任务
        future = asyncio.run_coroutine_threadsafe(coro, self._async_loop)
        
        # 可选：等待结果（但不阻塞 UI 线程）
        def check_result():
            try:
                if future.done():
                    result = future.result()
                    logger.debug(f"Async task completed: {result}")
            except Exception as e:
                logger.error(f"Async task failed: {e}", exc_info=True)
                self.signals.error_occurred.emit(str(e))
        
        # 使用 QTimer 异步检查结果
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(100, check_result)

    async def _start_recording(self):
        """开始录制"""
        try:
            # Check if model is selected (if model_manager is available)
            if self.model_manager and hasattr(self, 'model_combo'):
                selected_model = self.model_combo.currentData()
                if not selected_model:
                    error_msg = self.i18n.t("realtime_record.no_model_selected")
                    logger.error(error_msg)
                    self.signals.error_occurred.emit(error_msg)
                    return
                
                # Verify model is downloaded
                model_info = self.model_manager.get_model(selected_model)
                if not model_info or not model_info.is_downloaded:
                    error_msg = self.i18n.t("realtime_record.model_not_downloaded")
                    logger.error(error_msg)
                    self.signals.error_occurred.emit(error_msg)
                    return
                
                # Mark model as used
                self.model_manager.mark_model_used(selected_model)
                logger.info(f"Using model: {selected_model}")

            # 获取选项
            device_index = self.input_combo.currentData()
            source_lang = self.source_lang_combo.currentData()
            enable_translation = self.enable_translation_checkbox.isChecked()
            target_lang = self.target_lang_combo.currentData()

            options = {
                'language': source_lang,
                'enable_translation': enable_translation,
                'target_language': target_lang,
                'recording_format': 'wav',
                'save_recording': True,
                'save_transcript': True,
                'create_calendar_event': True
            }
            
            # Add model info if available
            if self.model_manager and hasattr(self, 'model_combo'):
                selected_model = self.model_combo.currentData()
                if selected_model:
                    model_info = self.model_manager.get_model(selected_model)
                    if model_info and model_info.is_downloaded:
                        options['model_name'] = selected_model
                        options['model_path'] = model_info.local_path

            # 清空文本显示和缓冲区
            with self._buffer_lock:
                self._transcription_buffer.clear()
                self._translation_buffer.clear()
            self.transcription_text.clear()
            self.translation_text.clear()

            # 清空音频可视化
            self.audio_visualizer.clear()

            # 清空标记
            self._reset_markers_ui()

            # 开始录制（音频数据会通过 on_audio_data 回调自动发送）
            # 传递事件循环引用
            await self.recorder.start_recording(
                input_source=device_index,
                options=options,
                event_loop=self._async_loop
            )

            # 发射信号通知主线程更新 UI
            self.signals.recording_started.emit()

            logger.info("Recording started")

        except Exception as e:
            logger.error(f"Failed to start recording: {e}", exc_info=True)
            self.signals.error_occurred.emit(f"Failed to start recording: {e}")

    async def _stop_recording(self):
        """停止录制"""
        try:
            # 停止录制
            result = await self.recorder.stop_recording()

            # 发射信号通知主线程更新 UI
            self.signals.recording_stopped.emit()

            logger.info(f"Recording stopped: {result}")

            # TODO: Show success notification

        except Exception as e:
            logger.error(f"Failed to stop recording: {e}", exc_info=True)
            self.signals.error_occurred.emit(f"Failed to stop recording: {e}")

    def _export_transcription(self):
        """导出转录文本"""
        from PyQt6.QtWidgets import QFileDialog

        # 获取累积的转录文本
        text = self.recorder.get_accumulated_transcription()

        if not text:
            logger.warning("No transcription text to export")
            return

        # 打开文件保存对话框
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Transcription",
            "",
            "Text Files (*.txt);;Markdown Files (*.md);;All Files (*)"
        )

        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(text)
                logger.info(f"Transcription exported to {file_path}")
            except Exception as e:
                logger.error(f"Failed to export transcription: {e}")
                self._show_error(f"Failed to export: {e}")

    def _export_translation(self):
        """导出翻译文本"""
        from PyQt6.QtWidgets import QFileDialog

        # 获取累积的翻译文本
        text = self.recorder.get_accumulated_translation()

        if not text:
            logger.warning("No translation text to export")
            return

        # 打开文件保存对话框
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Translation",
            "",
            "Text Files (*.txt);;Markdown Files (*.md);;All Files (*)"
        )

        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(text)
                logger.info(f"Translation exported to {file_path}")
            except Exception as e:
                logger.error(f"Failed to export translation: {e}")
                self._show_error(f"Failed to export: {e}")

    def _save_recording(self):
        """保存录音"""
        logger.info("Save recording - handled automatically on stop")
