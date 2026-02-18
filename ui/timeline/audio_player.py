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
Audio player widget for timeline recordings.

Provides playback controls for audio recordings.
"""

import logging
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
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
    create_vbox,
)
from utils.i18n import I18nQtManager

logger = logging.getLogger("echonote.ui.timeline.audio_player")


class AudioPlayer(BaseWidget):
    """
    Audio player widget with playback controls.

    Features:
    - Play/pause control
    - Progress slider with seek
    - Volume control
    - Time display
    - Optional transcript display
    """

    # Signals
    playback_error = Signal(str)  # error_message

    # Constants - avoid hardcoding
    DEFAULT_VOLUME = 70  # Default volume (0-100)
    TRANSCRIPT_AREA_HEIGHT = 220  # Fixed height for transcript area
    CONTROLS_WIDTH = 400  # Total width of control bar
    SIDE_CONTROL_WIDTH = 148  # Width of left/right control areas
    CENTER_CONTROL_WIDTH = 104  # Width of center play button area
    PLAY_BUTTON_SIZE = 56  # Play button size
    CONTROL_BUTTON_SIZE = 40  # Control button size
    VOLUME_SLIDER_WIDTH = 100  # 音量滑块宽度

    # Layout constants - 布局常量
    CONTENT_MARGIN = 20  # 内容区域边距
    CONTENT_SPACING = 8  # 内容区域间距
    CONTROL_BAR_SPACING = 12  # 控制栏间距
    CONTROLS_SPACING = 20  # 控制按钮间距
    INFO_BOTTOM_MARGIN = 16  # 信息区域底部边距
    TRANSCRIPT_BOTTOM_MARGIN = 12  # 转录区域底部边距

    _ERROR_TRANSLATIONS = {
        QMediaPlayer.Error.ResourceError: "timeline.audio_player.errors.resource_error",
        QMediaPlayer.Error.FormatError: "timeline.audio_player.errors.format_error",
        QMediaPlayer.Error.NetworkError: "timeline.audio_player.errors.network_error",
        QMediaPlayer.Error.AccessDeniedError: "timeline.audio_player.errors.access_denied",
    }

    def __init__(
        self,
        file_path: str,
        i18n: I18nQtManager,
        parent: Optional[QWidget] = None,
        *,
        auto_load: bool = True,
    ):
        """
        Initialize audio player.

        Args:
            file_path: Path to audio file
            i18n: Internationalization manager
            parent: Parent widget
            auto_load: Whether to immediately load the audio file.
        """
        super().__init__(i18n, parent)

        self.file_path = file_path
        self.i18n = i18n
        self._initial_time_text = self.i18n.t("timeline.audio_player.initial_time")
        self._playback_state = QMediaPlayer.PlaybackState.StoppedState

        # Media player setup
        self.player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.audio_output.setVolume(self.DEFAULT_VOLUME / 100.0)
        self.player.setAudioOutput(self.audio_output)

        # State
        self.is_seeking = False
        self._media_status = QMediaPlayer.MediaStatus.NoMedia
        self._is_muted = False
        self._transcript_format = None  # 'segments' or 'text'
        self._transcript_segments = None  # 原始segments数据
        self._transcript_view_mode = "formatted"  # 'formatted' or 'plain'

        # Setup UI
        self.setup_ui()

        # React to language updates
        self.i18n.language_changed.connect(self.update_translations)
        self.update_translations()

        # Connect player signals
        self.player.positionChanged.connect(self._on_position_changed)
        self.player.durationChanged.connect(self._on_duration_changed)
        self.player.playbackStateChanged.connect(self._on_state_changed)
        self.player.errorOccurred.connect(self._on_error)
        self.player.mediaStatusChanged.connect(self._on_media_status_changed)

        # Load file when requested so callers can attach error handlers first.
        self._set_controls_enabled(False)
        if auto_load:
            self.load_file(file_path)

        logger.info(f"Audio player initialized: {file_path}")

    def setup_ui(self):
        """Set up the player UI - 简洁居中设计."""
        self.setObjectName("audio_player")
        layout = QVBoxLayout(self)

        # 转录文本显示区域 - 顶部，默认隐藏
        self.transcript_area = self._create_transcript_area()
        layout.addWidget(self.transcript_area)

        # 中间信息区域
        info_container = QWidget()
        info_layout = QVBoxLayout(info_container)
        info_layout.setContentsMargins(
            self.CONTENT_MARGIN,
            self.CONTENT_MARGIN,
            self.CONTENT_MARGIN,
            self.INFO_BOTTOM_MARGIN,
        )
        info_layout.setSpacing(self.CONTENT_SPACING)

        # 文件名标签 - 居中
        file_name = Path(self.file_path).name
        self.file_label = QLabel(file_name)
        self.file_label.setObjectName("player_title")
        self.file_label.setWordWrap(True)
        self.file_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info_layout.addWidget(self.file_label)

        layout.addWidget(info_container)

        # 底部控制栏
        control_bar = self._create_control_bar()
        layout.addWidget(control_bar)

    def _create_transcript_area(self) -> QWidget:
        """创建转录文本显示区域 - 替代封面位置，固定高度避免堆叠."""
        from PySide6.QtWidgets import QTextEdit

        container = QWidget()
        container.setObjectName("transcript_container")
        container.setFixedHeight(self.TRANSCRIPT_AREA_HEIGHT)  # 使用常量，避免硬编码
        layout = QVBoxLayout(container)
        layout.setContentsMargins(
            self.CONTENT_MARGIN,
            self.CONTENT_MARGIN,
            self.CONTENT_MARGIN,
            self.TRANSCRIPT_BOTTOM_MARGIN,
        )
        layout.setSpacing(self.CONTENT_SPACING)

        # 标题
        title = QLabel(self.i18n.t("timeline.audio_player.transcript"))
        title.setObjectName("transcript_title")
        title.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(title)

        # 文本显示区域
        self.transcript_text = QTextEdit()
        self.transcript_text.setObjectName("transcript_text")
        self.transcript_text.setReadOnly(True)
        self.transcript_text.setPlaceholderText(self.i18n.t("timeline.audio_player.no_transcript"))
        layout.addWidget(self.transcript_text)

        # 格式切换按钮（仅在有segments时显示）
        self.format_toggle_button = QPushButton()
        self.format_toggle_button.setObjectName("transcript_format_toggle")
        connect_button_with_callback(self.format_toggle_button, self._toggle_transcript_format)
        self.format_toggle_button.setVisible(False)  # 默认隐藏
        layout.addWidget(self.format_toggle_button)

        # 默认隐藏
        container.setVisible(False)

        return container

    def _create_control_bar(self) -> QWidget:
        """创建控制栏 - 简洁的三列布局."""
        container = QWidget()
        container.setObjectName("player_control_bar")
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(
            self.CONTENT_MARGIN, 0, self.CONTENT_MARGIN, self.CONTENT_MARGIN
        )
        main_layout.setSpacing(self.CONTROL_BAR_SPACING)

        # 进度条区域
        progress_layout = create_vbox(spacing=6)

        self.progress_slider = QSlider(Qt.Orientation.Horizontal)
        self.progress_slider.setObjectName("player_progress")
        self.progress_slider.setRange(0, 0)
        self.progress_slider.setEnabled(False)
        self.progress_slider.sliderPressed.connect(self._on_slider_pressed)
        self.progress_slider.sliderReleased.connect(self._on_slider_released)
        self.progress_slider.sliderMoved.connect(self._on_slider_moved)
        progress_layout.addWidget(self.progress_slider)

        # 时间显示
        time_layout = create_hbox(spacing=0)

        self.current_time_label = QLabel(self._initial_time_text)
        self.current_time_label.setObjectName("player_time")
        time_layout.addWidget(self.current_time_label)

        time_layout.addStretch()

        self.total_time_label = QLabel(self._initial_time_text)
        self.total_time_label.setObjectName("player_time")
        time_layout.addWidget(self.total_time_label)

        progress_layout.addLayout(time_layout)
        main_layout.addLayout(progress_layout)

        # 控制按钮行 - 简单的三列布局，垂直居中对齐
        controls_layout = create_hbox()
        controls_layout.setSpacing(self.CONTROLS_SPACING)
        controls_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        # 左侧：音量控制
        self.volume_button = create_button("🔊")
        self.volume_button.setObjectName("player_control_button")
        self.volume_button.setFixedSize(self.CONTROL_BUTTON_SIZE, self.CONTROL_BUTTON_SIZE)
        connect_button_with_callback(self.volume_button, self._toggle_mute)
        controls_layout.addWidget(self.volume_button, alignment=Qt.AlignmentFlag.AlignVCenter)

        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setObjectName("player_volume")
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(self.DEFAULT_VOLUME)
        self.volume_slider.setFixedWidth(self.VOLUME_SLIDER_WIDTH)
        self.volume_slider.valueChanged.connect(self._on_volume_changed)
        controls_layout.addWidget(self.volume_slider, alignment=Qt.AlignmentFlag.AlignVCenter)

        # 弹性空间
        controls_layout.addStretch()

        # 中间：播放按钮
        self.play_button = create_button("▶")
        self.play_button.setObjectName("player_play_button")
        self.play_button.setFixedSize(self.PLAY_BUTTON_SIZE, self.PLAY_BUTTON_SIZE)
        connect_button_with_callback(self.play_button, self.toggle_playback)
        controls_layout.addWidget(self.play_button, alignment=Qt.AlignmentFlag.AlignVCenter)

        # 弹性空间
        controls_layout.addStretch()

        # 右侧：转录按钮
        self.show_transcript_button = create_button("📝")
        self.show_transcript_button.setObjectName("player_control_button")
        self.show_transcript_button.setFixedSize(self.CONTROL_BUTTON_SIZE, self.CONTROL_BUTTON_SIZE)
        self.show_transcript_button.setCheckable(True)
        connect_button_with_callback(
            self.show_transcript_button, self._toggle_transcript_visibility
        )
        controls_layout.addWidget(
            self.show_transcript_button, alignment=Qt.AlignmentFlag.AlignVCenter
        )

        main_layout.addLayout(controls_layout)

        return container

    def _toggle_transcript_visibility(self):
        """切换转录区域的显示/隐藏."""
        is_visible = self.transcript_area.isVisible()
        new_visible = not is_visible

        self.transcript_area.setVisible(new_visible)
        self.show_transcript_button.setChecked(new_visible)

        # 更新格式切换按钮的可见性（仅在有segments格式时显示）
        if new_visible and self._transcript_format == "segments":
            self.format_toggle_button.setVisible(True)
        else:
            self.format_toggle_button.setVisible(False)

        # 动态调整对话框高度
        if self.parent() and isinstance(self.parent(), QDialog):
            dialog = self.parent()
            if not is_visible:
                # 展开转录文本 - 增加高度
                new_height = dialog.height() + self.TRANSCRIPT_AREA_HEIGHT
                dialog.resize(dialog.width(), new_height)
            else:
                # 收起转录文本 - 减少高度
                new_height = max(
                    AudioPlayerDialog.MIN_DIALOG_HEIGHT,
                    dialog.height() - self.TRANSCRIPT_AREA_HEIGHT,
                )
                dialog.resize(dialog.width(), new_height)

    def load_file(self, file_path: str):
        """
        Load audio file and associated transcript.

        Args:
            file_path: Path to audio file
        """
        try:
            # Check if file exists
            resolved_path = Path(file_path).expanduser().resolve(strict=True)

            # Reset previous state before loading new source
            self.player.stop()
            self._reset_playback_state(reset_total=True)
            self._set_controls_enabled(False)

            # Update label with resolved path
            self.file_path = str(resolved_path)
            self.file_label.setText(resolved_path.name)

            # Load file
            url = QUrl.fromLocalFile(self.file_path)
            self.player.setSource(url)

            # Load transcript if available
            self._load_transcript(resolved_path)

            logger.info(f"Audio file loaded: {file_path}")

        except Exception as e:
            self._emit_playback_error("timeline.audio_player.load_failed", error=str(e))

    def _load_transcript(self, audio_path: Path):
        """
        Load transcript file associated with audio file.

        Supports multiple formats:
        - JSON format with segments (timestamped subtitles)
        - Plain text format (.txt)

        Args:
            audio_path: Path to audio file
        """
        # Try JSON format first (with segments/timestamps)
        json_path = audio_path.with_suffix(".json")
        txt_path = audio_path.with_suffix(".txt")

        transcript_content = None
        transcript_format = None

        # Try JSON format (segments with timestamps)
        if json_path.exists():
            try:
                import json

                with open(json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                if "segments" in data and isinstance(data["segments"], list):
                    # Format: JSON with segments (timestamped)
                    transcript_content = self._format_segments_transcript(data["segments"])
                    transcript_format = "segments"
                    logger.info(f"Transcript loaded (segments): {json_path}")
                elif isinstance(data, dict) and "text" in data:
                    # Format: JSON with plain text
                    transcript_content = data["text"]
                    transcript_format = "text"
                    logger.info(f"Transcript loaded (text): {json_path}")
                else:
                    logger.warning(f"Unknown JSON format in: {json_path}")
            except Exception as e:
                logger.warning(f"Failed to load JSON transcript: {e}")

        # Try plain text format if JSON not found or failed
        if transcript_content is None and txt_path.exists():
            try:
                with open(txt_path, "r", encoding="utf-8") as f:
                    transcript_content = f.read()

                if transcript_content.strip():
                    transcript_format = "text"
                    logger.info(f"Transcript loaded (text): {txt_path}")
            except Exception as e:
                logger.warning(f"Failed to load text transcript: {e}")

        # Update UI
        if transcript_content and transcript_content.strip():
            self.transcript_text.setPlainText(transcript_content)
            self._transcript_format = transcript_format
            # 格式切换按钮在转录区域显示时才可见
            # 不自动显示转录区域，让用户点击按钮显示
        else:
            self.transcript_text.clear()
            self._transcript_format = None
            self._transcript_segments = None
            if hasattr(self, "format_toggle_button"):
                self.format_toggle_button.setVisible(False)
            logger.debug(f"No transcript found for: {audio_path}")

    def _format_segments_transcript(self, segments: list) -> str:
        """
        Format segments with timestamps into readable text.

        Args:
            segments: List of segment dictionaries with 'start', 'end', 'text'

        Returns:
            Formatted transcript string
        """
        # 保存原始segments数据
        self._transcript_segments = segments

        # 格式切换按钮在转录区域显示时才可见，这里只设置文本
        if hasattr(self, "format_toggle_button"):
            self.format_toggle_button.setText(
                "📄 " + self.i18n.t("timeline.audio_player.hide_timestamps")
            )

        lines = []
        for i, segment in enumerate(segments, 1):
            start = segment.get("start", 0)
            end = segment.get("end", 0)
            text = segment.get("text", "").strip()

            if text:
                # Format: [00:00 - 00:05] Text content
                start_time = self._format_timestamp(start)
                end_time = self._format_timestamp(end)
                lines.append(f"[{start_time} - {end_time}] {text}")

        return "\n".join(lines)

    def _toggle_transcript_format(self):
        """切换转录文本显示格式（带时间戳 vs 纯文本）."""
        if self._transcript_format != "segments" or not self._transcript_segments:
            return

        # 切换显示模式
        if self._transcript_view_mode == "formatted":
            # 切换到纯文本模式
            plain_text = " ".join(
                segment.get("text", "").strip() for segment in self._transcript_segments
            )
            self.transcript_text.setPlainText(plain_text)
            self._transcript_view_mode = "plain"
            self.format_toggle_button.setText(
                "📝 " + self.i18n.t("timeline.audio_player.show_timestamps")
            )
        else:
            # 切换回带时间戳模式
            formatted_text = self._format_segments_transcript(self._transcript_segments)
            self.transcript_text.setPlainText(formatted_text)
            self._transcript_view_mode = "formatted"
            self.format_toggle_button.setText(
                "📄 " + self.i18n.t("timeline.audio_player.hide_timestamps")
            )

    def _format_timestamp(self, seconds: float) -> str:
        """
        Format seconds to MM:SS or HH:MM:SS.

        Args:
            seconds: Time in seconds

        Returns:
            Formatted timestamp string
        """
        total_seconds = int(seconds)
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        secs = total_seconds % 60

        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        else:
            return f"{minutes:02d}:{secs:02d}"

    def toggle_playback(self):
        """Toggle play/pause."""
        if not self.play_button.isEnabled():
            return

        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def _on_position_changed(self, position: int):
        """
        Handle playback position change.

        Args:
            position: Current position in milliseconds
        """
        if not self.is_seeking:
            self.progress_slider.setValue(position)
            self.current_time_label.setText(self._format_time(position))

    def _on_duration_changed(self, duration: int):
        """
        Handle duration change.

        Args:
            duration: Total duration in milliseconds
        """
        self.progress_slider.setRange(0, duration)
        self.total_time_label.setText(self._format_time(duration))
        if duration > 0:
            self._set_controls_enabled(True)

    def _on_state_changed(self, state: QMediaPlayer.PlaybackState):
        """
        Handle playback state change.

        Args:
            state: New playback state
        """
        self._playback_state = state

        if state == QMediaPlayer.PlaybackState.StoppedState:
            self._reset_playback_state()

        self.update_translations()

    def _on_error(self, error: QMediaPlayer.Error, error_string: str):
        """
        Handle playback error.

        Args:
            error: Error code
            error_string: Error description
        """
        try:
            error_enum = QMediaPlayer.Error(error)
        except ValueError:
            error_enum = error

        error_detail = error_string or getattr(error_enum, "name", str(error_enum))
        translation_key = self._ERROR_TRANSLATIONS.get(error_enum)

        if translation_key:
            self._emit_playback_error(translation_key, details=error_detail)
        else:
            self._emit_playback_error("timeline.audio_player.playback_error", error=error_detail)
        self._set_controls_enabled(False)

    def _on_slider_pressed(self):
        """Handle slider press (start seeking)."""
        self.is_seeking = True

    def _on_slider_released(self):
        """Handle slider release (end seeking)."""
        self.is_seeking = False
        position = self.progress_slider.value()
        self.player.setPosition(position)

    def _on_slider_moved(self, position: int):
        """
        Handle slider move during seeking.

        Args:
            position: Slider position
        """
        self.current_time_label.setText(self._format_time(position))

    def _toggle_mute(self):
        """切换静音状态."""
        self._is_muted = not self._is_muted

        if self._is_muted:
            self.audio_output.setVolume(0.0)
            self.volume_button.setText(self.i18n.t("ui_strings.timeline.audio_player.mute_icon"))
            self.volume_slider.setEnabled(False)
        else:
            volume = self.volume_slider.value() / 100.0
            self.audio_output.setVolume(volume)
            self.volume_button.setText(
                self.i18n.t("ui_strings.timeline.audio_player.high_volume_icon")
            )
            self.volume_slider.setEnabled(True)

    def _on_volume_changed(self, value: int):
        """
        Handle volume change.

        Args:
            value: Volume value (0-100)
        """
        if not self._is_muted:
            volume = value / 100.0
            self.audio_output.setVolume(volume)

            # 根据音量更新图标
            if value == 0:
                self.volume_button.setText(
                    self.i18n.t("ui_strings.timeline.audio_player.mute_icon")
                )
            elif value < 50:
                self.volume_button.setText(
                    self.i18n.t("ui_strings.timeline.audio_player.low_volume_icon")
                )
            else:
                self.volume_button.setText(
                    self.i18n.t("ui_strings.timeline.audio_player.high_volume_icon")
                )

    def _format_time(self, milliseconds: int) -> str:
        """
        Format time in milliseconds to MM:SS.

        Args:
            milliseconds: Time in milliseconds

        Returns:
            Formatted time string
        """
        seconds = milliseconds // 1000
        minutes = seconds // 60
        seconds = seconds % 60
        return f"{minutes:02d}:{seconds:02d}"

    def _reset_playback_state(self, *, reset_total: bool = False):
        """Reset slider and current time label to the beginning of the media."""
        self.is_seeking = False
        self.progress_slider.blockSignals(True)
        self.progress_slider.setValue(0)
        self.progress_slider.blockSignals(False)
        self.current_time_label.setText(self._initial_time_text)
        if reset_total or self.progress_slider.maximum() == 0:
            self.total_time_label.setText(self._initial_time_text)

    def _set_controls_enabled(self, enabled: bool) -> None:
        """Enable or disable interactive controls based on media readiness."""
        self.play_button.setEnabled(enabled)
        self.progress_slider.setEnabled(enabled)
        self.volume_slider.setEnabled(enabled)

    def update_translations(self):
        """Refresh translated text and tooltips when the language changes."""
        self._initial_time_text = self.i18n.t("timeline.audio_player.initial_time")

        if self.progress_slider.value() == 0:
            self.current_time_label.setText(self._initial_time_text)
        if self.progress_slider.maximum() == 0:
            self.total_time_label.setText(self._initial_time_text)

        # 更新播放按钮图标和提示
        if self._playback_state == QMediaPlayer.PlaybackState.PlayingState:
            self.play_button.setText(self.i18n.t("ui_strings.timeline.audio_player.pause_icon"))
            button_tooltip = self.i18n.t("timeline.audio_player.pause_tooltip")
        else:
            self.play_button.setText(self.i18n.t("ui_strings.timeline.audio_player.play_icon"))
            button_tooltip = self.i18n.t("timeline.audio_player.play_tooltip")

        self.play_button.setToolTip(button_tooltip)
        self.volume_slider.setToolTip(self.i18n.t("timeline.audio_player.volume_tooltip"))
        self.progress_slider.setToolTip(self.i18n.t("timeline.audio_player.progress_tooltip"))

    def _emit_playback_error(self, translation_key: str, **context):
        """Emit a localized playback error message."""
        error_msg = self.i18n.t(translation_key, **context)
        logger.error(error_msg)
        self.playback_error.emit(error_msg)

    def _on_media_status_changed(self, status: QMediaPlayer.MediaStatus):
        """React to media status updates to keep UI state in sync."""
        self._media_status = status

        if status == QMediaPlayer.MediaStatus.LoadedMedia:
            self._set_controls_enabled(True)
            # Ensure duration labels refresh when metadata arrives late
            self._on_duration_changed(self.player.duration())
        elif status in (
            QMediaPlayer.MediaStatus.NoMedia,
            QMediaPlayer.MediaStatus.LoadingMedia,
        ):
            # Keep controls disabled until we know media is playable
            if self.player.duration() == 0:
                self._set_controls_enabled(False)
        elif status == QMediaPlayer.MediaStatus.InvalidMedia:
            self._emit_playback_error(
                "timeline.audio_player.playback_error",
                error=self.i18n.t("timeline.audio_player.invalid_media"),
            )
            self.player.stop()
            self._playback_state = QMediaPlayer.PlaybackState.StoppedState
            self._reset_playback_state(reset_total=True)
            self.update_translations()
            self._set_controls_enabled(False)
        elif status == QMediaPlayer.MediaStatus.EndOfMedia:
            # Align UI with stopped state when playback naturally ends
            self._reset_playback_state()

    def cleanup(self):
        """Clean up resources."""
        self.player.stop()
        self.player.setSource(QUrl())
        try:
            self.i18n.language_changed.disconnect(self.update_translations)
        except (TypeError, RuntimeError):
            pass
        logger.debug("Audio player cleaned up")


class AudioPlayerDialog(QDialog):
    """Dialog wrapper for audio player."""

    # Constants - 避免硬编码
    MIN_DIALOG_WIDTH = 500  # 对话框最小宽度
    MIN_DIALOG_HEIGHT = 180  # 对话框最小高度（不含转录区域）
    DIALOG_MARGIN = 20  # 对话框边距
    DIALOG_SPACING = 16  # 对话框内部间距

    def __init__(self, file_path: str, i18n: I18nQtManager, parent: Optional[QWidget] = None):
        """
        Initialize audio player dialog.

        Args:
            file_path: Path to audio file
            i18n: Internationalization manager
            parent: Parent widget
        """
        super().__init__(parent)

        self.i18n = i18n

        # Setup dialog
        self.setObjectName("audio_player_dialog")
        self.setWindowTitle(i18n.t("timeline.audio_player_title"))
        self.setMinimumWidth(self.MIN_DIALOG_WIDTH)
        self.setMinimumHeight(self.MIN_DIALOG_HEIGHT)
        self.setWindowModality(Qt.WindowModality.NonModal)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)

        # Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            self.DIALOG_MARGIN, self.DIALOG_MARGIN, self.DIALOG_MARGIN, self.DIALOG_MARGIN
        )
        layout.setSpacing(self.DIALOG_SPACING)

        # Audio player
        self.player = AudioPlayer(
            file_path,
            i18n,
            self,
            auto_load=False,
        )
        self.player.playback_error.connect(self._on_playback_error)
        layout.addWidget(self.player)

        # Explicitly load after signals are connected so initialization errors propagate.
        self.player.load_file(file_path)

        self.i18n.language_changed.connect(self.update_translations)
        self.update_translations()

        logger.info(self.i18n.t("logging.timeline.audio_player_dialog_initialized"))

    def _on_playback_error(self, error_msg: str):
        """
        Handle playback error.

        Args:
            error_msg: Error message
        """
        QMessageBox.critical(
            self,
            self.i18n.t("common.error"),
            self.i18n.t("timeline.audio_player.dialog_error_body", message=error_msg),
        )

    def closeEvent(self, event):
        """Handle dialog close."""
        self.player.cleanup()
        super().closeEvent(event)

    def update_translations(self):
        """Refresh dialog-level translations when the language changes."""
        self.setWindowTitle(self.i18n.t("timeline.audio_player_title"))
        self.player.update_translations()
