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

from core.qt_imports import (
    QAudioOutput,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMediaPlayer,
    QMessageBox,
    QPushButton,
    QSlider,
    QSize,
    QStyle,
    QTextEdit,
    Qt,
    QUrl,
    QVBoxLayout,
    QWidget,
    Signal,
)

from ui.base_widgets import (
    BaseWidget,
    connect_button_with_callback,
    create_button,
    create_hbox,
    create_vbox,
)
from ui.constants import (
    AUDIO_PLAYER_CONTENT_MARGIN,
    AUDIO_PLAYER_CONTENT_SPACING,
    AUDIO_PLAYER_CONTROLS_SPACING,
    AUDIO_PLAYER_CONTROL_BAR_SPACING,
    AUDIO_PLAYER_CONTROL_BUTTON_SIZE,
    AUDIO_PLAYER_CONTROL_ICON_SIZE,
    AUDIO_PLAYER_DIALOG_MARGIN,
    AUDIO_PLAYER_DIALOG_MIN_HEIGHT,
    AUDIO_PLAYER_DIALOG_MIN_WIDTH,
    AUDIO_PLAYER_DIALOG_SPACING,
    AUDIO_PLAYER_INFO_BOTTOM_MARGIN,
    AUDIO_PLAYER_PLAY_BUTTON_SIZE,
    AUDIO_PLAYER_PLAY_ICON_SIZE,
    AUDIO_PLAYER_TRANSCRIPT_AREA_HEIGHT,
    AUDIO_PLAYER_TRANSCRIPT_BOTTOM_MARGIN,
    AUDIO_PLAYER_VOLUME_SLIDER_WIDTH,
    ROLE_AUDIO_PLAYER_CONTROL,
    ROLE_AUDIO_PLAYER_PRIMARY,
    ROLE_AUDIO_PLAYER_PROGRESS,
    ROLE_AUDIO_PLAYER_TIME,
    ROLE_AUDIO_PLAYER_TRANSCRIPT_TEXT,
    ROLE_AUDIO_PLAYER_TRANSCRIPT_TITLE,
    ROLE_AUDIO_PLAYER_TRANSCRIPT_TOGGLE,
    ROLE_AUDIO_PLAYER_VOLUME,
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
        transcript_path: Optional[str] = None,
    ):
        """
        Initialize audio player.

        Args:
            file_path: Path to audio file
            i18n: Internationalization manager
            parent: Parent widget
            auto_load: Whether to immediately load the audio file.
            transcript_path: Optional explicit path to the transcript file
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
            self.load_file(file_path, transcript_path)

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
            AUDIO_PLAYER_CONTENT_MARGIN,
            AUDIO_PLAYER_CONTENT_MARGIN,
            AUDIO_PLAYER_CONTENT_MARGIN,
            AUDIO_PLAYER_INFO_BOTTOM_MARGIN,
        )
        info_layout.setSpacing(AUDIO_PLAYER_CONTENT_SPACING)

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

        container = QWidget()
        container.setObjectName("transcript_container")
        container.setFixedHeight(AUDIO_PLAYER_TRANSCRIPT_AREA_HEIGHT)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(
            AUDIO_PLAYER_CONTENT_MARGIN,
            AUDIO_PLAYER_CONTENT_MARGIN,
            AUDIO_PLAYER_CONTENT_MARGIN,
            AUDIO_PLAYER_TRANSCRIPT_BOTTOM_MARGIN,
        )
        layout.setSpacing(AUDIO_PLAYER_CONTENT_SPACING)

        # 标题
        self.transcript_title_label = QLabel(self.i18n.t("timeline.audio_player.transcript"))
        self.transcript_title_label.setObjectName("transcript_title")
        self.transcript_title_label.setProperty("role", ROLE_AUDIO_PLAYER_TRANSCRIPT_TITLE)
        self.transcript_title_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.transcript_title_label)

        # 文本显示区域
        self.transcript_text = QTextEdit()
        self.transcript_text.setObjectName("transcript_text")
        self.transcript_text.setProperty("role", ROLE_AUDIO_PLAYER_TRANSCRIPT_TEXT)
        self.transcript_text.setReadOnly(True)
        self.transcript_text.setPlaceholderText(self.i18n.t("timeline.audio_player.no_transcript"))
        layout.addWidget(self.transcript_text)

        # 格式切换按钮（仅在有segments时显示）
        self.format_toggle_button = QPushButton()
        self.format_toggle_button.setObjectName("transcript_format_toggle")
        self.format_toggle_button.setProperty("role", ROLE_AUDIO_PLAYER_TRANSCRIPT_TOGGLE)
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
            AUDIO_PLAYER_CONTENT_MARGIN,
            0,
            AUDIO_PLAYER_CONTENT_MARGIN,
            AUDIO_PLAYER_CONTENT_MARGIN,
        )
        main_layout.setSpacing(AUDIO_PLAYER_CONTROL_BAR_SPACING)

        # 进度条区域
        progress_layout = create_vbox(spacing=AUDIO_PLAYER_CONTENT_SPACING)

        self.progress_slider = QSlider(Qt.Orientation.Horizontal)
        self.progress_slider.setProperty("role", ROLE_AUDIO_PLAYER_PROGRESS)
        self.progress_slider.setRange(0, 0)
        self.progress_slider.setEnabled(False)
        self.progress_slider.sliderPressed.connect(self._on_slider_pressed)
        self.progress_slider.sliderReleased.connect(self._on_slider_released)
        self.progress_slider.sliderMoved.connect(self._on_slider_moved)
        progress_layout.addWidget(self.progress_slider)

        # 时间显示
        time_layout = create_hbox(spacing=0)

        self.current_time_label = QLabel(self._initial_time_text)
        self.current_time_label.setProperty("role", ROLE_AUDIO_PLAYER_TIME)
        time_layout.addWidget(self.current_time_label)

        time_layout.addStretch()

        self.total_time_label = QLabel(self._initial_time_text)
        self.total_time_label.setProperty("role", ROLE_AUDIO_PLAYER_TIME)
        time_layout.addWidget(self.total_time_label)

        progress_layout.addLayout(time_layout)
        main_layout.addLayout(progress_layout)

        # 控制按钮行 - 简单的三列布局，垂直居中对齐
        controls_layout = create_hbox()
        controls_layout.setSpacing(AUDIO_PLAYER_CONTROLS_SPACING)
        controls_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        # 左侧：音量控制
        self.volume_button = self._create_icon_button(
            self._toggle_mute,
            role_name=ROLE_AUDIO_PLAYER_CONTROL,
            is_primary=False,
        )
        controls_layout.addWidget(self.volume_button, alignment=Qt.AlignmentFlag.AlignVCenter)

        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setProperty("role", ROLE_AUDIO_PLAYER_VOLUME)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(self.DEFAULT_VOLUME)
        self.volume_slider.setFixedWidth(AUDIO_PLAYER_VOLUME_SLIDER_WIDTH)
        self.volume_slider.valueChanged.connect(self._on_volume_changed)
        controls_layout.addWidget(self.volume_slider, alignment=Qt.AlignmentFlag.AlignVCenter)

        # 弹性空间
        controls_layout.addStretch()

        # 中间：播放按钮
        self.play_button = self._create_icon_button(
            self.toggle_playback,
            role_name=ROLE_AUDIO_PLAYER_PRIMARY,
            is_primary=True,
        )
        controls_layout.addWidget(self.play_button, alignment=Qt.AlignmentFlag.AlignVCenter)
        self.stop_button = self._create_icon_button(
            self.stop_playback,
            role_name=ROLE_AUDIO_PLAYER_CONTROL,
            is_primary=False,
        )
        controls_layout.addWidget(self.stop_button, alignment=Qt.AlignmentFlag.AlignVCenter)

        # 弹性空间
        controls_layout.addStretch()

        # 右侧：转录按钮
        self.show_transcript_button = self._create_icon_button(
            self._toggle_transcript_visibility,
            role_name=ROLE_AUDIO_PLAYER_CONTROL,
            is_primary=False,
            checkable=True,
        )
        controls_layout.addWidget(
            self.show_transcript_button, alignment=Qt.AlignmentFlag.AlignVCenter
        )

        main_layout.addLayout(controls_layout)

        return container

    def _create_icon_button(
        self,
        callback,
        *,
        role_name: str,
        is_primary: bool,
        checkable: bool = False,
    ) -> QPushButton:
        """Create a flat icon-only media button with unified size and behavior."""
        button = create_button("")
        button.setProperty("role", role_name)
        size = AUDIO_PLAYER_PLAY_BUTTON_SIZE if is_primary else AUDIO_PLAYER_CONTROL_BUTTON_SIZE
        button.setFixedSize(size, size)
        button.setCheckable(checkable)
        connect_button_with_callback(button, callback)
        return button

    def _set_button_icon(
        self,
        button: QPushButton,
        pixmap: QStyle.StandardPixmap,
        *,
        is_primary: bool,
    ) -> None:
        """Assign a standard Qt media icon with consistent sizing."""
        icon_size = AUDIO_PLAYER_PLAY_ICON_SIZE if is_primary else AUDIO_PLAYER_CONTROL_ICON_SIZE
        button.setIcon(button.style().standardIcon(pixmap))
        button.setIconSize(QSize(icon_size, icon_size))

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
                new_height = dialog.height() + AUDIO_PLAYER_TRANSCRIPT_AREA_HEIGHT
                dialog.resize(dialog.width(), new_height)
            else:
                # 收起转录文本 - 减少高度
                new_height = max(
                    AUDIO_PLAYER_DIALOG_MIN_HEIGHT,
                    dialog.height() - AUDIO_PLAYER_TRANSCRIPT_AREA_HEIGHT,
                )
                dialog.resize(dialog.width(), new_height)

    def load_file(self, file_path: str, transcript_path: Optional[str] = None):
        """
        Load audio file and associated transcript.

        Args:
            file_path: Path to audio file
            transcript_path: Optional explicit path to the transcript file
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
            self._load_transcript(resolved_path, transcript_path)

            logger.info(f"Audio file loaded: {file_path}")

        except Exception as e:
            self._emit_playback_error("timeline.audio_player.load_failed", error=str(e))

    def _load_transcript(self, audio_path: Path, transcript_path: Optional[str] = None):
        """
        Load transcript file associated with audio file.

        Supports multiple formats:
        - JSON format with segments (timestamped subtitles)
        - Plain text format (.txt)

        Args:
            audio_path: Path to audio file
            transcript_path: Optional explicit path to the transcript file
        """
        transcript_content = None
        transcript_format = None

        # Helper function to attempt loading a JSON transcript
        def load_json(path: Path) -> bool:
            nonlocal transcript_content, transcript_format
            if path.exists():
                try:
                    import json

                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)

                    if "segments" in data and isinstance(data["segments"], list):
                        transcript_format = "segments"
                        transcript_content = self._format_segments_transcript(data["segments"])
                        logger.info(f"Transcript loaded (segments): {path}")
                        return True
                    elif isinstance(data, dict) and "text" in data:
                        transcript_content = data["text"]
                        transcript_format = "text"
                        logger.info(f"Transcript loaded (text): {path}")
                        return True
                    else:
                        logger.warning(f"Unknown JSON format in: {path}")
                except Exception as e:
                    logger.warning(f"Failed to load JSON transcript at {path}: {e}")
            return False

        # Helper function to attempt loading a text transcript
        def load_text(path: Path) -> bool:
            nonlocal transcript_content, transcript_format
            if path.exists():
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        content = f.read()
                    if content.strip():
                        transcript_content = content
                        transcript_format = "text"
                        logger.info(f"Transcript loaded (text): {path}")
                        return True
                except Exception as e:
                    logger.warning(f"Failed to load text transcript at {path}: {e}")
            return False

        # Try explicitly provided transcript path first
        if transcript_path:
            explicit_path = Path(transcript_path).expanduser().resolve()
            if explicit_path.suffix.lower() == ".json":
                if load_json(explicit_path):
                    pass
                elif load_text(explicit_path):  # Fallback just in case text masquerades as json
                    pass
            else:
                if load_text(explicit_path):
                    pass
                elif load_json(explicit_path):  # Fallback
                    pass

        # If not found yet, try guessing based on audio path
        if transcript_content is None:
            json_path = audio_path.with_suffix(".json")
            load_json(json_path)

        if transcript_content is None:
            txt_path = audio_path.with_suffix(".txt")
            load_text(txt_path)

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
        self._transcript_view_mode = "formatted"

        # 格式切换按钮在转录区域显示时才可见，这里只设置文本
        if hasattr(self, "format_toggle_button"):
            self._refresh_format_toggle_text()

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
            self._refresh_format_toggle_text()
        else:
            # 切换回带时间戳模式
            formatted_text = self._format_segments_transcript(self._transcript_segments)
            self.transcript_text.setPlainText(formatted_text)
            self._transcript_view_mode = "formatted"
            self._refresh_format_toggle_text()

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

    def stop_playback(self):
        """Stop playback and reset timeline position."""
        if not self.stop_button.isEnabled():
            return
        self.player.stop()

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
            self.volume_slider.setEnabled(False)
        else:
            volume = self.volume_slider.value() / 100.0
            self.audio_output.setVolume(volume)
            self.volume_slider.setEnabled(True)
        self._update_volume_button_icon()

    def _on_volume_changed(self, value: int):
        """
        Handle volume change.

        Args:
            value: Volume value (0-100)
        """
        if not self._is_muted:
            volume = value / 100.0
            self.audio_output.setVolume(volume)
        self._update_volume_button_icon()

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
        self.stop_button.setEnabled(enabled)
        self.volume_button.setEnabled(enabled)
        self.progress_slider.setEnabled(enabled)
        self.volume_slider.setEnabled(enabled)

    def update_translations(self):
        """Refresh translated text and tooltips when the language changes."""
        self._initial_time_text = self.i18n.t("timeline.audio_player.initial_time")

        if self.progress_slider.value() == 0:
            self.current_time_label.setText(self._initial_time_text)
        if self.progress_slider.maximum() == 0:
            self.total_time_label.setText(self._initial_time_text)

        self.transcript_title_label.setText(self.i18n.t("timeline.audio_player.transcript"))
        self.transcript_text.setPlaceholderText(self.i18n.t("timeline.audio_player.no_transcript"))

        if self._playback_state == QMediaPlayer.PlaybackState.PlayingState:
            self._set_button_icon(
                self.play_button,
                QStyle.StandardPixmap.SP_MediaPause,
                is_primary=True,
            )
            self.play_button.setAccessibleName(
                self.i18n.t("timeline.audio_player.pause_button_label")
            )
            button_tooltip = self.i18n.t("timeline.audio_player.pause_tooltip")
        else:
            self._set_button_icon(
                self.play_button,
                QStyle.StandardPixmap.SP_MediaPlay,
                is_primary=True,
            )
            self.play_button.setAccessibleName(
                self.i18n.t("timeline.audio_player.play_button_label")
            )
            button_tooltip = self.i18n.t("timeline.audio_player.play_tooltip")

        self._set_button_icon(
            self.stop_button,
            QStyle.StandardPixmap.SP_MediaStop,
            is_primary=False,
        )
        self.stop_button.setAccessibleName(self.i18n.t("timeline.audio_player.stop_button_label"))
        self.stop_button.setToolTip(self.i18n.t("timeline.audio_player.stop_tooltip"))
        self._set_button_icon(
            self.show_transcript_button,
            QStyle.StandardPixmap.SP_FileDialogDetailedView,
            is_primary=False,
        )
        self.show_transcript_button.setAccessibleName(
            self.i18n.t("timeline.audio_player.transcript")
        )
        self.show_transcript_button.setToolTip(self.i18n.t("timeline.audio_player.transcript"))
        self.play_button.setToolTip(button_tooltip)
        self._update_volume_button_icon()
        self.volume_slider.setToolTip(self.i18n.t("timeline.audio_player.volume_tooltip"))
        self.progress_slider.setToolTip(self.i18n.t("timeline.audio_player.progress_tooltip"))
        self._refresh_format_toggle_text()

    def _update_volume_button_icon(self) -> None:
        """Update volume icon and accessible text according to current state."""
        volume_value = self.volume_slider.value()
        if self._is_muted or volume_value == 0:
            icon = QStyle.StandardPixmap.SP_MediaVolumeMuted
            accessible_name = self.i18n.t("timeline.audio_player.mute_icon")
        else:
            icon = QStyle.StandardPixmap.SP_MediaVolume
            if volume_value < 50:
                accessible_name = self.i18n.t("timeline.audio_player.low_volume_icon")
            else:
                accessible_name = self.i18n.t("timeline.audio_player.high_volume_icon")

        self._set_button_icon(self.volume_button, icon, is_primary=False)
        self.volume_button.setAccessibleName(accessible_name)
        self.volume_button.setToolTip(self.i18n.t("timeline.audio_player.volume_tooltip"))

    def _refresh_format_toggle_text(self) -> None:
        """Refresh transcript format toggle label for current mode."""
        if self._transcript_format != "segments":
            return

        translation_key = (
            "timeline.audio_player.show_timestamps"
            if self._transcript_view_mode == "plain"
            else "timeline.audio_player.hide_timestamps"
        )
        self.format_toggle_button.setText(self.i18n.t(translation_key))

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

    def __init__(
        self,
        file_path: str,
        i18n: I18nQtManager,
        parent: Optional[QWidget] = None,
        transcript_path: Optional[str] = None,
    ):
        """
        Initialize audio player dialog.

        Args:
            file_path: Path to audio file
            i18n: Internationalization manager
            parent: Parent widget
            transcript_path: Optional explicit path to the transcript file
        """
        super().__init__(parent)

        self.i18n = i18n

        # Setup dialog
        self.setObjectName("audio_player_dialog")
        self.setWindowTitle(i18n.t("timeline.audio_player_title"))
        self.setMinimumWidth(AUDIO_PLAYER_DIALOG_MIN_WIDTH)
        self.setMinimumHeight(AUDIO_PLAYER_DIALOG_MIN_HEIGHT)
        self.setWindowModality(Qt.WindowModality.NonModal)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)

        # Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            AUDIO_PLAYER_DIALOG_MARGIN,
            AUDIO_PLAYER_DIALOG_MARGIN,
            AUDIO_PLAYER_DIALOG_MARGIN,
            AUDIO_PLAYER_DIALOG_MARGIN,
        )
        layout.setSpacing(AUDIO_PLAYER_DIALOG_SPACING)

        # Audio player
        self.player = AudioPlayer(
            file_path,
            i18n,
            self,
            auto_load=False,
            transcript_path=transcript_path,
        )
        self.player.playback_error.connect(self._on_playback_error)
        layout.addWidget(self.player)

        # Explicitly load after signals are connected so initialization errors propagate.
        self.player.load_file(file_path, transcript_path)

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
