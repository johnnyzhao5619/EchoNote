from __future__ import annotations

import logging
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import List

import pytest
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
pytest.importorskip('cryptography')

from core.timeline.manager import (
    TimelineManager,
    to_local_naive,
)
from data.database.models import AutoTaskConfig, CalendarEvent, EventAttachment


class DummyCalendarManager:
    def __init__(self, events):
        self._events = list(events)

    def get_events(self, start_date=None, end_date=None, filters=None):
        return list(self._events)

    def get_event(self, event_id):
        for event in self._events:
            if event.id == event_id:
                return event
        return None


class RangeAwareCalendarManager(DummyCalendarManager):
    def get_events(self, start_date=None, end_date=None, filters=None):  # noqa: D401
        start_dt = to_local_naive(start_date) if start_date else datetime.min
        end_dt = to_local_naive(end_date) if end_date else datetime.max

        matches = []
        for event in self._events:
            event_start = to_local_naive(event.start_time)
            event_end_value = getattr(event, 'end_time', None) or event.start_time
            event_end = to_local_naive(event_end_value)

            if event_end >= start_dt and event_start <= end_dt:
                matches.append(event)

        return matches


NOOP_DB = SimpleNamespace(execute=lambda *args, **kwargs: [])


class TimelineManagerForTest(TimelineManager):
    def _get_auto_task_map(self, event_ids):  # noqa: D401
        return {
            event_id: {'enable_transcription': True}
            for event_id in event_ids
        }


class StubI18n:
    def __init__(self, mapping):
        self._mapping = dict(mapping)

    def t(self, key, **kwargs):  # noqa: D401
        return self._mapping.get(key, key)


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
        db_connection=NOOP_DB,
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


def _build_manager(events):
    return TimelineManagerForTest(
        calendar_manager=DummyCalendarManager(events),
        db_connection=NOOP_DB,
    )


def test_get_timeline_events_history_only_pagination():
    center_time = datetime(2024, 5, 20, 12, 0, tzinfo=timezone.utc)

    history = []
    for index in range(5):
        start = center_time - timedelta(hours=1 + index)
        end = start + timedelta(minutes=30)
        history.append(
            CalendarEvent(
                id=f'past-{index}',
                title=f'Past #{index}',
                start_time=iso_z(start),
                end_time=iso_z(end),
            )
        )

    manager = _build_manager(history)

    first_page = manager.get_timeline_events(
        center_time=center_time,
        past_days=1,
        future_days=1,
        page_size=2,
    )

    assert [item['event'].id for item in first_page['past_events']] == [
        'past-0', 'past-1'
    ]
    assert first_page['future_events'] == []
    assert first_page['total_count'] == len(history)
    assert first_page['future_total_count'] == 0
    assert first_page['has_more']

    second_page = manager.get_timeline_events(
        center_time=center_time,
        past_days=1,
        future_days=1,
        page_size=2,
        page=1,
    )

    assert [item['event'].id for item in second_page['past_events']] == [
        'past-2', 'past-3'
    ]
    assert second_page['future_events'] == []
    assert second_page['total_count'] == len(history)
    assert second_page['future_total_count'] == 0
    assert second_page['has_more']


def test_get_timeline_events_future_only_pagination():
    center_time = datetime(2024, 5, 20, 12, 0, tzinfo=timezone.utc)

    upcoming = []
    for index in range(4):
        start = center_time + timedelta(hours=1 + index)
        end = start + timedelta(minutes=45)
        upcoming.append(
            CalendarEvent(
                id=f'future-{index}',
                title=f'Future #{index}',
                start_time=iso_z(start),
                end_time=iso_z(end),
            )
        )

    manager = _build_manager(upcoming)

    first_page = manager.get_timeline_events(
        center_time=center_time,
        past_days=1,
        future_days=1,
        page_size=2,
    )

    assert first_page['past_events'] == []
    assert [item['event'].id for item in first_page['future_events']] == [
        'future-0', 'future-1'
    ]
    assert first_page['total_count'] == 0
    assert first_page['future_total_count'] == len(upcoming)
    assert not first_page['has_more']

    second_page = manager.get_timeline_events(
        center_time=center_time,
        past_days=1,
        future_days=1,
        page_size=2,
        page=1,
    )

    assert second_page['past_events'] == []
    assert second_page['future_events'] == []
    assert second_page['total_count'] == 0
    assert second_page['future_total_count'] == len(upcoming)
    assert not second_page['has_more']


