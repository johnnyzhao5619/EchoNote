"""Unit tests for calendar synchronization adapters time handling."""

import sys
from datetime import datetime
from pathlib import Path
import types
from urllib.parse import parse_qs, urlparse

import pytest
from typing import Optional

from zoneinfo import ZoneInfo


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tests.unit.test_transcription_manager_failure import _ensure_cryptography_stubs


_ensure_cryptography_stubs()


def _ensure_httpx_stub():
    if 'httpx' in sys.modules:
        return

    httpx_module = types.ModuleType('httpx')

    class Response:
        def __init__(self, status_code: int = 200, *, headers: Optional[dict] = None):
            self.status_code = status_code
            self.headers = headers or {}

        def raise_for_status(self):
            if 400 <= self.status_code:
                raise HTTPStatusError("HTTP error", response=self)

        def json(self):  # pragma: no cover - default stub behaviour
            return {}

    class Client:
        def __init__(self, **kwargs):  # noqa: D401 - stub
            self._responses = []

        def request(self, method, url, **kwargs):  # noqa: D401 - stub
            response = Response()
            self._responses.append((method, url, kwargs))
            return response

        def post(self, url, **kwargs):  # noqa: D401 - stub
            return self.request('POST', url, **kwargs)

        def close(self):  # noqa: D401 - stub
            return None

    class HTTPStatusError(Exception):
        def __init__(self, message: str = '', response=None):
            super().__init__(message)
            self.response = response

    class HTTPError(Exception):
        pass

    class ConnectError(HTTPError):
        pass

    class TimeoutException(HTTPError):
        pass

    class NetworkError(HTTPError):
        pass

    httpx_module.Client = Client
    httpx_module.Response = Response
    httpx_module.HTTPStatusError = HTTPStatusError
    httpx_module.HTTPError = HTTPError
    httpx_module.ConnectError = ConnectError
    httpx_module.TimeoutException = TimeoutException
    httpx_module.NetworkError = NetworkError
    sys.modules['httpx'] = httpx_module


_ensure_httpx_stub()

from data.database.models import CalendarEvent
from engines.calendar_sync.google_calendar import GoogleCalendarAdapter
from engines.calendar_sync.outlook_calendar import (
    OutlookCalendarAdapter,
    WINDOWS_TO_IANA_MAP,
)


@pytest.fixture
def google_adapter():
    return GoogleCalendarAdapter('id', 'secret')


@pytest.fixture
def outlook_adapter():
    adapter = OutlookCalendarAdapter('id', 'secret')
    adapter._iana_to_windows_map = {
        'UTC': 'UTC',
        'Etc/UTC': 'UTC',
        'Asia/Shanghai': 'China Standard Time',
        'Europe/Paris': 'Romance Standard Time',
        'America/Sao_Paulo': 'E. South America Standard Time',
        'Africa/Nairobi': 'E. Africa Standard Time',
    }
    adapter._timezone_map_loaded = True
    return adapter


def test_outlook_scopes_include_offline_access():
    adapter = OutlookCalendarAdapter('id', 'secret')

    assert 'offline_access' in adapter.SCOPES

    auth_payload = adapter.get_authorization_url()
    query = parse_qs(urlparse(auth_payload['authorization_url']).query)
    scope_value = query.get('scope', [''])[0].split()

    assert 'offline_access' in scope_value


def _normalise_iso_value(value: str) -> str:
    text = value.strip()
    if text.endswith('Z'):
        text = f"{text[:-1]}+00:00"

    if '.' not in text:
        return text

    main, remainder = text.split('.', 1)
    offset = ''
    for sign in ('+', '-'):
        idx = remainder.find(sign)
        if idx > 0:
            offset = remainder[idx:]
            remainder = remainder[:idx]
            break

    fraction = ''.join(ch for ch in remainder if ch.isdigit())
    if not fraction:
        return f"{main}{offset}"

    fraction = (fraction + '000000')[:6]
    if set(fraction) == {'0'}:
        return f"{main}{offset}"
    return f"{main}.{fraction}{offset}"


