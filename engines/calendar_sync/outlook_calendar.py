"""Outlook Calendar synchronization adapter."""

import logging
from typing import Dict, Any, Optional, List

import httpx

from engines.calendar_sync.base import OAuthCalendarAdapter, OAuthEndpoints
from data.database.models import CalendarEvent


logger = logging.getLogger('echonote.calendar_sync.outlook')


IANA_TO_WINDOWS_MAP = {
    'UTC': 'UTC',
    'Etc/UTC': 'UTC',
    'Etc/GMT': 'UTC',
    'GMT': 'UTC',
    'Asia/Shanghai': 'China Standard Time',
    'Asia/Tokyo': 'Tokyo Standard Time',
    'Asia/Kolkata': 'India Standard Time',
    'America/New_York': 'Eastern Standard Time',
    'America/Los_Angeles': 'Pacific Standard Time',
    'America/Chicago': 'Central Standard Time',
    'America/Denver': 'Mountain Standard Time',
    'Europe/London': 'GMT Standard Time',
    'Europe/Berlin': 'W. Europe Standard Time',
    'Australia/Sydney': 'AUS Eastern Standard Time',
}


class OutlookCalendarAdapter(OAuthCalendarAdapter):
    """Outlook Calendar synchronization adapter."""

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
                revoke_url=None,
            ),
            logger=logger,
            http_client_config=http_client_config,
        )
        self.logger.info("OutlookCalendarAdapter initialized")

    def build_authorization_params(
        self, state: str, code_challenge: str
    ) -> Dict[str, Any]:
        params = super().build_authorization_params(state, code_challenge)
        params['response_mode'] = 'query'
        return params

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
        try:
            events = []
            deleted_events: List[str] = []
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
                response = self.api_request(
                    'GET',
                    url if next_link else url,
                    headers={'Prefer': 'odata.maxpagesize=250'},
                    timeout=30.0,
                )
                data = response.json()

                # Convert Outlook events to internal format
                for item in data.get('value', []):
                    event = self._convert_outlook_event(item)
                    if not event:
                        continue

                    if event.get('deleted'):
                        event_id = event.get('id')
                        if event_id:
                            deleted_events.append(event_id)
                        continue

                    events.append(event)

                # Check for pagination
                next_link = data.get('@odata.nextLink')
                if not next_link:
                    new_delta_link = data.get('@odata.deltaLink')
                    break
                else:
                    url = next_link

            self.logger.info("Fetched %s events from Outlook", len(events))

            return {
                'events': events,
                'deleted': deleted_events,
                'sync_token': new_delta_link
            }

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 410:
                # Delta link expired, need full sync
                self.logger.warning(
                    "Delta link expired, performing full sync"
                )
                return self.fetch_events(start_date, end_date, None)
            self.logger.error("HTTP error fetching events: %s", e)
            raise
        except Exception as e:
            self.logger.error("Failed to fetch events: %s", e)
            raise

    def push_event(self, event: CalendarEvent) -> str:
        """
        Push a local event to Outlook Calendar.

        Args:
            event: CalendarEvent instance

        Returns:
            Outlook event ID
        """
        try:
            outlook_event = self._convert_to_outlook_event(event)

            response = self.api_request(
                'POST',
                f"{self.api_base_url}/me/calendar/events",
                json=outlook_event,
                headers={'Content-Type': 'application/json'},
                timeout=30.0,
            )
            data = response.json()
            outlook_id = data['id']

            self.logger.info("Pushed event to Outlook: %s", outlook_id)
            return outlook_id

        except Exception as e:
            self.logger.error("Failed to push event: %s", e)
            raise

    def update_event(self, event: CalendarEvent, external_id: str) -> None:
        """Update an existing Outlook calendar event."""
        if not external_id:
            raise ValueError("Missing external event identifier")

        try:
            outlook_event = self._convert_to_outlook_event(event)

            self.api_request(
                'PATCH',
                f"{self.api_base_url}/me/events/{external_id}",
                json=outlook_event,
                headers={'Content-Type': 'application/json'},
                timeout=30.0,
            )

            self.logger.info("Updated Outlook event: %s", external_id)

        except Exception as e:
            self.logger.error("Failed to update Outlook event %s: %s", external_id, e)
            raise

    def delete_event(self, event: CalendarEvent, external_id: str) -> None:
        """Delete an Outlook calendar event."""
        if not external_id:
            raise ValueError("Missing external event identifier")

        try:
            self.api_request(
                'DELETE',
                f"{self.api_base_url}/me/events/{external_id}",
                timeout=30.0,
            )

            self.logger.info("Deleted Outlook event: %s", external_id)

        except httpx.HTTPStatusError as err:
            if err.response.status_code == 404:
                self.logger.warning(
                    "Outlook event %s already removed", external_id
                )
                return
            self.logger.error(
                "HTTP error deleting Outlook event %s: %s", external_id, err
            )
            raise
        except Exception as e:
            self.logger.error("Failed to delete Outlook event %s: %s", external_id, e)
            raise

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
            show_as_value = outlook_event.get('showAs')
            if isinstance(show_as_value, str) and show_as_value.lower() == 'cancelled':
                event_id = outlook_event.get('id')
                if event_id:
                    return {'id': event_id, 'deleted': True}
                return None

            if outlook_event.get('isCancelled'):
                event_id = outlook_event.get('id')
                if event_id:
                    return {'id': event_id, 'deleted': True}
                return None

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
            self.logger.error("Failed to convert Outlook event: %s", e)
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
        local_tz = self._get_local_timezone()
        start_dt = self._parse_event_datetime(event.start_time, local_tz)
        end_dt = self._parse_event_datetime(event.end_time, local_tz)

        def _to_windows_timezone(identifier: str) -> str:
            if identifier in IANA_TO_WINDOWS_MAP:
                return IANA_TO_WINDOWS_MAP[identifier]
            if identifier.startswith('UTC') and identifier not in IANA_TO_WINDOWS_MAP:
                if identifier.endswith(':00'):
                    return identifier[:-3]
                return identifier
            return 'UTC'

        def _format_outlook_datetime(dt_value):
            identifier = self._get_timezone_identifier(dt_value) or 'UTC'
            tzinfo_value = self._timezone_from_identifier(identifier)
            localized = dt_value.astimezone(tzinfo_value)
            payload = {
                'dateTime': localized.replace(tzinfo=None).isoformat(),
                'timeZone': _to_windows_timezone(identifier)
            }
            return payload

        outlook_event = {
            'subject': event.title,
            'start': _format_outlook_datetime(start_dt),
            'end': _format_outlook_datetime(end_dt)
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
