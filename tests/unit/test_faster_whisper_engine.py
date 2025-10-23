"""针对 FasterWhisperEngine 的模型可用性刷新逻辑的测试。"""

from __future__ import annotations

import asyncio
import sys
import types
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

if "numpy" not in sys.modules:
    numpy_stub = types.SimpleNamespace(
        ndarray=object,
        sqrt=lambda value: value,
        mean=lambda value: value,
        concatenate=lambda seq: seq[0] if seq else seq,
    )
    sys.modules["numpy"] = numpy_stub
else:
    numpy_stub = sys.modules["numpy"]

if "soundfile" not in sys.modules:
    soundfile_stub = types.SimpleNamespace(
        info=lambda *_args, **_kwargs: types.SimpleNamespace(format=""),
        read=lambda *_args, **_kwargs: (numpy_stub, 16000),
        write=lambda *_args, **_kwargs: None,
        SoundFile=None,
    )
    sys.modules["soundfile"] = soundfile_stub

if "psutil" not in sys.modules:
    psutil_stub = types.SimpleNamespace(
        virtual_memory=lambda: types.SimpleNamespace(total=8 * 1024**3),
        cpu_count=lambda logical=True: 4,
        disk_usage=lambda _path: types.SimpleNamespace(total=1, used=0, free=1),
    )
    sys.modules["psutil"] = psutil_stub

if "PyQt6" not in sys.modules:
    qtcore_stub = types.SimpleNamespace(
        QObject=type("QObject", (), {"__init__": lambda self, *args, **kwargs: None}),
        QCoreApplication=type(
            "QCoreApplication", (), {"instance": staticmethod(lambda: None)}
        ),
        QTimer=type(
            "QTimer",
            (),
            {
                "singleShot": staticmethod(
                    lambda _interval, callback: callback() if callback else None
                )
            },
        ),
        pyqtSignal=lambda *args, **kwargs: types.SimpleNamespace(
            connect=lambda *_args, **_kwargs: None,
            emit=lambda *_args, **_kwargs: None,
        ),
    )
    pyqt6_stub = types.SimpleNamespace(QtCore=qtcore_stub)
    sys.modules["PyQt6"] = pyqt6_stub
    sys.modules["PyQt6.QtCore"] = qtcore_stub

if "requests" not in sys.modules:
    requests_stub = types.SimpleNamespace(
        Session=lambda: types.SimpleNamespace(close=lambda: None),
        exceptions=types.SimpleNamespace(RequestException=Exception),
    )
    sys.modules["requests"] = requests_stub

if "cryptography" not in sys.modules:
    cryptography_module = types.ModuleType("cryptography")
    hazmat_module = types.ModuleType("cryptography.hazmat")
    primitives_module = types.ModuleType("cryptography.hazmat.primitives")
    ciphers_module = types.ModuleType("cryptography.hazmat.primitives.ciphers")
    aead_module = types.ModuleType("cryptography.hazmat.primitives.ciphers.aead")
    hashes_module = types.ModuleType("cryptography.hazmat.primitives.hashes")
    kdf_module = types.ModuleType("cryptography.hazmat.primitives.kdf")
    pbkdf2_module = types.ModuleType(
        "cryptography.hazmat.primitives.kdf.pbkdf2"
    )

    class _AESGCM:
        def __init__(self, _key):
            self._key = _key

        def encrypt(self, _nonce, data, _aad):
            return data

        def decrypt(self, _nonce, data, _aad):
            return data

    class _SHA256:
        def __init__(self):
            self.name = "sha256"

    class _PBKDF2HMAC:
        def __init__(self, algorithm, length, salt, iterations):
            self.length = length

        def derive(self, _data):
            return b"0" * self.length

    aead_module.AESGCM = _AESGCM
    ciphers_module.aead = aead_module
    hashes_module.SHA256 = _SHA256
    pbkdf2_module.PBKDF2HMAC = _PBKDF2HMAC
    kdf_module.pbkdf2 = pbkdf2_module

    primitives_module.ciphers = ciphers_module
    primitives_module.hashes = hashes_module
    primitives_module.kdf = kdf_module
    hazmat_module.primitives = primitives_module
    cryptography_module.hazmat = hazmat_module

    sys.modules["cryptography"] = cryptography_module
    sys.modules["cryptography.hazmat"] = hazmat_module
    sys.modules["cryptography.hazmat.primitives"] = primitives_module
    sys.modules["cryptography.hazmat.primitives.ciphers"] = ciphers_module
    sys.modules[
        "cryptography.hazmat.primitives.ciphers.aead"
    ] = aead_module
    sys.modules["cryptography.hazmat.primitives.hashes"] = hashes_module
    sys.modules["cryptography.hazmat.primitives.kdf"] = kdf_module
    sys.modules[
        "cryptography.hazmat.primitives.kdf.pbkdf2"
    ] = pbkdf2_module

import pytest

from core.models.registry import get_default_model_names
from engines.speech.base import BASE_LANGUAGE_CODES, combine_languages
from engines.speech.faster_whisper_engine import FasterWhisperEngine


@dataclass
class _FakeModelInfo:
    """简化的模型信息，用于模拟下载状态。"""

    is_downloaded: bool
    local_path: str | None = None


