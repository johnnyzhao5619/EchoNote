"""
Timeline widget for EchoNote.

Displays a vertical timeline of past and future events with search and filtering.
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea,
    QLineEdit, QComboBox, QLabel, QFrame, QPushButton
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QPalette

from utils.i18n import I18nQtManager
from core.timeline.manager import to_local_naive


logger = logging.getLogger('echonote.ui.timeline.widget')


class TimelineWidget(QWidget):
    """
    Timeline view widget showing past and future events.
    
    Features:
    - Vertical scrolling timeline with current time indicator
    - Search and filter functionality
    - Lazy loading with pagination
    - Event cards for past and future events
    """
    
    # Signals
    event_selected = pyqtSignal(str)  # event_id
    auto_task_changed = pyqtSignal(str, dict)  # event_id, config
    
    def __init__(
        self,
        timeline_manager,
        i18n: I18nQtManager,
        parent: Optional[QWidget] = None
    ):
        """
        Initialize timeline widget.
        
        Args:
            timeline_manager: TimelineManager instance
            i18n: Internationalization manager
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.timeline_manager = timeline_manager
        self.i18n = i18n
        
        # State
        self.current_page = 0
        self.page_size = 50
        self.is_loading = False
        self.has_more = True
        self.event_cards: List[QWidget] = []
        self._audio_player_dialogs: Dict[str, 'AudioPlayerDialog'] = {}
        self._text_viewer_dialogs: Dict[str, 'TranscriptViewerDialog'] = {}
        
        # Current filters
        self.current_query = ""
        self.current_filters = {}
        
        # Setup UI
        self.setup_ui()
        
        # Connect language change
        self.i18n.language_changed.connect(self.update_translations)
        
        # Load initial data
        QTimer.singleShot(100, self.load_timeline_events)
        
        logger.info("Timeline widget initialized")
    
    def setup_ui(self):
        """Set up the timeline UI."""
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)
        
        # Title
        self.title_label = QLabel(self.i18n.t('timeline.title'))
        self.title_label.setObjectName("page_title")
        layout.addWidget(self.title_label)
        
        # Header with search and filters
        header_layout = self.create_header()
        layout.addLayout(header_layout)
        
        # Timeline scroll area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.scroll_area.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        
        # Timeline container
        self.timeline_container = QWidget()
        self.timeline_layout = QVBoxLayout(self.timeline_container)
        self.timeline_layout.setContentsMargins(0, 0, 0, 0)
        self.timeline_layout.setSpacing(15)
        
        # Add stretch at the end
        self.timeline_layout.addStretch()
        
        self.scroll_area.setWidget(self.timeline_container)
        layout.addWidget(self.scroll_area)
        
        # Connect scroll event for pagination
        self.scroll_area.verticalScrollBar().valueChanged.connect(
            self._on_scroll
        )
        
        logger.debug("Timeline UI setup complete")
    
    def create_header(self) -> QVBoxLayout:
        """
        Create header with search and filter controls.
        
        Returns:
            Header layout (VBoxLayout with search and filter rows)
        """
        from PyQt6.QtWidgets import QDateEdit
        from PyQt6.QtCore import QDate
        
        header_layout = QVBoxLayout()
        header_layout.setSpacing(10)
        
        # First row: Search
        search_row = QHBoxLayout()
        search_row.setSpacing(10)
        
        # Search box
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(
            self.i18n.t('timeline.search_placeholder')
        )
        self.search_input.setClearButtonEnabled(True)
        self.search_input.returnPressed.connect(self._on_search)
        search_row.addWidget(self.search_input, stretch=2)
        
        # Search button
        self.search_button = QPushButton(self.i18n.t('timeline.search'))
        self.search_button.clicked.connect(self._on_search)
        search_row.addWidget(self.search_button)
        
        header_layout.addLayout(search_row)
        
        # Second row: Filters
        filter_row = QHBoxLayout()
        filter_row.setSpacing(10)
        
        # Date range filter
        self.date_range_label = QLabel(
            self.i18n.t('timeline.filter_date_range_label')
        )
        filter_row.addWidget(self.date_range_label)
        
        self.start_date_edit = QDateEdit()
        self.start_date_edit.setCalendarPopup(True)
        self.start_date_edit.setDate(QDate.currentDate().addDays(-30))
        self.start_date_edit.dateChanged.connect(self._on_filter_changed)
        filter_row.addWidget(self.start_date_edit)
        
        self.date_range_separator = QLabel(
            self.i18n.t('timeline.filter_date_range_separator')
        )
        filter_row.addWidget(self.date_range_separator)
        
        self.end_date_edit = QDateEdit()
        self.end_date_edit.setCalendarPopup(True)
        self.end_date_edit.setDate(QDate.currentDate().addDays(30))
        self.end_date_edit.dateChanged.connect(self._on_filter_changed)
        filter_row.addWidget(self.end_date_edit)
        
        # Filter by event type
        self.type_filter = QComboBox()
        self.type_filter.addItem(self.i18n.t('timeline.filter_all'), None)
        self.type_filter.addItem(
            self.i18n.t('timeline.filter_event'), 'Event'
        )
        self.type_filter.addItem(
            self.i18n.t('timeline.filter_task'), 'Task'
        )
        self.type_filter.addItem(
            self.i18n.t('timeline.filter_appointment'), 'Appointment'
        )
        self.type_filter.currentIndexChanged.connect(self._on_filter_changed)
        filter_row.addWidget(self.type_filter, stretch=1)
        
        # Filter by source
        self.source_filter = QComboBox()
        self.source_filter.addItem(self.i18n.t('timeline.source_all'), None)
        self.source_filter.addItem(
            self.i18n.t('timeline.source_local'), 'local'
        )
        self.source_filter.addItem(
            self.i18n.t('timeline.source_google'), 'google'
        )
        self.source_filter.addItem(
            self.i18n.t('timeline.source_outlook'), 'outlook'
        )
        self.source_filter.currentIndexChanged.connect(self._on_filter_changed)
        filter_row.addWidget(self.source_filter, stretch=1)
        
        header_layout.addLayout(filter_row)
        
        return header_layout
    
    def load_timeline_events(self, reset: bool = True):
        """
        Load timeline events from the manager.
        
        Args:
            reset: If True, reset pagination and clear existing events
        """
        if self.is_loading:
            return
        
        try:
            self.is_loading = True
            
            if reset:
                self.current_page = 0
                self.clear_timeline()
            
            # Get timeline data
            center_time = datetime.now().astimezone()
            center_time_local = to_local_naive(center_time)
            
            if self.current_query:
                # Search mode
                results = self.timeline_manager.search_events(
                    self.current_query,
                    self.current_filters,
                    include_future_auto_tasks=True,
                )

                # Separate past and future
                past_events: List[Dict[str, Any]] = []
                future_events: List[Dict[str, Any]] = []

                for result in results:
                    event = result['event']
                    event_start = to_local_naive(event.start_time)

                    if event_start < center_time_local:
                        past_events.append(result)
                    else:
                        future_events.append({
                            'event': event,
                            'auto_tasks': result['auto_tasks']
                        })

                data = {
                    'current_time': center_time_local.isoformat(),
                    'past_events': past_events,
                    'future_events': future_events,
                    'has_more': False
                }
            else:
                # Normal timeline mode
                data = self.timeline_manager.get_timeline_events(
                    center_time=center_time_local,
                    past_days=30,
                    future_days=30,
                    page=self.current_page,
                    page_size=self.page_size
                )
            
            # Update state
            self.has_more = data.get('has_more', False)
            
            # Add events to timeline
            if reset and self.current_page == 0:
                # Add future events first
                for event_data in reversed(data['future_events']):
                    self._add_event_card(event_data, is_future=True)
                
                # Add current time indicator
                self._add_current_time_indicator()
                
                # Add past events
                for event_data in data['past_events']:
                    self._add_event_card(event_data, is_future=False)
            else:
                # Append more events (pagination)
                for event_data in data['past_events']:
                    self._add_event_card(event_data, is_future=False)
            
            logger.debug(
                f"Loaded timeline events: page {self.current_page}, "
                f"has_more={self.has_more}"
            )
            
        except Exception as e:
            logger.error(f"Failed to load timeline events: {e}")
        finally:
            self.is_loading = False
    
    def _add_current_time_indicator(self):
        """Add current time indicator line to timeline."""
        # Import here to avoid circular imports
        from ui.timeline.event_card import CurrentTimeIndicator
        
        indicator = CurrentTimeIndicator(self.i18n)
        self.timeline_layout.insertWidget(
            len(self.event_cards), indicator
        )
        self.event_cards.append(indicator)
    
    def _add_event_card(self, event_data: Dict[str, Any], is_future: bool):
        """
        Add an event card to the timeline.
        
        Args:
            event_data: Event data dictionary
            is_future: True if this is a future event
        """
        # Import here to avoid circular imports
        from ui.timeline.event_card import EventCard
        
        card = EventCard(
            event_data=event_data,
            is_future=is_future,
            i18n=self.i18n,
            parent=self
        )
        
        # Connect signals
        card.auto_task_changed.connect(self._on_auto_task_changed)
        card.view_recording.connect(self._on_view_recording)
        card.view_transcript.connect(self._on_view_transcript)
        card.view_translation.connect(self._on_view_translation)
        
        # Insert card at appropriate position
        if is_future:
            # Future events go at the top
            insert_pos = 0
            for i, existing_card in enumerate(self.event_cards):
                if not getattr(existing_card, 'is_future', False):
                    insert_pos = i
                    break
            else:
                insert_pos = len(self.event_cards)
            
            self.timeline_layout.insertWidget(insert_pos, card)
            self.event_cards.insert(insert_pos, card)
        else:
            # Past events go at the bottom (before stretch)
            insert_pos = len(self.event_cards)
            self.timeline_layout.insertWidget(insert_pos, card)
            self.event_cards.append(card)
    
    def clear_timeline(self):
        """Clear all event cards from timeline."""
        for card in self.event_cards:
            self.timeline_layout.removeWidget(card)
            card.deleteLater()
        
        self.event_cards.clear()
        logger.debug("Timeline cleared")
    
    def _on_scroll(self, value: int):
        """
        Handle scroll event for pagination.
        
        Args:
            value: Scroll bar value
        """
        # Check if scrolled near bottom
        scrollbar = self.scroll_area.verticalScrollBar()
        max_value = scrollbar.maximum()
        
        if max_value > 0:
            # Load more when 80% scrolled
            threshold = max_value * 0.8
            
            if value >= threshold and self.has_more and not self.is_loading:
                logger.debug("Loading more events (pagination)")
                self.current_page += 1
                self.load_timeline_events(reset=False)
    
    def _on_search(self):
        """Handle search button click."""
        query = self.search_input.text().strip()
        
        if query != self.current_query:
            self.current_query = query
            logger.info(f"Searching timeline: {query}")
            self.load_timeline_events(reset=True)
    
    def _on_filter_changed(self):
        """Handle filter change."""
        # Get current filter values
        event_type = self.type_filter.currentData()
        source = self.source_filter.currentData()
        
        # Get date range
        start_date = self.start_date_edit.date().toString("yyyy-MM-dd")
        end_date = self.end_date_edit.date().toString("yyyy-MM-dd")
        
        # Update filters
        self.current_filters = {}
        if event_type:
            self.current_filters['event_type'] = event_type
        if source:
            self.current_filters['source'] = source
        
        # Add date range to filters
        self.current_filters['start_date'] = start_date
        self.current_filters['end_date'] = end_date
        
        logger.info(f"Timeline filters changed: {self.current_filters}")
        self.load_timeline_events(reset=True)
    
    def _on_auto_task_changed(self, event_id: str, config: Dict[str, Any]):
        """
        Handle auto-task configuration change.
        
        Args:
            event_id: Event ID
            config: Auto-task configuration
        """
        try:
            self.timeline_manager.set_auto_task(event_id, config)
            logger.info(f"Auto-task config updated for event: {event_id}")
            self.auto_task_changed.emit(event_id, config)
        except Exception as e:
            logger.error(f"Failed to update auto-task config: {e}")
    
    def _on_view_recording(self, file_path: str):
        """
        Handle view recording request.
        
        Args:
            file_path: Path to recording file
        """
        # Import here to avoid circular imports
        from ui.timeline.audio_player import AudioPlayerDialog
        
        try:
            existing_dialog = self._audio_player_dialogs.get(file_path)

            if existing_dialog:
                existing_dialog.show()
                existing_dialog.raise_()
                existing_dialog.activateWindow()
                logger.info(f"Activated existing audio player for {file_path}")
                return

            dialog = AudioPlayerDialog(file_path, self.i18n, self)
            self._audio_player_dialogs[file_path] = dialog

            def _cleanup_dialog(*_):
                tracked_dialog = self._audio_player_dialogs.get(file_path)
                if tracked_dialog is dialog:
                    self._audio_player_dialogs.pop(file_path, None)
                    logger.debug(f"Closed audio player for {file_path}")

            dialog.finished.connect(_cleanup_dialog)
            dialog.destroyed.connect(_cleanup_dialog)

            dialog.show()
            dialog.raise_()
            dialog.activateWindow()
            logger.info(f"Opened audio player for {file_path}")
        except Exception as e:
            logger.error(f"Failed to open audio player: {e}")
    
    def _open_text_viewer(self, file_path: str, title_key: str):
        """Open a text viewer dialog for timeline artifacts."""
        from ui.timeline.transcript_viewer import TranscriptViewerDialog

        try:
            cache_key = str(file_path)
            existing_dialog = self._text_viewer_dialogs.get(cache_key)

            if existing_dialog:
                existing_dialog.show()
                existing_dialog.raise_()
                existing_dialog.activateWindow()
                logger.info(f"Activated text viewer for {cache_key}")
                return

            dialog = TranscriptViewerDialog(
                cache_key,
                self.i18n,
                self,
                title_key=title_key
            )
            self._text_viewer_dialogs[cache_key] = dialog

            def _cleanup_dialog(*_):
                tracked_dialog = self._text_viewer_dialogs.get(cache_key)
                if tracked_dialog is dialog:
                    self._text_viewer_dialogs.pop(cache_key, None)
                    logger.debug(f"Closed text viewer for {cache_key}")

            dialog.finished.connect(_cleanup_dialog)
            dialog.destroyed.connect(_cleanup_dialog)

            dialog.show()
            dialog.raise_()
            dialog.activateWindow()
            logger.info(f"Opened text viewer for {cache_key}")
        except Exception as e:
            logger.error(f"Failed to open text viewer: {e}")

    def _on_view_transcript(self, file_path: str):
        """Handle view transcript request."""
        self._open_text_viewer(file_path, 'transcript.viewer_title')

    def _on_view_translation(self, file_path: str):
        """Handle view translation request."""
        self._open_text_viewer(file_path, 'timeline.translation_viewer_title')
    
    def update_translations(self):
        """Update UI text when language changes."""
        # Update title
        self.title_label.setText(self.i18n.t('timeline.title'))
        
        self.search_input.setPlaceholderText(
            self.i18n.t('timeline.search_placeholder')
        )
        self.search_button.setText(self.i18n.t('timeline.search'))

        if hasattr(self, 'date_range_label'):
            self.date_range_label.setText(
                self.i18n.t('timeline.filter_date_range_label')
            )

        if hasattr(self, 'date_range_separator'):
            self.date_range_separator.setText(
                self.i18n.t('timeline.filter_date_range_separator')
            )

        # Update filter combo boxes
        self.type_filter.setItemText(
            0, self.i18n.t('timeline.filter_all')
        )
        self.type_filter.setItemText(
            1, self.i18n.t('timeline.filter_event')
        )
        self.type_filter.setItemText(
            2, self.i18n.t('timeline.filter_task')
        )
        self.type_filter.setItemText(
            3, self.i18n.t('timeline.filter_appointment')
        )
        
        self.source_filter.setItemText(
            0, self.i18n.t('timeline.source_all')
        )
        self.source_filter.setItemText(
            1, self.i18n.t('timeline.source_local')
        )
        self.source_filter.setItemText(
            2, self.i18n.t('timeline.source_google')
        )
        self.source_filter.setItemText(
            3, self.i18n.t('timeline.source_outlook')
        )
        
        # Update event cards
        for card in self.event_cards:
            if hasattr(card, 'update_translations'):
                card.update_translations()
        
        logger.debug("Timeline translations updated")