def _build_remote_instant(
    adapter: OutlookCalendarAdapter,
    date_value: str,
    timezone_identifier: str,
) -> datetime:
    identifier = WINDOWS_TO_IANA_MAP.get(timezone_identifier, timezone_identifier)
    tzinfo_value = adapter._timezone_from_identifier(identifier)

    parsed = datetime.fromisoformat(_normalise_iso_value(date_value))
    if parsed.tzinfo:
        return parsed.astimezone(tzinfo_value)
    return parsed.replace(tzinfo=tzinfo_value)


def _build_event(start: str, end: str) -> CalendarEvent:
    return CalendarEvent(
        title='Sample',
        start_time=start,
        end_time=end,
    )


def test_google_convert_naive_datetime(monkeypatch, google_adapter):
    monkeypatch.setenv('ECHONOTE_LOCAL_TIMEZONE', 'Asia/Shanghai')
    event = _build_event('2024-07-01T09:00:00', '2024-07-01T10:00:00')

    payload = google_adapter._convert_to_google_event(event)

    assert payload['start']['timeZone'] == 'Asia/Shanghai'
    assert payload['start']['dateTime'].endswith('+08:00')
    assert payload['end']['timeZone'] == 'Asia/Shanghai'
    assert payload['end']['dateTime'].endswith('+08:00')


def test_google_convert_utc_datetime(monkeypatch, google_adapter):
    monkeypatch.delenv('ECHONOTE_LOCAL_TIMEZONE', raising=False)
    event = _build_event('2024-07-01T01:00:00Z', '2024-07-01T02:00:00Z')

    payload = google_adapter._convert_to_google_event(event)

    assert payload['start']['timeZone'] == 'UTC'
    assert payload['start']['dateTime'].endswith('+00:00')
    assert payload['end']['timeZone'] == 'UTC'
    assert payload['end']['dateTime'].endswith('+00:00')


def test_google_convert_offset_datetime(monkeypatch, google_adapter):
    monkeypatch.delenv('ECHONOTE_LOCAL_TIMEZONE', raising=False)
    event = _build_event(
        '2024-07-01T09:00:00+02:00',
        '2024-07-01T10:30:00+02:00',
    )

    payload = google_adapter._convert_to_google_event(event)

    assert payload['start']['timeZone'] == 'UTC+02:00'
    assert payload['start']['dateTime'].endswith('+02:00')
    assert payload['end']['timeZone'] == 'UTC+02:00'
    assert payload['end']['dateTime'].endswith('+02:00')


def test_google_convert_event_with_default_reminder(google_adapter):
    google_event = {
        'id': 'evt-default',
        'summary': 'Meeting',
        'start': {'dateTime': '2024-08-01T09:00:00Z'},
        'end': {'dateTime': '2024-08-01T10:00:00Z'},
        'reminders': {'useDefault': True},
    }

    converted = google_adapter._convert_google_event(google_event)

    assert converted['reminder_minutes'] is None
    assert converted['reminder_use_default'] is True


def test_google_convert_event_with_custom_reminder(google_adapter):
    google_event = {
        'id': 'evt-custom',
        'summary': 'Check-in',
        'start': {'dateTime': '2024-08-01T09:00:00Z'},
        'end': {'dateTime': '2024-08-01T10:00:00Z'},
        'reminders': {
            'useDefault': False,
            'overrides': [{'method': 'popup', 'minutes': 25}],
        },
    }

    converted = google_adapter._convert_google_event(google_event)

    assert converted['reminder_minutes'] == 25
    assert converted['reminder_use_default'] is False


def test_google_convert_event_with_disabled_reminder(google_adapter):
    google_event = {
        'id': 'evt-disabled',
        'summary': 'Heads-down time',
        'start': {'dateTime': '2024-08-01T09:00:00Z'},
        'end': {'dateTime': '2024-08-01T11:00:00Z'},
        'reminders': {
            'useDefault': False,
            'overrides': [],
        },
    }

    converted = google_adapter._convert_google_event(google_event)

    assert converted['reminder_minutes'] is None
    assert converted['reminder_use_default'] is False


