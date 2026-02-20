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
Calendar Auto Task Scheduler for EchoNote.

Monitors calendar events and automatically triggers batch transcription
when an event ends if it has a recording but no transcript and auto-transcribe is enabled.
"""

import logging
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger

from data.database.models import AutoTaskConfig, CalendarEvent, EventAttachment
from core.calendar.manager import CalendarManager
from core.transcription.manager import TranscriptionManager

logger = logging.getLogger("echonote.calendar.auto_task_scheduler")

def to_local_naive(dt) -> datetime:
    """Helper to convert to naive local datetime, similarly to timeline manager."""
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt)
        except ValueError:
            pass
    if isinstance(dt, datetime):
        if dt.tzinfo is not None:
            return dt.astimezone().replace(tzinfo=None)
        return dt
    return datetime.now().replace(tzinfo=None)

class CalendarAutoTaskScheduler:
    """
    Automatic task scheduler for backend post-event tasks like batch transcription.
    
    Responsibilities:
    - Add precise DateTrigger jobs for when events end.
    - Fallback polling for missed events (e.g. app was closed).
    - Submits batch transcription tasks for events with audio but no transcript.
    """

    def __init__(
        self,
        calendar_manager: CalendarManager,
        transcription_manager: TranscriptionManager,
        polling_interval_minutes: int = 15,
    ):
        self.calendar_manager = calendar_manager
        self.transcription_manager = transcription_manager
        self.polling_interval_minutes = polling_interval_minutes
        self.scheduler = BackgroundScheduler()
        self.is_running = False

    def start(self):
        """Start the scheduler."""
        if self.is_running:
            return

        try:
            # Fallback polling job
            self.scheduler.add_job(
                func=self._poll_for_auto_tasks,
                trigger="interval",
                minutes=self.polling_interval_minutes,
                id="calendar_auto_task_polling",
                name="Calendar Auto Task Polling Job",
                replace_existing=True,
            )

            self.scheduler.start()
            self.is_running = True
            
            # Initial poll on start
            self._poll_for_auto_tasks()
            
            logger.info("CalendarAutoTaskScheduler started")
        except Exception as e:
            logger.error(f"Failed to start CalendarAutoTaskScheduler: {e}")

    def stop(self):
        """Stop the scheduler."""
        if not self.is_running:
            return

        try:
            self.scheduler.shutdown(wait=False)
            self.scheduler = BackgroundScheduler()
            self.is_running = False
            logger.info("CalendarAutoTaskScheduler stopped")
        except Exception as e:
            logger.error(f"Failed to stop CalendarAutoTaskScheduler: {e}")

    def schedule_event_task(self, event: CalendarEvent, config: AutoTaskConfig):
        """
        Schedule a precise DateTrigger job for when the event ends.
        Called by CalendarManager when an event is created/updated (if integrated).
        """
        if not self.is_running or not config.enable_transcription:
            return

        try:
            end_time = to_local_naive(event.end_time)
            now = to_local_naive(datetime.now())
            if end_time <= now:
                # Event already ended, process immediately
                self._process_event(event.id)
                return

            job_id = f"auto_transcribe_{event.id}"
            self.scheduler.add_job(
                func=self._process_event,
                trigger=DateTrigger(run_date=end_time.astimezone()),
                args=[event.id],
                id=job_id,
                name=f"Auto Transcribe Event {event.id}",
                replace_existing=True,
            )
            logger.info(f"Scheduled auto transcription for event {event.id} at {end_time}")
            
        except Exception as e:
            logger.error(f"Failed to schedule precise task for event {event.id}: {e}")

    def _poll_for_auto_tasks(self):
        """
        Periodic fallback to catch events that ended while the app was closed
        or missed their precise trigger.
        """
        try:
            logger.debug("Polling for missed calendar auto tasks...")
            
            # Find configurations with transcription enabled
            configs = self.calendar_manager.db.execute(
                "SELECT * FROM auto_task_configs WHERE enable_transcription = 1"
            )
            
            if not configs:
                return
                
            now = to_local_naive(datetime.now())
            
            for row in configs:
                config = AutoTaskConfig.from_db_row(row)
                event = CalendarEvent.get_by_id(self.calendar_manager.db, config.event_id)
                if not event:
                    continue
                    
                end_time = to_local_naive(event.end_time)
                # If event has ended
                if end_time <= now:
                    self._process_event(event.id)
                    
        except Exception as e:
            logger.error(f"Error polling for missed calendar auto tasks: {e}")

    def _process_event(self, event_id: str):
        """
        Evaluate and execute post-event transcription if applicable.
        """
        try:
            event = CalendarEvent.get_by_id(self.calendar_manager.db, event_id)
            if not event:
                return

            config = AutoTaskConfig.get_by_event_id(self.calendar_manager.db, event_id)
            if not config or not config.enable_transcription:
                return

            attachments = EventAttachment.get_by_event_id(self.calendar_manager.db, event_id)
            recording_path = None
            has_transcript = False

            for attachment in attachments:
                if attachment.attachment_type == "recording":
                    recording_path = attachment.file_path
                elif attachment.attachment_type in ("transcript", "translation"):
                    has_transcript = True

            if not recording_path:
                logger.debug(f"Event {event_id} has auto-transcribe enabled but no recording.")
                return

            if has_transcript:
                logger.debug(f"Event {event_id} already has a transcript, bypassing auto-transcribe.")
                self._disable_auto_transcribe(config)
                return

            logger.info(f"Triggering auto-transcribe for event {event_id}, audio: {recording_path}")

            options = {"event_id": event_id}
            if config.transcription_language and config.transcription_language != "auto":
                options["language"] = config.transcription_language

            self.transcription_manager.add_task(recording_path, options=options)
            
            # Note: We do not disable the config yet; we disable it so it only runs once here.
            # But the user might attach a new recording later. For now, disable it so we don't
            # endlessly poll and submit the same audio repeatedly.
            self._disable_auto_transcribe(config)

        except Exception as e:
            logger.error(f"Failed to process auto task for event {event_id}: {e}")

    def _disable_auto_transcribe(self, config: AutoTaskConfig):
        """Turn off the flag to prevent redundant processing."""
        try:
            config.enable_transcription = False
            config.save(self.calendar_manager.db)
        except Exception as e:
            logger.error(f"Failed to disable auto-transcribe config for event {config.event_id}: {e}")
