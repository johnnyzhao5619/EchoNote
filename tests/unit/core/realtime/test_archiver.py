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
Unit tests for SessionArchiver.
"""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from core.realtime.archiver import SessionArchiver


class TestSessionArchiver:
    @pytest.fixture
    def mock_file_manager(self):
        fm = MagicMock()
        fm.get_temp_path.side_effect = lambda name: f"/tmp/{name}"
        fm.create_unique_filename.side_effect = lambda base, ext, **kwargs: f"{base}.{ext}"
        fm.save_file.return_value = "/final/path/file.wav"
        fm.save_text_file.return_value = "/final/path/file.txt"
        return fm

    @pytest.fixture
    def archiver(self, mock_file_manager):
        return SessionArchiver(mock_file_manager)

    @pytest.mark.asyncio
    async def test_save_recording_success_wav(self, archiver, mock_file_manager):
        """Test saving audio as WAV."""
        audio_buffer = [np.zeros(1000, dtype=np.float32)]
        start_time = datetime(2023, 1, 1, 12, 0, 0)

        with (
            patch("core.realtime.archiver.tempfile.NamedTemporaryFile") as mock_temp,
            patch("builtins.open", new_callable=MagicMock) as mock_open,
            patch("os.unlink") as mock_unlink,
        ):

            mock_temp.return_value.__enter__.return_value.name = "/tmp/recording.wav"
            mock_file_manager.ensure_directory.return_value = "/final/path"
            mock_file_manager.save_file.return_value = "/final/path/file.wav"

            path = await archiver.save_recording(audio_buffer, start_time, 16000, format="wav")

            assert path == "/final/path/file.wav"
            mock_file_manager.save_file.assert_called_once()
            mock_unlink.assert_called_with("/tmp/recording_20230101_120000.wav")

    @pytest.mark.asyncio
    async def test_save_recording_empty_buffer(self, archiver):
        """Test saving with empty buffer."""
        path = await archiver.save_recording([], datetime.now(), 16000)
        assert path == ""

    @pytest.mark.asyncio
    async def test_save_text(self, archiver, mock_file_manager):
        """Test saving text content."""
        lines = ["Hello", "World"]
        start_time = datetime(2023, 1, 1, 12, 0, 0)

        path = await archiver.save_text(
            lines, start_time, prefix="transcript", subdirectory="Transcripts"
        )

        assert path == "/final/path/file.txt"
        mock_file_manager.save_text_file.assert_called()
        args = mock_file_manager.save_text_file.call_args
        assert args[0][0] == "Hello\nWorld"  # Content check

    @pytest.mark.asyncio
    async def test_save_markers(self, archiver, mock_file_manager):
        """Test saving markers."""
        markers = [{"index": 1, "offset": 10.5, "label": "Test"}]
        start_time = datetime(2023, 1, 1, 12, 0, 0)

        path = await archiver.save_markers(markers, start_time)

        assert path == "/final/path/file.txt"
        mock_file_manager.save_text_file.assert_called()

    @pytest.mark.asyncio
    async def test_save_recording_mp3_conversion(self, archiver, mock_file_manager):
        """Test saving as MP3 with conversion."""
        audio_buffer = [np.zeros(1000, dtype=np.float32)]
        start_time = datetime(2023, 1, 1, 12, 0, 0)

        with (
            patch("core.realtime.archiver.tempfile.NamedTemporaryFile") as mock_temp,
            patch("soundfile.write"),
            patch("shutil.which", return_value="/usr/bin/ffmpeg"),
            patch("subprocess.run") as mock_run,
            patch("builtins.open", new_callable=MagicMock),
            patch("os.unlink"),
        ):

            mock_temp.return_value.__enter__.return_value.name = "/tmp/recording.wav"
            mock_file_manager.ensure_directory.return_value = "/final/path"
            mock_file_manager.save_file.return_value = "/final/path/file.wav"

            path = await archiver.save_recording(audio_buffer, start_time, 16000, format="mp3")

            assert path == "/final/path/file.wav"
            mock_run.assert_called_once()
            # Verify ffmpeg command args
            cmd = mock_run.call_args[0][0]
            assert "ffmpeg" in cmd
            assert "libmp3lame" in cmd

    @pytest.mark.asyncio
    async def test_save_recording_uses_failed_prefix_without_buffer(self, archiver):
        """When stream failover produced prefix only, finalize that file directly."""
        archiver._failed_recording_prefix = {
            "temp_wav_path": "/tmp/prefix.wav",
            "base_filename": "recording_20230101_120000",
        }
        start_time = datetime(2023, 1, 1, 12, 0, 0)

        with patch.object(
            archiver, "_run_in_executor", new=AsyncMock(return_value="/final/path/file.wav")
        ) as mock_exec:
            path = await archiver.save_recording([], start_time, 16000, format="wav")

        assert path == "/final/path/file.wav"
        mock_exec.assert_called_once_with(
            archiver._finalize_recording_sync,
            "/tmp/prefix.wav",
            "recording_20230101_120000",
            "wav",
        )

    @pytest.mark.asyncio
    async def test_save_recording_merges_failed_prefix_and_buffer(self, archiver):
        """When stream failover happened, remaining buffer should merge with prefix."""
        audio_buffer = [np.zeros(1000, dtype=np.float32)]
        archiver._failed_recording_prefix = {
            "temp_wav_path": "/tmp/prefix.wav",
            "base_filename": "recording_20230101_120000",
        }
        start_time = datetime(2023, 1, 1, 12, 0, 0)

        with (
            patch.object(
                archiver, "_run_in_executor", new=AsyncMock(return_value="/final/path/file.wav")
            ) as mock_exec,
            patch("os.unlink") as mock_unlink,
        ):
            path = await archiver.save_recording(audio_buffer, start_time, 16000, format="wav")

        assert path == "/final/path/file.wav"
        mock_exec.assert_called_once_with(
            archiver._save_recording_from_buffer_sync,
            audio_buffer,
            "recording_20230101_120000",
            16000,
            "wav",
            "/tmp/prefix.wav",
        )
        mock_unlink.assert_called_with("/tmp/prefix.wav")