def test_google_convert_to_event_uses_default_reminder(google_adapter):
    event = CalendarEvent(
        title='Default reminder',
        start_time='2024-08-01T09:00:00Z',
        end_time='2024-08-01T10:00:00Z',
        reminder_use_default=True,
    )

    payload = google_adapter._convert_to_google_event(event)

    assert payload['reminders'] == {'useDefault': True}


def test_google_convert_to_event_custom_reminder(google_adapter):
    event = CalendarEvent(
        title='Custom reminder',
        start_time='2024-08-01T09:00:00Z',
        end_time='2024-08-01T10:00:00Z',
        reminder_minutes=20,
    )

    payload = google_adapter._convert_to_google_event(event)

    assert payload['reminders']['useDefault'] is False
    assert payload['reminders']['overrides'] == [
        {'method': 'popup', 'minutes': 20}
    ]


def test_google_convert_to_event_disables_reminders(google_adapter):
    event = CalendarEvent(
        title='No reminder',
        start_time='2024-08-01T09:00:00Z',
        end_time='2024-08-01T10:00:00Z',
        reminder_use_default=False,
    )

    payload = google_adapter._convert_to_google_event(event)

    assert payload['reminders'] == {
        'useDefault': False,
        'overrides': [],
    }


def test_google_disabled_reminder_roundtrip(google_adapter):
    remote_payload = {
        'id': 'evt-roundtrip-disabled',
        'summary': 'Focus block',
        'start': {'dateTime': '2024-08-01T09:00:00Z'},
        'end': {'dateTime': '2024-08-01T10:30:00Z'},
        'reminders': {
            'useDefault': False,
            'overrides': [],
        },
    }

    converted = google_adapter._convert_google_event(remote_payload)
    local_event = CalendarEvent(
        title=converted['title'],
        start_time=converted['start_time'],
        end_time=converted['end_time'],
        reminder_minutes=converted['reminder_minutes'],
        reminder_use_default=converted['reminder_use_default'],
    )

    payload = google_adapter._convert_to_google_event(local_event)

    assert payload['reminders'] == {
        'useDefault': False,
        'overrides': [],
    }


def test_outlook_convert_naive_datetime(monkeypatch, outlook_adapter):
    monkeypatch.setenv('ECHONOTE_LOCAL_TIMEZONE', 'Asia/Shanghai')
    event = _build_event('2024-07-01T09:00:00', '2024-07-01T10:00:00')

    payload = outlook_adapter._convert_to_outlook_event(event)

    assert payload['start']['timeZone'] == 'China Standard Time'
    assert payload['start']['dateTime'] == '2024-07-01T09:00:00'
    assert payload['end']['timeZone'] == 'China Standard Time'
    assert payload['end']['dateTime'] == '2024-07-01T10:00:00'


def test_outlook_convert_utc_datetime(monkeypatch, outlook_adapter):
    monkeypatch.delenv('ECHONOTE_LOCAL_TIMEZONE', raising=False)
    event = _build_event('2024-07-01T01:00:00Z', '2024-07-01T02:00:00Z')

    payload = outlook_adapter._convert_to_outlook_event(event)

    assert payload['start']['timeZone'] == 'UTC'
    assert payload['start']['dateTime'] == '2024-07-01T01:00:00'
    assert payload['end']['timeZone'] == 'UTC'
    assert payload['end']['dateTime'] == '2024-07-01T02:00:00'


