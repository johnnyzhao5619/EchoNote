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
"""
语音活动检测 (Voice Activity Detection)

集成 silero-vad 和 webrtcvad 实现语音段落检测
"""

import logging
from typing import Dict, List

import numpy as np

logger = logging.getLogger(__name__)

class VADDetector:
    """语音活动检测器"""

    def __init__(
        self, threshold: float = 0.5, silence_duration_ms: int = 2000, method: str = "silero"
    ):
        """
        初始化 VAD 检测器

        Args:
            threshold: 语音检测阈值（0.0-1.0），用于 VAD 灵敏度控制
            silence_duration_ms: 静音阈值（毫秒），超过此时长的静音视为语音段落结束
            method: VAD 方法 ('silero' 或 'webrtc')
        """
        self.threshold = threshold
        self.silence_duration_ms = silence_duration_ms
        self.method = method
        self.model = None
        self._initialize_model()

    def _initialize_model(self):
        """初始化 VAD 模型"""
        if self.method == "silero":
            self._initialize_silero()
        elif self.method == "webrtc":
            self._initialize_webrtc()
        else:
            raise ValueError(f"Unsupported VAD method: {self.method}")

    def _initialize_silero(self):
        """初始化 Silero VAD 模型"""
        try:
            import torch

            logger.info("Loading Silero VAD model...")
            self.model, utils = torch.hub.load(
                repo_or_dir="snakers4/silero-vad",
                model="silero_vad",
                force_reload=False,
                onnx=False,
            )
            self.get_speech_timestamps = utils[0]
            logger.info("Silero VAD model loaded successfully")

        except Exception as e:
            logger.error(f"Failed to load Silero VAD model: {e}")
            raise

    def _initialize_webrtc(self):
        """初始化 WebRTC VAD"""
        try:
            import webrtcvad

            logger.info("Initializing WebRTC VAD...")
            # 创建 VAD 实例，aggressiveness 级别 0-3（3 最激进）
            self.model = webrtcvad.Vad(2)
            logger.info("WebRTC VAD initialized successfully")

        except ImportError:
            raise ImportError(
                "webrtcvad is not installed. " "Please install it with: pip install webrtcvad"
            )

    def detect_speech(self, audio: np.ndarray, sample_rate: int = 16000) -> List[Dict]:
        """
        检测音频中的语音段落

        Args:
            audio: 音频数据（numpy array）
            sample_rate: 采样率（Hz）

        Returns:
            List[Dict]: 语音时间戳列表
                [
                    {'start': float, 'end': float},  # 时间单位：秒
                    ...
                ]
        """
        if self.method == "silero":
            return self._detect_speech_silero(audio, sample_rate)
        elif self.method == "webrtc":
            return self._detect_speech_webrtc(audio, sample_rate)
        else:
            return []

    def _detect_speech_silero(self, audio: np.ndarray, sample_rate: int) -> List[Dict]:
        """使用 Silero VAD 检测语音"""
        try:
            import torch

            # 转换为 torch tensor
            audio_tensor = torch.from_numpy(audio).float()

            # 获取语音时间戳
            # 注意：不使用 return_seconds=True，因为某些版本的 silero-vad 可能有 bug
            speech_timestamps = self.get_speech_timestamps(
                audio_tensor,
                self.model,
                sampling_rate=sample_rate,
                threshold=self.threshold,
                min_silence_duration_ms=self.silence_duration_ms,
            )

            # 转换为标准格式（从样本数转换为秒）
            result = []
            for ts in speech_timestamps:
                # silero-vad 返回的时间戳是样本数，需要转换为秒
                start_sec = (
                    ts["start"] / sample_rate
                    if isinstance(ts["start"], (int, float))
                    else ts["start"]
                )
                end_sec = (
                    ts["end"] / sample_rate if isinstance(ts["end"], (int, float)) else ts["end"]
                )
                result.append({"start": start_sec, "end": end_sec})

            logger.debug(f"Detected {len(result)} speech segments")
            return result

        except NameError as e:
            # 捕获 silero-vad 内部的 NameError（如 'current_time' 未定义）
            logger.error(
                f"Silero VAD internal error: {e}. This may be a version compatibility issue."
            )
            logger.info("Falling back to processing all audio without VAD")
            # 返回整个音频段作为语音
            duration = len(audio) / sample_rate
            return [{"start": 0.0, "end": duration}]

        except Exception as e:
            logger.error(f"Silero VAD detection failed: {e}")
            # 返回整个音频段作为语音
            duration = len(audio) / sample_rate
            return [{"start": 0.0, "end": duration}]

    def _detect_speech_webrtc(self, audio: np.ndarray, sample_rate: int) -> List[Dict]:
        """使用 WebRTC VAD 检测语音"""
        try:
            # WebRTC VAD 只支持 8kHz, 16kHz, 32kHz, 48kHz
            if sample_rate not in [8000, 16000, 32000, 48000]:
                logger.warning(
                    f"WebRTC VAD requires sample rate of 8k/16k/32k/48k, got {sample_rate}"
                )
                return []

            # 转换为 16-bit PCM
            audio_int16 = (audio * 32767).astype(np.int16)
            audio_bytes = audio_int16.tobytes()

            # WebRTC VAD 需要固定大小的帧（10ms, 20ms, 或 30ms）
            frame_duration_ms = 30
            frame_size = int(sample_rate * frame_duration_ms / 1000)
            frame_bytes = frame_size * 2  # 16-bit = 2 bytes per sample

            # 检测每一帧
            speech_frames = []
            for i in range(0, len(audio_bytes) - frame_bytes, frame_bytes):
                frame = audio_bytes[i : i + frame_bytes]
                is_speech = self.model.is_speech(frame, sample_rate)
                speech_frames.append(is_speech)

            # 合并连续的语音帧
            result = []
            in_speech = False
            start_frame = 0

            for i, is_speech in enumerate(speech_frames):
                if is_speech and not in_speech:
                    # 语音开始
                    in_speech = True
                    start_frame = i
                elif not is_speech and in_speech:
                    # 语音结束
                    in_speech = False
                    start_time = start_frame * frame_duration_ms / 1000
                    end_time = i * frame_duration_ms / 1000
                    result.append({"start": start_time, "end": end_time})

            # 处理最后一个语音段落
            if in_speech:
                start_time = start_frame * frame_duration_ms / 1000
                end_time = len(speech_frames) * frame_duration_ms / 1000
                result.append({"start": start_time, "end": end_time})

            # 过滤掉太短的段落（小于静音阈值）
            min_duration = self.silence_duration_ms / 1000
            result = [seg for seg in result if (seg["end"] - seg["start"]) >= min_duration]

            logger.debug(f"Detected {len(result)} speech segments")
            return result

        except Exception as e:
            logger.error(f"WebRTC VAD detection failed: {e}")
            return []

    def extract_speech_segments(
        self, audio: np.ndarray, speech_timestamps: List[Dict], sample_rate: int = 16000
    ) -> np.ndarray:
        """
        从音频中提取语音段落

        Args:
            audio: 完整音频数据
            speech_timestamps: 语音时间戳列表
            sample_rate: 采样率（Hz）

        Returns:
            np.ndarray: 提取的语音段落（合并后）
        """
        if not speech_timestamps:
            return audio

        rate = sample_rate if sample_rate and sample_rate > 0 else 16000
        segments = []

        for ts in speech_timestamps:
            start_sample = int(ts["start"] * rate)
            end_sample = int(ts["end"] * rate)

            # 确保索引在有效范围内
            start_sample = max(0, start_sample)
            end_sample = min(len(audio), end_sample)

            if start_sample < end_sample:
                segments.append(audio[start_sample:end_sample])

        # 合并所有语音段落
        if segments:
            return np.concatenate(segments)
        else:
            return audio

    def extract_speech(
        self, audio: np.ndarray, timestamps: list, sample_rate: int = 16000
    ) -> np.ndarray:
        """
        从音频中提取语音段落（别名方法，保持 API 一致性）

        Args:
            audio: 完整音频数据
            timestamps: 语音时间戳列表
            sample_rate: 采样率（Hz）

        Returns:
            np.ndarray: 提取的语音段落
        """
        return self.extract_speech_segments(audio, timestamps, sample_rate=sample_rate)

    def is_speech_present(self, audio: np.ndarray, sample_rate: int = 16000) -> bool:
        """
        快速检查音频中是否存在语音

        Args:
            audio: 音频数据
            sample_rate: 采样率

        Returns:
            bool: 是否存在语音
        """
        speech_timestamps = self.detect_speech(audio, sample_rate)
        return len(speech_timestamps) > 0
