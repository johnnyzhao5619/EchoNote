from __future__ import annotations

import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
pytest.importorskip('apscheduler')

from core.timeline.auto_task_scheduler import AutoTaskScheduler
from data.database.models import CalendarEvent


def iso_z(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')


class DummyTimelineManager:
    def __init__(self, future_events):
        self._future_events = list(future_events)
        self.calls = []

    def get_timeline_events(
        self,
        center_time,
        past_days,
        future_days,
        page=0,
        page_size=50,
    ):
        self.calls.append((center_time, past_days, future_days))
        if future_days == 0:
            return {
                'current_time': center_time.isoformat(),
                'future_events': [],
                'past_events': [],
                'has_more': False,
            }
        return {
            'current_time': center_time.isoformat(),
            'future_events': list(self._future_events),
            'past_events': [],
            'has_more': False,
        }


class DummyRecorder:
    def __init__(self):
        self.is_recording = False

    async def start_recording(self, *args, **kwargs):  # noqa: D401
        self.is_recording = True

    async def stop_recording(self):  # noqa: D401
        self.is_recording = False
        return {}


class DummyNotificationManager:
    def __init__(self):
        self.messages = []

    def send_info(self, title, message):
        self.messages.append(('info', title, message))

    def send_warning(self, title, message):  # noqa: D401
        self.messages.append(('warning', title, message))

    def send_success(self, title, message):  # noqa: D401
        self.messages.append(('success', title, message))

    def send_error(self, title, message):  # noqa: D401
        self.messages.append(('error', title, message))


def test_scheduler_triggers_reminder_with_timezone(monkeypatch):
    base_now = datetime.now().astimezone()
    future_event = CalendarEvent(
        id='future-event',
        title='Reminder Test',
        start_time=iso_z(base_now + timedelta(minutes=5)),
        end_time=iso_z(base_now + timedelta(minutes=65)),
    )

    future_events = [{
        'event': future_event,
        'auto_tasks': {'enable_transcription': True},
    }]

    timeline_manager = DummyTimelineManager(future_events)
    recorder = DummyRecorder()
    notifications = DummyNotificationManager()

    monkeypatch.setattr(
        'core.timeline.auto_task_scheduler.get_notification_manager',
        lambda: notifications,
    )

    scheduler = AutoTaskScheduler(
        timeline_manager=timeline_manager,
        realtime_recorder=recorder,
        db_connection=None,
        file_manager=None,
        reminder_minutes=5,
    )

    scheduler._check_upcoming_events()

    assert future_event.id in scheduler.notified_events
    assert any(kind == 'info' for kind, *_ in notifications.messages)
    assert not recorder.is_recording
    assert timeline_manager.calls  # ensure call recorded
    for center_time, _, _ in timeline_manager.calls:
        assert center_time.tzinfo is None
