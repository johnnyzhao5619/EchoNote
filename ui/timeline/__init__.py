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
"""Timeline UI components."""

import logging

logger = logging.getLogger("echonote.ui.timeline")

try:
    from ui.timeline.audio_player import AudioPlayer, AudioPlayerDialog
except ImportError as exc:  # pragma: no cover - exercised in degraded environments
    AudioPlayer = None
    AudioPlayerDialog = None
    logger.warning(
        "Audio playback components are unavailable: %s. Timeline UI will "
        "operate without inline audio playback.",
        exc,
    )

__all__ = [
    "TimelineWidget",
    "EventCard",
    "CurrentTimeIndicator",
    "AudioPlayer",
    "AudioPlayerDialog",
    "TranscriptViewer",
    "TranscriptViewerDialog",
]
