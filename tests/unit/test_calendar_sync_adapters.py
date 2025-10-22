"""Unit tests for calendar synchronization adapters time handling."""

import sys
from datetime import datetime
from pathlib import Path
import types

import pytest
from typing import Optional


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
    return OutlookCalendarAdapter('id', 'secret')


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

    assert payload['start']['timeZone'] == 'UTC+02'
    assert payload['start']['dateTime'] == '2024-07-01T09:00:00'
    assert payload['end']['timeZone'] == 'UTC+02'
    assert payload['end']['dateTime'] == '2024-07-01T10:30:00'


def test_outlook_event_roundtrip_with_explicit_timezone(outlook_adapter):
    remote_payload = {
        'id': 'evt-001',
        'subject': 'Remote Meeting',
        'start': {
            'dateTime': '2024-07-01T09:00:00.0000000',
            'timeZone': 'China Standard Time',
        },
        'end': {
            'dateTime': '2024-07-01T10:00:00.0000000',
            'timeZone': 'China Standard Time',
        },
    }

    internal_event = outlook_adapter._convert_outlook_event(remote_payload)

    assert internal_event['start_time'].startswith('2024-07-01T09:00:00')
    assert internal_event['start_time'].endswith('+08:00')
    assert internal_event['end_time'].startswith('2024-07-01T10:00:00')
    assert internal_event['end_time'].endswith('+08:00')

    calendar_event = CalendarEvent(
        id=internal_event['id'],
        title=internal_event['title'],
        event_type=internal_event['event_type'],
        start_time=internal_event['start_time'],
        end_time=internal_event['end_time'],
        location=internal_event['location'],
        attendees=internal_event['attendees'],
        description=internal_event['description'],
        reminder_minutes=internal_event['reminder_minutes'],
        recurrence_rule=internal_event['recurrence_rule'],
        source='outlook',
        external_id=internal_event['id'],
    )

    roundtrip_payload = outlook_adapter._convert_to_outlook_event(calendar_event)

    assert roundtrip_payload['start']['dateTime'] == '2024-07-01T09:00:00'
    assert roundtrip_payload['end']['dateTime'] == '2024-07-01T10:00:00'

    original_start = _build_remote_instant(
        outlook_adapter,
        remote_payload['start']['dateTime'],
        remote_payload['start']['timeZone'],
    )
    roundtrip_start = _build_remote_instant(
        outlook_adapter,
        roundtrip_payload['start']['dateTime'],
        roundtrip_payload['start']['timeZone'],
    )
    original_end = _build_remote_instant(
        outlook_adapter,
        remote_payload['end']['dateTime'],
        remote_payload['end']['timeZone'],
    )
    roundtrip_end = _build_remote_instant(
        outlook_adapter,
        roundtrip_payload['end']['dateTime'],
        roundtrip_payload['end']['timeZone'],
    )

    assert roundtrip_start == original_start
    assert roundtrip_end == original_end


def test_outlook_event_roundtrip_with_original_timezone(outlook_adapter):
    remote_payload = {
        'id': 'evt-002',
        'subject': 'Fallback Zone',
        'start': {
            'dateTime': '2024-12-01T09:30:00.0000000',
        },
        'end': {
            'dateTime': '2024-12-01T10:45:00.0000000',
        },
        'originalStartTimeZone': 'Pacific Standard Time',
    }

    internal_event = outlook_adapter._convert_outlook_event(remote_payload)

    assert internal_event['start_time'].startswith('2024-12-01T09:30:00')
    assert internal_event['start_time'].endswith('-08:00')
    assert internal_event['end_time'].startswith('2024-12-01T10:45:00')
    assert internal_event['end_time'].endswith('-08:00')

    calendar_event = CalendarEvent(
        id=internal_event['id'],
        title=internal_event['title'],
        event_type=internal_event['event_type'],
        start_time=internal_event['start_time'],
        end_time=internal_event['end_time'],
        location=internal_event['location'],
        attendees=internal_event['attendees'],
        description=internal_event['description'],
        reminder_minutes=internal_event['reminder_minutes'],
        recurrence_rule=internal_event['recurrence_rule'],
        source='outlook',
        external_id=internal_event['id'],
    )

    roundtrip_payload = outlook_adapter._convert_to_outlook_event(calendar_event)

    assert roundtrip_payload['start']['dateTime'] == '2024-12-01T09:30:00'
    assert roundtrip_payload['end']['dateTime'] == '2024-12-01T10:45:00'

    expected_identifier = remote_payload['start'].get(
        'timeZone', remote_payload['originalStartTimeZone']
    )
    original_start = _build_remote_instant(
        outlook_adapter,
        remote_payload['start']['dateTime'],
        expected_identifier,
    )
    original_end = _build_remote_instant(
        outlook_adapter,
        remote_payload['end']['dateTime'],
        expected_identifier,
    )
    roundtrip_start = _build_remote_instant(
        outlook_adapter,
        roundtrip_payload['start']['dateTime'],
        roundtrip_payload['start']['timeZone'],
    )
    roundtrip_end = _build_remote_instant(
        outlook_adapter,
        roundtrip_payload['end']['dateTime'],
        roundtrip_payload['end']['timeZone'],
    )

    assert roundtrip_start == original_start
    assert roundtrip_end == original_end


def test_outlook_all_day_event_conversion(outlook_adapter):
    remote_payload = {
        'id': 'evt-003',
        'subject': 'All Day',
        'isAllDay': True,
        'start': {
            'dateTime': '2024-08-15T00:00:00',
            'timeZone': 'UTC',
        },
        'end': {
            'dateTime': '2024-08-16T00:00:00',
            'timeZone': 'UTC',
        },
    }

    internal_event = outlook_adapter._convert_outlook_event(remote_payload)

    assert internal_event['start_time'] == '2024-08-15'
    assert internal_event['end_time'] == '2024-08-16'
