"""
Base class for external calendar synchronization adapters.

Defines the interface that all calendar sync adapters must implement.
"""

import base64
import hashlib
import logging
import secrets
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlencode
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List

from data.database.models import CalendarEvent
from utils.http_client import RetryableHttpClient


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


@dataclass(frozen=True)
class OAuthEndpoints:
    """OAuth 2.0 endpoint bundle for calendar providers."""

    auth_url: str
    token_url: str
    api_base_url: str
    revoke_url: Optional[str] = None


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
        if http_client and http_client_config:
            raise ValueError("Provide either http_client or http_client_config, not both")

        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.scopes = scopes
        self.endpoints = endpoints

        self.access_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.expires_at: Optional[str] = None
        self.token_type: Optional[str] = None

        self.logger = logger or logging.getLogger(
            f"echonote.calendar_sync.{self.get_name()}"
        )

        http_client_config = http_client_config or {}
        self._owns_http_client = http_client is None
        self.http_client = http_client or RetryableHttpClient(**http_client_config)

    @property
    def api_base_url(self) -> str:
        return self.endpoints.api_base_url

    def close(self) -> None:
        """Close the underlying HTTP client if this instance owns it."""

        if self._owns_http_client and self.http_client:
            self.http_client.close()

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

        try:
            token_data = self._token_request(data)
            self.logger.info("Successfully exchanged authorization code")
            return self._apply_token_response(token_data)
        except Exception as exc:
            self.logger.error("Failed to exchange code for token: %s", exc)
            raise

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

        try:
            token_data = self._token_request(data)
            self.logger.info("Successfully refreshed access token")
            return self._apply_token_response(token_data)
        except Exception as exc:
            self.logger.error("Failed to refresh token: %s", exc)
            raise

    def api_request(
        self, method: str, url: str, *, headers: Optional[Dict[str, str]] = None, **kwargs
    ):
        if not self.access_token:
            raise ValueError("Not authenticated")

        token_type = self.token_type or 'Bearer'
        auth_headers = {'Authorization': f'{token_type} {self.access_token}'}
        if headers:
            auth_headers.update(headers)

        return self.http_client.request(method, url, headers=auth_headers, **kwargs)

    def revoke_access(self):
        if not self.access_token:
            self.logger.warning("No access token to revoke")
            return

        if not self.endpoints.revoke_url:
            self.logger.info("No revoke endpoint defined; clearing local tokens only")
            self._clear_tokens()
            return

        try:
            request_kwargs = self.build_revoke_request()
            self.http_client.post(self.endpoints.revoke_url, **request_kwargs)
            self.logger.info("Successfully revoked access")
        except Exception as exc:
            self.logger.error("Failed to revoke access: %s", exc)
            raise
        finally:
            self._clear_tokens()

    def build_revoke_request(self) -> Dict[str, Any]:
        return {'params': {'token': self.access_token}}

    def _token_request(self, data: Dict[str, Any]) -> Dict[str, Any]:
        response = self.http_client.post(self.endpoints.token_url, data=data)
        return response.json()

    def _apply_token_response(self, token_data: Dict[str, Any]) -> Dict[str, Any]:
        self.access_token = token_data['access_token']

        refresh_token = token_data.get('refresh_token')
        if refresh_token:
            self.refresh_token = refresh_token

        raw_token_type = token_data.get('token_type')
        self.token_type = self._normalize_token_type(raw_token_type)

        raw_expires_in = token_data.get('expires_in')
        expires_in = raw_expires_in if raw_expires_in is not None else 3600
        expires_at_ts = datetime.now().timestamp() + expires_in
        self.expires_at = datetime.fromtimestamp(expires_at_ts).isoformat()

        return {
            'access_token': self.access_token,
            'refresh_token': self.refresh_token,
            'expires_in': raw_expires_in if raw_expires_in is not None else expires_in,
            'expires_at': self.expires_at,
            'token_type': self.token_type,
        }

    def _normalize_token_type(self, token_type: Optional[str]) -> str:
        if not token_type:
            return 'Bearer'
        normalized = token_type.strip()
        if normalized.lower() == 'bearer':
            return 'Bearer'
        return normalized

    def _clear_tokens(self) -> None:
        self.access_token = None
        self.refresh_token = None
        self.expires_at = None
        self.token_type = None
