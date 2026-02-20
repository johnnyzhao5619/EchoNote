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
Calendar View Components for EchoNote.

Provides month, week, and day views for displaying calendar events.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from core.qt_imports import (
    QBrush,
    QColor,
    QDate,
    QFont,
    QFrame,
    QGridLayout,
    QLabel,
    QLocale,
    QPainter,
    QPen,
    QPushButton,
    QRect,
    QScrollArea,
    Qt,
    QVBoxLayout,
    QWidget,
    Signal,
)

from ui.base_widgets import BaseWidget, BaseEventCard
from ui.constants import (
    CALENDAR_DAY_CELL_MIN_HEIGHT,
    CALENDAR_GRID_CELL_SPACING,
    PAGE_COMPACT_SPACING,
    PAGE_DENSE_SPACING,
    ROLE_CALENDAR_DAY_CELL,
    ROLE_CALENDAR_DAY_COLUMN,
    ROLE_CALENDAR_DAY_HEADER,
    ROLE_CALENDAR_DAY_NUMBER,
    ROLE_CALENDAR_EVENTS_CONTAINER,
    ROLE_CALENDAR_HEADER,
    ROLE_CALENDAR_WEEK_HEADER,
    ROLE_EVENT_CARD,
    ROLE_EVENT_INDICATOR,
    ROLE_EVENT_TIME,
    ROLE_EVENT_TITLE,
    ROLE_MORE_EVENTS,
    ROLE_NO_EVENTS,
    STATUS_INDICATOR_SYMBOL,
    ZERO_MARGINS,
)
from utils.i18n import I18nQtManager
from utils.time_utils import format_localized_datetime, now_local, to_local_datetime

logger = logging.getLogger("echonote.ui.calendar_view")


def _parse_datetime(value: Any) -> Optional[datetime]:
    """Parse values into local datetimes for UI comparisons."""
    try:
        return to_local_datetime(value)
    except (ValueError, TypeError):
        return None


def _event_bounds(calendar_event: Any) -> Optional[Tuple[datetime, datetime]]:
    """Return normalized event start/end bounds."""
    start_dt = _parse_datetime(getattr(calendar_event, "start_time", None))
    end_dt = _parse_datetime(getattr(calendar_event, "end_time", None))
    if start_dt is None or end_dt is None:
        return None

    if end_dt <= start_dt:
        end_dt = start_dt + timedelta(seconds=1)
    return start_dt, end_dt


def _event_sort_key(calendar_event: Any) -> datetime:
    bounds = _event_bounds(calendar_event)
    if bounds is None:
        return datetime.max
    return bounds[0]


def _get_weekday_labels(i18n: I18nQtManager) -> List[str]:
    keys_with_defaults = [
        ("calendar_hub.calendar_view.weekday_mon", "Mon"),
        ("calendar_hub.calendar_view.weekday_tue", "Tue"),
        ("calendar_hub.calendar_view.weekday_wed", "Wed"),
        ("calendar_hub.calendar_view.weekday_thu", "Thu"),
        ("calendar_hub.calendar_view.weekday_fri", "Fri"),
        ("calendar_hub.calendar_view.weekday_sat", "Sat"),
        ("calendar_hub.calendar_view.weekday_sun", "Sun"),
    ]

    labels: List[str] = []
    for key, default in keys_with_defaults:
        translated = i18n.t(key)
        labels.append(default if translated == key else translated)
    return labels


def _format_more_events_text(i18n: I18nQtManager, count: int) -> str:
    translated = i18n.t("calendar_hub.calendar_view.more_events", count=count)
    if translated == "calendar_hub.calendar_view.more_events":
        return f"+{count} more"
    return translated


def _get_ui_locale(i18n: I18nQtManager) -> QLocale:
    language_code = getattr(i18n, "current_language", None)
    if isinstance(language_code, str) and language_code.strip():
        return QLocale(language_code)
    return QLocale.system()


def _load_events_safe(calendar_manager: Any, start_date: datetime, end_date: datetime) -> List[Any]:
    """Load events for a time range with consistent error handling."""
    try:
        return calendar_manager.get_events(start_date=start_date, end_date=end_date)
    except Exception as exc:
        logger.error("Error loading events: %s", exc)
        return []


class ClickableDayFrame(QFrame):
    """A calendar day cell (MonthView) that can be clicked."""

    clicked = Signal(datetime)

    def __init__(self, date: datetime, parent=None):
        super().__init__(parent)
        self.date = date
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        self.clicked.emit(self.date)