def test_outlook_convert_offset_datetime(monkeypatch, outlook_adapter):
    monkeypatch.delenv('ECHONOTE_LOCAL_TIMEZONE', raising=False)
    event = _build_event(
        '2024-07-01T09:00:00+02:00',
        '2024-07-01T10:30:00+02:00',
    )

    payload = outlook_adapter._convert_to_outlook_event(event)

    assert payload['start']['timeZone'] == 'UTC+02:00'
    assert payload['start']['dateTime'] == '2024-07-01T09:00:00'
    assert payload['end']['timeZone'] == 'UTC+02:00'
    assert payload['end']['dateTime'] == '2024-07-01T10:30:00'


def test_outlook_convert_all_day_event(monkeypatch, outlook_adapter):
    monkeypatch.setenv('ECHONOTE_LOCAL_TIMEZONE', 'Asia/Shanghai')
    event = CalendarEvent(
        title='All-day workshop',
        start_time='2024-08-01',
        end_time='2024-08-02',
    )

    payload = outlook_adapter._convert_to_outlook_event(event)

    assert payload['isAllDay'] is True
    assert payload['start']['dateTime'] == '2024-08-01T00:00:00'
    assert payload['end']['dateTime'] == '2024-08-02T00:00:00'
    assert payload['start']['timeZone'] == 'China Standard Time'
    assert payload['end']['timeZone'] == 'China Standard Time'


def test_outlook_convert_all_day_event_roundtrip(monkeypatch, outlook_adapter):
    monkeypatch.setenv('ECHONOTE_LOCAL_TIMEZONE', 'Europe/Paris')
    event = CalendarEvent(
        title='Conference day',
        start_time='2024-08-01T00:00:00Z',
        end_time='2024-08-02T00:00:00Z',
    )

    payload = outlook_adapter._convert_to_outlook_event(event)

    assert payload['isAllDay'] is True
    assert payload['start']['dateTime'] == '2024-08-01T00:00:00'
    assert payload['end']['dateTime'] == '2024-08-02T00:00:00'
    assert payload['start']['timeZone'] == 'Romance Standard Time'
    assert payload['end']['timeZone'] == 'Romance Standard Time'

    roundtrip_payload = {
        'id': 'evt-roundtrip',
        'subject': payload['subject'],
        'start': payload['start'],
        'end': payload['end'],
        'isAllDay': payload['isAllDay'],
    }

    converted = outlook_adapter._convert_outlook_event(roundtrip_payload)

    assert converted['start_time'] == '2024-08-01'
    assert converted['end_time'] == '2024-08-02'


def test_outlook_convert_recurrence_with_interval(monkeypatch, outlook_adapter):
    monkeypatch.setenv('ECHONOTE_LOCAL_TIMEZONE', 'UTC')
    event = CalendarEvent(
        title='Bi-weekly sync',
        start_time='2024-07-01T09:00:00Z',
        end_time='2024-07-01T10:00:00Z',
        recurrence_rule='FREQ=WEEKLY;INTERVAL=2;BYDAY=MO,WE',
    )

    payload = outlook_adapter._convert_to_outlook_event(event)

    recurrence = payload['recurrence']
    assert recurrence['pattern']['type'] == 'weekly'
    assert recurrence['pattern']['interval'] == 2
    assert recurrence['pattern']['daysOfWeek'] == ['monday', 'wednesday']
    assert recurrence['range']['startDate'] == '2024-07-01'


def test_outlook_convert_recurrence_interval_and_byday(monkeypatch, outlook_adapter):
    monkeypatch.setenv('ECHONOTE_LOCAL_TIMEZONE', 'UTC')
    event = CalendarEvent(
        title='Training rotation',
        start_time='2024-07-02T09:00:00Z',
        end_time='2024-07-02T10:00:00Z',
        recurrence_rule='FREQ=WEEKLY;INTERVAL=3;BYDAY=TU,TH',
    )

    payload = outlook_adapter._convert_to_outlook_event(event)

    recurrence = payload['recurrence']
    assert recurrence['pattern']['type'] == 'weekly'
    assert recurrence['pattern']['interval'] == 3
    assert recurrence['pattern']['daysOfWeek'] == ['tuesday', 'thursday']
    assert recurrence['range']['startDate'] == '2024-07-02'


