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
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor

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

    def _run_in_executor(self, func, *args):
        """Helper to run synchronous IO/CPU tasks in a thread pool."""
        loop = asyncio.get_running_loop()
        return loop.run_in_executor(self._executor, func, *args)

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
        if not audio_buffer:
            logger.warning("No audio data to save")
            return ""

        timestamp = start_time.strftime("%Y%m%d_%H%M%S")
        base_filename = f"recording_{timestamp}"
        
        # Prepare data merging in thread
        try:
            audio_data = await self._run_in_executor(np.concatenate, audio_buffer)
        except Exception as e:
            logger.error(f"Failed to concatenate audio buffer: {e}")
            return ""

        return await self._run_in_executor(
            self._save_audio_sync,
            audio_data,
            base_filename,
            sample_rate,
            format
        )

    def _save_audio_sync(
        self,
        audio_data: np.ndarray,
        base_filename: str,
        sample_rate: int,
        format: str,
    ) -> str:
        """Synchronous implementation of audio saving."""
        try:
            # Always save as WAV first (temp)
            temp_wav_name = f"{base_filename}.wav"
            temp_path = self.file_manager.get_temp_path(temp_wav_name)
            
            sf.write(temp_path, audio_data, sample_rate)

            final_format = format.lower()
            if final_format == "mp3":
                if self._is_mp3_conversion_available():
                    temp_mp3_name = f"{base_filename}.mp3"
                    temp_mp3_path = self.file_manager.get_temp_path(temp_mp3_name)
                    try:
                        self._convert_wav_to_mp3(temp_path, temp_mp3_path)
                        # Read MP3 content to save via file manager
                        with open(temp_mp3_path, "rb") as f:
                            content = f.read()
                        
                        filename = self.file_manager.create_unique_filename(
                            base_filename, "mp3", subdirectory="Recordings"
                        )
                        final_path = self.file_manager.save_file(
                            content, filename, subdirectory="Recordings"
                        )
                        
                        # Cleanup temp MP3
                        try:
                            os.unlink(temp_mp3_path)
                        except OSError:
                            pass
                            
                        # Cleanup temp WAV
                        try:
                            os.unlink(temp_path)
                        except OSError:
                            pass
                            
                        logger.info(f"Recording saved as MP3: {final_path}")
                        return final_path
                        
                    except Exception as e:
                        logger.error(f"MP3 conversion failed: {e}. Falling back to WAV.")
                        # Fallback to WAV
                        final_format = "wav"
                else:
                    logger.warning("MP3 conversion not available. Saving as WAV.")
                    final_format = "wav"

            # WAV path
            if final_format == "wav":
                with open(temp_path, "rb") as f:
                    content = f.read()
                
                filename = self.file_manager.create_unique_filename(
                    base_filename, "wav", subdirectory="Recordings"
                )
                final_path = self.file_manager.save_file(
                    content, filename, subdirectory="Recordings"
                )
                
                try:
                    os.unlink(temp_path)
                except OSError:
                    pass
                    
                logger.info(f"Recording saved as WAV: {final_path}")
                return final_path

        except Exception as e:
            logger.error(f"Failed to save audio file: {e}", exc_info=True)
            return ""
        
        return ""

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
