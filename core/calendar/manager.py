"""
Calendar Manager for EchoNote.

Manages local calendar events and coordinates external calendar
synchronization.
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime

from data.database.models import CalendarEvent, CalendarSyncStatus


logger = logging.getLogger('echonote.calendar.manager')


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
        sync_adapters: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize the calendar manager.

        Args:
            db_connection: Database connection instance
            sync_adapters: Dictionary of sync adapters
                          {provider: adapter_instance}
        """
        self.db = db_connection
        self.sync_adapters = sync_adapters or {}
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
            # Create local event
            event = CalendarEvent(
                title=event_data.get('title', ''),
                event_type=event_data.get('event_type', 'Event'),
                start_time=event_data.get('start_time', ''),
                end_time=event_data.get('end_time', ''),
                location=event_data.get('location'),
                attendees=event_data.get('attendees', []),
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
                event.attendees = event_data['attendees']
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
