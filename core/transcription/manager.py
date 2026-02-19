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
Transcription manager for batch audio file processing.

Manages transcription tasks, coordinates speech engines, and handles
task lifecycle from creation to completion.
"""

import asyncio
import concurrent.futures
import json
import logging
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from config.app_config import get_app_dir
from core.transcription.format_converter import FormatConverter
from core.transcription.task_queue import TaskQueue, TaskStatus
from data.database.connection import DatabaseConnection
from data.database.models import TranscriptionTask
from engines.speech.base import AUDIO_VIDEO_SUFFIXES, SpeechEngine
from ui.common.notification import get_notification_manager

logger = logging.getLogger("echonote.transcription.manager")


class TaskNotFoundError(Exception):
    """Raised when a transcription task cannot be found."""

    pass


class TranscriptionManager:
    """
    Manages transcription tasks and coordinates speech engine processing.

    Handles task creation, queue management, progress tracking, and
    result export for batch audio transcription.
    """

    def __init__(
        self,
        db_connection: DatabaseConnection,
        speech_engine: SpeechEngine,
        config: Optional[Dict[str, Any]] = None,
        *,
        i18n: Optional[Any] = None,
        translate: Optional[Callable[..., str]] = None,
    ):
        """
        Initialize transcription manager.

        Args:
            db_connection: Database connection instance
            speech_engine: Speech recognition engine instance
            config: Transcription configuration dictionary
        """
        self.db = db_connection
        self.speech_engine = speech_engine
        self.config = config or {}

        self._translator: Optional[Callable[..., str]] = None
        if translate and callable(translate):
            self._translator = translate
        elif i18n is not None:
            translate_method = getattr(i18n, "t", None)
            if callable(translate_method):
                self._translator = translate_method

        self._default_save_path: Optional[str] = None
        raw_default_path = self.config.get("default_save_path")
        if isinstance(raw_default_path, (str, os.PathLike)) and raw_default_path:
            try:
                default_path = Path(raw_default_path).expanduser()
                default_path = default_path.resolve()
                default_path.mkdir(parents=True, exist_ok=True)
                try:
                    os.chmod(default_path, 0o700)
                except Exception as permission_error:
                    logger.warning(
                        f"Could not set directory permissions for default save path "
                        f"{default_path}: {permission_error}"
                    )
                self._default_save_path = str(default_path)
            except Exception as exc:
                logger.error(
                    f"Failed to prepare default save path '{raw_default_path}': {exc}",
                    exc_info=True,
                )
        elif raw_default_path:
            logger.warning(
                f"Ignoring default_save_path with unsupported type: {type(raw_default_path).__name__}"
            )

        task_queue_config = self.config.get("task_queue", {})
        if not isinstance(task_queue_config, dict):
            task_queue_config = {}

        def _resolve_queue_setting(key: str, fallback: Any) -> Any:
            if key in task_queue_config:
                return task_queue_config[key]
            if key in self.config:
                return self.config[key]
            return fallback

        # Initialize task queue
        max_concurrent = _resolve_queue_setting("max_concurrent_tasks", 2)
        max_retries = _resolve_queue_setting("max_retries", 3)
        retry_delay = _resolve_queue_setting("retry_delay", 1.0)
        self.task_queue = TaskQueue(
            max_concurrent=max_concurrent, max_retries=max_retries, retry_delay=retry_delay
        )

        from config.constants import DEFAULT_OUTPUT_FORMAT
        self._default_output_format = self.config.get("default_output_format", DEFAULT_OUTPUT_FORMAT)

        # Initialize format converter
        self.format_converter = FormatConverter()

        # Progress callbacks (task_id -> callback function)
        self.progress_callbacks: Dict[str, callable] = {}

        # Global event listeners
        self.event_listeners: List[Callable[[str, Dict[str, Any]], None]] = []

        # Background thread and event loop for additional async operations
        self._loop = None
        self._thread = None
        self._running = False

        # Queue scheduling buffer for tasks added before loop starts
        self._queue_buffer_lock = threading.Lock()
        self._pending_queue_entries: Dict[str, Tuple[Callable, tuple, dict]] = {}
        self._task_engine_options: Dict[str, Dict[str, Any]] = {}
        self._task_engine_options_path = get_app_dir() / "task_engine_options.json"
        self._load_persisted_task_engine_options()

        logger.info(
            f"Transcription manager initialized with engine: " f"{speech_engine.get_name()}"
        )

    def add_listener(self, callback: Callable[[str, Dict[str, Any]], None]):
        """
        Register a global event listener.
        
        Args:
            callback: Function(event_type: str, data: dict)
        """
        if callback not in self.event_listeners:
            self.event_listeners.append(callback)
            
    def remove_listener(self, callback: Callable[[str, Dict[str, Any]], None]):
        """
        Unregister a global event listener.
        
        Args:
            callback: Function to remove
        """
        if callback in self.event_listeners:
            self.event_listeners.remove(callback)
            
    def _notify_listeners(self, event_type: str, data: Dict[str, Any]):
        """
        Notify all listeners of an event.
        
        Args:
            event_type: Type of event (task_added, task_updated, task_deleted)
            data: Event data
        """
        for listener in self.event_listeners:
            try:
                listener(event_type, data)
            except Exception as e:
                logger.error(f"Error in event listener: {e}")

    def _load_persisted_task_engine_options(self) -> None:
        """Load task engine options persisted on disk."""
        try:
            if not self._task_engine_options_path.exists():
                return
            with open(self._task_engine_options_path, "r", encoding="utf-8") as handle:
                raw_data = json.load(handle)
            if isinstance(raw_data, dict):
                self._task_engine_options = {
                    str(task_id): value
                    for task_id, value in raw_data.items()
                    if isinstance(value, dict)
                }
        except Exception as exc:
            logger.warning("Failed to load persisted task engine options: %s", exc, exc_info=True)
            self._task_engine_options = {}

    def _persist_task_engine_options(self) -> None:
        """Persist task engine options to disk for restart recovery."""
        try:
            self._task_engine_options_path.parent.mkdir(parents=True, exist_ok=True)
            if not self._task_engine_options:
                if self._task_engine_options_path.exists():
                    self._task_engine_options_path.unlink()
                return

            with open(self._task_engine_options_path, "w", encoding="utf-8") as handle:
                json.dump(self._task_engine_options, handle, ensure_ascii=False, indent=2)
            try:
                os.chmod(self._task_engine_options_path, 0o600)
            except Exception:
                pass
        except Exception as exc:
            logger.warning("Failed to persist task engine options: %s", exc, exc_info=True)

    def _store_task_for_later(self, task_id: str, task_func, *args, **kwargs) -> None:
        """Cache tasks until the background event loop is ready."""
        with self._queue_buffer_lock:
            self._pending_queue_entries[task_id] = (task_func, args, kwargs)

        logger.debug(f"Cached task {task_id} for later scheduling")

        # If the loop is already running, schedule a flush
        self._schedule_buffer_flush_if_running()

    def _pop_buffered_tasks(self) -> List[Tuple[str, Tuple[Callable, tuple, dict]]]:
        """Retrieve and clear buffered tasks."""
        with self._queue_buffer_lock:
            buffered = list(self._pending_queue_entries.items())
            self._pending_queue_entries.clear()
        return buffered

    def _schedule_buffer_flush_if_running(self) -> None:
        """Schedule buffered tasks to be enqueued if the loop is active."""
        if not self._loop or not self._loop.is_running():
            return

        import asyncio

        asyncio.run_coroutine_threadsafe(self._drain_buffered_tasks(), self._loop)

    def _queue_or_buffer_task(self, task_id: str) -> bool:
        """Queue the task immediately if possible, otherwise cache it."""
        if self._loop and self._loop.is_running():
            import asyncio

            try:
                asyncio.run_coroutine_threadsafe(
                    self.task_queue.add_task(task_id, self._process_task_async, task_id), self._loop
                )
                return True
            except RuntimeError as exc:
                logger.warning(f"Event loop not ready for task {task_id}: {exc}. Caching for later")

        self._store_task_for_later(task_id, self._process_task_async, task_id)
        return False

    async def _drain_buffered_tasks(self) -> None:
        """Add all buffered tasks to the async queue."""
        buffered_tasks = self._pop_buffered_tasks()
        if not buffered_tasks:
            return

        for task_id, (task_func, args, kwargs) in buffered_tasks:
            try:
                await self.task_queue.add_task(task_id, task_func, *args, **kwargs)
                logger.info(f"Task {task_id} scheduled from buffer")
            except Exception as exc:
                logger.error(f"Failed to schedule buffered task {task_id}: {exc}", exc_info=True)

    def add_task(self, file_path: str, options: Optional[Dict[str, Any]] = None) -> str:
        """
        Add a transcription task for a single file.

        Args:
            file_path: Path to audio/video file
            options: Optional task options:
                - language: Source language code
                - output_format: Output format (txt/srt/md)
                - output_path: Custom output path

        Returns:
            Task ID

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If file format is not supported
        """
        options = options or {}
        engine_option_keys = {
            "model_name",
            "model_path",
            "beam_size",
            "vad_filter",
            "vad_min_silence_duration_ms",
            "prompt",
            "temperature",
        }

        # Validate file exists
        file_path = Path(file_path).expanduser().resolve()
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # Validate file format
        if file_path.suffix.lower() not in AUDIO_VIDEO_SUFFIXES:
            raise ValueError(
                f"Unsupported file format: {file_path.suffix}. "
                f"Supported formats: {', '.join(sorted(AUDIO_VIDEO_SUFFIXES))}"
            )

        # Create task record
        from config.constants import TASK_STATUS_PENDING

        task = TranscriptionTask(
            file_path=str(file_path),
            file_name=file_path.name,
            file_size=file_path.stat().st_size,
            status=TASK_STATUS_PENDING,
            language=options.get("language"),
            engine=self.speech_engine.get_name(),
            output_format=options.get("output_format", self._default_output_format),
            output_path=options.get("output_path"),
        )

        # Save to database
        task.save(self.db)

        # Store engine-only options in memory for runtime execution.
        # These options are not persisted in DB schema.
        engine_options = {key: options[key] for key in engine_option_keys if key in options}
        if engine_options:
            self._task_engine_options[task.id] = engine_options
            self._persist_task_engine_options()

        if not self._queue_or_buffer_task(task.id):
            logger.info(f"Task queue not ready, task {task.id} cached until processing starts")

        # Notify listeners
        self._notify_listeners(
            "task_added",
            {
                "id": task.id,
                "file_name": task.file_name,
                "status": task.status,
                "created_at": task.created_at,
            },
        )

        logger.info(f"Added transcription task: {task.id} for file {file_path.name}")
        return task.id

    def add_tasks_from_folder(
        self, folder_path: str, options: Optional[Dict[str, Any]] = None
    ) -> List[str]:
        """
        Add transcription tasks for all supported files in a folder.

        Args:
            folder_path: Path to folder containing audio/video files
            options: Optional task options (applied to all files)

        Returns:
            List of task IDs

        Raises:
            NotADirectoryError: If path is not a directory
        """
        folder_path = Path(folder_path).expanduser().resolve()
        if not folder_path.is_dir():
            raise NotADirectoryError(f"Not a directory: {folder_path}")

        task_ids = []

        # Recursively find all supported audio/video files
        for file_path in folder_path.rglob("*"):
            if file_path.is_file() and file_path.suffix.lower() in AUDIO_VIDEO_SUFFIXES:
                try:
                    task_id = self.add_task(str(file_path), options)
                    task_ids.append(task_id)
                except Exception as e:
                    logger.error(f"Failed to add task for {file_path}: {e}")

        logger.info(f"Added {len(task_ids)} transcription tasks from folder {folder_path}")
        return task_ids

    def start_processing(self):
        """Start processing tasks from the queue in a background thread."""
        if self._running:
            logger.warning("Transcription processing already running")
            return

        # Requeue tasks persisted in the database before starting the loop
        try:
            rows = self.db.execute(
                "SELECT id, status FROM transcription_tasks "
                "WHERE status IN ('pending', 'processing') "
                "ORDER BY created_at ASC"
            )
        except Exception as exc:
            logger.error(f"Failed to load tasks for restart: {exc}", exc_info=True)
            rows = []

        if rows:
            active_task_ids = {row["id"] for row in rows}
            stale_option_ids = set(self._task_engine_options.keys()) - active_task_ids
            if stale_option_ids:
                for stale_id in stale_option_ids:
                    self._task_engine_options.pop(stale_id, None)
                self._persist_task_engine_options()

            processing_ids = [row["id"] for row in rows if row["status"] == "processing"]

            if processing_ids:
                try:
                    self.db.execute_many(
                        "UPDATE transcription_tasks "
                        "SET status = 'pending', progress = 0, started_at = NULL "
                        "WHERE id = ?",
                        [(task_id,) for task_id in processing_ids],
                    )
                    logger.info(f"Reset {len(processing_ids)} tasks stuck in processing state")
                except Exception as exc:
                    logger.error(
                        f"Failed to reset processing tasks before restart: {exc}", exc_info=True
                    )

            for row in rows:
                # Ensure any stale queue state is removed before re-adding
                self.task_queue.tasks.pop(row["id"], None)
                self._store_task_for_later(row["id"], self._process_task_async, row["id"])

            logger.info(f"Queued {len(rows)} persisted tasks for background processing")

        def run_event_loop():
            """Run event loop in background thread."""
            import asyncio

            # Create new event loop for this thread
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)

            try:
                # Start task queue
                self._loop.run_until_complete(self.task_queue.start())

                # Schedule buffered tasks gathered before the loop started
                self._loop.create_task(self._drain_buffered_tasks())

                # Keep loop running
                self._loop.run_forever()

            except Exception as e:
                logger.error(f"Error in transcription event loop: {e}")
            finally:
                # Clean up
                loop = self._loop
                shutdown_error = None

                if loop and not loop.is_closed():
                    for attempt in range(1, 3):
                        try:
                            loop.run_until_complete(self.task_queue.stop())
                            shutdown_error = None
                            break
                        except Exception as exc:
                            shutdown_error = exc
                            logger.error(
                                "Task queue stop attempt %d failed: %s",
                                attempt,
                                exc,
                                exc_info=True,
                            )

                            pending_tasks = [
                                task for task in asyncio.all_tasks(loop=loop) if not task.done()
                            ]

                            if pending_tasks:
                                for task in pending_tasks:
                                    task.cancel()

                                try:
                                    loop.run_until_complete(
                                        asyncio.gather(
                                            *pending_tasks,
                                            return_exceptions=True,
                                        )
                                    )
                                except Exception as gather_exc:
                                    logger.error(
                                        "Error while awaiting cancelled tasks during shutdown: %s",
                                        gather_exc,
                                        exc_info=True,
                                    )

                            if attempt == 2:
                                logger.error(
                                    "Task queue stop failed after %d attempts; proceeding with forced shutdown",
                                    attempt,
                                )

                    self.task_queue.running = False
                    self.task_queue.worker_tasks = []

                if loop and not loop.is_closed():
                    try:
                        loop.close()
                    except Exception as loop_exc:
                        logger.error(
                            "Error closing transcription event loop: %s",
                            loop_exc,
                            exc_info=True,
                        )

                self._loop = None
                self._running = False

                if shutdown_error:
                    logger.warning("Transcription event loop closed with prior shutdown errors")

                logger.info("Transcription event loop closed")

        # Start background thread
        self._running = True
        self._thread = threading.Thread(target=run_event_loop, daemon=True)
        self._thread.start()

        logger.info("Started transcription task processing in background thread")

    def stop_processing(self):
        """Stop processing tasks."""
        if not self._running:
            return

        self._running = False

        if self._loop and self._loop.is_running():
            try:
                stop_future = asyncio.run_coroutine_threadsafe(self.task_queue.stop(), self._loop)
                stop_future.result(timeout=5.0)
            except Exception as exc:
                logger.warning("Failed to stop task queue gracefully: %s", exc)
            finally:
                # Stop the event loop
                self._loop.call_soon_threadsafe(self._loop.stop)

        if self._thread:
            # Wait for thread to finish (with timeout)
            self._thread.join(timeout=5.0)
            if not self._thread.is_alive():
                self._thread = None

        logger.info("Stopped transcription task processing")

    def pause_processing(self):
        """
        Pause processing new tasks (current tasks continue).

        This is useful when system resources are low.
        """
        if not self._running:
            logger.warning("Cannot pause: processing not running")
            return

        if self._loop:
            # Pause the task queue (stop accepting new tasks)
            future = asyncio.run_coroutine_threadsafe(self.task_queue.pause(), self._loop)
            try:
                future.result(timeout=2.0)
                # Notify listeners
                self._notify_listeners("processing_paused", {})
                logger.info("Paused transcription task processing")
            except Exception as e:
                logger.error(f"Error pausing task queue: {e}")

    def resume_processing(self):
        """
        Resume processing tasks after pause.
        """
        if not self._running:
            logger.warning("Cannot resume: processing not running")
            return

        if self._loop:
            # Resume the task queue
            future = asyncio.run_coroutine_threadsafe(self.task_queue.resume(), self._loop)
            try:
                future.result(timeout=2.0)
                # Notify listeners
                self._notify_listeners("processing_resumed", {})
                logger.info("Resumed transcription task processing")
            except Exception as e:
                logger.error(f"Error resuming task queue: {e}")

    def is_paused(self) -> bool:
        """Check if task processing is paused."""
        return self.task_queue.is_paused() if self._running else False

    def _get_runtime_processing_task_count(self) -> Optional[int]:
        """
        Return processing task count from in-memory queue state.

        Returns:
            Processing task count when runtime state is available, otherwise None.
        """
        if not self._running or not hasattr(self.task_queue, "tasks"):
            return None

        try:
            count = 0
            for task_info in self.task_queue.tasks.values():
                status = task_info.get("status")
                status_value = status.value if isinstance(status, TaskStatus) else str(status)
                if status_value == TaskStatus.PROCESSING.value:
                    count += 1
            return count
        except Exception as exc:
            logger.debug("Failed to read runtime task state: %s", exc)
            return None

    def _get_persisted_processing_task_count(self) -> int:
        """Return processing task count from persistent storage."""
        result = self.db.execute(
            "SELECT COUNT(*) as count FROM transcription_tasks WHERE status = 'processing'"
        )
        if result and len(result) > 0:
            return int(result[0]["count"])
        return 0

    def get_active_task_count(self) -> int:
        """
        Get active transcription task count.

        Returns:
            Number of tasks currently processing.
        """
        runtime_count = self._get_runtime_processing_task_count()
        if runtime_count is not None:
            return max(runtime_count, 0)

        try:
            return max(self._get_persisted_processing_task_count(), 0)
        except Exception as e:
            logger.error(f"Error getting active task count: {e}")
            return 0

    def has_running_tasks(self) -> bool:
        """
        Check if there are any running tasks.

        Returns:
            True if there are tasks in processing status
        """
        return self.get_active_task_count() > 0

    def stop_all_tasks(self):
        """
        Stop all running tasks gracefully.

        This method cancels all pending tasks and waits for
        current tasks to complete (with timeout).
        """
        try:
            logger.info("Stopping all transcription tasks...")

            # Get all pending and processing tasks
            pending_tasks = self.db.execute(
                "SELECT id FROM transcription_tasks " "WHERE status IN ('pending', 'processing')"
            )

            if pending_tasks:
                logger.info(f"Found {len(pending_tasks)} tasks to stop")

                # Cancel each task
                for task_row in pending_tasks:
                    task_id = task_row["id"]
                    try:
                        self.cancel_task(task_id)
                    except Exception as e:
                        logger.error(f"Error cancelling task {task_id}: {e}")

            # Stop processing
            self.stop_processing()

            logger.info("All transcription tasks stopped")

        except Exception as e:
            logger.error(f"Error stopping all tasks: {e}")

    async def _process_task_async(self, task_id: str, *, cancel_event: asyncio.Event):
        """
        Process a single transcription task (async wrapper).

        Args:
            task_id: Task identifier
            cancel_event: Event to check for cancellation
        """
        task: Optional[TranscriptionTask] = None

        def ensure_not_cancelled(stage: str) -> None:
            if cancel_event.is_set():
                logger.info(
                    "Cancellation detected for task %s %s",
                    task_id,
                    stage,
                )
                raise asyncio.CancelledError()

        try:
            ensure_not_cancelled("before loading task from database")

            # Load task from database
            task = TranscriptionTask.get_by_id(self.db, task_id)
            if not task:
                raise TaskNotFoundError(f"Task {task_id} not found in database")

            ensure_not_cancelled("after loading task from database")

            # Update status to processing
            from config.constants import TASK_STATUS_PROCESSING
            task.status = TASK_STATUS_PROCESSING
            task.started_at = datetime.now().isoformat()
            task.progress = 0.0
            task.save(self.db)

            # Notify progress: started
            self._update_progress(task_id, 0.0, "Starting transcription")

            logger.info(f"Processing task {task_id}: {task.file_name}")

            # Create progress callback for speech engine
            def progress_callback(progress: float):
                """Callback for speech engine progress updates."""
                try:
                    # Update task progress directly in DB to avoid object overhead
                    query = "UPDATE transcription_tasks SET progress = ? WHERE id = ?"
                    self.db.execute(query, (progress, task_id), commit=True)
                    
                    # Notify listeners
                    self._update_progress(task_id, progress, "Transcribing")
                except Exception as e:
                    logger.error(f"Error updating progress for task {task_id}: {e}", exc_info=True)

            self._update_progress(task_id, 10.0, "Loading audio file")

            # Also update database for 10% progress
            task.progress = 10.0
            task.save(self.db)
            
            logger.info(f"Calling speech_engine.transcribe_file for task {task_id}")
            ensure_not_cancelled("before starting transcription")

            # Prepare engine options
            engine_kwargs = dict(self._task_engine_options.get(task_id, {}))
            engine_kwargs["progress_callback"] = progress_callback
            
            # Execute transcription
            result = await self.speech_engine.transcribe_file(
                task.file_path, language=task.language, **engine_kwargs
            )
            
            ensure_not_cancelled("after completing transcription")
            logger.info(f"Transcription completed for task {task_id}, processing results")

            # Save results
            ensure_not_cancelled("before saving results")
            self._update_progress(task_id, 90.0, "Saving results")
            
            # Use helper to save internal result
            self._save_internal_result(task_id, result)

            # Finalize task
            ensure_not_cancelled("before marking task as completed")
            self._finalize_task_completion(task, result)

            # Notify completion
            self._notify_listeners("task_updated", task.to_dict())
            self._notify_listeners("task_completed", {"id": task_id})

            # Cleanup engine options
            if task_id in self._task_engine_options:
                del self._task_engine_options[task_id]
                self._persist_task_engine_options()

        except asyncio.CancelledError:
            logger.info(f"Task {task_id} cancelled")
            # Update status to cancelled
            from config.constants import TASK_STATUS_CANCELLED
            if task:
                task.status = TASK_STATUS_CANCELLED
                task.save(self.db)
                self._notify_listeners("task_updated", task.to_dict())
                self._notify_listeners("task_cancelled", {"id": task_id})
            
            # Use helper to ensure consistent cleanup if needed
            self._cleanup_after_cancellation(task_id)

        except Exception as e:
            logger.error(f"Error processing task {task_id}: {e}", exc_info=True)
            # Update status to failed
            from config.constants import TASK_STATUS_FAILED
            if task:
                task.status = TASK_STATUS_FAILED
                task.error_message = str(e)
                task.save(self.db)
                self._notify_listeners("task_updated", task.to_dict())
                self._notify_listeners("task_failed", {"id": task_id, "error": str(e)})

    def _save_internal_result(self, task_id: str, result: Dict[str, Any]) -> None:
        """
        Save transcription result to internal storage with secure permissions.
        
        Args:
            task_id: Task identifier
            result: Transcription result dictionary
        """
        internal_format_path = self._get_internal_format_path(task_id)
        internal_format_path_obj = Path(internal_format_path)
        internal_format_path_obj.parent.mkdir(parents=True, exist_ok=True)

        with open(internal_format_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        # Set secure file permissions (owner read/write only)
        try:
            os.chmod(internal_format_path, 0o600)
        except Exception as e:
            logger.warning(f"Could not set file permissions for {internal_format_path}: {e}")

    def _finalize_task_completion(self, task: TranscriptionTask, result: Dict[str, Any]) -> None:
        """
        Handle task completion steps: update metadata, status, and trigger export.
        
        Args:
            task: Task object
            result: Transcription result dictionary
        """
        # Extract audio duration if available
        if "duration" in result:
            task.audio_duration = result["duration"]

        from config.constants import TASK_STATUS_COMPLETED
        # Update status
        task.status = TASK_STATUS_COMPLETED
        task.completed_at = datetime.now().isoformat()
        task.progress = 100.0
        task.save(self.db)

        # Auto-export logic
        try:
            default_format = self._default_output_format
            if task.output_format:
                default_format = task.output_format

            # Generate default output path if not set
            if not task.output_path:
                source_path = Path(task.file_path)
                # Use a safe fallback if stem fails
                stem = source_path.stem if source_path.name else "output"
                output_filename = f"{stem}.{default_format}"
                task.output_path = str(source_path.parent / output_filename)
                task.save(self.db)

            self.export_result(task.id, default_format, task.output_path)
        except Exception as e:
            logger.error(f"Failed to auto-export task {task.id}: {e}", exc_info=True)
            
            # Fallback export to application-managed directory.
            try:
                fallback_dir = get_app_dir() / "exports"
                fallback_dir.mkdir(parents=True, exist_ok=True)
                # Ensure we have a valid format
                default_format = self._default_output_format
                if task.output_format:
                    default_format = task.output_format
                    
                fallback_output = fallback_dir / f"{Path(task.file_path).stem}.{default_format}"
                
                self.export_result(
                    task.id,
                    output_format=default_format,
                    output_path=str(fallback_output),
                )
                logger.warning(
                    "Task %s exported using fallback output path: %s",
                    task.id,
                    fallback_output,
                )
            except Exception as fallback_error:
                logger.error(
                    "Fallback export failed for task %s: %s",
                    task.id,
                    fallback_error,
                    exc_info=True,
                )
            
            # We don't fail the task if export fails, but we log it

    def _cleanup_after_cancellation(self, task_id: str) -> None:
        """Clean up resources after task cancellation."""
        if task_id in self._task_engine_options:
            del self._task_engine_options[task_id]
            self._persist_task_engine_options()



    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed status of a task.

        Args:
            task_id: Task identifier

        Returns:
            Dict with task information, or None if not found
        """
        task = TranscriptionTask.get_by_id(self.db, task_id)
        if not task:
            return None

        return {
            "id": task.id,
            "file_name": task.file_name,
            "file_path": task.file_path,
            "file_size": task.file_size,
            "audio_duration": task.audio_duration,
            "status": task.status,
            "progress": task.progress,
            "language": task.language,
            "engine": task.engine,
            "output_format": task.output_format,
            "output_path": task.output_path,
            "error_message": task.error_message,
            "created_at": task.created_at,
            "started_at": task.started_at,
            "completed_at": task.completed_at,
        }

    def cancel_task(self, task_id: str) -> bool:
        """
        Cancel a task.

        Args:
            task_id: Task identifier

        Returns:
            True if cancelled, False otherwise
        """
        if not self._loop or not self._running:
            logger.warning("Task queue not running, cannot cancel task")
            return False

        import asyncio
        from config.constants import TASK_STATUS_CANCELLED

        # Cancel in queue (schedule in background event loop)
        future = asyncio.run_coroutine_threadsafe(self.task_queue.cancel_task(task_id), self._loop)

        try:
            cancelled = future.result(timeout=5.0)

            if cancelled:
                # Update database
                task = TranscriptionTask.get_by_id(self.db, task_id)
                if task:
                    task.status = TASK_STATUS_CANCELLED
                    task.save(self.db)

                logger.info(f"Task {task_id} cancelled")

            return cancelled
        except concurrent.futures.TimeoutError:
            logger.error(f"Timeout cancelling task {task_id}")
            return False

    def retry_task(self, task_id: str) -> bool:
        """
        Retry a failed task.

        Args:
            task_id: Task identifier

        Returns:
            True if retry was initiated, False otherwise
        """
        from config.constants import TASK_STATUS_FAILED, TASK_STATUS_PENDING

        task = TranscriptionTask.get_by_id(self.db, task_id)
        if not task:
            logger.warning(f"Cannot retry task {task_id}: not found")
            return False

        if task.status != TASK_STATUS_FAILED:
            logger.warning(
                f"Cannot retry task {task_id}: status is {task.status}, " f"not 'failed'"
            )
            return False

        # Reset task status
        task.status = TASK_STATUS_PENDING
        task.progress = 0.0
        task.error_message = None
        task.started_at = None
        task.completed_at = None
        task.save(self.db)

        # Re-add to queue (schedule in background event loop)
        if self._loop and self._running:
            import asyncio

            asyncio.run_coroutine_threadsafe(
                self.task_queue.add_task(task.id, self._process_task_async, task.id), self._loop
            )
            logger.info(f"Task {task_id} queued for retry")
            return True
        else:
            logger.warning("Task queue not running, cannot retry task")
            return False



    def get_all_tasks(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all tasks, optionally filtered by status.

        Args:
            status: Optional status filter (pending/processing/completed/failed)

        Returns:
            List of task information dicts
        """
        tasks = TranscriptionTask.get_all(self.db, status=status)
        return [
            {
                "id": task.id,
                "file_name": task.file_name,
                "file_path": task.file_path,
                "file_size": task.file_size,
                "audio_duration": task.audio_duration,
                "status": task.status,
                "progress": task.progress,
                "language": task.language,
                "engine": task.engine,
                "output_format": task.output_format,
                "output_path": task.output_path,
                "error_message": task.error_message,
                "created_at": task.created_at,
                "started_at": task.started_at,
                "completed_at": task.completed_at,
            }
            for task in tasks
        ]

    def delete_task(self, task_id: str) -> bool:
        """
        Delete a task and its associated files.

        Args:
            task_id: Task identifier

        Returns:
            True if deleted, False if not found
        """
        task = TranscriptionTask.get_by_id(self.db, task_id)
        if not task:
            return False

        # Remove buffered entry if task was queued before event loop startup.
        with self._queue_buffer_lock:
            self._pending_queue_entries.pop(task_id, None)
        if self._task_engine_options.pop(task_id, None) is not None:
            self._persist_task_engine_options()

        from config.constants import TASK_STATUS_PROCESSING

        if task.status == TASK_STATUS_PROCESSING:
            # Processing tasks must be cancelled first; deleting here can race
            # with in-flight worker callbacks and produce inconsistent states.
            logger.warning(
                "Refusing to delete processing task %s directly; cancel it first",
                task_id,
            )
            return False

        # Best-effort cleanup for in-memory queue bookkeeping.
        self.task_queue.tasks.pop(task_id, None)

        # Delete internal format file
        internal_format_path = self._get_internal_format_path(task_id)
        if os.path.exists(internal_format_path):
            os.remove(internal_format_path)

        # Delete from database
        task.delete(self.db)

        # Notify listeners
        self._notify_listeners("task_deleted", {"id": task_id})

        logger.info(f"Deleted task {task_id}")
        return True

    def get_task_content(self, task_id: str) -> Dict[str, Any]:
        """
        Retrieve the internal structured content of a completed task.
        
        Args:
            task_id: Task identifier
            
        Returns:
            Dictionary containing the task content
            
        Raises:
            TaskNotFoundError: If task or its content file is not found
            ValueError: If content is invalid
        """
        internal_path = self._get_internal_format_path(task_id)
        if not os.path.exists(internal_path):
            # Check if task exists in DB to give better error
            task = TranscriptionTask.get_by_id(self.db, task_id)
            if not task:
                raise TaskNotFoundError(f"Task {task_id} not found")
            raise TaskNotFoundError(f"Content file for task {task_id} not found at {internal_path}")
            
        try:
            with open(internal_path, "r", encoding="utf-8") as f:
                content = json.load(f)
                return content
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode task content for {task_id}: {e}")
            raise ValueError(f"Invalid task content format: {e}")
        except Exception as e:
            logger.error(f"Error reading task content for {task_id}: {e}")
            raise

    def export_result(self, task_id: str, output_format: str, output_path: str) -> str:
        """
        Export task result to a specific format and path.
        
        Args:
            task_id: Task identifier
            output_format: Target format (txt, srt, md)
            output_path: Destination file path
            
        Returns:
            Path to the exported file
            
        Raises:
            TaskNotFoundError: If task content is missing
            ValueError: If format is unsupported
            IOError: If writing to file fails
        """
        # Validate task state first
        task = TranscriptionTask.get_by_id(self.db, task_id)
        if not task:
            raise TaskNotFoundError(f"Task {task_id} not found")

        if task.status != "completed":
            raise ValueError(f"Task {task_id} is not completed (status: {task.status})")

        # Get content
        try:
            content = self.get_task_content(task_id)
        except TaskNotFoundError:
            # Re-raise with context
            raise TaskNotFoundError(f"Cannot export task {task_id}: content not found")
            
        # Convert content
        try:
            formatted_content = self.format_converter.convert(content, output_format)
        except ValueError as e:
            logger.error(f"Format conversion failed for task {task_id}: {e}")
            raise
            
        # Ensure directory exists
        path_obj = Path(output_path)
        path_obj.parent.mkdir(parents=True, exist_ok=True)
        
        # Write to file
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(formatted_content)
        except Exception as e:
            logger.error(f"Failed to write exported file to {output_path}: {e}")
            raise IOError(f"Failed to write export file: {e}")
            
        logger.info(f"Exported task {task_id} to {output_format.upper()} at {output_path}")
        return output_path

    def _get_internal_format_path(self, task_id: str) -> str:
        """
        Get path for internal format JSON file.

        Args:
            task_id: Task identifier

        Returns:
            Path to internal format file
        """
        data_dir = get_app_dir() / "transcripts"
        data_dir.mkdir(parents=True, exist_ok=True)
        return str(data_dir / f"{task_id}.json")

    def _update_progress(self, task_id: str, progress: float, message: str = ""):
        """
        Update task progress and notify callbacks.

        Args:
            task_id: Task identifier
            progress: Progress percentage (0-100)
            message: Optional progress message
        """
        # Call registered callback if exists
        if task_id in self.progress_callbacks:
            try:
                self.progress_callbacks[task_id](task_id, progress, message)
            except Exception as e:
                logger.error(f"Error calling progress callback for task {task_id}: {e}")

        # Notify global listeners
        try:
            self._notify_listeners(
                "task_updated", 
                {"id": task_id, "progress": progress, "status": "processing", "message": message}
            )
        except Exception:
            pass
            
        logger.debug(f"Task {task_id} progress: {progress:.1f}% - {message}")

    def _translate(self, key: str, default: Optional[str] = None, **kwargs) -> str:
        """Translate a key using the configured translator."""
        translator = self._translator

        if translator:
            try:
                value = translator(key, **kwargs)
            except TypeError:
                value = translator(key)
            except Exception as exc:
                logger.warning(
                    "Translator raised error for key %s: %s",
                    key,
                    exc,
                )
                value = None

            if value is not None:
                translated = str(value)
                if default is not None and translated == key:
                    try:
                        return default.format(**kwargs)
                    except Exception:
                        return default
                return translated

        if default is None:
            if not kwargs:
                return key
            try:
                return key.format(**kwargs)
            except Exception:
                return key

        try:
            return default.format(**kwargs)
        except Exception:
            return default

    def _send_notification(
        self,
        base_key: str,
        notification_type: str,
        *,
        title_default: str = "EchoNote",
        message_default: str = "",
        **kwargs,
    ):
        """
        Send desktop notification.

        Args:
            base_key: Translation key prefix (expects ``.title`` and ``.message``)
            notification_type: Type of notification (success/error/info)
            title_default: Fallback title when translation unavailable
            message_default: Fallback message when translation unavailable
            **kwargs: Parameters for translation formatting
        """
        context = dict(kwargs) if kwargs else {}
        app_name = self._translate("app.title", default="EchoNote")
        context.setdefault("app_name", app_name)

        title = self._translate(
            f"{base_key}.title",
            default=title_default,
            **context,
        )
        message = self._translate(
            f"{base_key}.message",
            default=message_default,
            **context,
        )

        title = title.replace("\\n", "\n")
        message = message.replace("\\n", "\n")

        try:
            notification_manager = get_notification_manager()
        except Exception as exc:
            logger.error(f"Failed to acquire notification manager: {exc}")
            logger.info(f"Notification ({notification_type}): {message}")
            return

        try:
            send_methods = {
                "success": notification_manager.send_success,
                "error": notification_manager.send_error,
                "warning": notification_manager.send_warning,
                "info": notification_manager.send_info,
            }

            handler = send_methods.get(notification_type)

            if handler:
                handler(title, message)
            else:
                notification_manager.send_notification(
                    title,
                    message,
                    notification_type,
                )

        except Exception as exc:
            logger.error(f"Error sending notification: {exc}")
            logger.info(f"Notification ({notification_type}): {message}")

    def register_progress_callback(self, task_id: str, callback: callable):
        """
        Register a callback for task progress updates.

        The callback will be called with (task_id, progress, message) when
        progress is updated. This is useful for UI integration.

        Args:
            task_id: Task identifier
            callback: Callback function(task_id: str, progress: float, message: str)

        Example:
            def on_progress(task_id, progress, message):
                print(f"Task {task_id}: {progress}% - {message}")

            manager.register_progress_callback(task_id, on_progress)
        """
        self.progress_callbacks[task_id] = callback
        logger.debug(f"Registered progress callback for task {task_id}")

    def unregister_progress_callback(self, task_id: str):
        """
        Unregister progress callback for a task.

        Args:
            task_id: Task identifier
        """
        if task_id in self.progress_callbacks:
            del self.progress_callbacks[task_id]
            logger.debug(f"Unregistered progress callback for task {task_id}")

    def update_max_concurrent(self, max_concurrent: int):
        """
        Update the maximum number of concurrent tasks.

        This will restart the task queue with the new concurrency limit.

        Args:
            max_concurrent: New maximum concurrent tasks (1-5)
        """
        if not 1 <= max_concurrent <= 5:
            logger.error(
                f"Invalid max_concurrent value: {max_concurrent}. " f"Must be between 1 and 5."
            )
            return

        if max_concurrent == self.task_queue.max_concurrent:
            logger.debug(f"max_concurrent already set to {max_concurrent}, " f"no update needed")
            return

        logger.info(
            f"Updating max_concurrent from " f"{self.task_queue.max_concurrent} to {max_concurrent}"
        )

        # Stop current processing
        was_running = self._running
        if was_running:
            self.stop_processing()

        # Update task queue configuration
        self.task_queue.max_concurrent = max_concurrent
        self.task_queue.semaphore = asyncio.Semaphore(max_concurrent)

        # Restart processing if it was running
        if was_running:
            self.start_processing()

        logger.info(f"max_concurrent updated to {max_concurrent}")

    def reload_engine(self) -> bool:
        """
        Reload the speech engine with updated configuration.

        This method is called when API keys or engine settings are updated.
        It will reinitialize the engine with new credentials.

        Returns:
            True if reload completed, False if skipped.
        """
        logger.info("Reloading speech engine with updated configuration...")

        try:
            loader = getattr(self.speech_engine, "_loader", None)
            if loader is None:
                logger.warning("Speech engine does not expose lazy loader; reload skipped")
                return False

            # Eagerly initialize once so runtime errors surface immediately.
            if hasattr(loader, "reload") and callable(loader.reload):
                engine = loader.reload()
            else:
                # Backward-compatible fallback for custom loaders.
                loader._instance = None
                loader._initialized = False
                engine = loader.get()
            logger.info("Speech engine reloaded successfully: %s", engine.get_name())
            return True
        except Exception as e:
            logger.error(f"Error reloading speech engine: {e}", exc_info=True)
            raise
