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
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, Optional, Tuple

from apscheduler.schedulers.background import BackgroundScheduler

from config.constants import (
    DEFAULT_AUTO_STOP_GRACE_MINUTES,
    DEFAULT_REMINDER_MINUTES,
    DEFAULT_STOP_CONFIRMATION_DELAY_MINUTES,
    TIMELINE_STOP_CONFIRMATION_DELAY_MAX_MINUTES,
)
from core.realtime.integration import save_event_attachments
from core.timeline.manager import to_local_naive
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
        reminder_minutes: int = DEFAULT_REMINDER_MINUTES,
        auto_stop_grace_minutes: int = DEFAULT_AUTO_STOP_GRACE_MINUTES,
        stop_confirmation_delay_minutes: int = DEFAULT_STOP_CONFIRMATION_DELAY_MINUTES,
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
            auto_stop_grace_minutes: Grace period after event end before auto-stop
            stop_confirmation_delay_minutes: Default delay for stop confirmation
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
            initial_reminder = DEFAULT_REMINDER_MINUTES
        self._apply_reminder_minutes(initial_reminder)
        initial_stop_grace = self._coerce_auto_stop_grace_minutes(auto_stop_grace_minutes)
        if initial_stop_grace is None:
            initial_stop_grace = DEFAULT_AUTO_STOP_GRACE_MINUTES
        self._apply_auto_stop_grace_minutes(initial_stop_grace)
        initial_stop_confirmation_delay = self._coerce_stop_confirmation_delay_setting(
            stop_confirmation_delay_minutes
        )
        if initial_stop_confirmation_delay is None:
            initial_stop_confirmation_delay = DEFAULT_STOP_CONFIRMATION_DELAY_MINUTES
        self._apply_stop_confirmation_delay_minutes(initial_stop_confirmation_delay)

        # Track events that have been notified/started/stopped
        self.notified_events = set()
        self.started_events = set()
        self.active_recordings = {}  # event_id -> recording_info
        self.pending_stop_confirmations = {}  # event_id -> pending_stop_info
        self._ui_prompt_bridge = None

        # Get notification manager
        self.notification_manager = get_notification_manager()

        # Subscribe to setting changes when available
        self._subscribe_to_setting_changes()

        logger.info(
            "AutoTaskScheduler initialized (reminder: %s minutes, auto-stop grace: %s minutes, stop confirmation delay: %s minutes)",
            self.reminder_minutes,
            self.auto_stop_grace_minutes,
            self.stop_confirmation_delay_minutes,
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
                "interval",
                minutes=1,
                id="check_upcoming_events",
                replace_existing=True,
            )

            self.scheduler.start()
            self.is_running = True
            # Run one pass immediately so events that are about to start are
            # not delayed by the first scheduler tick.
            self._check_upcoming_events()
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
            self.pending_stop_confirmations.clear()

            # Shutdown scheduler
            self.scheduler.shutdown(wait=False)
            # Recreate scheduler so runtime enable/disable toggles can restart
            # background polling cleanly after a shutdown.
            self.scheduler = BackgroundScheduler()
            self.is_running = False
            logger.info("AutoTaskScheduler stopped")

        except Exception as e:
            logger.error(f"Failed to stop scheduler: {e}", exc_info=True)
            raise

    def _initialize_i18n(self, i18n_manager: Optional[I18nQtManager]) -> I18nQtManager:
        """Prepare the translation manager used for notifications."""
        if i18n_manager is not None:
            return i18n_manager

        default_language = "en_US"
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

    def _coerce_auto_stop_grace_minutes(self, value) -> Optional[int]:
        """Convert auto-stop grace minutes to a non-negative integer when possible."""
        if value is None:
            logger.info("Received None for auto-stop grace minutes; keeping previous value")
            return None

        try:
            minutes = int(value)
        except (TypeError, ValueError):
            logger.warning(
                "Invalid auto-stop grace minutes value %r; keeping previous value",
                value,
            )
            return None

        if minutes < 0:
            logger.warning("Auto-stop grace minutes %s is negative; clamping to zero", minutes)
            minutes = 0

        return minutes

    def _coerce_stop_confirmation_delay_setting(self, value) -> Optional[int]:
        """Convert stop confirmation delay to a positive integer when possible."""
        if value is None:
            logger.info("Received None for stop confirmation delay; keeping previous value")
            return None

        try:
            minutes = int(value)
        except (TypeError, ValueError):
            logger.warning(
                "Invalid stop confirmation delay value %r; keeping previous value",
                value,
            )
            return None

        if minutes < 1:
            logger.warning("Stop confirmation delay %s is invalid; clamping to 1", minutes)
            minutes = 1

        return min(minutes, TIMELINE_STOP_CONFIRMATION_DELAY_MAX_MINUTES)

    @staticmethod
    def _coerce_auto_start_enabled(value) -> Optional[bool]:
        """Coerce auto-start preference values to booleans when possible."""
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"1", "true", "yes", "on"}:
                return True
            if normalized in {"0", "false", "no", "off"}:
                return False
            return None
        if value is None:
            return None
        return bool(value)

    @staticmethod
    def _auto_tasks_enabled(auto_tasks: Optional[dict]) -> bool:
        """Return whether any auto-start action is enabled for an event."""
        if not auto_tasks:
            return False
        return bool(auto_tasks.get("enable_transcription") or auto_tasks.get("enable_recording"))

    def _apply_reminder_minutes(self, minutes: int) -> None:
        """Persist reminder minutes and refresh dependent time windows."""
        self.reminder_minutes = minutes
        from config.constants import (
            MIN_FUTURE_WINDOW_MINUTES,
            MIN_REMINDER_WINDOW_MINUTES,
            REMINDER_FUTURE_WINDOW_OFFSET_MINUTES,
        )

        self._past_window_minutes = max(minutes, MIN_REMINDER_WINDOW_MINUTES)
        self._future_window_minutes = max(
            minutes + REMINDER_FUTURE_WINDOW_OFFSET_MINUTES, MIN_FUTURE_WINDOW_MINUTES
        )

    def _apply_auto_stop_grace_minutes(self, minutes: int) -> None:
        """Persist auto-stop grace period settings for runtime checks."""
        self.auto_stop_grace_minutes = minutes
        self._auto_stop_grace_seconds = minutes * 60

    def _apply_stop_confirmation_delay_minutes(self, minutes: int) -> None:
        """Persist default stop confirmation delay minutes."""
        self.stop_confirmation_delay_minutes = minutes

    def _auto_start_recovery_window_seconds(self) -> int:
        """Return late-start recovery window based on reminder settings."""
        reminder_seconds = max(self.reminder_minutes, 0) * 60
        return max(60, reminder_seconds)

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
        """React to timeline preference updates at runtime."""
        if key == "timeline.reminder_minutes":
            minutes = self._coerce_reminder_minutes(value)
            if minutes is None or minutes == self.reminder_minutes:
                return

            self._apply_reminder_minutes(minutes)
            self.notified_events.clear()
            logger.info("Reminder minutes updated to %s via settings change", minutes)
            return

        if key == "timeline.auto_stop_grace_minutes":
            minutes = self._coerce_auto_stop_grace_minutes(value)
            if minutes is None or minutes == self.auto_stop_grace_minutes:
                return

            self._apply_auto_stop_grace_minutes(minutes)
            logger.info("Auto-stop grace minutes updated to %s via settings change", minutes)
            return

        if key == "timeline.stop_confirmation_delay_minutes":
            minutes = self._coerce_stop_confirmation_delay_setting(value)
            if minutes is None or minutes == self.stop_confirmation_delay_minutes:
                return

            self._apply_stop_confirmation_delay_minutes(minutes)
            logger.info("Stop confirmation delay updated to %s via settings change", minutes)
            return

        if key == "timeline.auto_start_enabled":
            enabled = self._coerce_auto_start_enabled(value)
            if enabled is None:
                logger.warning("Ignoring invalid timeline.auto_start_enabled value: %r", value)
                return

            if enabled and not self.is_running:
                logger.info("Enabling auto task scheduler via settings change")
                self.start()
            elif not enabled and self.is_running:
                logger.info("Disabling auto task scheduler via settings change")
                self.stop()

    def _check_upcoming_events(self):
        """
        Check for upcoming events and handle notifications/auto-start/auto-stop.

        This method is called every minute by the scheduler.
        """
        now_local = to_local_naive(datetime.now().astimezone())

        try:
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
                if not self._auto_tasks_enabled(auto_tasks):
                    continue

                event_start = to_local_naive(event.start_time)
                time_until_start = (event_start - now_local).total_seconds()

                # Send reminder N minutes before event
                reminder_seconds = self.reminder_minutes * 60
                if (
                    reminder_seconds > 0
                    and 0 < time_until_start <= reminder_seconds
                    and event.id not in self.notified_events
                ):
                    self._send_reminder_notification(event, auto_tasks)
                    self.notified_events.add(event.id)

                # Start auto tasks when event begins
                # (within 1 minute of start time)
                if 0 <= time_until_start <= 60 and event.id not in self.started_events:
                    started = self._start_auto_tasks(event, auto_tasks)
                    if started:
                        self.started_events.add(event.id)

            # Process past events (stop recordings and recover starts missed by
            # scheduler drift/app startup).
            for event_data in past_events:
                event = event_data["event"]
                event_start, event_end = self._resolve_event_window(event)

                # Stop checks are handled centrally via active_recordings so we
                # do not rely on the timeline query window to include long events.
                if event.id in self.active_recordings:
                    continue

                if event.id in self.started_events:
                    continue

                # If polling runs slightly late and the event has just started,
                # recover within a short grace period.
                if event_start <= now_local < event_end:
                    time_since_start = (now_local - event_start).total_seconds()
                    recovery_window_seconds = self._auto_start_recovery_window_seconds()
                    if 0 <= time_since_start <= recovery_window_seconds:
                        auto_tasks = self.timeline_manager.get_auto_task(event.id) or {}
                        if self._auto_tasks_enabled(auto_tasks):
                            started = self._start_auto_tasks(event, auto_tasks)
                            if started:
                                self.started_events.add(event.id)

        except Exception as e:
            logger.error(f"Error checking upcoming events: {e}", exc_info=True)
        finally:
            self._check_active_recordings_for_stop(now_local)
            # Clean up old event IDs from tracking sets
            # (events more than 1 hour old)
            self._cleanup_tracking_sets(now_local)

    def _get_latest_event_for_recording(self, event_id: str, fallback_event):
        """Return the freshest event snapshot for active recording stop checks."""
        calendar_manager = getattr(self.timeline_manager, "calendar_manager", None)
        if calendar_manager is None:
            return fallback_event

        get_event = getattr(calendar_manager, "get_event", None)
        if not callable(get_event):
            return fallback_event

        try:
            latest_event = get_event(event_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to refresh event %s for auto-stop: %s", event_id, exc)
            return fallback_event

        if latest_event is None:
            return fallback_event

        return latest_event

    def _check_active_recordings_for_stop(self, now_local: datetime) -> None:
        """Stop active recordings when event end + grace period has elapsed."""
        for event_id in list(self.active_recordings.keys()):
            recording_info = self.active_recordings.get(event_id)
            if not recording_info:
                continue

            try:
                event = recording_info.get("event")
                if event is None:
                    logger.warning(
                        "Active recording %s has no event metadata; skipping auto-stop check",
                        event_id,
                    )
                    continue

                latest_event = self._get_latest_event_for_recording(event_id, event)
                if latest_event is not event:
                    recording_info["event"] = latest_event
                    event = latest_event

                event_start, event_end = self._resolve_event_window(event)

                stop_deadline = event_end + timedelta(seconds=self._auto_stop_grace_seconds)
                if now_local < stop_deadline:
                    self.pending_stop_confirmations.pop(event_id, None)
                    continue

                pending_info = self.pending_stop_confirmations.get(event_id)
                if pending_info:
                    next_prompt_at = pending_info.get("next_prompt_at", stop_deadline)
                    if now_local < next_prompt_at:
                        continue

                decision = self._prompt_stop_confirmation(event)
                if decision.get("action") == "stop":
                    self.pending_stop_confirmations.pop(event_id, None)
                    self._stop_auto_tasks(event)
                    continue

                delay_minutes = self._coerce_stop_confirmation_delay_minutes(
                    decision.get("delay_minutes")
                )
                next_prompt_at = now_local + timedelta(minutes=delay_minutes)
                self.pending_stop_confirmations[event_id] = {
                    "next_prompt_at": next_prompt_at,
                }
                self._send_delayed_stop_notification(event, delay_minutes, next_prompt_at)
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    "Failed to evaluate auto-stop for event %s: %s",
                    event_id,
                    exc,
                    exc_info=True,
                )

    def _coerce_stop_confirmation_delay_minutes(self, value) -> int:
        """Normalize delay confirmation minutes to supported range."""
        minutes = self._coerce_stop_confirmation_delay_setting(value)
        if minutes is None:
            return self.stop_confirmation_delay_minutes
        return minutes

    def _prompt_stop_confirmation(self, event) -> Dict[str, Any]:
        """Ask user whether to stop now or postpone the stop prompt."""
        default_delay = self.stop_confirmation_delay_minutes
        result, error = self._run_ui_callable(
            lambda: self._show_stop_confirmation_dialog(event, default_delay),
            timeout_seconds=180,
        )
        if error is not None:
            logger.warning(
                "Stop confirmation dialog unavailable for event %s, falling back to delay: %s",
                event.id,
                error,
            )
            return {
                "action": "delay",
                "delay_minutes": default_delay,
            }

        if not isinstance(result, dict):
            return {
                "action": "delay",
                "delay_minutes": default_delay,
            }

        action = result.get("action")
        if action == "stop":
            return {"action": "stop"}

        return {
            "action": "delay",
            "delay_minutes": self._coerce_stop_confirmation_delay_minutes(
                result.get("delay_minutes")
            ),
        }

    def _show_stop_confirmation_dialog(self, event, default_delay_minutes: int) -> Dict[str, Any]:
        """Render stop confirmation dialog in UI thread and return decision."""
        from PySide6.QtWidgets import QApplication, QInputDialog, QMessageBox

        app_name = self.i18n.t("app.name")
        dialog_title = self.i18n.t("auto_task.stop_confirmation.title", app_name=app_name)
        dialog_message = self.i18n.t("auto_task.stop_confirmation.message", event_title=event.title)
        parent = QApplication.activeWindow()

        box = QMessageBox(parent)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle(dialog_title)
        box.setText(dialog_message)

        stop_now_btn = box.addButton(
            self.i18n.t("auto_task.stop_confirmation.stop_now"),
            QMessageBox.ButtonRole.AcceptRole,
        )
        delay_default_btn = box.addButton(
            self.i18n.t(
                "auto_task.stop_confirmation.delay_default",
                minutes=str(default_delay_minutes),
            ),
            QMessageBox.ButtonRole.ActionRole,
        )
        delay_custom_btn = box.addButton(
            self.i18n.t("auto_task.stop_confirmation.delay_custom"),
            QMessageBox.ButtonRole.ActionRole,
        )
        cancel_btn = box.addButton(
            self.i18n.t("common.cancel"),
            QMessageBox.ButtonRole.RejectRole,
        )
        box.setDefaultButton(delay_default_btn)
        box.exec()

        clicked = box.clickedButton()
        if clicked == stop_now_btn:
            return {"action": "stop"}
        if clicked == delay_custom_btn:
            custom_title = self.i18n.t("auto_task.stop_confirmation.custom_delay_title")
            custom_label = self.i18n.t("auto_task.stop_confirmation.custom_delay_label")
            minutes, ok = QInputDialog.getInt(
                parent,
                custom_title,
                custom_label,
                default_delay_minutes,
                1,
                TIMELINE_STOP_CONFIRMATION_DELAY_MAX_MINUTES,
            )
            if ok:
                return {"action": "delay", "delay_minutes": minutes}
        if clicked == delay_default_btn or clicked == cancel_btn:
            return {"action": "delay", "delay_minutes": default_delay_minutes}
        return {"action": "delay", "delay_minutes": default_delay_minutes}

    def _run_ui_callable(
        self,
        callback: Callable[[], Dict[str, Any]],
        timeout_seconds: int = 60,
    ) -> Tuple[Optional[Dict[str, Any]], Optional[Exception]]:
        """Execute callback on UI thread and wait for completion."""
        try:
            from PySide6.QtCore import QObject, Signal, Slot
            from PySide6.QtWidgets import QApplication
        except Exception as exc:  # noqa: BLE001
            return None, exc

        app = QApplication.instance()
        if app is None:
            return None, RuntimeError("QApplication is not initialized")

        if self._ui_prompt_bridge is None:

            class _UiPromptBridge(QObject):
                run_requested = Signal(object)

                def __init__(self):
                    super().__init__()
                    self.run_requested.connect(self._run)

                @Slot(object)
                def _run(self, payload):
                    try:
                        payload["result"]["value"] = payload["callback"]()
                    except Exception as callback_exc:  # noqa: BLE001
                        payload["result"]["error"] = callback_exc
                    finally:
                        payload["done"].set()

            self._ui_prompt_bridge = _UiPromptBridge()
            self._ui_prompt_bridge.moveToThread(app.thread())

        result: Dict[str, Any] = {}
        done = threading.Event()
        payload = {
            "callback": callback,
            "done": done,
            "result": result,
        }
        self._ui_prompt_bridge.run_requested.emit(payload)
        if not done.wait(timeout_seconds):
            return None, TimeoutError("Timed out waiting for UI prompt response")

        if "error" in result:
            callback_error = result["error"]
            if isinstance(callback_error, Exception):
                return None, callback_error
            return None, RuntimeError(str(callback_error))

        return result.get("value"), None

    def _send_delayed_stop_notification(
        self,
        event,
        delay_minutes: int,
        next_prompt_at: datetime,
    ) -> None:
        """Inform user that stop has been deferred and will be confirmed again."""
        title = self.i18n.t("auto_task.stop_confirmation.delayed_title", app_name=self.i18n.t("app.name"))
        message = self.i18n.t(
            "auto_task.stop_confirmation.delayed_message",
            event_title=event.title,
            delay_minutes=str(delay_minutes),
            next_time=next_prompt_at.strftime("%H:%M"),
        )
        self.notification_manager.send_info(title, message)

    @staticmethod
    def _resolve_event_window(event) -> Tuple[datetime, datetime]:
        """Normalize event start/end times into a safe local-naive window."""
        event_start = to_local_naive(event.start_time)
        event_end_raw = getattr(event, "end_time", None) or event.start_time
        try:
            event_end = to_local_naive(event_end_raw)
        except Exception:
            event_end = event_start

        if event_end < event_start:
            event_start, event_end = event_end, event_start

        return event_start, event_end

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

        return {
            "recording_format": "wav",
            "auto_save": True,
            "translation_engine": "google",
            "vad_threshold": 0.5,
            "silence_duration_ms": 2000,
            "min_audio_duration": 3.0,
            "save_transcript": True,
        }

    def _build_recording_options(self, event, auto_tasks: dict) -> Dict[str, Any]:
        """Assemble recording options for auto-started sessions."""
        preferences = self._get_realtime_preferences()

        enable_recording = auto_tasks.get("enable_recording")
        if enable_recording is None:
            save_recording = preferences.get("auto_save", True)
        else:
            save_recording = bool(enable_recording)

        enable_transcription = auto_tasks.get("enable_transcription")
        if enable_transcription is None:
            enable_transcription = bool(preferences.get("save_transcript", True))
        else:
            enable_transcription = bool(enable_transcription)

        save_transcript = bool(preferences.get("save_transcript", True) and enable_transcription)

        translation_globally_enabled = preferences.get("translation_engine", "google") != "none"
        translation_runtime_available = self._translation_engine_available()
        enable_translation = bool(
            enable_transcription
            and auto_tasks.get("enable_translation", False)
            and translation_globally_enabled
            and translation_runtime_available
        )

        options = {
            "event_id": event.id,
            "event_title": event.title,
            "language": auto_tasks.get("transcription_language"),
            "enable_transcription": enable_transcription,
            "enable_translation": enable_translation,
            "target_language": auto_tasks.get("translation_target_language") or "en",
            "recording_format": preferences.get("recording_format", "wav"),
            "save_recording": save_recording,
            "save_transcript": save_transcript,
            "vad_threshold": float(preferences.get("vad_threshold", 0.5)),
            "silence_duration_ms": int(preferences.get("silence_duration_ms", 2000)),
            "min_audio_duration": float(preferences.get("min_audio_duration", 3.0)),
            "create_calendar_event": False,
        }

        return options

    def _translation_engine_available(self) -> bool:
        """Return whether realtime recorder currently has a usable translation engine."""
        engine = getattr(self.realtime_recorder, "translation_engine", None)
        if engine is None:
            return False

        try:
            return bool(engine)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to evaluate translation engine availability: %s", exc)
            return False

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
        should_remove_active_state = False
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
                    should_remove_active_state = True

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
                    should_remove_active_state = True

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
                should_remove_active_state = True
                raise

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
        finally:
            # Always clear stale in-memory tracking when a stop was attempted.
            if should_remove_active_state:
                self.active_recordings.pop(event.id, None)
                self.started_events.discard(event.id)
                self.pending_stop_confirmations.pop(event.id, None)

    def _save_event_attachments(self, event_id: str, recording_result: Dict[str, Any]):
        """
        Save recording and transcript as event attachments.

        Args:
            event_id: Event ID
            recording_result: Result from stop_recording()
        """
        try:
            save_event_attachments(self.db, event_id, recording_result)
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

            active_event_ids = set(self.active_recordings.keys())
            stale_pending_ids = [
                event_id
                for event_id in self.pending_stop_confirmations
                if event_id not in active_event_ids
            ]
            for event_id in stale_pending_ids:
                self.pending_stop_confirmations.pop(event_id, None)

        except Exception as e:
            logger.error(f"Error cleaning up tracking sets: {e}", exc_info=True)