class ClickableDayWidget(QWidget):
    """A calendar day column (WeekView) that can be clicked."""

    clicked = Signal(datetime)

    def __init__(self, date: datetime, parent=None):
        super().__init__(parent)
        self.date = date
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        self.clicked.emit(self.date)


class EventCard(BaseEventCard):
    """
    Visual representation of a calendar event.
    """

    clicked = Signal(str)  # event_id

    def __init__(self, calendar_event: Any, i18n: I18nQtManager, parent: Optional[QWidget] = None):
        """
        Initialize event card.

        Args:
            calendar_event: CalendarEvent instance
            i18n: Internationalization manager
            parent: Parent widget
        """
        super().__init__(calendar_event, i18n, parent)
        self.setup_ui()

    def setup_ui(self):
        """Set up event card UI."""
        self.setup_base_ui()
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            PAGE_COMPACT_SPACING, PAGE_DENSE_SPACING, PAGE_COMPACT_SPACING, PAGE_DENSE_SPACING
        )
        layout.setSpacing(PAGE_DENSE_SPACING)

        # Title
        self.title_label = QLabel(self.calendar_event.title)
        self.title_label.setProperty("role", ROLE_EVENT_TITLE)
        self.title_label.setWordWrap(True)
        layout.addWidget(self.title_label)

        # Time
        self.time_label = QLabel(self._get_formatted_time_short())
        self.time_label.setProperty("role", ROLE_EVENT_TIME)
        layout.addWidget(self.time_label)

    def _get_formatted_time_short(self) -> str:
        """Get shortened localized time string."""
        bounds = _event_bounds(self.calendar_event)
        if bounds is not None:
            start_dt, end_dt = bounds
            return f"{format_localized_datetime(start_dt, include_date=False)} - {format_localized_datetime(end_dt, include_date=False)}"
        return f"{self.calendar_event.start_time} - {self.calendar_event.end_time}"

    def update_translations(self):
        """Update labels on language change."""
        super().update_translations()
        if self.time_label:
            self.time_label.setText(self._get_formatted_time_short())

    def mousePressEvent(self, mouse_event):
        """Handle mouse press event."""
        if mouse_event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.calendar_event.id)
            mouse_event.accept()
        else:
            super().mousePressEvent(mouse_event)


