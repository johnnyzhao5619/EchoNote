# SPDX-License-Identifier: Apache-2.0
#
# Copyright (c) 2024-2025 EchoNote Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
Calendar Manager for EchoNote.

Manages local calendar events and coordinates external calendar
synchronization.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, Union

from core.calendar.constants import CalendarSource, EventType
from core.calendar.exceptions import EventNotFoundError, SyncError
from data.database.models import (
    AutoTaskConfig,
    CalendarEvent,
    CalendarEventLink,
    CalendarSyncStatus,
    EventAttachment,
)
from data.storage.file_manager import FileManager
from utils.time_utils import now_utc

logger = logging.getLogger("echonote.calendar.manager")

if TYPE_CHECKING:
    from data.security.oauth_manager import OAuthManager

_MIN_EXTERNAL_EVENT_DURATION = timedelta(minutes=1)


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
        oauth_manager: Optional["OAuthManager"] = None,
        file_manager: Optional[FileManager] = None,
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
        self.file_manager = file_manager
        self.calendar_auto_task_scheduler = None
        logger.info("CalendarManager initialized")

    def set_calendar_auto_task_scheduler(self, scheduler):
        """Set the auto task scheduler for post-event processing."""
        self.calendar_auto_task_scheduler = scheduler

    def create_event(self, event_data: dict, sync_to: Optional[List[str]] = None) -> str:
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
            required_fields = ["title", "start_time", "end_time"]
            missing_fields = [field for field in required_fields if not event_data.get(field)]
            if missing_fields:
                raise ValueError(f"Missing required event fields: {', '.join(missing_fields)}")

            start_dt, end_dt = self._normalize_event_window(
                event_data["start_time"], event_data["end_time"]
            )
            if start_dt >= end_dt:
                raise ValueError("Event end_time must be later than start_time")
            event_data["start_time"] = start_dt.isoformat()
            event_data["end_time"] = end_dt.isoformat()

            attendees = event_data.get("attendees") or []
            if not isinstance(attendees, list):
                if isinstance(attendees, (set, tuple)):
                    attendees = list(attendees)
                else:
                    attendees = [attendees]

            # Create local event
            event = CalendarEvent(
                title=event_data.get("title", ""),
                event_type=event_data.get("event_type", EventType.EVENT),
                start_time=event_data.get("start_time", ""),
                end_time=event_data.get("end_time", ""),
                location=event_data.get("location"),
                attendees=attendees,
                description=event_data.get("description"),
                reminder_minutes=event_data.get("reminder_minutes"),
                recurrence_rule=event_data.get("recurrence_rule"),
                source=CalendarSource.LOCAL,
                is_readonly=False,
            )

            event.save(self.db)
            logger.info(f"Created local event: {event.id} - {event.title}")

            # Sync to external calendars if requested
            if sync_to:
                for provider in sync_to:
                    if provider in self.sync_adapters:
                        try:
                            external_id = self._push_to_external(event, provider)
                            if external_id:
                                self._upsert_event_link(
                                    event.id,
                                    provider,
                                    external_id,
                                )
                                logger.info(
                                    f"Synced event {event.id} to " f"{provider}: {external_id}"
                                )
                        except Exception as e:
                            logger.error(f"Failed to sync event to " f"{provider}: {e}")
                            # Continue with other providers
                    else:
                        logger.warning(f"Sync adapter for {provider} not found")

            # Save auto task config if provided
            if "auto_transcribe" in event_data or "enable_translation" in event_data:
                config = AutoTaskConfig(
                    event_id=event.id,
                    enable_transcription=bool(event_data.get("auto_transcribe", False)),
                    enable_translation=bool(event_data.get("enable_translation", False)),
                    translation_target_language=event_data.get("translation_target_lang"),
                )
                config.save(self.db)
                if self.calendar_auto_task_scheduler:
                    self.calendar_auto_task_scheduler.schedule_event_task(event, config)

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
                raise EventNotFoundError(event_id)

            if event.is_readonly:
                raise ValueError(f"Cannot update readonly event from {event.source}")

            if "start_time" in event_data or "end_time" in event_data:
                start_dt, end_dt = self._normalize_event_window(
                    event_data.get("start_time", event.start_time),
                    event_data.get("end_time", event.end_time),
                )
                if start_dt >= end_dt:
                    raise ValueError("Event end_time must be later than start_time")
                if "start_time" in event_data:
                    event_data["start_time"] = start_dt.isoformat()
                if "end_time" in event_data:
                    event_data["end_time"] = end_dt.isoformat()

            # Update fields
            if "title" in event_data:
                event.title = event_data["title"]
            if "event_type" in event_data:
                event.event_type = event_data["event_type"]
            if "start_time" in event_data:
                event.start_time = event_data["start_time"]
            if "end_time" in event_data:
                event.end_time = event_data["end_time"]
            if "location" in event_data:
                event.location = event_data["location"]
            if "attendees" in event_data:
                attendees = event_data.get("attendees") or []
                if not isinstance(attendees, list):
                    if isinstance(attendees, (set, tuple)):
                        attendees = list(attendees)
                    else:
                        attendees = [attendees]
                event.attendees = attendees
            if "description" in event_data:
                event.description = event_data["description"]
            if "reminder_minutes" in event_data:
                event.reminder_minutes = event_data["reminder_minutes"]
            if "recurrence_rule" in event_data:
                event.recurrence_rule = event_data["recurrence_rule"]

            event.save(self.db)
            logger.info(f"Updated event: {event_id}")

            # Update auto task config if provided
            if "auto_transcribe" in event_data or "enable_translation" in event_data:
                config = AutoTaskConfig.get_by_event_id(self.db, event_id)
                if not config:
                    config = AutoTaskConfig(event_id=event.id)

                if "auto_transcribe" in event_data:
                    config.enable_transcription = bool(event_data["auto_transcribe"])
                if "enable_translation" in event_data:
                    config.enable_translation = bool(event_data["enable_translation"])
                if "translation_target_lang" in event_data:
                    config.translation_target_language = event_data["translation_target_lang"]

                config.save(self.db)
                if self.calendar_auto_task_scheduler:
                    self.calendar_auto_task_scheduler.schedule_event_task(event, config)

            links = CalendarEventLink.list_for_event(self.db, event_id)
            sync_failures = []

            for link in links:
                adapter = self.sync_adapters.get(link.provider)
                if not adapter:
                    logger.warning(
                        "Sync adapter for %s not found; skipping update for event %s",
                        link.provider,
                        event_id,
                    )
                    sync_failures.append(link.provider)
                    continue

                if not link.external_id:
                    logger.warning(
                        "Missing external_id for provider %s on event %s",
                        link.provider,
                        event_id,
                    )
                    sync_failures.append(link.provider)
                    continue

                try:
                    adapter.update_event(event, link.external_id)
                    self._upsert_event_link(
                        event.id,
                        link.provider,
                        link.external_id,
                        last_synced_at=event.updated_at,
                    )
                except Exception as exc:  # pragma: no cover - defensive
                    logger.error(
                        "Failed to update external event %s (%s): %s",
                        event_id,
                        link.provider,
                        exc,
                    )
                    sync_failures.append(link.provider)

            if sync_failures:
                failed_msg = ", ".join(sorted(set(sync_failures)))
                raise SyncError(
                    f"Local event updated, but sync failed for: {failed_msg}",
                    failed_providers=sync_failures,
                )

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
                raise EventNotFoundError(event_id)

            if event.is_readonly:
                raise ValueError(f"Cannot delete readonly event from {event.source}")

            links = CalendarEventLink.list_for_event(self.db, event_id)
            sync_failures = []

            for link in links:
                adapter = self.sync_adapters.get(link.provider)
                if not adapter:
                    logger.warning(
                        "Sync adapter for %s not found; aborting deletion for event %s",
                        link.provider,
                        event_id,
                    )
                    sync_failures.append(link.provider)
                    continue

                if not link.external_id:
                    logger.warning(
                        "Missing external_id for provider %s on event %s",
                        link.provider,
                        event_id,
                    )
                    sync_failures.append(link.provider)
                    continue

                try:
                    adapter.delete_event(event, link.external_id)
                except Exception as exc:
                    logger.error(
                        "Failed to delete external event %s (%s): %s",
                        event_id,
                        link.provider,
                        exc,
                    )
                    sync_failures.append(link.provider)

            if sync_failures:
                failed_msg = ", ".join(sorted(set(sync_failures)))
                raise SyncError(
                    f"Local deletion blocked. Sync failed for: {failed_msg}",
                    failed_providers=sync_failures,
                )

            if links:
                self.db.execute(
                    "DELETE FROM calendar_event_links WHERE event_id = ?",
                    (event_id,),
                    commit=True,
                )

            attachments = EventAttachment.get_by_event_id(self.db, event_id)
            for attachment in attachments:
                if self.file_manager and attachment.file_path:
                    try:
                        self.file_manager.delete_file(attachment.file_path)
                    except FileNotFoundError:
                        logger.warning(
                            "Attachment file already missing: %s",
                            attachment.file_path,
                        )
                    except Exception as exc:  # pragma: no cover - defensive
                        logger.error(
                            "Failed to delete attachment file %s: %s",
                            attachment.file_path,
                            exc,
                        )
                attachment.delete(self.db)

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
        self, start_date, end_date, filters: Optional[Dict[str, Any]] = None
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

            # Normalize query bounds to UTC-aware ISO strings so comparisons
            # remain stable regardless of caller timezone representation.
            start_dt, end_dt = self._normalize_event_window(start_date, end_date)
            start_date = start_dt.isoformat()
            end_date = end_dt.isoformat()

            # Get events by time range
            events = CalendarEvent.get_by_time_range(
                self.db, start_date, end_date, source=filters.get("source")
            )

            # Apply additional filters
            if filters.get("event_type"):
                events = [e for e in events if e.event_type == filters["event_type"]]

            if filters.get("keyword"):
                keyword = filters["keyword"].lower()
                events = [
                    e
                    for e in events
                    if keyword in e.title.lower()
                    or (e.description and keyword in e.description.lower())
                ]

            logger.debug(f"Retrieved {len(events)} events from " f"{start_date} to {end_date}")
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
                raise ValueError(f"Sync adapter for {provider} not found")

            adapter = self.sync_adapters[provider]

            existing_links = self.db.execute(
                ("SELECT event_id, external_id FROM calendar_event_links " "WHERE provider = ?"),
                (provider,),
            )

            existing_map: Dict[str, Optional[str]] = {}
            for row in existing_links or []:
                external_id = row["external_id"]
                if external_id:
                    existing_map[external_id] = row["event_id"]

            legacy_rows = self.db.execute(
                (
                    "SELECT id, external_id FROM calendar_events "
                    "WHERE source = ? AND external_id IS NOT NULL"
                ),
                (provider,),
            )

            for row in legacy_rows or []:
                external_id = row["external_id"]
                if external_id and external_id not in existing_map:
                    existing_map[external_id] = row["id"]

            if self.oauth_manager:
                self._refresh_provider_token(provider, adapter)

            # Get sync status
            sync_status = CalendarSyncStatus.get_by_provider(self.db, provider)

            if not sync_status:
                logger.warning(f"No active sync status for {provider}")
                return

            # Fetch events from external calendar
            # Use last sync token for incremental sync
            result = adapter.fetch_events(
                start_date=None,  # Fetch all future events
                end_date=None,
                last_sync_token=sync_status.sync_token,
            )

            external_events = result.get("events", [])
            new_sync_token = result.get("sync_token")
            is_incremental = bool(result.get("is_incremental", bool(sync_status.sync_token)))

            deleted_external_ids = set(result.get("deleted", []) or [])
            remote_external_ids: set = set()

            # Save external events to local database
            for ext_event in external_events:
                if not isinstance(ext_event, dict):
                    continue

                if ext_event.get("deleted"):
                    if ext_event.get("id"):
                        deleted_external_ids.add(ext_event["id"])
                    continue

                ext_identifier = ext_event.get("id")
                if ext_identifier:
                    remote_external_ids.add(ext_identifier)

                self._save_external_event(ext_event, provider)

            existing_external_ids = set(existing_map.keys())
            if is_incremental:
                # Incremental APIs only return changed records. Never infer deletion
                # from absence in this response.
                removable_ids = deleted_external_ids & existing_external_ids
            else:
                removable_ids = (existing_external_ids - remote_external_ids) | (
                    deleted_external_ids & existing_external_ids
                )

            for external_id in removable_ids:
                event_id = existing_map.get(external_id)
                self._remove_external_event(event_id, provider, external_id)

            # Update sync status
            sync_status.last_sync_time = current_iso_timestamp()
            if new_sync_token:
                sync_status.sync_token = new_sync_token
            sync_status.save(self.db)

            logger.info(f"Synced {len(external_events)} events from {provider}")

        except Exception as e:
            logger.error(f"Failed to sync external calendar {provider}: {e}")
            raise

    def disconnect_provider(self, provider: str) -> None:
        """Detach all local data linked to an external provider.

        This operation removes provider links from local events and deletes
        provider-owned mirrored events plus their attachments.
        """
        try:
            link_rows = self.db.execute(
                "SELECT event_id, external_id FROM calendar_event_links WHERE provider = ?",
                (provider,),
            )
            for row in link_rows or []:
                self._remove_external_event(
                    row.get("event_id"),
                    provider,
                    row.get("external_id"),
                )

            # Also clean up provider-owned legacy rows that may not have links.
            provider_events = self.db.execute(
                "SELECT id FROM calendar_events WHERE source = ?",
                (provider,),
            )
            for row in provider_events or []:
                event_id = row.get("id")
                if event_id:
                    self._remove_external_event(event_id, provider)

        except Exception as exc:
            logger.error("Failed to disconnect provider %s: %s", provider, exc)
            raise

    def disconnect_provider_account(self, provider: str) -> None:
        """Disconnect an external provider account and clean related state.

        This operation revokes provider access when supported, deletes any
        stored OAuth token and sync status row, then removes provider-linked
        local events and attachments.
        """
        try:
            adapter = self.sync_adapters.get(provider)
            if adapter and hasattr(adapter, "revoke_access"):
                try:
                    adapter.revoke_access()
                except Exception as exc:  # noqa: BLE001 - continue cleanup
                    logger.warning("Could not revoke access for provider %s: %s", provider, exc)
            if adapter:
                # Clear in-memory credentials so disconnected accounts do not
                # retain stale tokens for the current process lifetime.
                for token_attr in ("access_token", "refresh_token", "expires_at"):
                    if hasattr(adapter, token_attr):
                        setattr(adapter, token_attr, None)

            if self.oauth_manager:
                try:
                    self.oauth_manager.delete_token(provider)
                except Exception as exc:  # noqa: BLE001 - continue cleanup
                    logger.warning("Could not delete OAuth token for %s: %s", provider, exc)

            sync_status = CalendarSyncStatus.get_by_provider(self.db, provider)
            if sync_status:
                sync_status.delete(self.db)

            self.disconnect_provider(provider)

        except Exception as exc:
            logger.error("Failed to disconnect provider account %s: %s", provider, exc)
            raise

    def _push_to_external(self, event: CalendarEvent, provider: str) -> Optional[str]:
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
            event: Optional[CalendarEvent] = None
            ext_identifier = ext_event.get("id")

            if ext_identifier:
                link = CalendarEventLink.get_by_provider_and_external_id(
                    self.db, provider, ext_identifier
                )
                if link:
                    event = CalendarEvent.get_by_id(self.db, link.event_id)

                if not event:
                    # Fallback for legacy records relying on calendar_events.external_id
                    query = "SELECT * FROM calendar_events " "WHERE external_id = ? AND source = ?"
                    result = self.db.execute(query, (ext_identifier, provider))
                    if result:
                        event = CalendarEvent.from_db_row(result[0])

            start_value = ext_event.get("start_time")
            end_value = ext_event.get("end_time")

            def _clean_time_value(value: Optional[Any]) -> Optional[Union[str, datetime]]:
                if isinstance(value, datetime):
                    return value
                if isinstance(value, str):
                    text = value.strip()
                    if text:
                        return text
                    return None
                return value

            start_value = _clean_time_value(start_value)
            end_value = _clean_time_value(end_value)

            base_start: Optional[Union[str, datetime]]
            if start_value is not None:
                base_start = start_value
            elif event and event.start_time:
                base_start = event.start_time
            else:
                base_start = None

            if end_value is not None:
                base_end: Optional[Union[str, datetime]] = end_value
            elif event and event.end_time:
                base_end = event.end_time
            else:
                base_end = None

            normalized_start: Optional[str] = None
            normalized_end: Optional[str] = None

            if base_start is not None:
                comparison_end = base_end if base_end is not None else base_start
                try:
                    start_dt, end_dt = self._normalize_event_window(
                        base_start,
                        comparison_end,
                    )
                except ValueError as exc:
                    logger.warning(
                        "Skipping external event %s due to invalid time window: %s",
                        ext_identifier or ext_event.get("title"),
                        exc,
                    )
                    if not event:
                        return
                else:
                    if end_dt <= start_dt:
                        end_dt = start_dt + _MIN_EXTERNAL_EVENT_DURATION
                    normalized_start = start_dt.isoformat()
                    normalized_end = end_dt.isoformat()
            else:
                logger.warning(
                    "Skipping external event %s without a valid start_time",
                    ext_identifier or ext_event.get("title"),
                )
                if not event:
                    return

            def _normalize_attendees(value: Any) -> List[str]:
                if value is None:
                    return []
                if isinstance(value, list):
                    return value
                if isinstance(value, (set, tuple)):
                    return list(value)
                return [value]

            if event:
                if "title" in ext_event:
                    event.title = ext_event.get("title", event.title)

                if normalized_start and (start_value is not None or not event.start_time):
                    event.start_time = normalized_start

                update_end = False
                if normalized_end:
                    if end_value is not None or not event.end_time:
                        update_end = True
                    elif start_value is not None and normalized_start:
                        try:
                            new_start_dt = datetime.fromisoformat(normalized_start)
                            existing_end_dt = datetime.fromisoformat(event.end_time)
                        except ValueError:
                            update_end = True
                        else:
                            if existing_end_dt <= new_start_dt:
                                update_end = True
                    if update_end:
                        event.end_time = normalized_end

                if "location" in ext_event:
                    event.location = ext_event.get("location", event.location)

                if "attendees" in ext_event:
                    event.attendees = _normalize_attendees(ext_event.get("attendees"))

                if "description" in ext_event:
                    event.description = ext_event.get("description", event.description)

                if "reminder_use_default" in ext_event:
                    event.reminder_use_default = ext_event.get("reminder_use_default")

                event.save(self.db)
                logger.debug(f"Updated external event: {event.id}")
            else:
                if not (normalized_start and normalized_end):
                    logger.warning(
                        "Skipping external event %s due to missing normalized times",
                        ext_identifier or ext_event.get("title"),
                    )
                    return

                event = CalendarEvent(
                    title=ext_event.get("title", ""),
                    event_type=ext_event.get("event_type", EventType.EVENT),
                    start_time=normalized_start,
                    end_time=normalized_end,
                    location=ext_event.get("location"),
                    attendees=_normalize_attendees(ext_event.get("attendees")),
                    description=ext_event.get("description"),
                    reminder_minutes=ext_event.get("reminder_minutes"),
                    reminder_use_default=ext_event.get("reminder_use_default"),
                    recurrence_rule=ext_event.get("recurrence_rule"),
                    source=provider,
                    is_readonly=True,  # External events are readonly
                )
                event.save(self.db)
                logger.debug(f"Created external event: {event.id}")

            if ext_identifier:
                last_synced = (
                    ext_event.get("last_synced_at")
                    or ext_event.get("updated_at")
                    or ext_event.get("last_modified")
                )
                self._upsert_event_link(
                    event.id, provider, ext_identifier, last_synced_at=last_synced
                )

        except Exception as e:
            logger.error(f"Failed to save external event: {e}")

    def _remove_external_event(
        self,
        event_id: Optional[str],
        provider: str,
        external_id: Optional[str] = None,
    ) -> None:
        """Remove a local event and associated metadata for a provider."""

        if not event_id and not external_id:
            return

        try:
            link: Optional[CalendarEventLink] = None

            if external_id:
                link = CalendarEventLink.get_by_provider_and_external_id(
                    self.db,
                    provider,
                    external_id,
                )

            if not link and event_id:
                link = CalendarEventLink.get_by_event_and_provider(
                    self.db,
                    event_id,
                    provider,
                )
                if link and not external_id:
                    external_id = link.external_id

            if link and not event_id:
                event_id = link.event_id

            if external_id:
                delete_link_query = (
                    "DELETE FROM calendar_event_links " "WHERE provider = ? AND external_id = ?"
                )
                self.db.execute(
                    delete_link_query,
                    (provider, external_id),
                    commit=True,
                )
            elif event_id:
                delete_link_query = (
                    "DELETE FROM calendar_event_links " "WHERE provider = ? AND event_id = ?"
                )
                self.db.execute(
                    delete_link_query,
                    (provider, event_id),
                    commit=True,
                )

            if not event_id:
                return

            event = CalendarEvent.get_by_id(self.db, event_id)
            if not event:
                return

            remaining_links = CalendarEventLink.list_for_event(self.db, event_id)
            remaining_link_count = len(remaining_links)
            should_delete_event = event.source == provider and remaining_link_count == 0

            if should_delete_event:
                attachments = EventAttachment.get_by_event_id(self.db, event_id)
                for attachment in attachments:
                    if self.file_manager and attachment.file_path:
                        try:
                            self.file_manager.delete_file(attachment.file_path)
                        except FileNotFoundError:
                            logger.warning(
                                "Attachment file already missing: %s",
                                attachment.file_path,
                            )
                        except Exception as exc:  # pragma: no cover - defensive
                            logger.error(
                                "Failed to delete attachment file %s: %s",
                                attachment.file_path,
                                exc,
                            )
                    attachment.delete(self.db)

                event.delete(self.db)
                logger.info("Removed local event %s for provider %s", event_id, provider)
            else:
                logger.info(
                    "Detached provider %s from event %s; %d other link(s) remain",
                    provider,
                    event_id,
                    remaining_link_count,
                )

        except Exception as exc:
            logger.error(
                "Failed to remove external event %s/%s: %s",
                provider,
                external_id or event_id,
                exc,
            )

    def _upsert_event_link(
        self, event_id: str, provider: str, external_id: str, last_synced_at: Optional[Any] = None
    ) -> None:
        """Persist or refresh the provider mapping for an event."""

        if not external_id:
            return

        timestamp: Optional[str]
        if isinstance(last_synced_at, datetime):
            timestamp = last_synced_at.isoformat()
        elif isinstance(last_synced_at, str) and last_synced_at.strip():
            timestamp = last_synced_at
        else:
            timestamp = current_iso_timestamp()

        existing_link = CalendarEventLink.get_by_event_and_provider(
            self.db,
            event_id,
            provider,
        )

        if existing_link and existing_link.external_id != external_id:
            delete_query = "DELETE FROM calendar_event_links " "WHERE event_id = ? AND provider = ?"
            self.db.execute(delete_query, (event_id, provider), commit=True)

        link = CalendarEventLink(
            event_id=event_id,
            provider=provider,
            external_id=external_id,
            last_synced_at=timestamp,
        )
        link.save(self.db)

    @staticmethod
    def _normalize_event_window(
        start_time: Union[str, datetime], end_time: Union[str, datetime]
    ) -> Tuple[datetime, datetime]:
        """Normalize event window datetimes for comparison.

        Args:
            start_time: Event start time as ISO string or ``datetime``
            end_time: Event end time as ISO string or ``datetime``

        Returns:
            Tuple containing normalized start and end datetimes in UTC with
            timezone information. Naive values inherit the timezone from the
            opposite endpoint when available; otherwise the system local
            timezone is assumed before converting to UTC.

        Raises:
            ValueError: If either value cannot be converted to ``datetime``.
        """

        def _coerce(value: Union[str, datetime], label: str) -> datetime:
            if isinstance(value, datetime):
                return value
            if isinstance(value, str):
                try:
                    text = value.strip()
                    if text.endswith("Z"):
                        text = f"{text[:-1]}+00:00"
                    return datetime.fromisoformat(text)
                except ValueError as exc:  # pragma: no cover - defensive branch
                    raise ValueError(
                        f"Event {label} must be a datetime instance or ISO 8601 string"
                    ) from exc
            raise ValueError(f"Event {label} must be a datetime instance or ISO 8601 string")

        start_dt = _coerce(start_time, "start_time")
        end_dt = _coerce(end_time, "end_time")

        local_tz = now_local().tzinfo

        def _ensure_aware(value: datetime, reference: Optional[datetime], fallback_tz) -> datetime:
            if value.tzinfo:
                return value
            if reference and reference.tzinfo:
                return value.replace(tzinfo=reference.tzinfo)
            return value.replace(tzinfo=fallback_tz)

        if local_tz is None:  # pragma: no cover - defensive fallback
            local_tz = timezone.utc

        start_dt = _ensure_aware(start_dt, end_dt, local_tz)
        end_dt = _ensure_aware(end_dt, start_dt, local_tz)

        return (
            start_dt.astimezone(timezone.utc),
            end_dt.astimezone(timezone.utc),
        )

    def _refresh_provider_token(self, provider: str, adapter: Any) -> None:
        """
        Refresh OAuth token for provider if needed.

        Args:
            provider: Provider name
            adapter: Sync adapter instance
        """
        if not self.oauth_manager or not hasattr(adapter, "refresh_access_token"):
            return

        if not getattr(adapter, "refresh_token", None):
            logger.warning("Adapter %s has no refresh_token; skipping token refresh", provider)
            return

        try:
            token_before_refresh = self.oauth_manager.get_token(provider)
            refresh_result: Dict[str, Any] = {}

            def _resolve_expires_in(data: Dict[str, Any], context: str) -> Optional[int]:
                expires_in_value = data.get("expires_in")
                if expires_in_value is not None:
                    return expires_in_value

                expires_at_value = data.get("expires_at")
                if not expires_at_value:
                    return None

                try:
                    expires_at_dt = datetime.fromisoformat(expires_at_value)
                    current_time = (
                        now_utc().astimezone(expires_at_dt.tzinfo)
                        if expires_at_dt.tzinfo
                        else now_local()
                    )
                    resolved = max(int((expires_at_dt - current_time).total_seconds()), 0)
                    logger.debug(
                        "Derived expires_in=%s from expires_at during %s for %s",
                        resolved,
                        context,
                        provider,
                    )
                    return resolved
                except ValueError:
                    logger.warning(
                        "Unable to parse expires_at during %s for %s: %s",
                        context,
                        provider,
                        expires_at_value,
                    )
                    return None

            def refresh_callback(refresh_token: str):
                adapter.refresh_token = refresh_token
                refreshed = adapter.refresh_access_token()

                new_refresh_token = refreshed.get("refresh_token")
                if new_refresh_token:
                    adapter.refresh_token = new_refresh_token

                adapter.access_token = refreshed.get("access_token")
                adapter.expires_at = refreshed.get("expires_at")
                if refreshed.get("token_type"):
                    setattr(adapter, "token_type", refreshed.get("token_type"))

                resolved_expires_in = _resolve_expires_in(refreshed, "refresh callback")

                refresh_result.clear()
                refresh_result.update(refreshed)
                if resolved_expires_in is not None:
                    refresh_result["expires_in"] = resolved_expires_in

                return {
                    "access_token": refreshed.get("access_token"),
                    "expires_in": resolved_expires_in,
                    "token_type": refreshed.get("token_type"),
                    "refresh_token": refreshed.get("refresh_token"),
                    "expires_at": refreshed.get("expires_at"),
                }

            token_data = self.oauth_manager.refresh_token_if_needed(provider, refresh_callback)

            if refresh_result and refresh_result.get("access_token"):
                expires_in_for_update = _resolve_expires_in(refresh_result, "post-refresh update")
                self.oauth_manager.update_access_token(
                    provider,
                    refresh_result.get("access_token"),
                    expires_in_for_update,
                    token_type=refresh_result.get("token_type"),
                    refresh_token=refresh_result.get("refresh_token"),
                    expires_at=refresh_result.get("expires_at"),
                )

            if token_data:
                adapter.access_token = token_data.get("access_token")
                adapter.expires_at = token_data.get("expires_at")

                refreshed_token = token_data.get("refresh_token")
                if refreshed_token:
                    adapter.refresh_token = refreshed_token

            if (
                token_before_refresh
                and token_data
                and token_data.get("access_token") != token_before_refresh.get("access_token")
            ):
                logger.info("Access token for %s refreshed successfully", provider)

        except ValueError as token_error:
            logger.warning("Skipping token refresh for %s: %s", provider, token_error)
        except Exception as token_error:
            logger.error("Token refresh failed for %s: %s", provider, token_error)
