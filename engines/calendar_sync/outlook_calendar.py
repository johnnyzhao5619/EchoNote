"""Outlook Calendar synchronization adapter."""

import logging
import re
from html import unescape
from datetime import datetime, timezone, timedelta, tzinfo
from typing import Dict, Any, Optional, List

import httpx

from engines.calendar_sync.base import OAuthCalendarAdapter, OAuthEndpoints
from data.database.models import CalendarEvent


logger = logging.getLogger('echonote.calendar_sync.outlook')


DEFAULT_IANA_TO_WINDOWS_MAP = {
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
    'America/Sao_Paulo': 'E. South America Standard Time',
    'Europe/London': 'GMT Standard Time',
    'Europe/Berlin': 'W. Europe Standard Time',
    'Europe/Paris': 'Romance Standard Time',
    'Africa/Nairobi': 'E. Africa Standard Time',
    'Australia/Sydney': 'AUS Eastern Standard Time',
}

IANA_TO_WINDOWS_MAP = DEFAULT_IANA_TO_WINDOWS_MAP

WINDOWS_TO_IANA_MAP = {
    value: key for key, value in DEFAULT_IANA_TO_WINDOWS_MAP.items()
}


class OutlookCalendarAdapter(OAuthCalendarAdapter):
    """Outlook Calendar synchronization adapter."""

    _RRULE_WEEKDAY_MAP = {
        'MO': 'monday',
        'TU': 'tuesday',
        'WE': 'wednesday',
        'TH': 'thursday',
        'FR': 'friday',
        'SA': 'saturday',
        'SU': 'sunday',
    }

    _RRULE_DAY_PATTERN = re.compile(r'^[+-]?\d*(?P<day>MO|TU|WE|TH|FR|SA|SU)$')

    # Microsoft OAuth endpoints
    AUTH_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"  # noqa: E501
    TOKEN_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/token"  # noqa: E501
    API_BASE_URL = "https://graph.microsoft.com/v1.0"

    # OAuth scopes
    SCOPES = [
        "Calendars.Read",
        "Calendars.ReadWrite",
        "User.Read",
        "offline_access",
        "openid",
        "profile",
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
        self._iana_to_windows_map: Dict[str, str] = {}
        self._timezone_map_loaded = False

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
            new_delta_link = None

            token = (last_sync_token or '').strip()
            if token:
                current_url = token
            else:
                base_url = f"{self.API_BASE_URL}/me/calendar/events/delta"
                filters = []

                if start_date:
                    filters.append(
                        f"start/dateTime ge '{start_date}'"
                    )
                if end_date:
                    filters.append(
                        f"end/dateTime le '{end_date}'"
                    )

                if filters:
                    filter_str = ' and '.join(filters)
                    current_url = f"{base_url}?$filter={filter_str}"
                else:
                    current_url = base_url

            while True:
                response = self.api_request(
                    'GET',
                    current_url,
                    headers={'Prefer': 'odata.maxpagesize=250'},
                    timeout=30.0,
                )
                data = response.json()

                # Convert Outlook events to internal format
                for item in data.get('value', []):
                    removed_payload = item.get('@removed')
                    if removed_payload is not None:
                        event_id = item.get('id')
                        if event_id:
                            deleted_events.append(event_id)
                        continue

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
                if next_link:
                    current_url = next_link
                    continue

                new_delta_link = data.get('@odata.deltaLink')
                break

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
            removed_payload = outlook_event.get('@removed')
            if removed_payload is not None:
                event_id = outlook_event.get('id')
                if event_id and (
                    not outlook_event.get('start') or not outlook_event.get('end')
                ):
                    return {'id': event_id, 'deleted': True}

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

            start_time_raw = start.get('dateTime')
            end_time_raw = end.get('dateTime')

            if not start_time_raw or not end_time_raw:
                return None

            fallback_start_identifier = outlook_event.get('originalStartTimeZone')
            fallback_end_identifier = outlook_event.get(
                'originalEndTimeZone', fallback_start_identifier
            )

            def _normalise_identifier(identifier: Optional[str]) -> Optional[str]:
                if not identifier:
                    return None
                normalised = identifier.strip()
                if not normalised:
                    return None
                return WINDOWS_TO_IANA_MAP.get(normalised, normalised)

            def _prepare_datetime_text(value: str) -> str:
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

            def _convert_datetime(
                payload: dict,
                *,
                fallback_identifier: Optional[str],
                is_all_day: bool,
            ) -> Optional[str]:
                value = payload.get('dateTime')
                if not value:
                    return None

                identifier = _normalise_identifier(
                    payload.get('timeZone') or fallback_identifier
                )

                # For all-day events, only keep the calendar date
                if is_all_day or 'T' not in value:
                    text = value.strip()
                    if 'T' in text:
                        try:
                            parsed = datetime.fromisoformat(_prepare_datetime_text(text))
                            if identifier:
                                tzinfo_value = self._timezone_from_identifier(identifier)
                                if parsed.tzinfo:
                                    parsed = parsed.astimezone(tzinfo_value)
                                else:
                                    parsed = parsed.replace(tzinfo=tzinfo_value)
                            return parsed.date().isoformat()
                        except Exception:  # pragma: no cover - fallback to raw date
                            pass
                    return text[:10]

                try:
                    parsed_value = datetime.fromisoformat(
                        _prepare_datetime_text(value)
                    )
                except ValueError:
                    self.logger.warning(
                        "Failed to parse Outlook datetime value: %s", value
                    )
                    return value

                if identifier:
                    tzinfo_value = self._timezone_from_identifier(identifier)
                    if parsed_value.tzinfo:
                        parsed_value = parsed_value.astimezone(tzinfo_value)
                    else:
                        parsed_value = parsed_value.replace(tzinfo=tzinfo_value)
                elif parsed_value.tzinfo is None:
                    parsed_value = parsed_value.replace(tzinfo=timezone.utc)

                return parsed_value.isoformat()

            is_all_day = bool(outlook_event.get('isAllDay'))
            if not is_all_day:
                if isinstance(start_time_raw, str) and 'T' not in start_time_raw:
                    is_all_day = True
                elif isinstance(end_time_raw, str) and 'T' not in end_time_raw:
                    is_all_day = True

            start_time = _convert_datetime(
                start,
                fallback_identifier=fallback_start_identifier,
                is_all_day=is_all_day,
            )
            end_time = _convert_datetime(
                end,
                fallback_identifier=fallback_end_identifier,
                is_all_day=is_all_day,
            )

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

            def _extract_description() -> Optional[str]:
                def _normalise_plain_text(value: str) -> str:
                    text_value = value.replace('\r\n', '\n').replace('\r', '\n')
                    text_value = text_value.replace('\xa0', ' ')
                    text_value = re.sub(r'\s+\n', '\n', text_value)
                    text_value = re.sub(r'\n{3,}', '\n\n', text_value)
                    return text_value.strip()

                body_payload = outlook_event.get('body')
                if isinstance(body_payload, dict):
                    content = body_payload.get('content')
                    if isinstance(content, str):
                        content_type = str(body_payload.get('contentType') or '').lower()
                        text = content
                        if content_type == 'html':
                            text = re.sub(
                                r'<(script|style)[^>]*?>.*?</\\1>',
                                '',
                                text,
                                flags=re.IGNORECASE | re.DOTALL,
                            )
                            text = re.sub(
                                r'<br\s*/?>',
                                '\n',
                                text,
                                flags=re.IGNORECASE,
                            )
                            text = re.sub(
                                r'</p\s*>',
                                '\n',
                                text,
                                flags=re.IGNORECASE,
                            )
                            text = re.sub(r'<[^>]+>', '', text)
                        text = unescape(text)
                        cleaned = _normalise_plain_text(text)
                        if cleaned:
                            return cleaned

                preview = outlook_event.get('bodyPreview')
                if isinstance(preview, str):
                    cleaned_preview = _normalise_plain_text(unescape(preview))
                    if cleaned_preview:
                        return cleaned_preview

                return None

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
                'description': _extract_description(),
                'reminder_minutes': reminder_minutes,
                'recurrence_rule': recurrence_rule
            }

        except Exception as e:
            self.logger.error("Failed to convert Outlook event: %s", e)
            return None

    _UTC_OFFSET_PATTERN = re.compile(r"^UTC(?P<sign>[+-])(?P<hours>\d{1,2})(?::?(?P<minutes>\d{2}))?$")

    def _normalize_utc_offset_name(self, identifier: str) -> Optional[str]:
        if identifier == 'UTC':
            return 'UTC'
        match = self._UTC_OFFSET_PATTERN.match(identifier)
        if not match:
            return None
        sign = match.group('sign')
        hours = int(match.group('hours'))
        minutes_group = match.group('minutes')
        minutes = int(minutes_group) if minutes_group else 0
        return f"UTC{sign}{hours:02d}:{minutes:02d}"

    def _query_supported_timezones(self, standard: str) -> List[Dict[str, Any]]:
        url = (
            f"{self.api_base_url}/me/outlook/supportedTimeZones("
            f"TimeZoneStandard=microsoft.graph.timeZoneStandard'{standard}')"
        )
        response = self.api_request('GET', url, timeout=30.0)
        data = response.json()
        return data.get('value', []) if isinstance(data, dict) else []

    def _fetch_supported_timezone_mappings(self) -> Dict[str, str]:
        if not self.access_token:
            return {}

        try:
            windows_timezones = self._query_supported_timezones('Windows')
            iana_timezones = self._query_supported_timezones('Iana')
        except Exception as exc:
            self.logger.warning(
                "Failed to load Outlook supported time zones dynamically: %s",
                exc
            )
            return {}

        mapping: Dict[str, str] = {}
        windows_by_display: Dict[str, str] = {}

        for entry in windows_timezones:
            windows_name = entry.get('alias') or entry.get('name')
            display_name = entry.get('displayName')
            if not windows_name:
                continue
            if display_name and display_name not in windows_by_display:
                windows_by_display[display_name] = windows_name
            mapping[windows_name] = windows_name

        for entry in iana_timezones:
            iana_name = entry.get('alias') or entry.get('name')
            display_name = entry.get('displayName')
            if not iana_name:
                continue
            if display_name and display_name in windows_by_display:
                mapping[iana_name] = windows_by_display[display_name]

        return mapping

    def _get_iana_to_windows_map(self) -> Dict[str, str]:
        if not self._timezone_map_loaded:
            mapping = self._fetch_supported_timezone_mappings()
            if not mapping:
                mapping = dict(DEFAULT_IANA_TO_WINDOWS_MAP)
                self.logger.debug(
                    "Using default Outlook timezone mapping with %d entries",
                    len(mapping)
                )
            mapping.setdefault('UTC', 'UTC')
            mapping.setdefault('Etc/UTC', 'UTC')
            mapping.setdefault('Etc/GMT', 'UTC')
            mapping.setdefault('GMT', 'UTC')
            self._iana_to_windows_map = mapping
            self._timezone_map_loaded = True
        return self._iana_to_windows_map

    def _to_windows_timezone(self, identifier: str, dt_value: datetime) -> str:
        normalized_offset = self._normalize_utc_offset_name(identifier)
        if normalized_offset:
            return normalized_offset

        mapping = self._get_iana_to_windows_map()
        mapped = mapping.get(identifier)
        if mapped:
            return mapped

        offset = dt_value.utcoffset()
        if offset is not None:
            total_minutes = int(offset.total_seconds() // 60)
            sign = '+' if total_minutes >= 0 else '-'
            total_minutes = abs(total_minutes)
            hours, minutes = divmod(total_minutes, 60)
            return f"UTC{sign}{hours:02d}:{minutes:02d}"

        self.logger.warning(
            "Unable to determine Outlook timezone for identifier '%s'; using UTC",
            identifier
        )
        return 'UTC'

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

        try:
            is_all_day = bool(event.is_all_day_event())
        except AttributeError:
            is_all_day = False
        except Exception:  # pragma: no cover - defensive guard
            is_all_day = False

        if is_all_day:
            target_tz = local_tz or start_dt.tzinfo or timezone.utc

            def _to_target_timezone(dt_value: datetime) -> datetime:
                if dt_value.tzinfo:
                    return dt_value.astimezone(target_tz)
                return dt_value.replace(tzinfo=target_tz)

            start_local = _to_target_timezone(start_dt)
            end_local = _to_target_timezone(end_dt)

            normalized_start = start_local.replace(
                hour=0,
                minute=0,
                second=0,
                microsecond=0,
            )

            day_span = (end_local.date() - start_local.date()).days
            if day_span <= 0:
                day_span = 1

            normalized_end = normalized_start + timedelta(days=day_span)

            start_dt = normalized_start
            end_dt = normalized_end

        def _format_outlook_datetime(dt_value):
            identifier = self._get_timezone_identifier(dt_value) or 'UTC'
            tzinfo_value = self._timezone_from_identifier(identifier)
            localized = dt_value.astimezone(tzinfo_value)
            payload = {
                'dateTime': localized.replace(tzinfo=None).isoformat(),
                'timeZone': self._to_windows_timezone(identifier, localized)
            }
            return payload

        outlook_event = {
            'subject': event.title,
            'start': _format_outlook_datetime(start_dt),
            'end': _format_outlook_datetime(end_dt)
        }

        if is_all_day:
            outlook_event['isAllDay'] = True

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

        if event.recurrence_rule:
            recurrence_payload = self._build_recurrence_payload(
                event.recurrence_rule,
                start_dt,
                local_tz,
            )
            if recurrence_payload:
                outlook_event['recurrence'] = recurrence_payload

        return outlook_event

    def _build_recurrence_payload(
        self,
        rule: str,
        start_dt: datetime,
        local_tz: Optional[tzinfo]
    ) -> Optional[Dict[str, Any]]:
        if not rule:
            return None

        components: Dict[str, str] = {}
        for segment in rule.split(';'):
            if not segment or '=' not in segment:
                continue
            key, value = segment.split('=', 1)
            components[key.upper()] = value

        freq = components.get('FREQ', '').upper()
        if not freq:
            return None

        pattern: Dict[str, Any] = {}
        if freq == 'DAILY':
            pattern['type'] = 'daily'
        elif freq == 'WEEKLY':
            pattern['type'] = 'weekly'
        else:
            return None

        try:
            interval_value = int(components.get('INTERVAL', '1'))
        except ValueError:
            interval_value = 1
        if interval_value < 1:
            interval_value = 1
        pattern['interval'] = interval_value

        if freq == 'WEEKLY':
            byday_value = components.get('BYDAY')
            if byday_value:
                days_of_week: List[str] = []
                for token in byday_value.split(','):
                    cleaned = token.strip().upper()
                    if not cleaned:
                        continue
                    match = self._RRULE_DAY_PATTERN.match(cleaned)
                    if match:
                        day_code = match.group('day')
                    else:
                        day_code = cleaned[-2:]
                    day_name = self._RRULE_WEEKDAY_MAP.get(day_code)
                    if day_name and day_name not in days_of_week:
                        days_of_week.append(day_name)
                if days_of_week:
                    pattern['daysOfWeek'] = days_of_week

        start_local = start_dt
        if local_tz and start_dt.tzinfo:
            start_local = start_dt.astimezone(local_tz)
        elif local_tz and start_dt.tzinfo is None:
            start_local = start_dt.replace(tzinfo=local_tz)

        recurrence_range: Dict[str, Any] = {
            'type': 'noEnd',
            'startDate': start_local.date().isoformat(),
        }

        return {'pattern': pattern, 'range': recurrence_range}
