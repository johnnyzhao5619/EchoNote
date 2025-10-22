"""Unit tests for calendar synchronization adapters time handling."""

import sys
from datetime import datetime
from pathlib import Path
import types

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
from engines.calendar_sync.outlook_calendar import OutlookCalendarAdapter


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

    assert payload['start']['timeZone'] == 'UTC+02:00'
    assert payload['start']['dateTime'] == '2024-07-01T09:00:00'
    assert payload['end']['timeZone'] == 'UTC+02:00'
    assert payload['end']['dateTime'] == '2024-07-01T10:30:00'


def test_outlook_convert_iana_paris(outlook_adapter):
    event = CalendarEvent(
        title='Sample',
        start_time=datetime(2024, 7, 1, 9, 0, tzinfo=ZoneInfo('Europe/Paris')),
        end_time=datetime(2024, 7, 1, 10, 0, tzinfo=ZoneInfo('Europe/Paris')),
    )

    payload = outlook_adapter._convert_to_outlook_event(event)

    assert payload['start']['timeZone'] == 'Romance Standard Time'
    assert payload['start']['dateTime'] == '2024-07-01T09:00:00'
    assert payload['end']['timeZone'] == 'Romance Standard Time'
    assert payload['end']['dateTime'] == '2024-07-01T10:00:00'


def test_outlook_convert_iana_sao_paulo(outlook_adapter):
    event = CalendarEvent(
        title='Sample',
        start_time=datetime(2024, 7, 1, 9, 0, tzinfo=ZoneInfo('America/Sao_Paulo')),
        end_time=datetime(2024, 7, 1, 10, 0, tzinfo=ZoneInfo('America/Sao_Paulo')),
    )

    payload = outlook_adapter._convert_to_outlook_event(event)

    assert payload['start']['timeZone'] == 'E. South America Standard Time'
    assert payload['start']['dateTime'] == '2024-07-01T09:00:00'
    assert payload['end']['timeZone'] == 'E. South America Standard Time'
    assert payload['end']['dateTime'] == '2024-07-01T10:00:00'


def test_outlook_convert_iana_nairobi(outlook_adapter):
    event = CalendarEvent(
        title='Sample',
        start_time=datetime(2024, 7, 1, 9, 0, tzinfo=ZoneInfo('Africa/Nairobi')),
        end_time=datetime(2024, 7, 1, 10, 0, tzinfo=ZoneInfo('Africa/Nairobi')),
    )

    payload = outlook_adapter._convert_to_outlook_event(event)

    assert payload['start']['timeZone'] == 'E. Africa Standard Time'
    assert payload['start']['dateTime'] == '2024-07-01T09:00:00'
    assert payload['end']['timeZone'] == 'E. Africa Standard Time'
    assert payload['end']['dateTime'] == '2024-07-01T10:00:00'
