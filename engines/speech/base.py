# SPDX-License-Identifier: Apache-2.0
#
# Copyright (c) 2024-2025 EchoNote Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Unified interface that all speech recognition engines must implement."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple, FrozenSet
import io
import numpy as np
import soundfile as sf


# Base language set shared by speech and translation engines.
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

# Additional languages typically supported by cloud speech services.
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

# Canonical locale mapping for cloud speech engines.
CLOUD_SPEECH_LANGUAGE_LOCALE_MAPPING: Dict[str, str] = {
    "zh": "zh-CN",
    "en": "en-US",
    "fr": "fr-FR",
    "de": "de-DE",
    "es": "es-ES",
    "it": "it-IT",
    "ja": "ja-JP",
    "ko": "ko-KR",
    "pt": "pt-BR",
    "ru": "ru-RU",
    "ar": "ar-SA",
    "hi": "hi-IN",
    "nl": "nl-NL",
    "pl": "pl-PL",
    "tr": "tr-TR",
    "vi": "vi-VN",
    "id": "id-ID",
    "th": "th-TH",
    "uk": "uk-UA",
    "sv": "sv-SE",
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

# Common Chinese locale variants for translation scenarios.
CHINESE_LANGUAGE_VARIANTS: Tuple[str, ...] = (
    "zh-CN",
    "zh-TW",
)


def combine_languages(*groups: Iterable[str]) -> List[str]:
    """Combine language codes in order while removing duplicates."""

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
    """Ensure the audio data matches the requested sampling rate.

    Args:
        audio_chunk: Input audio samples.
        source_rate: Actual sampling rate of the input data.
        target_rate: Desired sampling rate. ``None`` preserves the input rate.

    Returns:
        Tuple[np.ndarray, Optional[int]]: Resampled audio and its sampling rate.
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
    """Read an audio file and convert it to 16-bit PCM WAV at ``target_rate``.

    Args:
        audio_path: Input audio file path.
        target_rate: Target sampling rate. ``None`` keeps the original rate.

    Returns:
        Tuple[bytes, int, int, str]:
            - WAV byte payload after conversion.
            - Output audio sampling rate.
            - Original audio sampling rate.
            - Detected input format identifier.
    """

    detected_format = "UNKNOWN"

    try:
        info = sf.info(audio_path)
        if info.format:
            detected_format = info.format
    except RuntimeError:
        # ``soundfile`` cannot determine the format; fall back to librosa.
        pass

    try:
        data, source_rate = sf.read(audio_path, always_2d=True)
    except RuntimeError:
        try:
            import importlib
            librosa = importlib.import_module("librosa")
        except ModuleNotFoundError as exc:  # pragma: no cover - missing librosa is rare
            raise RuntimeError("Unable to decode audio file because librosa is missing.") from exc

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
        raise ValueError("Invalid audio data shape; channel information is missing.")

    if source_rate is None or source_rate <= 0:
        raise ValueError("Unable to determine the audio file sampling rate.")

    if data.shape[1] > 1:
        mono_audio = data.mean(axis=1)
    else:
        mono_audio = data[:, 0]

    mono_audio = mono_audio.astype(np.float32)

    desired_rate = target_rate if target_rate and target_rate > 0 else source_rate
    processed_audio, effective_rate = ensure_audio_sample_rate(mono_audio, source_rate, desired_rate)

    if effective_rate is None or effective_rate <= 0:
        raise ValueError("Failed to determine the effective sampling rate after conversion.")

    processed_audio = np.clip(processed_audio, -1.0, 1.0).astype(np.float32)

    buffer = io.BytesIO()
    sf.write(buffer, processed_audio, effective_rate, format="WAV", subtype="PCM_16")
    wav_bytes = buffer.getvalue()

    return wav_bytes, effective_rate, source_rate, detected_format


class SpeechEngine(ABC):
    """Abstract base class for speech recognition engines."""

    @abstractmethod
    def get_name(self) -> str:
        """Return the engine identifier (e.g., ``"faster-whisper"``)."""
        pass

    @abstractmethod
    def get_supported_languages(self) -> List[str]:
        """Return the list of language codes supported by the engine."""
        pass

    @abstractmethod
    async def transcribe_file(self, audio_path: str, language: Optional[str] = None, **kwargs) -> Dict:
        """Transcribe an audio file in batch mode.

        Args:
            audio_path: Path to the input audio file.
            language: Optional source language code. ``None`` enables detection.
            **kwargs: Additional engine-specific parameters.

        Returns:
            Dict: Structured transcription result including segments, detected
            language, and total duration.
        """
        pass

    @abstractmethod
    async def transcribe_stream(
        self,
        audio_chunk: np.ndarray,
        language: Optional[str] = None,
        **kwargs
    ) -> str:
        """Transcribe an audio chunk during real-time streaming.

        Args:
            audio_chunk: ``numpy`` array containing audio samples.
            language: Optional source language code.
            **kwargs: Engine-specific options (for example, ``sample_rate``).

        Returns:
            str: Transcribed text fragment.
        """
        pass

    @abstractmethod
    def get_config_schema(self) -> Dict:
        """Return the JSON schema that describes engine configuration."""
        pass

    def validate_config(self, config: Dict) -> bool:
        """Validate the provided configuration payload."""
        # Default implementation performs basic validation only.
        schema = self.get_config_schema()
        required_fields = schema.get('required', [])
        
        for field in required_fields:
            if field not in config:
                return False

        return True


# Unified list of audio/video extensions normalized to lowercase without dots.
AUDIO_VIDEO_FORMATS: Tuple[str, ...] = (
    "mp3",
    "wav",
    "m4a",
    "flac",
    "ogg",
    "opus",
    "mp4",
    "avi",
    "mkv",
    "mov",
    "webm",
    "mpeg",
    "mpga",
)
"""Audio/video extensions recognized by speech transcription features."""

AUDIO_VIDEO_FORMAT_SET: FrozenSet[str] = frozenset(AUDIO_VIDEO_FORMATS)
"""Extension set that supports fast membership checks."""

AUDIO_VIDEO_SUFFIXES: FrozenSet[str] = frozenset(
    f".{extension}" for extension in AUDIO_VIDEO_FORMAT_SET
)
"""Dot-prefixed extensions suitable for comparing with ``Path.suffix``."""

