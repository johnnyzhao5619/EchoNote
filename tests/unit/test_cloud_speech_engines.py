"""云端语音引擎音频预处理相关测试。"""

from __future__ import annotations

import asyncio
import base64
import io
import sys
import types
from typing import Any, Dict
from pathlib import Path

try:
    import numpy as np
except ModuleNotFoundError:  # pragma: no cover - 最小化依赖环境下的回退实现
    def _linspace(start: float, stop: float, num: int, dtype: Any | None = None):
        if num <= 1:
            return [start]
        step = (stop - start) / (num - 1)
        return [start + step * i for i in range(num)]

    def _zeros(count: int, dtype: Any | None = None):
        return [0.0] * count

    def _vstack(arrays: list[list[float]]):
        return arrays

    np = types.SimpleNamespace(  # type: ignore[assignment]
        ndarray=object,
        linspace=_linspace,
        zeros=_zeros,
        float32=float,
        vstack=_vstack,
        interp=lambda x, xp, fp: x,
        clip=lambda data, min_value, max_value: data,
    )
    sys.modules["numpy"] = np
import pytest

try:
    import soundfile as sf
except ModuleNotFoundError:  # pragma: no cover - 最小化依赖环境下的回退实现
    sf = types.SimpleNamespace(  # type: ignore[assignment]
        write=lambda *args, **kwargs: None,
        read=lambda *args, **kwargs: (_zeros(1), 16000),
        info=lambda *args, **kwargs: types.SimpleNamespace(format="WAV", duration=0.0),
        SoundFile=None,
    )
    sys.modules["soundfile"] = sf

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

if "httpx" not in sys.modules:
    class _Response:
        def __init__(self, status_code: int = 200, json_data: Dict[str, Any] | None = None) -> None:
            self.status_code = status_code
            self._json_data = json_data or {}

        def json(self) -> Dict[str, Any]:  # pragma: no cover - 仅用于类型占位
            return dict(self._json_data)

        def raise_for_status(self) -> None:  # pragma: no cover - 仅用于类型占位
            if self.status_code >= 400:
                raise _HTTPStatusError(f"HTTP {self.status_code}")

    class _HTTPError(Exception):
        pass

    class _HTTPStatusError(_HTTPError):
        pass

    class _ConnectError(_HTTPError):
        pass

    class _TimeoutException(_HTTPError):
        pass

    class _NetworkError(_HTTPError):
        pass

    class _BaseClient:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.headers = kwargs.get("headers", {})

        def close(self) -> None:  # pragma: no cover - 仅用于类型占位
            return None

    class _Client(_BaseClient):
        def request(self, *args: Any, **kwargs: Any) -> _Response:  # pragma: no cover
            raise NotImplementedError

    class _AsyncClient(_BaseClient):
        async def request(self, *args: Any, **kwargs: Any) -> _Response:  # pragma: no cover
            raise NotImplementedError

        async def post(self, *args: Any, **kwargs: Any) -> _Response:  # pragma: no cover
            return await self.request(*args, **kwargs)

        async def aclose(self) -> None:
            return None

    sys.modules["httpx"] = types.SimpleNamespace(
        AsyncClient=_AsyncClient,
        Client=_Client,
        Response=_Response,
        HTTPError=_HTTPError,
        HTTPStatusError=_HTTPStatusError,
        ConnectError=_ConnectError,
        TimeoutException=_TimeoutException,
        NetworkError=_NetworkError,
    )

if "data.database.models" not in sys.modules:
    data_module = sys.modules.setdefault("data", types.ModuleType("data"))
    database_module = types.ModuleType("data.database")
    models_module = types.ModuleType("data.database.models")

    class _APIUsage:  # pragma: no cover - 仅用于导入占位
        pass

    models_module.APIUsage = _APIUsage

    sys.modules["data.database"] = database_module
    sys.modules["data.database.models"] = models_module
    setattr(data_module, "database", database_module)
    setattr(database_module, "models", models_module)

from engines.speech import base as speech_base
from engines.speech.azure_engine import AzureEngine
from engines.speech.google_engine import GoogleEngine
from engines.speech.openai_engine import OpenAIEngine
from engines.translation.google_translate import GoogleTranslateEngine


def _generate_wav_bytes(sample_rate: int = 16000, frames: int = 320) -> bytes:
    """生成指定采样率的静音 WAV 字节。"""

    buffer = io.BytesIO()
    sf.write(buffer, np.zeros(frames, dtype=np.float32), sample_rate, format="WAV", subtype="PCM_16")
    return buffer.getvalue()


