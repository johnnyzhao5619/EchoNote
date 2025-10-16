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
from PyQt6.QtCore import Qt, QUrl, pyqtSignal, QTimer
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
        parent: Optional[QWidget] = None
    ):
        """
        Initialize audio player.
        
        Args:
            file_path: Path to audio file
            i18n: Internationalization manager
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.file_path = file_path
        self.i18n = i18n
        
        # Media player
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        
        # State
        self.is_seeking = False
        
        # Setup UI
        self.setup_ui()
        
        # Connect player signals
        self.player.positionChanged.connect(self._on_position_changed)
        self.player.durationChanged.connect(self._on_duration_changed)
        self.player.playbackStateChanged.connect(self._on_state_changed)
        self.player.errorOccurred.connect(self._on_error)
        
        # Load file
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
        self.progress_slider.sliderPressed.connect(self._on_slider_pressed)
        self.progress_slider.sliderReleased.connect(self._on_slider_released)
        self.progress_slider.sliderMoved.connect(self._on_slider_moved)
        layout.addWidget(self.progress_slider)
        
        # Time labels
        time_layout = QHBoxLayout()
        self.current_time_label = QLabel("00:00")
        self.current_time_label.setStyleSheet("color: #666;")
        time_layout.addWidget(self.current_time_label)
        
        time_layout.addStretch()
        
        self.total_time_label = QLabel("00:00")
        self.total_time_label.setStyleSheet("color: #666;")
        time_layout.addWidget(self.total_time_label)
        
        layout.addLayout(time_layout)
        
        # Controls
        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(10)
        
        # Play/Pause button
        self.play_button = QPushButton("▶")
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
        volume_label = QLabel("🔊")
        controls_layout.addWidget(volume_label)
        
        # Volume slider
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(70)
        self.volume_slider.setMaximumWidth(100)
        self.volume_slider.valueChanged.connect(self._on_volume_changed)
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
            if not Path(file_path).exists():
                raise FileNotFoundError(f"Audio file not found: {file_path}")
            
            # Load file
            url = QUrl.fromLocalFile(file_path)
            self.player.setSource(url)
            
            logger.info(f"Audio file loaded: {file_path}")
            
        except Exception as e:
            error_msg = f"Failed to load audio file: {e}"
            logger.error(error_msg)
            self.playback_error.emit(error_msg)
    
    def toggle_playback(self):
        """Toggle play/pause."""
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
    
    def _on_state_changed(self, state: QMediaPlayer.PlaybackState):
        """
        Handle playback state change.
        
        Args:
            state: New playback state
        """
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.play_button.setText("⏸")
        else:
            self.play_button.setText("▶")
    
    def _on_error(self, error: QMediaPlayer.Error, error_string: str):
        """
        Handle playback error.
        
        Args:
            error: Error code
            error_string: Error description
        """
        error_msg = f"Playback error: {error_string}"
        logger.error(error_msg)
        self.playback_error.emit(error_msg)
    
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
    
    def cleanup(self):
        """Clean up resources."""
        self.player.stop()
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
        self.setModal(False)
        
        # Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Audio player
        self.player = AudioPlayer(file_path, i18n, self)
        self.player.playback_error.connect(self._on_playback_error)
        layout.addWidget(self.player)
        
        # Close button
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        close_button = QPushButton(i18n.t('common.close'))
        close_button.clicked.connect(self.close)
        button_layout.addWidget(close_button)
        
        layout.addLayout(button_layout)
        
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
            error_msg
        )
    
    def closeEvent(self, event):
        """Handle dialog close."""
        self.player.cleanup()
        event.accept()
