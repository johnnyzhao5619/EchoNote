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
Session archiver for handling file persistence and conversion.
"""

import asyncio
import json
import logging
import os
import shutil
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import soundfile as sf

logger = logging.getLogger(__name__)


class SessionArchiver:
    """Handles the persistence of recording session artifacts (audio, text, markers)."""

    def __init__(self, file_manager):
        """
        Initialize the session archiver.

        Args:
            file_manager: FileManager instance for path management and basic file ops.
        """
        self.file_manager = file_manager
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="ArchiverWorker")

        # Streaming recording state used to avoid large in-memory concatenation.
        self._recording_lock = threading.Lock()
        self._active_recording: Optional[Dict[str, Any]] = None
        self._failed_recording_prefix: Optional[Dict[str, str]] = None

    def _run_in_executor(self, func, *args):
        """Helper to run synchronous IO/CPU tasks in a thread pool."""
        loop = asyncio.get_running_loop()
        return loop.run_in_executor(self._executor, func, *args)

    @staticmethod
    def _build_base_filename(start_time: datetime) -> str:
        timestamp = start_time.strftime("%Y%m%d_%H%M%S")
        return f"recording_{timestamp}"

    def start_recording_capture(self, start_time: datetime, sample_rate: int) -> bool:
        """Start streaming recording data to a temporary WAV file."""
        if sample_rate <= 0:
            logger.error("Invalid sample rate for streaming recording: %s", sample_rate)
            return False

        base_filename = self._build_base_filename(start_time)
        temp_wav_name = f"{base_filename}.wav"
        temp_path = self.file_manager.get_temp_path(temp_wav_name)

        with self._recording_lock:
            self._abort_active_recording_locked()
            self._cleanup_failed_prefix_locked()

            try:
                writer = sf.SoundFile(
                    temp_path,
                    mode="w",
                    samplerate=int(sample_rate),
                    channels=1,
                    subtype="PCM_16",
                )
            except Exception as exc:  # noqa: BLE001
                logger.error("Failed to open temporary WAV for streaming: %s", exc, exc_info=True)
                return False

            self._active_recording = {
                "base_filename": base_filename,
                "temp_wav_path": temp_path,
                "writer": writer,
                "write_error": None,
            }

        logger.info("Streaming recording persistence started: %s", temp_path)
        return True

    def failover_recording_capture(self) -> bool:
        """
        Stop active streaming capture and preserve already-written audio.

        Returns:
            ``True`` when an on-disk prefix was preserved for later merge.
        """
        with self._recording_lock:
            if not self._active_recording:
                return False

            recording = self._active_recording
            self._active_recording = None
            self._cleanup_failed_prefix_locked()

            writer = recording.get("writer")
            if writer is not None:
                try:
                    writer.close()
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Failed to close streaming writer during failover: %s", exc)

            temp_wav_path = str(recording.get("temp_wav_path", ""))
            base_filename = str(recording.get("base_filename", "recording"))
            if not temp_wav_path or not os.path.exists(temp_wav_path):
                return False

            self._failed_recording_prefix = {
                "temp_wav_path": temp_wav_path,
                "base_filename": base_filename,
            }
            logger.info("Streaming recording failover enabled with preserved prefix: %s", temp_wav_path)
            return True

    def append_recording_chunk(self, audio_chunk: np.ndarray) -> bool:
        """Append a single audio chunk to the active temporary recording file."""
        if audio_chunk is None or len(audio_chunk) == 0:
            return True

        with self._recording_lock:
            if not self._active_recording:
                return False

            if self._active_recording.get("write_error") is not None:
                return False

            writer = self._active_recording.get("writer")
            if writer is None:
                return False

            try:
                chunk = np.asarray(audio_chunk, dtype=np.float32).reshape(-1)
                writer.write(chunk)
                return True
            except Exception as exc:  # noqa: BLE001
                self._active_recording["write_error"] = exc
                logger.error("Failed to append streaming audio chunk: %s", exc, exc_info=True)
                return False

    async def finish_recording_capture(self, format: str = "wav") -> str:
        """Finish streaming capture and persist final recording format."""
        with self._recording_lock:
            recording = None
            write_error = None
            writer = None

            if self._active_recording:
                recording = self._active_recording
                self._active_recording = None
                writer = recording.get("writer")
                write_error = recording.get("write_error")
            elif self._failed_recording_prefix:
                recording = self._failed_recording_prefix
                self._failed_recording_prefix = None

            if not recording:
                return ""

            if writer is not None:
                try:
                    writer.close()
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Failed to close streaming writer: %s", exc)

            temp_wav_path = str(recording.get("temp_wav_path", ""))
            base_filename = str(recording.get("base_filename", "recording"))

        if write_error is not None:
            logger.error("Streaming recording capture failed: %s", write_error)
            self._cleanup_temp_file(temp_wav_path)
            return ""

        return await self._run_in_executor(
            self._finalize_recording_sync,
            temp_wav_path,
            base_filename,
            format,
        )

    def abort_recording_capture(self) -> None:
        """Abort active streaming recording and clean temporary resources."""
        with self._recording_lock:
            self._abort_active_recording_locked()
            self._cleanup_failed_prefix_locked()

    def _abort_active_recording_locked(self) -> None:
        """Internal abort helper that assumes ``_recording_lock`` is held."""
        if not self._active_recording:
            return

        writer = self._active_recording.get("writer")
        temp_wav_path = self._active_recording.get("temp_wav_path", "")

        if writer is not None:
            try:
                writer.close()
            except Exception as exc:  # noqa: BLE001
                logger.debug("Failed to close writer during abort: %s", exc)

        self._cleanup_temp_file(temp_wav_path)
        self._active_recording = None

    def _cleanup_failed_prefix_locked(self) -> None:
        """Internal helper that assumes ``_recording_lock`` is held."""
        if not self._failed_recording_prefix:
            return

        self._cleanup_temp_file(self._failed_recording_prefix.get("temp_wav_path", ""))
        self._failed_recording_prefix = None

    def _consume_failed_prefix(self) -> Optional[Dict[str, str]]:
        with self._recording_lock:
            if not self._failed_recording_prefix:
                return None
            prefix = self._failed_recording_prefix
            self._failed_recording_prefix = None
            return prefix

    @staticmethod
    def _cleanup_temp_file(path: str) -> None:
        if not path:
            return
        try:
            os.unlink(path)
        except OSError:
            pass

    async def save_recording(
        self,
        audio_buffer: List[np.ndarray],
        start_time: datetime,
        sample_rate: int,
        format: str = "wav",
    ) -> str:
        """
        Persist captured audio to disk.

        Args:
            audio_buffer: List of audio chunks.
            start_time: Session start time.
            sample_rate: Audio sample rate.
            format: Target format ('wav' or 'mp3').

        Returns:
            Path to the saved file.
        """
        prefix_recording = self._consume_failed_prefix()

        if not audio_buffer and not prefix_recording:
            logger.warning("No audio data to save")
            return ""

        if sample_rate <= 0:
            logger.error("Invalid sample rate when saving audio buffer: %s", sample_rate)
            if prefix_recording:
                self._cleanup_temp_file(prefix_recording.get("temp_wav_path", ""))
            return ""

        base_filename = self._build_base_filename(start_time)
        if prefix_recording:
            base_filename = str(prefix_recording.get("base_filename", base_filename))

            if not audio_buffer:
                temp_wav_path = prefix_recording.get("temp_wav_path", "")
                return await self._run_in_executor(
                    self._finalize_recording_sync,
                    temp_wav_path,
                    base_filename,
                    format,
                )

        try:
            return await self._run_in_executor(
                self._save_recording_from_buffer_sync,
                audio_buffer,
                base_filename,
                sample_rate,
                format,
                prefix_recording.get("temp_wav_path", "") if prefix_recording else "",
            )
        finally:
            if prefix_recording:
                self._cleanup_temp_file(prefix_recording.get("temp_wav_path", ""))

    def _save_recording_from_buffer_sync(
        self,
        audio_buffer: List[np.ndarray],
        base_filename: str,
        sample_rate: int,
        format: str,
        prefix_wav_path: str = "",
    ) -> str:
        """Synchronous fallback for persisting buffered audio chunks."""
        temp_wav_name = f"{base_filename}.wav"
        temp_path = self.file_manager.get_temp_path(temp_wav_name)
        wrote_audio = False

        try:
            with sf.SoundFile(
                temp_path,
                mode="w",
                samplerate=int(sample_rate),
                channels=1,
                subtype="PCM_16",
            ) as writer:
                if prefix_wav_path:
                    try:
                        with sf.SoundFile(prefix_wav_path, mode="r") as prefix_reader:
                            if int(prefix_reader.samplerate) != int(sample_rate):
                                logger.warning(
                                    "Prefix audio sample rate mismatch: prefix=%s, session=%s",
                                    prefix_reader.samplerate,
                                    sample_rate,
                                )
                            while True:
                                prefix_chunk = prefix_reader.read(
                                    frames=4096, dtype="float32", always_2d=False
                                )
                                if prefix_chunk is None or len(prefix_chunk) == 0:
                                    break
                                writer.write(np.asarray(prefix_chunk, dtype=np.float32).reshape(-1))
                                wrote_audio = True
                    except Exception as exc:  # noqa: BLE001
                        logger.error(
                            "Failed to merge prefix audio '%s': %s",
                            prefix_wav_path,
                            exc,
                            exc_info=True,
                        )

                for chunk in audio_buffer:
                    if chunk is None:
                        continue
                    chunk_array = np.asarray(chunk, dtype=np.float32).reshape(-1)
                    if chunk_array.size == 0:
                        continue
                    writer.write(chunk_array)
                    wrote_audio = True
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to persist buffered audio chunks: %s", exc, exc_info=True)
            self._cleanup_temp_file(temp_path)
            return ""

        if not wrote_audio:
            logger.warning("No valid audio content after buffer persistence merge")
            self._cleanup_temp_file(temp_path)
            return ""

        return self._finalize_recording_sync(temp_path, base_filename, format)

    def _finalize_recording_sync(self, temp_wav_path: str, base_filename: str, format: str) -> str:
        """Persist a temp WAV file to final format and location."""
        temp_wav = Path(temp_wav_path)
        if not temp_wav.exists():
            logger.error("Temporary WAV file missing: %s", temp_wav_path)
            return ""

        final_format = str(format or "wav").strip().lower()

        try:
            if final_format == "mp3":
                if self._is_mp3_conversion_available():
                    temp_mp3_name = f"{base_filename}.mp3"
                    temp_mp3_path = self.file_manager.get_temp_path(temp_mp3_name)
                    try:
                        self._convert_wav_to_mp3(str(temp_wav), temp_mp3_path)
                        with open(temp_mp3_path, "rb") as file:
                            content = file.read()

                        filename = self.file_manager.create_unique_filename(
                            base_filename, "mp3", subdirectory="Recordings"
                        )
                        final_path = self.file_manager.save_file(
                            content, filename, subdirectory="Recordings"
                        )
                        logger.info("Recording saved as MP3: %s", final_path)
                        return final_path
                    except Exception as exc:  # noqa: BLE001
                        logger.error("MP3 conversion failed: %s. Falling back to WAV.", exc)
                        final_format = "wav"
                    finally:
                        self._cleanup_temp_file(temp_mp3_path)
                else:
                    logger.warning("MP3 conversion not available. Saving as WAV.")
                    final_format = "wav"

            if final_format == "wav":
                with open(temp_wav, "rb") as file:
                    content = file.read()

                filename = self.file_manager.create_unique_filename(
                    base_filename, "wav", subdirectory="Recordings"
                )
                final_path = self.file_manager.save_file(content, filename, subdirectory="Recordings")
                logger.info("Recording saved as WAV: %s", final_path)
                return final_path

            logger.error("Unsupported recording format '%s', unable to finalize file", final_format)
            return ""
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to finalize audio file: %s", exc, exc_info=True)
            return ""
        finally:
            self._cleanup_temp_file(str(temp_wav))

    async def save_text(
        self,
        lines: List[str],
        start_time: datetime,
        prefix: str,
        subdirectory: str,
    ) -> str:
        """
        Persist text data (transcript or translation).
        """
        if not lines:
            return ""

        content = "\n".join(lines)
        timestamp = start_time.strftime("%Y%m%d_%H%M%S")
        base_filename = f"{prefix}_{timestamp}"

        return await self._run_in_executor(
            self._save_text_sync, content, base_filename, subdirectory
        )

    def _save_text_sync(self, content: str, base_filename: str, subdirectory: str) -> str:
        try:
            filename = self.file_manager.create_unique_filename(
                base_filename, "txt", subdirectory=subdirectory
            )
            final_path = self.file_manager.save_text_file(
                content, filename, subdirectory=subdirectory
            )
            logger.info(f"Text saved to {subdirectory}: {final_path}")
            return final_path
        except Exception as e:
            logger.error(f"Failed to save text content: {e}")
            return ""

    async def save_markers(self, markers: List[Dict[str, Any]], start_time: datetime) -> str:
        """Persist markers to JSON."""
        if not markers:
            return ""

        payload = {
            "start_time": start_time.isoformat(),
            "markers": markers,
        }

        timestamp = start_time.strftime("%Y%m%d_%H%M%S")
        base_filename = f"markers_{timestamp}"

        return await self._run_in_executor(
            self._save_markers_sync, payload, base_filename
        )

    def _save_markers_sync(self, payload: Dict[str, Any], base_filename: str) -> str:
        try:
            content = json.dumps(payload, ensure_ascii=False, indent=2)
            filename = self.file_manager.create_unique_filename(
                base_filename, "json", subdirectory="Markers"
            )
            final_path = self.file_manager.save_text_file(
                content, filename, subdirectory="Markers"
            )
            logger.info(f"Markers saved: {final_path}")
            return final_path
        except Exception as e:
            logger.error(f"Failed to save markers: {e}")
            return ""

    def _is_mp3_conversion_available(self) -> bool:
        """Check if FFmpeg is available."""
        return shutil.which("ffmpeg") is not None

    def _convert_wav_to_mp3(self, wav_path: str, mp3_path: str) -> None:
        """Convert WAV to MP3 using FFmpeg."""
        command = ["ffmpeg", "-y", "-i", wav_path, "-codec:a", "libmp3lame", mp3_path]
        subprocess.run(
            command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
