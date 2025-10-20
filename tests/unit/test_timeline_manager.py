from __future__ import annotations

import logging
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

import pytest
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
pytest.importorskip('cryptography')

from core.timeline.manager import (
    TimelineManager,
    to_local_naive,
    MISSING_TRANSCRIPT_MESSAGE,
    UNREADABLE_TRANSCRIPT_MESSAGE,
)
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


def test_get_timeline_events_includes_future_when_past_exceeds_page():
    center_time = datetime(2024, 5, 20, 12, 0, tzinfo=timezone.utc)

    past_events = []
    for index in range(5):
        start = center_time - timedelta(hours=2 + index)
        end = start + timedelta(minutes=45)
        past_events.append(
            CalendarEvent(
                id=f'past-{index}',
                title=f'Past #{index}',
                start_time=iso_z(start),
                end_time=iso_z(end),
            )
        )

    future_events = []
    for index in range(2):
        start = center_time + timedelta(hours=1 + index)
        end = start + timedelta(minutes=30)
        future_events.append(
            CalendarEvent(
                id=f'future-{index}',
                title=f'Future #{index}',
                start_time=iso_z(start),
                end_time=iso_z(end),
            )
        )

    manager = TimelineManagerForTest(
        calendar_manager=DummyCalendarManager(past_events + future_events),
        db_connection=None,
    )

    result = manager.get_timeline_events(
        center_time=center_time,
        past_days=1,
        future_days=1,
        page_size=3,
    )

    # 过去事件应按时间倒序分页
    assert [item['event'].id for item in result['past_events']] == [
        'past-0', 'past-1', 'past-2'
    ]

    future_ids = [item['event'].id for item in result['future_events']]
    assert future_ids == ['future-0', 'future-1']
    assert result['total_count'] == len(past_events) + len(future_events)


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


def test_search_events_filters_attendees_without_errors(monkeypatch):
    base_row = {
        'event_type': 'Event',
        'start_time': '2024-03-05T09:00:00Z',
        'end_time': '2024-03-05T10:00:00Z',
        'location': None,
        'description': None,
        'reminder_minutes': None,
        'recurrence_rule': None,
        'source': 'local',
        'external_id': None,
        'created_at': '2024-03-01T00:00:00Z',
        'updated_at': '2024-03-01T00:00:00Z',
    }

    row_without_attendees = {
        **base_row,
        'id': 'no-attendees',
        'title': 'Solo Work',
        'attendees': 'null',
        'is_readonly': 0,
    }

    row_with_attendees = {
        **base_row,
        'id': 'with-attendees',
        'title': 'Team Sync',
        'attendees': '["alice@example.com"]',
        'is_readonly': 0,
    }

    no_attendees_event = CalendarEvent.from_db_row(row_without_attendees)
    with_attendees_event = CalendarEvent.from_db_row(row_with_attendees)

    events = [with_attendees_event, no_attendees_event]

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

    filtered = manager.search_events(
        query='Team',
        filters={'attendees': ['alice@example.com']},
    )

    assert [item['event'].id for item in filtered] == ['with-attendees']


def test_get_search_snippet_returns_missing_message(monkeypatch, caplog, tmp_path):
    event = CalendarEvent(
        id='missing-transcript',
        title='Weekly Sync',
        start_time=iso_z(datetime(2024, 3, 5, 9, 0, tzinfo=timezone.utc)),
        end_time=iso_z(datetime(2024, 3, 5, 10, 0, tzinfo=timezone.utc)),
    )

    missing_path = tmp_path / 'missing.txt'

    manager = TimelineManagerForTest(
        calendar_manager=DummyCalendarManager([event]),
        db_connection=None,
    )

    monkeypatch.setattr(
        EventAttachment,
        'get_by_event_id',
        staticmethod(
            lambda db, event_id: [
                SimpleNamespace(
                    attachment_type='transcript',
                    file_path=str(missing_path),
                )
            ]
        ),
    )

    with caplog.at_level(logging.WARNING, logger='echonote.timeline.manager'):
        snippet = manager.get_search_snippet(event, 'notes')

    assert snippet == MISSING_TRANSCRIPT_MESSAGE
    assert 'Transcript file not found' in caplog.text


def test_get_search_snippet_returns_unreadable_message(monkeypatch, caplog, tmp_path):
    event = CalendarEvent(
        id='corrupt-transcript',
        title='Design Review',
        start_time=iso_z(datetime(2024, 3, 6, 9, 0, tzinfo=timezone.utc)),
        end_time=iso_z(datetime(2024, 3, 6, 10, 0, tzinfo=timezone.utc)),
    )

    corrupt_path = tmp_path / 'corrupt.txt'
    corrupt_path.write_bytes(b'\xff\xfe\xfd')

    manager = TimelineManagerForTest(
        calendar_manager=DummyCalendarManager([event]),
        db_connection=None,
    )

    monkeypatch.setattr(
        EventAttachment,
        'get_by_event_id',
        staticmethod(
            lambda db, event_id: [
                SimpleNamespace(
                    attachment_type='transcript',
                    file_path=str(corrupt_path),
                )
            ]
        ),
    )

    with caplog.at_level(logging.ERROR, logger='echonote.timeline.manager'):
        snippet = manager.get_search_snippet(event, 'notes')

    assert snippet == UNREADABLE_TRANSCRIPT_MESSAGE
    assert 'Failed to decode transcript' in caplog.text
