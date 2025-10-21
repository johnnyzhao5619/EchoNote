"""
Transcription manager for batch audio file processing.

Manages transcription tasks, coordinates speech engines, and handles
task lifecycle from creation to completion.
"""

import asyncio
import json
import logging
import os
import threading
from pathlib import Path
from typing import Callable, Dict, List, Optional, Any, Tuple
from datetime import datetime

from data.database.connection import DatabaseConnection
from data.database.models import TranscriptionTask
from engines.speech.base import SpeechEngine
from core.transcription.task_queue import TaskQueue
from core.transcription.format_converter import FormatConverter
from config.app_config import get_app_dir
from ui.common.notification import get_notification_manager


logger = logging.getLogger('echonote.transcription.manager')


# Supported audio/video formats
SUPPORTED_FORMATS = {
    '.mp3', '.wav', '.m4a', '.flac', '.ogg', '.opus',
    '.mp4', '.avi', '.mkv', '.mov', '.webm'
}


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
        config: Optional[Dict[str, Any]] = None
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

        self._default_save_path: Optional[str] = None
        raw_default_path = self.config.get('default_save_path')
        if isinstance(raw_default_path, (str, os.PathLike)) and raw_default_path:
            try:
                default_path = Path(raw_default_path).expanduser()
                default_path = default_path.resolve()
                default_path.mkdir(parents=True, exist_ok=True)
                try:
                    os.chmod(default_path, 0o700)
                except Exception as permission_error:
                    logger.warning(
                        f"Could not set directory permissions for default save path {default_path}: "
                        f"{permission_error}"
                    )
                self._default_save_path = str(default_path)
            except Exception as exc:
                logger.error(
                    f"Failed to prepare default save path '{raw_default_path}': {exc}",
                    exc_info=True
                )
        elif raw_default_path:
            logger.warning(
                f"Ignoring default_save_path with unsupported type: {type(raw_default_path).__name__}"
            )

        task_queue_config = self.config.get('task_queue', {})
        if not isinstance(task_queue_config, dict):
            task_queue_config = {}

        def _resolve_queue_setting(key: str, fallback: Any) -> Any:
            if key in task_queue_config:
                return task_queue_config[key]
            if key in self.config:
                return self.config[key]
            return fallback

        # Initialize task queue
        max_concurrent = _resolve_queue_setting('max_concurrent_tasks', 2)
        max_retries = _resolve_queue_setting('max_retries', 3)
        retry_delay = _resolve_queue_setting('retry_delay', 1.0)
        self.task_queue = TaskQueue(
            max_concurrent=max_concurrent,
            max_retries=max_retries,
            retry_delay=retry_delay
        )

        self._default_output_format = self.config.get('default_output_format', 'txt')
        
        # Initialize format converter
        self.format_converter = FormatConverter()
        
        # Progress callbacks (task_id -> callback function)
        self.progress_callbacks: Dict[str, callable] = {}

        # Background thread and event loop for async operations
        self._loop = None
        self._thread = None
        self._running = False

        # Queue scheduling buffer for tasks added before loop starts
        self._queue_buffer_lock = threading.Lock()
        self._pending_queue_entries: Dict[str, Tuple[Callable, tuple, dict]] = {}
        
        logger.info(
            f"Transcription manager initialized with engine: "
            f"{speech_engine.get_name()}"
        )

    def _store_task_for_later(
        self,
        task_id: str,
        task_func,
        *args,
        **kwargs
    ) -> None:
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

        asyncio.run_coroutine_threadsafe(
            self._drain_buffered_tasks(),
            self._loop
        )

    def _queue_or_buffer_task(self, task_id: str) -> bool:
        """Queue the task immediately if possible, otherwise cache it."""
        if self._loop and self._loop.is_running():
            import asyncio

            try:
                asyncio.run_coroutine_threadsafe(
                    self.task_queue.add_task(
                        task_id,
                        self._process_task_async,
                        task_id
                    ),
                    self._loop
                )
                return True
            except RuntimeError as exc:
                logger.warning(
                    f"Event loop not ready for task {task_id}: {exc}. Caching for later"
                )

        self._store_task_for_later(
            task_id,
            self._process_task_async,
            task_id
        )
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
                logger.error(
                    f"Failed to schedule buffered task {task_id}: {exc}",
                    exc_info=True
                )

    def add_task(
        self,
        file_path: str,
        options: Optional[Dict[str, Any]] = None
    ) -> str:
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
        
        # Validate file exists
        file_path = Path(file_path).expanduser().resolve()
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # Validate file format
        if file_path.suffix.lower() not in SUPPORTED_FORMATS:
            raise ValueError(
                f"Unsupported file format: {file_path.suffix}. "
                f"Supported formats: {', '.join(sorted(SUPPORTED_FORMATS))}"
            )
        
        # Create task record
        task = TranscriptionTask(
            file_path=str(file_path),
            file_name=file_path.name,
            file_size=file_path.stat().st_size,
            status="pending",
            language=options.get('language'),
            engine=self.speech_engine.get_name(),
            output_format=options.get(
                'output_format',
                self._default_output_format
            ),
            output_path=options.get('output_path')
        )
        
        # Save to database
        task.save(self.db)
        
        # Add to task queue (schedule in background event loop)
        if not self._queue_or_buffer_task(task.id):
            logger.info(
                f"Task queue not ready, task {task.id} cached until processing starts"
            )

        logger.info(f"Added transcription task: {task.id} for file {file_path.name}")
        return task.id
    
    def add_tasks_from_folder(
        self,
        folder_path: str,
        options: Optional[Dict[str, Any]] = None
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
        for file_path in folder_path.rglob('*'):
            if file_path.is_file() and file_path.suffix.lower() in SUPPORTED_FORMATS:
                try:
                    task_id = self.add_task(str(file_path), options)
                    task_ids.append(task_id)
                except Exception as e:
                    logger.error(f"Failed to add task for {file_path}: {e}")
        
        logger.info(
            f"Added {len(task_ids)} transcription tasks from folder {folder_path}"
        )
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
            processing_ids = [row['id'] for row in rows if row['status'] == 'processing']

            if processing_ids:
                try:
                    self.db.execute_many(
                        "UPDATE transcription_tasks "
                        "SET status = 'pending', progress = 0, started_at = NULL "
                        "WHERE id = ?",
                        [(task_id,) for task_id in processing_ids]
                    )
                    logger.info(
                        f"Reset {len(processing_ids)} tasks stuck in processing state"
                    )
                except Exception as exc:
                    logger.error(
                        f"Failed to reset processing tasks before restart: {exc}",
                        exc_info=True
                    )

            for row in rows:
                # Ensure any stale queue state is removed before re-adding
                self.task_queue.tasks.pop(row['id'], None)
                self._store_task_for_later(
                    row['id'],
                    self._process_task_async,
                    row['id']
                )

            logger.info(
                f"Queued {len(rows)} persisted tasks for background processing"
            )

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
                                task
                                for task in asyncio.all_tasks(loop=loop)
                                if not task.done()
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
                    logger.warning(
                        "Transcription event loop closed with prior shutdown errors"
                    )

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
                stop_future = asyncio.run_coroutine_threadsafe(
                    self.task_queue.stop(),
                    self._loop
                )
                stop_future.result(timeout=5.0)
            except Exception as exc:
                logger.warning(
                    "Failed to stop task queue gracefully: %s",
                    exc
                )
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
            future = asyncio.run_coroutine_threadsafe(
                self.task_queue.pause(),
                self._loop
            )
            try:
                future.result(timeout=2.0)
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
            future = asyncio.run_coroutine_threadsafe(
                self.task_queue.resume(),
                self._loop
            )
            try:
                future.result(timeout=2.0)
                logger.info("Resumed transcription task processing")
            except Exception as e:
                logger.error(f"Error resuming task queue: {e}")

    def is_paused(self) -> bool:
        """Check if task processing is paused."""
        return self.task_queue.is_paused() if self._running else False
    
    def has_running_tasks(self) -> bool:
        """
        Check if there are any running tasks.
        
        Returns:
            True if there are tasks in processing status
        """
        try:
            # Query database for tasks in processing status
            result = self.db.execute(
                "SELECT COUNT(*) as count FROM transcription_tasks "
                "WHERE status = 'processing'"
            )
            
            if result and len(result) > 0:
                count = result[0]['count']
                return count > 0
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking running tasks: {e}")
            return False
    
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
                "SELECT id FROM transcription_tasks "
                "WHERE status IN ('pending', 'processing')"
            )
            
            if pending_tasks:
                logger.info(f"Found {len(pending_tasks)} tasks to stop")
                
                # Cancel each task
                for task_row in pending_tasks:
                    task_id = task_row['id']
                    try:
                        self.cancel_task(task_id)
                    except Exception as e:
                        logger.error(f"Error cancelling task {task_id}: {e}")
            
            # Stop processing
            self.stop_processing()
            
            logger.info("All transcription tasks stopped")
            
        except Exception as e:
            logger.error(f"Error stopping all tasks: {e}")
    
    async def _process_task_async(
        self,
        task_id: str,
        *,
        cancel_event: asyncio.Event
    ):
        """
        Process a single transcription task (async wrapper).

        Args:
            task_id: Task identifier
        """
        task: Optional[TranscriptionTask] = None
        try:
            def ensure_not_cancelled(stage: str) -> None:
                if cancel_event.is_set():
                    logger.info(
                        "Cancellation detected for task %s %s",
                        task_id,
                        stage,
                    )
                    raise asyncio.CancelledError()

            ensure_not_cancelled("before loading task from database")

            # Load task from database
            task = TranscriptionTask.get_by_id(self.db, task_id)
            if not task:
                logger.error(f"Task {task_id} not found in database")
                return

            ensure_not_cancelled("after loading task from database")

            # Update status to processing
            task.status = "processing"
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
                    # Update task progress in database
                    # Direct SQL update to avoid model overhead in callback
                    query = "UPDATE transcription_tasks SET progress = ? WHERE id = ?"
                    self.db.execute(query, (progress, task_id), commit=True)
                    logger.debug(
                        f"Task {task_id} progress updated to {progress:.1f}% "
                        f"in database"
                    )
                    
                    # Notify registered callbacks
                    self._update_progress(task_id, progress, "Transcribing")
                except Exception as e:
                    logger.error(
                        f"Error updating progress for task {task_id}: {e}",
                        exc_info=True
                    )
            
            # Call speech engine to transcribe with progress callback
            self._update_progress(task_id, 10.0, "Loading audio file")

            # Also update database for 10% progress
            task.progress = 10.0
            task.save(self.db)
            logger.info(f"Task {task_id} progress set to 10%, starting transcription")

            # Call transcribe_file and log the start
            logger.info(f"Calling speech_engine.transcribe_file for task {task_id}")
            ensure_not_cancelled("before starting transcription")
            result = await self.speech_engine.transcribe_file(
                task.file_path,
                language=task.language,
                progress_callback=progress_callback
            )
            ensure_not_cancelled("after completing transcription")
            logger.info(f"Transcription completed for task {task_id}, processing results")

            # Extract audio duration if available
            if 'duration' in result:
                task.audio_duration = result['duration']

            # Update progress: saving results
            ensure_not_cancelled("before saving results")
            self._update_progress(task_id, 90.0, "Saving results")

            # Save internal format to file system
            # Note: Storing in file system instead of database to avoid
            # storing large JSON blobs in the database
            internal_format_path = self._get_internal_format_path(task_id)
            internal_format_path_obj = Path(internal_format_path)
            internal_format_path_obj.parent.mkdir(parents=True, exist_ok=True)

            # Write with secure permissions
            ensure_not_cancelled("before writing internal transcript")
            with open(internal_format_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)

            # Set secure file permissions (owner read/write only)
            import os
            try:
                os.chmod(internal_format_path, 0o600)
            except Exception as e:
                logger.warning(f"Could not set file permissions: {e}")

            # Update task status to completed FIRST
            # (export_result requires status to be "completed")
            ensure_not_cancelled("before marking task as completed")
            task.status = "completed"
            task.completed_at = datetime.now().isoformat()
            task.progress = 100.0
            task.save(self.db)

            # Automatically export to default format (TXT)
            # This ensures output_path is set for the viewer
            try:
                default_format = task.output_format or 'txt'

                # Generate default output path if not set
                if not task.output_path:
                    source_path = Path(task.file_path)
                    output_filename = f"{source_path.stem}.{default_format}"
                    if self._default_save_path:
                        output_dir = Path(self._default_save_path)
                    else:
                        output_dir = source_path.parent
                    output_path = output_dir / output_filename
                else:
                    output_path = Path(task.output_path)

                ensure_not_cancelled("before exporting results")
                self.export_result(
                    task_id,
                    output_format=default_format,
                    output_path=str(output_path)
                )
                logger.info(f"Task {task_id} exported to {output_path}")
            except Exception as export_error:
                logger.error(
                    f"Failed to export task {task_id}: {export_error}",
                    exc_info=True
                )
                # Continue anyway - the internal format is saved

            # Notify progress: completed
            self._update_progress(task_id, 100.0, "Completed")

            logger.info(f"Task {task_id} completed successfully")

            # Send completion notification
            ensure_not_cancelled("before sending completion notification")
            self._send_notification(
                f"Transcription completed: {task.file_name}",
                "success"
            )

        except asyncio.CancelledError:
            logger.info(f"Task {task_id} cancellation acknowledged, rolling back state")

            refreshed_task: Optional[TranscriptionTask] = None
            try:
                refreshed_task = TranscriptionTask.get_by_id(self.db, task_id)
            except Exception as fetch_error:
                logger.error(
                    f"Failed to reload task {task_id} during cancellation handling: {fetch_error}",
                    exc_info=True
                )

            task_for_update = refreshed_task or task
            progress_value = (
                task_for_update.progress
                if task_for_update and task_for_update.progress is not None
                else (task.progress if task and task.progress is not None else 0.0)
            )

            if task_for_update:
                task_for_update.status = "cancelled"
                task_for_update.completed_at = datetime.now().isoformat()
                task_for_update.error_message = None
                if task_for_update.progress is None:
                    task_for_update.progress = progress_value
                try:
                    task_for_update.save(self.db)
                except Exception as save_error:
                    logger.error(
                        f"Failed to record cancellation for task {task_id}: {save_error}",
                        exc_info=True
                    )

            self._update_progress(task_id, progress_value, "Cancelled")

            raise
        except Exception as e:
            logger.error(f"Task {task_id} failed: {e}", exc_info=True)

            refreshed_task: Optional[TranscriptionTask] = None
            try:
                refreshed_task = TranscriptionTask.get_by_id(self.db, task_id)
            except Exception as fetch_error:
                logger.error(
                    f"Failed to reload task {task_id} during error handling: {fetch_error}",
                    exc_info=True
                )

            task_for_update = refreshed_task or task
            progress_value = (
                task_for_update.progress
                if task_for_update and task_for_update.progress is not None
                else 0.0
            )
            file_name = (
                task_for_update.file_name
                if task_for_update and task_for_update.file_name
                else task_id
            )

            if task_for_update:
                task_for_update.status = "failed"
                task_for_update.error_message = str(e)
                task_for_update.completed_at = datetime.now().isoformat()
                if task_for_update.progress is None:
                    task_for_update.progress = progress_value
                try:
                    task_for_update.save(self.db)
                except Exception as save_error:
                    logger.error(
                        f"Failed to record failure for task {task_id}: {save_error}",
                        exc_info=True
                    )

            # Notify progress: failed
            self._update_progress(task_id, progress_value, f"Failed: {str(e)}")

            # Send failure notification
            self._send_notification(
                f"Transcription failed: {file_name}",
                "error"
            )

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
            'id': task.id,
            'file_name': task.file_name,
            'file_path': task.file_path,
            'file_size': task.file_size,
            'audio_duration': task.audio_duration,
            'status': task.status,
            'progress': task.progress,
            'language': task.language,
            'engine': task.engine,
            'output_format': task.output_format,
            'output_path': task.output_path,
            'error_message': task.error_message,
            'created_at': task.created_at,
            'started_at': task.started_at,
            'completed_at': task.completed_at
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
        import concurrent.futures
        
        # Cancel in queue (schedule in background event loop)
        future = asyncio.run_coroutine_threadsafe(
            self.task_queue.cancel_task(task_id),
            self._loop
        )
        
        try:
            cancelled = future.result(timeout=5.0)
            
            if cancelled:
                # Update database
                task = TranscriptionTask.get_by_id(self.db, task_id)
                if task:
                    task.status = "cancelled"
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
        task = TranscriptionTask.get_by_id(self.db, task_id)
        if not task:
            logger.warning(f"Cannot retry task {task_id}: not found")
            return False
        
        if task.status != "failed":
            logger.warning(
                f"Cannot retry task {task_id}: status is {task.status}, "
                f"not 'failed'"
            )
            return False
        
        # Reset task status
        task.status = "pending"
        task.progress = 0.0
        task.error_message = None
        task.started_at = None
        task.completed_at = None
        task.save(self.db)
        
        # Re-add to queue (schedule in background event loop)
        if self._loop and self._running:
            import asyncio
            asyncio.run_coroutine_threadsafe(
                self.task_queue.add_task(
                    task.id,
                    self._process_task_async,
                    task.id
                ),
                self._loop
            )
            logger.info(f"Task {task_id} queued for retry")
            return True
        else:
            logger.warning("Task queue not running, cannot retry task")
            return False
    
    def export_result(
        self,
        task_id: str,
        output_format: str,
        output_path: str
    ) -> str:
        """
        Export transcription result to a file.
        
        Args:
            task_id: Task identifier
            output_format: Output format (txt/srt/md)
            output_path: Path for output file
        
        Returns:
            Path to exported file
        
        Raises:
            ValueError: If task not found or not completed
            FileNotFoundError: If internal format file not found
        """
        task = TranscriptionTask.get_by_id(self.db, task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")
        
        if task.status != "completed":
            raise ValueError(
                f"Task {task_id} is not completed (status: {task.status})"
            )
        
        # Load internal format
        internal_format_path = self._get_internal_format_path(task_id)
        if not os.path.exists(internal_format_path):
            raise FileNotFoundError(
                f"Internal format file not found for task {task_id}"
            )
        
        with open(internal_format_path, 'r', encoding='utf-8') as f:
            internal_format = json.load(f)
        
        # Convert to requested format
        converted_text = self.format_converter.convert(
            internal_format,
            output_format
        )
        
        # Write to output file
        path_obj = Path(output_path).expanduser()
        try:
            resolved_output_path = path_obj.resolve()
        except Exception as exc:
            logger.error(
                f"Failed to resolve output path '{path_obj}': {exc}",
                exc_info=True
            )
            raise

        output_dir = resolved_output_path.parent
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            logger.error(
                f"Failed to create output directory '{output_dir}': {exc}",
                exc_info=True
            )
            raise

        # Set secure directory permissions
        try:
            os.chmod(output_dir, 0o700)
        except Exception as e:
            logger.warning(f"Could not set directory permissions: {e}")

        with open(resolved_output_path, 'w', encoding='utf-8') as f:
            f.write(converted_text)

        # Set secure file permissions (owner read/write only)
        try:
            os.chmod(resolved_output_path, 0o600)
        except Exception as e:
            logger.warning(f"Could not set file permissions: {e}")

        # Update task record
        task.output_path = str(resolved_output_path)
        task.output_format = output_format
        task.save(self.db)

        logger.info(
            f"Exported task {task_id} to {resolved_output_path} "
            f"in {output_format} format"
        )

        return str(resolved_output_path)
    
    def get_all_tasks(
        self,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
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
                'id': task.id,
                'file_name': task.file_name,
                'status': task.status,
                'progress': task.progress,
                'created_at': task.created_at
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
        
        # Delete internal format file
        internal_format_path = self._get_internal_format_path(task_id)
        if os.path.exists(internal_format_path):
            os.remove(internal_format_path)
        
        # Delete from database
        task.delete(self.db)
        
        logger.info(f"Deleted task {task_id}")
        return True
    
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
    
    def _update_progress(
        self,
        task_id: str,
        progress: float,
        message: str = ""
    ):
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
                logger.error(
                    f"Error calling progress callback for task {task_id}: {e}"
                )
        
        logger.debug(f"Task {task_id} progress: {progress:.1f}% - {message}")
    
    def _send_notification(self, message: str, notification_type: str):
        """
        Send desktop notification.

        Args:
            message: Notification message
            notification_type: Type of notification (success/error/info)
        """
        title = "EchoNote"

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
    
    def register_progress_callback(
        self,
        task_id: str,
        callback: callable
    ):
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
                f"Invalid max_concurrent value: {max_concurrent}. "
                f"Must be between 1 and 5."
            )
            return
        
        if max_concurrent == self.task_queue.max_concurrent:
            logger.debug(
                f"max_concurrent already set to {max_concurrent}, "
                f"no update needed"
            )
            return
        
        logger.info(
            f"Updating max_concurrent from "
            f"{self.task_queue.max_concurrent} to {max_concurrent}"
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

    def reload_engine(self):
        """
        Reload the speech engine with updated configuration.
        
        This method is called when API keys or engine settings are updated.
        It will reinitialize the engine with new credentials.
        """
        logger.info("Reloading speech engine with updated configuration...")
        
        try:
            # Get current engine type
            engine_name = self.speech_engine.get_name()
            logger.info(f"Current engine: {engine_name}")
            
            # For cloud engines, we need to reinitialize with new API keys
            # For local engines (faster-whisper), no reload needed
            if engine_name in ['openai-whisper', 'google-speech', 'azure-speech']:
                logger.info(f"Cloud engine detected: {engine_name}")
                logger.info("Note: Engine will use new API keys on next transcription")
                # Cloud engines typically load API keys on each request
                # So we don't need to reinitialize the engine itself
                # Just log that new keys will be used
            else:
                logger.info(f"Local engine detected: {engine_name}, no reload needed")
            
            logger.info("Speech engine reload completed")
            
        except Exception as e:
            logger.error(f"Error reloading speech engine: {e}")
            raise