def test_get_timeline_events_future_preserved_on_first_page():
    center_time = datetime(2024, 5, 20, 12, 0, tzinfo=timezone.utc)

    history = []
    for index in range(30):
        start = center_time - timedelta(minutes=30 + index)
        end = start + timedelta(minutes=25)
        history.append(
            CalendarEvent(
                id=f'past-{index}',
                title=f'Past #{index}',
                start_time=iso_z(start),
                end_time=iso_z(end),
            )
        )

    future = []
    for index in range(3):
        start = center_time + timedelta(hours=2 + index)
        end = start + timedelta(minutes=45)
        future.append(
            CalendarEvent(
                id=f'future-{index}',
                title=f'Future #{index}',
                start_time=iso_z(start),
                end_time=iso_z(end),
            )
        )

    manager = _build_manager(history + future)

    result = manager.get_timeline_events(
        center_time=center_time,
        past_days=2,
        future_days=2,
        page_size=10,
    )

    assert len(result['past_events']) == 10
    assert [item['event'].id for item in result['future_events']] == [
        'future-0', 'future-1', 'future-2'
    ]
    assert result['future_total_count'] == 3
    assert result['total_count'] == len(history)
    assert result['has_more']


def test_get_timeline_events_batches_past_attachments(monkeypatch):
    center_time = datetime(2024, 6, 1, 12, 0, tzinfo=timezone.utc)

    past_events = []
    for index in range(25):
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
    for index in range(3):
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

    attachment_calls = []

    def fake_get_by_event_ids(db, event_ids):
        attachment_calls.append(tuple(event_ids))
        return {event_id: [] for event_id in event_ids}

    monkeypatch.setattr(
        EventAttachment,
        'get_by_event_ids',
        staticmethod(fake_get_by_event_ids),
    )

    manager = TimelineManagerForTest(
        calendar_manager=DummyCalendarManager(past_events + future_events),
        db_connection=NOOP_DB,
    )

    result = manager.get_timeline_events(
        center_time=center_time,
        past_days=2,
        future_days=1,
        page_size=10,
    )

    expected_sorted = sorted(
        past_events,
        key=lambda evt: to_local_naive(evt.start_time),
        reverse=True,
    )
    first_page_expected = [event.id for event in expected_sorted[:10]]

    assert len(attachment_calls) == 1
    assert attachment_calls[0] == tuple(first_page_expected)

    assert len(result['past_events']) == 10
    assert result['total_count'] == len(past_events)
    assert [item['event'].id for item in result['future_events']] == [
        'future-0', 'future-1', 'future-2'
    ]
    assert result['future_total_count'] == len(future_events)

    second_page = manager.get_timeline_events(
        center_time=center_time,
        past_days=2,
        future_days=1,
        page_size=10,
        page=1,
    )

    second_page_expected = [event.id for event in expected_sorted[10:20]]

    assert len(attachment_calls) == 2
    assert attachment_calls[1] == tuple(second_page_expected)

    assert [item['event'].id for item in second_page['past_events']] == (
        second_page_expected
    )
    assert second_page['future_events'] == []