class MonthView(BaseWidget):
    """
    Month calendar view.
    """

    date_changed = Signal(datetime)
    event_clicked = Signal(str)  # event_id
    date_clicked = Signal(datetime)  # NEW: Emitted when an empty area of a day is clicked

    def __init__(self, calendar_manager, i18n: I18nQtManager, parent: Optional[QWidget] = None):
        """
        Initialize month view.

        Args:
            calendar_manager: CalendarManager instance
            i18n: Internationalization manager
            parent: Parent widget
        """
        super().__init__(i18n, parent)
        self.calendar_manager = calendar_manager
        self.i18n = i18n

        # Current date (aware)
        self.current_date = now_local()

        self.setup_ui()

    def setup_ui(self):
        """Set up month view UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(*ZERO_MARGINS)
        layout.setSpacing(PAGE_COMPACT_SPACING)

        # Month/year header
        self.header_label = QLabel()
        self.header_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.header_label.setProperty("role", ROLE_CALENDAR_HEADER)
        layout.addWidget(self.header_label)

        # Calendar grid
        self.calendar_grid = QGridLayout()
        self.calendar_grid.setSpacing(CALENDAR_GRID_CELL_SPACING)
        self.calendar_grid.setContentsMargins(*ZERO_MARGINS)

        # Add day headers
        day_names = _get_weekday_labels(self.i18n)
        for col, day_name in enumerate(day_names):
            header = QLabel(day_name)
            header.setAlignment(Qt.AlignmentFlag.AlignCenter)
            header.setProperty("role", ROLE_CALENDAR_DAY_HEADER)
            self.calendar_grid.addWidget(header, 0, col)

        # Add calendar cells (will be populated by refresh_view)
        self.day_cells: Dict[int, QWidget] = {}

        layout.addLayout(self.calendar_grid)

        # Refresh view
        self.refresh_view()

    def refresh_view(self):
        """Refresh the calendar view with current month data."""
        # Update header
        locale = _get_ui_locale(self.i18n)
        month_date = QDate(self.current_date.year, self.current_date.month, 1)
        self.header_label.setText(locale.toString(month_date, "MMMM yyyy"))

        # Clear existing cells
        for cell in self.day_cells.values():
            cell.deleteLater()
        self.day_cells.clear()

        # Get first day of month
        first_day = self.current_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        # Get day of week (0=Monday, 6=Sunday)
        start_weekday = first_day.weekday()

        # Get number of days in month
        if self.current_date.month == 12:
            next_month = first_day.replace(year=first_day.year + 1, month=1)
        else:
            next_month = first_day.replace(month=first_day.month + 1)
        days_in_month = (next_month - first_day).days

        # Load events for the month
        month_start = first_day
        month_end = next_month
        events = self._load_events(month_start, month_end)

        # Group events by overlap with each visible day.
        events_by_day: Dict[int, List[Any]] = {day: [] for day in range(1, days_in_month + 1)}
        day_windows: Dict[int, Tuple[datetime, datetime]] = {}
        for day in range(1, days_in_month + 1):
            day_start = first_day + timedelta(days=day - 1)
            day_windows[day] = (day_start, day_start + timedelta(days=1))

        for calendar_event in events:
            bounds = _event_bounds(calendar_event)
            if bounds is None:
                continue
            event_start, event_end = bounds

            for day, (day_start, day_end) in day_windows.items():
                if event_start < day_end and event_end > day_start:
                    events_by_day[day].append(calendar_event)

        for day_events in events_by_day.values():
            day_events.sort(key=_event_sort_key)

        # Create calendar cells
        row = 1
        col = start_weekday

        for day in range(1, days_in_month + 1):
            # Create day cell
            day_date = first_day + timedelta(days=day - 1)
            cell = self._create_day_cell(day_date, events_by_day.get(day, []))
            self.calendar_grid.addWidget(cell, row, col)
            self.day_cells[day] = cell

            # Move to next cell
            col += 1
            if col > 6:
                col = 0
                row += 1

    def _create_day_cell(self, day_date: datetime, events: List[Any]) -> QWidget:
        """
        Create a day cell widget.

        Args:
            day_date: Date for this cell
            events: List of events for this day

        Returns:
            Day cell widget
        """
        cell = ClickableDayFrame(day_date)
        cell.clicked.connect(self.date_clicked.emit)
        cell.setFrameStyle(QFrame.Shape.Box)
        cell.setMinimumHeight(CALENDAR_DAY_CELL_MIN_HEIGHT)
        cell.setProperty("role", ROLE_CALENDAR_DAY_CELL)

        layout = QVBoxLayout(cell)
        layout.setContentsMargins(
            PAGE_DENSE_SPACING, PAGE_DENSE_SPACING, PAGE_DENSE_SPACING, PAGE_DENSE_SPACING
        )
        layout.setSpacing(PAGE_DENSE_SPACING)

        # Day number
        day_label = QLabel(str(day_date.day))
        day_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        day_label.setProperty("role", ROLE_CALENDAR_DAY_NUMBER)
        layout.addWidget(day_label)

        # Event indicators (show up to 3 events)
        for calendar_event in events[:3]:
            indicator = QPushButton(STATUS_INDICATOR_SYMBOL)
            indicator.setFlat(True)
            indicator.setCursor(Qt.CursorShape.PointingHandCursor)
            indicator.setToolTip(getattr(calendar_event, "title", ""))
            indicator.setProperty("role", ROLE_EVENT_INDICATOR)
            indicator.setProperty("source", calendar_event.source)
            indicator.clicked.connect(
                lambda _checked=False, event_id=calendar_event.id: self.event_clicked.emit(event_id)
            )
            layout.addWidget(indicator)

        # Show "+N more" if there are more events
        if len(events) > 3:
            more_label = QLabel(_format_more_events_text(self.i18n, len(events) - 3))
            more_label.setProperty("role", ROLE_MORE_EVENTS)
            layout.addWidget(more_label)

        layout.addStretch()

        return cell

    def _load_events(self, start_date: datetime, end_date: datetime) -> List[Any]:
        """
        Load events from calendar manager.

        Args:
            start_date: Start date
            end_date: End date

        Returns:
            List of events
        """
        return _load_events_safe(self.calendar_manager, start_date, end_date)

    def set_date(self, date: datetime):
        """
        Set the current date and refresh view.

        Args:
            date: New date
        """
        self.current_date = date
        self.refresh_view()
        self.date_changed.emit(date)

    def next_month(self):
        """Navigate to next month."""
        if self.current_date.month == 12:
            new_date = self.current_date.replace(year=self.current_date.year + 1, month=1)
        else:
            new_date = self.current_date.replace(month=self.current_date.month + 1)
        self.set_date(new_date)

    def prev_month(self):
        """Navigate to previous month."""
        if self.current_date.month == 1:
            new_date = self.current_date.replace(year=self.current_date.year - 1, month=12)
        else:
            new_date = self.current_date.replace(month=self.current_date.month - 1)
        self.set_date(new_date)

    def today(self):
        """Navigate to today."""
        self.set_date(now_local())


class WeekView(BaseWidget):
    """
    Week calendar view.
    """

    date_changed = Signal(datetime)
    event_clicked = Signal(str)  # event_id
    date_clicked = Signal(datetime)  # NEW: Emitted when an empty area of a day is clicked

    def __init__(self, calendar_manager, i18n: I18nQtManager, parent: Optional[QWidget] = None):
        """
        Initialize week view.

        Args:
            calendar_manager: CalendarManager instance
            i18n: Internationalization manager
            parent: Parent widget
        """
        super().__init__(i18n, parent)
        self.calendar_manager = calendar_manager
        self.i18n = i18n

        # Current date (aware)
        self.current_date = now_local()

        self.setup_ui()

    def setup_ui(self):
        """Set up week view UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(*ZERO_MARGINS)
        layout.setSpacing(PAGE_COMPACT_SPACING)

        # Week header
        self.header_label = QLabel()
        self.header_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.header_label.setProperty("role", ROLE_CALENDAR_HEADER)
        layout.addWidget(self.header_label)

        # Scroll area for week grid
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # Week grid container
        week_container = QWidget()
        self.week_grid = QGridLayout(week_container)
        self.week_grid.setSpacing(CALENDAR_GRID_CELL_SPACING)
        self.week_grid.setContentsMargins(*ZERO_MARGINS)

        scroll.setWidget(week_container)
        layout.addWidget(scroll)

        # Refresh view
        self.refresh_view()

    def refresh_view(self):
        """Refresh the week view with current week data."""
        # Get week start (Monday)
        week_start = (self.current_date - timedelta(days=self.current_date.weekday())).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        week_end = week_start + timedelta(days=7)
        week_end_display = week_end - timedelta(days=1)
        locale = _get_ui_locale(self.i18n)

        # Update header
        start_qdate = QDate(week_start.year, week_start.month, week_start.day)
        end_qdate = QDate(week_end_display.year, week_end_display.month, week_end_display.day)
        self.header_label.setText(
            f"{locale.toString(start_qdate, 'MMM dd')} - {locale.toString(end_qdate, 'MMM dd, yyyy')}"
        )

        # Clear existing grid
        while self.week_grid.count():
            item = self.week_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Add day headers
        day_names = _get_weekday_labels(self.i18n)
        for col, day_name in enumerate(day_names):
            date = week_start + timedelta(days=col)
            header = QLabel(f"{day_name}\n{date.day}")
            header.setAlignment(Qt.AlignmentFlag.AlignCenter)
            header.setProperty("role", ROLE_CALENDAR_WEEK_HEADER)
            self.week_grid.addWidget(header, 0, col)

        # Load events for the week
        events = self._load_events(week_start, week_end)

        # Group events by overlap with each day in this week.
        events_by_day: Dict[int, List[Any]] = {day: [] for day in range(7)}
        day_windows: Dict[int, Tuple[datetime, datetime]] = {}
        for day in range(7):
            day_start = week_start + timedelta(days=day)
            day_windows[day] = (day_start, day_start + timedelta(days=1))

        for calendar_event in events:
            bounds = _event_bounds(calendar_event)
            if bounds is None:
                continue
            event_start, event_end = bounds

            for day, (day_start, day_end) in day_windows.items():
                if event_start < day_end and event_end > day_start:
                    events_by_day[day].append(calendar_event)

        for day_events in events_by_day.values():
            day_events.sort(key=_event_sort_key)

        # Create day columns
        for col in range(7):
            day_start = week_start + timedelta(days=col)
            day_events = events_by_day.get(col, [])
            day_column = self._create_day_column(day_start, day_events)
            self.week_grid.addWidget(day_column, 1, col)

    def _create_day_column(self, day_date: datetime, events: List[Any]) -> QWidget:
        """
        Create a day column with events.

        Args:
            day_date: Date for this column
            events: List of events for this day

        Returns:
            Day column widget
        """
        column = ClickableDayWidget(day_date)
        column.clicked.connect(self.date_clicked.emit)
        column.setProperty("role", ROLE_CALENDAR_DAY_COLUMN)
        layout = QVBoxLayout(column)
        layout.setContentsMargins(*ZERO_MARGINS)
        layout.setSpacing(PAGE_DENSE_SPACING)

        sorted_events = sorted(events, key=_event_sort_key)

        # Add event cards
        for calendar_event in sorted_events:
            card = EventCard(calendar_event, self.i18n)
            card.clicked.connect(self.event_clicked.emit)
            layout.addWidget(card)

        layout.addStretch()

        return column

    def _load_events(self, start_date: datetime, end_date: datetime) -> List[Any]:
        """
        Load events from calendar manager.

        Args:
            start_date: Start date
            end_date: End date

        Returns:
            List of events
        """
        return _load_events_safe(self.calendar_manager, start_date, end_date)

    def set_date(self, date: datetime):
        """
        Set the current date and refresh view.

        Args:
            date: New date
        """
        self.current_date = date
        self.refresh_view()
        self.date_changed.emit(date)

    def next_week(self):
        """Navigate to next week."""
        new_date = self.current_date + timedelta(days=7)
        self.set_date(new_date)

    def prev_week(self):
        """Navigate to previous week."""
        new_date = self.current_date - timedelta(days=7)
        self.set_date(new_date)

    def today(self):
        """Navigate to today."""
        self.set_date(now_local())


