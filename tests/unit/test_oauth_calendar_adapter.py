import pytest

httpx = pytest.importorskip("httpx")

from datetime import datetime
from typing import Any, Dict

from engines.calendar_sync.base import OAuthCalendarAdapter, OAuthEndpoints
from utils.http_client import RetryableHttpClient


class _DummyOAuthAdapter(OAuthCalendarAdapter):
    def __init__(self, transport: httpx.MockTransport):
        super().__init__(
            client_id='client',
            client_secret='secret',
            redirect_uri='https://app.local/callback',
            scopes=['calendar.read'],
            endpoints=OAuthEndpoints(
                auth_url='https://auth.example.com/authorize',
                token_url='https://auth.example.com/token',
                api_base_url='https://api.example.com',
            ),
            http_client_config={'transport': transport},
        )

    # The abstract methods are not exercised in these tests, keep no-op implementations.
    def fetch_events(self, *args, **kwargs) -> Dict[str, Any]:
        return {}

    def push_event(self, *args, **kwargs) -> str:
        return 'event-id'

    def update_event(self, *args, **kwargs) -> None:
        return None

    def delete_event(self, *args, **kwargs) -> None:
        return None


def test_exchange_code_normalizes_token_type_and_updates_state():
    token_response = {
        'access_token': 'access-123',
        'refresh_token': 'refresh-456',
        'token_type': 'bearer',
        'expires_in': 7200,
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith('/token'):
            body = request.content.decode()
            assert 'grant_type=authorization_code' in body
            return httpx.Response(200, json=token_response)

        if request.url == httpx.URL('https://api.example.com/ping'):
            # Authorization header should use normalized token type.
            assert request.headers['Authorization'] == 'Bearer access-123'
            return httpx.Response(200, json={'ok': True})

        raise AssertionError(f"Unexpected request: {request.url!r}")

    adapter = _DummyOAuthAdapter(httpx.MockTransport(handler))

    payload = adapter.exchange_code_for_token('auth-code', code_verifier='verifier')

    assert adapter.access_token == 'access-123'
    assert adapter.refresh_token == 'refresh-456'
    assert adapter.token_type == 'Bearer'
    # expires_at should be ISO formatted string
    datetime.fromisoformat(payload['expires_at'])
    assert payload['token_type'] == 'Bearer'

    # The adapter should reuse the same HTTP client for API calls.
    adapter.api_request('GET', 'https://api.example.com/ping')


def test_retryable_http_client_respects_max_retry_after(monkeypatch):
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(429, headers={'Retry-After': '5'})

    client = RetryableHttpClient(
        max_retries=1,
        max_retry_after=2,
        transport=httpx.MockTransport(handler),
    )

    # Avoid real sleeping during the test.
    monkeypatch.setattr('utils.http_client.time.sleep', lambda *_: None)

    with pytest.raises(httpx.HTTPStatusError):
        client.get('https://example.com/slow-retry')

    client.close()
