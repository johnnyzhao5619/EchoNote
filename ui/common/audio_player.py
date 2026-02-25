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
"""Reusable audio player widget and dialog for recording playback."""

import logging
import weakref
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from core.qt_imports import (
    QButtonGroup,
    QAudioOutput,
    QDialog,
    QFrame,
    QKeySequence,
    QLabel,
    QMediaPlayer,
    QMessageBox,
    QPushButton,
    QShortcut,
    QSizePolicy,
    QSlider,
    QSize,
    QStyle,
    QTextCharFormat,
    QTextCursor,
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
    AUDIO_PLAYER_DIALOG_EXPANDED_MIN_HEIGHT,
    AUDIO_PLAYER_DIALOG_DEFAULT_HEIGHT,
    AUDIO_PLAYER_DIALOG_DEFAULT_WIDTH,
    AUDIO_PLAYER_HEADER_MAX_HEIGHT,
    AUDIO_PLAYER_CONTROL_BAR_MAX_HEIGHT,
    AUDIO_PLAYER_DIALOG_MIN_HEIGHT,
    AUDIO_PLAYER_DIALOG_MIN_WIDTH,
    AUDIO_PLAYER_DIALOG_SPACING,
    AUDIO_PLAYER_PLAY_BUTTON_SIZE,
    AUDIO_PLAYER_PLAY_ICON_SIZE,
    AUDIO_PLAYER_TRANSCRIPT_MIN_HEIGHT,
    AUDIO_PLAYER_TRANSCRIPT_BOTTOM_MARGIN,
    AUDIO_PLAYER_VOLUME_SLIDER_WIDTH,
    ROLE_AUDIO_PLAYER_CONTROL,
    ROLE_AUDIO_PLAYER_DIVIDER,
    ROLE_AUDIO_PLAYER_MODE_ACTION,
    ROLE_AUDIO_PLAYER_MODE_CAPTION,
    ROLE_AUDIO_PLAYER_PRIMARY,
    ROLE_AUDIO_PLAYER_PROGRESS,
    ROLE_AUDIO_PLAYER_SUBTITLE,
    ROLE_AUDIO_PLAYER_SURFACE,
    ROLE_AUDIO_PLAYER_TIME,
    ROLE_AUDIO_PLAYER_TRANSCRIPT_PANEL,
    ROLE_AUDIO_PLAYER_TRANSCRIPT_TEXT,
    ROLE_AUDIO_PLAYER_TITLE,
    ROLE_AUDIO_PLAYER_TRANSCRIPT_TITLE,
    ROLE_AUDIO_PLAYER_TRANSCRIPT_TOGGLE,
    ROLE_AUDIO_PLAYER_VOLUME,
)
from ui.common.theme import ThemeManager
from utils.i18n import I18nQtManager