def test_convert_audio_to_wav_bytes_resamples(tmp_path):
    """验证辅助函数会将 44.1 kHz 音频重采样为 16 kHz。"""

    wav_path = tmp_path / "input.wav"
    duration_frames = 4410
    sf.write(wav_path, np.linspace(-0.5, 0.5, duration_frames, dtype=np.float32), 44100, subtype="PCM_16")

    wav_bytes, effective_rate, original_rate, detected_format = speech_base.convert_audio_to_wav_bytes(
        str(wav_path),
        target_rate=16000
    )

    assert effective_rate == 16000
    assert original_rate == 44100
    assert detected_format == "WAV"

    # 再次读取生成的字节，确认采样率标签正确
    with sf.SoundFile(io.BytesIO(wav_bytes)) as sound_file:
        assert sound_file.samplerate == 16000


def test_convert_audio_to_wav_bytes_fallback_to_librosa(monkeypatch, tmp_path):
    """模拟 MP3 输入，验证会回退到 librosa 并按目标采样率输出。"""

    mp3_path = tmp_path / "input.mp3"
    mp3_path.write_bytes(b"FAKE")

    def _raise_runtime_error(*_: Any, **__: Any):
        raise RuntimeError("unsupported format")

    monkeypatch.setattr(speech_base.sf, "info", _raise_runtime_error)
    monkeypatch.setattr(speech_base.sf, "read", _raise_runtime_error)

    def _fake_librosa_load(path: str, sr: Any = None, mono: bool = False):  # noqa: D401 - 与 librosa.load 对齐
        assert path == str(mp3_path)
        data = np.vstack([
            np.linspace(-0.1, 0.1, 4410, dtype=np.float32),
            np.linspace(0.1, -0.1, 4410, dtype=np.float32)
        ])
        return data, 44100

    fake_librosa = types.SimpleNamespace(load=_fake_librosa_load)
    monkeypatch.setitem(sys.modules, "librosa", fake_librosa)

    wav_bytes, effective_rate, original_rate, detected_format = speech_base.convert_audio_to_wav_bytes(
        str(mp3_path),
        target_rate=16000
    )

    assert effective_rate == 16000
    assert original_rate == 44100
    assert detected_format == "MP3"
    assert len(wav_bytes) > 0


@pytest.mark.asyncio
async def test_google_engine_transcribe_file_converts_mp3(monkeypatch, tmp_path):
    """Google 引擎应在请求中声明线性 16-bit PCM 及正确采样率。"""

    engine = GoogleEngine(api_key="test-key")
    audio_path = tmp_path / "sample.mp3"
    audio_path.write_bytes(b"MP3DATA")

    expected_bytes = _generate_wav_bytes()
    captured: Dict[str, Any] = {}

    def _fake_convert(audio_path_arg: str, target_rate: int):
        assert audio_path_arg == str(audio_path)
        assert target_rate == 16000
        return expected_bytes, 16000, 44100, "MP3"

    async def _fake_post(self, url: str, json: Dict[str, Any]):  # type: ignore[override]
        captured["url"] = url
        captured["json"] = json

        class _Response:
            status_code = 200

            def raise_for_status(self) -> None:  # noqa: D401
                return None

            def json(self) -> Dict[str, Any]:  # noqa: D401
                return {"results": []}

        return _Response()

    monkeypatch.setattr("engines.speech.google_engine.convert_audio_to_wav_bytes", _fake_convert)
    monkeypatch.setattr(
        engine.client,
        "post",
        types.MethodType(_fake_post, engine.client)
    )

    result = await engine.transcribe_file(str(audio_path), language="en")
    await engine.close()

    assert result["segments"] == []
    assert captured["json"]["config"]["encoding"] == "LINEAR16"
    assert captured["json"]["config"]["sampleRateHertz"] == 16000
    assert captured["json"]["audio"]["content"] == base64.b64encode(expected_bytes).decode("utf-8")


@pytest.mark.asyncio
async def test_google_engine_transcribe_file_rejects_large_converted_audio(monkeypatch, tmp_path):
    """当转换后的音频超出同步接口限制时应提前提示。"""

    engine = GoogleEngine(api_key="test-key")
    audio_path = tmp_path / "oversized.ogg"
    audio_path.write_bytes(b"small")  # 原始文件小于 10MB

    oversized_bytes = b"0" * (GoogleEngine.MAX_FILE_SIZE + 1)

    def _fake_convert(audio_path_arg: str, target_rate: int):
        assert audio_path_arg == str(audio_path)
        assert target_rate == 16000
        return oversized_bytes, 16000, 16000, "OGG"

    monkeypatch.setattr("engines.speech.google_engine.convert_audio_to_wav_bytes", _fake_convert)

    with pytest.raises(ValueError) as exc_info:
        await engine.transcribe_file(str(audio_path))

    await engine.close()

    assert "Google Cloud Storage" in str(exc_info.value)
    assert "asynchronous" in str(exc_info.value)


