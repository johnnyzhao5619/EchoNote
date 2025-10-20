"""
Event card components for timeline view.

Displays event information with different layouts for past and future events.
"""

import logging
from typing import Optional, Dict, Any

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QPushButton, QCheckBox, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QPalette, QColor

from utils.i18n import I18nQtManager
from core.timeline.manager import to_local_naive


logger = logging.getLogger('echonote.ui.timeline.event_card')


class CurrentTimeIndicator(QFrame):
    """Visual indicator for current time in timeline."""
    
    def __init__(self, i18n: I18nQtManager, parent: Optional[QWidget] = None):
        """
        Initialize current time indicator.
        
        Args:
            i18n: Internationalization manager
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.i18n = i18n
        self.setup_ui()
    
    def setup_ui(self):
        """Set up the indicator UI."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 10, 0, 10)
        
        # Left line (red dashed)
        left_line = QFrame()
        left_line.setFrameShape(QFrame.Shape.HLine)
        left_line.setFrameShadow(QFrame.Shadow.Plain)
        left_line.setStyleSheet(
            "background-color: #F44336; "
            "border: 1px dashed #F44336;"
        )
        left_line.setFixedHeight(2)
        layout.addWidget(left_line, stretch=1)
        
        # Label
        label = QLabel(self.i18n.t('timeline.current_time'))
        label.setStyleSheet("color: #F44336; font-weight: bold;")
        layout.addWidget(label)
        
        # Right line (red dashed)
        right_line = QFrame()
        right_line.setFrameShape(QFrame.Shape.HLine)
        right_line.setFrameShadow(QFrame.Shadow.Plain)
        right_line.setStyleSheet(
            "background-color: #F44336; "
            "border: 1px dashed #F44336;"
        )
        right_line.setFixedHeight(2)
        layout.addWidget(right_line, stretch=1)
    
    def update_translations(self):
        """Update text when language changes."""
        # Find label and update
        for child in self.children():
            if isinstance(child, QLabel):
                child.setText(self.i18n.t('timeline.current_time'))
                break


