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
Configuration for real-time recording and transcription.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class RealtimeConfig:
    """Configuration settings for real-time recording sessions."""

    # Audio Settings
    sample_rate: int = 16000
    channels: int = 1

    # VAD Settings
    vad_threshold: float = 0.5
    silence_duration_ms: int = 2000
    min_audio_duration: float = 3.0

    # Task Timeouts
    # processing_task_timeout: time to wait for the audio transcription task to finish on stop.
    processing_task_timeout: float = 5.0
    # translation_task_timeout: time to wait for pending translations to drain after stop.
    # Opus-MT model loading takes 5-30 s on first use; each segment ~1-2 s thereafter.
    # 120 s accommodates cold-start plus a reasonable translation backlog.
    translation_task_timeout: float = 120.0
    translation_task_shutdown_timeout: float = 5.0

    # Default Paths (can be overridden by FileManager or User settings)
    base_recording_dir: Path = field(default_factory=lambda: Path.home() / "Documents" / "EchoNote")

    @classmethod
    def from_dict(cls, config_dict: dict) -> "RealtimeConfig":
        """Create a RealtimeConfig instance from a dictionary."""
        from dataclasses import fields

        valid_keys = {f.name for f in fields(cls)}
        filtered_args = {k: v for k, v in config_dict.items() if k in valid_keys}

        return cls(**filtered_args)

    @property
    def recordings_dir(self) -> Path:
        return self.base_recording_dir / "Recordings"

    @property
    def transcripts_dir(self) -> Path:
        return self.base_recording_dir / "Transcripts"

    @property
    def translations_dir(self) -> Path:
        return self.base_recording_dir / "Translations"

    @property
    def markers_dir(self) -> Path:
        return self.base_recording_dir / "Markers"
