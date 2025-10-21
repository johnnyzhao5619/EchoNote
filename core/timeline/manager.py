"""Timeline Manager for EchoNote."""

import logging
from typing import Optional, List, Dict, Any, Union, Callable, TYPE_CHECKING, Iterable
from datetime import datetime, timedelta

from data.database.models import (
    CalendarEvent,
    EventAttachment,
    AutoTaskConfig
)

if TYPE_CHECKING:  # pragma: no cover - typing only
    from utils.i18n import I18nManager


logger = logging.getLogger('echonote.timeline.manager')


_DEFAULT_TRANSCRIPT_CANDIDATE_WINDOW_DAYS = 30
_MAX_TRANSCRIPT_CANDIDATES = 200


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
            past_events: List[Dict[str, Any]] = []
            future_event_ids: List[str] = []
            future_event_items: List[CalendarEvent] = []
            past_event_items: List[CalendarEvent] = []

            for event in all_events:
                event_start = to_local_naive(event.start_time)

                if event_start < center_time_local:
                    past_event_items.append(event)
                else:
                    # Future event - collect for batch auto-task lookup
                    future_event_ids.append(event.id)
                    future_event_items.append(event)

            past_event_items.sort(
                key=lambda evt: to_local_naive(evt.start_time),
                reverse=True
            )

            total_past_count = len(past_event_items)
            start_idx = max(page, 0) * page_size
            end_idx = start_idx + page_size

            current_page_items = past_event_items[start_idx:end_idx]
            page_event_ids = [event.id for event in current_page_items]

            attachments_map = self._get_attachments_map(page_event_ids)

            for event in current_page_items:
                attachments = attachments_map.get(event.id, [])
                artifacts = self._build_artifacts_from_attachments(attachments)
                past_events.append({
                    'event': event,
                    'artifacts': artifacts
                })

            auto_task_map = self._get_auto_task_map(future_event_ids)

            future_events = []
            for event in future_event_items:
                auto_tasks = auto_task_map.get(event.id)
                if auto_tasks is None:
                    auto_tasks = self._default_auto_task_config()
                future_events.append({
                    'event': event,
                    'auto_tasks': auto_tasks
                })

            # Sort events
            future_events.sort(
                key=lambda x: to_local_naive(x['event'].start_time)
            )

            total_future = len(future_events)

            # Future events always returned on the first page to avoid being
            # paged out by the historical window. Subsequent pages omit them.
            if page == 0:
                future_page = future_events
            else:
                future_page = []

            result = {
                'current_time': center_time_local.isoformat(),
                'past_events': past_events,
                'future_events': future_page,
                'total_count': total_past_count,
                'future_total_count': total_future,
                'page': page,
                'page_size': page_size,
                'has_more': end_idx < total_past_count
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

    def _default_auto_task_config(self) -> Dict[str, Any]:
        """Return the default auto-task configuration for events."""
        return {
            'enable_transcription': False,
            'enable_recording': False,
            'transcription_language': None,
            'enable_translation': False,
            'translation_target_language': None,
        }

    def _get_attachments_map(
        self,
        event_ids: Iterable[str],
        base_map: Optional[Dict[str, List[EventAttachment]]] = None
    ) -> Dict[str, List[EventAttachment]]:
        """Fetch attachments for multiple events in a single query."""
        attachments_map: Dict[str, List[EventAttachment]] = (
            base_map if base_map is not None else {}
        )

        try:
            event_ids_list = list(event_ids)

            unique_ids: List[str] = []
            for event_id in event_ids_list:
                if event_id not in attachments_map and event_id not in unique_ids:
                    unique_ids.append(event_id)
                else:
                    attachments_map.setdefault(event_id, [])

            if not unique_ids:
                return attachments_map

            fetched = EventAttachment.get_by_event_ids(self.db, unique_ids) or {}

            for event_id in unique_ids:
                attachments_map[event_id] = fetched.get(event_id, [])

            return attachments_map
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error(
                "Failed to get attachments for events %s: %s",
                event_ids_list,
                exc,
            )
            return attachments_map

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
        filters: Optional[Dict[str, Any]] = None,
        *,
        include_future_auto_tasks: bool = False,
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
            List of dictionaries containing event and artifacts. When
            ``include_future_auto_tasks`` is ``True`` the dictionaries for
            future events (relative to the current local time) also include an
            ``auto_tasks`` key matching the ``get_timeline_events`` contract.
        """
        try:
            filters = filters or {}

            query_lower = query.lower() if query else ''

            start_dt = (
                to_local_naive(filters['start_date'])
                if filters.get('start_date') else
                datetime(1970, 1, 1)
            )
            end_dt = (
                to_local_naive(filters['end_date'])
                if filters.get('end_date') else
                datetime(2099, 12, 31, 23, 59, 59)
            )
            start_iso = start_dt.isoformat()
            end_iso = end_dt.isoformat()
            has_date_filter = bool(filters.get('start_date') or filters.get('end_date'))

            filter_attendees = (
                set(filters['attendees']) if filters.get('attendees') else None
            )

            def _passes_filters(event: CalendarEvent) -> bool:
                if has_date_filter:
                    event_start = to_local_naive(event.start_time)
                    if not (start_dt <= event_start <= end_dt):
                        return False
                if filter_attendees:
                    attendees = getattr(event, 'attendees', []) or []
                    if not any(attendee in filter_attendees for attendee in attendees):
                        return False
                return True

            # Get events by keyword
            events = CalendarEvent.search(
                self.db,
                keyword=query,
                event_type=filters.get('event_type'),
                source=filters.get('source')
            )

            events = [event for event in events if _passes_filters(event)]

            event_ids = {event.id for event in events}

            attachments_map: Dict[str, List[EventAttachment]] = {}
            if event_ids:
                attachments_map = self._get_attachments_map(event_ids)

            def _attachments_contain_query(
                attachments: List[EventAttachment],
                keyword_lower: str,
                event_id: str,
            ) -> bool:
                for attachment in attachments:
                    if attachment.attachment_type not in {'transcript', 'translation'}:
                        continue

                    content, _ = self._read_attachment_text(
                        attachment,
                        getattr(attachment, 'event_id', event_id),
                        collect_fallback=False,
                    )

                    if content and keyword_lower in content.lower():
                        return True

                return False

            if query:
                candidate_filters = {
                    key: filters[key]
                    for key in ('event_type', 'source')
                    if filters.get(key)
                }

                candidate_start_dt, candidate_end_dt = self._resolve_transcript_candidate_range(
                    start_dt,
                    end_dt,
                    filters,
                )

                candidate_events = self.calendar_manager.get_events(
                    candidate_start_dt.isoformat(),
                    candidate_end_dt.isoformat(),
                    filters=candidate_filters or None
                ) or []

                additional_events: List[CalendarEvent] = []
                for candidate in candidate_events:
                    if candidate.id in event_ids:
                        continue
                    if not _passes_filters(candidate):
                        continue
                    additional_events.append(candidate)
                    if len(additional_events) >= _MAX_TRANSCRIPT_CANDIDATES:
                        break

                if additional_events:
                    attachments_map = self._get_attachments_map(
                        [event.id for event in additional_events],
                        attachments_map,
                    )

                    for candidate in additional_events:
                        attachments = attachments_map.get(candidate.id, [])
                        if _attachments_contain_query(
                            attachments,
                            query_lower,
                            candidate.id,
                        ):
                            events.append(candidate)
                            event_ids.add(candidate.id)
                            attachments_map.setdefault(candidate.id, attachments)

            # Build result with artifacts
            future_reference_time = (
                to_local_naive(datetime.now().astimezone())
                if include_future_auto_tasks
                else None
            )
            future_event_items: Dict[str, Dict[str, Any]] = {}
            future_event_ids: List[str] = []

            results = []
            for event in events:
                attachments = attachments_map.get(event.id, [])
                artifacts = self._build_artifacts_from_attachments(attachments)
                result_item = {
                    'event': event,
                    'artifacts': artifacts,
                    'match_snippet': self.get_search_snippet(
                        event,
                        query,
                        attachments
                    )
                }

                if (
                    include_future_auto_tasks
                    and future_reference_time is not None
                ):
                    event_start = to_local_naive(event.start_time)
                    if event_start >= future_reference_time:
                        future_event_items[event.id] = result_item
                        future_event_ids.append(event.id)

                results.append(result_item)

            if include_future_auto_tasks and future_event_ids:
                auto_task_map = self._get_auto_task_map(future_event_ids)
                for event_id in future_event_ids:
                    config = auto_task_map.get(event_id)
                    if config is None:
                        config = self._default_auto_task_config()
                    else:
                        config = dict(config)
                    future_event_items[event_id]['auto_tasks'] = config

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
            attachments_map = self._get_attachments_map([event_id])
            attachments = attachments_map.get(event_id, [])
            return self._build_artifacts_from_attachments(attachments)

        except Exception as e:
            logger.error(
                f"Failed to get artifacts for event {event_id}: {e}"
            )
            return {
                'recording': None,
                'transcript': None,
                'attachments': []
            }

    @staticmethod
    def _build_artifacts_from_attachments(
        attachments: List[EventAttachment]
    ) -> Dict[str, Any]:
        """Convert attachment objects to artifact dictionary."""
        recording = None
        transcript = None
        translation = None

        for attachment in attachments:
            if attachment.attachment_type == 'recording':
                recording = attachment.file_path
            elif attachment.attachment_type == 'transcript':
                transcript = attachment.file_path
            elif attachment.attachment_type == 'translation':
                translation = attachment.file_path

        return {
            'recording': recording,
            'transcript': transcript,
            'translation': translation,
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

    def _read_attachment_text(
        self,
        attachment: EventAttachment,
        event_id: str,
        collect_fallback: bool = True,
    ) -> tuple[Optional[str], Optional[str]]:
        """Read textual content from transcript/translation attachments."""

        if attachment.attachment_type not in {'transcript', 'translation'}:
            return None, None

        fallback_message: Optional[str] = None
        try:
            with open(attachment.file_path, 'r', encoding='utf-8') as file_obj:
                return file_obj.read(), None
        except FileNotFoundError:
            if attachment.attachment_type == 'translation':
                logger.warning(
                    "Translation file not found for event %s: %s",
                    event_id,
                    attachment.file_path,
                )
            else:
                logger.warning(
                    "Transcript file not found for event %s: %s",
                    event_id,
                    attachment.file_path,
                )
            if collect_fallback:
                fallback_message = self._translate(
                    'timeline.snippet.missing_transcript',
                    'Transcript unavailable (file missing)',
                )
        except UnicodeDecodeError:
            log_message = (
                "Failed to decode translation for event %s: %s"
                if attachment.attachment_type == 'translation'
                else "Failed to decode transcript for event %s: %s"
            )
            logger.error(
                log_message,
                event_id,
                attachment.file_path,
                exc_info=True,
            )
            if collect_fallback:
                fallback_message = self._translate(
                    'timeline.snippet.unreadable_transcript',
                    'Transcript unavailable (cannot read transcript)',
                )
        except Exception as exc:  # pragma: no cover - defensive logging
            log_message = (
                "Failed to read translation %s for event %s: %s"
                if attachment.attachment_type == 'translation'
                else "Failed to read transcript %s for event %s: %s"
            )
            logger.warning(
                log_message,
                attachment.file_path,
                event_id,
                exc,
            )
            if collect_fallback:
                fallback_message = self._translate(
                    'timeline.snippet.generic_transcript',
                    'Transcript unavailable',
                )

        return None, fallback_message

    def get_search_snippet(
        self,
        event: CalendarEvent,
        query: str,
        attachments: Optional[List[EventAttachment]] = None
    ) -> Optional[str]:
        """
        Get a snippet showing where the query matched.

        Args:
            event: CalendarEvent instance
            query: Search query
            attachments: Optional pre-fetched attachments for the event

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
        attachments_to_check = attachments
        if attachments_to_check is None:
            attachments_to_check = EventAttachment.get_by_event_id(
                self.db,
                event.id
            )
        fallback_message: Optional[str] = None
        for attachment in attachments_to_check:
            if attachment.attachment_type not in {'transcript', 'translation'}:
                continue

            content, attachment_fallback = self._read_attachment_text(
                attachment,
                event.id,
            )

            if attachment_fallback and fallback_message is None:
                fallback_message = attachment_fallback

            if not content:
                continue

            content_lower = content.lower()
            if query_lower in content_lower:
                pos = content_lower.find(query_lower)
                start = max(0, pos - 30)
                end = min(len(content), pos + len(query) + 30)
                snippet = content[start:end]

                prefix_key = 'timeline.snippet.transcript_prefix'
                default_prefix = 'Transcript'
                if attachment.attachment_type == 'translation':
                    prefix_key = 'timeline.snippet.translation_prefix'
                    default_prefix = 'Translation'

                transcript_prefix = self._translate(
                    prefix_key,
                    default_prefix,
                )
                return f"{transcript_prefix}: ...{snippet}..."

        return fallback_message

    def _get_match_snippet(
        self,
        event: CalendarEvent,
        query: str
    ) -> Optional[str]:
        """Compatibility wrapper for older callers."""
        return self.get_search_snippet(event, query)

    def _resolve_transcript_candidate_range(
        self,
        start_dt: datetime,
        end_dt: datetime,
        filters: Dict[str, Any]
    ) -> tuple[datetime, datetime]:
        """Determine a bounded range for transcript candidate expansion."""
        window = timedelta(days=_DEFAULT_TRANSCRIPT_CANDIDATE_WINDOW_DAYS)
        has_start = bool(filters.get('start_date'))
        has_end = bool(filters.get('end_date'))

        if has_start and has_end:
            candidate_start = start_dt
            candidate_end = end_dt
        elif has_start:
            candidate_start = start_dt
            candidate_end = start_dt + window
        elif has_end:
            candidate_end = end_dt
            candidate_start = end_dt - window
        else:
            event_type = filters.get('event_type')
            source = filters.get('source')

            bounds = CalendarEvent.get_time_bounds(
                self.db,
                event_type=event_type,
                source=source,
            )

            if bounds:
                min_start, max_end = bounds
                candidate_start = to_local_naive(min_start)
                candidate_end = to_local_naive(max_end)
            else:
                attachment_bounds = EventAttachment.get_transcript_event_bounds(
                    self.db,
                    limit=_MAX_TRANSCRIPT_CANDIDATES,
                    event_type=event_type,
                    source=source,
                )

                if attachment_bounds:
                    min_start, max_end = attachment_bounds
                    candidate_start = to_local_naive(min_start)
                    candidate_end = to_local_naive(max_end)
                else:
                    candidate_start = start_dt
                    candidate_end = end_dt

        if candidate_end < candidate_start:
            candidate_start, candidate_end = candidate_end, candidate_start

        return candidate_start, candidate_end
