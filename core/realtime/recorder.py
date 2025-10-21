"""
实时录制管理器

实现实时音频录制、转录和翻译的完整流程
"""

import asyncio
import contextlib
import json
import logging
import os
import shutil
import subprocess
import threading
from datetime import datetime, timedelta
from typing import Optional, Dict, AsyncIterator, Callable, List, Any
import numpy as np
import soundfile as sf

from core.realtime.audio_buffer import AudioBuffer

logger = logging.getLogger(__name__)


class RealtimeRecorder:
    """实时录制管理器"""

    TRANSLATION_TASK_TIMEOUT = 5.0
    TRANSLATION_TASK_SHUTDOWN_TIMEOUT = 2.0

    def __init__(self, audio_capture, speech_engine, translation_engine,
                 db_connection, file_manager, i18n=None):
        """
        初始化实时录制管理器

        Args:
            audio_capture: AudioCapture 实例
            speech_engine: SpeechEngine 实例
            translation_engine: TranslationEngine 实例（可选）
            db_connection: 数据库连接
            file_manager: FileManager 实例
            i18n: 可选的国际化管理器，用于翻译提示文本
        """
        self.audio_capture = audio_capture
        self.speech_engine = speech_engine
        self.translation_engine = translation_engine
        self.db = db_connection
        self.file_manager = file_manager
        self.i18n = i18n

        if self.audio_capture is None:
            logger.warning(
                "Audio capture not available. Real-time recording features will remain disabled."
            )

        # 默认采样率
        self.sample_rate = 16000
        if self.audio_capture is not None:
            capture_rate = getattr(self.audio_capture, 'sample_rate', None)
            if isinstance(capture_rate, (int, float)) and capture_rate > 0:
                self.sample_rate = int(capture_rate)

        # 录制状态
        self.is_recording = False
        self.recording_start_time = None
        self.recording_audio_buffer = []
        self.audio_buffer: Optional[AudioBuffer] = None

        # 转录和翻译队列（在每次会话开始时重新构建）
        self.transcription_queue: Optional[asyncio.Queue] = None
        self.translation_queue: Optional[asyncio.Queue] = None

        # 面向外部消费者的文本流队列（用于生成器接口）
        self._transcription_stream_queue: Optional[asyncio.Queue] = None
        self._translation_stream_queue: Optional[asyncio.Queue] = None

        # 异步任务
        self.processing_task = None
        self.translation_task = None

        # 录制选项
        self.current_options = {}

        # 回调函数（用于 UI 更新）
        self.on_transcription_update = None
        self.on_translation_update = None
        self.on_error = None
        self.on_audio_data = None  # 音频数据回调（用于可视化等）
        self.on_marker_added = None

        # 累积的转录和翻译文本
        self.accumulated_transcription = []
        self.accumulated_translation = []

        # 标记数据
        self.markers: List[Dict[str, Any]] = []
        self._marker_lock = threading.Lock()

        # 事件循环引用（用于线程安全的队列操作）
        self._event_loop = None

        logger.info("RealtimeRecorder initialized")

    def _translate(self, key: str, default: str, **kwargs) -> str:
        """Return localized text for the given key with graceful fallback."""
        if self.i18n is not None:
            try:
                translated = self.i18n.t(key, **kwargs)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Translation lookup failed for %s: %s", key, exc)
            else:
                if translated and translated != key:
                    return translated

        try:
            return default.format(**kwargs)
        except Exception:  # noqa: BLE001
            return default

    def audio_input_available(self) -> bool:
        """实时录音输入是否可用。"""
        return self.audio_capture is not None

    def set_callbacks(
        self,
        on_transcription: Optional[Callable[[str], None]] = None,
        on_translation: Optional[Callable[[str], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
        on_audio_data: Optional[Callable[[np.ndarray], None]] = None,
        on_marker: Optional[Callable[[Dict[str, Any]], None]] = None
    ):
        """
        设置回调函数（用于 UI 更新）

        Args:
            on_transcription: 转录文本更新回调
            on_translation: 翻译文本更新回调
            on_error: 错误回调
            on_audio_data: 音频数据回调（用于可视化等）
            on_marker: 标记创建回调
        """
        self.on_transcription_update = on_transcription
        self.on_translation_update = on_translation
        self.on_error = on_error
        self.on_audio_data = on_audio_data
        self.on_marker_added = on_marker

    def _initialize_session_queues(self) -> None:
        """在当前事件循环中创建新的异步队列。"""
        for queue in (
            self.transcription_queue,
            self.translation_queue,
            self._transcription_stream_queue,
            self._translation_stream_queue,
        ):
            self._drain_queue(queue)

        self.transcription_queue = asyncio.Queue()
        self.translation_queue = asyncio.Queue()
        self._transcription_stream_queue = asyncio.Queue()
        self._translation_stream_queue = asyncio.Queue()

    def _release_session_queues(self) -> None:
        """释放异步队列引用，等待下次会话重新创建。"""
        self.transcription_queue = None
        self.translation_queue = None
        self._transcription_stream_queue = None
        self._translation_stream_queue = None
        self._event_loop = None

    async def start_recording(
        self, input_source: Optional[int] = None,
        options: Optional[Dict] = None,
        event_loop=None
    ):
        """
        开始录制

        Args:
            input_source: 音频输入设备索引（None 表示默认设备）
            options: 录制选项
                - language: 源语言代码
                - enable_translation: 是否启用翻译
                - target_language: 目标语言代码
                - recording_format: 录音格式（'wav' 或 'mp3'）
                - save_recording: 是否保存录音文件
                - save_transcript: 是否保存转录文本
                - create_calendar_event: 是否创建日历事件
            event_loop: 事件循环（如果提供，将使用此循环）
        """
        if self.is_recording:
            logger.warning("Recording is already in progress")
            return

        if self.audio_capture is None:
            raise RuntimeError(
                "Audio capture is not available. Install PyAudio to enable real-time recording."
            )

        # 保存事件循环引用（用于线程安全的队列操作）
        if event_loop is not None:
            self._event_loop = event_loop
        else:
            self._event_loop = asyncio.get_event_loop()

        # 保存选项
        self.current_options = options or {}

        # 同步采样率设置（优先使用选项覆盖，其次使用音频采集配置）
        option_rate = self.current_options.get('sample_rate')
        if isinstance(option_rate, (int, float)) and option_rate > 0:
            self.sample_rate = int(option_rate)
        elif self.audio_capture is not None:
            capture_rate = getattr(self.audio_capture, 'sample_rate', None)
            if isinstance(capture_rate, (int, float)) and capture_rate > 0:
                self.sample_rate = int(capture_rate)
        else:
            self.sample_rate = 16000

        if self.audio_capture is not None and hasattr(self.audio_capture, 'sample_rate'):
            try:
                self.audio_capture.sample_rate = self.sample_rate
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"Failed to apply sample rate to audio capture: {exc}")

        # 为本次会话重建异步队列，确保绑定当前事件循环
        self._initialize_session_queues()

        # 重置状态
        self.is_recording = True
        self.recording_start_time = datetime.now()
        self.recording_audio_buffer = []
        self.audio_buffer = AudioBuffer(sample_rate=self.sample_rate)
        self.accumulated_transcription = []
        self.accumulated_translation = []
        with self._marker_lock:
            self.markers = []

        try:
            # 启动音频捕获
            self.audio_capture.start_capture(
                device_index=input_source,
                callback=self._audio_callback
            )

            # 启动异步处理任务
            self.processing_task = asyncio.create_task(
                self._process_audio_stream()
            )

            # 如果启用翻译，启动翻译任务
            if self.current_options.get('enable_translation', False):
                self.translation_task = asyncio.create_task(
                    self._process_translation_stream()
                )
        except Exception as exc:
            logger.error(
                "Failed to start real-time recording: %s", exc,
                exc_info=True
            )
            await self._rollback_failed_start()

            message = f"Failed to start recording: {exc}"
            if self.on_error:
                try:
                    self.on_error(message)
                except Exception as callback_exc:  # noqa: BLE001
                    logger.error(
                        "Error invoking start failure callback: %s",
                        callback_exc,
                        exc_info=True
                    )

            raise

        logger.info(f"Recording started (input_source={input_source})")

    def _audio_callback(self, audio_chunk: np.ndarray):
        """
        音频回调函数（在音频捕获线程中调用）

        Args:
            audio_chunk: 音频数据块
        """
        if not self.is_recording:
            return

        # 保存音频数据用于最终保存
        self.recording_audio_buffer.append(audio_chunk.copy())

        # 将音频块放入转录队列（使用线程安全的方式）
        try:
            # 使用 call_soon_threadsafe 来在事件循环中安全地添加任务
            if (
                hasattr(self, '_event_loop')
                and self._event_loop is not None
                and self.transcription_queue is not None
            ):
                self._event_loop.call_soon_threadsafe(
                    self.transcription_queue.put_nowait,
                    audio_chunk.copy()
                )
            else:
                logger.debug("Event loop or transcription queue not ready, audio chunk skipped")
        except Exception as e:
            logger.warning(f"Failed to queue audio chunk: {e}")

        # 调用音频数据回调（用于可视化等）
        if self.on_audio_data:
            try:
                self.on_audio_data(audio_chunk.copy())
            except Exception as e:
                logger.warning(f"Error in audio data callback: {e}")

    async def _process_audio_stream(self):
        """处理音频流的异步任务"""
        logger.info("Audio stream processing started")

        # 导入 VAD 检测器
        from engines.audio.vad import VADDetector

        queue = self.transcription_queue
        stream_queue = self._transcription_stream_queue
        if queue is None or stream_queue is None:
            logger.error("Transcription queues are not initialized; aborting audio stream processing")
            return

        # 创建 VAD 检测器和音频缓冲区
        vad = None
        try:
            vad = VADDetector(
                threshold=0.3,  # 降低阈值，更容易检测到语音
                silence_duration_ms=1500,  # 减少静音时长要求
                method='silero'
            )
            logger.info("VAD detector initialized successfully")
        except Exception as e:
            logger.warning(f"Failed to initialize VAD: {e}. Will process all audio without VAD.")
            # 不返回，继续处理但不使用 VAD

        sample_rate = self.sample_rate if self.sample_rate and self.sample_rate > 0 else 16000

        audio_buffer = self.audio_buffer
        if audio_buffer is None:
            audio_buffer = AudioBuffer(sample_rate=sample_rate)
            self.audio_buffer = audio_buffer

        min_audio_duration = 3.0  # 最小3秒音频才处理

        audio_chunks_received = 0
        transcription_attempts = 0
        last_transcription = ""  # 记录上一次转录结果，用于去重
        translation_queue = self.translation_queue

        async def _process_buffered_audio(force: bool = False) -> None:
            nonlocal last_transcription, transcription_attempts

            pending_duration = audio_buffer.get_duration()
            if pending_duration <= 0:
                return

            if not force and pending_duration < min_audio_duration:
                return

            logger.info(
                "Processing accumulated audio: %.2fs%s",
                pending_duration,
                " (forced)" if force else ""
            )

            window_audio = audio_buffer.get_latest(pending_duration)
            if len(window_audio) == 0:
                audio_buffer.clear()
                return

            logger.debug(f"Window audio size: {len(window_audio)} samples")

            speech_audio = window_audio
            if vad is not None:
                try:
                    speech_timestamps = vad.detect_speech(window_audio, sample_rate)
                    logger.debug(f"VAD detected {len(speech_timestamps)} speech segments")

                    if speech_timestamps:
                        speech_audio = vad.extract_speech(
                            window_audio,
                            speech_timestamps,
                            sample_rate=sample_rate
                        )
                    else:
                        logger.debug("No speech detected by VAD, skipping transcription")
                        audio_buffer.clear()
                        return
                except Exception as e:
                    logger.warning(f"VAD detection failed: {e}, processing all audio")
                    speech_audio = window_audio

            try:
                transcription_attempts += 1
                logger.info(f"Transcription attempt #{transcription_attempts}")

                language = self.current_options.get('language')
                text = await self.speech_engine.transcribe_stream(
                    speech_audio,
                    language=language,
                    sample_rate=self.sample_rate
                )

                logger.info(f"Transcription result: '{text}'")

                if text.strip():
                    if self._is_duplicate_transcription(text, last_transcription):
                        logger.debug(f"Duplicate transcription detected, skipping: {text[:50]}...")
                    else:
                        self.accumulated_transcription.append(text)
                        await stream_queue.put(text)

                        if self.on_transcription_update:
                            try:
                                self.on_transcription_update(text)
                                logger.debug("UI callback invoked successfully")
                            except Exception as e:
                                logger.error(f"Error in transcription callback: {e}")

                        enable_trans = self.current_options.get('enable_translation', False)
                        if enable_trans and translation_queue is not None:
                            await translation_queue.put(text)

                        logger.info(f"Transcribed successfully: {text[:50]}...")
                        last_transcription = text
                else:
                    logger.debug("Transcription returned empty text")
            except Exception as e:
                logger.error(f"Transcription failed: {e}", exc_info=True)
                if self.on_error:
                    self.on_error(f"Transcription error: {e}")
            finally:
                audio_buffer.clear()

        try:
            while self.is_recording or not queue.empty():
                try:
                    audio_chunk = await asyncio.wait_for(
                        queue.get(),
                        timeout=0.5
                    )
                except asyncio.TimeoutError:
                    if not self.is_recording:
                        break
                    continue

                audio_chunks_received += 1
                logger.debug(
                    f"Received audio chunk #{audio_chunks_received}, size: {len(audio_chunk)}"
                )

                audio_buffer.append(audio_chunk)

                try:
                    await _process_buffered_audio(force=False)
                except Exception as e:
                    logger.error(f"Error in audio stream processing: {e}", exc_info=True)
                    if self.on_error:
                        self.on_error(f"Processing error: {e}")
                    if not self.is_recording and queue.empty():
                        break
        except asyncio.CancelledError:
            logger.info("Audio stream processing cancelled")
            raise
        except Exception as e:
            logger.error(f"Error in audio stream processing loop: {e}", exc_info=True)
            if self.on_error:
                self.on_error(f"Processing error: {e}")
        finally:
            try:
                await _process_buffered_audio(force=True)
            except Exception as e:
                logger.error(f"Failed to flush audio buffer: {e}", exc_info=True)
                if self.on_error:
                    self.on_error(f"Processing error: {e}")

            logger.info(
                "Audio stream processing stopped. Total chunks: %s, Transcription attempts: %s",
                audio_chunks_received,
                transcription_attempts
            )

    async def _process_translation_stream(self):
        """处理翻译流的异步任务"""
        logger.info("Translation stream processing started")

        # 检查翻译引擎是否可用
        if not self.translation_engine:
            logger.warning("Translation engine not available")
            if self.on_error:
                self.on_error("Translation not available: No API key configured")
            return

        queue = self.translation_queue
        stream_queue = self._translation_stream_queue
        if queue is None or stream_queue is None:
            logger.error("Translation queues are not initialized; aborting translation stream processing")
            return

        try:
            while self.is_recording or not queue.empty():
                try:
                    # 从队列获取转录文本（超时 0.5 秒）
                    text = await asyncio.wait_for(
                        queue.get(),
                        timeout=0.5
                    )

                    if text is None:
                        logger.debug("Received translation shutdown signal")
                        break

                    # 翻译
                    source_lang = self.current_options.get('language', 'auto')
                    target_lang = self.current_options.get('target_language', 'en')

                    # 翻译引擎已在函数开始时检查
                    translated_text = await self.translation_engine.translate(
                        text,
                        source_lang=source_lang,
                        target_lang=target_lang
                    )

                    if translated_text.strip():
                        # 累积翻译文本
                        self.accumulated_translation.append(translated_text)

                        # 推送到实时翻译流
                        await stream_queue.put(translated_text)

                        # 通知 UI 更新
                        if self.on_translation_update:
                            self.on_translation_update(translated_text)

                        logger.debug(f"Translated: {translated_text}")

                except asyncio.TimeoutError:
                    # 超时，继续等待
                    continue
                except Exception as e:
                    logger.error(f"Error in translation stream processing: {e}")
                    if self.on_error:
                        self.on_error(f"Translation error: {e}")
                    if self.is_recording:
                        continue
                    else:
                        break
        except asyncio.CancelledError:
            logger.info("Translation stream processing cancelled")
            raise

        logger.info("Translation stream processing stopped")

    async def stop_recording(self) -> Dict:
        """
        停止录制

        Returns:
            Dict: 录制结果。始终包含以下键：
                - ``duration`` (float)：录制时长（秒）。
                - ``start_time`` (str)：会话开始时间（ISO 8601）。
                - ``end_time`` (str)：会话结束时间（ISO 8601）。

            根据配置与会话内容，可能额外包含：
                - ``recording_path`` (str)：当 ``save_recording`` 启用且存在音频数据时，指向保存的音频文件。
                - ``transcript_path`` (str)：当 ``save_transcript`` 启用且转录文本生成成功时，指向保存的转录文件。
                - ``translation_path`` (str)：当 ``enable_translation`` 启用且翻译文本生成成功时，指向保存的翻译文件。
                - ``markers`` (List[Dict])：会话期间创建的标记，仅在存在标记时返回。
                - ``markers_path`` (str)：当存在标记且标记导出成功时，指向保存的标记 JSON 文件。
                - ``event_id`` (str)：当 ``create_calendar_event`` 成功创建日历事件时返回；若数据库未配置或创建失败则缺失。
        """
        if not self.is_recording:
            logger.warning("Recording is not in progress")
            return {}

        logger.info("Stopping recording...")

        # 停止录制
        self.is_recording = False

        # 停止音频捕获
        if self.audio_capture is not None:
            self.audio_capture.stop_capture()

        # 等待处理任务完成
        if self.processing_task:
            try:
                await asyncio.wait_for(self.processing_task, timeout=5.0)
            except asyncio.TimeoutError:
                logger.warning("Processing task timeout")
            finally:
                self.processing_task = None

        if self.translation_task:
            await self._ensure_translation_task_stopped()

        # 标记流式队列完成，确保生成器退出
        transcription_stream_queue = self._transcription_stream_queue
        translation_stream_queue = self._translation_stream_queue
        self._signal_stream_completion(transcription_stream_queue)
        self._signal_stream_completion(translation_stream_queue)

        # 计算录制时长
        recording_end_time = datetime.now()
        duration = (
            recording_end_time - self.recording_start_time
        ).total_seconds()

        if self.audio_buffer is not None:
            self.audio_buffer.clear()
            self.audio_buffer = None

        result = {
            'duration': duration,
            'start_time': self.recording_start_time.isoformat(),
            'end_time': recording_end_time.isoformat()
        }

        # 保存录音文件
        if self.current_options.get('save_recording', True):
            recording_path = await self._save_recording()
            result['recording_path'] = recording_path

        # 保存转录文本
        if self.current_options.get('save_transcript', True):
            transcript_path = await self._save_transcript()
            result['transcript_path'] = transcript_path

        # 保存翻译文本（如果启用了翻译）
        if self.current_options.get('enable_translation', False):
            translation_path = await self._save_translation()
            if translation_path:
                result['translation_path'] = translation_path

        with self._marker_lock:
            if self.markers:
                result['markers'] = [marker.copy() for marker in self.markers]
                markers_path = self._save_markers()
                if markers_path:
                    result['markers_path'] = markers_path

        # 创建日历事件
        create_event_requested = self.current_options.get('create_calendar_event', True)
        if create_event_requested and self.db is None:
            logger.info(
                "Skipping calendar event creation: database connection is not configured."
            )
            create_event_requested = False

        if create_event_requested:
            event_id = await self._create_calendar_event(result)
            result['event_id'] = event_id

        logger.info(f"Recording stopped: duration={duration:.2f}s")

        # 本次会话完成后清理队列引用
        self._release_session_queues()

        return result

    async def _ensure_translation_task_stopped(self) -> None:
        """确保翻译任务在停止录音前已完全退出。"""
        task = self.translation_task
        if task is None:
            return

        try:
            await asyncio.wait_for(
                task,
                timeout=self.TRANSLATION_TASK_TIMEOUT
            )
        except asyncio.TimeoutError:
            logger.warning("Translation task timeout; requesting graceful shutdown")
            await self._request_translation_shutdown(task)
        finally:
            self.translation_task = None

    async def _request_translation_shutdown(self, task: asyncio.Task) -> None:
        """向翻译协程发送终止信号并确保其退出。"""
        queue = self.translation_queue
        stream_queue = self._translation_stream_queue

        if queue is not None:
            try:
                queue.put_nowait(None)
            except asyncio.QueueFull:  # pragma: no cover - 默认队列无限大
                logger.warning("Translation queue full when sending shutdown signal")

        if stream_queue is not None:
            self._signal_stream_completion(stream_queue)

        try:
            await asyncio.wait_for(
                task,
                timeout=self.TRANSLATION_TASK_SHUTDOWN_TIMEOUT
            )
        except asyncio.TimeoutError:
            logger.error("Translation task did not stop after shutdown request; cancelling")
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        finally:
            self._drain_queue(queue)
            self._drain_queue(stream_queue)

    async def _save_recording(self) -> str:
        """
        保存录音文件

        Returns:
            str: 录音文件路径
        """
        if not self.recording_audio_buffer:
            logger.warning("No audio data to save")
            return ""

        # 合并所有音频块
        audio_data = np.concatenate(self.recording_audio_buffer)

        # 生成文件名
        timestamp = self.recording_start_time.strftime("%Y%m%d_%H%M%S")
        requested_format = str(
            self.current_options.get('recording_format', 'wav')
        ).lower()
        base_filename = f"recording_{timestamp}"
        mp3_requested = requested_format == 'mp3'
        mp3_supported = False
        if mp3_requested:
            try:
                mp3_supported = self._is_mp3_conversion_available()
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    "Failed to determine MP3 conversion capability: %s", exc
                )
                mp3_supported = False

            if not mp3_supported:
                warning_message = (
                    "MP3 recording requires FFmpeg. Saved recording as WAV instead."
                )
                logger.warning(warning_message)
                if self.on_error:
                    self.on_error(warning_message)

        final_format = 'mp3' if mp3_requested and mp3_supported else 'wav'
        def _generate_filename(extension: str) -> str:
            return self.file_manager.create_unique_filename(
                base_filename,
                extension,
                subdirectory='Recordings'
            )

        filename = _generate_filename(final_format)

        # 保存文件
        try:
            # 创建临时文件
            temp_wav_name = f"{base_filename}.wav"
            temp_path = self.file_manager.get_temp_path(temp_wav_name)

            # 写入音频数据
            write_rate = self.sample_rate if self.sample_rate and self.sample_rate > 0 else 16000
            sf.write(temp_path, audio_data, write_rate)

            source_path = temp_path
            temp_mp3_path = None
            if final_format == 'mp3':
                temp_mp3_name = f"{base_filename}.mp3"
                temp_mp3_path = self.file_manager.get_temp_path(temp_mp3_name)
                try:
                    self._convert_wav_to_mp3(temp_path, temp_mp3_path)
                    source_path = temp_mp3_path
                except Exception as exc:  # noqa: BLE001
                    error_message = (
                        f"Failed to convert recording to MP3: {exc}. Saved as WAV instead."
                    )
                    logger.error(error_message)
                    if self.on_error:
                        self.on_error(error_message)
                    final_format = 'wav'
                    filename = _generate_filename(final_format)
                    source_path = temp_path
                    temp_mp3_path = None

            # 移动到最终位置
            with open(source_path, 'rb') as f:
                final_path = self.file_manager.save_file(
                    f.read(),
                    filename,
                    subdirectory='Recordings'
                )

            # 删除临时文件
            try:
                os.unlink(temp_path)
            except FileNotFoundError:
                logger.debug("Temporary WAV file already removed: %s", temp_path)
            if temp_mp3_path:
                try:
                    os.unlink(temp_mp3_path)
                except FileNotFoundError:
                    logger.debug(
                        "Temporary MP3 file already removed: %s", temp_mp3_path
                    )

            logger.info(f"Recording saved: {final_path}")
            return final_path

        except Exception as e:
            logger.error(f"Failed to save recording: {e}")
            if self.on_error:
                self.on_error(f"Failed to save recording: {e}")
            return ""

    def _is_mp3_conversion_available(self) -> bool:
        """MP3 转换工具是否可用。"""
        try:
            from utils.ffmpeg_checker import get_ffmpeg_checker
        except Exception:  # noqa: BLE001
            fallback_available = shutil.which('ffmpeg') is not None
            logger.debug(
                "FFmpeg checker unavailable; fallback detection result: %s",
                fallback_available
            )
            return fallback_available

        checker = get_ffmpeg_checker()
        available = checker.is_ffmpeg_available()
        logger.debug("MP3 conversion availability: %s", available)
        return available

    def _convert_wav_to_mp3(self, wav_path: str, mp3_path: str) -> None:
        """使用 FFmpeg 将 WAV 转换成 MP3。"""
        command = [
            'ffmpeg',
            '-y',
            '-i', wav_path,
            '-codec:a', 'libmp3lame',
            mp3_path
        ]
        logger.debug("Converting WAV to MP3 via command: %s", ' '.join(command))
        completed = subprocess.run(
            command,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        logger.debug(
            "FFmpeg conversion completed with return code %s", completed.returncode
        )

    async def _save_transcript(self) -> str:
        """
        保存转录文本

        Returns:
            str: 转录文本文件路径
        """
        if not self.accumulated_transcription:
            logger.warning("No transcription data to save")
            return ""

        # 合并所有转录文本
        full_transcript = "\n".join(self.accumulated_transcription)

        # 生成文件名
        timestamp = self.recording_start_time.strftime("%Y%m%d_%H%M%S")
        def _generate_filename(extension: str) -> str:
            return self.file_manager.create_unique_filename(
                f"transcript_{timestamp}",
                extension,
                subdirectory='Transcripts'
            )

        filename = _generate_filename('txt')

        # 保存文件
        try:
            final_path = self.file_manager.save_text_file(
                full_transcript,
                filename,
                subdirectory='Transcripts'
            )

            logger.info(f"Transcript saved: {final_path}")
            return final_path

        except Exception as e:
            logger.error(f"Failed to save transcript: {e}")
            if self.on_error:
                self.on_error(f"Failed to save transcript: {e}")
            return ""

    async def _save_translation(self) -> str:
        """
        保存翻译文本

        Returns:
            str: 翻译文本文件路径
        """
        if not self.accumulated_translation:
            logger.warning("No translation data to save")
            return ""

        # 合并所有翻译文本
        full_translation = "\n".join(self.accumulated_translation)

        # 生成文件名
        timestamp = self.recording_start_time.strftime("%Y%m%d_%H%M%S")
        target_lang = self.current_options.get('target_language', 'en')
        def _generate_filename(extension: str) -> str:
            return self.file_manager.create_unique_filename(
                f"translation_{target_lang}_{timestamp}",
                extension,
                subdirectory='Translations'
            )

        filename = _generate_filename('txt')

        # 保存文件
        try:
            final_path = self.file_manager.save_text_file(
                full_translation,
                filename,
                subdirectory='Translations'
            )

            logger.info(f"Translation saved: {final_path}")
            return final_path

        except Exception as e:
            logger.error(f"Failed to save translation: {e}")
            if self.on_error:
                self.on_error(f"Failed to save translation: {e}")
            return ""

    def _save_markers(self) -> str:
        """保存标记数据到文件"""
        if not self.markers or not self.recording_start_time:
            logger.debug("No markers to save")
            return ""

        payload = {
            'start_time': self.recording_start_time.isoformat(),
            'markers': [marker.copy() for marker in self.markers]
        }

        timestamp = self.recording_start_time.strftime("%Y%m%d_%H%M%S")
        def _generate_filename(extension: str) -> str:
            return self.file_manager.create_unique_filename(
                f"markers_{timestamp}",
                extension,
                subdirectory='Markers'
            )

        filename = _generate_filename('json')

        try:
            json_content = json.dumps(payload, ensure_ascii=False, indent=2)
            final_path = self.file_manager.save_text_file(
                json_content,
                filename,
                subdirectory='Markers'
            )
            logger.info(f"Markers saved: {final_path}")
            return final_path
        except Exception as e:  # noqa: BLE001
            logger.error(f"Failed to save markers: {e}")
            if self.on_error:
                self.on_error(f"Failed to save markers: {e}")
            return ""

    def add_marker(self, label: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """为当前录制添加标记。"""
        if not self.is_recording or not self.recording_start_time:
            logger.warning("Cannot add marker when recording is inactive")
            return None

        offset_seconds = self.get_recording_duration()
        absolute_time = self.recording_start_time + timedelta(seconds=offset_seconds)

        with self._marker_lock:
            marker = {
                'index': len(self.markers) + 1,
                'offset': offset_seconds,
                'absolute_time': absolute_time.isoformat(),
                'label': label or ""
            }
            self.markers.append(marker)

        logger.info(
            "Marker added at %.3f seconds (index %d)",
            offset_seconds,
            marker['index']
        )

        if self.on_marker_added:
            try:
                self.on_marker_added(marker.copy())
            except Exception as exc:  # noqa: BLE001
                logger.warning("Marker callback failed: %s", exc)

        return marker.copy()

    def get_markers(self) -> List[Dict[str, Any]]:
        """获取当前累积的标记列表。"""
        with self._marker_lock:
            return [marker.copy() for marker in self.markers]

    async def _create_calendar_event(self, recording_result: Dict) -> str:
        """
        创建日历事件

        Args:
            recording_result: 录制结果

        Returns:
            str: 事件 ID
        """
        if self.db is None:
            warning_message = self._translate(
                'realtime_record.calendar_event.db_missing',
                (
                    "Cannot create calendar event because no database connection is configured. "
                    "Configure the database to enable calendar integrations."
                ),
            )
            logger.warning(warning_message)
            if self.on_error:
                try:
                    self.on_error(warning_message)
                except Exception as callback_exc:  # noqa: BLE001
                    logger.error(
                        "Error invoking calendar warning callback: %s",
                        callback_exc,
                        exc_info=True
                    )
            return ""

        try:
            from data.database.models import CalendarEvent, EventAttachment

            # 创建事件
            start_reference = self.recording_start_time or datetime.now()
            title_time = start_reference.strftime('%Y-%m-%d %H:%M')
            duration_value = recording_result.get('duration', 0.0)
            try:
                duration_label = f"{float(duration_value):.2f}"
            except (TypeError, ValueError):
                duration_label = str(duration_value)

            event = CalendarEvent(
                title=self._translate(
                    'realtime_record.calendar_event.title',
                    '录音会话 - {timestamp}',
                    timestamp=title_time,
                ),
                event_type='Event',
                start_time=recording_result['start_time'],
                end_time=recording_result['end_time'],
                description=self._translate(
                    'realtime_record.calendar_event.description',
                    '录制时长: {duration} 秒',
                    duration=duration_label,
                ),
                source='local'
            )
            event.save(self.db)

            # 添加附件
            if 'recording_path' in recording_result:
                rec_path = recording_result['recording_path']
                if rec_path and os.path.exists(rec_path):
                    attachment = EventAttachment(
                        event_id=event.id,
                        attachment_type='recording',
                        file_path=rec_path,
                        file_size=os.path.getsize(rec_path)
                    )
                    attachment.save(self.db)

            if 'transcript_path' in recording_result:
                trans_path = recording_result['transcript_path']
                if trans_path and os.path.exists(trans_path):
                    attachment = EventAttachment(
                        event_id=event.id,
                        attachment_type='transcript',
                        file_path=trans_path,
                        file_size=os.path.getsize(trans_path)
                    )
                    attachment.save(self.db)

            # 添加翻译附件（如果有）
            if 'translation_path' in recording_result:
                translation_path = recording_result['translation_path']
                if translation_path and os.path.exists(translation_path):
                    attachment = EventAttachment(
                        event_id=event.id,
                        attachment_type='translation',
                        file_path=translation_path,
                        file_size=os.path.getsize(translation_path)
                    )
                    attachment.save(self.db)

            logger.info(f"Calendar event created: {event.id}")
            return event.id

        except Exception as e:
            error_message = self._translate(
                'realtime_record.calendar_event.creation_failed',
                'Failed to create calendar event: {error}',
                error=str(e)
            )
            logger.error(error_message)
            if self.on_error:
                self.on_error(error_message)
            return ""

    async def get_transcription_stream(self) -> AsyncIterator[str]:
        """
        获取实时转录文本流

        Yields:
            str: 转录文本片段

        Note:
            仍然推荐通过 set_callbacks 与 UI Signal 集成；
            该生成器主要面向需要纯异步接口的调用方。
        """
        queue = self._transcription_stream_queue
        if queue is None:
            return

        # 队列由 _process_audio_stream 异步生产文本片段
        while True:
            if not self.is_recording and queue.empty():
                break

            try:
                item = await asyncio.wait_for(
                    queue.get(),
                    timeout=0.2
                )
            except asyncio.TimeoutError:
                continue

            if item is None:
                break

            yield item

    async def get_translation_stream(self) -> AsyncIterator[str]:
        """
        获取实时翻译文本流

        Yields:
            str: 翻译文本片段

        Note:
            仍然推荐通过 set_callbacks 与 UI Signal 集成；
            该生成器面向需要纯异步接口的场景。
        """
        queue = self._translation_stream_queue
        if queue is None:
            return

        while True:
            if not self.is_recording and queue.empty():
                break

            try:
                item = await asyncio.wait_for(
                    queue.get(),
                    timeout=0.2
                )
            except asyncio.TimeoutError:
                continue

            if item is None:
                break

            yield item

    @staticmethod
    def _drain_queue(queue: Optional[asyncio.Queue]) -> None:
        """快速清空异步队列中的残留元素。"""
        if queue is None:
            return

        while not queue.empty():
            try:
                queue.get_nowait()
            except asyncio.QueueEmpty:
                break

    @staticmethod
    def _signal_stream_completion(queue: Optional[asyncio.Queue]) -> None:
        """在生成器队列尾部追加终止标记。"""
        if queue is None:
            return

        try:
            queue.put_nowait(None)
        except asyncio.QueueFull:  # pragma: no cover - 默认队列无限大
            logger.warning("Stream queue full when signaling completion")

    def get_recording_duration(self) -> float:
        """
        获取当前录制时长

        Returns:
            float: 录制时长（秒）
        """
        if not self.is_recording or not self.recording_start_time:
            return 0.0

        return (datetime.now() - self.recording_start_time).total_seconds()

    def get_recording_status(self) -> Dict:
        """
        获取录制状态

        Returns:
            Dict: 录制状态信息
        """
        start_time = None
        if self.recording_start_time:
            start_time = self.recording_start_time.isoformat()

        return {
            'is_recording': self.is_recording,
            'duration': self.get_recording_duration(),
            'start_time': start_time,
            'buffer_size': len(self.recording_audio_buffer),
            'transcription_queue_size': (
                self.transcription_queue.qsize()
                if self.transcription_queue is not None
                else 0
            ),
            'translation_queue_size': (
                self.translation_queue.qsize()
                if self.translation_queue is not None
                else 0
            ),
            'transcription_count': len(self.accumulated_transcription),
            'translation_count': len(self.accumulated_translation)
        }

    def get_accumulated_transcription(self) -> str:
        """
        获取累积的转录文本

        Returns:
            str: 完整的转录文本
        """
        return "\n".join(self.accumulated_transcription)

    def get_accumulated_translation(self) -> str:
        """
        获取累积的翻译文本

        Returns:
            str: 完整的翻译文本
        """
        return "\n".join(self.accumulated_translation)

    async def _rollback_failed_start(self) -> None:
        """在录音启动失败后回滚内部状态。"""
        if self.audio_capture is not None and hasattr(self.audio_capture, 'stop_capture'):
            try:
                self.audio_capture.stop_capture()
            except Exception as exc:  # noqa: BLE001
                logger.debug("Stop capture during rollback failed: %s", exc)

        tasks_to_await = []
        if self.processing_task:
            self.processing_task.cancel()
            tasks_to_await.append(self.processing_task)
            self.processing_task = None

        if self.translation_task:
            self.translation_task.cancel()
            tasks_to_await.append(self.translation_task)
            self.translation_task = None

        for task in tasks_to_await:
            with contextlib.suppress(asyncio.CancelledError):
                await task

        self.is_recording = False
        self.recording_start_time = None
        self.recording_audio_buffer = []

        if self.audio_buffer is not None:
            self.audio_buffer.clear()
            self.audio_buffer = None

        self.accumulated_transcription = []
        self.accumulated_translation = []

        with self._marker_lock:
            self.markers = []

        self._drain_queue(self.transcription_queue)
        self._drain_queue(self.translation_queue)
        self._drain_queue(self._transcription_stream_queue)
        self._drain_queue(self._translation_stream_queue)

        self._release_session_queues()
    
    def _is_duplicate_transcription(self, new_text: str, last_text: str) -> bool:
        """
        检查新转录文本是否与上一次重复

        Args:
            new_text: 新的转录文本
            last_text: 上一次的转录文本

        Returns:
            bool: 是否重复
        """
        if not last_text:
            return False
        
        # 完全相同
        if new_text == last_text:
            return True
        
        # 计算相似度（使用简单的字符串包含检查）
        # 如果新文本完全包含在旧文本中，或旧文本完全包含在新文本中
        new_lower = new_text.lower().strip()
        last_lower = last_text.lower().strip()
        
        # 如果一个文本是另一个的子串，且长度差异不大，认为是重复
        if new_lower in last_lower or last_lower in new_lower:
            length_ratio = min(len(new_lower), len(last_lower)) / max(len(new_lower), len(last_lower))
            if length_ratio > 0.7:  # 70% 相似度阈值
                return True
        
        return False
