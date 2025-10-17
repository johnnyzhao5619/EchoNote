"""
Outlook Calendar synchronization adapter.

Implements OAuth 2.0 authentication and event synchronization
with Microsoft Graph API.
"""

import logging
from urllib.parse import urlencode

import httpx
from typing import Dict, Any, Optional
from datetime import datetime

from engines.calendar_sync.base import CalendarSyncAdapter
from data.database.models import CalendarEvent


logger = logging.getLogger('echonote.calendar_sync.outlook')


class OutlookCalendarAdapter(CalendarSyncAdapter):
    """
    Outlook Calendar synchronization adapter.

    Implements OAuth 2.0 authentication and event sync using
    Microsoft Graph API.
    """

    # Microsoft OAuth endpoints
    AUTH_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"  # noqa: E501
    TOKEN_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/token"  # noqa: E501
    API_BASE_URL = "https://graph.microsoft.com/v1.0"

    # OAuth scopes
    SCOPES = [
        "Calendars.Read",
        "Calendars.ReadWrite"
    ]

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        redirect_uri: str = "http://localhost:8080/callback"
    ):
        """
        Initialize Outlook Calendar adapter.

        Args:
            client_id: Microsoft OAuth client ID
            client_secret: Microsoft OAuth client secret
            redirect_uri: OAuth redirect URI
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.access_token = None
        self.refresh_token = None
        self.expires_at: Optional[str] = None
        self.token_type: Optional[str] = None
        logger.info("OutlookCalendarAdapter initialized")

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
            'response_mode': 'query'
        }

        query_string = urlencode(params, doseq=True)
        auth_url = f"{self.AUTH_URL}?{query_string}"

        logger.info("Generated Outlook authorization URL: %s", auth_url)
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
            token_type = token_data.get('token_type', 'Bearer')
            self.token_type = token_type

            # Calculate expiration time
            raw_expires_in = token_data.get('expires_in')
            expires_in = raw_expires_in if raw_expires_in is not None else 3600
            expires_at = datetime.now().timestamp() + expires_in
            self.expires_at = datetime.fromtimestamp(expires_at).isoformat()

            logger.info("Successfully exchanged code for token")

            return {
                'access_token': self.access_token,
                'refresh_token': self.refresh_token,
                'expires_in': raw_expires_in if raw_expires_in is not None else expires_in,
                'expires_at': self.expires_at,
                'token_type': token_type
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
            token_type = token_data.get('token_type', 'Bearer')
            self.token_type = token_type

            new_refresh_token = token_data.get('refresh_token')
            if new_refresh_token:
                self.refresh_token = new_refresh_token

            raw_expires_in = token_data.get('expires_in')
            expires_in = raw_expires_in if raw_expires_in is not None else 3600
            expires_at = datetime.now().timestamp() + expires_in
            self.expires_at = datetime.fromtimestamp(expires_at).isoformat()

            logger.info("Successfully refreshed access token")

            return {
                'access_token': self.access_token,
                'refresh_token': self.refresh_token,
                'expires_in': raw_expires_in if raw_expires_in is not None else expires_in,
                'expires_at': self.expires_at,
                'token_type': token_type
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
        Fetch events from Outlook Calendar.

        Args:
            start_date: Optional start date in ISO format
            end_date: Optional end date in ISO format
            last_sync_token: Optional delta link for incremental sync

        Returns:
            Dictionary with events and new delta link
        """
        if not self.access_token:
            raise ValueError("Not authenticated")

        try:
            events = []
            next_link = None
            new_delta_link = None

            # Use delta link for incremental sync
            if last_sync_token:
                url = last_sync_token
            else:
                url = f"{self.API_BASE_URL}/me/calendar/events"
                params = []

                if start_date:
                    params.append(
                        f"start/dateTime ge '{start_date}'"
                    )
                if end_date:
                    params.append(
                        f"end/dateTime le '{end_date}'"
                    )

                if params:
                    filter_str = ' and '.join(params)
                    url += f"?$filter={filter_str}"

                # Request delta link for next sync
                url += ('&' if '?' in url else '?') + '$deltatoken=latest'

            while True:
                with httpx.Client() as client:
                    response = client.get(
                        url if next_link else url,
                        headers={
                            'Authorization': f'Bearer {self.access_token}',
                            'Prefer': 'odata.maxpagesize=250'
                        },
                        timeout=30.0
                    )
                    response.raise_for_status()

                data = response.json()

                # Convert Outlook events to internal format
                for item in data.get('value', []):
                    event = self._convert_outlook_event(item)
                    if event:
                        events.append(event)

                # Check for pagination
                next_link = data.get('@odata.nextLink')
                if not next_link:
                    new_delta_link = data.get('@odata.deltaLink')
                    break
                else:
                    url = next_link

            logger.info(f"Fetched {len(events)} events from Outlook")

            return {
                'events': events,
                'sync_token': new_delta_link
            }

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 410:
                # Delta link expired, need full sync
                logger.warning(
                    "Delta link expired, performing full sync"
                )
                return self.fetch_events(start_date, end_date, None)
            logger.error(f"HTTP error fetching events: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to fetch events: {e}")
            raise

    def push_event(self, event: CalendarEvent) -> str:
        """
        Push a local event to Outlook Calendar.

        Args:
            event: CalendarEvent instance

        Returns:
            Outlook event ID
        """
        if not self.access_token:
            raise ValueError("Not authenticated")

        try:
            outlook_event = self._convert_to_outlook_event(event)

            with httpx.Client() as client:
                response = client.post(
                    f"{self.API_BASE_URL}/me/calendar/events",
                    json=outlook_event,
                    headers={
                        'Authorization': f'Bearer {self.access_token}',
                        'Content-Type': 'application/json'
                    },
                    timeout=30.0
                )
                response.raise_for_status()

            data = response.json()
            outlook_id = data['id']

            logger.info(f"Pushed event to Outlook: {outlook_id}")
            return outlook_id

        except Exception as e:
            logger.error(f"Failed to push event: {e}")
            raise

    def revoke_access(self):
        """
        Revoke OAuth access token.

        Note: Microsoft doesn't provide a direct revoke endpoint,
        so we just clear the local tokens.
        """
        self.access_token = None
        self.refresh_token = None
        logger.info("Cleared access tokens")

    def _convert_outlook_event(
        self,
        outlook_event: dict
    ) -> Optional[dict]:
        """
        Convert Outlook Calendar event to internal format.

        Args:
            outlook_event: Outlook event data

        Returns:
            Internal event format or None if conversion fails
        """
        try:
            # Extract start and end times
            start = outlook_event.get('start', {})
            end = outlook_event.get('end', {})

            start_time = start.get('dateTime')
            end_time = end.get('dateTime')

            if not start_time or not end_time:
                return None

            # Extract attendees
            attendees = [
                att['emailAddress']['address']
                for att in outlook_event.get('attendees', [])
                if 'emailAddress' in att and 'address' in att['emailAddress']  # noqa: E501
            ]

            # Extract reminder
            reminder_minutes = None
            if outlook_event.get('isReminderOn'):
                reminder_minutes = outlook_event.get(
                    'reminderMinutesBeforeStart'
                )

            # Extract recurrence
            recurrence_rule = None
            if outlook_event.get('recurrence'):
                # Convert Outlook recurrence to iCalendar format
                # This is simplified - full implementation would be complex
                pattern = outlook_event['recurrence'].get('pattern', {})
                if pattern.get('type') == 'daily':
                    recurrence_rule = f"FREQ=DAILY;INTERVAL={pattern.get('interval', 1)}"  # noqa: E501
                elif pattern.get('type') == 'weekly':
                    recurrence_rule = f"FREQ=WEEKLY;INTERVAL={pattern.get('interval', 1)}"  # noqa: E501

            return {
                'id': outlook_event['id'],
                'title': outlook_event.get('subject', 'Untitled'),
                'event_type': 'Event',
                'start_time': start_time,
                'end_time': end_time,
                'location': outlook_event.get('location', {}).get(
                    'displayName'
                ),
                'attendees': attendees,
                'description': outlook_event.get('bodyPreview'),
                'reminder_minutes': reminder_minutes,
                'recurrence_rule': recurrence_rule
            }

        except Exception as e:
            logger.error(f"Failed to convert Outlook event: {e}")
            return None

    def _convert_to_outlook_event(
        self,
        event: CalendarEvent
    ) -> dict:
        """
        Convert internal event to Outlook Calendar format.

        Args:
            event: CalendarEvent instance

        Returns:
            Outlook event format
        """
        outlook_event = {
            'subject': event.title,
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
            outlook_event['location'] = {
                'displayName': event.location
            }

        if event.description:
            outlook_event['body'] = {
                'contentType': 'text',
                'content': event.description
            }

        if event.attendees:
            outlook_event['attendees'] = [
                {
                    'emailAddress': {'address': email},
                    'type': 'required'
                }
                for email in event.attendees
            ]

        if event.reminder_minutes is not None:
            outlook_event['isReminderOn'] = True
            outlook_event['reminderMinutesBeforeStart'] = (
                event.reminder_minutes
            )

        # Note: Recurrence conversion from iCalendar to Outlook format
        # would require more complex parsing - simplified here
        if event.recurrence_rule:
            if 'DAILY' in event.recurrence_rule:
                outlook_event['recurrence'] = {
                    'pattern': {
                        'type': 'daily',
                        'interval': 1
                    },
                    'range': {
                        'type': 'noEnd',
                        'startDate': event.start_time.split('T')[0]
                    }
                }
            elif 'WEEKLY' in event.recurrence_rule:
                outlook_event['recurrence'] = {
                    'pattern': {
                        'type': 'weekly',
                        'interval': 1
                    },
                    'range': {
                        'type': 'noEnd',
                        'startDate': event.start_time.split('T')[0]
                    }
                }

        return outlook_event
