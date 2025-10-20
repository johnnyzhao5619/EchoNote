import asyncio
import logging
import sys
import types
from pathlib import Path
import time

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


def _ensure_soundfile_stub():
    if "soundfile" in sys.modules:
        return

    soundfile_module = types.ModuleType("soundfile")

    def _write_stub(*args, **kwargs):  # noqa: ARG002
        return None

    def _info_stub(*args, **kwargs):  # noqa: ARG002
        return types.SimpleNamespace(format="")

    def _read_stub(*args, **kwargs):  # noqa: ARG002
        raise RuntimeError("soundfile stub does not provide read support")

    class _SoundFileStub:
        def __init__(self, *_args, **_kwargs):
            self.samplerate = 16000

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):  # noqa: D401
            return False

    soundfile_module.write = _write_stub  # type: ignore[attr-defined]
    soundfile_module.info = _info_stub  # type: ignore[attr-defined]
    soundfile_module.read = _read_stub  # type: ignore[attr-defined]
    soundfile_module.SoundFile = _SoundFileStub  # type: ignore[attr-defined]

    sys.modules["soundfile"] = soundfile_module


_ensure_soundfile_stub()


def _ensure_pyqt_stub():
    if "PyQt6" in sys.modules:
        return

    pyqt6_module = types.ModuleType("PyQt6")
    qtwidgets_module = types.ModuleType("PyQt6.QtWidgets")
    qtcore_module = types.ModuleType("PyQt6.QtCore")
    qtgui_module = types.ModuleType("PyQt6.QtGui")

    class _BaseWidget:
        def __init__(self, *args, **kwargs):  # noqa: D401
            pass

    class _Layout:
        def __init__(self, *args, **kwargs):  # noqa: D401
            pass

        def setContentsMargins(self, *args, **kwargs):  # noqa: D401, ARG002
            return None

        def setSpacing(self, *args, **kwargs):  # noqa: D401, ARG002
            return None

        def addWidget(self, *args, **kwargs):  # noqa: D401, ARG002
            return None

        def addLayout(self, *args, **kwargs):  # noqa: D401, ARG002
            return None

        def addStretch(self, *args, **kwargs):  # noqa: D401, ARG002
            return None

    class _Label(_BaseWidget):
        def setAlignment(self, *args, **kwargs):  # noqa: D401, ARG002
            return None

        def setText(self, *args, **kwargs):  # noqa: D401, ARG002
            return None

        def setWordWrap(self, *args, **kwargs):  # noqa: D401, ARG002
            return None

        def setObjectName(self, *args, **kwargs):  # noqa: D401, ARG002
            return None

    class _ProgressBar(_BaseWidget):
        def setMinimum(self, *args, **kwargs):  # noqa: D401, ARG002
            return None

        def setMaximum(self, *args, **kwargs):  # noqa: D401, ARG002
            return None

        def setValue(self, *args, **kwargs):  # noqa: D401, ARG002
            return None

        def setTextVisible(self, *args, **kwargs):  # noqa: D401, ARG002
            return None

    class _Signal:
        def connect(self, *args, **kwargs):  # noqa: D401, ARG002
            return None

        def emit(self, *args, **kwargs):  # noqa: D401, ARG002
            return None

    class _QDialog(_BaseWidget):
        def setWindowTitle(self, *args, **kwargs):  # noqa: D401, ARG002
            return None

        def setMinimumWidth(self, *args, **kwargs):  # noqa: D401, ARG002
            return None

        def setModal(self, *args, **kwargs):  # noqa: D401, ARG002
            return None

        def accept(self, *args, **kwargs):  # noqa: D401, ARG002
            return None

    class _QPushButton(_BaseWidget):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.clicked = _Signal()

        def setText(self, *args, **kwargs):  # noqa: D401, ARG002
            return None

        def setDefault(self, *args, **kwargs):  # noqa: D401, ARG002
            return None

    class _QTextEdit(_BaseWidget):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._visible = True

        def setPlainText(self, *args, **kwargs):  # noqa: D401, ARG002
            return None

        def setReadOnly(self, *args, **kwargs):  # noqa: D401, ARG002
            return None

        def setMaximumHeight(self, *args, **kwargs):  # noqa: D401, ARG002
            return None

        def setObjectName(self, *args, **kwargs):  # noqa: D401, ARG002
            return None

        def hide(self):
            self._visible = False

        def show(self):
            self._visible = True

        def isVisible(self):  # noqa: D401
            return self._visible

    class _QClipboard:
        def setText(self, *args, **kwargs):  # noqa: D401, ARG002
            return None

    class _QApplication:
        _clipboard = _QClipboard()

        @classmethod
        def clipboard(cls):  # noqa: D401
            return cls._clipboard

    class _QTimer:
        @staticmethod
        def singleShot(*args, **kwargs):  # noqa: D401, ARG002
            return None

    class _QIcon:
        def __init__(self, *args, **kwargs):  # noqa: D401, ARG002
            pass

    class _Qt:
        class AlignmentFlag:
            AlignRight = 0

    def _pyqt_signal(*args, **kwargs):  # noqa: D401, ARG002
        return _Signal()

    qtwidgets_module.QWidget = _BaseWidget  # type: ignore[attr-defined]
    qtwidgets_module.QVBoxLayout = _Layout  # type: ignore[attr-defined]
    qtwidgets_module.QHBoxLayout = _Layout  # type: ignore[attr-defined]
    qtwidgets_module.QLabel = _Label  # type: ignore[attr-defined]
    qtwidgets_module.QProgressBar = _ProgressBar  # type: ignore[attr-defined]
    qtwidgets_module.QDialog = _QDialog  # type: ignore[attr-defined]
    qtwidgets_module.QPushButton = _QPushButton  # type: ignore[attr-defined]
    qtwidgets_module.QTextEdit = _QTextEdit  # type: ignore[attr-defined]
    qtwidgets_module.QApplication = _QApplication  # type: ignore[attr-defined]

    qtcore_module.Qt = _Qt  # type: ignore[attr-defined]
    qtcore_module.pyqtSignal = _pyqt_signal  # type: ignore[attr-defined]
    qtcore_module.QTimer = _QTimer  # type: ignore[attr-defined]

    qtgui_module.QIcon = _QIcon  # type: ignore[attr-defined]
    qtgui_module.QClipboard = _QClipboard  # type: ignore[attr-defined]

    pyqt6_module.QtWidgets = qtwidgets_module  # type: ignore[attr-defined]
    pyqt6_module.QtCore = qtcore_module  # type: ignore[attr-defined]
    pyqt6_module.QtGui = qtgui_module  # type: ignore[attr-defined]

    sys.modules["PyQt6"] = pyqt6_module
    sys.modules["PyQt6.QtWidgets"] = qtwidgets_module
    sys.modules["PyQt6.QtCore"] = qtcore_module
    sys.modules["PyQt6.QtGui"] = qtgui_module


