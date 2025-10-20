"""云端语音引擎音频预处理相关测试。"""

from __future__ import annotations

import base64
import io
import sys
import types
from typing import Any, Dict

import numpy as np
import pytest
import soundfile as sf

from engines.speech import base as speech_base
from engines.speech.azure_engine import AzureEngine
from engines.speech.google_engine import GoogleEngine


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
