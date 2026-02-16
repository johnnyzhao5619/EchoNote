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

    def __init__(self, db_connection, i18n=None):
        self.db = db_connection
        self.i18n = i18n

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
        if not self.db:
            logger.warning("No database connection for calendar integration")
            return ""

        try:
            from data.database.models import CalendarEvent

            start_time_str = recording_result.get("start_time")
            if not start_time_str:
                return ""
            
            start_time = datetime.fromisoformat(start_time_str)
            title_time = start_time.strftime("%Y-%m-%d %H:%M")
            duration_value = recording_result.get("duration", 0.0)
            
            title = self._translate(
                "realtime_record.calendar_event.title",
                "Recording Session - {timestamp}",
                timestamp=title_time,
            )
            
            description = self._translate(
                "realtime_record.calendar_event.description",
                "Recording duration: {duration} seconds",
                duration=f"{float(duration_value):.2f}",
            )

            event = CalendarEvent(
                title=title,
                event_type="Event",
                start_time=recording_result["start_time"],
                end_time=recording_result["end_time"],
                description=description,
                source="local",
            )
            event.save(self.db)

            save_event_attachments(self.db, event.id, recording_result)

            logger.info(f"Calendar event created: {event.id}")
            return event.id

        except Exception as e:
            logger.error(f"Failed to create calendar event: {e}")
            return ""