@pytest.mark.asyncio
async def test_azure_engine_transcribe_file_converts_mp3(monkeypatch, tmp_path):
    """Azure 引擎应发送 16-bit PCM WAV 并声明实际采样率。"""

    engine = AzureEngine(subscription_key="test", region="eastus")
    audio_path = tmp_path / "sample.mp3"
    audio_path.write_bytes(b"MP3DATA")

    expected_bytes = _generate_wav_bytes()
    captured: Dict[str, Any] = {}

    def _fake_convert(audio_path_arg: str, target_rate: int):
        assert audio_path_arg == str(audio_path)
        assert target_rate == 16000
        return expected_bytes, 16000, 44100, "MP3"

    async def _fake_post(self, url: str, params: Dict[str, Any], content: bytes, headers: Dict[str, str]):  # type: ignore[override]
        captured["url"] = url
        captured["params"] = params
        captured["content"] = content
        captured["headers"] = headers

        class _Response:
            status_code = 200

            def raise_for_status(self) -> None:  # noqa: D401
                return None

            def json(self) -> Dict[str, Any]:  # noqa: D401
                return {"RecognitionStatus": "Success", "NBest": []}

        return _Response()

    monkeypatch.setattr("engines.speech.azure_engine.convert_audio_to_wav_bytes", _fake_convert)
    monkeypatch.setattr(
        engine.client,
        "post",
        types.MethodType(_fake_post, engine.client)
    )

    result = await engine.transcribe_file(str(audio_path), language="en")
    await engine.close()

    assert result["segments"] == []
    assert captured["headers"]["Content-Type"] == "audio/wav; codecs=audio/pcm; samplerate=16000"
    assert captured["content"] == expected_bytes
    assert captured["params"]["language"] == "en-US"


def test_google_engine_languages_follow_shared_constants():
    engine = GoogleEngine(api_key="test-key")

    expected = speech_base.combine_languages(
        speech_base.BASE_LANGUAGE_CODES,
        speech_base.CLOUD_SPEECH_ADDITIONAL_LANGUAGES,
    )

    assert engine.get_supported_languages() == expected

    asyncio.run(engine.close())


def test_azure_engine_languages_follow_shared_constants():
    engine = AzureEngine(subscription_key="test", region="eastus")

    expected = speech_base.combine_languages(
        speech_base.BASE_LANGUAGE_CODES,
        speech_base.CLOUD_SPEECH_ADDITIONAL_LANGUAGES,
    )

    assert engine.get_supported_languages() == expected

    asyncio.run(engine.close())


def test_openai_engine_languages_follow_shared_constants():
    engine = OpenAIEngine(api_key="test-key")

    expected = speech_base.combine_languages(
        speech_base.BASE_LANGUAGE_CODES,
        speech_base.CLOUD_SPEECH_ADDITIONAL_LANGUAGES,
    )

    assert engine.get_supported_languages() == expected

    asyncio.run(engine.close())


def test_openai_engine_supported_formats_follow_shared_constant():
    assert OpenAIEngine.SUPPORTED_FORMATS == list(speech_base.AUDIO_VIDEO_FORMATS)


def test_google_translate_supported_languages_follow_shared_constants():
    expected = speech_base.combine_languages(
        ("zh",),
        speech_base.CHINESE_LANGUAGE_VARIANTS,
        speech_base.BASE_LANGUAGE_CODES,
    )

    assert GoogleTranslateEngine.SUPPORTED_LANGUAGES == expected


@pytest.mark.parametrize(
    "engine_factory",
    [
        lambda: GoogleEngine(api_key="test-key"),
        lambda: AzureEngine(subscription_key="test", region="eastus"),
    ],
)
def test_cloud_speech_language_code_mapping(engine_factory):
    """云端语音引擎应共享语言代码映射与回退策略。"""

    engine = engine_factory()

    try:
        expected_mapping = {
            "da": "da-DK",
            "no": "no-NO",
            "fi": "fi-FI",
            "cs": "cs-CZ",
            "ro": "ro-RO",
            "bg": "bg-BG",
            "el": "el-GR",
            "he": "he-IL",
            "fa": "fa-IR",
            "ur": "ur-PK",
        }

        for language, locale in expected_mapping.items():
            assert engine._convert_language_code(language) == locale

        assert engine._convert_language_code(None) == "en-US"
        assert engine._convert_language_code("xx") == "xx"
    finally:
        asyncio.run(engine.close())


def test_close_lazy_loaded_translation_engine_releases_resources(monkeypatch):
    import logging
    from utils.resource_cleanup import close_lazy_loaded_engine

    engine = GoogleTranslateEngine(api_key="test-key")
    closed_clients: list[object] = []
    original_aclose = engine.client.aclose

    async def _fake_aclose(self):  # type: ignore[override]
        closed_clients.append(self)
        await original_aclose()

    monkeypatch.setattr(
        engine.client,
        "aclose",
        types.MethodType(_fake_aclose, engine.client),
    )

    class _InitializedLoader:
        def __init__(self, instance):
            self._instance = instance

        def get(self):
            return self._instance

        def is_initialized(self):
            return True

    loader = _InitializedLoader(engine)

    close_lazy_loaded_engine('translation engine', loader, logging.getLogger(__name__))

    assert closed_clients, "Expected AsyncClient.aclose to be called"
