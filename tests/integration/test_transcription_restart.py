import asyncio
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from queue import Queue

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tests.unit.test_transcription_manager_failure import (  # type: ignore
    _ensure_cryptography_stubs,
    _ensure_numpy_stub,
)

_ensure_cryptography_stubs()
_ensure_numpy_stub()

from core.transcription.manager import TranscriptionManager
from data.database.connection import DatabaseConnection
from data.database.models import TranscriptionTask


class ControlledSpeechEngine:
    """Speech engine stub that waits for an external signal to finish."""

    def __init__(self, finish_event: threading.Event, started_queue: Queue):
        self._finish_event = finish_event
        self._started_queue = started_queue

    def get_name(self) -> str:
        return "controlled-stub"

    async def transcribe_file(self, file_path, language=None, progress_callback=None):
        file_name = Path(file_path).name
        self._started_queue.put(file_name)

        if progress_callback:
            progress_callback(25.0)

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._finish_event.wait)

        if progress_callback:
            progress_callback(75.0)

        return {
            "text": f"Transcript for {file_name}",
            "segments": [
                {
                    "start": 0.0,
                    "end": 1.0,
                    "text": f"Transcript for {file_name}"
                }
            ],
            "duration": 1.0,
        }


def wait_for_status(db: DatabaseConnection, task_id: str, expected_status: str, timeout: float = 5.0) -> bool:
    """Poll the database until the task reaches the expected status."""

    deadline = time.time() + timeout
    while time.time() < deadline:
        rows = db.execute(
            "SELECT status FROM transcription_tasks WHERE id = ?",
            (task_id,)
        )
        if rows and rows[0]["status"] == expected_status:
            return True
        time.sleep(0.05)
    return False


def test_tasks_resume_after_restart(tmp_path):
    db_path = tmp_path / "restart.db"
    db = DatabaseConnection(str(db_path))
    db.initialize_schema()

    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()

    file_one = audio_dir / "first.wav"
    file_one.write_bytes(b"audio-data-1")
    file_two = audio_dir / "second.wav"
    file_two.write_bytes(b"audio-data-2")

    pending_task = TranscriptionTask(
        file_path=str(file_one),
        file_name=file_one.name,
        status="pending"
    )
    pending_task.save(db)

    processing_task = TranscriptionTask(
        file_path=str(file_two),
        file_name=file_two.name,
        status="processing",
        progress=45.0,
        started_at=datetime.now().isoformat()
    )
    processing_task.save(db)

    finish_event = threading.Event()
    started_queue: Queue = Queue()
    engine = ControlledSpeechEngine(finish_event, started_queue)
    manager = TranscriptionManager(
        db,
        engine,
        config={"max_concurrent_tasks": 1}
    )

    manager2 = None
    finish_event2 = None

    try:
        manager.start_processing()

        first_started = started_queue.get(timeout=5)
        assert first_started in {file_one.name, file_two.name}

        finish_event.set()

        second_started = started_queue.get(timeout=5)
        assert {first_started, second_started} == {file_one.name, file_two.name}

        assert wait_for_status(db, pending_task.id, "completed")
        assert wait_for_status(db, processing_task.id, "completed")

        all_statuses = {task['status'] for task in manager.get_all_tasks()}
        assert all_statuses == {"completed"}

        manager.stop_processing()

        # Verify tasks added before the loop starts are also processed after restart
        finish_event2 = threading.Event()
        started_queue2: Queue = Queue()
        engine2 = ControlledSpeechEngine(finish_event2, started_queue2)

        manager2 = TranscriptionManager(
            db,
            engine2,
            config={"max_concurrent_tasks": 1}
        )

        third_file = audio_dir / "third.wav"
        third_file.write_bytes(b"audio-data-3")

        queued_task_id = manager2.add_task(str(third_file))
        manager2.start_processing()

        started_name = started_queue2.get(timeout=5)
        assert started_name == third_file.name

        finish_event2.set()
        assert wait_for_status(db, queued_task_id, "completed")

        manager2.stop_processing()
    finally:
        finish_event.set()
        manager.stop_processing()
        if finish_event2 is not None:
            finish_event2.set()
        if manager2 is not None:
            manager2.stop_processing()
