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
    """Manage the end-to-end lifecycle of real-time recording sessions."""

    TRANSLATION_TASK_TIMEOUT = 5.0
    TRANSLATION_TASK_SHUTDOWN_TIMEOUT = 2.0

    def __init__(
        self,
        audio_capture,
        speech_engine,
        translation_engine,
        db_connection,
        file_manager,
        i18n=None,
    ):
        """Initialize the real-time recorder.

        Args:
            audio_capture: ``AudioCapture`` instance used to acquire audio
                frames. May be ``None`` when audio input is unavailable.
            speech_engine: ``SpeechEngine`` instance used for transcription.
            translation_engine: Optional ``TranslationEngine`` instance used
                for post-transcription translation.
            db_connection: Database connection used for calendar integration
                and persistence.
            file_manager: ``FileManager`` responsible for creating and saving
                artifacts.
            i18n: Optional internationalization helper that provides localized
                user-facing messages.
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

        # Default sample rate used for newly created sessions.
        self.sample_rate = 16000
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
        """Register callback hooks used by the user interface.

        Args:
            on_transcription: Invoked when new transcription text is available.
            on_translation: Invoked when new translated text is available.
            on_error: Invoked when a recoverable error occurs.
            on_audio_data: Receives audio frames for visualization or metering.
            on_marker: Invoked when a marker is created during the session.
        """
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
        self, input_source: Optional[int] = None, options: Optional[Dict] = None, event_loop=None
    ):
        """Start a new real-time recording session.

        Args:
            input_source: Index of the audio input device. ``None`` selects the
                system default input.
            options: Optional configuration dictionary. Recognized keys
                include ``language`` (source language code),
                ``enable_translation`` (``bool`` flag), ``target_language``
                (translation target code), ``recording_format`` (``"wav"`` or
                ``"mp3"``), ``save_recording`` and ``save_transcript``
                (``bool`` flags), and ``create_calendar_event`` (``bool`` flag).
                Additional engine-specific options are passed through.
            event_loop: Optional event loop reference. When provided, the
                recorder binds its queues and callbacks to this loop.
        """
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
        self.current_options = options or {}

        # Synchronize the sample rate, preferring explicit options over
        # capture defaults.
        option_rate = self.current_options.get("sample_rate")
        if isinstance(option_rate, (int, float)) and option_rate > 0:
            self.sample_rate = int(option_rate)
        elif self.audio_capture is not None:
            capture_rate = getattr(self.audio_capture, "sample_rate", None)
            if isinstance(capture_rate, (int, float)) and capture_rate > 0:
                self.sample_rate = int(capture_rate)
        else:
            self.sample_rate = 16000

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
        with self._marker_lock:
            self.markers = []

        try:
            # Start audio acquisition.
            self.audio_capture.start_capture(
                device_index=input_source, callback=self._audio_callback
            )

            # Launch asynchronous processing tasks.
            self.processing_task = asyncio.create_task(self._process_audio_stream())

            # Launch translation worker when enabled.
            if self.current_options.get("enable_translation", False):
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
        """Receive audio buffers from the capture thread.

        Args:
            audio_chunk: ``numpy`` array containing a single audio frame.
        """
        if not self.is_recording:
            return

        # Stash audio data so the full session can be persisted.
        self.recording_audio_buffer.append(audio_chunk.copy())

        # Push audio into the transcription queue in a thread-safe manner.
        try:
            # ``call_soon_threadsafe`` safely schedules the queue operation.
            if (
                hasattr(self, "_event_loop")
                and self._event_loop is not None
                and self.transcription_queue is not None
            ):
                self._event_loop.call_soon_threadsafe(
                    self.transcription_queue.put_nowait, audio_chunk.copy()
                )
            else:
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

        # Create the VAD detector and the rolling audio buffer.
        vad = None
        try:
            vad = VADDetector(
                threshold=0.3,  # Lower threshold makes speech detection easier.
                silence_duration_ms=1500,  # Reduce silence requirement.
                method="silero",
            )
            logger.info("VAD detector initialized successfully")
        except Exception as e:
            logger.warning(f"Failed to initialize VAD: {e}. Will process all audio without VAD.")
            # Continue without VAD when initialization fails.

        sample_rate = self.sample_rate if self.sample_rate and self.sample_rate > 0 else 16000

        audio_buffer = self.audio_buffer
        if audio_buffer is None:
            audio_buffer = AudioBuffer(sample_rate=sample_rate)
            self.audio_buffer = audio_buffer

        min_audio_duration = 3.0  # Require at least three seconds before running inference.

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

            logger.debug(f"Window audio size: {len(window_audio)} samples")

            speech_audio = window_audio
            if vad is not None:
                try:
                    speech_timestamps = vad.detect_speech(window_audio, sample_rate)
                    logger.debug(f"VAD detected {len(speech_timestamps)} speech segments")

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
                logger.info(f"Transcription attempt #{transcription_attempts}")

                language = self.current_options.get("language")
                text = await self.speech_engine.transcribe_stream(
                    speech_audio, language=language, sample_rate=self.sample_rate
                )

                logger.info(f"Transcription result: '{text}'")

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
                                logger.debug("UI callback invoked successfully")
                            except Exception as e:
                                logger.error(f"Error in transcription callback: {e}")

                        enable_trans = self.current_options.get("enable_translation", False)
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
                    audio_chunk = await asyncio.wait_for(queue.get(), timeout=0.5)
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

                    # The translation engine was already validated above.
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
                    # Timeout: continue waiting for more data.
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
        """Stop the active recording session and persist its artifacts.

        Returns:
            Dict: Result payload with at least the following keys:
                - ``duration`` (float): Session duration in seconds.
                - ``start_time`` (str): ISO 8601 timestamp for session start.
                - ``end_time`` (str): ISO 8601 timestamp for session end.

            Optional keys are included when applicable:
                - ``recording_path`` (str): Location of the saved audio file
                  when ``save_recording`` is enabled and audio is available.
                - ``transcript_path`` (str): Location of the saved transcript
                  when ``save_transcript`` is enabled and text is available.
                - ``translation_path`` (str): Location of the saved translation
                  when translation is enabled and output is available.
                - ``markers`` (List[Dict]): Marker metadata captured during the
                  session.
                - ``markers_path`` (str): Location of the exported marker JSON
                  file when markers exist.
                - ``event_id`` (str): Identifier of the calendar event when one
                  is created successfully.
        """
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
            recording_path = await self._save_recording()
            result["recording_path"] = recording_path

        # Persist transcription when requested.
        if self.current_options.get("save_transcript", True):
            transcript_path = await self._save_transcript()
            result["transcript_path"] = transcript_path

        # Persist translation output when requested.
        if self.current_options.get("enable_translation", False):
            translation_path = await self._save_translation()
            if translation_path:
                result["translation_path"] = translation_path

        with self._marker_lock:
            if self.markers:
                result["markers"] = [marker.copy() for marker in self.markers]
                markers_path = self._save_markers()
                if markers_path:
                    result["markers_path"] = markers_path

        # Create a calendar event when requested.
        create_event_requested = self.current_options.get("create_calendar_event", True)
        if create_event_requested and self.db is None:
            logger.info("Skipping calendar event creation: database connection is not configured.")
            create_event_requested = False

        if create_event_requested:
            event_id = await self._create_calendar_event(result)
            result["event_id"] = event_id

        self._record_model_usage_if_needed()

        logger.info(f"Recording stopped: duration={duration:.2f}s")

        # Release queue references after the session completes.
        self._release_session_queues()

        return result

    def _record_model_usage_if_needed(self) -> None:
        """Record model usage metrics when the session produced transcription."""
        if self._model_usage_recorded or not self._transcription_succeeded:
            return

        manager = getattr(self.speech_engine, "model_manager", None)
        model_name = getattr(self.speech_engine, "model_size", None)

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

    async def _ensure_translation_task_stopped(self) -> None:
        """Wait for the translation coroutine to exit before finishing."""
        task = self.translation_task
        if task is None:
            return

        try:
            await asyncio.wait_for(task, timeout=self.TRANSLATION_TASK_TIMEOUT)
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
            except asyncio.QueueFull:  # pragma: no cover - queue is unbounded by default
                logger.warning("Translation queue full when sending shutdown signal")

        if stream_queue is not None:
            self._signal_stream_completion(stream_queue)

        try:
            await asyncio.wait_for(task, timeout=self.TRANSLATION_TASK_SHUTDOWN_TIMEOUT)
        except asyncio.TimeoutError:
            logger.error("Translation task did not stop after shutdown request; cancelling")
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        finally:
            self._drain_queue(queue)
            self._drain_queue(stream_queue)

    async def _save_recording(self) -> str:
        """Persist the captured audio to disk and return the file path."""
        if not self.recording_audio_buffer:
            logger.warning("No audio data to save")
            return ""

        # Merge all audio frames.
        audio_data = np.concatenate(self.recording_audio_buffer)

        # Build the target filename.
        timestamp = self.recording_start_time.strftime("%Y%m%d_%H%M%S")
        requested_format = str(self.current_options.get("recording_format", "wav")).lower()
        base_filename = f"recording_{timestamp}"
        mp3_requested = requested_format == "mp3"
        mp3_supported = False
        if mp3_requested:
            try:
                mp3_supported = self._is_mp3_conversion_available()
            except Exception as exc:  # noqa: BLE001
                logger.error("Failed to determine MP3 conversion capability: %s", exc)
                mp3_supported = False

            if not mp3_supported:
                warning_message = "MP3 recording requires FFmpeg. Saved recording as WAV instead."
                logger.warning(warning_message)
                if self.on_error:
                    self.on_error(warning_message)

        final_format = "mp3" if mp3_requested and mp3_supported else "wav"

        def _generate_filename(extension: str) -> str:
            return self.file_manager.create_unique_filename(
                base_filename, extension, subdirectory="Recordings"
            )

        filename = _generate_filename(final_format)

        # Persist the file to the configured location.
        try:
            # Create a temporary WAV file on disk.
            temp_wav_name = f"{base_filename}.wav"
            temp_path = self.file_manager.get_temp_path(temp_wav_name)

            # Write the audio payload.
            write_rate = self.sample_rate if self.sample_rate and self.sample_rate > 0 else 16000
            sf.write(temp_path, audio_data, write_rate)

            source_path = temp_path
            temp_mp3_path = None
            if final_format == "mp3":
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
                    final_format = "wav"
                    filename = _generate_filename(final_format)
                    source_path = temp_path
                    temp_mp3_path = None

            # Move the finished file into place.
            with open(source_path, "rb") as f:
                final_path = self.file_manager.save_file(
                    f.read(), filename, subdirectory="Recordings"
                )

            # Remove the temporary artifact when finished.
            try:
                os.unlink(temp_path)
            except FileNotFoundError:
                logger.debug("Temporary WAV file already removed: %s", temp_path)
            if temp_mp3_path:
                try:
                    os.unlink(temp_mp3_path)
                except FileNotFoundError:
                    logger.debug("Temporary MP3 file already removed: %s", temp_mp3_path)

            logger.info(f"Recording saved: {final_path}")
            return final_path

        except Exception as e:
            logger.error(f"Failed to save recording: {e}")
            if self.on_error:
                self.on_error(f"Failed to save recording: {e}")
            return ""

    def _is_mp3_conversion_available(self) -> bool:
        """Return ``True`` when FFmpeg-based MP3 conversion is available."""
        try:
            from utils.ffmpeg_checker import get_ffmpeg_checker
        except Exception:  # noqa: BLE001
            fallback_available = shutil.which("ffmpeg") is not None
            logger.debug(
                "FFmpeg checker unavailable; fallback detection result: %s", fallback_available
            )
            return fallback_available

        checker = get_ffmpeg_checker()
        available = checker.is_ffmpeg_available()
        logger.debug("MP3 conversion availability: %s", available)
        return available

    def _convert_wav_to_mp3(self, wav_path: str, mp3_path: str) -> None:
        """Convert a WAV file to MP3 using FFmpeg."""
        command = ["ffmpeg", "-y", "-i", wav_path, "-codec:a", "libmp3lame", mp3_path]
        logger.debug("Converting WAV to MP3 via command: %s", " ".join(command))
        completed = subprocess.run(
            command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        logger.debug("FFmpeg conversion completed with return code %s", completed.returncode)

    async def _save_transcript(self) -> str:
        """Persist accumulated transcription text and return the file path."""
        if not self.accumulated_transcription:
            logger.warning("No transcription data to save")
            return ""

        # Combine all transcript fragments.
        full_transcript = "\n".join(self.accumulated_transcription)

        # Build the output filename.
        timestamp = self.recording_start_time.strftime("%Y%m%d_%H%M%S")

        def _generate_filename(extension: str) -> str:
            return self.file_manager.create_unique_filename(
                f"transcript_{timestamp}", extension, subdirectory="Transcripts"
            )

        filename = _generate_filename("txt")

        # Save the text to disk.
        try:
            final_path = self.file_manager.save_text_file(
                full_transcript, filename, subdirectory="Transcripts"
            )

            logger.info(f"Transcript saved: {final_path}")
            return final_path

        except Exception as e:
            logger.error(f"Failed to save transcript: {e}")
            if self.on_error:
                self.on_error(f"Failed to save transcript: {e}")
            return ""

    async def _save_translation(self) -> str:
        """Persist accumulated translation text and return the file path."""
        if not self.accumulated_translation:
            logger.warning("No translation data to save")
            return ""

        # Combine all translation fragments.
        full_translation = "\n".join(self.accumulated_translation)

        # Build the output filename.
        timestamp = self.recording_start_time.strftime("%Y%m%d_%H%M%S")
        target_lang = self.current_options.get("target_language", "en")

        def _generate_filename(extension: str) -> str:
            return self.file_manager.create_unique_filename(
                f"translation_{target_lang}_{timestamp}", extension, subdirectory="Translations"
            )

        filename = _generate_filename("txt")

        # Save the text to disk.
        try:
            final_path = self.file_manager.save_text_file(
                full_translation, filename, subdirectory="Translations"
            )

            logger.info(f"Translation saved: {final_path}")
            return final_path

        except Exception as e:
            logger.error(f"Failed to save translation: {e}")
            if self.on_error:
                self.on_error(f"Failed to save translation: {e}")
            return ""

    def _save_markers(self) -> str:
        """Persist marker metadata to disk and return the file path."""
        if not self.markers or not self.recording_start_time:
            logger.debug("No markers to save")
            return ""

        payload = {
            "start_time": self.recording_start_time.isoformat(),
            "markers": [marker.copy() for marker in self.markers],
        }

        timestamp = self.recording_start_time.strftime("%Y%m%d_%H%M%S")

        def _generate_filename(extension: str) -> str:
            return self.file_manager.create_unique_filename(
                f"markers_{timestamp}", extension, subdirectory="Markers"
            )

        filename = _generate_filename("json")

        try:
            json_content = json.dumps(payload, ensure_ascii=False, indent=2)
            final_path = self.file_manager.save_text_file(
                json_content, filename, subdirectory="Markers"
            )
            logger.info(f"Markers saved: {final_path}")
            return final_path
        except Exception as e:  # noqa: BLE001
            logger.error(f"Failed to save markers: {e}")
            if self.on_error:
                self.on_error(f"Failed to save markers: {e}")
            return ""

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

    async def _create_calendar_event(self, recording_result: Dict) -> str:
        """Create a calendar event describing the completed recording session.

        Args:
            recording_result: Result payload returned by :meth:`stop_recording`.

        Returns:
            str: Identifier of the created event, or an empty string on failure.
        """
        if self.db is None:
            warning_message = self._translate(
                "realtime_record.calendar_event.db_missing",
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
                        "Error invoking calendar warning callback: %s", callback_exc, exc_info=True
                    )
            return ""

        try:
            from data.database.models import CalendarEvent, EventAttachment

            # Create the calendar event entry.
            start_reference = self.recording_start_time or datetime.now()
            title_time = start_reference.strftime("%Y-%m-%d %H:%M")
            duration_value = recording_result.get("duration", 0.0)
            try:
                duration_label = f"{float(duration_value):.2f}"
            except (TypeError, ValueError):
                duration_label = str(duration_value)

            event = CalendarEvent(
                title=self._translate(
                    "realtime_record.calendar_event.title",
                    "Recording Session - {timestamp}",
                    timestamp=title_time,
                ),
                event_type="Event",
                start_time=recording_result["start_time"],
                end_time=recording_result["end_time"],
                description=self._translate(
                    "realtime_record.calendar_event.description",
                    "Recording duration: {duration} seconds",
                    duration=duration_label,
                ),
                source="local",
            )
            event.save(self.db)

            # Attach artifacts that were produced during the session.
            if "recording_path" in recording_result:
                rec_path = recording_result["recording_path"]
                if rec_path and os.path.exists(rec_path):
                    attachment = EventAttachment(
                        event_id=event.id,
                        attachment_type="recording",
                        file_path=rec_path,
                        file_size=os.path.getsize(rec_path),
                    )
                    attachment.save(self.db)

            if "transcript_path" in recording_result:
                trans_path = recording_result["transcript_path"]
                if trans_path and os.path.exists(trans_path):
                    attachment = EventAttachment(
                        event_id=event.id,
                        attachment_type="transcript",
                        file_path=trans_path,
                        file_size=os.path.getsize(trans_path),
                    )
                    attachment.save(self.db)

            # Attach translation output when available.
            if "translation_path" in recording_result:
                translation_path = recording_result["translation_path"]
                if translation_path and os.path.exists(translation_path):
                    attachment = EventAttachment(
                        event_id=event.id,
                        attachment_type="translation",
                        file_path=translation_path,
                        file_size=os.path.getsize(translation_path),
                    )
                    attachment.save(self.db)

            logger.info(f"Calendar event created: {event.id}")
            return event.id

        except Exception as e:
            error_message = self._translate(
                "realtime_record.calendar_event.creation_failed",
                "Failed to create calendar event: {error}",
                error=str(e),
            )
            logger.error(error_message)
            if self.on_error:
                self.on_error(error_message)
            return ""

    async def get_transcription_stream(self) -> AsyncIterator[str]:
        """Yield transcription snippets as they become available.

        Yields:
            str: Incremental transcription text.

        Note:
            The callback-based API remains the preferred integration point for
            UI updates. The async generator is provided for consumers that need
            a pure asyncio interface.
        """
        queue = self._transcription_stream_queue
        if queue is None:
            return

        # Queue items are produced asynchronously by ``_process_audio_stream``.
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
        """Yield translation snippets as they become available.

        Yields:
            str: Incremental translation text.

        Note:
            The callback API remains the primary integration surface. Use the
            async generator when a coroutine-based interface is preferable.
        """
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
        except asyncio.QueueFull:  # pragma: no cover - queue is unbounded by default
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

        with self._marker_lock:
            self.markers = []

        self._drain_queue(self.transcription_queue)
        self._drain_queue(self.translation_queue)
        self._drain_queue(self._transcription_stream_queue)
        self._drain_queue(self._translation_stream_queue)

        self._release_session_queues()

    def _is_duplicate_transcription(self, new_text: str, last_text: str) -> bool:
        """Return ``True`` when the new transcript duplicates the last output.

        Args:
            new_text: Latest transcript candidate.
            last_text: Previous transcript text.

        Returns:
            bool: ``True`` if the new transcript is considered a duplicate.
        """
        if not last_text:
            return False

        # Exact string equality is a duplication.
        if new_text == last_text:
            return True

        # Approximate similarity detection by checking substring relationships.
        new_lower = new_text.lower().strip()
        last_lower = last_text.lower().strip()

        # Treat the texts as duplicates when they largely overlap in content.
        if new_lower in last_lower or last_lower in new_lower:
            length_ratio = min(len(new_lower), len(last_lower)) / max(
                len(new_lower), len(last_lower)
            )
            if length_ratio > 0.7:  # 70% similarity threshold.
                return True

        return False