logger = logging.getLogger("echonote.ui.common.audio_player")


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
    SEEK_STEP_MS = 10_000
    _ACTIVE_PLAYERS: "weakref.WeakSet[AudioPlayer]" = weakref.WeakSet()

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
        translation_path: Optional[str] = None,
    ):
        """
        Initialize audio player.

        Args:
            file_path: Path to audio file
            i18n: Internationalization manager
            parent: Parent widget
            auto_load: Whether to immediately load the audio file.
            transcript_path: Optional explicit path to the transcript file
            translation_path: Optional explicit path to translation file
        """
        super().__init__(i18n, parent)

        self.file_path = file_path
        self.i18n = i18n
        self._full_file_name = Path(file_path).name
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
        self._translation_format = None  # 'segments' or 'text'
        self._translation_segments = None
        self._transcript_plain_text = ""
        self._transcript_formatted_text = ""
        self._translation_text = ""
        self._active_text_mode = "transcript"
        self._segment_timeline: List[Tuple[int, int]] = []
        self._segment_line_map: Dict[int, int] = {}
        self._active_segment_index = -1
        self._mode_buttons: Dict[str, QPushButton] = {}
        self._mode_button_group: Optional[QButtonGroup] = None
        self.info_container: Optional[QWidget] = None
        self.control_bar: Optional[QWidget] = None

        # Setup UI
        self.setup_ui()
        self._setup_shortcuts()
        self._ACTIVE_PLAYERS.add(self)

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
            self.load_file(file_path, transcript_path, translation_path)

        logger.info(f"Audio player initialized: {file_path}")

    def setup_ui(self):
        """Set up the player UI with a clear media-first layout."""
        self.setObjectName("audio_player")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.surface = QWidget()
        self.surface.setProperty("role", ROLE_AUDIO_PLAYER_SURFACE)
        surface_layout = QVBoxLayout(self.surface)
        surface_layout.setContentsMargins(
            AUDIO_PLAYER_CONTENT_MARGIN,
            AUDIO_PLAYER_CONTENT_MARGIN,
            AUDIO_PLAYER_CONTENT_MARGIN,
            AUDIO_PLAYER_CONTENT_MARGIN,
        )
        surface_layout.setSpacing(AUDIO_PLAYER_CONTENT_SPACING * 2)

        self.top_fill = QWidget()
        self.top_fill.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        surface_layout.addWidget(self.top_fill, stretch=1)

        # 主信息 + 控制区域（媒体主轴）
        self.chrome_container = QWidget()
        chrome_layout = QVBoxLayout(self.chrome_container)
        chrome_layout.setContentsMargins(0, 0, 0, 0)
        chrome_layout.setSpacing(AUDIO_PLAYER_CONTENT_SPACING * 2)

        info_container = QWidget()
        self.info_container = info_container
        info_container.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        info_container.setMaximumHeight(AUDIO_PLAYER_HEADER_MAX_HEIGHT)
        info_layout = QVBoxLayout(info_container)
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(2)

        self.now_playing_label = QLabel(self.i18n.t("timeline.audio_player.now_playing"))
        self.now_playing_label.setProperty("role", ROLE_AUDIO_PLAYER_SUBTITLE)
        self.now_playing_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info_layout.addWidget(self.now_playing_label)

        self.file_label = QLabel(self._full_file_name)
        self.file_label.setProperty("role", ROLE_AUDIO_PLAYER_TITLE)
        self.file_label.setWordWrap(False)
        self.file_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.file_label.setToolTip(self._full_file_name)
        info_layout.addWidget(self.file_label)
        self._refresh_file_label()
        chrome_layout.addWidget(info_container)

        # 控制栏
        control_bar = self._create_control_bar()
        self.control_bar = control_bar
        control_bar.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        control_bar.setMaximumHeight(AUDIO_PLAYER_CONTROL_BAR_MAX_HEIGHT)
        chrome_layout.addWidget(control_bar)
        surface_layout.addWidget(self.chrome_container, stretch=0)

        self.bottom_fill = QWidget()
        self.bottom_fill.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        surface_layout.addWidget(self.bottom_fill, stretch=1)

        # 文本面板下沉到底部折叠区，避免顶部信息堆叠
        self.transcript_divider = QFrame()
        self.transcript_divider.setFrameShape(QFrame.Shape.HLine)
        self.transcript_divider.setProperty("role", ROLE_AUDIO_PLAYER_DIVIDER)
        self.transcript_divider.setVisible(False)
        surface_layout.addWidget(self.transcript_divider, stretch=0)

        self.transcript_area = self._create_transcript_area()
        self.transcript_area.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding
        )
        surface_layout.addWidget(self.transcript_area, stretch=1)
        self._apply_layout_mode(show_transcript=False)

        layout.addWidget(self.surface)

    def _create_transcript_area(self) -> QWidget:
        """Create transcript panel with dedicated height and mode controls."""

        container = QWidget()
        container.setProperty("role", ROLE_AUDIO_PLAYER_TRANSCRIPT_PANEL)
        container.setMinimumHeight(AUDIO_PLAYER_TRANSCRIPT_MIN_HEIGHT)
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
        self.transcript_title_label.setProperty("role", ROLE_AUDIO_PLAYER_TRANSCRIPT_TITLE)
        self.transcript_title_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.transcript_title_label)

        mode_layout = create_hbox(spacing=AUDIO_PLAYER_CONTENT_SPACING)
        self.mode_caption_label = QLabel(self.i18n.t("timeline.audio_player.view_mode"))
        self.mode_caption_label.setProperty("role", ROLE_AUDIO_PLAYER_MODE_CAPTION)
        mode_layout.addWidget(self.mode_caption_label)

        self._mode_button_group = QButtonGroup(self)
        self._mode_button_group.setExclusive(True)
        mode_map = (
            ("transcript", "timeline.audio_player.mode_transcript"),
            ("translation", "timeline.audio_player.mode_translation"),
            ("compare", "timeline.audio_player.mode_compare"),
        )
        for mode, text_key in mode_map:
            button = create_button(self.i18n.t(text_key))
            button.setCheckable(True)
            button.setProperty("role", ROLE_AUDIO_PLAYER_MODE_ACTION)
            connect_button_with_callback(
                button,
                lambda _checked=False, selected_mode=mode: self._on_mode_selected(selected_mode),
            )
            self._mode_button_group.addButton(button)
            self._mode_buttons[mode] = button
            mode_layout.addWidget(button)
        mode_layout.addStretch()
        layout.addLayout(mode_layout)

        # 文本显示区域
        self.transcript_text = QTextEdit()
        self.transcript_text.setProperty("role", ROLE_AUDIO_PLAYER_TRANSCRIPT_TEXT)
        self.transcript_text.setReadOnly(True)
        self.transcript_text.setPlaceholderText(self.i18n.t("timeline.audio_player.no_transcript"))
        layout.addWidget(self.transcript_text)

        # 格式切换按钮（仅在有segments时显示）
        self.format_toggle_button = QPushButton()
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
        self.rewind_button = self._create_icon_button(
            self._skip_backward,
            role_name=ROLE_AUDIO_PLAYER_CONTROL,
            is_primary=False,
        )
        controls_layout.addWidget(self.rewind_button, alignment=Qt.AlignmentFlag.AlignVCenter)
        controls_layout.addWidget(self.play_button, alignment=Qt.AlignmentFlag.AlignVCenter)
        self.stop_button = self._create_icon_button(
            self.stop_playback,
            role_name=ROLE_AUDIO_PLAYER_CONTROL,
            is_primary=False,
        )
        controls_layout.addWidget(self.stop_button, alignment=Qt.AlignmentFlag.AlignVCenter)
        self.forward_button = self._create_icon_button(
            self._skip_forward,
            role_name=ROLE_AUDIO_PLAYER_CONTROL,
            is_primary=False,
        )
        controls_layout.addWidget(self.forward_button, alignment=Qt.AlignmentFlag.AlignVCenter)

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

    def _setup_shortcuts(self) -> None:
        """Register keyboard shortcuts for core playback controls."""
        self._play_pause_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Space), self)
        self._play_pause_shortcut.activated.connect(self.toggle_playback)

        self._rewind_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Left), self)
        self._rewind_shortcut.activated.connect(self._skip_backward)

        self._forward_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Right), self)
        self._forward_shortcut.activated.connect(self._skip_forward)

    def _toggle_transcript_visibility(self):
        """切换转录区域的显示/隐藏."""
        is_visible = self.transcript_area.isVisible()
        new_visible = not is_visible

        self._apply_layout_mode(show_transcript=new_visible)
        self._sync_transcript_toggle_tooltip()

        self._update_format_toggle_visibility()
        if new_visible:
            self._ensure_dialog_height_for_transcript()
            self._sync_transcript_with_playback(self.player.position())

    def _apply_layout_mode(self, *, show_transcript: bool) -> None:
        """Apply centered or transcript-priority layout mode."""
        self.top_fill.setVisible(not show_transcript)
        self.bottom_fill.setVisible(not show_transcript)
        self.transcript_divider.setVisible(show_transcript)
        self.transcript_area.setVisible(show_transcript)
        self.show_transcript_button.setChecked(show_transcript)

    def _sync_transcript_toggle_tooltip(self) -> None:
        """Update transcript toggle tooltip based on current panel visibility."""
        is_panel_open = not self.transcript_area.isHidden()
        tooltip_key = (
            "timeline.audio_player.hide_text_panel"
            if is_panel_open
            else "timeline.audio_player.show_text_panel"
        )
        self.show_transcript_button.setToolTip(self.i18n.t(tooltip_key))

    def _ensure_dialog_height_for_transcript(self) -> None:
        """Grow dialog to avoid cramped overlay when transcript panel opens."""
        window = self.window()
        if not isinstance(window, QDialog):
            return

        recommended_height = AUDIO_PLAYER_DIALOG_EXPANDED_MIN_HEIGHT
        if window.height() < recommended_height:
            window.resize(window.width(), recommended_height)

    def _skip_backward(self) -> None:
        """Seek backward by configured step."""
        self._seek_relative(-self.SEEK_STEP_MS)

    def _skip_forward(self) -> None:
        """Seek forward by configured step."""
        self._seek_relative(self.SEEK_STEP_MS)

    def _seek_relative(self, delta_ms: int) -> None:
        """Seek media position by relative milliseconds and clamp to valid bounds."""
        if not self.play_button.isEnabled():
            return

        duration = max(self.player.duration(), self.progress_slider.maximum())
        if duration <= 0:
            return

        current_position = self.player.position()
        if current_position <= 0 and self.progress_slider.maximum() > 0:
            current_position = self.progress_slider.value()
        target = max(0, min(duration, current_position + delta_ms))
        self.player.setPosition(target)
        self.progress_slider.setValue(target)
        self.current_time_label.setText(self._format_time(target))
        self._sync_transcript_with_playback(target)

    def load_file(
        self,
        file_path: str,
        transcript_path: Optional[str] = None,
        translation_path: Optional[str] = None,
    ):
        """
        Load audio file and associated transcript/translation.

        Args:
            file_path: Path to audio file
            transcript_path: Optional explicit path to the transcript file
            translation_path: Optional explicit path to the translation file
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
            self._full_file_name = resolved_path.name
            self.file_label.setToolTip(self._full_file_name)
            self._refresh_file_label()

            # Load file
            url = QUrl.fromLocalFile(self.file_path)
            self.player.setSource(url)

            # Load transcript/translation artifacts if available
            self._load_transcript(resolved_path, transcript_path)
            self._load_translation(resolved_path, translation_path)
            self._refresh_transcript_display()

            logger.info(f"Audio file loaded: {file_path}")

        except Exception as e:
            self._emit_playback_error("timeline.audio_player.load_failed", error=str(e))

    def _resolve_artifact_candidates(
        self,
        audio_path: Path,
        explicit_path: Optional[str],
        *,
        allow_audio_fallback: bool,
    ) -> List[Path]:
        """Build candidate paths with JSON-first preference for timestamped segments."""
        candidates: List[Path] = []
        if explicit_path:
            resolved = Path(explicit_path).expanduser().resolve()
            if resolved.suffix.lower() == ".json":
                candidates.extend([resolved, resolved.with_suffix(".txt")])
            else:
                candidates.extend([resolved.with_suffix(".json"), resolved])

        if allow_audio_fallback:
            candidates.extend([audio_path.with_suffix(".json"), audio_path.with_suffix(".txt")])

        unique: List[Path] = []
        seen: set[str] = set()
        for candidate in candidates:
            normalized = str(candidate)
            if normalized in seen:
                continue
            seen.add(normalized)
            unique.append(candidate)
        return unique

    @staticmethod
    def _segments_to_plain_text(segments: List[dict]) -> str:
        """Flatten segment payload into plain text content."""
        return " ".join(
            str(segment.get("text", "")).strip()
            for segment in segments
            if str(segment.get("text", "")).strip()
        ).strip()

    def _load_text_payload(
        self,
        audio_path: Path,
        explicit_path: Optional[str],
        *,
        label: str,
        allow_audio_fallback: bool,
    ) -> tuple[str, Optional[str], Optional[List[dict]]]:
        """Load text/segments payload from json/txt candidates."""
        for path in self._resolve_artifact_candidates(
            audio_path,
            explicit_path,
            allow_audio_fallback=allow_audio_fallback,
        ):
            if not path.exists():
                continue

            suffix = path.suffix.lower()
            if suffix == ".json":
                try:
                    import json

                    with open(path, "r", encoding="utf-8") as handle:
                        data = json.load(handle)
                except Exception as exc:
                    logger.warning("Failed to load %s JSON at %s: %s", label, path, exc)
                    continue

                if isinstance(data, dict):
                    segments = data.get("segments")
                    if isinstance(segments, list) and segments:
                        text_value = self._segments_to_plain_text(segments)
                        logger.info("%s loaded (segments): %s", label.capitalize(), path)
                        return text_value, "segments", segments

                    text_value = data.get("text")
                    if isinstance(text_value, str) and text_value.strip():
                        logger.info("%s loaded (text-json): %s", label.capitalize(), path)
                        return text_value.strip(), "text", None
                continue

            try:
                content = path.read_text(encoding="utf-8").strip()
            except Exception as exc:
                logger.warning("Failed to load %s text at %s: %s", label, path, exc)
                continue

            if content:
                logger.info("%s loaded (text): %s", label.capitalize(), path)
                return content, "text", None

        return "", None, None

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
        text, transcript_format, segments = self._load_text_payload(
            audio_path,
            transcript_path,
            label="transcript",
            allow_audio_fallback=True,
        )
        self._transcript_format = transcript_format
        self._transcript_segments = segments
        self._transcript_plain_text = text
        self._transcript_formatted_text = (
            self._format_segments_text(segments) if segments else text
        )
        if transcript_format != "segments":
            self._transcript_view_mode = "formatted"

    def _load_translation(self, audio_path: Path, translation_path: Optional[str] = None) -> None:
        """Load translation content associated with the audio file."""
        text, translation_format, segments = self._load_text_payload(
            audio_path,
            translation_path,
            label="translation",
            allow_audio_fallback=False,
        )
        self._translation_format = translation_format
        self._translation_segments = segments
        if translation_format == "segments" and segments:
            self._translation_text = self._format_segments_text(segments)
        else:
            self._translation_text = text

    def _format_segments_text(self, segments: Optional[List[dict]]) -> str:
        """
        Format segments with timestamps into readable text.

        Args:
            segments: List of segment dictionaries with 'start', 'end', 'text'

        Returns:
            Formatted transcript string
        """
        if not segments:
            return ""

        lines = []
        for segment in segments:
            start = segment.get("start", 0)
            end = segment.get("end", 0)
            text = str(segment.get("text", "")).strip()

            if text:
                start_time = self._format_timestamp(start)
                end_time = self._format_timestamp(end)
                lines.append(f"[{start_time} - {end_time}] {text}")

        return "\n".join(lines)

    @staticmethod
    def _segment_to_ms(segment: dict) -> Tuple[int, int]:
        """Convert segment seconds to millisecond bounds."""
        start = int(float(segment.get("start", 0)) * 1000)
        end = int(float(segment.get("end", 0)) * 1000)
        if end <= start:
            end = start + 1
        return start, end

    def _build_display_content(
        self, mode: str
    ) -> tuple[str, List[Tuple[int, int]], Dict[int, int]]:
        """Build display text plus timeline metadata for the selected mode."""
        timeline: List[Tuple[int, int]] = []
        line_map: Dict[int, int] = {}

        if mode == "transcript":
            if (
                self._transcript_format == "segments"
                and self._transcript_segments
                and self._transcript_view_mode == "formatted"
            ):
                lines: List[str] = []
                for segment in self._transcript_segments:
                    text = str(segment.get("text", "")).strip()
                    if not text:
                        continue
                    start, end = self._segment_to_ms(segment)
                    timeline.append((start, end))
                    line_map[len(timeline) - 1] = len(lines)
                    lines.append(
                        f"[{self._format_timestamp(start / 1000)} - {self._format_timestamp(end / 1000)}] {text}"
                    )
                return "\n".join(lines), timeline, line_map
            if self._transcript_view_mode == "plain":
                return self._transcript_plain_text, timeline, line_map
            return self._transcript_formatted_text, timeline, line_map

        if mode == "translation":
            if self._translation_segments:
                lines = []
                for segment in self._translation_segments:
                    text = str(segment.get("text", "")).strip()
                    if not text:
                        continue
                    start, end = self._segment_to_ms(segment)
                    timeline.append((start, end))
                    line_map[len(timeline) - 1] = len(lines)
                    lines.append(
                        f"[{self._format_timestamp(start / 1000)} - {self._format_timestamp(end / 1000)}] {text}"
                    )
                return "\n".join(lines), timeline, line_map
            return self._translation_text, timeline, line_map

        # Compare mode
        transcript_segments = self._transcript_segments or []
        if transcript_segments:
            translation_lines = [
                line.strip() for line in self._translation_text.splitlines() if line.strip()
            ]
            lines = []
            for index, segment in enumerate(transcript_segments):
                source_text = str(segment.get("text", "")).strip()
                if not source_text:
                    continue
                translated_text = (
                    translation_lines[index]
                    if index < len(translation_lines)
                    else (self._translation_text if index == 0 else "")
                )
                start, end = self._segment_to_ms(segment)
                timeline.append((start, end))
                line_map[len(timeline) - 1] = len(lines)
                lines.append(
                    f"[{self._format_timestamp(start / 1000)}] "
                    f"{self.i18n.t('viewer.mode_transcript')}: {source_text}  |  "
                    f"{self.i18n.t('viewer.mode_translation')}: {translated_text}"
                )
            return "\n".join(lines), timeline, line_map

        if self._transcript_formatted_text and self._translation_text:
            return (
                f"{self.i18n.t('viewer.mode_transcript')}:\n{self._transcript_formatted_text}\n\n"
                f"{self.i18n.t('viewer.mode_translation')}:\n{self._translation_text}"
            ), timeline, line_map

        return self._transcript_formatted_text or self._translation_text, timeline, line_map

    def _available_text_modes(self) -> List[str]:
        """Return display modes supported by current artifacts."""
        has_transcript = bool(self._transcript_formatted_text.strip())
        has_translation = bool(self._translation_text.strip())
        modes: List[str] = []
        if has_transcript:
            modes.append("transcript")
        if has_translation:
            modes.append("translation")
        if has_transcript and has_translation:
            modes.append("compare")
        if not modes:
            modes.append("transcript")
        return modes

    def _refresh_mode_buttons(self) -> None:
        """Synchronize mode button availability with loaded artifacts."""
        available = self._available_text_modes()
        show_mode_switch = len(available) > 1
        self.mode_caption_label.setVisible(show_mode_switch)
        if self._active_text_mode not in available:
            self._active_text_mode = available[0]

        for mode, button in self._mode_buttons.items():
            is_available = mode in available
            button.setVisible(show_mode_switch and is_available)
            button.setEnabled(is_available)
            button.setChecked(mode == self._active_text_mode)

    def _refresh_transcript_display(self) -> None:
        """Refresh text area content for current mode and data."""
        self._refresh_mode_buttons()
        text, timeline, line_map = self._build_display_content(self._active_text_mode)
        self.transcript_text.setPlainText(text or self.i18n.t("timeline.audio_player.no_transcript"))
        self._segment_timeline = timeline
        self._segment_line_map = line_map
        self._active_segment_index = -1
        self._clear_segment_highlight()
        self._refresh_format_toggle_text()
        self._update_format_toggle_visibility()
        if self.transcript_area.isVisible():
            self._sync_transcript_with_playback(self.player.position())

    def _on_mode_selected(self, mode: str) -> None:
        """Switch transcript panel mode."""
        if mode == self._active_text_mode:
            return
        self._active_text_mode = mode
        self._refresh_transcript_display()
        if self.transcript_area.isVisible():
            self._sync_transcript_with_playback(self.player.position())

    def _update_format_toggle_visibility(self) -> None:
        """Show transcript format toggle only when formatted transcript mode is active."""
        show_toggle = (
            self.transcript_area.isVisible()
            and self._active_text_mode == "transcript"
            and self._transcript_format == "segments"
            and bool(self._transcript_segments)
        )
        self.format_toggle_button.setVisible(show_toggle)
        self.format_toggle_button.setEnabled(show_toggle)

    def _clear_segment_highlight(self) -> None:
        """Clear active-line highlight from transcript text view."""
        self.transcript_text.setExtraSelections([])

    def _sync_transcript_with_playback(self, position_ms: int) -> None:
        """Highlight and scroll the active segment based on playback position."""
        if not self._segment_timeline:
            self._active_segment_index = -1
            self._clear_segment_highlight()
            return

        target_index = -1
        for index, (start_ms, end_ms) in enumerate(self._segment_timeline):
            if start_ms <= position_ms < end_ms:
                target_index = index
                break

        if target_index == -1:
            if position_ms < self._segment_timeline[0][0]:
                target_index = 0
            elif position_ms >= self._segment_timeline[-1][1]:
                target_index = len(self._segment_timeline) - 1
            else:
                return

        if target_index == self._active_segment_index:
            return

        self._active_segment_index = target_index
        line_number = self._segment_line_map.get(target_index)
        if line_number is None:
            self._clear_segment_highlight()
            return

        block = self.transcript_text.document().findBlockByLineNumber(line_number)
        if not block.isValid():
            self._clear_segment_highlight()
            return

        cursor = QTextCursor(block)
        cursor.select(QTextCursor.SelectionType.LineUnderCursor)

        highlight = QTextEdit.ExtraSelection()
        highlight.cursor = cursor
        highlight.format = QTextCharFormat()
        highlight.format.setBackground(ThemeManager().get_color("highlight"))
        self.transcript_text.setExtraSelections([highlight])
        self.transcript_text.setTextCursor(cursor)
        self._scroll_cursor_into_view(cursor)

    def _scroll_cursor_into_view(self, cursor: QTextCursor) -> None:
        """Scroll QTextEdit so active cursor line stays near viewport center."""
        self.transcript_text.ensureCursorVisible()

        scrollbar = self.transcript_text.verticalScrollBar()
        if scrollbar is None:
            return

        cursor_rect = self.transcript_text.cursorRect(cursor)
        viewport_height = self.transcript_text.viewport().height()
        if viewport_height <= 0:
            return

        target = scrollbar.value() + cursor_rect.center().y() - (viewport_height // 2)
        target = max(scrollbar.minimum(), min(scrollbar.maximum(), int(target)))
        scrollbar.setValue(target)

    def _toggle_transcript_format(self):
        """切换转录文本显示格式（带时间戳 vs 纯文本）."""
        if self._transcript_format != "segments" or not self._transcript_segments:
            return

        if self._transcript_view_mode == "formatted":
            self._transcript_view_mode = "plain"
        else:
            self._transcript_view_mode = "formatted"

        self._refresh_transcript_display()
        if self.transcript_area.isVisible():
            self._sync_transcript_with_playback(self.player.position())

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
            self._pause_other_players()
            self.player.play()

    def _pause_other_players(self) -> None:
        """Ensure only one audio player plays at a time."""
        for player in list(self._ACTIVE_PLAYERS):
            if player is self:
                continue
            if player.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
                player.player.pause()

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
            self._sync_transcript_with_playback(position)

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
        self._sync_transcript_with_playback(position)

    def _on_slider_moved(self, position: int):
        """
        Handle slider move during seeking.

        Args:
            position: Slider position
        """
        self.current_time_label.setText(self._format_time(position))
        self._sync_transcript_with_playback(position)

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
        self.rewind_button.setEnabled(enabled)
        self.stop_button.setEnabled(enabled)
        self.forward_button.setEnabled(enabled)
        self.volume_button.setEnabled(enabled)
        self.progress_slider.setEnabled(enabled)
        self.volume_slider.setEnabled(enabled)

    def _refresh_file_label(self) -> None:
        """Render file name with middle ellipsis for narrow widths."""
        metrics = self.file_label.fontMetrics()
        available_width = max(120, self.file_label.width() or 360)
        display_name = metrics.elidedText(
            self._full_file_name,
            Qt.TextElideMode.ElideMiddle,
            available_width,
        )
        self.file_label.setText(display_name)

    def resizeEvent(self, event):
        """Keep title eliding in sync with current widget width."""
        super().resizeEvent(event)
        self._refresh_file_label()

    def update_translations(self):
        """Refresh translated text and tooltips when the language changes."""
        self._initial_time_text = self.i18n.t("timeline.audio_player.initial_time")

        if self.progress_slider.value() == 0:
            self.current_time_label.setText(self._initial_time_text)
        if self.progress_slider.maximum() == 0:
            self.total_time_label.setText(self._initial_time_text)

        self.now_playing_label.setText(self.i18n.t("timeline.audio_player.now_playing"))
        self.transcript_title_label.setText(self.i18n.t("timeline.audio_player.transcript"))
        self.mode_caption_label.setText(self.i18n.t("timeline.audio_player.view_mode"))
        self._mode_buttons["transcript"].setText(
            self.i18n.t("timeline.audio_player.mode_transcript")
        )
        self._mode_buttons["translation"].setText(
            self.i18n.t("timeline.audio_player.mode_translation")
        )
        self._mode_buttons["compare"].setText(self.i18n.t("timeline.audio_player.mode_compare"))
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
        self._set_button_icon(
            self.rewind_button,
            QStyle.StandardPixmap.SP_MediaSeekBackward,
            is_primary=False,
        )
        self._set_button_icon(
            self.forward_button,
            QStyle.StandardPixmap.SP_MediaSeekForward,
            is_primary=False,
        )
        self.rewind_button.setAccessibleName(
            self.i18n.t("timeline.audio_player.rewind_button_label")
        )
        self.forward_button.setAccessibleName(
            self.i18n.t("timeline.audio_player.forward_button_label")
        )
        self.rewind_button.setToolTip(self.i18n.t("timeline.audio_player.rewind_tooltip"))
        self.forward_button.setToolTip(self.i18n.t("timeline.audio_player.forward_tooltip"))
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
        self._sync_transcript_toggle_tooltip()
        self.play_button.setToolTip(button_tooltip)
        self._update_volume_button_icon()
        self.volume_slider.setToolTip(self.i18n.t("timeline.audio_player.volume_tooltip"))
        self.progress_slider.setToolTip(self.i18n.t("timeline.audio_player.progress_tooltip"))
        self._refresh_transcript_display()

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
        if self._transcript_format != "segments" or self._active_text_mode != "transcript":
            self.format_toggle_button.setText("")
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
        self._ACTIVE_PLAYERS.discard(self)
        self._clear_segment_highlight()
        for shortcut_name in (
            "_play_pause_shortcut",
            "_rewind_shortcut",
            "_forward_shortcut",
        ):
            shortcut = getattr(self, shortcut_name, None)
            if shortcut is not None:
                shortcut.setEnabled(False)
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
        translation_path: Optional[str] = None,
    ):
        """
        Initialize audio player dialog.

        Args:
            file_path: Path to audio file
            i18n: Internationalization manager
            parent: Parent widget
            transcript_path: Optional explicit path to the transcript file
            translation_path: Optional explicit path to the translation file
        """
        super().__init__(parent)

        self.i18n = i18n

        # Setup dialog
        self.setObjectName("audio_player_dialog")
        self.setWindowTitle(i18n.t("timeline.audio_player_title"))
        self.setMinimumWidth(AUDIO_PLAYER_DIALOG_MIN_WIDTH)
        self.setMinimumHeight(AUDIO_PLAYER_DIALOG_MIN_HEIGHT)
        self.resize(AUDIO_PLAYER_DIALOG_DEFAULT_WIDTH, AUDIO_PLAYER_DIALOG_DEFAULT_HEIGHT)
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
            translation_path=translation_path,
        )
        self.player.playback_error.connect(self._on_playback_error)
        layout.addWidget(self.player)

        # Explicitly load after signals are connected so initialization errors propagate.
        self.player.load_file(file_path, transcript_path, translation_path)

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
