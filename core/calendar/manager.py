"""
Calendar Manager for EchoNote.

Manages local calendar events and coordinates external calendar
synchronization.
"""

import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, TYPE_CHECKING, Tuple, Union

from data.database.models import CalendarEvent, CalendarSyncStatus


logger = logging.getLogger('echonote.calendar.manager')


if TYPE_CHECKING:
    from data.security.oauth_manager import OAuthManager


class CalendarManager:
    """
    Manages calendar events and external calendar synchronization.

    Responsibilities:
    - CRUD operations for local calendar events
    - Coordination with external calendar sync adapters
    - Event querying and filtering
    """

    def __init__(
        self,
        db_connection,
        sync_adapters: Optional[Dict[str, Any]] = None,
        oauth_manager: Optional['OAuthManager'] = None
    ):
        """
        Initialize the calendar manager.

        Args:
            db_connection: Database connection instance
            sync_adapters: Dictionary of sync adapters
                          {provider: adapter_instance}
            oauth_manager: OAuth token manager for external providers
        """
        self.db = db_connection
        self.sync_adapters = sync_adapters or {}
        self.oauth_manager = oauth_manager
        logger.info("CalendarManager initialized")

    def create_event(
        self,
        event_data: dict,
        sync_to: Optional[List[str]] = None
    ) -> str:
        """
        Create a new calendar event.

        Args:
            event_data: Dictionary containing event information
            sync_to: Optional list of providers to sync to
                    (e.g., ['google', 'outlook'])

        Returns:
            Event ID
        """
        try:
            # Basic validation for required fields
            required_fields = ['title', 'start_time', 'end_time']
            missing_fields = [
                field for field in required_fields
                if not event_data.get(field)
            ]
            if missing_fields:
                raise ValueError(
                    f"Missing required event fields: {', '.join(missing_fields)}"
                )

            start_dt, end_dt = self._normalize_event_window(
                event_data['start_time'],
                event_data['end_time']
            )
            if start_dt >= end_dt:
                raise ValueError(
                    "Event end_time must be later than start_time"
                )
            event_data['start_time'] = start_dt.isoformat()
            event_data['end_time'] = end_dt.isoformat()

            attendees = event_data.get('attendees') or []
            if not isinstance(attendees, list):
                if isinstance(attendees, (set, tuple)):
                    attendees = list(attendees)
                else:
                    attendees = [attendees]

            # Create local event
            event = CalendarEvent(
                title=event_data.get('title', ''),
                event_type=event_data.get('event_type', 'Event'),
                start_time=event_data.get('start_time', ''),
                end_time=event_data.get('end_time', ''),
                location=event_data.get('location'),
                attendees=attendees,
                description=event_data.get('description'),
                reminder_minutes=event_data.get('reminder_minutes'),
                recurrence_rule=event_data.get('recurrence_rule'),
                source='local',
                is_readonly=False
            )

            event.save(self.db)
            logger.info(
                f"Created local event: {event.id} - {event.title}"
            )

            # Sync to external calendars if requested
            if sync_to:
                for provider in sync_to:
                    if provider in self.sync_adapters:
                        try:
                            external_id = self._push_to_external(
                                event, provider
                            )
                            if external_id:
                                # Update event with external ID
                                event.external_id = external_id
                                event.save(self.db)
                                logger.info(
                                    f"Synced event {event.id} to "
                                    f"{provider}: {external_id}"
                                )
                        except Exception as e:
                            logger.error(
                                f"Failed to sync event to "
                                f"{provider}: {e}"
                            )
                            # Continue with other providers
                    else:
                        logger.warning(
                            f"Sync adapter for {provider} not found"
                        )

            return event.id

        except Exception as e:
            logger.error(f"Failed to create event: {e}")
            raise

    def update_event(self, event_id: str, event_data: dict):
        """
        Update an existing calendar event.

        Args:
            event_id: Event ID to update
            event_data: Dictionary containing updated event information
        """
        try:
            event = CalendarEvent.get_by_id(self.db, event_id)

            if not event:
                raise ValueError(f"Event not found: {event_id}")

            if event.is_readonly:
                raise ValueError(
                    f"Cannot update readonly event from {event.source}"
                )

            if 'start_time' in event_data or 'end_time' in event_data:
                start_dt, end_dt = self._normalize_event_window(
                    event_data.get('start_time', event.start_time),
                    event_data.get('end_time', event.end_time)
                )
                if start_dt >= end_dt:
                    raise ValueError(
                        "Event end_time must be later than start_time"
                    )
                if 'start_time' in event_data:
                    event_data['start_time'] = start_dt.isoformat()
                if 'end_time' in event_data:
                    event_data['end_time'] = end_dt.isoformat()

            # Update fields
            if 'title' in event_data:
                event.title = event_data['title']
            if 'event_type' in event_data:
                event.event_type = event_data['event_type']
            if 'start_time' in event_data:
                event.start_time = event_data['start_time']
            if 'end_time' in event_data:
                event.end_time = event_data['end_time']
            if 'location' in event_data:
                event.location = event_data['location']
            if 'attendees' in event_data:
                attendees = event_data.get('attendees') or []
                if not isinstance(attendees, list):
                    if isinstance(attendees, (set, tuple)):
                        attendees = list(attendees)
                    else:
                        attendees = [attendees]
                event.attendees = attendees
            if 'description' in event_data:
                event.description = event_data['description']
            if 'reminder_minutes' in event_data:
                event.reminder_minutes = event_data['reminder_minutes']
            if 'recurrence_rule' in event_data:
                event.recurrence_rule = event_data['recurrence_rule']

            event.save(self.db)
            logger.info(f"Updated event: {event_id}")

        except Exception as e:
            logger.error(f"Failed to update event {event_id}: {e}")
            raise

    def delete_event(self, event_id: str):
        """
        Delete a calendar event.

        Args:
            event_id: Event ID to delete
        """
        try:
            event = CalendarEvent.get_by_id(self.db, event_id)

            if not event:
                raise ValueError(f"Event not found: {event_id}")

            if event.is_readonly:
                raise ValueError(
                    f"Cannot delete readonly event from {event.source}"
                )

            event.delete(self.db)
            logger.info(f"Deleted event: {event_id}")

        except Exception as e:
            logger.error(f"Failed to delete event {event_id}: {e}")
            raise

    def get_event(self, event_id: str) -> Optional[CalendarEvent]:
        """
        Get a single calendar event by ID.

        Args:
            event_id: Event ID

        Returns:
            CalendarEvent instance or None if not found
        """
        try:
            return CalendarEvent.get_by_id(self.db, event_id)
        except Exception as e:
            logger.error(f"Failed to get event {event_id}: {e}")
            return None

    def get_events(
        self,
        start_date,
        end_date,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[CalendarEvent]:
        """
        Query calendar events within a time range with optional filters.

        Args:
            start_date: Start date/time (datetime object or ISO format string)
            end_date: End date/time (datetime object or ISO format string)
            filters: Optional filters (event_type, source, keyword)

        Returns:
            List of CalendarEvent instances
        """
        try:
            filters = filters or {}
            
            # Convert datetime objects to ISO format strings if needed
            if isinstance(start_date, datetime):
                start_date = start_date.isoformat()
            if isinstance(end_date, datetime):
                end_date = end_date.isoformat()

            # Get events by time range
            events = CalendarEvent.get_by_time_range(
                self.db,
                start_date,
                end_date,
                source=filters.get('source')
            )

            # Apply additional filters
            if filters.get('event_type'):
                events = [
                    e for e in events
                    if e.event_type == filters['event_type']
                ]

            if filters.get('keyword'):
                keyword = filters['keyword'].lower()
                events = [
                    e for e in events
                    if keyword in e.title.lower() or
                    (e.description and keyword in e.description.lower())
                ]

            logger.debug(
                f"Retrieved {len(events)} events from "
                f"{start_date} to {end_date}"
            )
            return events

        except Exception as e:
            logger.error(f"Failed to get events: {e}")
            return []

    def sync_external_calendar(self, provider: str):
        """
        Synchronize events from an external calendar provider.

        Args:
            provider: Provider name (google/outlook)
        """
        try:
            if provider not in self.sync_adapters:
                raise ValueError(
                    f"Sync adapter for {provider} not found"
                )

            adapter = self.sync_adapters[provider]

            token_before_refresh: Optional[Dict[str, Any]] = None
            refresh_result: Dict[str, Any] = {}

            if self.oauth_manager and hasattr(adapter, 'refresh_access_token'):
                if not getattr(adapter, 'refresh_token', None):
                    logger.warning(
                        "Adapter %s has no refresh_token; skipping token refresh",
                        provider
                    )
                else:
                    try:
                        token_before_refresh = self.oauth_manager.get_token(provider)

                        def _resolve_expires_in(data: Dict[str, Any], context: str) -> Optional[int]:
                            expires_in_value = data.get('expires_in')
                            if expires_in_value is not None:
                                return expires_in_value

                            expires_at_value = data.get('expires_at')
                            if not expires_at_value:
                                return None

                            try:
                                expires_at_dt = datetime.fromisoformat(expires_at_value)
                                current_time = datetime.now(
                                    expires_at_dt.tzinfo
                                ) if expires_at_dt.tzinfo else datetime.now()
                                resolved = max(
                                    int((expires_at_dt - current_time).total_seconds()),
                                    0
                                )
                                logger.debug(
                                    "Derived expires_in=%s from expires_at during %s for %s",
                                    resolved,
                                    context,
                                    provider
                                )
                                return resolved
                            except ValueError:
                                logger.warning(
                                    "Unable to parse expires_at during %s for %s: %s",
                                    context,
                                    provider,
                                    expires_at_value
                                )
                                return None

                        def refresh_callback(refresh_token: str):
                            adapter.refresh_token = refresh_token
                            refreshed = adapter.refresh_access_token()

                            new_refresh_token = refreshed.get('refresh_token')
                            if new_refresh_token:
                                adapter.refresh_token = new_refresh_token

                            adapter.access_token = refreshed.get('access_token')
                            adapter.expires_at = refreshed.get('expires_at')
                            if refreshed.get('token_type'):
                                setattr(adapter, 'token_type', refreshed.get('token_type'))

                            resolved_expires_in = _resolve_expires_in(
                                refreshed,
                                'refresh callback'
                            )

                            refresh_result.clear()
                            refresh_result.update(refreshed)
                            if resolved_expires_in is not None:
                                refresh_result['expires_in'] = resolved_expires_in

                            return {
                                'access_token': refreshed.get('access_token'),
                                'expires_in': resolved_expires_in,
                                'token_type': refreshed.get('token_type'),
                                'refresh_token': refreshed.get('refresh_token'),
                                'expires_at': refreshed.get('expires_at')
                            }

                        token_data = self.oauth_manager.refresh_token_if_needed(
                            provider,
                            refresh_callback
                        )

                        if refresh_result and refresh_result.get('access_token'):
                            expires_in_for_update = _resolve_expires_in(
                                refresh_result,
                                'post-refresh update'
                            )
                            self.oauth_manager.update_access_token(
                                provider,
                                refresh_result.get('access_token'),
                                expires_in_for_update,
                                token_type=refresh_result.get('token_type'),
                                refresh_token=refresh_result.get('refresh_token'),
                                expires_at=refresh_result.get('expires_at')
                            )

                        if token_data:
                            adapter.access_token = token_data.get('access_token')
                            adapter.expires_at = token_data.get('expires_at')

                            refreshed_token = token_data.get('refresh_token')
                            if refreshed_token:
                                adapter.refresh_token = refreshed_token

                        if (
                            token_before_refresh
                            and token_data
                            and token_data.get('access_token')
                            != token_before_refresh.get('access_token')
                        ):
                            logger.info(
                                "Access token for %s refreshed successfully", provider
                            )

                    except ValueError as token_error:
                        logger.warning(
                            "Skipping token refresh for %s: %s", provider, token_error
                        )
                    except Exception as token_error:
                        logger.error(
                            "Token refresh failed for %s: %s", provider, token_error
                        )

            # Get sync status
            sync_status = CalendarSyncStatus.get_by_provider(
                self.db, provider
            )

            if not sync_status:
                logger.warning(
                    f"No active sync status for {provider}"
                )
                return

            # Fetch events from external calendar
            # Use last sync token for incremental sync
            result = adapter.fetch_events(
                start_date=None,  # Fetch all future events
                end_date=None,
                last_sync_token=sync_status.sync_token
            )

            external_events = result.get('events', [])
            new_sync_token = result.get('sync_token')

            # Save external events to local database
            for ext_event in external_events:
                self._save_external_event(ext_event, provider)

            # Update sync status
            sync_status.last_sync_time = datetime.now().isoformat()
            if new_sync_token:
                sync_status.sync_token = new_sync_token
            sync_status.save(self.db)

            logger.info(
                f"Synced {len(external_events)} events from {provider}"
            )

        except Exception as e:
            logger.error(
                f"Failed to sync external calendar {provider}: {e}"
            )
            raise

    def _push_to_external(
        self,
        event: CalendarEvent,
        provider: str
    ) -> Optional[str]:
        """
        Push a local event to an external calendar.

        Args:
            event: CalendarEvent instance
            provider: Provider name

        Returns:
            External event ID or None if failed
        """
        try:
            adapter = self.sync_adapters[provider]
            external_id = adapter.push_event(event)
            return external_id
        except Exception as e:
            logger.error(f"Failed to push event to {provider}: {e}")
            return None

    def _save_external_event(self, ext_event: dict, provider: str):
        """
        Save an external event to the local database.

        Args:
            ext_event: External event data
            provider: Provider name
        """
        try:
            # Check if event already exists
            existing = None
            if ext_event.get('id'):
                # Try to find by external_id
                query = (
                    "SELECT * FROM calendar_events "
                    "WHERE external_id = ? AND source = ?"
                )
                result = self.db.execute(
                    query, (ext_event['id'], provider)
                )
                if result:
                    existing = CalendarEvent.from_db_row(result[0])

            if existing:
                # Update existing event
                existing.title = ext_event.get(
                    'title', existing.title
                )
                existing.start_time = ext_event.get(
                    'start_time', existing.start_time
                )
                existing.end_time = ext_event.get(
                    'end_time', existing.end_time
                )
                existing.location = ext_event.get(
                    'location', existing.location
                )
                existing.attendees = ext_event.get(
                    'attendees', existing.attendees
                )
                existing.description = ext_event.get(
                    'description', existing.description
                )
                existing.save(self.db)
                logger.debug(f"Updated external event: {existing.id}")
            else:
                # Create new event
                event = CalendarEvent(
                    title=ext_event.get('title', ''),
                    event_type=ext_event.get('event_type', 'Event'),
                    start_time=ext_event.get('start_time', ''),
                    end_time=ext_event.get('end_time', ''),
                    location=ext_event.get('location'),
                    attendees=ext_event.get('attendees', []),
                    description=ext_event.get('description'),
                    reminder_minutes=ext_event.get('reminder_minutes'),
                    recurrence_rule=ext_event.get('recurrence_rule'),
                    source=provider,
                    external_id=ext_event.get('id'),
                    is_readonly=True  # External events are readonly
                )
                event.save(self.db)
                logger.debug(f"Created external event: {event.id}")

        except Exception as e:
            logger.error(f"Failed to save external event: {e}")

    @staticmethod
    def _normalize_event_window(
        start_time: Union[str, datetime],
        end_time: Union[str, datetime]
    ) -> Tuple[datetime, datetime]:
        """Normalize event window datetimes for comparison.

        Args:
            start_time: Event start time as ISO string or ``datetime``
            end_time: Event end time as ISO string or ``datetime``

        Returns:
            Tuple containing normalized start and end datetimes.

        Raises:
            ValueError: If either value cannot be converted to ``datetime``.
        """

        def _coerce(value: Union[str, datetime], label: str) -> datetime:
            if isinstance(value, datetime):
                return value
            if isinstance(value, str):
                try:
                    return datetime.fromisoformat(value)
                except ValueError as exc:  # pragma: no cover - defensive branch
                    raise ValueError(
                        f"Event {label} must be a datetime instance or ISO 8601 string"
                    ) from exc
            raise ValueError(
                f"Event {label} must be a datetime instance or ISO 8601 string"
            )

        start_dt = _coerce(start_time, 'start_time')
        end_dt = _coerce(end_time, 'end_time')

        if start_dt.tzinfo and end_dt.tzinfo:
            return (
                start_dt.astimezone(timezone.utc),
                end_dt.astimezone(timezone.utc)
            )

        if start_dt.tzinfo and not end_dt.tzinfo:
            return (
                start_dt.astimezone().replace(tzinfo=None),
                end_dt
            )

        if end_dt.tzinfo and not start_dt.tzinfo:
            return (
                start_dt,
                end_dt.astimezone().replace(tzinfo=None)
            )

        return start_dt, end_dt
