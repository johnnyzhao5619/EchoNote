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
Timeline widget for EchoNote.

Displays a vertical timeline of past and future events with search and filtering.
"""

import importlib
import logging
import math
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional, cast

from ui.qt_imports import (
    QComboBox,
    QDate,
    QDateEdit,
    QDateTime,
    QLabel,
    QLineEdit,
    QLocale,
    QScrollArea,
    Qt,
    QTime,
    QTimer,
    QVBoxLayout,
    QWidget,
    Signal,
)
from ui.signal_helpers import (
    connect_button_with_callback,
    connect_value_changed,
)

if TYPE_CHECKING:
    from ui.timeline.audio_player import AudioPlayerDialog
    from ui.timeline.transcript_viewer import TranscriptViewerDialog

from core.calendar.constants import CalendarSource, EventType
from utils.time_utils import now_local, to_local_datetime, to_utc_iso
from ui.base_widgets import BaseWidget, create_button, create_hbox, create_vbox
from ui.constants import PAGE_COMPACT_SPACING, PAGE_LAYOUT_SPACING, ZERO_MARGINS
from utils.i18n import I18nQtManager

if TYPE_CHECKING:  # pragma: no cover - imported for type checking only
    from ui.timeline.event_card import EventCard

logger = logging.getLogger("echonote.ui.timeline.widget")


class TimelineWidget(BaseWidget):
    """
    Timeline view widget showing past and future events.

    Features:
    - Vertical scrolling timeline with current time indicator
    - Search and filter functionality
    - Lazy loading with pagination
    - Event cards for past and future events
    """

    # Signals
    event_selected = Signal(str)  # event_id
    auto_task_changed = Signal(str, dict)  # event_id, config
    _EVENT_TYPE_FILTER_OPTIONS = (
        ("timeline.filter_all", None),
        ("timeline.filter_event", EventType.EVENT),
        ("timeline.filter_task", EventType.TASK),
        ("timeline.filter_appointment", EventType.APPOINTMENT),
    )
    _SOURCE_FILTER_OPTIONS = (
        ("timeline.source_all", None),
        ("timeline.source_local", CalendarSource.LOCAL),
        ("timeline.source_google", CalendarSource.GOOGLE),
        ("timeline.source_outlook", CalendarSource.OUTLOOK),
    )

    def __init__(
        self,
        timeline_manager,
        transcription_manager,
        i18n: I18nQtManager,
        parent: Optional[QWidget] = None,
        settings_manager: Optional[object] = None,
    ):
        """
        Initialize timeline widget.

        Args:
            timeline_manager: TimelineManager instance
            i18n: Internationalization manager
            parent: Parent widget
        """
        super().__init__(i18n, parent)

        self.timeline_manager = timeline_manager
        self.transcription_manager = transcription_manager
        self.settings_manager = settings_manager
        self._settings_signal_connected = False

        # State
        self.current_page = 0
        self.past_days = self._get_timeline_setting("timeline.past_days", default=30)
        self.future_days = self._get_timeline_setting("timeline.future_days", default=30)
        self.page_size = self._get_timeline_setting("timeline.page_size", default=50, minimum=1)
        self.is_loading = False
        self._pending_refresh: Optional[bool] = None
        self.has_more = True
        self.event_cards: List[QWidget] = []
        self._audio_player_dialogs: Dict[str, "AudioPlayerDialog"] = {}
        self._text_viewer_dialogs: Dict[str, "TranscriptViewerDialog"] = {}

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

        logger.info(self.i18n.t("logging.timeline.widget_initialized"))

    def setup_ui(self):
        """Set up the timeline UI."""
        # Main layout
        layout = self.create_page_layout()

        # Title
        self.title_label = self.create_page_title("timeline.title", layout)

        # Header with search and filters
        header_layout = self.create_header()
        layout.addLayout(header_layout)

        # Timeline scroll area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        # Timeline container
        self.timeline_container = QWidget()
        self.timeline_layout = QVBoxLayout(self.timeline_container)
        self.timeline_layout.setContentsMargins(*ZERO_MARGINS)
        self.timeline_layout.setSpacing(PAGE_LAYOUT_SPACING)

        # Add stretch at the end
        self.timeline_layout.addStretch()

        self.scroll_area.setWidget(self.timeline_container)
        layout.addWidget(self.scroll_area)

        # Connect scroll event for pagination
        connect_value_changed(self.scroll_area.verticalScrollBar(), self._on_scroll)

        logger.debug("Timeline UI setup complete")

    def create_header(self) -> QVBoxLayout:
        """
        Create header with search and filter controls.

        Returns:
            Header layout (VBoxLayout with search and filter rows)
        """
        header_layout = create_vbox(spacing=PAGE_COMPACT_SPACING)

        # First row: Search
        search_row = create_hbox(spacing=PAGE_COMPACT_SPACING)

        # Search box
        self.search_input = QLineEdit()
        self.search_input.setProperty("role", "timeline-search-input")
        self.search_input.setPlaceholderText(self.i18n.t("timeline.search_placeholder"))
        self.search_input.setClearButtonEnabled(True)
        self.search_input.returnPressed.connect(self._on_search)
        search_row.addWidget(self.search_input, stretch=2)

        # Search button
        self.search_button = create_button(self.i18n.t("timeline.search"))
        self.search_button.setProperty("role", "timeline-search-action")
        connect_button_with_callback(self.search_button, self._on_search)
        search_row.addWidget(self.search_button)

        header_layout.addLayout(search_row)

        # Second row: Filters
        filter_row = create_hbox(spacing=PAGE_COMPACT_SPACING)

        # Date range filter
        self.date_range_label = QLabel(self.i18n.t("timeline.filter_date_range_label"))
        filter_row.addWidget(self.date_range_label)

        self.start_date_edit = QDateEdit()
        self.start_date_edit.setProperty("role", "timeline-filter-control")
        self.start_date_edit.setCalendarPopup(True)
        filter_row.addWidget(self.start_date_edit)

        self.date_range_separator = QLabel(self.i18n.t("timeline.filter_date_range_separator"))
        filter_row.addWidget(self.date_range_separator)

        self.end_date_edit = QDateEdit()
        self.end_date_edit.setProperty("role", "timeline-filter-control")
        self.end_date_edit.setCalendarPopup(True)
        self.sync_date_filters_with_preferences()

        self.start_date_edit.dateChanged.connect(self._on_filter_changed)
        self.end_date_edit.dateChanged.connect(self._on_filter_changed)
        filter_row.addWidget(self.end_date_edit)

        # Filter by event type
        self.type_filter = QComboBox()
        self.type_filter.setProperty("role", "timeline-filter-control")
        self._populate_filter_combo(
            self.type_filter,
            self._EVENT_TYPE_FILTER_OPTIONS,
        )
        self.type_filter.currentIndexChanged.connect(self._on_filter_changed)
        filter_row.addWidget(self.type_filter, stretch=1)

        # Filter by source
        self.source_filter = QComboBox()
        self.source_filter.setProperty("role", "timeline-filter-control")
        self._populate_filter_combo(
            self.source_filter,
            self._SOURCE_FILTER_OPTIONS,
        )
        self.source_filter.currentIndexChanged.connect(self._on_filter_changed)
        filter_row.addWidget(self.source_filter, stretch=1)

        header_layout.addLayout(filter_row)

        return header_layout

    def _populate_filter_combo(
        self,
        combo: QComboBox,
        options: tuple[tuple[str, object], ...],
        selected_data: object = None,
    ) -> None:
        """Populate a filter combo box from i18n key/value option tuples."""
        previous_state = combo.blockSignals(True)
        try:
            combo.clear()
            selected_index = 0
            for index, (text_key, value) in enumerate(options):
                combo.addItem(self.i18n.t(text_key), value)
                if value == selected_data:
                    selected_index = index
            combo.setCurrentIndex(selected_index)
        finally:
            combo.blockSignals(previous_state)

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
        if not hasattr(self, "start_date_edit") or not hasattr(self, "end_date_edit"):
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
            pending_request = bool(reset)
            if self._pending_refresh is None:
                self._pending_refresh = pending_request
            else:
                # Preserve any queued reset request so pagination doesn't override it.
                self._pending_refresh = self._pending_refresh or pending_request
            return False

        previous_has_more = self.has_more
        previous_page = self.current_page if reset else max(self.current_page - 1, 0)
        page_to_load = 0 if reset else self.current_page
        success = False

        try:
            self.is_loading = True

            # Get timeline data
            center_time = now_local()
            center_time_local = center_time

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
                    event = result["event"]
                    event_start = to_local_datetime(event.start_time)

                    if event_start < center_time_local:
                        past_events.append(result)
                    else:
                        future_events.append({"event": event, "auto_tasks": result["auto_tasks"]})

                future_events.sort(
                    key=lambda item: to_local_datetime(item["event"].start_time),
                    reverse=True,
                )

                data = {
                    "current_time": center_time_local.isoformat(),
                    "past_events": past_events,
                    "future_events": future_events,
                    "has_more": False,
                }
            else:
                # Normal timeline mode
                effective_past_days = self.past_days
                effective_future_days = self.future_days
                seconds_per_day = 24 * 60 * 60

                if self.current_filters:
                    start_filter = self.current_filters.get("start_date")
                    if start_filter:
                        start_dt = to_local_datetime(start_filter)
                        if start_dt < center_time_local:
                            delta_seconds = (center_time_local - start_dt).total_seconds()
                            if delta_seconds > 0:
                                required_days = math.ceil(delta_seconds / seconds_per_day)
                                effective_past_days = max(effective_past_days, required_days)

                    end_filter = self.current_filters.get("end_date")
                    if end_filter:
                        end_dt = to_local_datetime(end_filter)
                        if end_dt > center_time_local:
                            delta_seconds = (end_dt - center_time_local).total_seconds()
                            if delta_seconds > 0:
                                required_days = math.ceil(delta_seconds / seconds_per_day)
                                effective_future_days = max(effective_future_days, required_days)

                data = self.timeline_manager.get_timeline_events(
                    center_time=center_time_local,
                    past_days=effective_past_days,
                    future_days=effective_future_days,
                    page=page_to_load,
                    page_size=self.page_size,
                    filters=self.current_filters or None,
                )

            # Update state
            self.has_more = data.get("has_more", False)

            # Clear and rebuild timeline only after data retrieval succeeded
            if reset and page_to_load == 0:
                self.clear_timeline()

                # Add future events first
                for event_data in data["future_events"]:
                    self._add_event_card(event_data, is_future=True)

                # Add current time indicator
                self._add_current_time_indicator()

                # Add past events
                for event_data in data["past_events"]:
                    self._add_event_card(event_data, is_future=False)
            else:
                # Append more events (pagination)
                for event_data in data["past_events"]:
                    self._add_event_card(event_data, is_future=False)

            self.current_page = page_to_load

            logger.debug(
                f"Loaded timeline events: page {self.current_page}, " f"has_more={self.has_more}"
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
                    lambda pending=pending_reset: self.load_timeline_events(reset=pending),
                )

        return success

    def _get_timeline_setting(self, key: str, default: int, *, minimum: int = 0) -> int:
        """Return a timeline preference from settings with fallbacks."""
        manager = self.settings_manager
        if manager is None:
            return default

        value: Any = default

        try:
            if hasattr(manager, "get_setting"):
                # SettingsManager.get_setting() only takes one argument (key)
                value = getattr(manager, "get_setting")(key)
                # If value is None, use default
                if value is None:
                    value = default
            elif hasattr(manager, "get"):
                # ConfigManager.get() can take two arguments (key, default)
                getter = getattr(manager, "get")
                try:
                    value = getter(key, default)
                except TypeError:
                    # If it doesn't support default, just get the value
                    value = getter(key)
                    if value is None:
                        value = default
            else:
                return default
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.warning("Failed to read %s from settings manager: %s", key, exc, exc_info=True)
            return default

        if isinstance(value, bool):
            return default

        if isinstance(value, int):
            return value if value >= minimum else default

        if isinstance(value, float) and value.is_integer():
            coerced = int(value)
            return coerced if coerced >= minimum else default

        logger.debug("Using default for %s due to invalid value: %r", key, value)
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
        if not hasattr(self, "start_date_edit") or not hasattr(self, "end_date_edit"):
            return

        if not isinstance(getattr(self, "current_filters", None), dict):
            self.current_filters = {}

        start_qdate = self.start_date_edit.date()
        end_qdate = self.end_date_edit.date()

        start_dt = QDateTime(start_qdate, QTime(0, 0, 0))
        end_dt = QDateTime(end_qdate, QTime(23, 59, 59))

        self.current_filters["start_date"] = to_utc_iso(start_dt)
        self.current_filters["end_date"] = to_utc_iso(end_dt)

    def _on_settings_changed(self, key: str, _value: Any) -> None:
        """React to preference changes that impact the timeline view."""
        preference_map = {
            "timeline.past_days": (
                "past_days",
                lambda: self._get_timeline_setting(
                    "timeline.past_days",
                    default=self.past_days,
                ),
                True,
            ),
            "timeline.future_days": (
                "future_days",
                lambda: self._get_timeline_setting(
                    "timeline.future_days",
                    default=self.future_days,
                ),
                True,
            ),
            "timeline.page_size": (
                "page_size",
                lambda: self._get_timeline_setting(
                    "timeline.page_size",
                    default=self.page_size,
                    minimum=1,
                ),
                False,
            ),
        }

        if not isinstance(getattr(self, "current_filters", None), dict):
            self.current_filters = {}

        entry = preference_map.get(key)
        if not entry:
            return

        attr_name, loader, should_sync_dates = entry
        new_value = loader()
        if getattr(self, attr_name) == new_value:
            return

        setattr(self, attr_name, new_value)

        if attr_name == "page_size":
            self.current_page = 0

        if should_sync_dates:
            preserved_event_type = self.current_filters.get("event_type")
            preserved_source = self.current_filters.get("source")

            self.sync_date_filters_with_preferences()

            self.current_filters = {}
            if preserved_event_type:
                self.current_filters["event_type"] = preserved_event_type
            if preserved_source:
                self.current_filters["source"] = preserved_source

            self._update_current_filter_dates()

        logger.info("Timeline preference %s updated to %s", key, new_value)
        self.load_timeline_events(reset=True)

    def _add_current_time_indicator(self):
        """Add current time indicator line to timeline."""
        # Import here to avoid circular imports
        from ui.timeline.event_card import CurrentTimeIndicator

        indicator = CurrentTimeIndicator(self.i18n)
        self.timeline_layout.insertWidget(len(self.event_cards), indicator)
        self.event_cards.append(indicator)

    def _add_event_card(self, event_data: Dict[str, Any], is_future: bool):
        """
        Add an event card to the timeline.

        Args:
            event_data: Event data dictionary
            is_future: True if this is a future event
        """
        # Import here to avoid circular imports
        from ui.timeline.event_card import CurrentTimeIndicator, EventCard

        card = EventCard(event_data=event_data, is_future=is_future, i18n=self.i18n, parent=self)

        # Connect signals
        card.auto_task_changed.connect(self._on_auto_task_changed)
        card.view_recording.connect(self._on_view_recording)
        card.view_transcript.connect(self._on_view_transcript)
        card.view_translation.connect(self._on_view_translation)
        card.delete_requested.connect(self._on_delete_event_requested)
        card.secondary_transcribe_requested.connect(self._on_secondary_transcribe_requested)

        # Insert card at appropriate position
        if is_future:
            # Future events stay grouped above the current time indicator.
            new_start = to_local_datetime(card.calendar_event.start_time)

            indicator_index = next(
                (
                    i
                    for i, existing_card in enumerate(self.event_cards)
                    if isinstance(existing_card, CurrentTimeIndicator)
                ),
                None,
            )

            # Search within the future event group for the correct position.
            # Future group is ordered from farthest -> nearest.
            search_limit = indicator_index if indicator_index is not None else len(self.event_cards)
            insert_pos = search_limit
            for i in range(search_limit):
                existing_card = self.event_cards[i]
                existing_start = to_local_datetime(existing_card.calendar_event.start_time)
                if existing_start < new_start:
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
                        1
                        for card_item in self.event_cards
                        if getattr(card_item, "is_future", False)
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

    def get_event_card_by_id(self, event_id: str) -> Optional["EventCard"]:
        """Return the event card associated with the given event id."""
        for card in self.event_cards:
            event = getattr(card, "calendar_event", None)
            if getattr(event, "id", None) == event_id:
                return cast("EventCard", card)
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
            logger.info(self.i18n.t("logging.timeline.refreshing_without_query_filter"))

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
            self.current_filters["event_type"] = event_type
        if source:
            self.current_filters["source"] = source

        self._update_current_filter_dates()

        logger.info(f"Timeline filters changed: {self.current_filters}")
        self._refresh_timeline(reset=True)

    def _refresh_timeline(self, reset: bool = True):
        """Trigger a timeline refresh respecting the loading guard."""
        self.load_timeline_events(reset=reset)

    def _show_audio_unavailable_message(self):
        """Inform the user that audio playback components are unavailable."""
        title = self.i18n.t("timeline.audio_player_unavailable_title")
        message = self.i18n.t("timeline.audio_player_unavailable_message")
        self.show_warning(title, message)

    def _on_auto_task_changed(self, event_id: str, config: Dict[str, Any]):
        """
        Handle auto-task configuration change.

        Args:
            event_id: Event ID
            config: Auto-task configuration
        """
        card = self.get_event_card_by_id(event_id)

        try:
            self.timeline_manager.set_auto_task(event_id, config)
            logger.info(f"Auto-task config updated for event: {event_id}")
            if card:
                card.event_data["auto_tasks"] = dict(config)
            self.auto_task_changed.emit(event_id, config)
        except Exception as exc:
            logger.exception("Failed to update auto-task config for %s", event_id)

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
                    persisted_config = self.timeline_manager.get_default_auto_task_config()
                except Exception as default_error:  # pragma: no cover
                    logger.error(
                        "Failed to obtain default auto-task config: %s",
                        default_error,
                    )
                    persisted_config = {}

            if card:
                card.apply_auto_task_config(persisted_config)

            title = self.i18n.t("timeline.auto_task_save_failed_title")
            message = self.i18n.t("timeline.auto_task_save_failed_message").format(error=str(exc))
            self.show_warning(title, message)

    def _on_delete_event_requested(self, event_id: str):
        """Handle delete requests from timeline event cards."""
        calendar_manager = getattr(self.timeline_manager, "calendar_manager", None)
        if calendar_manager is None:
            self.show_error(self.i18n.t("common.error"), self.i18n.t("errors.unknown_error"))
            return

        event = calendar_manager.get_event(event_id)
        if not event:
            self.show_warning(
                self.i18n.t("common.warning"),
                self.i18n.t("calendar.error.event_not_found"),
            )
            return

        from ui.calendar_event_actions import confirm_and_delete_event

        confirm_and_delete_event(
            parent=self,
            i18n=self.i18n,
            calendar_manager=calendar_manager,
            event=event,
            on_deleted=lambda: self._refresh_timeline(reset=True),
        )

    def _on_view_recording(self, file_path: str, event_id: Optional[str] = None):
        """
        Handle view recording request.

        Args:
            file_path: Path to recording file
            event_id: Associated event ID
        """
        try:
            audio_module = importlib.import_module("ui.timeline.audio_player")
        except ImportError as exc:
            logger.warning("Failed to import audio playback components: %s", exc)
            self._show_audio_unavailable_message()
            return

        AudioPlayerDialog = getattr(audio_module, "AudioPlayerDialog", None)
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

            transcript_path = None
            if event_id:
                card = self.get_event_card_by_id(event_id)
                if card:
                    transcript_path = card.artifacts.get("transcript")

            dialog = AudioPlayerDialog(file_path, self.i18n, self, transcript_path)
        except Exception as exc:
            logger.exception("Failed to create audio player dialog for %s", file_path)
            title = self.i18n.t("timeline.audio_player_open_failed_title")
            message = self.i18n.t("timeline.audio_player_open_failed_message").format(
                error=str(exc)
            )
            self.show_error(title, message)
            return

        self._audio_player_dialogs[file_path] = dialog

        try:

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
        except Exception as exc:
            self._audio_player_dialogs.pop(file_path, None)
            logger.exception("Failed to display audio player dialog for %s", file_path)
            title = self.i18n.t("timeline.audio_player_open_failed_title")
            message = self.i18n.t("timeline.audio_player_open_failed_message").format(
                error=str(exc)
            )
            self.show_error(title, message)

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

            dialog = TranscriptViewerDialog(cache_key, self.i18n, self, title_key=title_key)
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
        self._open_text_viewer(file_path, "transcript.viewer_title")

    def _on_view_translation(self, file_path: str):
        """Handle view translation request."""
        self._open_text_viewer(file_path, "timeline.translation_viewer_title")

    def _on_secondary_transcribe_requested(self, event_id: str, recording_path: str):
        """Handle request for high-quality secondary transcription of an existing event."""
        if not self.transcription_manager:
            logger.error("Transcription manager not available for re-transcription")
            return

        logger.info(f"Submitting high-quality re-transcription for event {event_id}")
        options = {
            "event_id": event_id,
            "replace_realtime": True,
        }

        # Use event-specific language if available in auto-task config
        try:
            config = self.timeline_manager.get_auto_task(event_id)
            if (
                config
                and config.get("transcription_language")
                and config["transcription_language"] != "auto"
            ):
                options["language"] = config["transcription_language"]
        except Exception as e:
            logger.warning(
                f"Failed to fetch auto-task config for event {event_id}, using default: {e}"
            )

        self.transcription_manager.add_task(recording_path, options=options)

    def update_translations(self):
        """Update UI text when language changes."""
        # Update title
        self.title_label.setText(self.i18n.t("timeline.title"))

        self.search_input.setPlaceholderText(self.i18n.t("timeline.search_placeholder"))
        self.search_button.setText(self.i18n.t("timeline.search"))

        if hasattr(self, "date_range_label"):
            self.date_range_label.setText(self.i18n.t("timeline.filter_date_range_label"))

        if hasattr(self, "date_range_separator"):
            self.date_range_separator.setText(self.i18n.t("timeline.filter_date_range_separator"))

        # Update filter combo boxes while keeping selected value stable.
        self._populate_filter_combo(
            self.type_filter,
            self._EVENT_TYPE_FILTER_OPTIONS,
            selected_data=self.type_filter.currentData(),
        )
        self._populate_filter_combo(
            self.source_filter,
            self._SOURCE_FILTER_OPTIONS,
            selected_data=self.source_filter.currentData(),
        )

        # Update event cards
        for card in self.event_cards:
            if hasattr(card, "update_translations"):
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
