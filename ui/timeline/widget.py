"""
Timeline widget for EchoNote.

Displays a vertical timeline of past and future events with search and filtering.
"""

import importlib
import logging
import math
from typing import Optional, Dict, Any, List, TYPE_CHECKING, cast
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea,
    QLineEdit, QComboBox, QLabel, QFrame, QPushButton, QMessageBox, QDateEdit
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QDateTime, QTime, QDate
from PyQt6.QtGui import QPalette

from utils.i18n import I18nQtManager
from core.timeline.manager import to_local_naive

if TYPE_CHECKING:  # pragma: no cover - imported for type checking only
    from ui.timeline.event_card import EventCard


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
        parent: Optional[QWidget] = None,
        settings_manager: Optional[object] = None
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
        self.settings_manager = settings_manager
        self._settings_signal_connected = False

        # State
        self.current_page = 0
        self.past_days = self._get_timeline_setting(
            "timeline.past_days", default=30
        )
        self.future_days = self._get_timeline_setting(
            "timeline.future_days", default=30
        )
        self.page_size = self._get_timeline_setting(
            "timeline.page_size", default=50, minimum=1
        )
        self.is_loading = False
        self._pending_refresh: Optional[bool] = None
        self.has_more = True
        self.event_cards: List[QWidget] = []
        self._audio_player_dialogs: Dict[str, 'AudioPlayerDialog'] = {}
        self._text_viewer_dialogs: Dict[str, 'TranscriptViewerDialog'] = {}
        self._auto_task_state_cache: Dict[str, Dict[str, Any]] = {}
        
        # Current filters
        self.current_query = ""
        self.current_filters = {}
        
        # Setup UI
        self.setup_ui()
        
        # Connect language change
        self.i18n.language_changed.connect(self.update_translations)
        
        # Connect settings change notifications when available
        self._connect_settings_manager()

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
        filter_row.addWidget(self.start_date_edit)

        self.date_range_separator = QLabel(
            self.i18n.t('timeline.filter_date_range_separator')
        )
        filter_row.addWidget(self.date_range_separator)

        self.end_date_edit = QDateEdit()
        self.end_date_edit.setCalendarPopup(True)
        self.sync_date_filters_with_preferences()

        self.start_date_edit.dateChanged.connect(self._on_filter_changed)
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

    def _normalize_day_span(self, value: Any) -> int:
        """Return a non-negative integer day span derived from ``value``."""
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return 0

        normalized = math.floor(numeric)
        return max(normalized, 0)

    def _calculate_date_range_defaults(self) -> tuple[QDate, QDate]:
        """Compute default start/end dates derived from user preferences."""
        current_date = QDate.currentDate()
        past_days = self._normalize_day_span(self.past_days)
        future_days = self._normalize_day_span(self.future_days)

        start_date = current_date.addDays(-past_days) if past_days else current_date
        end_date = current_date.addDays(future_days) if future_days else current_date
        return start_date, end_date

    def sync_date_filters_with_preferences(self) -> None:
        """Update date range widgets so they match the configured preferences."""
        if not hasattr(self, 'start_date_edit') or not hasattr(self, 'end_date_edit'):
            return

        start_date, end_date = self._calculate_date_range_defaults()

        previous_start_block = self.start_date_edit.blockSignals(True)
        previous_end_block = self.end_date_edit.blockSignals(True)
        try:
            self.start_date_edit.setDate(start_date)
            self.end_date_edit.setDate(end_date)
        finally:
            self.start_date_edit.blockSignals(previous_start_block)
            self.end_date_edit.blockSignals(previous_end_block)
    
    def load_timeline_events(self, reset: bool = True) -> bool:
        """
        Load timeline events from the manager.

        Args:
            reset: If True, reset pagination and clear existing events

        Returns:
            bool: ``True`` if events were loaded successfully, ``False`` otherwise.
        """
        if self.is_loading:
            self._pending_refresh = bool(reset)
            return False

        previous_has_more = self.has_more
        previous_page = (
            self.current_page if reset else max(self.current_page - 1, 0)
        )
        page_to_load = 0 if reset else self.current_page
        success = False

        try:
            self.is_loading = True

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

                future_events.sort(
                    key=lambda item: to_local_naive(item['event'].start_time)
                )

                data = {
                    'current_time': center_time_local.isoformat(),
                    'past_events': past_events,
                    'future_events': future_events,
                    'has_more': False
                }
            else:
                # Normal timeline mode
                effective_past_days = self.past_days
                effective_future_days = self.future_days
                seconds_per_day = 24 * 60 * 60

                if self.current_filters:
                    start_filter = self.current_filters.get('start_date')
                    if start_filter:
                        start_dt = to_local_naive(start_filter)
                        if start_dt < center_time_local:
                            delta_seconds = (
                                center_time_local - start_dt
                            ).total_seconds()
                            if delta_seconds > 0:
                                required_days = math.ceil(
                                    delta_seconds / seconds_per_day
                                )
                                effective_past_days = max(
                                    effective_past_days, required_days
                                )

                    end_filter = self.current_filters.get('end_date')
                    if end_filter:
                        end_dt = to_local_naive(end_filter)
                        if end_dt > center_time_local:
                            delta_seconds = (
                                end_dt - center_time_local
                            ).total_seconds()
                            if delta_seconds > 0:
                                required_days = math.ceil(
                                    delta_seconds / seconds_per_day
                                )
                                effective_future_days = max(
                                    effective_future_days, required_days
                                )

                data = self.timeline_manager.get_timeline_events(
                    center_time=center_time_local,
                    past_days=effective_past_days,
                    future_days=effective_future_days,
                    page=page_to_load,
                    page_size=self.page_size,
                    filters=self.current_filters or None
                )

            # Update state
            self.has_more = data.get('has_more', False)

            # Clear and rebuild timeline only after data retrieval succeeded
            if reset and page_to_load == 0:
                self.clear_timeline()

                # Add future events first
                for event_data in data['future_events']:
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

            self.current_page = page_to_load

            logger.debug(
                f"Loaded timeline events: page {self.current_page}, "
                f"has_more={self.has_more}"
            )

            success = True
        except Exception as e:
            logger.error(f"Failed to load timeline events: {e}")
            self.has_more = previous_has_more
            self.current_page = previous_page
        finally:
            self.is_loading = False

            if self._pending_refresh is not None:
                pending_reset = self._pending_refresh
                self._pending_refresh = None
                QTimer.singleShot(
                    0,
                    lambda pending=pending_reset: self.load_timeline_events(
                        reset=pending
                    ),
                )

        return success

    def _get_timeline_setting(
        self,
        key: str,
        default: int,
        *,
        minimum: int = 0
    ) -> int:
        """Return a timeline preference from settings with fallbacks."""
        manager = self.settings_manager
        if manager is None:
            return default

        value: Any = default

        try:
            if hasattr(manager, "get_setting"):
                value = getattr(manager, "get_setting")(key)
            elif hasattr(manager, "get"):
                getter = getattr(manager, "get")
                try:
                    value = getter(key, default)
                except TypeError:
                    value = getter(key)
            else:
                return default
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.warning(
                "Failed to read %s from settings manager: %s", key, exc,
                exc_info=True
            )
            return default

        if isinstance(value, bool):
            return default

        if isinstance(value, int):
            return value if value >= minimum else default

        if isinstance(value, float) and value.is_integer():
            coerced = int(value)
            return coerced if coerced >= minimum else default

        logger.debug(
            "Using default for %s due to invalid value: %r", key, value
        )
        return default

    def _connect_settings_manager(self) -> None:
        """Subscribe to settings changes when the manager exposes a signal."""
        manager = self.settings_manager
        if not manager:
            return

        signal = getattr(manager, "setting_changed", None)
        if signal is None or not hasattr(signal, "connect"):
            return

        try:
            signal.connect(self._on_settings_changed)
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.warning(
                "Failed to connect to settings_manager.setting_changed: %s",
                exc,
            )
        else:
            self._settings_signal_connected = True

    def _disconnect_settings_manager(self) -> None:
        """Detach from settings change notifications when cleaning up."""
        if not getattr(self, "_settings_signal_connected", False):
            return

        manager = getattr(self, "settings_manager", None)
        signal = getattr(manager, "setting_changed", None) if manager else None

        if signal is None or not hasattr(signal, "disconnect"):
            self._settings_signal_connected = False
            return

        try:
            signal.disconnect(self._on_settings_changed)
        except (TypeError, RuntimeError, AttributeError):
            pass
        finally:
            self._settings_signal_connected = False

    def _update_current_filter_dates(self) -> None:
        """Ensure ``current_filters`` stores the date range from the widgets."""
        if not hasattr(self, 'start_date_edit') or not hasattr(self, 'end_date_edit'):
            return

        if not isinstance(getattr(self, 'current_filters', None), dict):
            self.current_filters = {}

        start_qdate = self.start_date_edit.date()
        end_qdate = self.end_date_edit.date()

        start_dt = QDateTime(start_qdate, QTime(0, 0, 0))
        end_dt = QDateTime(end_qdate, QTime(23, 59, 59))

        self.current_filters['start_date'] = start_dt.toString(Qt.DateFormat.ISODate)
        self.current_filters['end_date'] = end_dt.toString(Qt.DateFormat.ISODate)

    def _on_settings_changed(self, key: str, _value: Any) -> None:
        """React to preference changes that impact the timeline view."""
        preference_map = {
            'timeline.past_days': (
                'past_days',
                lambda: self._get_timeline_setting(
                    'timeline.past_days',
                    default=self.past_days,
                ),
                True,
            ),
            'timeline.future_days': (
                'future_days',
                lambda: self._get_timeline_setting(
                    'timeline.future_days',
                    default=self.future_days,
                ),
                True,
            ),
            'timeline.page_size': (
                'page_size',
                lambda: self._get_timeline_setting(
                    'timeline.page_size',
                    default=self.page_size,
                    minimum=1,
                ),
                False,
            ),
        }

        if not isinstance(getattr(self, 'current_filters', None), dict):
            self.current_filters = {}

        entry = preference_map.get(key)
        if not entry:
            return

        attr_name, loader, should_sync_dates = entry
        new_value = loader()
        if getattr(self, attr_name) == new_value:
            return

        setattr(self, attr_name, new_value)

        if attr_name == 'page_size':
            self.current_page = 0

        if should_sync_dates:
            preserved_event_type = self.current_filters.get('event_type')
            preserved_source = self.current_filters.get('source')

            self.sync_date_filters_with_preferences()

            self.current_filters = {}
            if preserved_event_type:
                self.current_filters['event_type'] = preserved_event_type
            if preserved_source:
                self.current_filters['source'] = preserved_source

            self._update_current_filter_dates()

        logger.info("Timeline preference %s updated to %s", key, new_value)
        self.load_timeline_events(reset=True)
    
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
        from ui.timeline.event_card import EventCard, CurrentTimeIndicator
        
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
            # Future events stay grouped above the current time indicator.
            new_start = to_local_naive(card.event.start_time)

            indicator_index = next(
                (
                    i
                    for i, existing_card in enumerate(self.event_cards)
                    if isinstance(existing_card, CurrentTimeIndicator)
                ),
                None,
            )

            # Search within the future event group for the correct position.
            search_limit = (
                indicator_index
                if indicator_index is not None
                else len(self.event_cards)
            )
            insert_pos = search_limit
            for i in range(search_limit):
                existing_card = self.event_cards[i]
                existing_start = to_local_naive(existing_card.event.start_time)
                if existing_start > new_start:
                    insert_pos = i
                    break

            self.timeline_layout.insertWidget(insert_pos, card)
            self.event_cards.insert(insert_pos, card)

            # Verify the indicator still follows the future event group.
            if indicator_index is not None:
                indicator_widget = next(
                    (
                        existing_card
                        for existing_card in self.event_cards
                        if isinstance(existing_card, CurrentTimeIndicator)
                    ),
                    None,
                )

                if indicator_widget is not None:
                    layout_index = self.timeline_layout.indexOf(indicator_widget)
                    list_index = self.event_cards.index(indicator_widget)
                    if layout_index != list_index:
                        logger.debug(
                            "Current time indicator layout index mismatch: "
                            f"layout={layout_index}, list={list_index}"
                        )

                    future_count = sum(
                        1 for card_item in self.event_cards
                        if getattr(card_item, 'is_future', False)
                    )
                    if list_index != future_count:
                        logger.debug(
                            "Current time indicator misaligned after future event "
                            f"insert: indicator_index={list_index}, future_count="
                            f"{future_count}"
                        )
        else:
            # Past events go at the bottom (before stretch)
            insert_pos = len(self.event_cards)
            self.timeline_layout.insertWidget(insert_pos, card)
            self.event_cards.append(card)

        if is_future:
            auto_tasks = event_data.get('auto_tasks') or {}
            self._auto_task_state_cache[card.event.id] = dict(auto_tasks)

    def get_event_card_by_id(self, event_id: str) -> Optional['EventCard']:
        """Return the event card associated with the given event id."""
        for card in self.event_cards:
            if not hasattr(card, 'event'):
                continue
            if getattr(card.event, 'id', None) == event_id:
                return cast('EventCard', card)
        return None
    
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
                previous_page = self.current_page
                target_page = self.current_page + 1
                self.current_page = target_page
                if not self.load_timeline_events(reset=False):
                    self.current_page = previous_page
    
    def _on_search(self):
        """Handle search button click."""
        query = self.search_input.text().strip()
        
        self.current_query = query

        if query:
            logger.info(f"Searching timeline: {query}")
        else:
            logger.info("Refreshing timeline without query filter")

        self._refresh_timeline(reset=True)
    
    def _on_filter_changed(self):
        """Handle filter change."""
        # Get current filter values
        event_type = self.type_filter.currentData()
        source = self.source_filter.currentData()

        start_qdate = self.start_date_edit.date()
        end_qdate = self.end_date_edit.date()

        if start_qdate > end_qdate:
            logger.warning(
                "Start date %s is after end date %s; swapping values for timeline filter.",
                start_qdate.toString(Qt.DateFormat.ISODate),
                end_qdate.toString(Qt.DateFormat.ISODate),
            )

            prev_start_blocked = self.start_date_edit.blockSignals(True)
            prev_end_blocked = self.end_date_edit.blockSignals(True)
            try:
                self.start_date_edit.setDate(end_qdate)
                self.end_date_edit.setDate(start_qdate)
            finally:
                self.start_date_edit.blockSignals(prev_start_blocked)
                self.end_date_edit.blockSignals(prev_end_blocked)

            start_qdate, end_qdate = end_qdate, start_qdate
            logger.info(
                "Timeline date range corrected to %s → %s.",
                start_qdate.toString(Qt.DateFormat.ISODate),
                end_qdate.toString(Qt.DateFormat.ISODate),
            )

        # Update filters
        self.current_filters = {}
        if event_type:
            self.current_filters['event_type'] = event_type
        if source:
            self.current_filters['source'] = source

        self._update_current_filter_dates()

        logger.info(f"Timeline filters changed: {self.current_filters}")
        self._refresh_timeline(reset=True)

    def _refresh_timeline(self, reset: bool = True):
        """Trigger a timeline refresh respecting the loading guard."""
        self.load_timeline_events(reset=reset)

    def _show_audio_unavailable_message(self):
        """Inform the user that audio playback components are unavailable."""
        title = self.i18n.t('timeline.audio_player_unavailable_title')
        message = self.i18n.t('timeline.audio_player_unavailable_message')
        QMessageBox.warning(self, title, message)

    def _on_auto_task_changed(self, event_id: str, config: Dict[str, Any]):
        """
        Handle auto-task configuration change.

        Args:
            event_id: Event ID
            config: Auto-task configuration
        """
        card = self.get_event_card_by_id(event_id)
        if card:
            self._auto_task_state_cache[event_id] = dict(config)

        try:
            self.timeline_manager.set_auto_task(event_id, config)
            logger.info(f"Auto-task config updated for event: {event_id}")
            if card:
                card.event_data['auto_tasks'] = dict(config)
            self.auto_task_changed.emit(event_id, config)
        except Exception as exc:
            logger.exception(
                "Failed to update auto-task config for %s", event_id
            )

            persisted_config: Optional[Dict[str, Any]] = None
            try:
                persisted_config = self.timeline_manager.get_auto_task(event_id)
            except Exception as fetch_error:  # pragma: no cover - defensive log
                logger.error(
                    "Failed to retrieve persisted auto-task config for %s: %s",
                    event_id,
                    fetch_error,
                )

            if persisted_config is None:
                try:
                    persisted_config = (
                        self.timeline_manager._default_auto_task_config()
                    )
                except Exception as default_error:  # pragma: no cover
                    logger.error(
                        "Failed to obtain default auto-task config: %s",
                        default_error,
                    )
                    persisted_config = {}

            if card:
                card.apply_auto_task_config(persisted_config)

            self._auto_task_state_cache[event_id] = dict(persisted_config)

            title = self.i18n.t('timeline.auto_task_save_failed_title')
            message = self.i18n.t('timeline.auto_task_save_failed_message').format(
                error=str(exc)
            )
            QMessageBox.warning(self, title, message)
    
    def _on_view_recording(self, file_path: str):
        """
        Handle view recording request.

        Args:
            file_path: Path to recording file
        """
        try:
            audio_module = importlib.import_module('ui.timeline.audio_player')
        except ImportError as exc:
            logger.warning(
                "Failed to import audio playback components: %s", exc
            )
            self._show_audio_unavailable_message()
            return

        AudioPlayerDialog = getattr(audio_module, 'AudioPlayerDialog', None)
        if AudioPlayerDialog is None:
            logger.warning(
                "Audio playback dialog is unavailable; skipping playback for %s",
                file_path,
            )
            self._show_audio_unavailable_message()
            return

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

    def deleteLater(self):  # noqa: D401
        """Ensure external signals are disconnected before deletion."""
        self._disconnect_settings_manager()
        super().deleteLater()

    def __del__(self):
        """Best-effort cleanup when the widget is garbage collected."""
        try:
            self._disconnect_settings_manager()
        except Exception:  # pragma: no cover - guard against PyQt teardown
            pass
