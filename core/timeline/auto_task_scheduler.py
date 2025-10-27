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
Auto Task Scheduler for EchoNote.

Monitors upcoming events and automatically starts configured tasks
(recording, transcription) when events begin.
"""

import asyncio
import logging
import queue
import threading
from datetime import datetime
from typing import Any, Dict, Optional

from apscheduler.schedulers.background import BackgroundScheduler

from core.timeline.manager import to_local_naive
from data.database.models import EventAttachment
from ui.common.notification import get_notification_manager
from utils.i18n import I18nQtManager

logger = logging.getLogger("echonote.timeline.auto_task_scheduler")


class AutoTaskScheduler:
    """
    Automatic task scheduler for calendar events.

    Responsibilities:
    - Monitor upcoming events
    - Send reminder notifications before events start
    - Automatically start recording/transcription when events begin
    - Stop recording when events end and save attachments
    - Handle errors gracefully without stopping the scheduler
    """

    def __init__(
        self,
        timeline_manager,
        realtime_recorder,
        db_connection,
        file_manager,
        reminder_minutes: int = 5,
        settings_manager=None,
        i18n_manager: Optional[I18nQtManager] = None,
    ):
        """
        Initialize the auto task scheduler.

        Args:
            timeline_manager: TimelineManager instance
            realtime_recorder: RealtimeRecorder instance
            db_connection: Database connection instance
            file_manager: FileManager instance
            reminder_minutes: Minutes before event to send reminder (default: 5)
            settings_manager: SettingsManager instance providing global defaults
        """
        self.timeline_manager = timeline_manager
        self.realtime_recorder = realtime_recorder
        self.db = db_connection
        self.file_manager = file_manager
        self.scheduler = BackgroundScheduler()
        self.is_running = False
        self.settings_manager = settings_manager
        self.i18n = self._initialize_i18n(i18n_manager)

        initial_reminder = self._coerce_reminder_minutes(reminder_minutes)
        if initial_reminder is None:
            initial_reminder = 5
        self._apply_reminder_minutes(initial_reminder)

        # Track events that have been notified/started/stopped
        self.notified_events = set()
        self.started_events = set()
        self.active_recordings = {}  # event_id -> recording_info

        # Get notification manager
        self.notification_manager = get_notification_manager()

        # Subscribe to setting changes when available
        self._subscribe_to_setting_changes()

        logger.info(
            f"AutoTaskScheduler initialized " f"(reminder: {self.reminder_minutes} minutes)"
        )

    def start(self):
        """
        Start the scheduler.

        Checks for upcoming events every minute.
        """
        if self.is_running:
            logger.warning("Scheduler is already running")
            return

        try:
            # Add job to check upcoming events every minute
            self.scheduler.add_job(
                self._check_upcoming_events, "interval", minutes=1, id="check_upcoming_events"
            )

            self.scheduler.start()
            self.is_running = True
            logger.info("AutoTaskScheduler started")

        except Exception as e:
            logger.error(f"Failed to start scheduler: {e}")
            raise

    def stop(self):
        """Stop the scheduler and clean up active recordings."""
        if not self.is_running:
            logger.warning("Scheduler is not running")
            return

        try:
            # Stop all active recordings
            if self.active_recordings:
                logger.info(f"Stopping {len(self.active_recordings)} active recordings...")
                for event_id in list(self.active_recordings.keys()):
                    try:
                        recording_info = self.active_recordings[event_id]
                        event = recording_info.get("event")
                        if event:
                            self._stop_auto_tasks(event)
                    except Exception as e:
                        logger.error(f"Error stopping recording for event {event_id}: {e}")

            # Shutdown scheduler
            self.scheduler.shutdown(wait=False)
            self.is_running = False
            logger.info("AutoTaskScheduler stopped")

        except Exception as e:
            logger.error(f"Failed to stop scheduler: {e}", exc_info=True)
            raise

    def _initialize_i18n(self, i18n_manager: Optional[I18nQtManager]) -> I18nQtManager:
        """Prepare the translation manager used for notifications."""
        if i18n_manager is not None:
            return i18n_manager

        default_language = "zh_CN"
        if self.settings_manager and hasattr(self.settings_manager, "get_language"):
            try:
                language = self.settings_manager.get_language()
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Failed to load language preference for auto tasks: %s", exc, exc_info=True
                )
            else:
                if language:
                    default_language = language

        return I18nQtManager(default_language=default_language)

    def _coerce_reminder_minutes(self, value) -> Optional[int]:
        """Convert reminder minutes to a non-negative integer when possible."""
        if value is None:
            logger.info("Received None for reminder minutes; keeping previous value")
            return None

        try:
            minutes = int(value)
        except (TypeError, ValueError):
            logger.warning("Invalid reminder minutes value %r; keeping previous value", value)
            return None

        if minutes < 0:
            logger.warning("Reminder minutes %s is negative; clamping to zero", minutes)
            minutes = 0

        return minutes

    def _apply_reminder_minutes(self, minutes: int) -> None:
        """Persist reminder minutes and refresh dependent time windows."""
        self.reminder_minutes = minutes
        from config.constants import (
            MIN_REMINDER_WINDOW_MINUTES,
            REMINDER_FUTURE_WINDOW_OFFSET_MINUTES,
            MIN_FUTURE_WINDOW_MINUTES,
        )

        self._past_window_minutes = max(minutes, MIN_REMINDER_WINDOW_MINUTES)
        self._future_window_minutes = max(
            minutes + REMINDER_FUTURE_WINDOW_OFFSET_MINUTES, MIN_FUTURE_WINDOW_MINUTES
        )

    def _subscribe_to_setting_changes(self) -> None:
        """Listen for reminder preference updates from the settings manager."""
        if not self.settings_manager:
            return

        signal = getattr(self.settings_manager, "setting_changed", None)
        if signal is None:
            return

        connect = getattr(signal, "connect", None)
        if not callable(connect):
            logger.warning("settings_manager.setting_changed lacks a callable connect method")
            return

        try:
            connect(self._on_setting_changed)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Failed to connect to settings_manager.setting_changed: %s", exc, exc_info=True
            )

    def _on_setting_changed(self, key: str, value) -> None:
        """React to reminder preference updates without restarting the scheduler."""
        if key != "timeline.reminder_minutes":
            return

        minutes = self._coerce_reminder_minutes(value)
        if minutes is None or minutes == self.reminder_minutes:
            return

        self._apply_reminder_minutes(minutes)
        self.notified_events.clear()

        logger.info("Reminder minutes updated to %s via settings change", minutes)

    def _check_upcoming_events(self):
        """
        Check for upcoming events and handle notifications/auto-start/auto-stop.

        This method is called every minute by the scheduler.
        """
        try:
            now_local = to_local_naive(datetime.now().astimezone())

            past_window_days = self._past_window_minutes / (24 * 60)
            future_window_days = self._future_window_minutes / (24 * 60)

            # Get events within the configured windows to drive reminders
            timeline_data = self.timeline_manager.get_timeline_events(
                center_time=now_local, past_days=past_window_days, future_days=future_window_days
            )

            future_events = timeline_data.get("future_events", [])
            past_events = timeline_data.get("past_events", [])

            # Process future events (notifications and start)
            for event_data in future_events:
                event = event_data["event"]
                auto_tasks = event_data["auto_tasks"]

                # Skip if no auto tasks configured
                if not (
                    auto_tasks.get("enable_transcription") or auto_tasks.get("enable_recording")
                ):
                    continue

                event_start = to_local_naive(event.start_time)
                time_until_start = (event_start - now_local).total_seconds()

                # Send reminder N minutes before event
                reminder_seconds = self.reminder_minutes * 60
                if (
                    reminder_seconds <= time_until_start <= reminder_seconds + 60
                    and event.id not in self.notified_events
                ):
                    self._send_reminder_notification(event, auto_tasks)
                    self.notified_events.add(event.id)

                # Start auto tasks when event begins
                # (within 1 minute of start time)
                if -60 <= time_until_start <= 60 and event.id not in self.started_events:
                    started = self._start_auto_tasks(event, auto_tasks)
                    if started:
                        self.started_events.add(event.id)

            # Process past events (stop recordings)
            for event_data in past_events:
                event = event_data["event"]

                # Check if this event has an active recording
                if event.id in self.active_recordings:
                    event_end = to_local_naive(event.end_time)
                    time_since_end = (now_local - event_end).total_seconds()

                    # Stop recording if event ended (within 2 minutes)
                    if 0 <= time_since_end <= 120:
                        self._stop_auto_tasks(event)

            # Clean up old event IDs from tracking sets
            # (events more than 1 hour old)
            self._cleanup_tracking_sets(now_local)

        except Exception as e:
            logger.error(f"Error checking upcoming events: {e}", exc_info=True)
            # Don't raise - we want the scheduler to continue

    def _send_reminder_notification(self, event, auto_tasks: dict):
        """
        Send a reminder notification for an upcoming event.

        Args:
            event: CalendarEvent instance
            auto_tasks: Dictionary of auto-task configuration
        """
        try:
            # Build notification message
            tasks = []
            if auto_tasks.get("enable_transcription"):
                tasks.append(self.i18n.t("auto_task.tasks.transcription"))
            if auto_tasks.get("enable_recording"):
                tasks.append(self.i18n.t("auto_task.tasks.recording"))

            separator = self.i18n.t("auto_task.tasks.separator")
            if not isinstance(separator, str) or not separator:
                separator = ", "
            tasks_str = separator.join(tasks) if tasks else self.i18n.t("auto_task.tasks.none")

            # Format start time for display
            try:
                start_dt = to_local_naive(event.start_time)
            except Exception:
                start_time_str = event.start_time
            else:
                start_time_str = start_dt.strftime("%H:%M")

            title = self.i18n.t("auto_task.reminder.title", app_name=self.i18n.t("app.name"))
            start_time_label = self.i18n.t("auto_task.reminder.start_time_label")
            task_list_label = self.i18n.t("auto_task.reminder.task_list_label")
            message = self.i18n.t(
                "auto_task.reminder.message",
                event_title=event.title,
                start_time_label=start_time_label,
                start_time=start_time_str,
                task_list_label=task_list_label,
                task_list=tasks_str,
            )

            # Send desktop notification
            self.notification_manager.send_info(title, message)

            logger.info(f"Reminder notification sent for event: {event.id} - {event.title}")

        except Exception as e:
            logger.error(f"Failed to send reminder for event {event.id}: {e}", exc_info=True)

    def _get_realtime_preferences(self) -> Dict[str, Any]:
        """Load realtime recording defaults from settings manager."""
        if self.settings_manager and hasattr(self.settings_manager, "get_realtime_preferences"):
            try:
                return self.settings_manager.get_realtime_preferences()
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Failed to load realtime preferences for auto tasks: %s", exc, exc_info=True
                )

        return {"recording_format": "wav", "auto_save": True}

    def _build_recording_options(self, event, auto_tasks: dict) -> Dict[str, Any]:
        """Assemble recording options for auto-started sessions."""
        preferences = self._get_realtime_preferences()

        enable_recording = auto_tasks.get("enable_recording")
        if enable_recording is None:
            save_recording = preferences.get("auto_save", True)
        else:
            save_recording = bool(enable_recording)

        options = {
            "event_id": event.id,
            "event_title": event.title,
            "language": auto_tasks.get("transcription_language"),
            "enable_translation": auto_tasks.get("enable_translation", False),
            "target_language": auto_tasks.get("translation_target_language"),
            "recording_format": preferences.get("recording_format", "wav"),
            "save_recording": save_recording,
            "save_transcript": auto_tasks.get("enable_transcription", True),
            "create_calendar_event": False,
        }

        return options

    def _start_auto_tasks(self, event, auto_tasks: dict) -> bool:
        """
        Start automatic tasks for an event.

        Args:
            event: CalendarEvent instance
            auto_tasks: Dictionary of auto-task configuration
        """
        loop = None
        thread = None
        result_queue = queue.Queue(maxsize=1)

        try:
            logger.info(f"Starting auto tasks for event: {event.id} - {event.title}")

            # Check if already recording
            if self.realtime_recorder.is_recording:
                logger.warning(
                    f"Cannot start auto tasks for event {event.id}: " f"recorder is already active"
                )
                # Send notification to user
                app_name = self.i18n.t("app.name")
                title = self.i18n.t(
                    "auto_task.notifications.recorder_busy.title", app_name=app_name
                )
                message = self.i18n.t(
                    "auto_task.notifications.recorder_busy.message", event_title=event.title
                )
                self.notification_manager.send_warning(title, message)
                return False

            # Prepare recording options
            options = self._build_recording_options(event, auto_tasks)

            # Create a new event loop for this recording
            loop = asyncio.new_event_loop()

            # Define async function to start recording
            async def start_recording_async():
                await self.realtime_recorder.start_recording(
                    input_source=None, options=options, event_loop=loop  # Use default
                )

            # Start the event loop in a separate thread
            def run_loop():
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(start_recording_async())
                except Exception as exc:  # noqa: BLE001
                    logger.error("Error in event loop while starting: %s", exc, exc_info=True)
                    try:
                        result_queue.put_nowait(("error", exc))
                    except queue.Full:
                        pass
                else:
                    try:
                        result_queue.put_nowait(("success", None))
                    except queue.Full:
                        pass
                    # Keep loop running for background tasks
                    loop.run_forever()
                finally:
                    loop.close()

            thread = threading.Thread(target=run_loop, daemon=True)
            thread.start()

            # Wait for start result from background thread
            try:
                status, payload = result_queue.get(timeout=5.0)
            except queue.Empty:
                status = "success" if self.realtime_recorder.is_recording else "error"
                payload = None

            if status == "error":
                raise RuntimeError(
                    f"自动录制启动失败：{payload}" if payload else "自动录制启动失败"
                )

            if not self.realtime_recorder.is_recording:
                raise RuntimeError("自动录制未在预期时间内启动")

            # Store recording info for later stopping
            self.active_recordings[event.id] = {
                "event": event,
                "auto_tasks": auto_tasks,
                "start_time": to_local_naive(datetime.now().astimezone()),
                "loop": loop,
                "thread": thread,
            }

            logger.info(f"Successfully started auto tasks for event {event.id}")

            # Send success notification
            app_name = self.i18n.t("app.name")
            title = self.i18n.t("auto_task.notifications.start_success.title", app_name=app_name)
            message = self.i18n.t(
                "auto_task.notifications.start_success.message", event_title=event.title
            )
            self.notification_manager.send_success(title, message)
            return True

        except Exception as e:  # noqa: BLE001
            logger.error(f"Failed to start auto tasks for event {event.id}: {e}", exc_info=True)

            # Ensure no stale state remains
            self.active_recordings.pop(event.id, None)
            self.started_events.discard(event.id)

            if loop is not None:
                try:
                    if not loop.is_closed():
                        loop.call_soon_threadsafe(loop.stop)
                except Exception:  # noqa: BLE001
                    pass

            if thread is not None and thread.is_alive():
                thread.join(timeout=2.0)

            app_name = self.i18n.t("app.name")
            title = self.i18n.t("auto_task.notifications.start_error.title", app_name=app_name)
            error_detail = str(e)
            if not error_detail:
                error_detail = repr(e)
            message = self.i18n.t(
                "auto_task.notifications.start_error.message",
                event_title=event.title,
                error_message=error_detail,
            )
            # Send error notification
            self.notification_manager.send_error(title, message)
            return False
            # Don't raise - we want the scheduler to continue

    def _stop_auto_tasks(self, event):
        """
        Stop automatic tasks for an event and save attachments.

        Args:
            event: CalendarEvent instance
        """
        try:
            if event.id not in self.active_recordings:
                logger.debug(f"No active recording for event {event.id}, skipping stop")
                return

            recording_info = self.active_recordings[event.id]
            loop = recording_info.get("loop")
            thread = recording_info.get("thread")

            logger.info(f"Stopping auto tasks for event: {event.id} - {event.title}")

            # Stop recording
            try:
                if loop and not loop.is_closed():
                    # Schedule stop_recording in the event loop
                    future = asyncio.run_coroutine_threadsafe(
                        self.realtime_recorder.stop_recording(), loop
                    )

                    # Wait for result (with timeout)
                    try:
                        result = future.result(timeout=10.0)
                    except Exception as e:
                        logger.error(f"Timeout or error stopping recording: {e}")
                        result = {}

                    # Stop the event loop
                    loop.call_soon_threadsafe(loop.stop)

                    # Wait for thread to finish (with timeout)
                    if thread and thread.is_alive():
                        thread.join(timeout=5.0)

                    # Close the loop
                    if not loop.is_closed():
                        loop.close()

                    # Save attachments to database
                    self._save_event_attachments(event.id, result)

                    logger.info(f"Successfully stopped auto tasks for event {event.id}")

                    # Send success notification
                    duration = result.get("duration", 0)
                    app_name = self.i18n.t("app.name")
                    title = self.i18n.t(
                        "auto_task.notifications.stop_success.title", app_name=app_name
                    )
                    message = self.i18n.t(
                        "auto_task.notifications.stop_success.message",
                        event_title=event.title,
                        duration_seconds=f"{duration:.1f}",
                    )
                    self.notification_manager.send_success(title, message)
                else:
                    logger.warning(f"Event loop for event {event.id} is closed or invalid")

            except Exception as e:
                logger.error(f"Error stopping recording for event {event.id}: {e}", exc_info=True)
                # Try to clean up loop anyway
                if loop and not loop.is_closed():
                    try:
                        loop.call_soon_threadsafe(loop.stop)
                        if thread and thread.is_alive():
                            thread.join(timeout=2.0)
                        loop.close()
                    except Exception:
                        pass
                raise

            # Remove from active recordings
            del self.active_recordings[event.id]

        except Exception as e:
            logger.error(f"Failed to stop auto tasks for event {event.id}: {e}", exc_info=True)

            app_name = self.i18n.t("app.name")
            title = self.i18n.t("auto_task.notifications.stop_error.title", app_name=app_name)
            error_detail = str(e)
            if not error_detail:
                error_detail = repr(e)
            message = self.i18n.t(
                "auto_task.notifications.stop_error.message",
                event_title=event.title,
                error_message=error_detail,
            )
            # Send error notification
            self.notification_manager.send_error(title, message)
            # Don't raise - we want the scheduler to continue

    def _save_event_attachments(self, event_id: str, recording_result: Dict[str, Any]):
        """
        Save recording and transcript as event attachments.

        Args:
            event_id: Event ID
            recording_result: Result from stop_recording()
        """
        try:
            import os

            # Save recording attachment
            recording_path = recording_result.get("recording_path")
            if recording_path and os.path.exists(recording_path):
                attachment = EventAttachment(
                    event_id=event_id,
                    attachment_type="recording",
                    file_path=recording_path,
                    file_size=os.path.getsize(recording_path),
                )
                attachment.save(self.db)
                logger.info(f"Saved recording attachment for event {event_id}")

            # Save transcript attachment
            transcript_path = recording_result.get("transcript_path")
            if transcript_path and os.path.exists(transcript_path):
                attachment = EventAttachment(
                    event_id=event_id,
                    attachment_type="transcript",
                    file_path=transcript_path,
                    file_size=os.path.getsize(transcript_path),
                )
                attachment.save(self.db)
                logger.info(f"Saved transcript attachment for event {event_id}")

            # Save translation attachment (if exists)
            translation_path = recording_result.get("translation_path")
            if translation_path and os.path.exists(translation_path):
                attachment = EventAttachment(
                    event_id=event_id,
                    attachment_type="translation",
                    file_path=translation_path,
                    file_size=os.path.getsize(translation_path),
                )
                attachment.save(self.db)
                logger.info(f"Saved translation attachment for event {event_id}")

        except Exception as e:
            logger.error(f"Failed to save attachments for event {event_id}: {e}", exc_info=True)

    def _cleanup_tracking_sets(self, now: datetime):
        """
        Clean up old event IDs from tracking sets.

        Args:
            now: Current datetime
        """
        try:
            # Get events from the past 2 hours
            timeline_data = self.timeline_manager.get_timeline_events(
                center_time=now, past_days=0.0833, future_days=0  # ~2 hours in days
            )

            past_events = timeline_data.get("past_events", [])
            recent_event_ids = {e["event"].id for e in past_events}

            # Remove event IDs that are no longer in recent past
            old_notified = self.notified_events - recent_event_ids
            old_started = self.started_events - recent_event_ids

            if old_notified:
                logger.debug(f"Cleaning up {len(old_notified)} old notified events")
                self.notified_events = self.notified_events & recent_event_ids

            if old_started:
                logger.debug(f"Cleaning up {len(old_started)} old started events")
                self.started_events = self.started_events & recent_event_ids

            # Clean up active recordings that are too old (safety check)
            old_recordings = []
            for event_id, recording_info in self.active_recordings.items():
                start_time = recording_info.get("start_time")
                if start_time:
                    age = (now - start_time).total_seconds()
                    # If recording is older than 4 hours, force stop
                    if age > 14400:
                        old_recordings.append(event_id)
                        logger.warning(
                            f"Found stale recording for event {event_id}, "
                            f"age: {age/3600:.1f} hours"
                        )

            # Force stop old recordings
            for event_id in old_recordings:
                try:
                    recording_info = self.active_recordings[event_id]
                    event = recording_info.get("event")
                    if event:
                        self._stop_auto_tasks(event)
                except Exception as e:
                    logger.error(f"Error force-stopping old recording {event_id}: {e}")

        except Exception as e:
            logger.error(f"Error cleaning up tracking sets: {e}", exc_info=True)