class _FakeModelManager:
    """最小化的模型管理器实现。"""

    def __init__(self, model_info: _FakeModelInfo) -> None:
        self._model_info = model_info
        self._requested_names: list[str] = []
        self.used_names: list[str] = []

    def get_model(self, name: str) -> _FakeModelInfo:
        self._requested_names.append(name)
        return self._model_info

    def mark_model_used(self, name: str) -> None:  # pragma: no cover - 仅保持接口兼容
        self._requested_names.append(f"used:{name}")
        self.used_names.append(name)


def test_faster_whisper_engine_refreshes_availability(monkeypatch, tmp_path):
    """模型下载完成后，应能刷新可用状态并顺利加载。"""

    # 固定硬件检测结果，避免依赖真实环境
    monkeypatch.setattr(
        "utils.gpu_detector.GPUDetector.validate_device_config",
        staticmethod(lambda device, compute_type: ("cpu", "int8", "")),
    )

    model_info = _FakeModelInfo(is_downloaded=False)
    manager = _FakeModelManager(model_info)

    engine = FasterWhisperEngine(model_size="base", model_manager=manager)

    assert not engine.is_model_available()

    # 模拟模型下载完成
    model_dir = tmp_path / "base"
    model_dir.mkdir()
    model_info.is_downloaded = True
    model_info.local_path = str(model_dir)

    # 准备 faster_whisper 的假实现，避免真实加载
    class _DummyWhisperModel:
        def __init__(self, model_path: str, device: str, compute_type: str) -> None:
            self.model_path = model_path
            self.device = device
            self.compute_type = compute_type

    monkeypatch.setitem(
        sys.modules,
        "faster_whisper",
        types.SimpleNamespace(WhisperModel=_DummyWhisperModel),
    )

    # 再次检查时应反映最新状态
    assert engine.is_model_available()
    assert engine.download_root == str(tmp_path)

    # 加载模型应成功，并使用最新的本地路径
    engine._load_model()

    assert engine.model is not None
    assert engine.model.model_path == model_info.local_path


def test_faster_whisper_supported_languages_follow_shared_constants(monkeypatch):
    """基础语言列表应与共享常量保持一致。"""

    monkeypatch.setattr(
        "utils.gpu_detector.GPUDetector.validate_device_config",
        staticmethod(lambda device, compute_type: ("cpu", "int8", "")),
    )

    engine = FasterWhisperEngine(model_size="base")

    expected = combine_languages(BASE_LANGUAGE_CODES)

    assert engine.get_supported_languages() == expected


def test_model_sizes_follow_registry(monkeypatch):
    """模型枚举应与注册表保持一致。"""

    monkeypatch.setattr(
        "utils.gpu_detector.GPUDetector.validate_device_config",
        staticmethod(lambda device, compute_type: ("cpu", "int8", "")),
    )

    engine = FasterWhisperEngine(model_size="base")

    expected_names = list(get_default_model_names())

    assert list(engine.MODEL_SIZES.keys()) == expected_names
    schema = engine.get_config_schema()
    assert schema["properties"]["model_size"]["enum"] == expected_names


def test_engine_initialization_does_not_mark_usage(monkeypatch):
    """初始化时不应记录模型使用次数。"""

    monkeypatch.setattr(
        "utils.gpu_detector.GPUDetector.validate_device_config",
        staticmethod(lambda device, compute_type: ("cpu", "int8", "")),
    )

    model_info = _FakeModelInfo(is_downloaded=True, local_path="/tmp/model")
    manager = _FakeModelManager(model_info)

    FasterWhisperEngine(model_size="base", model_manager=manager)

    assert manager.used_names == []


def test_transcribe_file_marks_usage_after_success(monkeypatch, tmp_path):
    """转录成功后应记录模型使用次数。"""

    monkeypatch.setattr(
        "utils.gpu_detector.GPUDetector.validate_device_config",
        staticmethod(lambda device, compute_type: ("cpu", "int8", "")),
    )

    model_info = _FakeModelInfo(is_downloaded=True, local_path=str(tmp_path / "base"))
    manager = _FakeModelManager(model_info)

    engine = FasterWhisperEngine(model_size="base", model_manager=manager)

    assert manager.used_names == []

    # 确保模型可用
    engine._refresh_model_status()

    class _DummyWhisperModel:
        def __init__(self) -> None:
            self.model_path = model_info.local_path

        def transcribe(self, *_args, **_kwargs):
            segments = [
                types.SimpleNamespace(start=0.0, end=1.0, text="hello world"),
            ]
            info = types.SimpleNamespace(language="en", duration=1.0)
            return iter(segments), info

    engine._load_model = lambda: setattr(engine, "model", _DummyWhisperModel())

    class _DummyLoop:
        async def run_in_executor(self, _executor, func, *args, **kwargs):
            return func(*args, **kwargs)

    monkeypatch.setattr(asyncio, "get_event_loop", lambda: _DummyLoop())

    monkeypatch.setattr(
        sys.modules["soundfile"],
        "info",
        lambda *_args, **_kwargs: types.SimpleNamespace(duration=1.0),
    )

    audio_path = tmp_path / "audio.wav"
    audio_path.write_bytes(b"data")

    asyncio.run(engine.transcribe_file(str(audio_path)))

    assert manager.used_names == ["base"]
