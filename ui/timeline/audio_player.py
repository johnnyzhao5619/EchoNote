"""
Audio player widget for timeline recordings.

Provides playback controls for audio recordings.
"""

import logging
from typing import Optional
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QSlider, QDialog, QMessageBox
)
from PyQt6.QtCore import Qt, QUrl, pyqtSignal
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput

from utils.i18n import I18nQtManager


logger = logging.getLogger('echonote.ui.timeline.audio_player')


class AudioPlayer(QWidget):
    """
    Audio player widget with playback controls.
    
    Features:
    - Play/pause control
    - Progress slider with seek
    - Volume control
    - Time display
    """
    
    # Signals
    playback_error = pyqtSignal(str)  # error_message
    
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
        super().__init__(parent)
        
        self.file_path = file_path
        self.i18n = i18n
        self._initial_time_text = self.i18n.t('timeline.audio_player.initial_time')
        self._playback_state = QMediaPlayer.PlaybackState.StoppedState
        
        # Media player
        self.player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.player.setAudioOutput(self.audio_output)

        # State
        self.is_seeking = False
        self._media_status = QMediaPlayer.MediaStatus.NoMedia

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
        """Set up the player UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # File name label
        file_name = Path(self.file_path).name
        self.file_label = QLabel(file_name)
        self.file_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(self.file_label)
        
        # Progress slider
        self.progress_slider = QSlider(Qt.Orientation.Horizontal)
        self.progress_slider.setRange(0, 0)
        self.progress_slider.setEnabled(False)
        self.progress_slider.sliderPressed.connect(self._on_slider_pressed)
        self.progress_slider.sliderReleased.connect(self._on_slider_released)
        self.progress_slider.sliderMoved.connect(self._on_slider_moved)
        layout.addWidget(self.progress_slider)
        
        # Time labels
        time_layout = QHBoxLayout()
        self.current_time_label = QLabel(self._initial_time_text)
        self.current_time_label.setStyleSheet("color: #666;")
        time_layout.addWidget(self.current_time_label)
        
        time_layout.addStretch()
        
        self.total_time_label = QLabel(self._initial_time_text)
        self.total_time_label.setStyleSheet("color: #666;")
        time_layout.addWidget(self.total_time_label)
        
        layout.addLayout(time_layout)
        
        # Controls
        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(10)
        
        # Play/Pause button
        self.play_button = QPushButton(
            self.i18n.t('timeline.audio_player.play_button_label')
        )
        self.play_button.setFixedSize(40, 40)
        self.play_button.clicked.connect(self.toggle_playback)
        self.play_button.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                border-radius: 20px;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """)
        controls_layout.addWidget(self.play_button)
        
        # Volume label
        self.volume_label = QLabel(
            self.i18n.t('timeline.audio_player.volume_icon')
        )
        controls_layout.addWidget(self.volume_label)
        
        # Volume slider
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(70)
        self.volume_slider.setMaximumWidth(100)
        self.volume_slider.valueChanged.connect(self._on_volume_changed)
        self.volume_slider.setEnabled(False)
        controls_layout.addWidget(self.volume_slider)
        
        controls_layout.addStretch()
        
        layout.addLayout(controls_layout)
        
        # Set initial volume
        self.audio_output.setVolume(0.7)

    def load_file(self, file_path: str):
        """
        Load audio file.

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

            logger.info(f"Audio file loaded: {file_path}")

        except Exception as e:
            self._emit_playback_error(
                'timeline.audio_player.load_failed',
                error=str(e)
            )

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
        error_detail = error_string or getattr(error, 'name', str(error))
        self._emit_playback_error(
            'timeline.audio_player.playback_error',
            error=error_detail
        )
        self.player.stop()
        self._playback_state = QMediaPlayer.PlaybackState.StoppedState
        self._reset_playback_state(reset_total=True)
        self.update_translations()
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
    
    def _on_volume_changed(self, value: int):
        """
        Handle volume change.
        
        Args:
            value: Volume value (0-100)
        """
        volume = value / 100.0
        self.audio_output.setVolume(volume)

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
        self._initial_time_text = self.i18n.t('timeline.audio_player.initial_time')

        if self.progress_slider.value() == 0:
            self.current_time_label.setText(self._initial_time_text)
        if self.progress_slider.maximum() == 0:
            self.total_time_label.setText(self._initial_time_text)

        if self._playback_state == QMediaPlayer.PlaybackState.PlayingState:
            button_label = self.i18n.t('timeline.audio_player.pause_button_label')
            button_tooltip = self.i18n.t('timeline.audio_player.pause_tooltip')
        else:
            button_label = self.i18n.t('timeline.audio_player.play_button_label')
            button_tooltip = self.i18n.t('timeline.audio_player.play_tooltip')

        self.play_button.setText(button_label)
        self.play_button.setToolTip(button_tooltip)

        self.volume_label.setText(
            self.i18n.t('timeline.audio_player.volume_icon')
        )
        self.volume_slider.setToolTip(
            self.i18n.t('timeline.audio_player.volume_tooltip')
        )
        self.progress_slider.setToolTip(
            self.i18n.t('timeline.audio_player.progress_tooltip')
        )

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
            QMediaPlayer.MediaStatus.UnknownMediaStatus,
            QMediaPlayer.MediaStatus.LoadingMedia,
        ):
            # Keep controls disabled until we know media is playable
            if self.player.duration() == 0:
                self._set_controls_enabled(False)
        elif status == QMediaPlayer.MediaStatus.InvalidMedia:
            self._emit_playback_error(
                'timeline.audio_player.playback_error',
                error=self.i18n.t('timeline.audio_player.invalid_media')
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
        parent: Optional[QWidget] = None
    ):
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
        self.setWindowTitle(i18n.t('timeline.audio_player_title'))
        self.setMinimumWidth(400)
        self.setWindowModality(Qt.WindowModality.NonModal)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        
        # Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
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
        
        # Close button
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.close_button = QPushButton(i18n.t('common.close'))
        self.close_button.clicked.connect(self.close)
        button_layout.addWidget(self.close_button)

        layout.addLayout(button_layout)

        self.i18n.language_changed.connect(self.update_translations)
        self.update_translations()

        logger.info("Audio player dialog initialized")
    
    def _on_playback_error(self, error_msg: str):
        """
        Handle playback error.
        
        Args:
            error_msg: Error message
        """
        QMessageBox.critical(
            self,
            self.i18n.t('common.error'),
            self.i18n.t(
                'timeline.audio_player.dialog_error_body',
                message=error_msg
            )
        )
    
    def closeEvent(self, event):
        """Handle dialog close."""
        self.player.cleanup()
        super().closeEvent(event)

    def update_translations(self):
        """Refresh dialog-level translations when the language changes."""
        self.setWindowTitle(self.i18n.t('timeline.audio_player_title'))
        self.close_button.setText(self.i18n.t('common.close'))
        self.player.update_translations()
