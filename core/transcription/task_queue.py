"""
Asynchronous task queue for transcription processing.

Manages concurrent task execution with configurable limits.
"""

import asyncio
import logging
from typing import Dict, Callable, Any, Optional
from enum import Enum


logger = logging.getLogger('echonote.transcription.task_queue')


class TaskStatus(Enum):
    """Task status enumeration."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskQueue:
    """
    Asynchronous task queue with concurrency control.
    
    Manages task execution with configurable maximum concurrent tasks.
    Provides task status tracking and cancellation support.
    """
    
    def __init__(
        self,
        max_concurrent: int = 2,
        max_retries: int = 3,
        retry_delay: float = 1.0
    ):
        """
        Initialize task queue.
        
        Args:
            max_concurrent: Maximum number of concurrent tasks (default: 2)
            max_retries: Maximum number of retry attempts (default: 3)
            retry_delay: Initial delay between retries in seconds (default: 1.0)
        """
        self.max_concurrent = max_concurrent
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.queue = asyncio.Queue()
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.tasks: Dict[str, Dict[str, Any]] = {}
        self.running = False
        self.paused = False
        self.worker_tasks = []
        
        logger.info(
            f"Task queue initialized with max_concurrent={max_concurrent}, "
            f"max_retries={max_retries}"
        )
    
    async def add_task(
        self,
        task_id: str,
        task_func: Callable,
        *args,
        **kwargs
    ):
        """
        Add a task to the queue.
        
        Args:
            task_id: Unique task identifier
            task_func: Async function to execute
            *args: Positional arguments for task_func
            **kwargs: Keyword arguments for task_func
        """
        if task_id in self.tasks:
            logger.warning(f"Task {task_id} already exists in queue")
            return
        
        # Store task info
        self.tasks[task_id] = {
            'status': TaskStatus.PENDING,
            'func': task_func,
            'args': args,
            'kwargs': kwargs,
            'result': None,
            'error': None,
            'cancel_event': asyncio.Event(),
            'retry_count': 0
        }
        
        # Add to queue
        await self.queue.put(task_id)
        logger.info(f"Task {task_id} added to queue")
    
    async def start(self):
        """Start processing tasks from the queue."""
        if self.running:
            logger.warning("Task queue is already running")
            return
        
        self.running = True
        logger.info("Starting task queue processing")
        
        # Create worker tasks
        self.worker_tasks = [
            asyncio.create_task(self._worker(i))
            for i in range(self.max_concurrent)
        ]
        
        logger.info(f"Started {self.max_concurrent} worker tasks")
    
    async def stop(self):
        """Stop processing tasks and wait for current tasks to complete."""
        if not self.running:
            return
        
        logger.info("Stopping task queue")
        self.running = False
        
        # Cancel all worker tasks
        for worker in self.worker_tasks:
            worker.cancel()
        
        # Wait for workers to finish
        await asyncio.gather(*self.worker_tasks, return_exceptions=True)
        self.worker_tasks = []
        
        logger.info("Task queue stopped")

    async def pause(self):
        """Pause processing new tasks (current tasks continue)."""
        if self.paused:
            logger.warning("Task queue is already paused")
            return

        self.paused = True
        logger.info("Task queue paused")

    async def resume(self):
        """Resume processing tasks."""
        if not self.paused:
            logger.warning("Task queue is not paused")
            return

        self.paused = False
        logger.info("Task queue resumed")

    def is_paused(self) -> bool:
        """Check if queue is paused."""
        return self.paused
    
    async def _worker(self, worker_id: int):
        """
        Worker coroutine that processes tasks from the queue.
        
        Args:
            worker_id: Worker identifier for logging
        """
        logger.debug(f"Worker {worker_id} started")
        
        while self.running:
            # Check if paused
            if self.paused:
                await asyncio.sleep(1.0)
                continue

            try:
                # Get task from queue with timeout
                task_id = await asyncio.wait_for(
                    self.queue.get(),
                    timeout=1.0
                )
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                logger.debug(f"Worker {worker_id} cancelled")
                break
            
            # Check again if paused (task was retrieved but queue is paused)
            if self.paused:
                # Put task back in queue
                await self.queue.put(task_id)
                await asyncio.sleep(1.0)
                continue

            # Process task
            await self._process_task(task_id, worker_id)
            self.queue.task_done()
        
        logger.debug(f"Worker {worker_id} stopped")
    
    async def _process_task(self, task_id: str, worker_id: int):
        """
        Process a single task with retry logic.
        
        Args:
            task_id: Task identifier
            worker_id: Worker identifier for logging
        """
        if task_id not in self.tasks:
            logger.error(f"Task {task_id} not found in tasks dict")
            return
        
        task_info = self.tasks[task_id]
        
        # Check if task was cancelled
        if task_info['cancel_event'].is_set():
            task_info['status'] = TaskStatus.CANCELLED
            logger.info(f"Task {task_id} was cancelled before processing")
            return
        
        # Acquire semaphore to limit concurrency
        async with self.semaphore:
            # Update status
            task_info['status'] = TaskStatus.PROCESSING
            logger.info(f"Worker {worker_id} processing task {task_id}")
            
            # Retry loop
            while task_info['retry_count'] <= self.max_retries:
                try:
                    # Execute task function
                    result = await task_info['func'](
                        *task_info['args'],
                        **task_info['kwargs']
                    )
                    
                    # Check if cancelled during execution
                    if task_info['cancel_event'].is_set():
                        task_info['status'] = TaskStatus.CANCELLED
                        logger.info(
                            f"Task {task_id} was cancelled during processing"
                        )
                    else:
                        task_info['status'] = TaskStatus.COMPLETED
                        task_info['result'] = result
                        logger.info(f"Task {task_id} completed successfully")
                    
                    # Success, break retry loop
                    break
                    
                except Exception as e:
                    task_info['retry_count'] += 1
                    task_info['error'] = str(e)
                    
                    if task_info['retry_count'] <= self.max_retries:
                        # Calculate exponential backoff delay
                        delay = self.retry_delay * (2 ** (task_info['retry_count'] - 1))
                        
                        logger.warning(
                            f"Task {task_id} failed (attempt "
                            f"{task_info['retry_count']}/{self.max_retries}): {e}. "
                            f"Retrying in {delay:.1f}s..."
                        )
                        
                        # Wait before retry
                        await asyncio.sleep(delay)
                    else:
                        # Max retries exceeded
                        task_info['status'] = TaskStatus.FAILED
                        logger.error(
                            f"Task {task_id} failed after {self.max_retries} "
                            f"retries: {e}",
                            exc_info=True
                        )
                        break
    
    def get_status(self, task_id: str) -> Optional[str]:
        """
        Get the status of a task.
        
        Args:
            task_id: Task identifier
        
        Returns:
            Task status string, or None if task not found
        """
        if task_id not in self.tasks:
            return None
        
        return self.tasks[task_id]['status'].value
    
    def get_task_info(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a task.
        
        Args:
            task_id: Task identifier
        
        Returns:
            Dict with task info, or None if task not found
        """
        if task_id not in self.tasks:
            return None
        
        task_info = self.tasks[task_id]
        return {
            'status': task_info['status'].value,
            'result': task_info['result'],
            'error': task_info['error'],
            'retry_count': task_info['retry_count']
        }
    
    async def cancel_task(self, task_id: str) -> bool:
        """
        Cancel a task.
        
        Args:
            task_id: Task identifier
        
        Returns:
            True if task was cancelled, False if not found or already completed
        """
        if task_id not in self.tasks:
            logger.warning(f"Cannot cancel task {task_id}: not found")
            return False
        
        task_info = self.tasks[task_id]
        
        # Can only cancel pending or processing tasks
        if task_info['status'] in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
            logger.warning(
                f"Cannot cancel task {task_id}: "
                f"already in status {task_info['status'].value}"
            )
            return False
        
        # Set cancel event
        task_info['cancel_event'].set()
        logger.info(f"Task {task_id} cancellation requested")
        return True
    
    def get_queue_size(self) -> int:
        """
        Get the number of pending tasks in the queue.
        
        Returns:
            Number of pending tasks
        """
        return self.queue.qsize()
    
    def get_all_tasks(self) -> Dict[str, str]:
        """
        Get status of all tasks.
        
        Returns:
            Dict mapping task_id to status string
        """
        return {
            task_id: task_info['status'].value
            for task_id, task_info in self.tasks.items()
        }
    
    async def wait_for_completion(self):
        """Wait for all tasks in the queue to complete."""
        await self.queue.join()
        logger.info("All tasks completed")
