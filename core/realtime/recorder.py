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
"""Realtime recording manager.

This module implements the full workflow for capturing, transcribing, and
translating audio in real time.
"""

import asyncio
import contextlib
import logging
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, AsyncIterator, Callable, Dict, List, Optional

import numpy as np

from core.realtime.audio_buffer import AudioBuffer
from core.realtime.config import RealtimeConfig
from core.realtime.archiver import SessionArchiver
from core.realtime.integration import CalendarIntegration
from config.constants import RECORDING_FORMAT_WAV

logger = logging.getLogger(__name__)


class RealtimeRecorder:
    """Manage the end-to-end lifecycle of real-time recording sessions."""

    def __init__(
        self,
        audio_capture,
        speech_engine,
        translation_engine,
        db_connection,
        file_manager,
        i18n=None,
        config: Optional[RealtimeConfig] = None,
    ):
        """Initialize the real-time recorder.

        Args:
            audio_capture: ``AudioCapture`` instance used to acquire audio
                frames.
            speech_engine: ``SpeechEngine`` instance used for transcription.
            translation_engine: Optional ``TranslationEngine`` instance used
                for post-transcription translation.
            db_connection: Database connection used for calendar integration
                and persistence.
            file_manager: ``FileManager`` responsible for creating and saving
                artifacts.
            i18n: Optional internationalization helper that provides localized
                user-facing messages.
            config: Optional configuration object.
        """
        self.audio_capture = audio_capture
        self.speech_engine = speech_engine
        self.translation_engine = translation_engine
        self.db = db_connection
        # file_manager is used by session_archiver
        self.i18n = i18n
        
        if config:
            self.config = config
        else:
            # Load defaults from centralized configuration
            try:
                from config.app_config import ConfigManager
                config_manager = ConfigManager()
                realtime_settings = config_manager.get("realtime", {})
                self.config = RealtimeConfig.from_dict(realtime_settings)
            except Exception as e:
                logger.warning(f"Failed to load realtime config from ConfigManager: {e}")
                self.config = RealtimeConfig()

        if self.audio_capture is None:
            logger.warning(
                "Audio capture not available. Real-time recording features will remain disabled."
            )

        # Components
        self.session_archiver = SessionArchiver(file_manager)
        self.calendar_integration = CalendarIntegration(db_connection, i18n)

        # Default sample rate used for newly created sessions.
        self.sample_rate = self.config.sample_rate
        if self.audio_capture is not None:
            capture_rate = getattr(self.audio_capture, "sample_rate", None)
            if isinstance(capture_rate, (int, float)) and capture_rate > 0:
                self.sample_rate = int(capture_rate)

        # Recording state indicators.
        self.is_recording = False
        self.recording_start_time = None
        self.recording_audio_buffer = []
        self.audio_buffer: Optional[AudioBuffer] = None

        # Transcription and translation queues, re-created for every session.
        self.transcription_queue: Optional[asyncio.Queue] = None
        self.translation_queue: Optional[asyncio.Queue] = None

        # Queues that expose streaming text to external consumers.
        self._transcription_stream_queue: Optional[asyncio.Queue] = None
        self._translation_stream_queue: Optional[asyncio.Queue] = None

        # Asynchronous tasks that perform background processing.
        self.processing_task = None
        self.translation_task = None

        # Recording options captured at session start.
        self.current_options = {}
        self._transcription_enabled = True
        self._stream_recording_active = False

        # Callback functions that notify external observers.
        self.on_transcription_update = None
        self.on_translation_update = None
        self.on_error = None
        self.on_audio_data = None  # Audio data callback (e.g., visualization).
        self.on_marker_added = None

        # Accumulated transcription and translation text.
        self.accumulated_transcription = []
        self.accumulated_translation = []

        # Marker metadata recorded during the session.
        self.markers: List[Dict[str, Any]] = []
        self._marker_lock = threading.Lock()

        # Reference to the event loop for thread-safe queue operations.
        self._event_loop = None

        # Flags that track model usage reporting.
        self._transcription_succeeded = False
        self._model_usage_recorded = False

        logger.info("RealtimeRecorder initialized")

    def audio_input_available(self) -> bool:
        """Return ``True`` when microphone input is available."""
        return self.audio_capture is not None

    def set_callbacks(
        self,
        on_transcription: Optional[Callable[[str], None]] = None,
        on_translation: Optional[Callable[[str], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
        on_audio_data: Optional[Callable[[np.ndarray], None]] = None,
        on_marker: Optional[Callable[[Dict[str, Any]], None]] = None,
    ):
        """Register callback hooks used by the user interface."""
        self.on_transcription_update = on_transcription
        self.on_translation_update = on_translation
        self.on_error = on_error
        self.on_audio_data = on_audio_data
        self.on_marker_added = on_marker

    def _initialize_session_queues(self) -> None:
        """Create fresh asyncio queues bound to the active event loop."""
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
        """Drop references to queues so the next session can rebuild them."""
        self.transcription_queue = None
        self.translation_queue = None
        self._transcription_stream_queue = None
        self._translation_stream_queue = None
        self._event_loop = None

    async def start_recording(
        self,
        input_source: Optional[int] = None,
        options: Optional[Dict] = None,
        event_loop=None,
    ):
        """Start a new real-time recording session."""
        if self.is_recording:
            logger.warning("Recording is already in progress")
            return

        if self.audio_capture is None:
            raise RuntimeError(
                "Audio capture is not available. Install PyAudio to enable real-time recording."
            )

        # Store the loop reference so that thread-safe queue operations work.
        if event_loop is not None:
            self._event_loop = event_loop
        else:
            self._event_loop = asyncio.get_event_loop()

        # Capture the supplied options.
        self.current_options = dict(options or {})
        self.current_options["enable_transcription"] = bool(
            self.current_options.get("enable_transcription", True)
        )
        if (
            self.current_options.get("enable_translation", False)
            and not self.current_options["enable_transcription"]
        ):
            logger.warning("Translation requires transcription; disabling translation for this session")
            self.current_options["enable_translation"] = False
        self._transcription_enabled = self.current_options["enable_transcription"]
        self._apply_session_model_selection()

        # Validate model availability after applying per-session model override.
        engine = self._resolve_speech_engine()
        if hasattr(engine, "is_model_available") and not engine.is_model_available():
            error_msg = (
                "Speech recognition model is not available. "
                "Please download a model from Settings > Model Management before recording."
            )
            logger.error(error_msg)
            raise RuntimeError(error_msg)

        # Synchronize the sample rate
        option_rate = self.current_options.get("sample_rate")
        if isinstance(option_rate, (int, float)) and option_rate > 0:
            self.sample_rate = int(option_rate)
        elif self.audio_capture is not None:
            capture_rate = getattr(self.audio_capture, "sample_rate", None)
            if isinstance(capture_rate, (int, float)) and capture_rate > 0:
                self.sample_rate = int(capture_rate)
        else:
            self.sample_rate = self.config.sample_rate

        if self.audio_capture is not None and hasattr(self.audio_capture, "sample_rate"):
            try:
                self.audio_capture.sample_rate = self.sample_rate
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"Failed to apply sample rate to audio capture: {exc}")

        # Rebuild queues for this session to ensure loop affinity.
        self._initialize_session_queues()

        # Reset per-session state.
        self.is_recording = True
        self.recording_start_time = datetime.now()
        self.recording_audio_buffer = []
        self.audio_buffer = AudioBuffer(sample_rate=self.sample_rate)
        self.accumulated_transcription = []
        self.accumulated_translation = []
        self._transcription_succeeded = False
        self._model_usage_recorded = False
        self._stream_recording_active = False
        with self._marker_lock:
            self.markers = []

        try:
            # Start recording stream persistence when enabled.
            if self.current_options.get("save_recording", True):
                starter = getattr(self.session_archiver, "start_recording_capture", None)
                if callable(starter):
                    started = starter(self.recording_start_time, self.sample_rate)
                    self._stream_recording_active = started if isinstance(started, bool) else False

            # Start audio acquisition.
            self.audio_capture.start_capture(
                device_index=input_source, callback=self._audio_callback
            )

            # Launch asynchronous processing tasks.
            if self._transcription_enabled:
                self.processing_task = asyncio.create_task(self._process_audio_stream())
            else:
                self.processing_task = None

            # Launch translation worker when enabled.
            if self.current_options.get("enable_translation", False) and self._transcription_enabled:
                self.translation_task = asyncio.create_task(self._process_translation_stream())
        except Exception as exc:
            logger.error("Failed to start real-time recording: %s", exc, exc_info=True)
            await self._rollback_failed_start()

            message = f"Failed to start recording: {exc}"
            if self.on_error:
                try:
                    self.on_error(message)
                except Exception as callback_exc:  # noqa: BLE001
                    logger.error(
                        "Error invoking start failure callback: %s", callback_exc, exc_info=True
                    )

            raise

        logger.info(f"Recording started (input_source={input_source})")

    def _audio_callback(self, audio_chunk: np.ndarray):
        """Receive audio buffers from the capture thread."""
        if not self.is_recording:
            return

        # Stash audio data so the full session can be persisted.
        if self.current_options.get("save_recording", True):
            if self._stream_recording_active:
                append_chunk = getattr(self.session_archiver, "append_recording_chunk", None)
                if callable(append_chunk) and append_chunk(audio_chunk.copy()):
                    pass
                else:
                    logger.warning(
                        "Streaming recording persistence failed; falling back to in-memory buffering"
                    )
                    preserved_prefix = False
                    failover = getattr(self.session_archiver, "failover_recording_capture", None)
                    if callable(failover):
                        try:
                            preserved_prefix = bool(failover())
                        except Exception as exc:  # noqa: BLE001
                            logger.warning("Streaming failover unavailable: %s", exc)

                    if not preserved_prefix:
                        aborter = getattr(self.session_archiver, "abort_recording_capture", None)
                        if callable(aborter):
                            aborter()
                    self._stream_recording_active = False
                    self.recording_audio_buffer.append(audio_chunk.copy())
            else:
                self.recording_audio_buffer.append(audio_chunk.copy())

        # Push audio into the transcription queue in a thread-safe manner.
        try:
            # ``call_soon_threadsafe`` safely schedules the queue operation.
            if (
                self._transcription_enabled
                and hasattr(self, "_event_loop")
                and self._event_loop is not None
                and self.transcription_queue is not None
            ):
                self._event_loop.call_soon_threadsafe(
                    self.transcription_queue.put_nowait, audio_chunk.copy()
                )
            elif self._transcription_enabled:
                logger.debug("Event loop or transcription queue not ready, audio chunk skipped")
        except Exception as e:
            logger.warning(f"Failed to queue audio chunk: {e}")

        # Notify observers that fresh audio data is available.
        if self.on_audio_data:
            try:
                self.on_audio_data(audio_chunk.copy())
            except Exception as e:
                logger.warning(f"Error in audio data callback: {e}")

    async def _process_audio_stream(self):
        """Background coroutine that ingests and transcribes audio buffers."""
        logger.info("Audio stream processing started")

        # Import the VAD detector lazily to avoid optional dependency churn.
        from engines.audio.vad import VADDetector

        queue = self.transcription_queue
        stream_queue = self._transcription_stream_queue
        if queue is None or stream_queue is None:
            logger.error(
                "Transcription queues are not initialized; aborting audio stream processing"
            )
            return

        # VAD Configuration
        vad = None
        vad_threshold = self.current_options.get(
            "vad_threshold", self.config.vad_threshold
        )
        silence_duration_ms = self.current_options.get(
            "silence_duration_ms", self.config.silence_duration_ms
        )
        min_audio_duration = self.current_options.get(
            "min_audio_duration", self.config.min_audio_duration
        )

        try:
            vad = VADDetector(
                threshold=float(vad_threshold),
                silence_duration_ms=int(silence_duration_ms),
                method="silero",
            )
            logger.info("VAD detector initialized successfully")
        except Exception as e:
            logger.warning(f"Failed to initialize VAD: {e}. Will process all audio without VAD.")

        sample_rate = self.sample_rate if self.sample_rate and self.sample_rate > 0 else 16000

        audio_buffer = self.audio_buffer
        if audio_buffer is None:
            audio_buffer = AudioBuffer(sample_rate=sample_rate)
            self.audio_buffer = audio_buffer

        audio_chunks_received = 0
        transcription_attempts = 0
        last_transcription = ""  # Track the previous transcription to avoid duplicates.
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
                " (forced)" if force else "",
            )

            window_audio = audio_buffer.get_latest(pending_duration)
            if len(window_audio) == 0:
                audio_buffer.clear()
                return

            speech_audio = window_audio
            if vad is not None:
                try:
                    speech_timestamps = vad.detect_speech(window_audio, sample_rate)
                    
                    if speech_timestamps:
                        speech_audio = vad.extract_speech(
                            window_audio, speech_timestamps, sample_rate=sample_rate
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
                logger.debug(f"Transcription attempt #{transcription_attempts}")

                language = self.current_options.get("language")
                text = await self.speech_engine.transcribe_stream(
                    speech_audio, language=language, sample_rate=self.sample_rate
                )

                if text.strip():
                    if self._is_duplicate_transcription(text, last_transcription):
                        logger.debug(f"Duplicate transcription detected, skipping: {text[:50]}...")
                    else:
                        self.accumulated_transcription.append(text)
                        self._transcription_succeeded = True
                        await stream_queue.put(text)

                        if self.on_transcription_update:
                            try:
                                self.on_transcription_update(text)
                            except Exception as e:
                                logger.error(f"Error in transcription callback: {e}")

                        enable_trans = self.current_options.get("enable_translation", False)
                        if enable_trans and translation_queue is not None:
                            await translation_queue.put(text)

                        logger.info(f"Transcribed successfully: {text[:50]}...")
                        last_transcription = text
            except Exception as e:
                logger.error(f"Transcription failed: {e}", exc_info=True)
                if self.on_error:
                    self.on_error(f"Transcription error: {e}")
            finally:
                audio_buffer.clear()

        try:
            while self.is_recording or not queue.empty():
                try:
                    audio_chunk = await asyncio.wait_for(queue.get(), timeout=0.5)
                except asyncio.TimeoutError:
                    if not self.is_recording:
                        break
                    continue

                audio_chunks_received += 1
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
                transcription_attempts,
            )

    async def _process_translation_stream(self):
        """Background coroutine that consumes transcription results and translates them."""
        logger.info("Translation stream processing started")

        # Ensure that a translation engine is configured.
        if not self.translation_engine:
            logger.warning("Translation engine not available")
            if self.on_error:
                self.on_error("Translation not available: No API key configured")
            return

        queue = self.translation_queue
        stream_queue = self._translation_stream_queue
        if queue is None or stream_queue is None:
            logger.error(
                "Translation queues are not initialized; aborting translation stream processing"
            )
            return

        try:
            while self.is_recording or not queue.empty():
                try:
                    # Pull transcription output with a short timeout.
                    text = await asyncio.wait_for(queue.get(), timeout=0.5)

                    if text is None:
                        logger.debug("Received translation shutdown signal")
                        break

                    # Perform translation.
                    source_lang = self.current_options.get("language", "auto")
                    target_lang = self.current_options.get("target_language", "en")

                    translated_text = await self.translation_engine.translate(
                        text, source_lang=source_lang, target_lang=target_lang
                    )

                    if translated_text.strip():
                        # Store translated text for persistence.
                        self.accumulated_translation.append(translated_text)

                        # Push the translation into the streaming queue.
                        await stream_queue.put(translated_text)

                        # Notify observers that translation text is available.
                        if self.on_translation_update:
                            self.on_translation_update(translated_text)

                        logger.debug(f"Translated: {translated_text}")

                except asyncio.TimeoutError:
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
        """Stop the active recording session and persist its artifacts."""
        if not self.is_recording:
            logger.warning("Recording is not in progress")
            return {}

        logger.info("Stopping recording...")

        # Signal the session to stop.
        self.is_recording = False

        # Stop audio capture immediately.
        if self.audio_capture is not None:
            self.audio_capture.stop_capture()

        # Wait for background processing to drain.
        if self.processing_task:
            try:
                await asyncio.wait_for(self.processing_task, timeout=5.0)
            except asyncio.TimeoutError:
                logger.warning("Processing task timeout")
                self.processing_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await self.processing_task
            finally:
                self.processing_task = None

        if self.translation_task:
            await self._ensure_translation_task_stopped()

        # Signal streaming queues so generators exit gracefully.
        transcription_stream_queue = self._transcription_stream_queue
        translation_stream_queue = self._translation_stream_queue
        self._signal_stream_completion(transcription_stream_queue)
        self._signal_stream_completion(translation_stream_queue)

        # Compute session duration.
        recording_end_time = datetime.now()
        duration = (recording_end_time - self.recording_start_time).total_seconds()

        if self.audio_buffer is not None:
            self.audio_buffer.clear()
            self.audio_buffer = None

        result = {
            "duration": duration,
            "start_time": self.recording_start_time.isoformat(),
            "end_time": recording_end_time.isoformat(),
        }

        # Persist audio when requested.
        if self.current_options.get("save_recording", True):
            recording_format = self.current_options.get("recording_format", RECORDING_FORMAT_WAV)
            recording_path = ""

            if self._stream_recording_active:
                finisher = getattr(self.session_archiver, "finish_recording_capture", None)
                if callable(finisher):
                    recording_path = await finisher(format=recording_format)
                self._stream_recording_active = False

            if not recording_path:
                recording_path = await self.session_archiver.save_recording(
                    self.recording_audio_buffer,
                    self.recording_start_time,
                    self.sample_rate,
                    format=recording_format,
                )

            result["recording_path"] = recording_path
        elif self._stream_recording_active:
            aborter = getattr(self.session_archiver, "abort_recording_capture", None)
            if callable(aborter):
                aborter()
            self._stream_recording_active = False

        # Persist transcription when requested.
        if self._transcription_enabled and self.current_options.get("save_transcript", True):
            transcript_path = await self.session_archiver.save_text(
                self.accumulated_transcription,
                self.recording_start_time,
                prefix="transcript",
                subdirectory="Transcripts",
            )
            result["transcript_path"] = transcript_path

        # Persist translation output when requested.
        if self._transcription_enabled and self.current_options.get("enable_translation", False):
            target_lang = self.current_options.get("target_language", "en")
            translation_path = await self.session_archiver.save_text(
                self.accumulated_translation,
                self.recording_start_time,
                prefix=f"translation_{target_lang}",
                subdirectory="Translations",
            )
            result["translation_path"] = translation_path

        # Persist markers.
        with self._marker_lock:
            if self.markers:
                result["markers"] = [marker.copy() for marker in self.markers]
                markers_path = await self.session_archiver.save_markers(
                    self.markers, self.recording_start_time
                )
                result["markers_path"] = markers_path

        # Create a calendar event when requested.
        create_event_requested = self.current_options.get("create_calendar_event", True)
        if create_event_requested:
            event_id = await self.calendar_integration.create_event(result)
            result["event_id"] = event_id

        self._record_model_usage_if_needed()

        logger.info(f"Recording stopped: duration={duration:.2f}s")

        # Ensure no dangling temporary streaming resources remain.
        aborter = getattr(self.session_archiver, "abort_recording_capture", None)
        if callable(aborter):
            aborter()

        # Release queue references after the session completes.
        self._release_session_queues()
        self.recording_audio_buffer = []

        return result

    def _record_model_usage_if_needed(self) -> None:
        """Record model usage metrics when the session produced transcription."""
        if self._model_usage_recorded or not self._transcription_succeeded:
            return

        engine = self._resolve_speech_engine()
        manager = getattr(engine, "model_manager", None)
        model_name = getattr(engine, "model_size", None)

        if not manager or not model_name:
            return

        try:
            manager.mark_model_used(model_name)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Failed to record model usage for real-time session (model=%s): %s",
                model_name,
                exc,
                exc_info=True,
            )
        else:
            self._model_usage_recorded = True

    def _resolve_speech_engine(self):
        """Return the concrete speech engine behind optional lazy proxies."""
        engine = self.speech_engine
        loader = getattr(engine, "_loader", None)
        if loader is not None and hasattr(loader, "get"):
            try:
                resolved_engine = loader.get()
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to resolve speech engine from lazy loader: %s", exc)
            else:
                if resolved_engine is not None:
                    return resolved_engine
        return engine

    def reload_engine(self) -> bool:
        """Reload lazy-loaded engines when credentials or settings change."""
        if self.is_recording:
            logger.warning("Skipping engine reload while recording is active")
            return False

        reloaded = False
        for engine in (self.speech_engine, self.translation_engine):
            loader = getattr(engine, "_loader", None)
            if loader is None:
                continue

            try:
                if hasattr(loader, "reload") and callable(loader.reload):
                    loader.reload()
                else:
                    loader._instance = None
                    loader._initialized = False
                    loader.get()
            except Exception as exc:  # noqa: BLE001
                logger.error("Failed to reload realtime engine: %s", exc, exc_info=True)
                raise
            else:
                reloaded = True

        return reloaded

    def _apply_session_model_selection(self) -> None:
        """Apply per-session model selection options when supported by the engine."""
        selected_model = self.current_options.get("model_name")
        if not selected_model:
            return

        engine = self._resolve_speech_engine()
        model_path = self.current_options.get("model_path")

        if hasattr(engine, "_apply_runtime_model_selection"):
            try:
                engine._apply_runtime_model_selection(selected_model, model_path)
            except Exception as exc:  # noqa: BLE001
                raise RuntimeError(f"Failed to activate selected model '{selected_model}': {exc}") from exc
            logger.info("Activated session model: %s", selected_model)
            return

        if not hasattr(engine, "model_size"):
            logger.debug("Current speech engine does not support per-session model selection")
            return

        current_model = getattr(engine, "model_size", None)
        if current_model == selected_model:
            return

        manager = getattr(engine, "model_manager", None)
        if manager is not None and hasattr(manager, "get_model"):
            try:
                model_info = manager.get_model(selected_model)
            except Exception as exc:  # noqa: BLE001
                raise RuntimeError(f"Failed to resolve selected model '{selected_model}': {exc}") from exc
            if not model_info or not getattr(model_info, "is_downloaded", False):
                raise RuntimeError(
                    f"Selected model '{selected_model}' is not downloaded. "
                    "Please download it from Settings > Model Management."
                )

        if model_path and hasattr(engine, "download_root"):
            try:
                engine.download_root = str(Path(model_path).expanduser().parent)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to apply model path '%s': %s", model_path, exc)

        try:
            engine.model_size = selected_model
            if hasattr(engine, "model"):
                engine.model = None
            if hasattr(engine, "_refresh_model_status"):
                engine._refresh_model_status()
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"Failed to activate selected model '{selected_model}': {exc}") from exc

        logger.info("Activated session model: %s", selected_model)

    async def _ensure_translation_task_stopped(self) -> None:
        """Wait for the translation coroutine to exit before finishing."""
        task = self.translation_task
        if task is None:
            return

        try:
            await asyncio.wait_for(task, timeout=self.config.translation_task_timeout)
        except asyncio.TimeoutError:
            logger.warning("Translation task timeout; requesting graceful shutdown")
            await self._request_translation_shutdown(task)
        finally:
            self.translation_task = None

    async def _request_translation_shutdown(self, task: asyncio.Task) -> None:
        """Send a shutdown signal to the translation coroutine and await exit."""
        queue = self.translation_queue
        stream_queue = self._translation_stream_queue

        if queue is not None:
            try:
                queue.put_nowait(None)
            except asyncio.QueueFull:  # pragma: no cover
                logger.warning("Translation queue full when sending shutdown signal")

        if stream_queue is not None:
            self._signal_stream_completion(stream_queue)

        try:
            await asyncio.wait_for(task, timeout=self.config.translation_task_shutdown_timeout)
        except asyncio.TimeoutError:
            logger.error("Translation task did not stop after shutdown request; cancelling")
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        finally:
            self._drain_queue(queue)
            self._drain_queue(stream_queue)

    def add_marker(self, label: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Create a marker at the current session position."""
        if not self.is_recording or not self.recording_start_time:
            logger.warning("Cannot add marker when recording is inactive")
            return None

        offset_seconds = self.get_recording_duration()
        absolute_time = self.recording_start_time + timedelta(seconds=offset_seconds)

        with self._marker_lock:
            marker = {
                "index": len(self.markers) + 1,
                "offset": offset_seconds,
                "absolute_time": absolute_time.isoformat(),
                "label": label or "",
            }
            self.markers.append(marker)

        logger.info("Marker added at %.3f seconds (index %d)", offset_seconds, marker["index"])

        if self.on_marker_added:
            try:
                self.on_marker_added(marker.copy())
            except Exception as exc:  # noqa: BLE001
                logger.warning("Marker callback failed: %s", exc)

        return marker.copy()

    def get_markers(self) -> List[Dict[str, Any]]:
        """Return a copy of all markers captured in the session."""
        with self._marker_lock:
            return [marker.copy() for marker in self.markers]

    def clear_markers(self) -> None:
        """Clear all markers captured in the current session."""
        with self._marker_lock:
            self.markers = []

    async def get_transcription_stream(self) -> AsyncIterator[str]:
        """Yield transcription snippets as they become available."""
        queue = self._transcription_stream_queue
        if queue is None:
            return

        while True:
            if not self.is_recording and queue.empty():
                break

            try:
                item = await asyncio.wait_for(queue.get(), timeout=0.2)
            except asyncio.TimeoutError:
                continue

            if item is None:
                break

            yield item

    async def get_translation_stream(self) -> AsyncIterator[str]:
        """Yield translation snippets as they become available."""
        queue = self._translation_stream_queue
        if queue is None:
            return

        while True:
            if not self.is_recording and queue.empty():
                break

            try:
                item = await asyncio.wait_for(queue.get(), timeout=0.2)
            except asyncio.TimeoutError:
                continue

            if item is None:
                break

            yield item

    @staticmethod
    def _drain_queue(queue: Optional[asyncio.Queue]) -> None:
        """Remove pending items from the queue without awaiting."""
        if queue is None:
            return

        while not queue.empty():
            try:
                queue.get_nowait()
            except asyncio.QueueEmpty:
                break

    @staticmethod
    def _signal_stream_completion(queue: Optional[asyncio.Queue]) -> None:
        """Append a sentinel value to indicate stream completion."""
        if queue is None:
            return

        try:
            queue.put_nowait(None)
        except asyncio.QueueFull:  # pragma: no cover
            logger.warning("Stream queue full when signaling completion")

    def get_recording_duration(self) -> float:
        """Return the elapsed recording duration in seconds."""
        if not self.is_recording or not self.recording_start_time:
            return 0.0

        return (datetime.now() - self.recording_start_time).total_seconds()

    def get_recording_status(self) -> Dict:
        """Return a snapshot of the current recording status."""
        start_time = None
        if self.recording_start_time:
            start_time = self.recording_start_time.isoformat()

        return {
            "is_recording": self.is_recording,
            "duration": self.get_recording_duration(),
            "start_time": start_time,
            "buffer_size": len(self.recording_audio_buffer),
            "transcription_queue_size": (
                self.transcription_queue.qsize() if self.transcription_queue is not None else 0
            ),
            "translation_queue_size": (
                self.translation_queue.qsize() if self.translation_queue is not None else 0
            ),
            "transcription_count": len(self.accumulated_transcription),
            "translation_count": len(self.accumulated_translation),
        }

    def get_accumulated_transcription(self) -> str:
        """Return all accumulated transcription text as a single string."""
        return "\n".join(self.accumulated_transcription)

    def get_accumulated_translation(self) -> str:
        """Return all accumulated translation text as a single string."""
        return "\n".join(self.accumulated_translation)

    async def _rollback_failed_start(self) -> None:
        """Reset internal state after a failed recording startup."""
        if self.audio_capture is not None and hasattr(self.audio_capture, "stop_capture"):
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
        self._stream_recording_active = False

        with self._marker_lock:
            self.markers = []

        aborter = getattr(self.session_archiver, "abort_recording_capture", None)
        if callable(aborter):
            aborter()

        self._drain_queue(self.transcription_queue)
        self._drain_queue(self.translation_queue)
        self._drain_queue(self._transcription_stream_queue)
        self._drain_queue(self._translation_stream_queue)

        self._release_session_queues()

    def _is_duplicate_transcription(self, new_text: str, last_text: str) -> bool:
        """Return ``True`` when the new transcript duplicates the last output."""
        if not last_text:
            return False

        if new_text == last_text:
            return True

        new_lower = new_text.lower().strip()
        last_lower = last_text.lower().strip()

        if new_lower in last_lower or last_lower in new_lower:
            length_ratio = min(len(new_lower), len(last_lower)) / max(
                len(new_lower), len(last_lower)
            )
            if length_ratio > 0.7:  # 70% similarity threshold.
                return True

        return False
