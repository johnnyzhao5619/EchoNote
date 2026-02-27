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
import re
import threading
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from config.app_config import get_app_dir
from core.transcription.format_converter import FormatConverter
from core.transcription.task_queue import TaskQueue, TaskStatus
from data.database.connection import DatabaseConnection
from data.database.models import (
    EventAttachment,
    TranscriptionTask,
    current_iso_timestamp,
)
from engines.speech.base import AUDIO_VIDEO_SUFFIXES, SpeechEngine
from ui.common.notification import get_notification_manager

logger = logging.getLogger("echonote.transcription.manager")

TEXT_TRANSLATION_SUFFIXES = frozenset({".txt", ".md"})
TRANSLATION_OUTPUT_FORMATS = frozenset({"txt", "md"})
TRANSLATION_TASK_ENGINE = "translation"
TRANSLATION_TASK_KIND = "translation"
TRANSCRIPTION_TASK_KIND = "transcription"


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
        translation_engine: Optional[Any] = None,
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

        # 翻译引擎（可选），用于批量转写任务完成后自动翻译
        self.translation_engine = translation_engine

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
                "Ignoring default_save_path with unsupported type: %s",
                type(raw_default_path).__name__,
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

        self._default_output_format = self.config.get(
            "default_output_format", DEFAULT_OUTPUT_FORMAT
        )

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
        self._task_quality_notes: Dict[str, str] = {}
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
        # Snapshot the list before iterating to avoid RuntimeError if a listener
        # is added or removed concurrently from another thread.
        for listener in list(self.event_listeners):
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
        logger.info("Starting to drain buffered transcription tasks...")
        buffered_tasks = self._pop_buffered_tasks()
        if not buffered_tasks:
            logger.info("No buffered tasks to drain")
            return

        logger.info(f"Draining {len(buffered_tasks)} tasks from buffer")
        for task_id, (task_func, args, kwargs) in buffered_tasks:
            try:
                await self.task_queue.add_task(task_id, task_func, *args, **kwargs)
                logger.info(f"Task {task_id} successfully scheduled from buffer")
            except Exception as exc:
                logger.error(
                    f"CRITICAL: Failed to schedule buffered task {task_id}: {exc}", exc_info=True
                )
        logger.info("Finished draining buffered transcription tasks")

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
            "replace_realtime",
            "event_id",
            # 翻译选项
            "enable_translation",
            "translation_source_lang",
            "translation_target_lang",
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
                "task_kind": TRANSCRIPTION_TASK_KIND,
            },
        )

        logger.info(f"Added transcription task: {task.id} for file {file_path.name}")
        return task.id

    def add_translation_task(self, file_path: str, options: Optional[Dict[str, Any]] = None) -> str:
        """
        Add a translation task for a text/audio/video source file.

        Args:
            file_path: Path to source file (audio/video/txt/md)
            options: Optional task options:
                - translation_source_lang: Source language code
                - translation_target_lang: Target language code
                - language: Source transcription language (audio/video only)
                - output_format: Output format (txt/md)
                - output_path: Custom output path

        Returns:
            Task ID
        """
        if not self.translation_engine:
            raise RuntimeError("Translation engine is unavailable")

        options = options or {}
        source_path = Path(file_path).expanduser().resolve()
        if not source_path.exists():
            raise FileNotFoundError(f"File not found: {source_path}")

        supported_suffixes = AUDIO_VIDEO_SUFFIXES | TEXT_TRANSLATION_SUFFIXES
        suffix = source_path.suffix.lower()
        if suffix not in supported_suffixes:
            raise ValueError(
                f"Unsupported file format: {source_path.suffix}. "
                f"Supported formats: {', '.join(sorted(supported_suffixes))}"
            )

        output_format = (options.get("output_format") or "").strip().lower()
        if not output_format:
            output_format = "md" if suffix == ".md" else "txt"
        if output_format not in TRANSLATION_OUTPUT_FORMATS:
            raise ValueError(
                f"Translation output_format must be one of: {', '.join(sorted(TRANSLATION_OUTPUT_FORMATS))}"
            )

        from config.constants import TASK_STATUS_PENDING

        task = TranscriptionTask(
            file_path=str(source_path),
            file_name=source_path.name,
            file_size=source_path.stat().st_size,
            status=TASK_STATUS_PENDING,
            language=options.get("translation_source_lang") or "auto",
            engine=TRANSLATION_TASK_ENGINE,
            output_format=output_format,
            output_path=options.get("output_path"),
        )
        task.save(self.db)

        engine_option_keys = {
            "model_name",
            "model_path",
            "beam_size",
            "vad_filter",
            "vad_min_silence_duration_ms",
            "prompt",
            "temperature",
            "event_id",
            "language",
            "translation_source_lang",
            "translation_target_lang",
        }
        engine_options = {key: options[key] for key in engine_option_keys if key in options}
        engine_options["task_kind"] = TRANSLATION_TASK_KIND
        self._task_engine_options[task.id] = engine_options
        self._persist_task_engine_options()

        if not self._queue_or_buffer_task(task.id):
            logger.info(f"Task queue not ready, task {task.id} cached until processing starts")

        self._notify_listeners(
            "task_added",
            {
                "id": task.id,
                "file_name": task.file_name,
                "status": task.status,
                "created_at": task.created_at,
                "task_kind": TRANSLATION_TASK_KIND,
            },
        )
        logger.info("Added translation task: %s for file %s", task.id, source_path.name)
        return task.id

    def add_translation_tasks_from_folder(
        self, folder_path: str, options: Optional[Dict[str, Any]] = None
    ) -> List[str]:
        """
        Add translation tasks for all supported files in a folder.

        Supported input formats: audio/video/txt/md.
        """
        folder_path_obj = Path(folder_path).expanduser().resolve()
        if not folder_path_obj.is_dir():
            raise NotADirectoryError(f"Not a directory: {folder_path_obj}")

        task_ids: List[str] = []
        supported_suffixes = AUDIO_VIDEO_SUFFIXES | TEXT_TRANSLATION_SUFFIXES
        for file_path in folder_path_obj.rglob("*"):
            if not file_path.is_file():
                continue
            if file_path.suffix.lower() not in supported_suffixes:
                continue
            try:
                task_ids.append(self.add_translation_task(str(file_path), options))
            except Exception as exc:
                logger.error("Failed to add translation task for %s: %s", file_path, exc)

        logger.info("Added %d translation tasks from folder %s", len(task_ids), folder_path_obj)
        return task_ids

    def add_translation_text_task(
        self,
        text: str,
        *,
        file_name: str = "pasted_text.txt",
        options: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Persist pasted text as a source file and enqueue a translation task.
        """
        content = text.strip()
        if not content:
            raise ValueError("Text content is empty")

        clean_file_name = Path(file_name or "pasted_text.txt").name
        suffix = Path(clean_file_name).suffix.lower()
        if suffix not in TEXT_TRANSLATION_SUFFIXES:
            clean_file_name = f"{Path(clean_file_name).stem}.txt"

        input_dir = get_app_dir() / "translation_inputs"
        input_dir.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(input_dir, 0o700)
        except Exception:
            pass

        task_seed = TranscriptionTask()
        source_path = input_dir / f"{task_seed.id}_{clean_file_name}"
        source_path.write_text(content, encoding="utf-8")
        try:
            os.chmod(source_path, 0o600)
        except Exception:
            pass

        return self.add_translation_task(str(source_path), options=options)

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
                                    "Task queue stop failed after %d attempts; "
                                    "proceeding with forced shutdown",
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
        runtime_options: Dict[str, Any] = {}

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
            from utils.time_utils import current_iso_timestamp

            task.status = TASK_STATUS_PROCESSING
            task.started_at = current_iso_timestamp()
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

            # Prepare engine/runtime options
            runtime_options = dict(self._task_engine_options.get(task_id, {}))
            task_kind = runtime_options.get("task_kind")
            if task_kind == TRANSLATION_TASK_KIND:
                await self._process_translation_task_async(
                    task=task,
                    task_id=task_id,
                    runtime_options=runtime_options,
                    ensure_not_cancelled=ensure_not_cancelled,
                )
                updated_task = TranscriptionTask.get_by_id(self.db, task_id) or task
                self._notify_listeners(
                    "task_updated",
                    self._build_task_payload(updated_task, runtime_options=runtime_options),
                )
                self._notify_listeners("task_completed", {"id": task_id})
                if task_id in self._task_engine_options:
                    del self._task_engine_options[task_id]
                    self._persist_task_engine_options()
                return

            replace_realtime = bool(runtime_options.pop("replace_realtime", False))
            event_id = runtime_options.get("event_id")

            # Only pass speech-engine-specific options to transcription engine.
            engine_kwargs = dict(runtime_options)
            engine_kwargs.pop("event_id", None)
            engine_kwargs.pop("enable_translation", None)
            engine_kwargs.pop("translation_source_lang", None)
            engine_kwargs.pop("translation_target_lang", None)
            engine_kwargs.pop("target_language", None)
            engine_kwargs["progress_callback"] = progress_callback

            # Execute transcription
            result = await self.speech_engine.transcribe_file(
                task.file_path, language=task.language, **engine_kwargs
            )
            transcript_text = self._extract_transcript_text(result)
            existing_transcript_text = ""
            if replace_realtime and event_id:
                existing_transcript_text = self._read_event_attachment_text(
                    event_id=event_id,
                    attachment_type="transcript",
                )
            transcript_valid, transcript_issue = self._evaluate_transcription_output(
                result=result,
                transcript_text=transcript_text,
                existing_transcript_text=existing_transcript_text,
            )
            if not transcript_valid:
                self._set_task_quality_note(task_id, transcript_issue)
                raise ValueError(f"Transcription output is invalid ({transcript_issue})")

            ensure_not_cancelled("after completing transcription")
            logger.info(f"Transcription completed for task {task_id}, processing results")

            # Save results
            ensure_not_cancelled("before saving results")
            self._update_progress(task_id, 90.0, "Saving results")

            # Use helper to save internal result
            self._save_internal_result(task_id, result)

            if replace_realtime:
                try:
                    txt_path = self._resolve_realtime_transcript_path(task, event_id)
                    json_path = txt_path.with_suffix(".json")

                    with open(json_path, "w", encoding="utf-8") as f:
                        json.dump(result, f, ensure_ascii=False, indent=2)

                    if transcript_text:
                        with open(txt_path, "w", encoding="utf-8") as f:
                            f.write(transcript_text)

                    if event_id:
                        file_size = None
                        if txt_path.exists():
                            file_size = txt_path.stat().st_size
                        EventAttachment.upsert_for_event_type(
                            db_connection=self.db,
                            event_id=event_id,
                            attachment_type="transcript",
                            file_path=str(txt_path),
                            file_size=file_size,
                        )

                    logger.info("Replaced realtime transcripts at %s", json_path)
                except Exception as e:
                    logger.error(f"Failed to replace realtime transcripts: {e}", exc_info=True)

            # Finalize task
            ensure_not_cancelled("before marking task as completed")
            self._finalize_task_completion(task, result)

            # Optional: translate transcription result.
            # For secondary re-transcription, if a translation attachment already exists,
            # always retranslate against the refreshed transcript and overwrite it.
            should_translate = bool(runtime_options.get("enable_translation"))
            had_existing_translation = False
            if (
                not should_translate
                and replace_realtime
                and event_id
                and self._event_has_attachment_type(event_id, "translation")
            ):
                should_translate = True
                had_existing_translation = True

            if self.translation_engine and should_translate:
                try:
                    await self._translate_and_save(task, transcript_text, runtime_options)
                except Exception as trans_exc:
                    self._set_task_quality_note(task_id, f"translation refresh failed: {trans_exc}")
                    if replace_realtime and event_id and had_existing_translation:
                        if self._remove_event_attachment_by_type(
                            event_id=event_id,
                            attachment_type="translation",
                        ):
                            self._set_task_quality_note(
                                task_id,
                                "stale translation attachment removed after failed refresh",
                            )
                    logger.error(
                        "Translation failed for task %s: %s", task_id, trans_exc, exc_info=True
                    )
                    # 翻译失败不影响转写任务的完成状态

            # Notify completion
            self._notify_listeners(
                "task_updated",
                self._build_task_payload(task, runtime_options=runtime_options),
            )
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
                self._notify_listeners(
                    "task_updated",
                    self._build_task_payload(task, runtime_options=runtime_options),
                )
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
                self._notify_listeners(
                    "task_updated",
                    self._build_task_payload(task, runtime_options=runtime_options),
                )
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
        task.completed_at = current_iso_timestamp()
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

    async def _process_translation_task_async(
        self,
        *,
        task: TranscriptionTask,
        task_id: str,
        runtime_options: Dict[str, Any],
        ensure_not_cancelled: Callable[[str], None],
    ) -> None:
        """Process translation task for text/audio/video inputs."""
        if not self.translation_engine:
            raise RuntimeError("Translation engine is unavailable")

        source_path = Path(task.file_path).expanduser().resolve()
        suffix = source_path.suffix.lower()
        source_lang = runtime_options.get("translation_source_lang") or "auto"
        target_lang = runtime_options.get("translation_target_lang") or "en"
        source_text = ""
        transcribe_result: Dict[str, Any] = {}

        def _persist_progress(progress: float, message: str) -> None:
            self.db.execute(
                "UPDATE transcription_tasks SET progress = ? WHERE id = ?",
                (float(progress), task_id),
                commit=True,
            )
            self._update_progress(task_id, float(progress), message)

        _persist_progress(5.0, "Loading source")
        ensure_not_cancelled("before loading translation source")

        if suffix in AUDIO_VIDEO_SUFFIXES:
            self._update_progress(task_id, 10.0, "Transcribing source audio")
            audio_language = runtime_options.get("language")
            engine_kwargs = dict(runtime_options)
            engine_kwargs.pop("task_kind", None)
            engine_kwargs.pop("event_id", None)
            engine_kwargs.pop("language", None)
            engine_kwargs.pop("translation_source_lang", None)
            engine_kwargs.pop("translation_target_lang", None)
            engine_kwargs["progress_callback"] = (
                lambda progress: _persist_progress(10.0 + (float(progress) * 0.5), "Transcribing")
            )
            transcribe_result = await self.speech_engine.transcribe_file(
                task.file_path,
                language=audio_language,
                **engine_kwargs,
            )
            source_text = self._extract_transcript_text(transcribe_result)
            source_valid, source_issue = self._evaluate_transcription_output(
                result=transcribe_result,
                transcript_text=source_text,
            )
            if not source_valid:
                self._set_task_quality_note(task_id, source_issue)
                raise ValueError(
                    f"Translation source transcription is invalid ({source_issue})"
                )
        elif suffix in TEXT_TRANSLATION_SUFFIXES:
            source_text = source_path.read_text(encoding="utf-8")
        else:
            raise ValueError(
                f"Unsupported file format for translation: {source_path.suffix}. "
                f"Supported formats: {', '.join(sorted(AUDIO_VIDEO_SUFFIXES | TEXT_TRANSLATION_SUFFIXES))}"
            )

        if not source_text.strip():
            raise ValueError("Translation source text is empty")

        ensure_not_cancelled("before translation")
        _persist_progress(70.0, "Translating")
        translated_text = await self._translate_text(
            text=source_text,
            source_lang=source_lang,
            target_lang=target_lang,
            task_id=task_id,
        )
        if not translated_text.strip():
            raise ValueError("Translation result is empty")

        ensure_not_cancelled("before saving translation")
        _persist_progress(90.0, "Saving results")

        output_format = (task.output_format or "txt").lower()
        if output_format not in TRANSLATION_OUTPUT_FORMATS:
            raise ValueError(
                f"Translation output_format must be one of: {', '.join(sorted(TRANSLATION_OUTPUT_FORMATS))}"
            )

        event_id = runtime_options.get("event_id")
        if task.output_path:
            output_path = Path(task.output_path).expanduser().resolve()
        else:
            output_path = self._resolve_translation_output_path(
                base_path=source_path,
                target_lang=target_lang,
                event_id=event_id,
                extension=output_format,
            )
        task.output_path = str(output_path)
        task.output_format = output_format
        task.save(self.db)

        internal_result = self._build_internal_result_from_text(translated_text)
        self._save_internal_result(task_id, internal_result)

        self._write_translation_output(
            text=translated_text,
            output_format=output_format,
            output_path=output_path,
        )
        self._upsert_translation_attachment(event_id=event_id, translation_path=output_path)

        if suffix in AUDIO_VIDEO_SUFFIXES and isinstance(transcribe_result, dict):
            duration = transcribe_result.get("duration")
            if isinstance(duration, (int, float)):
                task.audio_duration = float(duration)

        from config.constants import TASK_STATUS_COMPLETED

        task.status = TASK_STATUS_COMPLETED
        task.completed_at = current_iso_timestamp()
        task.progress = 100.0
        task.error_message = None
        task.save(self.db)

        _persist_progress(100.0, "Completed")

    @staticmethod
    def _build_internal_result_from_text(text: str) -> Dict[str, Any]:
        """Build internal transcript-like payload from plain text."""
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        segments = []
        for index, line in enumerate(lines):
            start_time = float(index)
            segments.append(
                {
                    "start": start_time,
                    "end": start_time,
                    "text": line,
                }
            )

        return {
            "text": text.strip(),
            "segments": segments,
            "duration": float(len(lines)),
        }

    def _resolve_task_kind(
        self,
        *,
        task: Optional[TranscriptionTask] = None,
        task_id: Optional[str] = None,
        runtime_options: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Resolve task kind from runtime options first, then persisted metadata."""
        options = runtime_options
        if options is None and task_id:
            options = self._task_engine_options.get(task_id, {})

        if isinstance(options, dict):
            task_kind = options.get("task_kind")
            if isinstance(task_kind, str) and task_kind:
                return task_kind

        if task and task.engine == TRANSLATION_TASK_ENGINE:
            return TRANSLATION_TASK_KIND

        return TRANSCRIPTION_TASK_KIND

    def _build_task_payload(
        self,
        task: TranscriptionTask,
        *,
        runtime_options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Serialize task to listener payload with stable task kind metadata."""
        payload = task.to_dict()
        payload["task_kind"] = self._resolve_task_kind(
            task=task,
            task_id=task.id,
            runtime_options=runtime_options,
        )
        quality_note = self._task_quality_notes.get(task.id)
        if quality_note:
            payload["quality_note"] = quality_note
        return payload

    @staticmethod
    def _extract_transcript_text(result: Dict[str, Any]) -> str:
        """Normalize transcript text from engine payload."""
        text = result.get("text")
        if isinstance(text, str) and text.strip():
            return text

        segments = result.get("segments")
        if not isinstance(segments, list):
            return ""

        collected: list[str] = []
        for segment in segments:
            if not isinstance(segment, dict):
                continue
            segment_text = segment.get("text")
            if isinstance(segment_text, str) and segment_text.strip():
                collected.append(segment_text.strip())
        return "\n".join(collected).strip()

    @classmethod
    def _evaluate_transcription_output(
        cls,
        *,
        result: Dict[str, Any],
        transcript_text: str,
        existing_transcript_text: str = "",
    ) -> Tuple[bool, str]:
        """Validate transcription output quality for completeness and regression."""
        normalized_text = transcript_text.strip()
        if not normalized_text:
            return False, "empty transcript text"

        segments = result.get("segments")
        if isinstance(segments, list) and segments:
            non_empty_segments = 0
            for segment in segments:
                if not isinstance(segment, dict):
                    continue
                segment_text = segment.get("text")
                if isinstance(segment_text, str) and segment_text.strip():
                    non_empty_segments += 1
            if non_empty_segments == 0:
                return False, "no non-empty transcript segments"

        if existing_transcript_text.strip() and cls._is_likely_degraded_transcript(
            new_transcript=normalized_text,
            previous_transcript=existing_transcript_text,
        ):
            return False, "secondary transcription quality regression"

        return True, ""

    @staticmethod
    def _non_whitespace_length(text: str) -> int:
        """Count non-whitespace characters."""
        return sum(1 for char in text if not char.isspace())

    @classmethod
    def _is_likely_degraded_transcript(
        cls, *, new_transcript: str, previous_transcript: str
    ) -> bool:
        """
        Detect obvious quality regression for secondary transcription replacement.

        Secondary transcription should improve or at least preserve transcript completeness.
        """
        new_units = cls._count_semantic_units(new_transcript)
        previous_units = cls._count_semantic_units(previous_transcript)
        if previous_units < 8:
            return False

        if new_units <= max(2, previous_units // 5):
            return True

        new_len = cls._non_whitespace_length(new_transcript)
        previous_len = cls._non_whitespace_length(previous_transcript)
        if previous_len >= 120 and new_len <= max(40, int(previous_len * 0.35)):
            return True

        return False

    async def _translate_and_save(
        self, task: TranscriptionTask, text: str, options: Dict[str, Any]
    ) -> None:
        """翻译转写文本并将翻译文件路径关联到任务。

        有 event_id 时通过 event_attachments 关联（attachment_type='translation'）；
        无 event_id 时保存至音频文件同目录，命名为 <stem>_translation_<target_lang>.<format>。
        """
        if not text.strip():
            return

        source_lang = options.get("translation_source_lang") or "auto"
        target_lang = options.get("translation_target_lang") or options.get("target_language") or "en"
        event_id = options.get("event_id")

        logger.info("Translating task %s (%s→%s)", task.id, source_lang, target_lang)
        translated_text = await self._translate_text(
            text=text,
            source_lang=source_lang,
            target_lang=target_lang,
            task_id=task.id,
        )

        if not translated_text:
            return

        audio_path = Path(task.file_path)
        output_format = task.output_format or "txt"
        translation_path = self._resolve_translation_output_path(
            base_path=audio_path,
            target_lang=target_lang,
            event_id=event_id,
            extension=output_format,
        )
        self._write_translation_file(translation_path, translated_text)

        logger.info("Translation saved to %s", translation_path)

        self._upsert_translation_attachment(event_id=event_id, translation_path=translation_path)

    async def translate_transcript_file(
        self,
        transcript_path: str,
        *,
        source_lang: str = "auto",
        target_lang: str = "en",
        event_id: Optional[str] = None,
    ) -> str:
        """Translate a transcript text file and persist translation output.

        Args:
            transcript_path: Source transcript file path.
            source_lang: Source language hint (default ``auto``).
            target_lang: Target language code (default ``en``).
            event_id: Optional linked calendar event id for attachment upsert.

        Returns:
            The translated file path.
        """
        if not self.translation_engine:
            raise RuntimeError("Translation engine is unavailable")

        source_path = Path(transcript_path).expanduser().resolve()
        if not source_path.exists():
            raise FileNotFoundError(f"Transcript file not found: {source_path}")

        text = source_path.read_text(encoding="utf-8")
        if not text.strip():
            raise ValueError("Transcript content is empty")

        translated_text = await self._translate_text(
            text=text,
            source_lang=source_lang,
            target_lang=target_lang,
        )
        if not translated_text:
            raise ValueError("Translation result is empty")

        ext = source_path.suffix.lstrip(".") or "txt"
        translation_path = self._resolve_translation_output_path(
            base_path=source_path,
            target_lang=target_lang,
            event_id=event_id,
            extension=ext,
        )
        self._write_translation_file(translation_path, translated_text)
        self._upsert_translation_attachment(event_id=event_id, translation_path=translation_path)
        return str(translation_path)

    async def _translate_text(
        self, *, text: str, source_lang: str, target_lang: str, task_id: Optional[str] = None
    ) -> str:
        """Translate text with quality guards against masked/truncated outputs."""
        if not self.translation_engine:
            raise RuntimeError("Translation engine is unavailable")

        effective_source_lang = self._resolve_translation_source_language(
            source_lang=source_lang,
            text=text,
        )
        if self._should_use_chunked_translation_first(text):
            chunked_text = await self._translate_text_chunked(
                text=text,
                source_lang=effective_source_lang,
                target_lang=target_lang,
            )
            chunked_valid, chunked_issue = self._evaluate_translation_output(
                source_text=text,
                translated_text=chunked_text,
                check_truncation=False,
            )
            if not chunked_valid:
                self._set_task_quality_note(task_id, chunked_issue)
                raise ValueError(f"Translation output is invalid ({chunked_issue})")
            return chunked_text

        translated_text = await self._translate_once(
            text=text,
            source_lang=effective_source_lang,
            target_lang=target_lang,
        )
        is_valid, issue = self._evaluate_translation_output(
            source_text=text,
            translated_text=translated_text,
        )
        if is_valid:
            return translated_text

        logger.warning(
            "Detected low-quality translation output (%s; source=%s, target=%s). "
            "Retrying with chunked translation fallback.",
            issue,
            effective_source_lang,
            target_lang,
        )

        try:
            fallback_text = await self._translate_text_chunked(
                text=text,
                source_lang=effective_source_lang,
                target_lang=target_lang,
            )
            self._set_task_quality_note(
                task_id,
                self._translate(
                    "batch_transcribe.quality.translation_chunked_fallback",
                    default=(
                        "Translation quality guard triggered ({issue}); "
                        "chunked fallback applied."
                    ),
                    issue=issue,
                ),
            )
        except ValueError as exc:
            self._set_task_quality_note(task_id, issue)
            raise ValueError(f"Translation output is invalid ({issue})") from exc

        fallback_valid, fallback_issue = self._evaluate_translation_output(
            source_text=text,
            translated_text=fallback_text,
            check_truncation=False,
        )
        if fallback_valid:
            return fallback_text

        if not fallback_issue:
            fallback_issue = issue or "unknown output issue"
        self._set_task_quality_note(task_id, fallback_issue)
        raise ValueError(f"Translation output is invalid ({fallback_issue})")

    async def _translate_text_chunked(self, *, text: str, source_lang: str, target_lang: str) -> str:
        """Translate text by chunks and require every chunk to produce valid output."""
        chunks = self._split_translation_chunks(text)
        if not chunks:
            return ""

        translated_parts: List[str] = []
        total_chunks = len(chunks)
        for index, chunk in enumerate(chunks, start=1):
            chunk_translation = await self._translate_once(
                text=chunk,
                source_lang=source_lang,
                target_lang=target_lang,
            )
            if (
                self._is_masked_placeholder_text(chunk_translation)
                and source_lang != "zh"
                and self._contains_cjk(chunk)
            ):
                chunk_translation = await self._translate_once(
                    text=chunk,
                    source_lang="zh",
                    target_lang=target_lang,
                )

            normalized_chunk = chunk_translation.strip()
            if not normalized_chunk or self._is_masked_placeholder_text(normalized_chunk):
                raise ValueError(
                    f"Invalid translation output for chunk {index}/{total_chunks}"
                )
            if self._is_likely_extremely_short_translation(chunk, normalized_chunk):
                raise ValueError(
                    f"Suspiciously short translation output for chunk {index}/{total_chunks}"
                )
            translated_parts.append(normalized_chunk)

        return "\n".join(translated_parts).strip()

    async def _translate_once(self, *, text: str, source_lang: str, target_lang: str) -> str:
        """Run a single translation engine call and normalize return value."""
        translated = self.translation_engine.translate(text, source_lang, target_lang)
        if asyncio.iscoroutine(translated):
            translated = await translated
        if translated is None:
            return ""
        return str(translated)

    @staticmethod
    def _contains_cjk(text: str) -> bool:
        """Return whether text contains at least one CJK Unified Ideograph."""
        return any("\u4e00" <= char <= "\u9fff" for char in text)

    @staticmethod
    def _contains_hiragana_or_katakana(text: str) -> bool:
        """Return whether text contains Japanese Hiragana/Katakana characters."""
        return any(
            ("\u3040" <= char <= "\u30ff") or ("\u31f0" <= char <= "\u31ff")
            for char in text
        )

    @staticmethod
    def _contains_hangul(text: str) -> bool:
        """Return whether text contains Hangul characters."""
        return any("\uac00" <= char <= "\ud7af" for char in text)

    @classmethod
    def _resolve_translation_source_language(cls, *, source_lang: str, text: str) -> str:
        """
        Resolve effective source language for translation requests.

        For CJK scripts, explicit language improves model selection stability
        and avoids auto-detect mismatches on long transcript text.
        """
        normalized = (source_lang or "").strip().lower() or "auto"
        if normalized != "auto":
            return normalized

        if cls._contains_hangul(text):
            return "ko"
        if cls._contains_hiragana_or_katakana(text):
            return "ja"
        if cls._contains_cjk(text):
            return "zh"
        return "auto"

    @classmethod
    def _should_use_chunked_translation_first(cls, text: str) -> bool:
        """
        Decide whether to skip one-shot translation and use chunked mode directly.

        Long transcript-like inputs are translated chunk-by-chunk to minimize
        content drops from a single large generation call.
        """
        normalized = text.strip()
        if not normalized:
            return False

        source_lines = cls._count_non_empty_lines(normalized)
        if source_lines >= 8:
            return True

        source_units = cls._count_semantic_units(normalized)
        if source_units >= 10:
            return True

        return cls._non_whitespace_length(normalized) >= 260

    @staticmethod
    def _is_masked_placeholder_text(text: str) -> bool:
        """
        Detect degenerate outputs like '* * * * ...' produced by bad decoding.

        Keep threshold conservative to avoid false positives for normal markdown content.
        """
        stripped = text.strip()
        if not stripped:
            return True

        non_whitespace = [char for char in stripped if not char.isspace()]
        if len(non_whitespace) < 20:
            return False

        star_count = sum(1 for char in non_whitespace if char in {"*", "＊"})
        return (star_count / len(non_whitespace)) >= 0.85

    @classmethod
    def _evaluate_translation_output(
        cls,
        *,
        source_text: str,
        translated_text: str,
        check_truncation: bool = True,
    ) -> Tuple[bool, str]:
        """Validate translation output and classify failure reason when invalid."""
        normalized = translated_text.strip()
        if not normalized:
            return False, "empty output"
        if cls._is_masked_placeholder_text(normalized):
            return False, "masked placeholder text"
        if check_truncation and cls._is_likely_truncated_translation(
            source_text=source_text,
            translated_text=normalized,
        ):
            return False, "likely truncated output"
        return True, ""

    @staticmethod
    def _count_non_empty_lines(text: str) -> int:
        """Count non-empty lines in text."""
        return sum(1 for line in text.splitlines() if line.strip())

    @staticmethod
    def _count_semantic_units(text: str) -> int:
        """
        Count rough sentence/line units for completeness checks.

        We keep this heuristic conservative to avoid false positives on short text.
        """
        normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
        if not normalized:
            return 0

        parts = [
            part.strip()
            for part in re.split(r"(?:\n+|(?<=[。！？.!?;；]))", normalized)
            if part.strip()
        ]
        return len(parts)

    @classmethod
    def _is_likely_truncated_translation(cls, *, source_text: str, translated_text: str) -> bool:
        """Detect likely truncation where only the beginning of source content is translated."""
        source_normalized = source_text.strip()
        translated_normalized = translated_text.strip()
        if not source_normalized or not translated_normalized:
            return True

        source_lines = cls._count_non_empty_lines(source_normalized)
        translated_lines = cls._count_non_empty_lines(translated_normalized)

        source_units = cls._count_semantic_units(source_normalized)
        translated_units = cls._count_semantic_units(translated_normalized)
        if source_lines >= 8 and translated_lines <= 1 and source_units >= 8 and translated_units <= 2:
            return True
        if source_units >= 10 and translated_units <= max(2, source_units // 4):
            return True

        source_non_ws = cls._non_whitespace_length(source_normalized)
        translated_non_ws = cls._non_whitespace_length(translated_normalized)
        if source_non_ws >= 200 and translated_non_ws <= max(30, int(source_non_ws * 0.2)):
            return True

        return False

    @classmethod
    def _is_likely_extremely_short_translation(
        cls, source_text: str, translated_text: str
    ) -> bool:
        """Detect chunk-level outputs that are implausibly short for the input."""
        source_non_ws = cls._non_whitespace_length(source_text)
        translated_non_ws = cls._non_whitespace_length(translated_text)
        if source_non_ws < 80:
            return False
        return translated_non_ws <= max(12, int(source_non_ws * 0.08))

    @staticmethod
    def _split_translation_chunks(text: str, *, max_chunk_chars: int = 220) -> List[str]:
        """Split translation input into compact chunks while preserving line boundaries."""
        normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
        if not normalized:
            return []

        chunks: List[str] = []

        def append_fragments(fragment: str) -> None:
            text_part = fragment.strip()
            if not text_part:
                return
            if len(text_part) <= max_chunk_chars:
                chunks.append(text_part)
                return

            sub_parts = [part.strip() for part in re.split(r"(?<=[，,、])", text_part) if part.strip()]
            if not sub_parts:
                sub_parts = [text_part]

            for sub_part in sub_parts:
                if len(sub_part) <= max_chunk_chars:
                    chunks.append(sub_part)
                    continue
                for start in range(0, len(sub_part), max_chunk_chars):
                    piece = sub_part[start : start + max_chunk_chars].strip()
                    if piece:
                        chunks.append(piece)

        for line in normalized.split("\n"):
            line_text = line.strip()
            if not line_text:
                continue
            sentence_parts = [
                segment.strip()
                for segment in re.split(r"(?<=[。！？.!?;；])", line_text)
                if segment.strip()
            ]
            if not sentence_parts:
                sentence_parts = [line_text]
            for sentence in sentence_parts:
                append_fragments(sentence)
        return chunks

    def _resolve_translation_output_path(
        self,
        *,
        base_path: Path,
        target_lang: str,
        event_id: Optional[str],
        extension: str,
    ) -> Path:
        """Resolve translation output path with attachment overwrite preference."""
        normalized_extension = extension.lstrip(".") or "txt"
        if event_id:
            existing_attachment = EventAttachment.get_by_event_and_type(
                self.db, event_id, "translation"
            )
            if existing_attachment and existing_attachment.file_path:
                return Path(existing_attachment.file_path).expanduser().resolve()

        translation_filename = f"{base_path.stem}_translation_{target_lang}.{normalized_extension}"
        return base_path.parent / translation_filename

    def _write_translation_output(self, *, text: str, output_format: str, output_path: Path) -> None:
        """Write translated text to output format without transcription-specific conversion."""
        normalized_format = output_format.lower()
        if normalized_format not in TRANSLATION_OUTPUT_FORMATS:
            raise ValueError(
                f"Translation output_format must be one of: {', '.join(sorted(TRANSLATION_OUTPUT_FORMATS))}"
            )
        self._write_translation_file(output_path, text)

    @staticmethod
    def _write_translation_file(path: Path, text: str) -> None:
        """Persist translated text to disk."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        try:
            os.chmod(path, 0o600)
        except Exception:
            pass

    def _upsert_translation_attachment(
        self, *, event_id: Optional[str], translation_path: Path
    ) -> None:
        """Upsert translation attachment record when event context is available."""
        if not event_id:
            return
        try:
            file_size = translation_path.stat().st_size if translation_path.exists() else None
            EventAttachment.upsert_for_event_type(
                db_connection=self.db,
                event_id=event_id,
                attachment_type="translation",
                file_path=str(translation_path),
                file_size=file_size,
            )
            logger.info("Translation attachment saved for event %s", event_id)
        except Exception as exc:
            logger.warning("Failed to save translation attachment: %s", exc)

    def _event_has_attachment_type(self, event_id: str, attachment_type: str) -> bool:
        """Return whether event currently has an attachment of a specific type."""
        try:
            attachment = EventAttachment.get_by_event_and_type(self.db, event_id, attachment_type)
            return bool(attachment and attachment.file_path)
        except Exception:
            return False

    def _remove_event_attachment_by_type(self, *, event_id: str, attachment_type: str) -> bool:
        """Remove event attachment metadata for a given type."""
        try:
            attachment = EventAttachment.get_by_event_and_type(self.db, event_id, attachment_type)
        except Exception as exc:
            logger.warning(
                "Failed to query %s attachment for event %s before delete: %s",
                attachment_type,
                event_id,
                exc,
            )
            return False

        if not attachment:
            return False

        try:
            attachment.delete(self.db)
            return True
        except Exception as exc:
            logger.warning(
                "Failed to delete %s attachment for event %s: %s",
                attachment_type,
                event_id,
                exc,
            )
            return False

    def _read_event_attachment_text(self, *, event_id: str, attachment_type: str) -> str:
        """Best-effort load textual attachment content for quality checks."""
        try:
            attachment = EventAttachment.get_by_event_and_type(self.db, event_id, attachment_type)
        except Exception as exc:
            logger.warning(
                "Failed to query %s attachment for event %s: %s",
                attachment_type,
                event_id,
                exc,
            )
            return ""

        if not attachment or not attachment.file_path:
            return ""

        attachment_path = Path(attachment.file_path).expanduser()
        if not attachment_path.exists():
            return ""

        try:
            return attachment_path.read_text(encoding="utf-8")
        except Exception as exc:
            logger.warning(
                "Failed to read %s attachment text %s for event %s: %s",
                attachment_type,
                attachment_path,
                event_id,
                exc,
            )
            return ""

    def _set_task_quality_note(self, task_id: Optional[str], note: Optional[str]) -> None:
        """Attach deduplicated quality notes to task payloads."""
        if not task_id:
            return
        normalized = (note or "").strip()
        if not normalized:
            return

        existing = self._task_quality_notes.get(task_id)
        if not existing:
            self._task_quality_notes[task_id] = normalized
            return
        if normalized in existing:
            return
        self._task_quality_notes[task_id] = f"{existing}; {normalized}"

    def _resolve_realtime_transcript_path(
        self, task: TranscriptionTask, event_id: Optional[str]
    ) -> Path:
        """Pick replacement transcript path, preferring existing event transcript attachment."""
        if event_id:
            attachment = EventAttachment.get_by_event_and_type(self.db, event_id, "transcript")
            if attachment and attachment.file_path:
                return Path(attachment.file_path)
        return Path(task.file_path).with_suffix(".txt")

    def _cleanup_after_cancellation(self, task_id: str) -> None:
        """Clean up resources after task cancellation."""
        if task_id in self._task_engine_options:
            del self._task_engine_options[task_id]
            self._persist_task_engine_options()
        self._task_quality_notes.pop(task_id, None)

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
            "quality_note": self._task_quality_notes.get(task.id),
            "created_at": task.created_at,
            "started_at": task.started_at,
            "completed_at": task.completed_at,
            "task_kind": self._resolve_task_kind(task=task, task_id=task.id),
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
        self._task_quality_notes.pop(task_id, None)

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
                "quality_note": self._task_quality_notes.get(task.id),
                "created_at": task.created_at,
                "started_at": task.started_at,
                "completed_at": task.completed_at,
                "task_kind": self._resolve_task_kind(task=task, task_id=task.id),
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
        self._task_quality_notes.pop(task_id, None)

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

        task_kind = self._resolve_task_kind(task=task, task_id=task.id)
        if task_kind == TRANSLATION_TASK_KIND and output_format.lower() in {"txt", "md"}:
            formatted_content = self._resolve_translation_export_text(task, content)
        else:
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

    def _resolve_translation_export_text(
        self, task: TranscriptionTask, content: Dict[str, Any]
    ) -> str:
        """Resolve raw translation text for txt/md export without template conversion."""
        if task.output_path:
            output_file = Path(task.output_path).expanduser().resolve()
            if output_file.exists():
                try:
                    return output_file.read_text(encoding="utf-8")
                except Exception as exc:
                    logger.warning(
                        "Failed to read existing translation output file %s: %s",
                        output_file,
                        exc,
                    )

        text = content.get("text")
        if isinstance(text, str):
            return text
        return self.format_converter.convert(content, "txt")

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
            task_kind = self._resolve_task_kind(task_id=task_id)
            payload = {
                "id": task_id,
                "progress": progress,
                "status": "processing",
                "message": message,
            }
            quality_note = self._task_quality_notes.get(task_id)
            if quality_note:
                payload["quality_note"] = quality_note
            if task_kind:
                payload["task_kind"] = task_kind
            self._notify_listeners(
                "task_updated",
                payload,
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
