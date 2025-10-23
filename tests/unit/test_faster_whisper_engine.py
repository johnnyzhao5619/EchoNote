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

import pytest

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
