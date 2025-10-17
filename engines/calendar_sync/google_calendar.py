"""
Google Calendar synchronization adapter.

Implements OAuth 2.0 authentication and event synchronization
with Google Calendar API v3.
"""

import logging
import httpx
from typing import Dict, Any, Optional
from datetime import datetime

from engines.calendar_sync.base import CalendarSyncAdapter
from data.database.models import CalendarEvent


logger = logging.getLogger('echonote.calendar_sync.google')


class GoogleCalendarAdapter(CalendarSyncAdapter):
    """
    Google Calendar synchronization adapter.

    Implements OAuth 2.0 authentication and event sync using
    Google Calendar API v3.
    """

    # Google OAuth endpoints
    AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    TOKEN_URL = "https://oauth2.googleapis.com/token"
    REVOKE_URL = "https://oauth2.googleapis.com/revoke"
    API_BASE_URL = "https://www.googleapis.com/calendar/v3"

    # OAuth scopes
    SCOPES = [
        "https://www.googleapis.com/auth/calendar.readonly",
        "https://www.googleapis.com/auth/calendar.events"
    ]

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        redirect_uri: str = "http://localhost:8080/callback"
    ):
        """
        Initialize Google Calendar adapter.

        Args:
            client_id: Google OAuth client ID
            client_secret: Google OAuth client secret
            redirect_uri: OAuth redirect URI
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.access_token = None
        self.refresh_token = None
        self.expires_at: Optional[str] = None
        logger.info("GoogleCalendarAdapter initialized")

    def get_authorization_url(self) -> str:
        """
        Generate OAuth authorization URL.

        Returns:
            Authorization URL for user to visit
        """
        params = {
            'client_id': self.client_id,
            'redirect_uri': self.redirect_uri,
            'response_type': 'code',
            'scope': ' '.join(self.SCOPES),
            'access_type': 'offline',
            'prompt': 'consent'
        }

        query_string = '&'.join(
            [f"{k}={v}" for k, v in params.items()]
        )
        auth_url = f"{self.AUTH_URL}?{query_string}"

        logger.info("Generated authorization URL")
        return auth_url

    def exchange_code_for_token(self, code: str) -> dict:
        """
        Exchange authorization code for access token.

        Args:
            code: Authorization code from OAuth callback

        Returns:
            Token data dictionary
        """
        try:
            with httpx.Client() as client:
                response = client.post(
                    self.TOKEN_URL,
                    data={
                        'code': code,
                        'client_id': self.client_id,
                        'client_secret': self.client_secret,
                        'redirect_uri': self.redirect_uri,
                        'grant_type': 'authorization_code'
                    }
                )
                response.raise_for_status()

            token_data = response.json()
            self.access_token = token_data['access_token']
            self.refresh_token = token_data.get('refresh_token')

            # Calculate expiration time
            expires_in = token_data.get('expires_in', 3600)
            expires_at = datetime.now().timestamp() + expires_in
            self.expires_at = datetime.fromtimestamp(expires_at).isoformat()

            logger.info("Successfully exchanged code for token")

            return {
                'access_token': self.access_token,
                'refresh_token': self.refresh_token,
                'expires_in': expires_in,
                'expires_at': self.expires_at
            }

        except Exception as e:
            logger.error(f"Failed to exchange code for token: {e}")
            raise

    def authenticate(self, credentials: dict) -> dict:
        """
        Perform OAuth authentication.

        Args:
            credentials: Dictionary with client_id, client_secret,
                        and optionally authorization_code

        Returns:
            Token data dictionary
        """
        try:
            if 'authorization_code' in credentials:
                return self.exchange_code_for_token(
                    credentials['authorization_code']
                )
            else:
                # Return authorization URL for user to visit
                return {
                    'authorization_url': self.get_authorization_url()
                }

        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            raise

    def refresh_access_token(self) -> dict:
        """
        Refresh the access token using refresh token.

        Returns:
            New token data
        """
        if not self.refresh_token:
            raise ValueError("No refresh token available")

        try:
            with httpx.Client() as client:
                response = client.post(
                    self.TOKEN_URL,
                    data={
                        'refresh_token': self.refresh_token,
                        'client_id': self.client_id,
                        'client_secret': self.client_secret,
                        'grant_type': 'refresh_token'
                    }
                )
                response.raise_for_status()

            token_data = response.json()
            self.access_token = token_data['access_token']

            expires_in = token_data.get('expires_in', 3600)
            expires_at = datetime.now().timestamp() + expires_in
            self.expires_at = datetime.fromtimestamp(expires_at).isoformat()

            logger.info("Successfully refreshed access token")

            return {
                'access_token': self.access_token,
                'refresh_token': self.refresh_token,
                'expires_in': expires_in,
                'expires_at': self.expires_at
            }

        except Exception as e:
            logger.error(f"Failed to refresh token: {e}")
            raise

    def fetch_events(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        last_sync_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Fetch events from Google Calendar.

        Args:
            start_date: Optional start date in ISO format
            end_date: Optional end date in ISO format
            last_sync_token: Optional sync token for incremental sync

        Returns:
            Dictionary with events and new sync token
        """
        if not self.access_token:
            raise ValueError("Not authenticated")

        try:
            events = []
            page_token = None
            new_sync_token = None

            while True:
                params = {
                    'maxResults': 250,
                    'singleEvents': True,
                    'orderBy': 'startTime'
                }

                # Use sync token for incremental sync
                if last_sync_token:
                    params['syncToken'] = last_sync_token
                else:
                    if start_date:
                        params['timeMin'] = start_date
                    if end_date:
                        params['timeMax'] = end_date

                if page_token:
                    params['pageToken'] = page_token

                with httpx.Client() as client:
                    response = client.get(
                        f"{self.API_BASE_URL}/calendars/primary/events",
                        params=params,
                        headers={
                            'Authorization': f'Bearer {self.access_token}'
                        },
                        timeout=30.0
                    )
                    response.raise_for_status()

                data = response.json()

                # Convert Google events to internal format
                for item in data.get('items', []):
                    event = self._convert_google_event(item)
                    if event:
                        events.append(event)

                # Check for pagination
                page_token = data.get('nextPageToken')
                if not page_token:
                    new_sync_token = data.get('nextSyncToken')
                    break

            logger.info(f"Fetched {len(events)} events from Google")

            return {
                'events': events,
                'sync_token': new_sync_token
            }

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 410:
                # Sync token expired, need full sync
                logger.warning("Sync token expired, performing full sync")
                return self.fetch_events(start_date, end_date, None)
            logger.error(f"HTTP error fetching events: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to fetch events: {e}")
            raise

    def push_event(self, event: CalendarEvent) -> str:
        """
        Push a local event to Google Calendar.

        Args:
            event: CalendarEvent instance

        Returns:
            Google event ID
        """
        if not self.access_token:
            raise ValueError("Not authenticated")

        try:
            google_event = self._convert_to_google_event(event)

            with httpx.Client() as client:
                response = client.post(
                    f"{self.API_BASE_URL}/calendars/primary/events",
                    json=google_event,
                    headers={
                        'Authorization': f'Bearer {self.access_token}',
                        'Content-Type': 'application/json'
                    },
                    timeout=30.0
                )
                response.raise_for_status()

            data = response.json()
            google_id = data['id']

            logger.info(f"Pushed event to Google: {google_id}")
            return google_id

        except Exception as e:
            logger.error(f"Failed to push event: {e}")
            raise

    def revoke_access(self):
        """
        Revoke OAuth access token.
        """
        if not self.access_token:
            logger.warning("No access token to revoke")
            return

        try:
            with httpx.Client() as client:
                response = client.post(
                    self.REVOKE_URL,
                    params={'token': self.access_token},
                    timeout=10.0
                )
                response.raise_for_status()

            self.access_token = None
            self.refresh_token = None

            logger.info("Successfully revoked access")

        except Exception as e:
            logger.error(f"Failed to revoke access: {e}")
            raise

    def _convert_google_event(self, google_event: dict) -> Optional[dict]:
        """
        Convert Google Calendar event to internal format.

        Args:
            google_event: Google event data

        Returns:
            Internal event format or None if conversion fails
        """
        try:
            # Extract start and end times
            start = google_event.get('start', {})
            end = google_event.get('end', {})

            start_time = start.get('dateTime') or start.get('date')
            end_time = end.get('dateTime') or end.get('date')

            if not start_time or not end_time:
                return None

            # Extract attendees
            attendees = [
                att['email']
                for att in google_event.get('attendees', [])
                if 'email' in att
            ]

            # Extract reminder
            reminder_minutes = None
            reminders = google_event.get('reminders', {})
            if reminders.get('useDefault'):
                reminder_minutes = 10  # Default
            elif reminders.get('overrides'):
                # Use first reminder
                reminder_minutes = reminders['overrides'][0].get(
                    'minutes'
                )

            return {
                'id': google_event['id'],
                'title': google_event.get('summary', 'Untitled'),
                'event_type': 'Event',
                'start_time': start_time,
                'end_time': end_time,
                'location': google_event.get('location'),
                'attendees': attendees,
                'description': google_event.get('description'),
                'reminder_minutes': reminder_minutes,
                'recurrence_rule': (
                    google_event.get('recurrence', [None])[0]
                    if google_event.get('recurrence') else None
                )
            }

        except Exception as e:
            logger.error(f"Failed to convert Google event: {e}")
            return None

    def _convert_to_google_event(
        self,
        event: CalendarEvent
    ) -> dict:
        """
        Convert internal event to Google Calendar format.

        Args:
            event: CalendarEvent instance

        Returns:
            Google event format
        """
        google_event = {
            'summary': event.title,
            'start': {
                'dateTime': event.start_time,
                'timeZone': 'UTC'
            },
            'end': {
                'dateTime': event.end_time,
                'timeZone': 'UTC'
            }
        }

        if event.location:
            google_event['location'] = event.location

        if event.description:
            google_event['description'] = event.description

        if event.attendees:
            google_event['attendees'] = [
                {'email': email} for email in event.attendees
            ]

        if event.reminder_minutes is not None:
            google_event['reminders'] = {
                'useDefault': False,
                'overrides': [
                    {
                        'method': 'popup',
                        'minutes': event.reminder_minutes
                    }
                ]
            }

        if event.recurrence_rule:
            google_event['recurrence'] = [event.recurrence_rule]

        return google_event
