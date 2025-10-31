# SPDX-License-Identifier: Apache-2.0
"""
Unit tests for TaskQueue - Simplified version.

Tests asynchronous task queue with concurrency control, retry logic,
and cancellation support.
"""

import asyncio

import pytest

from core.transcription.task_queue import TaskQueue, TaskStatus


class TestTaskQueueBasics:
    """Test suite for TaskQueue basic functionality."""

    def test_init_default_params(self):
        """Test TaskQueue initialization with default parameters."""
        queue = TaskQueue()

        assert queue.max_concurrent == 2
        assert queue.max_retries == 3
        assert queue.retry_delay == 1.0
        assert not queue.running
        assert not queue.paused

    def test_init_custom_params(self):
        """Test TaskQueue initialization with custom parameters."""
        queue = TaskQueue(max_concurrent=5, max_retries=2, retry_delay=0.5)

        assert queue.max_concurrent == 5
        assert queue.max_retries == 2
        assert queue.retry_delay == 0.5

    @pytest.mark.asyncio
    async def test_add_task_success(self):
        """Test adding a task to the queue."""
        queue = TaskQueue()
        
        async def sample_task(cancel_event):
            return "result"

        await queue.add_task("task1", sample_task)

        assert "task1" in queue.tasks
        assert queue.tasks["task1"]["status"] == TaskStatus.PENDING

    @pytest.mark.asyncio
    async def test_start_and_stop_queue(self):
        """Test starting and stopping the task queue."""
        queue = TaskQueue(max_concurrent=2)
        
        await queue.start()
        assert queue.running
        assert len(queue.worker_tasks) == 2

        await queue.stop()
        assert not queue.running
        assert len(queue.worker_tasks) == 0

    @pytest.mark.asyncio
    async def test_process_simple_task(self):
        """Test processing a simple task."""
        queue = TaskQueue(max_concurrent=2, retry_delay=0.1)
        await queue.start()

        result_value = "success"

        async def simple_task(cancel_event):
            await asyncio.sleep(0.01)
            return result_value

        await queue.add_task("task1", simple_task)
        await queue.wait_for_completion()

        await queue.stop()

    @pytest.mark.asyncio
    async def test_process_multiple_tasks(self):
        """Test processing multiple tasks concurrently."""
        queue = TaskQueue(max_concurrent=2, retry_delay=0.1)
        await queue.start()

        results = []

        async def task_func(task_id, cancel_event):
            await asyncio.sleep(0.01)
            results.append(task_id)
            return f"result_{task_id}"

        await queue.add_task("task1", task_func, "task1")
        await queue.add_task("task2", task_func, "task2")
        await queue.add_task("task3", task_func, "task3")

        await queue.wait_for_completion()

        assert len(results) == 3
        assert "task1" in results
        assert "task2" in results
        assert "task3" in results

        await queue.stop()

    @pytest.mark.asyncio
    async def test_task_failure_with_retry(self):
        """Test task failure triggers retry logic."""
        queue = TaskQueue(max_concurrent=1, max_retries=2, retry_delay=0.05)
        await queue.start()

        attempt_count = 0

        async def failing_task(cancel_event):
            nonlocal attempt_count
            attempt_count += 1
            raise ValueError("Task failed")

        await queue.add_task("task1", failing_task)
        await queue.wait_for_completion()

        # Should retry max_retries + 1 times (initial + retries)
        assert attempt_count == queue.max_retries + 1

        await queue.stop()

    @pytest.mark.asyncio
    async def test_pause_and_resume(self):
        """Test pausing and resuming the queue."""
        queue = TaskQueue(max_concurrent=2)
        await queue.start()

        await queue.pause()
        assert queue.paused
        assert queue.is_paused()

        await queue.resume()
        assert not queue.paused
        assert not queue.is_paused()

        await queue.stop()

    @pytest.mark.asyncio
    async def test_cancel_task(self):
        """Test cancelling a pending task."""
        queue = TaskQueue(max_concurrent=1, retry_delay=0.1)
        await queue.start()

        async def long_task(cancel_event):
            for _ in range(100):
                if cancel_event.is_set():
                    raise asyncio.CancelledError()
                await asyncio.sleep(0.01)
            return "result"

        await queue.add_task("task1", long_task)
        await asyncio.sleep(0.01)  # Let it start

        cancelled = await queue.cancel_task("task1")
        assert cancelled

        await queue.stop()

    @pytest.mark.asyncio
    async def test_get_status(self):
        """Test getting task status."""
        queue = TaskQueue()

        async def sample_task(cancel_event):
            return "result"

        await queue.add_task("task1", sample_task)

        status = queue.get_status("task1")
        assert status == "pending"

        # Nonexistent task
        status = queue.get_status("nonexistent")
        assert status is None

    @pytest.mark.asyncio
    async def test_get_task_info(self):
        """Test getting detailed task information."""
        queue = TaskQueue()

        async def sample_task(cancel_event):
            return "result"

        await queue.add_task("task1", sample_task)

        info = queue.get_task_info("task1")

        assert info is not None
        assert info["status"] == "pending"
        assert info["result"] is None
        assert info["error"] is None
        assert info["retry_count"] == 0

    @pytest.mark.asyncio
    async def test_concurrency_limit(self):
        """Test that concurrency limit is respected."""
        max_concurrent = 2
        queue = TaskQueue(max_concurrent=max_concurrent, retry_delay=0.1)
        await queue.start()

        active_count = 0
        max_active = 0
        lock = asyncio.Lock()

        async def concurrent_task(cancel_event):
            nonlocal active_count, max_active
            async with lock:
                active_count += 1
                max_active = max(max_active, active_count)

            await asyncio.sleep(0.1)

            async with lock:
                active_count -= 1

        # Add more tasks than max_concurrent
        for i in range(5):
            await queue.add_task(f"task{i}", concurrent_task)

        await queue.wait_for_completion()
        await queue.stop()

        # Max active should not exceed max_concurrent
        assert max_active <= max_concurrent


class TestTaskStatus:
    """Test suite for TaskStatus enum."""

    def test_task_status_values(self):
        """Test TaskStatus enum values."""
        assert TaskStatus.PENDING.value == "pending"
        assert TaskStatus.PROCESSING.value == "processing"
        assert TaskStatus.COMPLETED.value == "completed"
        assert TaskStatus.FAILED.value == "failed"
        assert TaskStatus.CANCELLED.value == "cancelled"

    def test_get_display_name_without_i18n(self):
        """Test getting display name without i18n manager."""
        assert TaskStatus.PENDING.get_display_name() == "Pending"
        assert TaskStatus.PROCESSING.get_display_name() == "Processing"
        assert TaskStatus.COMPLETED.get_display_name() == "Completed"
        assert TaskStatus.FAILED.get_display_name() == "Failed"
        assert TaskStatus.CANCELLED.get_display_name() == "Cancelled"

    def test_get_display_name_with_i18n(self):
        """Test getting display name with i18n manager."""
        class MockI18n:
            def t(self, key):
                return f"translated_{key}"

        i18n = MockI18n()

        result = TaskStatus.PENDING.get_display_name(i18n)
        assert result == "translated_constants.task_status.pending"
