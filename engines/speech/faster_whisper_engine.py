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
Faster-Whisper Speech Recognition Engine Implementation

Local speech recognition engine based on the faster-whisper library
Reference: https://github.com/SYSTRAN/faster-whisper
"""

import logging
import os
import threading
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

from config.app_config import get_app_dir
from core.models.registry import get_model_size_metadata
from engines.speech.base import (
    BASE_LANGUAGE_CODES,
    SpeechEngine,
    combine_languages,
    ensure_audio_sample_rate,
)

logger = logging.getLogger(__name__)


class FasterWhisperEngine(SpeechEngine):
    """Faster-Whisper 引擎实现"""

    # 支持的模型大小及其特性（来自模型注册表）
    MODEL_SIZES = dict(get_model_size_metadata())
    _VIDEO_CONTAINER_SUFFIXES = frozenset({".mp4", ".avi", ".mkv", ".mov", ".webm", ".mpeg"})

    def __init__(
        self,
        model_size: str = "base",
        device: str = "auto",
        compute_type: str = "int8",
        download_root: Optional[str] = None,
        model_manager=None,
    ):
        """
        初始化 Faster-Whisper 引擎

        Args:
            model_size: 模型大小（参见模型注册表定义）
            device: 计算设备 ('cpu', 'cuda', 'auto')
            compute_type: 计算类型 ('int8', 'float16', 'float32')
            download_root: 模型下载根目录（向后兼容，如果提供了 model_manager 则忽略）
            model_manager: 模型管理器实例（可选，用于动态模型管理）
        """
        self.model_size = model_size
        self.model_manager = model_manager
        self.model = None
        self._vad_model = None
        self._model_available = False  # 标记模型是否可用
        self._model_state_lock = threading.RLock()

        # Validate and adjust device configuration
        from utils.gpu_detector import GPUDetector

        self.device, self.compute_type, warning = GPUDetector.validate_device_config(
            device, compute_type
        )

        if warning:
            logger.warning(warning)

        # 如果提供了 model_manager，检查模型是否已下载
        if self.model_manager:
            model_info = self.model_manager.get_model(model_size)
            if model_info and model_info.is_downloaded:
                # 使用模型管理器提供的路径
                self.download_root = str(Path(model_info.local_path).parent)
                self._model_available = True
                logger.info(
                    f"Using ModelManager: model={model_size}, " f"path={model_info.local_path}"
                )
            else:
                # 模型未下载，尝试查找已下载的模型作为备选
                downloaded_models = self.model_manager.get_downloaded_models()
                if downloaded_models:
                    # 选择第一个已下载的模型作为备选
                    fallback_model = downloaded_models[0]
                    logger.warning(
                        f"Model '{model_size}' is not downloaded. "
                        f"Using '{fallback_model.name}' as fallback."
                    )
                    self.model_size = fallback_model.name
                    self.download_root = str(Path(fallback_model.local_path).parent)
                    self._model_available = True
                else:
                    # 没有任何已下载的模型
                    logger.warning(
                        f"Model '{model_size}' is not downloaded and no fallback models available. "
                        f"Transcription will be unavailable until a model is downloaded. "
                        f"Please download a model from Settings > Model Management."
                    )
                    self._model_available = False
                    self.download_root = None
        else:
            # 向后兼容：使用传统的 download_root 参数
            self.download_root = download_root or str(get_app_dir() / "models")
            # 确保模型目录存在
            Path(self.download_root).mkdir(parents=True, exist_ok=True)
            self._model_available = True  # 假设模型可用（向后兼容）
            logger.info(
                f"Using legacy mode (no ModelManager): "
                f"model={model_size}, download_root={self.download_root}"
            )

        logger.info(
            f"Initializing Faster-Whisper engine: "
            f"model={model_size}, device={device}, compute_type={compute_type}, "
            f"available={self._model_available}"
        )

    def _record_model_usage(self, model_name: Optional[str] = None) -> None:
        """在模型管理器中记录一次模型使用。"""
        if not self.model_manager:
            return

        target_model_name = model_name or self.model_size
        try:
            self.model_manager.mark_model_used(target_model_name)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Failed to record usage for model '%s': %s",
                target_model_name,
                exc,
                exc_info=True,
            )

    def _load_model(self):
        """延迟加载模型"""
        with self._model_state_lock:
            # 如果模型已加载，直接返回
            if self.model is not None:
                return

            # 每次尝试加载前都重新检查模型状态，以反映最新的下载结果
            if self.model_manager:
                self._refresh_model_status()

            if self.model is None:
                # 首先检查模型是否可用
                if not self._model_available:
                    # 提供更详细的错误信息
                    if self.model_manager:
                        downloaded_models = self.model_manager.get_downloaded_models()
                        if downloaded_models:
                            available_names = ", ".join(m.name for m in downloaded_models)
                            error_msg = (
                                f"Model '{self.model_size}' is not downloaded. "
                                f"Available models: {available_names}. "
                                f"Please select an available model in Settings > Transcription, "
                                f"or download '{self.model_size}' from Settings > Model Management."
                            )
                        else:
                            error_msg = (
                                "No speech recognition models are downloaded. "
                                "Please download a model from Settings > Model Management."
                            )
                    else:
                        error_msg = (
                            f"Model '{self.model_size}' is not available. "
                            "Please check your model configuration."
                        )
                    logger.error(error_msg)
                    raise ValueError(error_msg)

                try:
                    from faster_whisper import WhisperModel

                    logger.info(f"Loading Faster-Whisper model: {self.model_size}")

                    # 确定模型路径
                    if self.model_manager:
                        # 使用 ModelManager 管理的模型
                        model_info = self.model_manager.get_model(self.model_size)
                        if not model_info or not model_info.is_downloaded:
                            error_msg = (
                                f"Model '{self.model_size}' is not available. "
                                f"Please download it from Settings > Model Management."
                            )
                            logger.error(error_msg)
                            raise ValueError(error_msg)

                        # 使用模型的本地路径
                        model_path = model_info.local_path
                        logger.info(f"Loading model from: {model_path}")
                    else:
                        # 向后兼容：使用 model_size 和 download_root
                        model_path = self.model_size

                    # 确保在 macOS/非 CUDA 环境下使用 CPU
                    device = self.device
                    compute_type = self.compute_type

                    # 如果遇到 CUDA 错误，强制使用 CPU
                    try:
                        if self.model_manager:
                            # 使用本地路径加载模型
                            self.model = WhisperModel(
                                model_path, device=device, compute_type=compute_type
                            )
                        else:
                            # 使用 model_size 和 download_root 加载模型
                            self.model = WhisperModel(
                                model_path,
                                device=device,
                                compute_type=compute_type,
                                download_root=self.download_root,
                            )
                    except ValueError as e:
                        if "CUDA" in str(e):
                            logger.warning(f"CUDA not available: {e}. Falling back to CPU.")
                            device = "cpu"
                            compute_type = "int8"
                            self.device = device
                            self.compute_type = compute_type

                            if self.model_manager:
                                self.model = WhisperModel(
                                    model_path, device=device, compute_type=compute_type
                                )
                            else:
                                self.model = WhisperModel(
                                    model_path,
                                    device=device,
                                    compute_type=compute_type,
                                    download_root=self.download_root,
                                )
                        else:
                            raise

                    logger.info(
                        f"Model loaded successfully (device={device}, compute_type={compute_type})"
                    )
                except ImportError:
                    raise ImportError(
                        "faster-whisper is not installed. "
                        "Please install it with: pip install faster-whisper"
                    )
                except Exception as e:
                    logger.error(f"Failed to load model: {e}")
                    raise

    def _load_vad_model(self):
        """加载 VAD 模型（用于实时转录）"""
        if self._vad_model is None:
            try:
                import torch

                # 尝试加载 silero-vad
                self._vad_model, utils = torch.hub.load(
                    repo_or_dir="snakers4/silero-vad",
                    model="silero_vad",
                    force_reload=False,
                    onnx=False,
                )
                logger.info("VAD model loaded successfully")
            except Exception as e:
                logger.warning(
                    f"Failed to load VAD model: {e}. VAD will be disabled for streaming."
                )
                self._vad_model = None

    def is_model_available(self) -> bool:
        """
        检查模型是否可用

        Returns:
            bool: 模型是否已下载并可用
        """
        # 每次检查时都刷新状态，确保反映最新的下载结果
        if self.model_manager:
            self._refresh_model_status()

        return self._model_available

    def _refresh_model_status(self) -> None:
        """根据 ModelManager 的最新信息刷新模型缓存状态。"""
        with self._model_state_lock:
            if not self.model_manager:
                return

            model_info = self.model_manager.get_model(self.model_size)
            if model_info and model_info.is_downloaded:
                self._model_available = True
                if model_info.local_path:
                    self.download_root = str(Path(model_info.local_path).parent)
            else:
                self._model_available = False
                self.download_root = None

    def _apply_runtime_model_selection(
        self,
        model_name: Optional[str],
        model_path: Optional[str] = None,
    ) -> None:
        """Apply per-request model override for batch/realtime calls."""
        with self._model_state_lock:
            if not model_name or model_name == self.model_size:
                if model_path:
                    self.download_root = str(Path(model_path).expanduser().parent)
                return

            if self.model_manager:
                model_info = self.model_manager.get_model(model_name)
                if not model_info or not model_info.is_downloaded:
                    raise ValueError(
                        f"Model '{model_name}' is not downloaded. "
                        "Please download it from Settings > Model Management."
                    )

            self.model_size = model_name
            if model_path:
                self.download_root = str(Path(model_path).expanduser().parent)
            self.model = None
            self._refresh_model_status()
            logger.info("Switched faster-whisper runtime model to: %s", model_name)

    def _prepare_active_model(
        self,
        model_name: Optional[str] = None,
        model_path: Optional[str] = None,
    ):
        """Prepare and snapshot active model for a transcription request."""
        with self._model_state_lock:
            self._apply_runtime_model_selection(model_name, model_path)
            self._load_model()
            return self.model, self.model_size

    def get_name(self) -> str:
        """获取引擎名称"""
        return f"faster-whisper-{self.model_size}"

    def get_supported_languages(self) -> List[str]:
        """获取支持的语言列表"""
        # Whisper 支持的基础语言
        return combine_languages(BASE_LANGUAGE_CODES)

    def _probe_duration_with_soundfile(self, audio_path: str) -> Optional[float]:
        """Probe media duration using soundfile when supported."""
        try:
            import soundfile as sf

            info = sf.info(audio_path)
            duration = float(getattr(info, "duration", 0.0) or 0.0)
            if duration > 0:
                logger.debug("Audio duration: %.2fs (via soundfile)", duration)
                return duration
        except Exception as exc:
            logger.debug("Duration probe via soundfile skipped/failed for %s: %s", audio_path, exc)
        return None

    def _probe_duration_with_ffprobe(self, audio_path: str) -> Optional[float]:
        """Probe media duration using ffprobe."""
        try:
            import json
            import subprocess

            result = subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "quiet",
                    "-print_format",
                    "json",
                    "-show_format",
                    audio_path,
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                logger.debug(
                    "Duration probe via ffprobe failed for %s: returncode=%s stderr=%s",
                    audio_path,
                    result.returncode,
                    (result.stderr or "").strip(),
                )
                return None

            probe_data = json.loads(result.stdout or "{}")
            raw_duration = probe_data.get("format", {}).get("duration")
            duration = float(raw_duration) if raw_duration is not None else 0.0
            if duration > 0:
                logger.debug("Audio duration: %.2fs (via ffprobe)", duration)
                return duration
        except Exception as exc:
            logger.debug("Duration probe via ffprobe skipped/failed for %s: %s", audio_path, exc)
        return None

    def _estimate_duration_from_file_size(self, audio_path: str) -> Optional[float]:
        """Estimate duration from file size as a last resort."""
        try:
            file_size = os.path.getsize(audio_path)
            # Rough estimate with assumed 128kbps average bitrate.
            duration = file_size / (128 * 1024 / 8)
            if duration > 0:
                logger.debug("Audio duration: %.2fs (estimated from file size)", duration)
                return duration
        except Exception as exc:
            logger.debug("Duration estimation from file size failed for %s: %s", audio_path, exc)
        return None

    def _detect_audio_duration(self, audio_path: str) -> Optional[float]:
        """
        Detect media duration with format-aware probing order.

        Video containers usually fail with soundfile; prefer ffprobe first to avoid noisy logs.
        """
        suffix = Path(audio_path).suffix.lower()
        if suffix in self._VIDEO_CONTAINER_SUFFIXES:
            audio_duration = self._probe_duration_with_ffprobe(audio_path)
            if audio_duration is None:
                audio_duration = self._probe_duration_with_soundfile(audio_path)
        else:
            audio_duration = self._probe_duration_with_soundfile(audio_path)
            if audio_duration is None:
                audio_duration = self._probe_duration_with_ffprobe(audio_path)

        if audio_duration is None:
            audio_duration = self._estimate_duration_from_file_size(audio_path)
        if audio_duration is None:
            logger.warning(
                "Could not determine media duration for %s; progress updates may be limited",
                audio_path,
            )
        return audio_duration

    async def transcribe_file(
        self, audio_path: str, language: Optional[str] = None, **kwargs
    ) -> Dict:
        """
        批量转录音频文件

        Args:
            audio_path: 音频文件路径
            language: 源语言代码
            **kwargs: 额外参数
                - beam_size: beam search 大小（默认 5）
                - vad_filter: 是否启用 VAD 过滤（默认 True）
                - vad_min_silence_duration_ms: VAD 最小静音时长
                  （默认 500ms）
                - progress_callback: 进度回调函数
                  (progress: float) -> None
        """
        active_model, active_model_name = self._prepare_active_model(
            kwargs.get("model_name"),
            kwargs.get("model_path"),
        )

        beam_size = kwargs.get("beam_size", 5)
        vad_filter = kwargs.get("vad_filter", True)
        vad_min_silence_duration_ms = kwargs.get("vad_min_silence_duration_ms", 500)
        progress_callback = kwargs.get("progress_callback")

        logger.info(f"Transcribing file: {audio_path}, language={language}")

        try:
            # 首先获取音频时长以计算进度
            audio_duration = self._detect_audio_duration(audio_path)

            # 定义一个同步函数来执行完整的转录过程
            def do_transcription():
                """在线程池中执行的同步转录函数"""
                # 执行转录（返回迭代器）
                segments_iterator, transcribe_info = active_model.transcribe(
                    audio_path,
                    language=language,
                    beam_size=beam_size,
                    vad_filter=vad_filter,
                    vad_parameters=(
                        dict(min_silence_duration_ms=vad_min_silence_duration_ms)
                        if vad_filter
                        else None
                    ),
                )

                # 转换为标准格式，同时更新进度
                result_segments = []
                last_progress = 0.0
                segment_count = 0

                logger.info("Starting to iterate through segments")
                for segment in segments_iterator:
                    segment_count += 1
                    result_segments.append(
                        {"start": segment.start, "end": segment.end, "text": segment.text.strip()}
                    )

                    # Log every 10 segments
                    if segment_count % 10 == 0:
                        logger.debug(f"Processed {segment_count} segments")

                    # 更新进度（基于已处理的音频时长或段落数）
                    if progress_callback:
                        if audio_duration and audio_duration > 0:
                            # 计算进度：已处理时长 / 总时长 * 80 + 10
                            # 10-90% 用于转录，前10%用于加载，后10%用于保存
                            current_progress = min(
                                90.0, (segment.end / audio_duration) * 80.0 + 10.0
                            )
                        else:
                            # 如果没有时长信息，基于段落数估算进度
                            # 假设平均每分钟30个段落，最多估算到85%
                            estimated_progress = min(85.0, 10.0 + (segment_count / 30.0) * 2.5)
                            current_progress = estimated_progress

                        # 只在进度变化超过1%时更新，避免过于频繁
                        if current_progress - last_progress >= 1.0:
                            try:
                                progress_callback(current_progress)
                                last_progress = current_progress
                                logger.debug(
                                    f"Progress: {current_progress:.1f}% (segment {segment_count})"
                                )
                            except Exception as e:
                                logger.error(f"Error in progress callback: {e}")

                logger.info(f"Finished iterating, processed {segment_count} segments")

                # 如果有进度回调，设置为90%（转录完成，准备保存）
                if progress_callback:
                    try:
                        progress_callback(90.0)
                    except Exception as e:
                        logger.error(f"Error in final progress callback: {e}")

                return result_segments, transcribe_info

            # 在线程池中执行转录（避免阻塞事件循环）
            import asyncio

            loop = asyncio.get_event_loop()

            logger.info("Starting transcription in thread pool")
            result_segments, transcribe_info = await loop.run_in_executor(
                None, do_transcription  # 使用默认线程池
            )
            logger.info(f"Transcription completed with {len(result_segments)} segments")

            result = {
                "segments": result_segments,
                "language": transcribe_info.language,
                "duration": audio_duration
                or (transcribe_info.duration if hasattr(transcribe_info, "duration") else 0.0),
            }

            logger.info(
                f"Transcription completed: {len(result_segments)} segments, "
                f"language={transcribe_info.language}"
            )

            # 转录成功后记录模型使用
            self._record_model_usage(active_model_name)
            return result

        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            raise

    async def transcribe_stream(
        self,
        audio_chunk: np.ndarray,
        language: Optional[str] = None,
        sample_rate: Optional[int] = None,
        **kwargs,
    ) -> str:
        """
        实时转录音频流

        使用滑动窗口机制和 VAD 检测

        Args:
            audio_chunk: 音频数据块
            language: 源语言代码
            sample_rate: 音频块的采样率
            **kwargs: 额外参数
                - use_vad: 是否使用 VAD（默认 False，因为外部已经做了 VAD）
        """
        active_model, _ = self._prepare_active_model()

        # 检查音频长度
        if len(audio_chunk) == 0:
            logger.debug("Empty audio chunk, skipping transcription")
            return ""

        # 检查音频能量（避免转录静音）
        audio_energy = np.sqrt(np.mean(audio_chunk**2))
        if audio_energy < 0.01:  # 能量阈值
            logger.debug(f"Audio energy too low ({audio_energy:.4f}), skipping transcription")
            return ""

        logger.debug(
            f"Transcribing audio chunk: length={len(audio_chunk)}, energy={audio_energy:.4f}"
        )

        processed_audio, effective_rate = ensure_audio_sample_rate(audio_chunk, sample_rate, 16000)

        use_vad = kwargs.get("use_vad", False)

        # 如果启用 VAD，先进行语音活动检测
        if use_vad:
            self._load_vad_model()
            if self._vad_model is not None:
                # 检测语音活动
                speech_timestamps = self._detect_speech(processed_audio)
                if not speech_timestamps:
                    # 没有检测到语音
                    logger.debug("No speech detected by internal VAD")
                    return ""

                # 提取语音段落
                processed_audio = self._extract_speech_segments(processed_audio, speech_timestamps)

        try:
            # 转录音频块
            # 注意：faster-whisper 需要音频文件路径，所以需要临时保存
            import tempfile

            import soundfile as sf

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
                tmp_path = tmp_file.name

            try:
                # 写入音频文件
                sf.write(tmp_path, processed_audio, effective_rate or 16000)
                logger.debug(f"Wrote audio to temp file: {tmp_path}")

                # 转录
                segments, info = active_model.transcribe(
                    tmp_path,
                    language=language,
                    beam_size=1,  # 实时转录使用较小的 beam size
                    vad_filter=False,  # 已经做过 VAD
                    word_timestamps=False,  # 不需要词级时间戳
                )

                # 合并所有段落的文本
                text_parts = []
                for seg in segments:
                    text_parts.append(seg.text.strip())

                text = " ".join(text_parts)
                lang = info.language if hasattr(info, "language") else "unknown"
                logger.debug(f"Transcription result: '{text}' (language: {lang})")
                return {"text": text, "language": lang}


            finally:
                # 清理临时文件
                try:
                    if os.path.exists(tmp_path):
                        os.unlink(tmp_path)
                except Exception as e:
                    logger.warning(f"Failed to delete temp file {tmp_path}: {e}")

        except Exception as e:
            logger.error(f"Stream transcription failed: {e}", exc_info=True)
            return ""

    def _detect_speech(self, audio_chunk: np.ndarray) -> List[Dict]:
        """
        使用 VAD 检测语音活动

        Args:
            audio_chunk: 音频数据

        Returns:
            List[Dict]: 语音时间戳列表 [{'start': float, 'end': float}, ...]
        """
        if self._vad_model is None:
            return [{"start": 0, "end": len(audio_chunk) / 16000}]

        try:
            import torch

            # 转换为 torch tensor
            audio_tensor = torch.from_numpy(audio_chunk).float()

            # 使用 VAD 模型检测语音（silero-vad 返回概率）
            # 注意：silero-vad 需要使用 get_speech_timestamps 函数
            # 但这里我们只是简单检测，所以直接返回整个音频段
            # 如果需要更精确的 VAD，应该使用 engines/audio/vad.py 中的 VADDetector

            # 简单检查：使用模型预测语音概率
            speech_prob = self._vad_model(audio_tensor, 16000).item()

            # 如果语音概率高于阈值，返回整个音频段
            if speech_prob > 0.5:
                return [{"start": 0, "end": len(audio_chunk) / 16000}]
            else:
                return []

        except Exception as e:
            logger.warning(f"VAD detection failed: {e}, processing all audio")
            return [{"start": 0, "end": len(audio_chunk) / 16000}]

    def _extract_speech_segments(
        self, audio_chunk: np.ndarray, speech_timestamps: List[Dict]
    ) -> np.ndarray:
        """
        从音频中提取语音段落

        Args:
            audio_chunk: 完整音频数据
            speech_timestamps: 语音时间戳列表

        Returns:
            np.ndarray: 提取的语音段落
        """
        if not speech_timestamps:
            return audio_chunk

        segments = []
        for ts in speech_timestamps:
            start_sample = int(ts["start"] * 16000)
            end_sample = int(ts["end"] * 16000)
            segments.append(audio_chunk[start_sample:end_sample])

        # 合并所有语音段落
        if segments:
            return np.concatenate(segments)
        else:
            return audio_chunk

    def get_config_schema(self) -> Dict:
        """获取配置 Schema"""
        return {
            "type": "object",
            "properties": {
                "model_size": {
                    "type": "string",
                    "enum": list(self.MODEL_SIZES.keys()),
                    "default": "base",
                    "description": "模型大小",
                },
                "device": {
                    "type": "string",
                    "enum": ["cpu", "cuda", "auto"],
                    "default": "cpu",
                    "description": "计算设备",
                },
                "compute_type": {
                    "type": "string",
                    "enum": ["int8", "float16", "float32"],
                    "default": "int8",
                    "description": "计算精度",
                },
                "download_root": {"type": "string", "description": "模型下载目录"},
            },
            "required": [],
        }
