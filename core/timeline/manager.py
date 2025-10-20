"""Timeline Manager for EchoNote."""

import logging
from typing import Optional, List, Dict, Any, Union, Callable, TYPE_CHECKING
from datetime import datetime, timedelta

from data.database.models import (
    CalendarEvent,
    EventAttachment,
    AutoTaskConfig
)

if TYPE_CHECKING:  # pragma: no cover - typing only
    from utils.i18n import I18nManager


logger = logging.getLogger('echonote.timeline.manager')


def to_local_naive(value: Union[datetime, str]) -> datetime:
    """Convert datetime/ISO string to local-time naive datetime."""
    if isinstance(value, str):
        text = value.strip()
        if text.endswith('Z'):
            text = text[:-1] + '+00:00'
        dt = datetime.fromisoformat(text)
    elif isinstance(value, datetime):
        dt = value
    else:
        raise TypeError(
            f"Unsupported value type for to_local_naive: {type(value)!r}"
        )

    if dt.tzinfo is not None:
        return dt.astimezone().replace(tzinfo=None)
    return dt


class TimelineManager:
    """
    Manages timeline view data and auto-task configurations.

    Responsibilities:
    - Provide timeline event data with pagination
    - Manage auto-task configurations for events
    - Search events and transcripts
    - Retrieve event artifacts (recordings, transcripts)
    """

    def __init__(
        self,
        calendar_manager,
        db_connection,
        i18n: Optional['I18nManager'] = None,
        translate: Optional[Callable[[str], str]] = None,
    ):
        """
        Initialize the timeline manager.

        Args:
            calendar_manager: CalendarManager instance
            db_connection: Database connection instance
            i18n: Optional translation manager providing ``t`` method
            translate: Optional translation callback taking a translation key
        """
        self.calendar_manager = calendar_manager
        self.db = db_connection
        if i18n is not None and translate is not None:
            raise ValueError(
                "Provide either an i18n manager or a translation callback, not both"
            )
        self._translate_callback = translate or (i18n.t if i18n else None)
        logger.info("TimelineManager initialized")

    def _translate(self, key: str, default: str) -> str:
        """Return translated text for ``key`` with ``default`` fallback."""
        if self._translate_callback is None:
            return default

        try:
            value = self._translate_callback(key)
        except TypeError:
            # Some callbacks might require keyword arguments for clarity.
            try:
                value = self._translate_callback(key=key)  # type: ignore[call-arg]
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.warning(
                    "Translation callback invocation failed for %s: %s",
                    key,
                    exc,
                )
                return default
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.warning(
                "Translation callback invocation failed for %s: %s",
                key,
                exc,
            )
            return default

        if not isinstance(value, str):
            logger.warning(
                "Translation callback returned non-string for %s: %r",
                key,
                value,
            )
            return default

        if not value or value == key:
            return default

        return value

    def get_timeline_events(
        self,
        center_time: datetime,
        past_days: float,
        future_days: float,
        page: int = 0,
        page_size: int = 50
    ) -> Dict[str, Any]:
        """
        Get timeline events around a center time.

        Args:
            center_time: Center time for the timeline
            past_days: Number of days to look back (supports fractional days)
            future_days: Number of days to look forward (supports fractional days)
            page: Page number for pagination (0-indexed)
            page_size: Number of events per page

        Returns:
            Dictionary containing:
            - current_time: ISO format timestamp
            - past_events: List of past events with artifacts
            - future_events: List of future events with auto-task configs.
              Always populated (when events exist) regardless of how many
              historical events fall into the current page window.
        """
        center_time_local = to_local_naive(center_time)

        try:
            # Calculate time range
            start_time = center_time_local - timedelta(days=past_days)
            end_time = center_time_local + timedelta(days=future_days)

            # Get all events in range
            all_events = self.calendar_manager.get_events(
                start_date=start_time.isoformat(),
                end_date=end_time.isoformat()
            )

            # Separate past and future events
            past_events = []
            future_events = []

            for event in all_events:
                event_start = to_local_naive(event.start_time)

                if event_start < center_time_local:
                    # Past event - get artifacts
                    artifacts = self.get_event_artifacts(event.id)
                    past_events.append({
                        'event': event,
                        'artifacts': artifacts
                    })
                else:
                    # Future event - get auto-task config
                    auto_tasks = self.get_auto_task(event.id)
                    future_events.append({
                        'event': event,
                        'auto_tasks': auto_tasks or {
                            'enable_transcription': False,
                            'enable_recording': False,
                            'transcription_language': None,
                            'enable_translation': False,
                            'translation_target_language': None
                        }
                    })

            # Sort events
            past_events.sort(
                key=lambda x: to_local_naive(x['event'].start_time),
                reverse=True  # Most recent first
            )
            future_events.sort(
                key=lambda x: to_local_naive(x['event'].start_time)
            )

            # Apply pagination for past events only
            total_past = len(past_events)
            total_future = len(future_events)

            start_idx = max(page, 0) * page_size
            end_idx = start_idx + page_size

            past_page = past_events[start_idx:end_idx]

            # Future events always returned on the first page to avoid being
            # paged out by the historical window. Subsequent pages omit them.
            if page == 0:
                future_page = future_events
            else:
                future_page = []

            result = {
                'current_time': center_time_local.isoformat(),
                'past_events': past_page,
                'future_events': future_page,
                'total_count': total_past,
                'future_total_count': total_future,
                'page': page,
                'page_size': page_size,
                'has_more': end_idx < total_past
            }

            logger.debug(
                f"Retrieved timeline events: {len(past_events)} past, "
                f"{len(future_events)} future"
            )
            return result

        except Exception as e:
            logger.error(f"Failed to get timeline events: {e}")
            return {
                'current_time': center_time_local.isoformat(),
                'past_events': [],
                'future_events': [],
                'total_count': 0,
                'future_total_count': 0,
                'page': page,
                'page_size': page_size,
                'has_more': False
            }

    def set_auto_task(self, event_id: str, task_config: dict):
        """
        Set auto-task configuration for an event.

        Args:
            event_id: Event ID
            task_config: Dictionary containing:
                - enable_transcription: bool
                - enable_recording: bool
                - transcription_language: str (optional)
                - enable_translation: bool
                - translation_target_language: str (optional)
        """
        try:
            # Check if event exists
            event = self.calendar_manager.get_event(event_id)
            if not event:
                raise ValueError(f"Event not found: {event_id}")

            # Check if config already exists
            existing_config = AutoTaskConfig.get_by_event_id(
                self.db, event_id
            )

            if existing_config:
                # Update existing config
                existing_config.enable_transcription = task_config.get(
                    'enable_transcription', False
                )
                existing_config.enable_recording = task_config.get(
                    'enable_recording', False
                )
                existing_config.transcription_language = task_config.get(
                    'transcription_language'
                )
                existing_config.enable_translation = task_config.get(
                    'enable_translation', False
                )
                existing_config.translation_target_language = (
                    task_config.get('translation_target_language')
                )
                existing_config.save(self.db)
                logger.info(
                    f"Updated auto-task config for event: {event_id}"
                )
            else:
                # Create new config
                config = AutoTaskConfig(
                    event_id=event_id,
                    enable_transcription=task_config.get(
                        'enable_transcription', False
                    ),
                    enable_recording=task_config.get(
                        'enable_recording', False
                    ),
                    transcription_language=task_config.get(
                        'transcription_language'
                    ),
                    enable_translation=task_config.get(
                        'enable_translation', False
                    ),
                    translation_target_language=task_config.get(
                        'translation_target_language'
                    )
                )
                config.save(self.db)
                logger.info(f"Created auto-task config for event: {event_id}")

        except Exception as e:
            logger.error(
                f"Failed to set auto-task config for event {event_id}: {e}"
            )
            raise

    def _serialize_auto_task_config(
        self,
        config: AutoTaskConfig
    ) -> Dict[str, Any]:
        """Convert an ``AutoTaskConfig`` instance to a serializable dict."""
        return {
            'enable_transcription': config.enable_transcription,
            'enable_recording': config.enable_recording,
            'transcription_language': config.transcription_language,
            'enable_translation': config.enable_translation,
            'translation_target_language': config.translation_target_language,
        }

    def _get_auto_task_map(
        self,
        event_ids: List[str]
    ) -> Dict[str, Dict[str, Any]]:
        """Fetch auto-task configurations for multiple events at once."""
        try:
            if not event_ids:
                return {}

            configs = AutoTaskConfig.get_by_event_ids(self.db, event_ids)
            return {
                config.event_id: self._serialize_auto_task_config(config)
                for config in configs
            }
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error(
                "Failed to get auto-task configs for events %s: %s",
                event_ids,
                exc,
            )
            return {}

    def get_auto_task(self, event_id: str) -> Optional[Dict[str, Any]]:
        """
        Get auto-task configuration for an event.

        Args:
            event_id: Event ID

        Returns:
            Dictionary containing auto-task configuration or None
        """
        try:
            config = AutoTaskConfig.get_by_event_id(self.db, event_id)

            if config:
                return self._serialize_auto_task_config(config)

            return None

        except Exception as e:
            logger.error(
                f"Failed to get auto-task config for event {event_id}: {e}"
            )
            return None

    def search_events(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search events by keyword and filters.

        Args:
            query: Search keyword (searches title, description, transcript)
            filters: Optional filters:
                - start_date: ISO format date string
                - end_date: ISO format date string
                - attendees: List of attendee emails
                - event_type: Event type filter
                - source: Event source filter

        Returns:
            List of dictionaries containing event and artifacts
        """
        try:
            filters = filters or {}

            # Get events by keyword
            events = CalendarEvent.search(
                self.db,
                keyword=query,
                event_type=filters.get('event_type'),
                source=filters.get('source')
            )

            # Apply date range filter
            if filters.get('start_date') or filters.get('end_date'):
                start_date_value = filters.get('start_date', '1970-01-01')
                end_date_value = filters.get('end_date', '2099-12-31')

                start_dt = to_local_naive(start_date_value)
                end_dt = to_local_naive(end_date_value)

                events = [
                    e for e in events
                    if start_dt <= to_local_naive(e.start_time) <= end_dt
                ]

            # Apply attendees filter
            if filters.get('attendees'):
                filter_attendees = set(filters['attendees'])
                events = [
                    e for e in events
                    if any(a in filter_attendees for a in e.attendees)
                ]

            # Search in transcripts
            if query:
                # Get all event attachments and search transcript content
                events_with_transcript_match = []

                for event in events:
                    attachments = EventAttachment.get_by_event_id(
                        self.db, event.id
                    )

                    # Check if any transcript contains the query
                    transcript_match = False
                    for attachment in attachments:
                        if attachment.attachment_type == 'transcript':
                            try:
                                with open(
                                    attachment.file_path,
                                    'r',
                                    encoding='utf-8'
                                ) as f:
                                    content = f.read()
                                    if query.lower() in content.lower():
                                        transcript_match = True
                                        break
                            except Exception as e:
                                logger.warning(
                                    f"Failed to read transcript "
                                    f"{attachment.file_path}: {e}"
                                )

                    if transcript_match:
                        events_with_transcript_match.append(event)

                # Combine events (remove duplicates)
                event_ids = {e.id for e in events}
                for event in events_with_transcript_match:
                    if event.id not in event_ids:
                        events.append(event)
                        event_ids.add(event.id)

            # Build result with artifacts
            results = []
            for event in events:
                artifacts = self.get_event_artifacts(event.id)
                results.append({
                    'event': event,
                    'artifacts': artifacts,
                    'match_snippet': self.get_search_snippet(
                        event, query
                    )
                })

            logger.debug(
                f"Search found {len(results)} events for query: {query}"
            )
            return results

        except Exception as e:
            logger.error(f"Failed to search events: {e}")
            return []

    def get_event_artifacts(self, event_id: str) -> Dict[str, Any]:
        """
        Get artifacts (recordings, transcripts) for an event.

        Args:
            event_id: Event ID

        Returns:
            Dictionary containing:
            - recording: Recording file path or None
            - transcript: Transcript file path or None
            - attachments: List of all attachments
        """
        try:
            attachments = EventAttachment.get_by_event_id(
                self.db, event_id
            )

            recording = None
            transcript = None

            for attachment in attachments:
                if attachment.attachment_type == 'recording':
                    recording = attachment.file_path
                elif attachment.attachment_type == 'transcript':
                    transcript = attachment.file_path

            return {
                'recording': recording,
                'transcript': transcript,
                'attachments': [
                    {
                        'id': a.id,
                        'type': a.attachment_type,
                        'path': a.file_path,
                        'size': a.file_size,
                        'created_at': a.created_at
                    }
                    for a in attachments
                ]
            }

        except Exception as e:
            logger.error(
                f"Failed to get artifacts for event {event_id}: {e}"
            )
            return {
                'recording': None,
                'transcript': None,
                'attachments': []
            }

    def get_search_snippet(
        self,
        event: CalendarEvent,
        query: str
    ) -> Optional[str]:
        """
        Get a snippet showing where the query matched.

        Args:
            event: CalendarEvent instance
            query: Search query

        Returns:
            Snippet string or None
        """
        if not query:
            return None

        query_lower = query.lower()

        # Check title
        if query_lower in event.title.lower():
            title_prefix = self._translate(
                'timeline.snippet.title_prefix',
                'Title'
            )
            return f"{title_prefix}: ...{event.title}..."

        # Check description
        if event.description and query_lower in event.description.lower():
            # Find the position and extract context
            pos = event.description.lower().find(query_lower)
            start = max(0, pos - 30)
            end = min(len(event.description), pos + len(query) + 30)
            snippet = event.description[start:end]
            description_prefix = self._translate(
                'timeline.snippet.description_prefix',
                'Description'
            )
            return f"{description_prefix}: ...{snippet}..."

        # Check transcripts
        attachments = EventAttachment.get_by_event_id(self.db, event.id)
        fallback_message: Optional[str] = None
        for attachment in attachments:
            if attachment.attachment_type == 'transcript':
                try:
                    with open(
                        attachment.file_path, 'r', encoding='utf-8'
                    ) as f:
                        content = f.read()
                        if query_lower in content.lower():
                            pos = content.lower().find(query_lower)
                            start = max(0, pos - 30)
                            end = min(
                                len(content), pos + len(query) + 30
                            )
                            snippet = content[start:end]
                            transcript_prefix = self._translate(
                                'timeline.snippet.transcript_prefix',
                                'Transcript'
                            )
                            return f"{transcript_prefix}: ...{snippet}..."
                except FileNotFoundError:
                    logger.warning(
                        "Transcript file not found for event %s: %s",
                        event.id,
                        attachment.file_path,
                    )
                    if fallback_message is None:
                        fallback_message = self._translate(
                            'timeline.snippet.missing_transcript',
                            'Transcript unavailable (file missing)'
                        )
                except UnicodeDecodeError:
                    logger.error(
                        "Failed to decode transcript for event %s: %s",
                        event.id,
                        attachment.file_path,
                        exc_info=True,
                    )
                    if fallback_message is None:
                        fallback_message = self._translate(
                            'timeline.snippet.unreadable_transcript',
                            'Transcript unavailable (cannot read transcript)'
                        )
                except Exception as exc:
                    logger.warning(
                        "Failed to read transcript %s for event %s: %s",
                        attachment.file_path,
                        event.id,
                        exc,
                    )
                    if fallback_message is None:
                        fallback_message = self._translate(
                            'timeline.snippet.generic_transcript',
                            'Transcript unavailable'
                        )

        return fallback_message

    def _get_match_snippet(
        self,
        event: CalendarEvent,
        query: str
    ) -> Optional[str]:
        """Compatibility wrapper for older callers."""
        return self.get_search_snippet(event, query)
