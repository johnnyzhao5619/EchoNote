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
"""Helpers for input audio routing analysis (microphone vs loopback/system-audio)."""

from __future__ import annotations

import re
from typing import Any, Mapping

# Strict loopback/virtual-cable identifiers.
LOOPBACK_DEVICE_KEYWORDS = (
    "loopback",
    "blackhole",
    "soundflower",
    "vb-cable",
    "vb cable",
    "virtual audio",
    "stereo mix",
    "monitor of",
    "what u hear",
)

# Broader meeting/system-audio virtual input identifiers.
SYSTEM_AUDIO_DEVICE_KEYWORDS = LOOPBACK_DEVICE_KEYWORDS + (
    "microsoft teams",
    "teams",
    "teams audio",
    "microsoft teams audio",
    "zoom",
    "zoom audio",
    "zoomaudio",
    "google meet",
    "webex",
    "discord",
    "meeting audio",
    "virtual mic",
    "application audio",
    "app audio",
)

APP_SCOPED_SYSTEM_AUDIO_KEYWORDS = {
    "Microsoft Teams": (
        "microsoft teams",
        "teams",
    ),
    "Zoom": (
        "zoom",
        "zoomaudio",
    ),
    "Google Meet": (
        "google meet",
        "meet audio",
    ),
    "Webex": ("webex",),
    "Discord": ("discord",),
}


def _normalize_device_name(device_name: str) -> str:
    """Normalize device names to improve keyword matching stability."""
    lowered_name = str(device_name or "").strip().lower()
    if not lowered_name:
        return ""
    collapsed = re.sub(r"[^a-z0-9]+", " ", lowered_name)
    return " ".join(collapsed.split())


def is_loopback_device_name(device_name: str) -> bool:
    """Return ``True`` when ``device_name`` looks like a loopback/virtual input."""
    normalized_name = _normalize_device_name(device_name)
    if not normalized_name:
        return False
    return any(keyword in normalized_name for keyword in LOOPBACK_DEVICE_KEYWORDS)


def is_loopback_input_device(device: Mapping[str, Any] | None) -> bool:
    """Return ``True`` when the input device metadata indicates loopback capture."""
    if not device:
        return False
    return is_loopback_device_name(str(device.get("name", "")))


def is_system_audio_device_name(device_name: str) -> bool:
    """Return ``True`` when ``device_name`` appears to capture system/meeting audio."""
    normalized_name = _normalize_device_name(device_name)
    if not normalized_name:
        return False
    return any(keyword in normalized_name for keyword in SYSTEM_AUDIO_DEVICE_KEYWORDS)


def is_system_audio_input_device(device: Mapping[str, Any] | None) -> bool:
    """Return ``True`` when the device metadata indicates system-audio capture capability."""
    if not device:
        return False
    return is_system_audio_device_name(str(device.get("name", "")))


def detect_app_scoped_system_audio_device(device_name: str) -> str:
    """Return app label when input is likely scoped to a specific meeting app."""
    normalized_name = _normalize_device_name(device_name)
    if not normalized_name:
        return ""
    for app_name, keywords in APP_SCOPED_SYSTEM_AUDIO_KEYWORDS.items():
        if any(keyword in normalized_name for keyword in keywords):
            return app_name
    return ""
