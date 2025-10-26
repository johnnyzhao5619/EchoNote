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
from typing import Optional, List, Dict, Any

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QScrollArea, QFrame, QPushButton
)
from PySide6.QtCore import Qt, Signal, QDate
from PySide6.QtGui import QColor, QPalette

from utils.i18n import I18nQtManager


logger = logging.getLogger('echonote.ui.calendar_view')


class EventCard(QFrame):
    """
    Visual representation of a calendar event.
    """
    
    clicked = Signal(str)  # event_id
    
    def __init__(
        self,
        event: Any,
        color: str,
        parent: Optional[QWidget] = None
    ):
        """
        Initialize event card.
        
        Args:
            event: CalendarEvent instance
            color: Color code for the event source
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.event = event
        self.color = color
        
        self.setup_ui()
    
    def setup_ui(self):
        """Set up event card UI."""
        self.setObjectName('event_card')
        self.setFrameStyle(QFrame.Shape.StyledPanel)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        # Set background color based on source
        self.setStyleSheet(f"""
            #event_card {{
                background-color: {self.color};
                border-radius: 4px;
                padding: 4px;
            }}
            #event_card:hover {{
                border: 2px solid #333;
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)
        
        # Event title
        title_label = QLabel(self.event.title)
        title_label.setWordWrap(True)
        title_label.setStyleSheet("font-weight: bold; color: white;")
        layout.addWidget(title_label)
        
        # Event time
        # Parse datetime if it's a string
        if isinstance(self.event.start_time, str):
            start_dt = datetime.fromisoformat(self.event.start_time)
            end_dt = datetime.fromisoformat(self.event.end_time)
        else:
            start_dt = self.event.start_time
            end_dt = self.event.end_time
        
        start_time = start_dt.strftime('%H:%M')
        end_time = end_dt.strftime('%H:%M')
        time_label = QLabel(f"{start_time} - {end_time}")
        time_label.setStyleSheet("font-size: 10px; color: white;")
        layout.addWidget(time_label)
    
    def mousePressEvent(self, event):
        """Handle mouse press event."""
        self.clicked.emit(self.event.id)
        super().mousePressEvent(event)


