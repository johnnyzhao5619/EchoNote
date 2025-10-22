"""Google Calendar synchronization adapter."""

import logging
from datetime import timezone
from typing import Dict, Any, Optional, List

import httpx

from engines.calendar_sync.base import OAuthCalendarAdapter, OAuthEndpoints
from data.database.models import CalendarEvent


logger = logging.getLogger('echonote.calendar_sync.google')


class GoogleCalendarAdapter(OAuthCalendarAdapter):
    """Google Calendar synchronization adapter."""

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
        redirect_uri: str = "http://localhost:8080/callback",
        http_client_config: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            scopes=self.SCOPES,
            endpoints=OAuthEndpoints(
                auth_url=self.AUTH_URL,
                token_url=self.TOKEN_URL,
                api_base_url=self.API_BASE_URL,
                revoke_url=self.REVOKE_URL,
            ),
            logger=logger,
            http_client_config=http_client_config,
        )
        self.logger.info("GoogleCalendarAdapter initialized")

    def build_authorization_params(
        self, state: str, code_challenge: str
    ) -> Dict[str, Any]:
        params = super().build_authorization_params(state, code_challenge)
        params.update({
            'access_type': 'offline',
            'prompt': 'consent',
        })
        return params

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
        try:
            events = []
            deleted_events: List[str] = []
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

                response = self.api_request(
                    'GET',
                    f"{self.api_base_url}/calendars/primary/events",
                    params=params,
                    timeout=30.0,
                )
                data = response.json()

                # Convert Google events to internal format
                for item in data.get('items', []):
                    event = self._convert_google_event(item)
                    if not event:
                        continue

                    if event.get('deleted'):
                        event_id = event.get('id')
                        if event_id:
                            deleted_events.append(event_id)
                        continue

                    events.append(event)

                # Check for pagination
                page_token = data.get('nextPageToken')
                if not page_token:
                    new_sync_token = data.get('nextSyncToken')
                    break

            self.logger.info("Fetched %s events from Google", len(events))

            return {
                'events': events,
                'deleted': deleted_events,
                'sync_token': new_sync_token
            }

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 410:
                # Sync token expired, need full sync
                self.logger.warning("Sync token expired, performing full sync")
                return self.fetch_events(start_date, end_date, None)
            self.logger.error("HTTP error fetching events: %s", e)
            raise
        except Exception as e:
            self.logger.error("Failed to fetch events: %s", e)
            raise

    def push_event(self, event: CalendarEvent) -> str:
        """
        Push a local event to Google Calendar.

        Args:
            event: CalendarEvent instance

        Returns:
            Google event ID
        """
        try:
            google_event = self._convert_to_google_event(event)

            response = self.api_request(
                'POST',
                f"{self.api_base_url}/calendars/primary/events",
                json=google_event,
                headers={'Content-Type': 'application/json'},
                timeout=30.0,
            )
            data = response.json()
            google_id = data['id']

            self.logger.info("Pushed event to Google: %s", google_id)
            return google_id

        except Exception as e:
            self.logger.error("Failed to push event: %s", e)
            raise

    def update_event(self, event: CalendarEvent, external_id: str) -> None:
        """Update an existing Google Calendar event."""
        if not external_id:
            raise ValueError("Missing external event identifier")

        try:
            google_event = self._convert_to_google_event(event)

            self.api_request(
                'PATCH',
                f"{self.api_base_url}/calendars/primary/events/{external_id}",
                json=google_event,
                headers={'Content-Type': 'application/json'},
                timeout=30.0,
            )

            self.logger.info("Updated Google event: %s", external_id)

        except Exception as e:
            self.logger.error("Failed to update event %s: %s", external_id, e)
            raise

    def delete_event(self, event: CalendarEvent, external_id: str) -> None:
        """Delete an event from Google Calendar."""
        if not external_id:
            raise ValueError("Missing external event identifier")

        try:
            self.api_request(
                'DELETE',
                f"{self.api_base_url}/calendars/primary/events/{external_id}",
                timeout=30.0,
            )

            self.logger.info("Deleted Google event: %s", external_id)

        except httpx.HTTPStatusError as err:
            if err.response.status_code == 404:
                self.logger.warning("Google event %s already removed", external_id)
                return
            self.logger.error("HTTP error deleting event %s: %s", external_id, err)
            raise
        except Exception as e:
            self.logger.error("Failed to delete event %s: %s", external_id, e)
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
            status_value = google_event.get('status')
            if isinstance(status_value, str) and status_value.lower() == 'cancelled':
                event_id = google_event.get('id')
                if event_id:
                    return {'id': event_id, 'deleted': True}
                return None

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
            self.logger.error("Failed to convert Google event: %s", e)
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
        local_tz = self._get_local_timezone()
        start_dt = self._parse_event_datetime(event.start_time, local_tz)
        end_dt = self._parse_event_datetime(event.end_time, local_tz)

        def _format_google_datetime(dt_value):
            identifier = self._get_timezone_identifier(dt_value)
            payload = {'dateTime': dt_value.isoformat()}
            if identifier:
                if identifier == 'UTC':
                    payload['dateTime'] = dt_value.astimezone(timezone.utc).isoformat()
                payload['timeZone'] = identifier
            return payload

        google_event = {
            'summary': event.title,
            'start': _format_google_datetime(start_dt),
            'end': _format_google_datetime(end_dt)
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