_ensure_pyqt_stub()

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


class SuccessfulSpeechEngine:
    def get_name(self) -> str:
        return "successful-engine"

    async def transcribe_file(self, file_path, language=None, progress_callback=None):
        if progress_callback:
            progress_callback(55.0)
        return {
            "duration": 1.2,
            "segments": [
                {"start": 0.0, "end": 1.0, "text": "hello world"},
            ],
        }


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


def test_successful_process_uses_default_save_path(initialized_db, tmp_path):
    default_dir = tmp_path / "exports"
    engine = SuccessfulSpeechEngine()
    manager = TranscriptionManager(
        initialized_db,
        engine,
        config={
            "default_save_path": str(default_dir),
            "default_output_format": "txt",
        },
    )

    audio_file = tmp_path / "sample.wav"
    audio_file.write_bytes(b"fake-audio")

    task = TranscriptionTask(
        file_path=str(audio_file),
        file_name=audio_file.name,
        file_size=audio_file.stat().st_size,
        status="pending",
        output_format="txt",
    )
    task.save(initialized_db)

    asyncio.run(manager._process_task_async(task.id))

    expected_output = (default_dir / f"{audio_file.stem}.txt").resolve()
    assert expected_output.exists()

    with open(expected_output, "r", encoding="utf-8") as exported:
        content = exported.read()
    assert "hello world" in content

    refreshed_task = TranscriptionTask.get_by_id(initialized_db, task.id)
    assert refreshed_task is not None
    assert refreshed_task.output_path == str(expected_output)


def test_background_shutdown_logs_and_cleans_up(initialized_db, monkeypatch, caplog):
    engine = StubSpeechEngine()
    manager = TranscriptionManager(initialized_db, engine, config={})

    async def failing_stop():
        raise RuntimeError("simulated stop failure")

    monkeypatch.setattr(manager.task_queue, "stop", failing_stop)

    caplog.set_level(logging.DEBUG, logger="echonote.transcription.manager")

    manager.start_processing()

    deadline = time.time() + 5.0
    while (manager._loop is None or not manager._loop.is_running()) and time.time() < deadline:
        time.sleep(0.05)

    assert manager._loop is not None
    assert manager._loop.is_running()

    manager._loop.call_soon_threadsafe(manager._loop.stop)

    if manager._thread is not None:
        manager._thread.join(timeout=5.0)
        assert not manager._thread.is_alive()

    assert manager._loop is None
    assert manager._running is False
    assert manager.task_queue.worker_tasks == []

    manager._thread = None

    manager_logs = [
        record.getMessage()
        for record in caplog.records
        if record.name == "echonote.transcription.manager"
    ]

    assert any("Task queue stop attempt" in message for message in manager_logs)
    assert any("forced shutdown" in message for message in manager_logs)
    assert any("closed with prior shutdown errors" in message for message in manager_logs)


def test_send_notification_handles_quotes(monkeypatch, manager):
    import ui.common.notification as notification_module

    monkeypatch.setattr(notification_module.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(notification_module, "_notification_manager", None)

    captured = {}

    def fake_run(cmd, capture_output, timeout, check):
        captured["cmd"] = cmd
        return types.SimpleNamespace(returncode=0)

    monkeypatch.setattr("subprocess.run", fake_run)

    message = 'Transcription completed: task "alpha"'
    manager._send_notification(message, "success")

    assert "cmd" in captured
    script = captured["cmd"][2]
    assert '\\"' in script

    notification_module._notification_manager = None