class EventCard(QFrame):
    """
    Event card widget for timeline.
    
    Displays event information with different layouts for past and future events.
    """
    
    # Signals
    auto_task_changed = pyqtSignal(str, dict)  # event_id, config
    view_recording = pyqtSignal(str)  # file_path
    view_transcript = pyqtSignal(str)  # file_path
    
    def __init__(
        self,
        event_data: Dict[str, Any],
        is_future: bool,
        i18n: I18nQtManager,
        parent: Optional[QWidget] = None
    ):
        """
        Initialize event card.
        
        Args:
            event_data: Event data dictionary containing 'event' and either
                       'artifacts' (past) or 'auto_tasks' (future)
            is_future: True if this is a future event
            i18n: Internationalization manager
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.event_data = event_data
        self.event = event_data['event']
        self.is_future = is_future
        self.i18n = i18n
        
        # Lazy load artifacts
        self.artifacts_loaded = False
        self.artifacts = event_data.get('artifacts', {})
        
        # Setup UI
        self.setup_ui()
        
        # Store reference for future updates
        self.is_future = is_future
        
        logger.debug(f"Event card created: {self.event.id}")
    
    def setup_ui(self):
        """Set up the card UI."""
        # Card styling
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setFrameShadow(QFrame.Shadow.Raised)
        self.setObjectName("event_card")
        # Styling is handled by theme files (dark.qss / light.qss)
        
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)
        
        # Header with title and time
        header_layout = self.create_header()
        layout.addLayout(header_layout)
        
        # Event details
        details_layout = self.create_details()
        layout.addLayout(details_layout)
        
        # Actions (different for past/future)
        if self.is_future:
            actions_layout = self.create_future_actions()
        else:
            actions_layout = self.create_past_actions()
        
        layout.addLayout(actions_layout)
    
    def create_header(self) -> QVBoxLayout:
        """
        Create card header with title and time.
        
        Returns:
            Header layout
        """
        header_layout = QVBoxLayout()
        header_layout.setSpacing(5)
        
        # Title
        title_label = QLabel(self.event.title)
        title_font = QFont()
        title_font.setPointSize(12)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setWordWrap(True)
        header_layout.addWidget(title_label)
        
        # Time and type
        time_layout = QHBoxLayout()
        
        # Format time
        start_value = self.event.start_time
        end_value = self.event.end_time

        try:
            start_time = to_local_naive(start_value)
            end_time = to_local_naive(end_value)
        except Exception as exc:  # pragma: no cover - defensive log
            logger.warning(
                "Failed to localize event time for %s: %s",
                getattr(self.event, 'id', '<unknown>'),
                exc,
            )
            time_str = f"{start_value} - {end_value}"
        else:
            time_str = (
                f"{start_time.strftime('%Y-%m-%d %H:%M')} - "
                f"{end_time.strftime('%H:%M')}"
            )
        
        time_label = QLabel(time_str)
        time_label.setObjectName("time_label")
        time_layout.addWidget(time_label)
        
        # Event type badge
        type_badge = QLabel(self.event.event_type)
        type_badge.setObjectName("type_badge")
        type_badge.setStyleSheet("""
            QLabel#type_badge {
                background-color: rgba(33, 150, 243, 0.2);
                color: #2196F3;
                padding: 2px 8px;
                border-radius: 10px;
                font-size: 10px;
            }
        """)
        time_layout.addWidget(type_badge)
        
        # Source badge - get colors from configuration
        # Default colors if not configured
        default_colors = {
            'local': '#2196F3',
            'google': '#EA4335',
            'outlook': '#FF6F00'
        }
        
        # Try to get colors from event_data if provided by manager
        source_colors = self.event_data.get('source_colors', default_colors)
        source_color = source_colors.get(self.event.source, '#666')
        
        source_badge = QLabel(self.event.source.capitalize())
        source_badge.setObjectName("source_badge")
        source_badge.setStyleSheet(f"""
            QLabel#source_badge {{
                background-color: rgba({int(source_color[1:3], 16)}, {int(source_color[3:5], 16)}, {int(source_color[5:7], 16)}, 0.2);
                color: {source_color};
                padding: 2px 8px;
                border-radius: 10px;
                font-size: 10px;
            }}
        """)
        time_layout.addWidget(source_badge)
        
        time_layout.addStretch()
        header_layout.addLayout(time_layout)
        
        return header_layout
    
    def create_details(self) -> QVBoxLayout:
        """
        Create event details section.
        
        Returns:
            Details layout
        """
        details_layout = QVBoxLayout()
        details_layout.setSpacing(5)
        
        # Location
        if self.event.location:
            location_layout = QHBoxLayout()
            location_icon = QLabel("📍")
            location_layout.addWidget(location_icon)
            
            location_label = QLabel(self.event.location)
            location_label.setObjectName("detail_label")
            location_layout.addWidget(location_label)
            location_layout.addStretch()
            
            details_layout.addLayout(location_layout)
        
        # Attendees
        if self.event.attendees:
            attendees_layout = QHBoxLayout()
            attendees_icon = QLabel("👥")
            attendees_layout.addWidget(attendees_icon)
            
            attendees_text = ", ".join(self.event.attendees[:3])
            if len(self.event.attendees) > 3:
                attendees_text += f" +{len(self.event.attendees) - 3}"
            
            attendees_label = QLabel(attendees_text)
            attendees_label.setObjectName("detail_label")
            attendees_layout.addWidget(attendees_label)
            attendees_layout.addStretch()
            
            details_layout.addLayout(attendees_layout)
        
        # Description (truncated)
        if self.event.description:
            desc_label = QLabel(self.event.description[:100])
            if len(self.event.description) > 100:
                desc_label.setText(desc_label.text() + "...")
            desc_label.setObjectName("description_label")
            desc_label.setStyleSheet("font-size: 11px;")
            desc_label.setWordWrap(True)
            details_layout.addWidget(desc_label)
        
        return details_layout
    
    def create_future_actions(self) -> QHBoxLayout:
        """
        Create actions for future events (auto-task toggles).
        
        Returns:
            Actions layout
        """
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(15)
        
        # Get auto-task config
        auto_tasks = self.event_data.get('auto_tasks', {})
        
        # Transcription toggle
        self.transcription_checkbox = QCheckBox(
            self.i18n.t('timeline.enable_transcription')
        )
        self.transcription_checkbox.setChecked(
            auto_tasks.get('enable_transcription', False)
        )
        self.transcription_checkbox.stateChanged.connect(
            self._on_auto_task_changed
        )
        actions_layout.addWidget(self.transcription_checkbox)
        
        # Recording toggle
        self.recording_checkbox = QCheckBox(
            self.i18n.t('timeline.enable_recording')
        )
        self.recording_checkbox.setChecked(
            auto_tasks.get('enable_recording', False)
        )
        self.recording_checkbox.stateChanged.connect(
            self._on_auto_task_changed
        )
        actions_layout.addWidget(self.recording_checkbox)
        
        actions_layout.addStretch()
        
        return actions_layout
    
    def create_past_actions(self) -> QHBoxLayout:
        """
        Create actions for past events (view artifacts).
        
        Returns:
            Actions layout
        """
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(10)
        
        # Lazy load artifacts if not loaded
        if not self.artifacts_loaded:
            self._load_artifacts()
        
        # Recording button
        if self.artifacts.get('recording'):
            self.recording_btn = QPushButton("🎵 " + self.i18n.t('timeline.play_recording'))
            self.recording_btn.clicked.connect(self._on_play_recording)
            self.recording_btn.setObjectName("recording_btn")
            # Styling is handled by theme files (dark.qss / light.qss)
            actions_layout.addWidget(self.recording_btn)
        
        # Transcript button
        if self.artifacts.get('transcript'):
            self.transcript_btn = QPushButton("📄 " + self.i18n.t('timeline.view_transcript'))
            self.transcript_btn.clicked.connect(self._on_view_transcript)
            self.transcript_btn.setObjectName("transcript_btn")
            # Styling is handled by theme files (dark.qss / light.qss)
            actions_layout.addWidget(self.transcript_btn)
        
        # Show message if no artifacts
        if not self.artifacts.get('recording') and not self.artifacts.get('transcript'):
            no_artifacts_label = QLabel(self.i18n.t('timeline.no_artifacts'))
            no_artifacts_label.setObjectName("no_artifacts_label")
            no_artifacts_label.setStyleSheet("font-style: italic;")
            actions_layout.addWidget(no_artifacts_label)
        
        actions_layout.addStretch()
        
        return actions_layout
    
    def _load_artifacts(self):
        """Lazy load artifacts for past events."""
        if not self.artifacts_loaded and not self.is_future:
            # Artifacts should already be in event_data
            # This is just a placeholder for future optimization
            self.artifacts_loaded = True
            logger.debug(f"Artifacts loaded for event: {self.event.id}")
    
    def _on_auto_task_changed(self):
        """Handle auto-task checkbox change."""
        config = {
            'enable_transcription': self.transcription_checkbox.isChecked(),
            'enable_recording': self.recording_checkbox.isChecked()
        }
        
        logger.debug(f"Auto-task changed for event {self.event.id}: {config}")
        self.auto_task_changed.emit(self.event.id, config)
    
    def _on_play_recording(self):
        """Handle play recording button click."""
        recording_path = self.artifacts.get('recording')
        if recording_path:
            logger.info(f"Playing recording: {recording_path}")
            self.view_recording.emit(recording_path)
    
    def _on_view_transcript(self):
        """Handle view transcript button click."""
        transcript_path = self.artifacts.get('transcript')
        if transcript_path:
            logger.info(f"Viewing transcript: {transcript_path}")
            self.view_transcript.emit(transcript_path)
    
    def update_translations(self):
        """Update UI text when language changes."""
        if self.is_future:
            # Update checkboxes
            if hasattr(self, 'transcription_checkbox'):
                self.transcription_checkbox.setText(
                    self.i18n.t('timeline.enable_transcription')
                )
            if hasattr(self, 'recording_checkbox'):
                self.recording_checkbox.setText(
                    self.i18n.t('timeline.enable_recording')
                )
        else:
            # Update buttons
            if hasattr(self, 'recording_btn'):
                self.recording_btn.setText(
                    "🎵 " + self.i18n.t('timeline.play_recording')
                )
            if hasattr(self, 'transcript_btn'):
                self.transcript_btn.setText(
                    "📄 " + self.i18n.t('timeline.view_transcript')
                )
            
            # Update no artifacts label
            for child in self.findChildren(QLabel):
                if child.objectName() == "no_artifacts_label":
                    child.setText(self.i18n.t('timeline.no_artifacts'))
                    break