def test_outlook_convert_removed_event(outlook_adapter):
    outlook_payload = {
        'id': 'evt-deleted',
        '@removed': {'reason': 'deleted'},
    }

    converted = outlook_adapter._convert_outlook_event(outlook_payload)

    assert converted == {'id': 'evt-deleted', 'deleted': True}


def test_outlook_convert_removed_event_without_times(outlook_adapter):
    outlook_payload = {
        'id': 'evt-no-times',
        '@removed': {'reason': 'deleted'},
        'start': None,
        'end': None,
    }

    converted = outlook_adapter._convert_outlook_event(outlook_payload)

    assert converted == {'id': 'evt-no-times', 'deleted': True}


def test_outlook_convert_event_prefers_body_content(outlook_adapter):
    outlook_payload = {
        'id': 'evt-body',
        'subject': 'Team Sync',
        'start': {'dateTime': '2024-08-01T09:00:00'},
        'end': {'dateTime': '2024-08-01T10:00:00'},
        'body': {
            'contentType': 'HTML',
            'content': '<p>Hello&nbsp;team<br>Thanks &amp; regards</p>',
        },
        'bodyPreview': 'Preview should not be used',
    }

    converted = outlook_adapter._convert_outlook_event(outlook_payload)

    assert converted['description'] == 'Hello team\nThanks & regards'


def test_outlook_convert_event_falls_back_to_preview(outlook_adapter):
    outlook_payload = {
        'id': 'evt-preview',
        'subject': 'Team Sync',
        'start': {'dateTime': '2024-08-01T09:00:00'},
        'end': {'dateTime': '2024-08-01T10:00:00'},
        'bodyPreview': 'Preview content only',
    }

    converted = outlook_adapter._convert_outlook_event(outlook_payload)

    assert converted['description'] == 'Preview content only'


def test_outlook_fetch_events_initial_sync_uses_delta_endpoint(monkeypatch, outlook_adapter):
    captured = {}

    class DummyResponse:
        def __init__(self, data):
            self._data = data

        def json(self):
            return self._data

    def fake_api_request(method, url, **kwargs):
        captured['method'] = method
        captured['url'] = url
        return DummyResponse({
            'value': [],
            '@odata.deltaLink': 'https://graph.microsoft.com/v1.0/me/calendar/events/delta?$deltatoken=abc',
        })

    monkeypatch.setattr(outlook_adapter, 'api_request', fake_api_request)

    result = outlook_adapter.fetch_events()

    assert captured['method'] == 'GET'
    assert captured['url'].startswith(
        f"{outlook_adapter.API_BASE_URL}/me/calendar/events/delta"
    )
    assert '$deltatoken=latest' in captured['url']
    assert result['sync_token'] == 'https://graph.microsoft.com/v1.0/me/calendar/events/delta?$deltatoken=abc'


def test_outlook_fetch_events_tracks_deletions(monkeypatch, outlook_adapter):
    payload = {
        'value': [
            {
                'id': 'evt-deleted',
                '@removed': {'reason': 'deleted'},
            },
            {
                'id': 'evt-active',
                'subject': 'Meeting',
                'start': {'dateTime': '2024-08-01T09:00:00'},
                'end': {'dateTime': '2024-08-01T10:00:00'},
                'attendees': [],
            },
        ],
        '@odata.deltaLink': 'delta-token',
    }

    class DummyResponse:
        def __init__(self, data):
            self._data = data

        def json(self):
            return self._data

    def fake_api_request(method, url, **kwargs):
        assert method == 'GET'
        return DummyResponse(payload)

    monkeypatch.setattr(outlook_adapter, 'api_request', fake_api_request)

    result = outlook_adapter.fetch_events(last_sync_token='https://delta-link')

    assert result['deleted'] == ['evt-deleted']
    assert [event['id'] for event in result['events']] == ['evt-active']
    assert result['sync_token'] == 'delta-token'
