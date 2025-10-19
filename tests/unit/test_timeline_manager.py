from __future__ import annotations

import sys
from pathlib import Path
from datetime import datetime, timezone

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
pytest.importorskip('cryptography')

from core.timeline.manager import TimelineManager, to_local_naive
from data.database.models import CalendarEvent, EventAttachment


class DummyCalendarManager:
    def __init__(self, events):
        self._events = list(events)

    def get_events(self, start_date=None, end_date=None):
        return list(self._events)

    def get_event(self, event_id):
        for event in self._events:
            if event.id == event_id:
                return event
        return None


class TimelineManagerForTest(TimelineManager):
    def get_event_artifacts(self, event_id: str):  # noqa: D401
        return {'recording': None, 'transcript': None, 'attachments': []}

    def get_auto_task(self, event_id: str):  # noqa: D401
        return {'enable_transcription': True}


def iso_z(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')


def test_get_timeline_events_handles_mixed_timezones():
    center_time = datetime(2024, 3, 1, 12, 0, tzinfo=timezone.utc)

    events = [
        CalendarEvent(
            id='recent-past',
            title='Recent Past',
            start_time=iso_z(datetime(2024, 3, 1, 2, 0, tzinfo=timezone.utc)),
            end_time=iso_z(datetime(2024, 3, 1, 3, 0, tzinfo=timezone.utc)),
        ),
        CalendarEvent(
            id='offset-past',
            title='Offset Past',
            start_time='2024-03-01T03:00:00+08:00',
            end_time='2024-03-01T04:30:00+08:00',
        ),
        CalendarEvent(
            id='future',
            title='Future Event',
            start_time=iso_z(datetime(2024, 3, 1, 15, 0, tzinfo=timezone.utc)),
            end_time=iso_z(datetime(2024, 3, 1, 16, 0, tzinfo=timezone.utc)),
        ),
    ]

    manager = TimelineManagerForTest(
        calendar_manager=DummyCalendarManager(events),
        db_connection=None,
    )

    result = manager.get_timeline_events(
        center_time=center_time,
        past_days=1,
        future_days=1,
    )

    past_ids = [item['event'].id for item in result['past_events']]
    future_ids = [item['event'].id for item in result['future_events']]

    assert past_ids == ['recent-past', 'offset-past']
    assert future_ids == ['future']
    assert result['current_time'] == to_local_naive(center_time).isoformat()


def test_search_events_applies_timezone_filters(monkeypatch):
    in_range = CalendarEvent(
        id='in-range',
        title='Meeting',
        start_time='2024-03-01T08:00:00+08:00',
        end_time='2024-03-01T09:00:00+08:00',
    )
    out_of_range = CalendarEvent(
        id='out-of-range',
        title='Old Meeting',
        start_time=iso_z(datetime(2024, 2, 28, 22, 0, tzinfo=timezone.utc)),
        end_time=iso_z(datetime(2024, 2, 28, 23, 0, tzinfo=timezone.utc)),
    )

    events = [in_range, out_of_range]
    manager = TimelineManagerForTest(
        calendar_manager=DummyCalendarManager(events),
        db_connection=None,
    )

    monkeypatch.setattr(
        CalendarEvent,
        'search',
        staticmethod(lambda db, keyword=None, event_type=None, source=None: events),
    )
    monkeypatch.setattr(
        EventAttachment,
        'get_by_event_id',
        staticmethod(lambda db, event_id: []),
    )

    results = manager.search_events(
        query='Meeting',
        filters={
            'start_date': '2024-03-01T00:00:00+08:00',
            'end_date': '2024-03-02T00:00:00Z',
        },
    )

    assert [item['event'].id for item in results] == ['in-range']