def test_get_timeline_events_mixed_across_pages_without_future_duplicates():
    center_time = datetime(2024, 5, 20, 12, 0, tzinfo=timezone.utc)

    past_events = []
    for index in range(3):
        start = center_time - timedelta(hours=1 + index)
        end = start + timedelta(minutes=30)
        past_events.append(
            CalendarEvent(
                id=f'past-{index}',
                title=f'Past #{index}',
                start_time=iso_z(start),
                end_time=iso_z(end),
            )
        )

    future_events = []
    for index in range(3):
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

    manager = _build_manager(past_events + future_events)

    first_page = manager.get_timeline_events(
        center_time=center_time,
        past_days=1,
        future_days=1,
        page_size=2,
    )

    assert [item['event'].id for item in first_page['past_events']] == [
        'past-0', 'past-1'
    ]
    assert [item['event'].id for item in first_page['future_events']] == [
        'future-0', 'future-1', 'future-2'
    ]
    assert first_page['future_total_count'] == 3
    assert first_page['has_more']

    second_page = manager.get_timeline_events(
        center_time=center_time,
        past_days=1,
        future_days=1,
        page_size=2,
        page=1,
    )

    assert [item['event'].id for item in second_page['past_events']] == ['past-2']
    assert second_page['future_events'] == []
    assert second_page['future_total_count'] == 3
    assert not second_page['has_more']


