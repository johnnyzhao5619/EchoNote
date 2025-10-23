"""
语音引擎抽象基类

定义所有语音识别引擎必须实现的统一接口
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple
import io
import numpy as np
import soundfile as sf


# 基础语言常量，供语音/翻译引擎共享
BASE_LANGUAGE_CODES: Tuple[str, ...] = (
    "zh",
    "en",
    "fr",
    "de",
    "es",
    "it",
    "ja",
    "ko",
    "pt",
    "ru",
    "ar",
    "hi",
    "nl",
    "pl",
    "tr",
    "vi",
    "id",
    "th",
    "uk",
    "sv",
)

# 云端语音引擎通常额外支持的语言
CLOUD_SPEECH_ADDITIONAL_LANGUAGES: Tuple[str, ...] = (
    "da",
    "no",
    "fi",
    "cs",
    "ro",
    "bg",
    "el",
    "he",
    "fa",
    "ur",
)

# 中文常见地区变体（供翻译等需要精细区分的场景使用）
CHINESE_LANGUAGE_VARIANTS: Tuple[str, ...] = (
    "zh-CN",
    "zh-TW",
)


def combine_languages(*groups: Iterable[str]) -> List[str]:
    """按顺序合并语言代码，并移除重复项。"""

    seen = set()
    combined: List[str] = []
    for group in groups:
        for code in group:
            if code not in seen:
                combined.append(code)
                seen.add(code)
    return combined


def ensure_audio_sample_rate(
    audio_chunk: np.ndarray,
    source_rate: Optional[int],
    target_rate: Optional[int]
) -> Tuple[np.ndarray, Optional[int]]:
    """确保音频数据与目标采样率一致。

    Args:
        audio_chunk: 原始音频数据。
        source_rate: 音频的实际采样率。
        target_rate: 需要输出的目标采样率；如果为 None 则保持原始采样率。

    Returns:
        Tuple[np.ndarray, Optional[int]]: 处理后的音频数据及其采样率。
    """
    if audio_chunk.size == 0:
        return audio_chunk, target_rate or source_rate

    if source_rate is None or source_rate <= 0:
        source_rate = target_rate

    if target_rate is None or target_rate <= 0 or source_rate == target_rate:
        return audio_chunk, source_rate

    duration = audio_chunk.shape[0] / float(source_rate)
    if duration == 0:
        return audio_chunk, target_rate

    target_length = max(1, int(round(duration * target_rate)))
    if target_length == audio_chunk.shape[0]:
        return audio_chunk, target_rate

    source_positions = np.linspace(0.0, duration, num=audio_chunk.shape[0], endpoint=False)
    target_positions = np.linspace(0.0, duration, num=target_length, endpoint=False)
    resampled = np.interp(target_positions, source_positions, audio_chunk).astype(np.float32)
    return resampled, target_rate


def convert_audio_to_wav_bytes(
    audio_path: str,
    target_rate: Optional[int] = None
) -> Tuple[bytes, int, int, str]:
    """读取音频文件并转换为指定采样率的 16-bit PCM WAV。

    Args:
        audio_path: 音频文件路径。
        target_rate: 目标采样率；若为 ``None`` 则保持原采样率。

    Returns:
        Tuple[bytes, int, int, str]:
            - 转换后的 WAV 字节数据；
            - 输出音频采样率；
            - 原始音频采样率；
            - 检测到的音频格式标识。
    """

    detected_format = "UNKNOWN"

    try:
        info = sf.info(audio_path)
        if info.format:
            detected_format = info.format
    except RuntimeError:
        # soundfile 无法识别格式，稍后回退到 librosa
        pass

    try:
        data, source_rate = sf.read(audio_path, always_2d=True)
    except RuntimeError:
        try:
            import importlib
            librosa = importlib.import_module("librosa")
        except ModuleNotFoundError as exc:  # pragma: no cover - 运行环境缺少 librosa 的极端情况
            raise RuntimeError("无法解码音频文件，缺少 librosa 依赖。") from exc

        waveform, source_rate = librosa.load(audio_path, sr=None, mono=False)  # type: ignore[attr-defined]
        if waveform.ndim == 1:
            data = waveform.reshape(-1, 1)
        else:
            data = np.transpose(waveform)
        if detected_format == "UNKNOWN":
            detected_format = Path(audio_path).suffix.lstrip('.').upper() or "UNKNOWN"
    else:
        if detected_format == "UNKNOWN":
            detected_format = Path(audio_path).suffix.lstrip('.').upper() or "UNKNOWN"

    if data.ndim != 2 or data.shape[1] == 0:
        raise ValueError("音频数据格式无效，无法确定声道信息。")

    if source_rate is None or source_rate <= 0:
        raise ValueError("无法确定音频文件的采样率。")

    if data.shape[1] > 1:
        mono_audio = data.mean(axis=1)
    else:
        mono_audio = data[:, 0]

    mono_audio = mono_audio.astype(np.float32)

    desired_rate = target_rate if target_rate and target_rate > 0 else source_rate
    processed_audio, effective_rate = ensure_audio_sample_rate(mono_audio, source_rate, desired_rate)

    if effective_rate is None or effective_rate <= 0:
        raise ValueError("音频采样率转换失败。")

    processed_audio = np.clip(processed_audio, -1.0, 1.0).astype(np.float32)

    buffer = io.BytesIO()
    sf.write(buffer, processed_audio, effective_rate, format="WAV", subtype="PCM_16")
    wav_bytes = buffer.getvalue()

    return wav_bytes, effective_rate, source_rate, detected_format


class SpeechEngine(ABC):
    """语音识别引擎抽象基类"""

    @abstractmethod
    def get_name(self) -> str:
        """
        获取引擎名称
        
        Returns:
            str: 引擎名称（如 'faster-whisper', 'openai', 'google'）
        """
        pass

    @abstractmethod
    def get_supported_languages(self) -> List[str]:
        """
        获取引擎支持的语言列表
        
        Returns:
            List[str]: 语言代码列表（如 ['zh', 'en', 'fr']）
        """
        pass

    @abstractmethod
    async def transcribe_file(self, audio_path: str, language: Optional[str] = None, **kwargs) -> Dict:
        """
        转录音频文件（批量转录）
        
        Args:
            audio_path: 音频文件路径
            language: 源语言代码（可选，None 表示自动检测）
            **kwargs: 引擎特定的额外参数
            
        Returns:
            Dict: 转录结果，格式为：
            {
                "segments": [
                    {
                        "start": float,  # 开始时间（秒）
                        "end": float,    # 结束时间（秒）
                        "text": str      # 转录文本
                    },
                    ...
                ],
                "language": str,  # 检测到的语言代码
                "duration": float  # 音频总时长（秒）
            }
        """
        pass

    @abstractmethod
    async def transcribe_stream(
        self,
        audio_chunk: np.ndarray,
        language: Optional[str] = None,
        **kwargs
    ) -> str:
        """
        转录音频流（实时转录）

        Args:
            audio_chunk: 音频数据块（numpy array）
            language: 源语言代码（可选）
            **kwargs: 引擎特定的额外参数（如 sample_rate）

        Returns:
            str: 转录文本片段
        """
        pass

    @abstractmethod
    def get_config_schema(self) -> Dict:
        """
        获取引擎配置的 JSON Schema
        
        Returns:
            Dict: JSON Schema 定义，描述引擎所需的配置参数
        """
        pass

    def validate_config(self, config: Dict) -> bool:
        """
        验证配置是否有效
        
        Args:
            config: 配置字典
            
        Returns:
            bool: 配置是否有效
        """
        # 默认实现：基本验证
        schema = self.get_config_schema()
        required_fields = schema.get('required', [])
        
        for field in required_fields:
            if field not in config:
                return False
        
        return True