class MonthView(QWidget):
    """
    Month calendar view.
    """
    
    date_changed = Signal(datetime)
    event_clicked = Signal(str)  # event_id
    
    def __init__(
        self,
        calendar_manager,
        i18n: I18nQtManager,
        parent: Optional[QWidget] = None
    ):
        """
        Initialize month view.
        
        Args:
            calendar_manager: CalendarManager instance
            i18n: Internationalization manager
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.calendar_manager = calendar_manager
        self.i18n = i18n
        
        # Current date
        self.current_date = datetime.now()
        
        # Color mapping for event sources
        self.source_colors = {
            'local': '#2196F3',    # Blue
            'google': '#EA4335',   # Red
            'outlook': '#FF6F00'   # Orange
        }
        
        self.setup_ui()
    
    def setup_ui(self):
        """Set up month view UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        
        # Month/year header
        self.header_label = QLabel()
        self.header_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.header_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(self.header_label)
        
        # Calendar grid
        self.calendar_grid = QGridLayout()
        self.calendar_grid.setSpacing(1)
        
        # Add day headers
        day_names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        for col, day_name in enumerate(day_names):
            header = QLabel(day_name)
            header.setAlignment(Qt.AlignmentFlag.AlignCenter)
            header.setStyleSheet("font-weight: bold; padding: 5px;")
            self.calendar_grid.addWidget(header, 0, col)
        
        # Add calendar cells (will be populated by refresh_view)
        self.day_cells: Dict[int, QWidget] = {}
        
        layout.addLayout(self.calendar_grid)
        
        # Refresh view
        self.refresh_view()
    
    def refresh_view(self):
        """Refresh the calendar view with current month data."""
        # Update header
        self.header_label.setText(
            self.current_date.strftime('%B %Y')
        )
        
        # Clear existing cells
        for cell in self.day_cells.values():
            cell.deleteLater()
        self.day_cells.clear()
        
        # Get first day of month
        first_day = self.current_date.replace(day=1)
        
        # Get day of week (0=Monday, 6=Sunday)
        start_weekday = first_day.weekday()
        
        # Get number of days in month
        if self.current_date.month == 12:
            next_month = self.current_date.replace(
                year=self.current_date.year + 1, month=1, day=1
            )
        else:
            next_month = self.current_date.replace(
                month=self.current_date.month + 1, day=1
            )
        days_in_month = (next_month - first_day).days
        
        # Load events for the month
        month_start = first_day
        month_end = next_month - timedelta(days=1)
        events = self._load_events(month_start, month_end)
        
        # Group events by day
        events_by_day: Dict[int, List[Any]] = {}
        for event in events:
            # Parse start_time if it's a string
            if isinstance(event.start_time, str):
                start_dt = datetime.fromisoformat(event.start_time)
            else:
                start_dt = event.start_time
            
            day = start_dt.day
            if day not in events_by_day:
                events_by_day[day] = []
            events_by_day[day].append(event)
        
        # Create calendar cells
        row = 1
        col = start_weekday
        
        for day in range(1, days_in_month + 1):
            # Create day cell
            cell = self._create_day_cell(day, events_by_day.get(day, []))
            self.calendar_grid.addWidget(cell, row, col)
            self.day_cells[day] = cell
            
            # Move to next cell
            col += 1
            if col > 6:
                col = 0
                row += 1
    
    def _create_day_cell(
        self,
        day: int,
        events: List[Any]
    ) -> QWidget:
        """
        Create a day cell widget.
        
        Args:
            day: Day number
            events: List of events for this day
        
        Returns:
            Day cell widget
        """
        cell = QFrame()
        cell.setFrameStyle(QFrame.Shape.Box)
        cell.setMinimumHeight(80)
        
        layout = QVBoxLayout(cell)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)
        
        # Day number
        day_label = QLabel(str(day))
        day_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(day_label)
        
        # Event indicators (show up to 3 events)
        for event in events[:3]:
            color = self.source_colors.get(event.source, '#999999')
            indicator = QLabel('●')
            indicator.setStyleSheet(f"color: {color};")
            layout.addWidget(indicator)
        
        # Show "+N more" if there are more events
        if len(events) > 3:
            more_label = QLabel(f"+{len(events) - 3} more")
            more_label.setStyleSheet("font-size: 10px; color: #666;")
            layout.addWidget(more_label)
        
        layout.addStretch()
        
        return cell
    
    def _load_events(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> List[Any]:
        """
        Load events from calendar manager.
        
        Args:
            start_date: Start date
            end_date: End date
        
        Returns:
            List of events
        """
        try:
            events = self.calendar_manager.get_events(
                start_date=start_date,
                end_date=end_date
            )
            return events
        except Exception as e:
            logger.error(f"Error loading events: {e}")
            return []
    
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
            new_date = self.current_date.replace(
                year=self.current_date.year + 1, month=1
            )
        else:
            new_date = self.current_date.replace(
                month=self.current_date.month + 1
            )
        self.set_date(new_date)
    
    def prev_month(self):
        """Navigate to previous month."""
        if self.current_date.month == 1:
            new_date = self.current_date.replace(
                year=self.current_date.year - 1, month=12
            )
        else:
            new_date = self.current_date.replace(
                month=self.current_date.month - 1
            )
        self.set_date(new_date)
    
    def today(self):
        """Navigate to today."""
        self.set_date(datetime.now())


class WeekView(QWidget):
    """
    Week calendar view.
    """
    
    date_changed = Signal(datetime)
    event_clicked = Signal(str)  # event_id
    
    def __init__(
        self,
        calendar_manager,
        i18n: I18nQtManager,
        parent: Optional[QWidget] = None
    ):
        """
        Initialize week view.
        
        Args:
            calendar_manager: CalendarManager instance
            i18n: Internationalization manager
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.calendar_manager = calendar_manager
        self.i18n = i18n
        
        # Current date
        self.current_date = datetime.now()
        
        # Color mapping for event sources
        self.source_colors = {
            'local': '#2196F3',    # Blue
            'google': '#EA4335',   # Red
            'outlook': '#FF6F00'   # Orange
        }
        
        self.setup_ui()
    
    def setup_ui(self):
        """Set up week view UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        
        # Week header
        self.header_label = QLabel()
        self.header_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.header_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(self.header_label)
        
        # Scroll area for week grid
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        
        # Week grid container
        week_container = QWidget()
        self.week_grid = QGridLayout(week_container)
        self.week_grid.setSpacing(1)
        
        scroll.setWidget(week_container)
        layout.addWidget(scroll)
        
        # Refresh view
        self.refresh_view()
    
    def refresh_view(self):
        """Refresh the week view with current week data."""
        # Get week start (Monday)
        week_start = self.current_date - timedelta(
            days=self.current_date.weekday()
        )
        week_end = week_start + timedelta(days=6)
        
        # Update header
        self.header_label.setText(
            f"{week_start.strftime('%b %d')} - "
            f"{week_end.strftime('%b %d, %Y')}"
        )
        
        # Clear existing grid
        while self.week_grid.count():
            item = self.week_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # Add day headers
        day_names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        for col, day_name in enumerate(day_names):
            date = week_start + timedelta(days=col)
            header = QLabel(f"{day_name}\n{date.day}")
            header.setAlignment(Qt.AlignmentFlag.AlignCenter)
            header.setStyleSheet("font-weight: bold; padding: 10px;")
            self.week_grid.addWidget(header, 0, col)
        
        # Load events for the week
        events = self._load_events(week_start, week_end)
        
        # Group events by day
        events_by_day: Dict[int, List[Any]] = {}
        for event in events:
            # Parse start_time if it's a string
            if isinstance(event.start_time, str):
                start_dt = datetime.fromisoformat(event.start_time)
            else:
                start_dt = event.start_time
            
            weekday = start_dt.weekday()
            if weekday not in events_by_day:
                events_by_day[weekday] = []
            events_by_day[weekday].append(event)
        
        # Create day columns
        for col in range(7):
            day_events = events_by_day.get(col, [])
            day_column = self._create_day_column(day_events)
            self.week_grid.addWidget(day_column, 1, col)
    
    def _create_day_column(self, events: List[Any]) -> QWidget:
        """
        Create a day column with events.
        
        Args:
            events: List of events for this day
        
        Returns:
            Day column widget
        """
        column = QWidget()
        layout = QVBoxLayout(column)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        
        # Sort events by start time
        def get_start_time(e):
            if isinstance(e.start_time, str):
                return datetime.fromisoformat(e.start_time)
            return e.start_time
        
        sorted_events = sorted(events, key=get_start_time)
        
        # Add event cards
        for event in sorted_events:
            color = self.source_colors.get(event.source, '#999999')
            card = EventCard(event, color)
            card.clicked.connect(self.event_clicked.emit)
            layout.addWidget(card)
        
        layout.addStretch()
        
        return column
    
    def _load_events(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> List[Any]:
        """
        Load events from calendar manager.
        
        Args:
            start_date: Start date
            end_date: End date
        
        Returns:
            List of events
        """
        try:
            events = self.calendar_manager.get_events(
                start_date=start_date,
                end_date=end_date
            )
            return events
        except Exception as e:
            logger.error(f"Error loading events: {e}")
            return []
    
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
        self.set_date(datetime.now())


class DayView(QWidget):
    """
    Day calendar view.
    """
    
    date_changed = Signal(datetime)
    event_clicked = Signal(str)  # event_id
    
    def __init__(
        self,
        calendar_manager,
        i18n: I18nQtManager,
        parent: Optional[QWidget] = None
    ):
        """
        Initialize day view.
        
        Args:
            calendar_manager: CalendarManager instance
            i18n: Internationalization manager
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.calendar_manager = calendar_manager
        self.i18n = i18n
        
        # Current date
        self.current_date = datetime.now()
        
        # Color mapping for event sources
        self.source_colors = {
            'local': '#2196F3',    # Blue
            'google': '#EA4335',   # Red
            'outlook': '#FF6F00'   # Orange
        }
        
        self.setup_ui()
    
    def setup_ui(self):
        """Set up day view UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        
        # Day header
        self.header_label = QLabel()
        self.header_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.header_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(self.header_label)
        
        # Scroll area for events
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        
        # Events container
        self.events_container = QWidget()
        self.events_layout = QVBoxLayout(self.events_container)
        self.events_layout.setContentsMargins(10, 10, 10, 10)
        self.events_layout.setSpacing(10)
        
        scroll.setWidget(self.events_container)
        layout.addWidget(scroll)
        
        # Refresh view
        self.refresh_view()
    
    def refresh_view(self):
        """Refresh the day view with current day data."""
        # Update header
        self.header_label.setText(
            self.current_date.strftime('%A, %B %d, %Y')
        )
        
        # Clear existing events
        while self.events_layout.count():
            item = self.events_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # Load events for the day
        day_start = self.current_date.replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        day_end = day_start + timedelta(days=1)
        events = self._load_events(day_start, day_end)
        
        # Sort events by start time
        def get_start_time(e):
            if isinstance(e.start_time, str):
                return datetime.fromisoformat(e.start_time)
            return e.start_time
        
        sorted_events = sorted(events, key=get_start_time)
        
        # Add event cards
        if sorted_events:
            for event in sorted_events:
                color = self.source_colors.get(event.source, '#999999')
                card = EventCard(event, color)
                card.clicked.connect(self.event_clicked.emit)
                self.events_layout.addWidget(card)
        else:
            # No events message
            no_events_label = QLabel("No events for this day")
            no_events_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            no_events_label.setStyleSheet("color: #999; font-style: italic;")
            self.events_layout.addWidget(no_events_label)
        
        self.events_layout.addStretch()
    
    def _load_events(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> List[Any]:
        """
        Load events from calendar manager.
        
        Args:
            start_date: Start date
            end_date: End date
        
        Returns:
            List of events
        """
        try:
            events = self.calendar_manager.get_events(
                start_date=start_date,
                end_date=end_date
            )
            return events
        except Exception as e:
            logger.error(f"Error loading events: {e}")
            return []
    
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
        self.set_date(datetime.now())