def test_get_timeline_events_batches_future_auto_tasks():
    center_time = datetime(2024, 5, 20, 12, 0, tzinfo=timezone.utc)

    future_events = []
    for index in range(12):
        start = center_time + timedelta(minutes=30 * (index + 1))
        end = start + timedelta(minutes=25)
        future_events.append(
            CalendarEvent(
                id=f'future-{index}',
                title=f'Future #{index}',
                start_time=iso_z(start),
                end_time=iso_z(end),
            )
        )

    class CountingManager(TimelineManagerForTest):
        def __init__(self, *args, configured_ids=None, **kwargs):
            super().__init__(*args, **kwargs)
            self.auto_task_calls = []
            self._configured_ids = set(configured_ids or [])

        def _get_auto_task_map(self, event_ids):  # noqa: D401
            self.auto_task_calls.append(list(event_ids))
            return {
                event_id: {'enable_transcription': True}
                for event_id in event_ids
                if event_id in self._configured_ids
            }

    configured_ids = {f'future-{index}' for index in range(0, 12, 3)}
    manager = CountingManager(
        calendar_manager=DummyCalendarManager(future_events),
        db_connection=NOOP_DB,
        configured_ids=configured_ids,
    )

    result = manager.get_timeline_events(
        center_time=center_time,
        past_days=0,
        future_days=3,
    )

    assert len(manager.auto_task_calls) == 1
    assert manager.auto_task_calls[0] == [event.id for event in future_events]

    default_config = manager._default_auto_task_config()
    assert len(result['future_events']) == len(future_events)
    for item in result['future_events']:
        event_id = item['event'].id
        auto_tasks = item['auto_tasks']
        if event_id in configured_ids:
            assert auto_tasks == {'enable_transcription': True}
        else:
            assert auto_tasks == default_config

    assert result['future_total_count'] == len(future_events)


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
        db_connection=NOOP_DB,
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
    monkeypatch.setattr(
        EventAttachment,
        'get_by_event_ids',
        staticmethod(lambda db, event_ids: {}),
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
        db_connection=NOOP_DB,
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
    monkeypatch.setattr(
        EventAttachment,
        'get_by_event_ids',
        staticmethod(lambda db, event_ids: {}),
    )

    filtered = manager.search_events(
        query='Team',
        filters={'attendees': ['alice@example.com']},
    )

    assert [item['event'].id for item in filtered] == ['with-attendees']


def test_search_events_batches_attachment_lookup(monkeypatch, tmp_path):
    event_one = CalendarEvent(
        id='event-one',
        title='Project Update',
        start_time=iso_z(datetime(2024, 3, 10, 9, 0, tzinfo=timezone.utc)),
        end_time=iso_z(datetime(2024, 3, 10, 10, 0, tzinfo=timezone.utc)),
    )
    event_two = CalendarEvent(
        id='event-two',
        title='Sprint Planning',
        start_time=iso_z(datetime(2024, 3, 11, 9, 0, tzinfo=timezone.utc)),
        end_time=iso_z(datetime(2024, 3, 11, 10, 0, tzinfo=timezone.utc)),
    )

    events = [event_one, event_two]

    transcript_path = tmp_path / 'event-one-transcript.txt'
    transcript_path.write_text('Project notes and action items.', encoding='utf-8')

    attachments_map = {
        event_one.id: [
            EventAttachment(
                event_id=event_one.id,
                attachment_type='transcript',
                file_path=str(transcript_path),
            )
        ]
    }

    batch_calls = []

    def fake_get_by_event_ids(db, event_ids):
        batch_calls.append(tuple(event_ids))
        return attachments_map

    def fail_single_lookup(db, event_id):
        raise AssertionError('single attachment lookup should not be used')

    monkeypatch.setattr(
        CalendarEvent,
        'search',
        staticmethod(lambda db, keyword=None, event_type=None, source=None: events),
    )
    monkeypatch.setattr(
        EventAttachment,
        'get_by_event_ids',
        staticmethod(fake_get_by_event_ids),
    )
    monkeypatch.setattr(
        EventAttachment,
        'get_by_event_id',
        staticmethod(fail_single_lookup),
    )

    manager = TimelineManagerForTest(
        calendar_manager=DummyCalendarManager(events),
        db_connection=NOOP_DB,
    )

    results = manager.search_events(query='notes')

    assert len(batch_calls) == 1
    assert set(batch_calls[0]) == {event_one.id, event_two.id}

    results_by_id = {item['event'].id: item for item in results}
    assert results_by_id[event_one.id]['artifacts']['transcript'] == str(
        transcript_path
    )
    assert results_by_id[event_two.id]['artifacts']['transcript'] is None
    assert results_by_id[event_one.id]['match_snippet'] is not None
    assert 'notes' in results_by_id[event_one.id]['match_snippet'].lower()


def test_search_events_future_auto_tasks(monkeypatch):
    past_event = CalendarEvent(
        id='past-event',
        title='Weekly Recap',
        start_time=iso_z(datetime(2024, 1, 5, 10, 0, tzinfo=timezone.utc)),
        end_time=iso_z(datetime(2024, 1, 5, 11, 0, tzinfo=timezone.utc)),
    )
    configured_future = CalendarEvent(
        id='configured-future',
        title='Roadmap Review',
        start_time='2099-03-15T09:00:00Z',
        end_time='2099-03-15T10:00:00Z',
    )
    default_future = CalendarEvent(
        id='default-future',
        title='Planning Session',
        start_time='2099-03-20T09:00:00Z',
        end_time='2099-03-20T10:00:00Z',
    )

    events = [past_event, configured_future, default_future]

    class AutoTaskAwareManager(TimelineManager):
        def __init__(self, calendar_manager, db_connection):
            super().__init__(calendar_manager, db_connection)
            self.auto_task_calls: List[List[str]] = []

        def _get_auto_task_map(self, event_ids):  # noqa: D401
            self.auto_task_calls.append(list(event_ids))
            return {
                'configured-future': {'enable_transcription': True}
            }

    manager = AutoTaskAwareManager(
        calendar_manager=DummyCalendarManager(events),
        db_connection=NOOP_DB,
    )

    monkeypatch.setattr(
        CalendarEvent,
        'search',
        staticmethod(lambda db, keyword=None, event_type=None, source=None: events),
    )
    monkeypatch.setattr(
        EventAttachment,
        'get_by_event_ids',
        staticmethod(lambda db, event_ids: {}),
    )

    results = manager.search_events(
        query='Review',
        include_future_auto_tasks=True,
    )

    assert manager.auto_task_calls == [[
        configured_future.id,
        default_future.id,
    ]]

    results_by_id = {item['event'].id: item for item in results}

    assert 'auto_tasks' not in results_by_id[past_event.id]
    assert results_by_id[configured_future.id]['auto_tasks'] == {
        'enable_transcription': True
    }
    assert results_by_id[default_future.id]['auto_tasks'] == (
        manager._default_auto_task_config()
    )


def test_search_events_returns_transcript_only_hits(monkeypatch, tmp_path):
    event = CalendarEvent(
        id='transcript-only',
        title='Quarterly Briefing',
        start_time=iso_z(datetime(2024, 3, 12, 9, 0, tzinfo=timezone.utc)),
        end_time=iso_z(datetime(2024, 3, 12, 10, 0, tzinfo=timezone.utc)),
        description='General updates',
    )

    transcript_path = tmp_path / 'transcript-only.txt'
    transcript_path.write_text(
        'Discussed product synergy and follow-ups.',
        encoding='utf-8',
    )

    attachments = [
        EventAttachment(
            event_id=event.id,
            attachment_type='transcript',
            file_path=str(transcript_path),
        )
    ]

    manager = TimelineManagerForTest(
        calendar_manager=DummyCalendarManager([event]),
        db_connection=NOOP_DB,
    )

    monkeypatch.setattr(
        CalendarEvent,
        'search',
        staticmethod(lambda db, keyword=None, event_type=None, source=None: []),
    )

    batch_calls = []

    def fake_get_by_event_ids(db, event_ids):
        batch_calls.append(tuple(event_ids))
        return {event.id: attachments}

    def fail_single_lookup(db, event_id):
        raise AssertionError('single attachment lookup should not be used')

    monkeypatch.setattr(
        EventAttachment,
        'get_by_event_ids',
        staticmethod(fake_get_by_event_ids),
    )
    monkeypatch.setattr(
        EventAttachment,
        'get_by_event_id',
        staticmethod(fail_single_lookup),
    )

    results = manager.search_events(
        query='Synergy',
        filters={
            'start_date': iso_z(datetime(2024, 3, 12, 8, 0, tzinfo=timezone.utc)),
            'end_date': iso_z(datetime(2024, 3, 12, 12, 0, tzinfo=timezone.utc)),
        },
    )

    assert batch_calls == [(event.id,)]
    assert [item['event'].id for item in results] == [event.id]

    artifact = results[0]['artifacts']['transcript']
    assert artifact == str(transcript_path)

    snippet = results[0]['match_snippet']
    assert snippet is not None
    assert 'transcript' in snippet.lower()


def test_search_events_transcript_hits_without_filters(monkeypatch, tmp_path):
    now = datetime.now(timezone.utc)
    event = CalendarEvent(
        id='transcript-window',
        title='Weekly Wrap',
        start_time=iso_z(now - timedelta(minutes=30)),
        end_time=iso_z(now - timedelta(minutes=5)),
        description='General notes',
    )

    transcript_path = tmp_path / 'transcript-window.txt'
    transcript_path.write_text(
        'Action items include roadmap alignment and customer outreach.',
        encoding='utf-8',
    )

    attachments = [
        EventAttachment(
            event_id=event.id,
            attachment_type='transcript',
            file_path=str(transcript_path),
        )
    ]

    manager = TimelineManagerForTest(
        calendar_manager=DummyCalendarManager([event]),
        db_connection=NOOP_DB,
    )

    monkeypatch.setattr(
        CalendarEvent,
        'search',
        staticmethod(lambda db, keyword=None, event_type=None, source=None: []),
    )

    batch_calls = []

    def fake_get_by_event_ids(db, event_ids):
        batch_calls.append(tuple(event_ids))
        return {event.id: attachments}

    def fail_single_lookup(db, event_id):
        raise AssertionError('single attachment lookup should not be used')

    monkeypatch.setattr(
        EventAttachment,
        'get_by_event_ids',
        staticmethod(fake_get_by_event_ids),
    )
    monkeypatch.setattr(
        EventAttachment,
        'get_by_event_id',
        staticmethod(fail_single_lookup),
    )

    results = manager.search_events(query='Roadmap')

    assert batch_calls == [(event.id,)]
    assert [item['event'].id for item in results] == [event.id]

    snippet = results[0]['match_snippet']
    assert snippet is not None
    assert 'transcript' in snippet.lower()


def test_search_events_transcript_hits_beyond_default_window(monkeypatch, tmp_path):
    past_time = datetime.now(timezone.utc) - timedelta(days=45)
    event = CalendarEvent(
        id='historic-transcript',
        title='Historic Meeting',
        start_time=iso_z(past_time),
        end_time=iso_z(past_time + timedelta(hours=1)),
        description='Legacy notes',
    )

    transcript_path = tmp_path / 'historic-transcript.txt'
    transcript_path.write_text(
        'Key alignment decisions captured in archival transcript.',
        encoding='utf-8',
    )

    attachments = [
        EventAttachment(
            event_id=event.id,
            attachment_type='transcript',
            file_path=str(transcript_path),
        )
    ]

    manager = TimelineManagerForTest(
        calendar_manager=RangeAwareCalendarManager([event]),
        db_connection=NOOP_DB,
    )

    monkeypatch.setattr(
        CalendarEvent,
        'search',
        staticmethod(lambda db, keyword=None, event_type=None, source=None: []),
    )
    monkeypatch.setattr(
        CalendarEvent,
        'get_time_bounds',
        staticmethod(
            lambda db, event_type=None, source=None: (
                event.start_time,
                event.end_time,
            )
        ),
    )

    monkeypatch.setattr(
        EventAttachment,
        'get_by_event_ids',
        staticmethod(lambda db, event_ids: {event.id: attachments}),
    )
    monkeypatch.setattr(
        EventAttachment,
        'get_by_event_id',
        staticmethod(lambda db, event_id: attachments if event_id == event.id else []),
    )

    results = manager.search_events(query='alignment')

    assert [item['event'].id for item in results] == [event.id]

    snippet = results[0]['match_snippet']
    assert snippet is not None
    assert 'transcript' in snippet.lower()


def test_search_events_translation_hits(monkeypatch, tmp_path):
    now = datetime.now(timezone.utc)
    event = CalendarEvent(
        id='translation-window',
        title='Weekly Wrap Translation',
        start_time=iso_z(now - timedelta(minutes=30)),
        end_time=iso_z(now - timedelta(minutes=5)),
        description='General notes',
    )

    translation_path = tmp_path / 'translation-window.txt'
    translation_path.write_text(
        'Localized roadmap alignment for international teams.',
        encoding='utf-8',
    )

    attachments = [
        EventAttachment(
            event_id=event.id,
            attachment_type='translation',
            file_path=str(translation_path),
        )
    ]

    manager = TimelineManagerForTest(
        calendar_manager=DummyCalendarManager([event]),
        db_connection=NOOP_DB,
    )

    monkeypatch.setattr(
        CalendarEvent,
        'search',
        staticmethod(lambda db, keyword=None, event_type=None, source=None: []),
    )

    batch_calls = []

    def fake_get_by_event_ids(db, event_ids):
        batch_calls.append(tuple(event_ids))
        return {event.id: attachments}

    def fail_single_lookup(db, event_id):
        raise AssertionError('single attachment lookup should not be used')

    monkeypatch.setattr(
        EventAttachment,
        'get_by_event_ids',
        staticmethod(fake_get_by_event_ids),
    )
    monkeypatch.setattr(
        EventAttachment,
        'get_by_event_id',
        staticmethod(fail_single_lookup),
    )

    results = manager.search_events(query='localized')

    assert batch_calls == [(event.id,)]
    assert [item['event'].id for item in results] == [event.id]

    snippet = results[0]['match_snippet']
    assert snippet is not None
    assert 'translation' in snippet.lower()


def test_get_search_snippet_uses_translated_prefix():
    event = CalendarEvent(
        id='prefixed-title',
        title='Weekly Sync',
        start_time=iso_z(datetime(2024, 3, 5, 9, 0, tzinfo=timezone.utc)),
        end_time=iso_z(datetime(2024, 3, 5, 10, 0, tzinfo=timezone.utc)),
        description='Discuss weekly action items',
    )

    manager = TimelineManagerForTest(
        calendar_manager=DummyCalendarManager([event]),
        db_connection=NOOP_DB,
        i18n=StubI18n({
            'timeline.snippet.title_prefix': '标题',
            'timeline.snippet.description_prefix': '描述',
        }),
    )

    snippet = manager.get_search_snippet(event, 'weekly')

    assert snippet == '标题: ...Weekly Sync...'


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
        db_connection=NOOP_DB,
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

    assert snippet == 'Transcript unavailable (file missing)'
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
        db_connection=NOOP_DB,
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

    assert snippet == 'Transcript unavailable (cannot read transcript)'
    assert 'Failed to decode transcript' in caplog.text


def test_get_search_snippet_missing_transcript_uses_translation(monkeypatch, tmp_path):
    event = CalendarEvent(
        id='missing-transcript-i18n',
        title='Weekly Sync',
        start_time=iso_z(datetime(2024, 3, 5, 9, 0, tzinfo=timezone.utc)),
        end_time=iso_z(datetime(2024, 3, 5, 10, 0, tzinfo=timezone.utc)),
    )

    missing_path = tmp_path / 'missing.txt'

    manager = TimelineManagerForTest(
        calendar_manager=DummyCalendarManager([event]),
        db_connection=NOOP_DB,
        i18n=StubI18n({
            'timeline.snippet.missing_transcript': '转录文件缺失',
        }),
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

    snippet = manager.get_search_snippet(event, 'notes')

    assert snippet == '转录文件缺失'


def test_get_search_snippet_translation_fallbacks(monkeypatch, caplog, tmp_path):
    event = CalendarEvent(
        id='translation-fallback',
        title='Translation Missing',
        start_time=iso_z(datetime(2024, 4, 5, 9, 0, tzinfo=timezone.utc)),
        end_time=iso_z(datetime(2024, 4, 5, 10, 0, tzinfo=timezone.utc)),
    )

    missing_path = tmp_path / 'missing-translation.txt'
    corrupt_path = tmp_path / 'corrupt-translation.txt'
    corrupt_path.write_bytes(b'\xff\xfe\xfd')

    manager = TimelineManagerForTest(
        calendar_manager=DummyCalendarManager([event]),
        db_connection=NOOP_DB,
    )

    def _run_snippet(attachment_path):
        monkeypatch.setattr(
            EventAttachment,
            'get_by_event_id',
            staticmethod(
                lambda db, event_id: [
                    SimpleNamespace(
                        attachment_type='translation',
                        file_path=attachment_path,
                    )
                ]
            ),
        )
        return manager.get_search_snippet(event, 'notes')

    with caplog.at_level(logging.WARNING, logger='echonote.timeline.manager'):
        missing_result = _run_snippet(str(missing_path))

    assert missing_result == 'Transcript unavailable (file missing)'
    assert 'Translation file not found' in caplog.text

    caplog.clear()

    with caplog.at_level(logging.ERROR, logger='echonote.timeline.manager'):
        unreadable_result = _run_snippet(str(corrupt_path))

    assert unreadable_result == 'Transcript unavailable (cannot read transcript)'
    assert 'Failed to decode translation' in caplog.text


class AutoTaskDbStub:
    def __init__(self, rows):
        self._rows = {row['event_id']: dict(row) for row in rows}
        self.executed = []

    def execute(self, query, params=None, commit=False):  # noqa: D401
        self.executed.append((query, params))

        if params is None:
            return []

        if ' IN (' in query:
            event_ids = list(params)
            return [
                self._rows[event_id]
                for event_id in event_ids
                if event_id in self._rows
            ]

        if 'WHERE event_id = ?' in query:
            event_id = params[0]
            row = self._rows.get(event_id)
            return [row] if row else []

        return []


def test_get_auto_task_map_matches_single_lookup():
    config_row = {
        'id': 'cfg-1',
        'event_id': 'with-config',
        'enable_transcription': 1,
        'enable_recording': 0,
        'transcription_language': 'en-US',
        'enable_translation': 0,
        'translation_target_language': None,
        'created_at': '2024-03-01T00:00:00Z',
    }

    db = AutoTaskDbStub([config_row])
    manager = TimelineManager(
        calendar_manager=DummyCalendarManager([]),
        db_connection=db,
    )

    single_lookup = manager.get_auto_task('with-config')
    batched = manager._get_auto_task_map([
        'with-config',
        'missing',
        'with-config',
    ])

    assert single_lookup == {
        'enable_transcription': True,
        'enable_recording': False,
        'transcription_language': 'en-US',
        'enable_translation': False,
        'translation_target_language': None,
    }
    assert batched['with-config'] == single_lookup
    assert 'missing' not in batched

    # Verify the second query used the batched path with a single unique ID
    assert len(db.executed) == 2
    batched_query, params = db.executed[1]
    assert ' IN (' in batched_query
    assert params == ('with-config',)


def test_set_auto_task_persists_translation(monkeypatch):
    event = CalendarEvent(
        id='future-1',
        title='Future Meeting',
        start_time='2024-08-01T09:00:00Z',
        end_time='2024-08-01T10:00:00Z',
    )

    manager = TimelineManager(
        calendar_manager=DummyCalendarManager([event]),
        db_connection=NOOP_DB,
    )

    stored_configs = {}

    def fake_get_by_event_id(cls, db, event_id):
        return stored_configs.get(event_id)

    def fake_save(self, db):
        stored_configs[self.event_id] = self

    monkeypatch.setattr(
        AutoTaskConfig,
        'get_by_event_id',
        classmethod(fake_get_by_event_id),
    )
    monkeypatch.setattr(AutoTaskConfig, 'save', fake_save)

    manager.set_auto_task(
        event.id,
        {
            'enable_transcription': True,
            'enable_recording': False,
            'enable_translation': True,
            'translation_target_language': 'fr',
        }
    )

    saved = stored_configs[event.id]
    assert saved.enable_translation is True
    assert saved.translation_target_language == 'fr'

    restored = manager.get_auto_task(event.id)
    assert restored == {
        'enable_transcription': True,
        'enable_recording': False,
        'transcription_language': None,
        'enable_translation': True,
        'translation_target_language': 'fr',
    }


def test_build_artifacts_includes_translation():
    attachments = [
        EventAttachment(
            id='att-translation',
            event_id='event-1',
            attachment_type='translation',
            file_path='/tmp/translation.txt',
            file_size=64,
            created_at='2024-06-01T12:00:00Z',
        )
    ]

    artifacts = TimelineManager._build_artifacts_from_attachments(attachments)

    assert artifacts['translation'] == '/tmp/translation.txt'
    assert artifacts['attachments'][0]['type'] == 'translation'


def test_get_timeline_events_include_translation_path(monkeypatch):
    center_time = datetime(2024, 6, 1, 12, 0, tzinfo=timezone.utc)

    event = CalendarEvent(
        id='past-translation',
        title='Past with Translation',
        start_time=iso_z(center_time - timedelta(hours=1)),
        end_time=iso_z(center_time - timedelta(minutes=30)),
    )

    translation_attachment = EventAttachment(
        id='translation-att',
        event_id=event.id,
        attachment_type='translation',
        file_path='/tmp/past-translation.txt',
        file_size=1024,
        created_at='2024-06-01T10:00:00Z',
    )

    monkeypatch.setattr(
        EventAttachment,
        'get_by_event_ids',
        staticmethod(lambda db, ids: {event.id: [translation_attachment]}),
    )

    manager = _build_manager([event])

    result = manager.get_timeline_events(
        center_time=center_time,
        past_days=1,
        future_days=0,
    )

    assert len(result['past_events']) == 1
    artifacts = result['past_events'][0]['artifacts']
    assert artifacts['translation'] == '/tmp/past-translation.txt'
    assert any(att['type'] == 'translation' for att in artifacts['attachments'])
