"""Base utilities and interfaces for calendar synchronization adapters."""

import base64
import hashlib
import logging
import os
import secrets
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone, tzinfo, timedelta
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urlencode

try:  # Python 3.9+
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
except ImportError:  # pragma: no cover - fallback for older Python
    ZoneInfo = None  # type: ignore
    ZoneInfoNotFoundError = Exception  # type: ignore

from data.database.models import CalendarEvent
from utils.http_client import RetryableHttpClient


logger = logging.getLogger('echonote.calendar_sync.base')


class CalendarSyncAdapter(ABC):
    """
    Abstract base class for calendar synchronization adapters.

    All external calendar sync implementations (Google, Outlook, etc.)
    must inherit from this class and implement all abstract methods.
    """

    @abstractmethod
    def authenticate(self, credentials: dict) -> dict:
        """
        Perform OAuth authentication with the calendar provider.

        Args:
            credentials: Dictionary containing authentication credentials
                        (e.g., client_id, client_secret, redirect_uri)

        Returns:
            Dictionary containing authentication tokens:
            {
                'access_token': str,
                'refresh_token': str,
                'expires_at': str (ISO format timestamp)
            }

        Raises:
            Exception: If authentication fails
        """
        pass

    @abstractmethod
    def fetch_events(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        last_sync_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Fetch events from the external calendar.

        Supports incremental synchronization using sync tokens.

        Args:
            start_date: Optional start date in ISO format
            end_date: Optional end date in ISO format
            last_sync_token: Optional token for incremental sync

        Returns:
            Dictionary containing:
            {
                'events': [
                    {
                        'id': str,
                        'title': str,
                        'event_type': str,
                        'start_time': str (ISO format),
                        'end_time': str (ISO format),
                        'location': Optional[str],
                        'attendees': List[str],
                        'description': Optional[str],
                        'reminder_minutes': Optional[int],
                        'recurrence_rule': Optional[str]
                    },
                    ...
                ],
                'deleted': List[str],  # External IDs removed or cancelled remotely
                'sync_token': Optional[str]  # For next incremental sync
            }

        Raises:
            Exception: If fetching events fails
        """
        pass

    @abstractmethod
    def push_event(self, event: CalendarEvent) -> str:
        """
        Push a local event to the external calendar.

        Args:
            event: CalendarEvent instance to push

        Returns:
            External event ID (string)

        Raises:
            Exception: If pushing event fails
        """
        pass

    @abstractmethod
    def update_event(self, event: CalendarEvent, external_id: str) -> None:
        """
        Update an existing event on the external calendar.

        Args:
            event: CalendarEvent instance with latest local data
            external_id: Provider-specific identifier for the event

        Raises:
            Exception: If updating the external event fails
        """
        pass

    @abstractmethod
    def delete_event(self, event: CalendarEvent, external_id: str) -> None:
        """
        Delete an event from the external calendar.

        Args:
            event: CalendarEvent instance scheduled for deletion
            external_id: Provider-specific identifier for the event

        Raises:
            Exception: If deleting the external event fails
        """
        pass

    @abstractmethod
    def revoke_access(self):
        """
        Revoke access to the external calendar.

        This should invalidate the OAuth tokens and disconnect
        the calendar integration.

        Raises:
            Exception: If revoking access fails
        """
        pass

    def get_name(self) -> str:
        """
        Get the name of the calendar provider.

        Returns:
            Provider name (e.g., 'google', 'outlook')
        """
        return self.__class__.__name__.lower().replace('adapter', '')

    def get_supported_features(self) -> Dict[str, bool]:
        """
        Get the features supported by this adapter.

        Returns:
            Dictionary of feature flags:
            {
                'incremental_sync': bool,
                'push_events': bool,
                'recurrence': bool,
                'reminders': bool
            }
        """
        return {
            'incremental_sync': True,
            'push_events': True,
            'recurrence': True,
            'reminders': True
        }

    @staticmethod
    def _generate_state_and_pkce() -> Dict[str, str]:
        """Generate OAuth state and PKCE parameters."""

        state = secrets.token_urlsafe(16)
        code_verifier = secrets.token_urlsafe(64)

        while len(code_verifier) < 43:
            code_verifier += secrets.token_urlsafe(32)

        code_verifier = code_verifier[:128]

        code_challenge_bytes = hashlib.sha256(code_verifier.encode('ascii')).digest()
        code_challenge = base64.urlsafe_b64encode(code_challenge_bytes).decode('ascii').rstrip('=')

        return {
            'state': state,
            'code_verifier': code_verifier,
            'code_challenge': code_challenge,
        }

    # ------------------------------------------------------------------
    # Date/time helpers
    # ------------------------------------------------------------------
    @classmethod
    def _get_local_timezone(cls) -> tzinfo:
        """Return the preferred local timezone.

        Lookup order:
            1. ``ECHONOTE_LOCAL_TIMEZONE`` environment variable.
            2. System timezone via ``datetime.now().astimezone()``.
            3. UTC fallback.
        """

        env_tz = os.getenv('ECHONOTE_LOCAL_TIMEZONE')
        if env_tz and ZoneInfo is not None:
            try:
                return ZoneInfo(env_tz)
            except ZoneInfoNotFoundError:
                logger.warning(
                    "Unknown timezone configured in ECHONOTE_LOCAL_TIMEZONE: %s",
                    env_tz
                )

        try:
            system_tz = datetime.now().astimezone().tzinfo
            if system_tz:
                return system_tz
        except Exception:  # pragma: no cover - defensive
            logger.exception("Failed to detect system timezone")

        return timezone.utc

    @classmethod
    def _parse_event_datetime(
        cls,
        value: Union[str, datetime],
        local_tz: Optional[tzinfo] = None,
    ) -> datetime:
        """Parse calendar event datetimes and attach timezone information."""

        if isinstance(value, datetime):
            dt_value = value
        elif isinstance(value, str):
            text = value.strip()
            if text.endswith('Z'):
                text = f"{text[:-1]}+00:00"
            try:
                dt_value = datetime.fromisoformat(text)
            except ValueError as exc:
                raise ValueError(
                    "Event datetime must be a datetime instance or ISO 8601 string"
                ) from exc
        else:  # pragma: no cover - defensive branch
            raise TypeError(
                "Event datetime must be provided as datetime instance or ISO string"
            )

        if dt_value.tzinfo:
            return dt_value

        tzinfo_value = local_tz or cls._get_local_timezone()
        return dt_value.replace(tzinfo=tzinfo_value)

    @staticmethod
    def _get_timezone_identifier(dt_value: datetime) -> Optional[str]:
        """Return a descriptive timezone identifier for payload construction."""

        tzinfo_value = dt_value.tzinfo
        if tzinfo_value is None:
            return None

        key = getattr(tzinfo_value, 'key', None)
        if key:
            if key in {'UTC', 'Etc/UTC', 'Etc/GMT', 'GMT'}:
                return 'UTC'
            return key

        if tzinfo_value is timezone.utc:
            return 'UTC'

        tz_name = tzinfo_value.tzname(dt_value)
        if tz_name in {'UTC', 'GMT', 'Etc/UTC'}:
            return 'UTC'

        offset = dt_value.utcoffset()
        if offset is None:
            return None

        total_minutes = int(offset.total_seconds() // 60)
        if total_minutes == 0:
            return 'UTC'

        sign = '+' if total_minutes > 0 else '-'
        total_minutes = abs(total_minutes)
        hours, minutes = divmod(total_minutes, 60)
        return f"UTC{sign}{hours:02d}:{minutes:02d}"

    @staticmethod
    def _timezone_from_identifier(identifier: str) -> tzinfo:
        """Convert timezone identifier to a ``tzinfo`` implementation."""

        if identifier == 'UTC':
            return timezone.utc

        if identifier.startswith('UTC') and len(identifier) > 3:
            sign = 1 if identifier[3] == '+' else -1
            remainder = identifier[4:]
            try:
                if ':' in remainder:
                    hours_text, minutes_text = remainder.split(':', 1)
                else:
                    hours_text, minutes_text = remainder, '00'
                offset = timedelta(
                    hours=int(hours_text) * sign,
                    minutes=int(minutes_text) * sign,
                )
                return timezone(offset)
            except (ValueError, TypeError):  # pragma: no cover - defensive
                return timezone.utc

        if ZoneInfo is not None:
            try:
                return ZoneInfo(identifier)
            except ZoneInfoNotFoundError:
                logger.warning("Unknown timezone identifier: %s", identifier)
        return timezone.utc


@dataclass(frozen=True)
class OAuthEndpoints:
    """OAuth 2.0 endpoint bundle for calendar providers."""

    auth_url: str
    token_url: str
    api_base_url: str
    revoke_url: Optional[str] = None


@dataclass
class OAuthTokenState:
    """In-memory snapshot of the provider OAuth tokens."""

    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    expires_at: Optional[str] = None
    token_type: Optional[str] = None


class OAuthHttpClient:
    """Encapsulates OAuth token handling and retryable HTTP requests."""

    def __init__(
        self,
        *,
        endpoints: OAuthEndpoints,
        logger: logging.Logger,
        http_client: Optional[RetryableHttpClient] = None,
        http_client_config: Optional[Dict[str, Any]] = None,
    ) -> None:
        if http_client and http_client_config:
            raise ValueError("Provide either http_client or http_client_config, not both")

        self.endpoints = endpoints
        self.logger = logger

        http_client_config = http_client_config or {}
        self._owns_http_client = http_client is None
        self._http_client = http_client or RetryableHttpClient(**http_client_config)
        self.state = OAuthTokenState()

    @property
    def http_client(self) -> RetryableHttpClient:
        return self._http_client

    def close(self) -> None:
        if self._owns_http_client:
            self._http_client.close()

    # Token lifecycle -------------------------------------------------
    def exchange_authorization_code(self, data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            token_data = self._token_request(data)
            self.logger.info("Successfully exchanged authorization code")
            return self._apply_token_response(token_data)
        except Exception as exc:  # pragma: no cover - propagated for callers to inspect
            self.logger.error("Failed to exchange code for token: %s", exc)
            raise

    def refresh_access_token(self, data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            token_data = self._token_request(data)
            self.logger.info("Successfully refreshed access token")
            return self._apply_token_response(token_data)
        except Exception as exc:  # pragma: no cover - propagated for callers to inspect
            self.logger.error("Failed to refresh token: %s", exc)
            raise

    # HTTP interactions -----------------------------------------------
    def api_request(
        self,
        method: str,
        url: str,
        *,
        headers: Optional[Dict[str, str]] = None,
        **kwargs: Any,
    ):
        if not self.state.access_token:
            raise ValueError("Not authenticated")

        token_type = self.state.token_type or 'Bearer'
        auth_headers = {'Authorization': f'{token_type} {self.state.access_token}'}
        if headers:
            auth_headers.update(headers)

        return self._http_client.request(method, url, headers=auth_headers, **kwargs)

    def revoke(
        self,
        revoke_url: Optional[str],
        request_kwargs: Optional[Dict[str, Any]],
    ) -> None:
        if not self.state.access_token:
            self.logger.warning("No access token to revoke")
            return

        if not revoke_url:
            self.logger.info("No revoke endpoint defined; clearing local tokens only")
            self.clear_tokens()
            return

        try:
            self._http_client.post(revoke_url, **(request_kwargs or {}))
            self.logger.info("Successfully revoked access")
        except Exception as exc:  # pragma: no cover - network errors bubbled to caller
            self.logger.error("Failed to revoke access: %s", exc)
            raise
        finally:
            self.clear_tokens()

    # State helpers ---------------------------------------------------
    def clear_tokens(self) -> None:
        self.state = OAuthTokenState()

    def set_access_token(self, access_token: Optional[str]) -> None:
        self.state.access_token = access_token

    def set_refresh_token(self, refresh_token: Optional[str]) -> None:
        self.state.refresh_token = refresh_token

    def set_expires_at(self, expires_at: Optional[str]) -> None:
        self.state.expires_at = expires_at

    def set_token_type(self, token_type: Optional[str]) -> None:
        if token_type is None:
            self.state.token_type = None
        else:
            self.state.token_type = self._normalize_token_type(token_type)

    # Internal utilities ----------------------------------------------
    def _token_request(self, data: Dict[str, Any]) -> Dict[str, Any]:
        response = self._http_client.post(self.endpoints.token_url, data=data)
        return response.json()

    def _apply_token_response(self, token_data: Dict[str, Any]) -> Dict[str, Any]:
        access_token = token_data['access_token']
        self.state.access_token = access_token

        refresh_token = token_data.get('refresh_token')
        if refresh_token:
            self.state.refresh_token = refresh_token

        self.state.token_type = self._normalize_token_type(token_data.get('token_type'))

        raw_expires_in = token_data.get('expires_in')
        expires_in = self._normalize_expires_in(raw_expires_in)
        expires_at_ts = datetime.now().timestamp() + expires_in
        expires_at = datetime.fromtimestamp(expires_at_ts).isoformat()
        self.state.expires_at = expires_at

        return {
            'access_token': access_token,
            'refresh_token': self.state.refresh_token,
            'expires_in': expires_in,
            'expires_at': expires_at,
            'token_type': self.state.token_type,
        }

    def _normalize_token_type(self, token_type: Optional[str]) -> str:
        if not token_type:
            return 'Bearer'
        normalized = token_type.strip()
        if normalized.lower() == 'bearer':
            return 'Bearer'
        return normalized

    def _normalize_expires_in(self, expires_in: Any) -> int:
        default = 3600
        if expires_in is None:
            return default
        try:
            return int(expires_in)
        except (TypeError, ValueError):
            self.logger.warning(
                "Invalid expires_in value %r; defaulting to %s", expires_in, default
            )
            return default


class OAuthCalendarAdapter(CalendarSyncAdapter):
    """Calendar adapter base that provides OAuth + HTTP helpers."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        scopes: List[str],
        endpoints: OAuthEndpoints,
        logger: Optional[logging.Logger] = None,
        http_client: Optional[RetryableHttpClient] = None,
        http_client_config: Optional[Dict[str, Any]] = None,
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.scopes = scopes
        self.endpoints = endpoints

        self.logger = logger or logging.getLogger(
            f"echonote.calendar_sync.{self.get_name()}"
        )

        self._oauth_client = OAuthHttpClient(
            endpoints=endpoints,
            logger=self.logger,
            http_client=http_client,
            http_client_config=http_client_config,
        )

    @property
    def api_base_url(self) -> str:
        return self.endpoints.api_base_url

    @property
    def http_client(self) -> RetryableHttpClient:
        """Expose the underlying HTTP client for advanced scenarios/tests."""

        return self._oauth_client.http_client

    def close(self) -> None:
        """Close the underlying HTTP client if this instance owns it."""

        self._oauth_client.close()

    def build_authorization_params(
        self, state: str, code_challenge: str
    ) -> Dict[str, Any]:
        """Base authorization parameters; subclasses may extend."""

        return {
            'client_id': self.client_id,
            'redirect_uri': self.redirect_uri,
            'response_type': 'code',
            'scope': ' '.join(self.scopes),
            'state': state,
            'code_challenge': code_challenge,
            'code_challenge_method': 'S256',
        }

    def get_authorization_url(self) -> Dict[str, str]:
        oauth_params = self._generate_state_and_pkce()
        params = self.build_authorization_params(
            oauth_params['state'], oauth_params['code_challenge']
        )

        query_string = urlencode(params, doseq=True)
        auth_url = f"{self.endpoints.auth_url}?{query_string}"

        self.logger.info("Generated authorization URL: %s", auth_url)

        return {
            'authorization_url': auth_url,
            'state': oauth_params['state'],
            'code_verifier': oauth_params['code_verifier'],
        }

    def authenticate(self, credentials: dict) -> dict:
        try:
            if 'authorization_code' in credentials:
                return self.exchange_code_for_token(
                    credentials['authorization_code'],
                    code_verifier=credentials.get('code_verifier'),
                )
            return self.get_authorization_url()
        except Exception as exc:
            self.logger.error("Authentication failed: %s", exc)
            raise

    def exchange_code_for_token(
        self, code: str, code_verifier: Optional[str] = None
    ) -> dict:
        data = {
            'code': code,
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'redirect_uri': self.redirect_uri,
            'grant_type': 'authorization_code',
        }
        if code_verifier:
            data['code_verifier'] = code_verifier

        return self._oauth_client.exchange_authorization_code(data)

    def refresh_access_token(self, code_verifier: Optional[str] = None) -> dict:
        if not self.refresh_token:
            raise ValueError("No refresh token available")

        data = {
            'refresh_token': self.refresh_token,
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'grant_type': 'refresh_token',
        }
        if code_verifier:
            data['code_verifier'] = code_verifier

        return self._oauth_client.refresh_access_token(data)

    def api_request(
        self, method: str, url: str, *, headers: Optional[Dict[str, str]] = None, **kwargs
    ):
        return self._oauth_client.api_request(
            method,
            url,
            headers=headers,
            **kwargs,
        )

    def revoke_access(self):
        request_kwargs = self.build_revoke_request()
        self._oauth_client.revoke(self.endpoints.revoke_url, request_kwargs)

    def build_revoke_request(self) -> Dict[str, Any]:
        return {'params': {'token': self.access_token}}

    # Token state passthroughs ---------------------------------------
    @property
    def access_token(self) -> Optional[str]:
        return self._oauth_client.state.access_token

    @access_token.setter
    def access_token(self, value: Optional[str]) -> None:
        self._oauth_client.set_access_token(value)

    @property
    def refresh_token(self) -> Optional[str]:
        return self._oauth_client.state.refresh_token

    @refresh_token.setter
    def refresh_token(self, value: Optional[str]) -> None:
        self._oauth_client.set_refresh_token(value)

    @property
    def expires_at(self) -> Optional[str]:
        return self._oauth_client.state.expires_at

    @expires_at.setter
    def expires_at(self, value: Optional[str]) -> None:
        self._oauth_client.set_expires_at(value)

    @property
    def token_type(self) -> Optional[str]:
        return self._oauth_client.state.token_type

    @token_type.setter
    def token_type(self, value: Optional[str]) -> None:
        self._oauth_client.set_token_type(value)

    def clear_tokens(self) -> None:
        """Reset any cached OAuth tokens (used when revoking externally)."""

        self._oauth_client.clear_tokens()
