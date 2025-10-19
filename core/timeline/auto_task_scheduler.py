"""
Auto Task Scheduler for EchoNote.

Monitors upcoming events and automatically starts configured tasks
(recording, transcription) when events begin.
"""

import logging
import asyncio
import threading
from datetime import datetime
from typing import Dict, Any
from apscheduler.schedulers.background import BackgroundScheduler

from ui.common.notification import get_notification_manager
from data.database.models import EventAttachment


logger = logging.getLogger('echonote.timeline.auto_task_scheduler')


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
        settings_manager=None
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
        self.reminder_minutes = reminder_minutes
        self.settings_manager = settings_manager

        # Track events that have been notified/started/stopped
        self.notified_events = set()
        self.started_events = set()
        self.active_recordings = {}  # event_id -> recording_info

        # Get notification manager
        self.notification_manager = get_notification_manager()

        logger.info(
            f"AutoTaskScheduler initialized "
            f"(reminder: {reminder_minutes} minutes)"
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
                self._check_upcoming_events,
                'interval',
                minutes=1,
                id='check_upcoming_events'
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
                logger.info(
                    f"Stopping {len(self.active_recordings)} active recordings..."
                )
                for event_id in list(self.active_recordings.keys()):
                    try:
                        recording_info = self.active_recordings[event_id]
                        event = recording_info.get('event')
                        if event:
                            self._stop_auto_tasks(event)
                    except Exception as e:
                        logger.error(
                            f"Error stopping recording for event {event_id}: {e}"
                        )

            # Shutdown scheduler
            self.scheduler.shutdown(wait=False)
            self.is_running = False
            logger.info("AutoTaskScheduler stopped")

        except Exception as e:
            logger.error(f"Failed to stop scheduler: {e}", exc_info=True)
            raise

    def _check_upcoming_events(self):
        """
        Check for upcoming events and handle notifications/auto-start/auto-stop.

        This method is called every minute by the scheduler.
        """
        try:
            now = datetime.now()

            # Get events in the next 15 minutes and past 5 minutes
            # (to catch events that just ended)
            timeline_data = self.timeline_manager.get_timeline_events(
                center_time=now,
                past_days=0.0035,  # ~5 minutes in days
                future_days=0.0104  # ~15 minutes in days
            )

            future_events = timeline_data.get('future_events', [])
            past_events = timeline_data.get('past_events', [])

            # Process future events (notifications and start)
            for event_data in future_events:
                event = event_data['event']
                auto_tasks = event_data['auto_tasks']

                # Skip if no auto tasks configured
                if not (auto_tasks.get('enable_transcription') or
                        auto_tasks.get('enable_recording')):
                    continue

                event_start = datetime.fromisoformat(event.start_time)
                time_until_start = (event_start - now).total_seconds()

                # Send reminder N minutes before event
                reminder_seconds = self.reminder_minutes * 60
                if (reminder_seconds <= time_until_start <=
                        reminder_seconds + 60 and
                        event.id not in self.notified_events):
                    self._send_reminder_notification(event, auto_tasks)
                    self.notified_events.add(event.id)

                # Start auto tasks when event begins
                # (within 1 minute of start time)
                if (-60 <= time_until_start <= 60 and
                        event.id not in self.started_events):
                    self._start_auto_tasks(event, auto_tasks)
                    self.started_events.add(event.id)

            # Process past events (stop recordings)
            for event_data in past_events:
                event = event_data['event']
                
                # Check if this event has an active recording
                if event.id in self.active_recordings:
                    event_end = datetime.fromisoformat(event.end_time)
                    time_since_end = (now - event_end).total_seconds()
                    
                    # Stop recording if event ended (within 2 minutes)
                    if 0 <= time_since_end <= 120:
                        self._stop_auto_tasks(event)

            # Clean up old event IDs from tracking sets
            # (events more than 1 hour old)
            self._cleanup_tracking_sets(now)

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
            if auto_tasks.get('enable_transcription'):
                tasks.append('实时转录')
            if auto_tasks.get('enable_recording'):
                tasks.append('会议录音')

            tasks_str = '、'.join(tasks)

            # Format start time for display
            try:
                start_dt = datetime.fromisoformat(event.start_time)
                start_time_str = start_dt.strftime('%H:%M')
            except Exception:
                start_time_str = event.start_time

            title = 'EchoNote - 事件提醒'
            message = (
                f"{event.title}\n"
                f"开始时间：{start_time_str}\n"
                f"将自动启动：{tasks_str}"
            )

            # Send desktop notification
            self.notification_manager.send_info(title, message)
            
            logger.info(
                f"Reminder notification sent for event: {event.id} - {event.title}"
            )

        except Exception as e:
            logger.error(
                f"Failed to send reminder for event {event.id}: {e}",
                exc_info=True
            )

    def _get_realtime_preferences(self) -> Dict[str, Any]:
        """Load realtime recording defaults from settings manager."""
        if self.settings_manager and hasattr(
            self.settings_manager, 'get_realtime_preferences'
        ):
            try:
                return self.settings_manager.get_realtime_preferences()
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Failed to load realtime preferences for auto tasks: %s",
                    exc,
                    exc_info=True
                )

        return {'recording_format': 'wav', 'auto_save': True}

    def _build_recording_options(self, event, auto_tasks: dict) -> Dict[str, Any]:
        """Assemble recording options for auto-started sessions."""
        preferences = self._get_realtime_preferences()

        enable_recording = auto_tasks.get('enable_recording')
        if enable_recording is None:
            save_recording = preferences.get('auto_save', True)
        else:
            save_recording = bool(enable_recording)

        options = {
            'event_id': event.id,
            'event_title': event.title,
            'language': auto_tasks.get('transcription_language'),
            'enable_translation': auto_tasks.get('enable_translation', False),
            'target_language': auto_tasks.get('translation_target_language'),
            'recording_format': preferences.get('recording_format', 'wav'),
            'save_recording': save_recording,
            'save_transcript': auto_tasks.get('enable_transcription', True),
            'create_calendar_event': False
        }

        return options

    def _start_auto_tasks(self, event, auto_tasks: dict):
        """
        Start automatic tasks for an event.

        Args:
            event: CalendarEvent instance
            auto_tasks: Dictionary of auto-task configuration
        """
        try:
            logger.info(
                f"Starting auto tasks for event: {event.id} - {event.title}"
            )

            # Check if already recording
            if self.realtime_recorder.is_recording:
                logger.warning(
                    f"Cannot start auto tasks for event {event.id}: "
                    f"recorder is already active"
                )
                # Send notification to user
                self.notification_manager.send_warning(
                    'EchoNote - 无法启动自动任务',
                    f"无法为事件 '{event.title}' 启动自动录制：\n"
                    f"录制器正在使用中"
                )
                return

            # Prepare recording options
            options = self._build_recording_options(event, auto_tasks)

            # Create a new event loop for this recording
            loop = asyncio.new_event_loop()
            
            # Define async function to start recording
            async def start_recording_async():
                await self.realtime_recorder.start_recording(
                    input_source=None,  # Use default
                    options=options,
                    event_loop=loop
                )
            
            # Start the event loop in a separate thread
            def run_loop():
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(start_recording_async())
                    # Keep loop running for background tasks
                    loop.run_forever()
                except Exception as e:
                    logger.error(f"Error in event loop: {e}", exc_info=True)
                finally:
                    loop.close()
            
            thread = threading.Thread(target=run_loop, daemon=True)
            thread.start()
            
            # Wait a bit for recording to actually start
            import time
            time.sleep(0.5)
            
            # Store recording info for later stopping
            self.active_recordings[event.id] = {
                'event': event,
                'auto_tasks': auto_tasks,
                'start_time': datetime.now(),
                'loop': loop,
                'thread': thread
            }
            
            logger.info(
                f"Successfully started auto tasks for event {event.id}"
            )
            
            # Send success notification
            self.notification_manager.send_success(
                'EchoNote - 自动任务已启动',
                f"已为事件 '{event.title}' 启动自动录制"
            )

        except Exception as e:
            logger.error(
                f"Failed to start auto tasks for event {event.id}: {e}",
                exc_info=True
            )
            
            # Send error notification
            self.notification_manager.send_error(
                'EchoNote - 自动任务启动失败',
                f"无法为事件 '{event.title}' 启动自动录制：\n{str(e)}"
            )
            # Don't raise - we want the scheduler to continue

    def _stop_auto_tasks(self, event):
        """
        Stop automatic tasks for an event and save attachments.

        Args:
            event: CalendarEvent instance
        """
        try:
            if event.id not in self.active_recordings:
                logger.debug(
                    f"No active recording for event {event.id}, skipping stop"
                )
                return

            recording_info = self.active_recordings[event.id]
            loop = recording_info.get('loop')
            thread = recording_info.get('thread')
            
            logger.info(
                f"Stopping auto tasks for event: {event.id} - {event.title}"
            )

            # Stop recording
            try:
                if loop and not loop.is_closed():
                    # Schedule stop_recording in the event loop
                    future = asyncio.run_coroutine_threadsafe(
                        self.realtime_recorder.stop_recording(),
                        loop
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
                    
                    logger.info(
                        f"Successfully stopped auto tasks for event {event.id}"
                    )
                    
                    # Send success notification
                    duration = result.get('duration', 0)
                    self.notification_manager.send_success(
                        'EchoNote - 自动录制已完成',
                        f"事件 '{event.title}' 的录制已完成\n"
                        f"录制时长：{duration:.1f} 秒"
                    )
                else:
                    logger.warning(
                        f"Event loop for event {event.id} is closed or invalid"
                    )
                    
            except Exception as e:
                logger.error(
                    f"Error stopping recording for event {event.id}: {e}",
                    exc_info=True
                )
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
            logger.error(
                f"Failed to stop auto tasks for event {event.id}: {e}",
                exc_info=True
            )
            
            # Send error notification
            self.notification_manager.send_error(
                'EchoNote - 自动录制停止失败',
                f"无法停止事件 '{event.title}' 的录制：\n{str(e)}"
            )
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
            recording_path = recording_result.get('recording_path')
            if recording_path and os.path.exists(recording_path):
                attachment = EventAttachment(
                    event_id=event_id,
                    attachment_type='recording',
                    file_path=recording_path,
                    file_size=os.path.getsize(recording_path)
                )
                attachment.save(self.db)
                logger.info(f"Saved recording attachment for event {event_id}")

            # Save transcript attachment
            transcript_path = recording_result.get('transcript_path')
            if transcript_path and os.path.exists(transcript_path):
                attachment = EventAttachment(
                    event_id=event_id,
                    attachment_type='transcript',
                    file_path=transcript_path,
                    file_size=os.path.getsize(transcript_path)
                )
                attachment.save(self.db)
                logger.info(f"Saved transcript attachment for event {event_id}")

            # Save translation attachment (if exists)
            translation_path = recording_result.get('translation_path')
            if translation_path and os.path.exists(translation_path):
                attachment = EventAttachment(
                    event_id=event_id,
                    attachment_type='translation',
                    file_path=translation_path,
                    file_size=os.path.getsize(translation_path)
                )
                attachment.save(self.db)
                logger.info(f"Saved translation attachment for event {event_id}")

        except Exception as e:
            logger.error(
                f"Failed to save attachments for event {event_id}: {e}",
                exc_info=True
            )

    def _cleanup_tracking_sets(self, now: datetime):
        """
        Clean up old event IDs from tracking sets.

        Args:
            now: Current datetime
        """
        try:
            # Get events from the past 2 hours
            timeline_data = self.timeline_manager.get_timeline_events(
                center_time=now,
                past_days=0.0833,  # ~2 hours in days
                future_days=0
            )

            past_events = timeline_data.get('past_events', [])
            recent_event_ids = {e['event'].id for e in past_events}

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
                start_time = recording_info.get('start_time')
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
                    event = recording_info.get('event')
                    if event:
                        self._stop_auto_tasks(event)
                except Exception as e:
                    logger.error(
                        f"Error force-stopping old recording {event_id}: {e}"
                    )

        except Exception as e:
            logger.error(f"Error cleaning up tracking sets: {e}", exc_info=True)
