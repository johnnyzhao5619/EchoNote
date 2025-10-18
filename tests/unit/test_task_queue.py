import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.transcription.task_queue import TaskQueue


def test_completed_task_removed_after_processing():
    async def _run():
        queue = TaskQueue(max_concurrent=1, max_retries=0)

        async def successful_task(value):
            await asyncio.sleep(0)
            return value

        try:
            await queue.start()
            await queue.add_task("task-success", successful_task, 42)
            await queue.wait_for_completion()

            assert queue.get_status("task-success") is None
            assert "task-success" not in queue.tasks
            assert queue.get_all_tasks() == {}
        finally:
            await queue.stop()

    asyncio.run(_run())


def test_cancelled_task_removed_after_processing():
    async def _run():
        queue = TaskQueue(max_concurrent=1, max_retries=0)

        async def long_running_task():
            await asyncio.sleep(0.1)

        try:
            await queue.add_task("task-cancel", long_running_task)
            cancelled = await queue.cancel_task("task-cancel")
            assert cancelled is True

            await queue.start()
            await queue.wait_for_completion()

            assert queue.get_status("task-cancel") is None
            assert "task-cancel" not in queue.tasks
        finally:
            await queue.stop()

    asyncio.run(_run())


def test_duplicate_task_does_not_expand_tasks():
    async def _run():
        queue = TaskQueue(max_concurrent=1, max_retries=0)

        async def noop_task():
            await asyncio.sleep(0)

        try:
            await queue.add_task("duplicate", noop_task)
            initial_size = len(queue.tasks)

            await queue.add_task("duplicate", noop_task)
            assert len(queue.tasks) == initial_size

            await queue.start()
            await queue.wait_for_completion()

            assert queue.get_status("duplicate") is None
        finally:
            await queue.stop()

    asyncio.run(_run())


def test_failed_task_removed_after_retries():
    async def _run():
        queue = TaskQueue(max_concurrent=1, max_retries=1, retry_delay=0)

        async def failing_task():
            raise RuntimeError("boom")

        try:
            await queue.add_task("task-fail", failing_task)
            await queue.start()
            await queue.wait_for_completion()

            assert queue.get_status("task-fail") is None
            assert "task-fail" not in queue.tasks
        finally:
            await queue.stop()

    asyncio.run(_run())
