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
Unit tests for RealtimeConfig.
"""

from pathlib import Path

from core.realtime.config import RealtimeConfig


def test_realtime_config_defaults():
    """Test default values of RealtimeConfig."""
    config = RealtimeConfig()

    assert config.sample_rate == 16000
    assert config.channels == 1
    assert config.vad_threshold == 0.5
    assert config.silence_duration_ms == 2000
    assert config.min_audio_duration == 3.0
    assert config.translation_task_timeout == 5.0
    assert config.translation_task_shutdown_timeout == 2.0

    # Check default paths
    expected_base = Path.home() / "Documents" / "EchoNote"
    assert config.base_recording_dir == expected_base
    assert config.recordings_dir == expected_base / "Recordings"
    assert config.transcripts_dir == expected_base / "Transcripts"
    assert config.translations_dir == expected_base / "Translations"
    assert config.markers_dir == expected_base / "Markers"


def test_realtime_config_overrides():
    """Test overriding values in RealtimeConfig."""
    custom_path = Path("/tmp/echonote_test")
    config = RealtimeConfig(sample_rate=44100, vad_threshold=0.5, base_recording_dir=custom_path)

    assert config.sample_rate == 44100
    assert config.vad_threshold == 0.5
    assert config.base_recording_dir == custom_path
    assert config.recordings_dir == custom_path / "Recordings"
