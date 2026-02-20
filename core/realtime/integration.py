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
Integration services for real-time recording (e.g., Calendar).
"""

import logging
import os
from datetime import datetime
from typing import Dict, Optional

from core.calendar.constants import CalendarSource, EventType
from utils.time_utils import format_localized_datetime

logger = logging.getLogger(__name__)


def save_event_attachments(db_connection, event_id: str, recording_result: Dict) -> None:
    """Persist recording artifacts as event attachments when files exist."""
    if not db_connection or not event_id:
        return

    try:
        from data.database.models import EventAttachment
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to import EventAttachment model: %s", exc)
        return

    for key, type_code in (
        ("recording_path", "recording"),
        ("transcript_path", "transcript"),
        ("translation_path", "translation"),
    ):
        path = recording_result.get(key)
        if not path or not os.path.exists(path):
            continue

        try:
            EventAttachment(
                event_id=event_id,
                attachment_type=type_code,
                file_path=path,
                file_size=os.path.getsize(path),
            ).save(db_connection)
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "Failed to save %s attachment for event %s: %s",
                type_code,
                event_id,
                exc,
                exc_info=True,
            )


class CalendarIntegration:
    """Handles calendar event updates for recording sessions."""

    def __init__(self, db_connection, i18n=None, calendar_manager=None):
        self.db = db_connection
        self.i18n = i18n
        self.calendar_manager = calendar_manager
        self._last_error = ""

    def set_calendar_manager(self, calendar_manager) -> None:
        """Inject or replace calendar manager at runtime."""
        self.calendar_manager = calendar_manager

    def get_last_error(self) -> str:
        """Return the latest event creation error message."""
        return self._last_error

    def _translate(self, key: str, default: str, **kwargs) -> str:
        """Helper for translation."""
        if self.i18n:
            try:
                translated = self.i18n.t(key, **kwargs)
                if translated and translated != key:
                    return translated
            except Exception:
                pass
        return default.format(**kwargs)

    async def create_event(self, recording_result: Dict) -> str:
        """
        Create a calendar event for the session.

        Args:
            recording_result: Dictionary containing session metadata and file paths.

        Returns:
            Event ID if successful, empty string otherwise.
        """
        self._last_error = ""
        if not self.db:
            self._last_error = "No database connection for calendar integration"
            logger.warning(self._last_error)
            return ""

        try:
            start_time_str = recording_result.get("start_time")
            if not start_time_str:
                self._last_error = "Missing recording start_time"
                return ""

            start_time = datetime.fromisoformat(start_time_str)
            title_time = format_localized_datetime(start_time)
            duration_value = recording_result.get("duration", 0.0)

            title = self._translate(
                "realtime_record.calendar_event.title",
                "Recording Session - {timestamp}",
                timestamp=title_time,
            )
            description = self._build_event_description(recording_result, duration_value)

            event_data = {
                "title": title,
                "event_type": EventType.EVENT,
                "start_time": recording_result["start_time"],
                "end_time": recording_result["end_time"],
                "description": description,
                "source": CalendarSource.LOCAL,
            }

            if self.calendar_manager is not None:
                event_id = self.calendar_manager.create_event(event_data)
            else:
                from data.database.models import CalendarEvent

                event = CalendarEvent(**event_data)
                event.save(self.db)
                event_id = event.id

            save_event_attachments(self.db, event_id, recording_result)

            logger.info(f"Calendar event created: {event_id}")
            return event_id

        except Exception as e:
            self._last_error = str(e)
            logger.error(f"Failed to create calendar event: {e}", exc_info=True)
            return ""

    def _build_event_description(self, recording_result: Dict, duration_value: float) -> str:
        """Build a rich event description for recordings."""
        start_time = recording_result.get("start_time", "")
        end_time = recording_result.get("end_time", "")
        recording_path = recording_result.get("recording_path", "")
        transcript_path = recording_result.get("transcript_path", "")
        translation_path = recording_result.get("translation_path", "")
        input_device_name = recording_result.get("input_device_name", "")
        input_device_is_loopback = bool(recording_result.get("input_device_is_loopback", False))
        input_device_is_system_audio = bool(
            recording_result.get("input_device_is_system_audio", False)
        )
        input_device_scoped_app = str(recording_result.get("input_device_scoped_app", "") or "")

        capture_route = "Microphone/unknown"
        if input_device_is_loopback:
            capture_route = "Loopback/System audio capable"
        elif input_device_is_system_audio:
            capture_route = "Virtual meeting/system audio input"
            if input_device_scoped_app:
                capture_route = f"{capture_route} ({input_device_scoped_app})"

        transcript_preview = recording_result.get("transcript_preview") or self._read_text_preview(
            transcript_path
        )
        translation_preview = recording_result.get(
            "translation_preview"
        ) or self._read_text_preview(translation_path)

        lines = [
            self._translate(
                "realtime_record.calendar_event.description",
                "Recording duration: {duration} seconds",
                duration=f"{float(duration_value):.2f}",
            ),
            f"Start: {format_localized_datetime(start_time)}",
            f"End: {format_localized_datetime(end_time)}",
            f"Input device: {input_device_name or 'N/A'}",
            f"Capture route: {capture_route}",
            f"Recording file: {recording_path or 'N/A'}",
            f"Transcript file: {transcript_path or 'N/A'}",
            f"Translation file: {translation_path or 'N/A'}",
        ]

        if transcript_preview:
            lines.append(f"Transcript preview: {transcript_preview}")
        if translation_preview:
            lines.append(f"Translation preview: {translation_preview}")

        return "\n".join(lines)

    @staticmethod
    def _read_text_preview(path: str, max_chars: int = 300) -> str:
        """Read a short preview from a text file if available."""
        if not path or not os.path.exists(path):
            return ""
        try:
            with open(path, "r", encoding="utf-8") as handle:
                text = handle.read(max_chars).strip()
            return " ".join(text.split())
        except Exception:
            return ""
