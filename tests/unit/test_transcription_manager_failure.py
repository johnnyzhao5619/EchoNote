import asyncio
import sys
import types
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _ensure_cryptography_stubs():
    if "cryptography" in sys.modules:
        return

    cryptography_module = types.ModuleType("cryptography")
    hazmat_module = types.ModuleType("cryptography.hazmat")
    primitives_module = types.ModuleType("cryptography.hazmat.primitives")
    ciphers_module = types.ModuleType("cryptography.hazmat.primitives.ciphers")
    aead_module = types.ModuleType("cryptography.hazmat.primitives.ciphers.aead")
    hashes_module = types.ModuleType("cryptography.hazmat.primitives.hashes")
    kdf_module = types.ModuleType("cryptography.hazmat.primitives.kdf")
    pbkdf2_module = types.ModuleType("cryptography.hazmat.primitives.kdf.pbkdf2")

    class _DummyAESGCM:
        def __init__(self, key):
            self._key = key

        def encrypt(self, nonce, data, associated_data=None):
            return data

        def decrypt(self, nonce, data, associated_data=None):
            return data

    class _DummySHA256:
        name = "sha256"

    class _DummyPBKDF2HMAC:
        def __init__(self, algorithm, length, salt, iterations):
            self._length = length

        def derive(self, data):
            if not data:
                return b"\x00" * self._length
            repeated = (data * ((self._length // len(data)) + 1))[: self._length]
            return repeated

    aead_module.AESGCM = _DummyAESGCM
    hashes_module.SHA256 = _DummySHA256
    pbkdf2_module.PBKDF2HMAC = _DummyPBKDF2HMAC

    cryptography_module.hazmat = hazmat_module
    hazmat_module.primitives = primitives_module
    primitives_module.ciphers = ciphers_module
    primitives_module.hashes = hashes_module
    primitives_module.kdf = kdf_module
    ciphers_module.aead = aead_module
    kdf_module.pbkdf2 = pbkdf2_module

    sys.modules["cryptography"] = cryptography_module
    sys.modules["cryptography.hazmat"] = hazmat_module
    sys.modules["cryptography.hazmat.primitives"] = primitives_module
    sys.modules["cryptography.hazmat.primitives.ciphers"] = ciphers_module
    sys.modules["cryptography.hazmat.primitives.ciphers.aead"] = aead_module
    sys.modules["cryptography.hazmat.primitives.hashes"] = hashes_module
    sys.modules["cryptography.hazmat.primitives.kdf"] = kdf_module
    sys.modules["cryptography.hazmat.primitives.kdf.pbkdf2"] = pbkdf2_module


_ensure_cryptography_stubs()


def _ensure_numpy_stub():
    if "numpy" in sys.modules:
        return

    numpy_module = types.ModuleType("numpy")

    class _DummyNDArray:
        """Placeholder for numpy.ndarray used only for type hints."""

    numpy_module.ndarray = _DummyNDArray
    numpy_module.isscalar = staticmethod(
        lambda obj: not isinstance(obj, (list, tuple, dict, set))
    )
    numpy_module.bool_ = bool
    sys.modules["numpy"] = numpy_module


_ensure_numpy_stub()

from core.transcription.manager import TranscriptionManager
from data.database.connection import DatabaseConnection
from data.database.models import TranscriptionTask


class StubSpeechEngine:
    def __init__(self):
        self.failure_hook = None

    def get_name(self) -> str:
        return "stub-engine"

    async def transcribe_file(self, file_path, language=None, progress_callback=None):
        if self.failure_hook:
            self.failure_hook()
        raise RuntimeError("simulated failure")


@pytest.fixture()
def initialized_db(tmp_path):
    db_path = tmp_path / "test.db"
    db = DatabaseConnection(str(db_path))
    db.initialize_schema()
    return db


@pytest.fixture()
def manager(initialized_db):
    engine = StubSpeechEngine()
    mgr = TranscriptionManager(initialized_db, engine, config={})
    return mgr


def test_process_task_failure_after_task_removed(manager, initialized_db, monkeypatch):
    notifications = []
    progress_updates = []

    monkeypatch.setattr(
        manager,
        "_send_notification",
        lambda message, notification_type: notifications.append((message, notification_type)),
    )
    monkeypatch.setattr(
        manager,
        "_update_progress",
        lambda task_id, progress, message: progress_updates.append((task_id, progress, message)),
    )

    task = TranscriptionTask(file_path=str(Path("/tmp/audio.wav")), file_name="audio.wav")
    task.save(initialized_db)

    task_id = task.id

    def remove_task_record():
        initialized_db.execute(
            "DELETE FROM transcription_tasks WHERE id = ?",
            (task_id,),
            commit=True,
        )

    manager.speech_engine.failure_hook = remove_task_record

    asyncio.run(manager._process_task_async(task_id))

    assert notifications[-1] == (f"Transcription failed: {task.file_name}", "error")
    assert progress_updates[-1][0] == task_id
    assert progress_updates[-1][1] == pytest.approx(10.0)

    rows = initialized_db.execute(
        "SELECT status, error_message FROM transcription_tasks WHERE id = ?",
        (task_id,),
    )
    assert rows
    row = rows[0]
    assert row["status"] == "failed"
    assert "simulated failure" in row["error_message"]


def test_process_task_failure_when_lookup_raises(manager, initialized_db, monkeypatch):
    notifications = []
    progress_updates = []

    monkeypatch.setattr(
        manager,
        "_send_notification",
        lambda message, notification_type: notifications.append((message, notification_type)),
    )
    monkeypatch.setattr(
        manager,
        "_update_progress",
        lambda task_id, progress, message: progress_updates.append((task_id, progress, message)),
    )

    task_id = "missing-task"

    def failing_get_by_id(db_connection, lookup_id):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(
        TranscriptionTask,
        "get_by_id",
        staticmethod(failing_get_by_id),
    )

    asyncio.run(manager._process_task_async(task_id))

    assert notifications[-1] == (f"Transcription failed: {task_id}", "error")
    assert progress_updates[-1][0] == task_id
    assert progress_updates[-1][1] == pytest.approx(0.0)

    rows = initialized_db.execute(
        "SELECT * FROM transcription_tasks WHERE id = ?",
        (task_id,),
    )
    assert rows == []


def test_task_queue_configuration_overrides(initialized_db):
    engine = StubSpeechEngine()
    config = {
        'task_queue': {
            'max_concurrent_tasks': 4,
            'max_retries': 5,
            'retry_delay': 2.5,
        }
    }

    manager = TranscriptionManager(initialized_db, engine, config=config)

    assert manager.task_queue.max_concurrent == 4
    assert manager.task_queue.max_retries == 5
    assert manager.task_queue.retry_delay == pytest.approx(2.5)


def test_default_output_format_override(initialized_db, tmp_path):
    engine = StubSpeechEngine()
    config = {
        'default_output_format': 'md'
    }

    manager = TranscriptionManager(initialized_db, engine, config=config)

    audio_file = tmp_path / "sample.wav"
    audio_file.write_bytes(b"RIFF")

    task_id = manager.add_task(str(audio_file))
    task = TranscriptionTask.get_by_id(initialized_db, task_id)

    assert task is not None
    assert task.output_format == 'md'