class DayView(BaseWidget):
    """
    Day calendar view.
    """

    date_changed = Signal(datetime)
    event_clicked = Signal(str)  # event_id

    def __init__(self, calendar_manager, i18n: I18nQtManager, parent: Optional[QWidget] = None):
        """
        Initialize day view.

        Args:
            calendar_manager: CalendarManager instance
            i18n: Internationalization manager
            parent: Parent widget
        """
        super().__init__(i18n, parent)
        self.calendar_manager = calendar_manager
        self.i18n = i18n

        # Current date (aware)
        self.current_date = to_local_datetime(datetime.now())

        self.setup_ui()

    def setup_ui(self):
        """Set up day view UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(*ZERO_MARGINS)
        layout.setSpacing(PAGE_COMPACT_SPACING)

        # Day header
        self.header_label = QLabel()
        self.header_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.header_label.setProperty("role", ROLE_CALENDAR_HEADER)
        layout.addWidget(self.header_label)

        # Scroll area for events
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        # Events container
        self.events_container = QWidget()
        self.events_container.setProperty("role", ROLE_CALENDAR_EVENTS_CONTAINER)
        self.events_layout = QVBoxLayout(self.events_container)
        self.events_layout.setContentsMargins(
            PAGE_COMPACT_SPACING,
            PAGE_COMPACT_SPACING,
            PAGE_COMPACT_SPACING,
            PAGE_COMPACT_SPACING,
        )
        self.events_layout.setSpacing(PAGE_COMPACT_SPACING)

        scroll.setWidget(self.events_container)
        layout.addWidget(scroll)

        # Refresh view
        self.refresh_view()

    def refresh_view(self):
        """Refresh the day view with current day data."""
        # Update header
        locale = _get_ui_locale(self.i18n)
        current_qdate = QDate(
            self.current_date.year, self.current_date.month, self.current_date.day
        )
        self.header_label.setText(locale.toString(current_qdate, QLocale.FormatType.LongFormat))

        # Clear existing events
        while self.events_layout.count():
            item = self.events_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Load events for the day
        day_start = self.current_date.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        events = self._load_events(day_start, day_end)

        sorted_events = sorted(events, key=_event_sort_key)

        # Add event cards
        if sorted_events:
            for calendar_event in sorted_events:
                card = EventCard(calendar_event, self.i18n)
                card.clicked.connect(self.event_clicked.emit)
                self.events_layout.addWidget(card)
        else:
            # No events message
            no_events_label = QLabel(self.i18n.t("calendar_hub.calendar_view.no_events"))
            no_events_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            no_events_label.setProperty("role", ROLE_NO_EVENTS)
            self.events_layout.addWidget(no_events_label)

        self.events_layout.addStretch()

    def _load_events(self, start_date: datetime, end_date: datetime) -> List[Any]:
        """
        Load events from calendar manager.

        Args:
            start_date: Start date
            end_date: End date

        Returns:
            List of events
        """
        return _load_events_safe(self.calendar_manager, start_date, end_date)

    def set_date(self, date: datetime):
        """
        Set the current date and refresh view.

        Args:
            date: New date
        """
        self.current_date = date
        self.refresh_view()
        self.date_changed.emit(date)

    def next_day(self):
        """Navigate to next day."""
        new_date = self.current_date + timedelta(days=1)
        self.set_date(new_date)

    def prev_day(self):
        """Navigate to previous day."""
        new_date = self.current_date - timedelta(days=1)
        self.set_date(new_date)

    def today(self):
        """Navigate to today."""
        self.set_date(now_local())
