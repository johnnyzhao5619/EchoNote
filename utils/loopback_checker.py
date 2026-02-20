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
"""Loopback input availability checker."""

from __future__ import annotations

import logging
import platform
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.realtime.audio_routing import is_loopback_input_device

logger = logging.getLogger("echonote.utils.loopback_checker")


class LoopbackChecker:
    """Detect loopback-capable input routes and provide installation guidance."""

    def __init__(self, audio_capture=None):
        self.audio_capture = audio_capture

    def set_audio_capture(self, audio_capture) -> None:
        """Update audio capture backend used for device enumeration."""
        self.audio_capture = audio_capture

    def get_input_devices(self) -> List[Dict[str, Any]]:
        """Return input devices from configured audio backend."""
        if self.audio_capture is None:
            logger.info("Audio capture backend unavailable while checking loopback input")
            return []

        lister = getattr(self.audio_capture, "get_input_devices", None)
        if not callable(lister):
            logger.info("Audio capture backend does not expose get_input_devices")
            return []

        try:
            devices = lister() or []
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to enumerate input devices for loopback check: %s", exc)
            return []

        if not isinstance(devices, list):
            return []
        return [device for device in devices if isinstance(device, dict)]

    def get_loopback_devices(self) -> List[Dict[str, Any]]:
        """Return detected loopback-capable input devices."""
        devices = self.get_input_devices()
        return [device for device in devices if is_loopback_input_device(device)]

    def is_loopback_available(self) -> bool:
        """Return whether loopback route appears available on current machine."""
        loopback_devices = self.get_loopback_devices()
        if loopback_devices:
            return True

        if platform.system() == "Darwin":
            return self._has_macos_loopback_driver()

        return False

    def _has_macos_loopback_driver(self) -> bool:
        """Detect known loopback drivers on macOS as a fallback."""
        hal_dirs = (
            Path("/Library/Audio/Plug-Ins/HAL"),
            Path.home() / "Library/Audio/Plug-Ins/HAL",
        )
        hal_patterns = (
            "BlackHole*.driver",
            "Soundflower*.driver",
        )

        for hal_dir in hal_dirs:
            if not hal_dir.exists():
                continue
            for pattern in hal_patterns:
                try:
                    if any(hal_dir.glob(pattern)):
                        return True
                except Exception:  # pragma: no cover
                    continue

        if Path("/Applications/Loopback.app").exists():
            return True

        return False

    def get_installation_instructions(self, i18n=None) -> Tuple[str, str]:
        """Return platform-specific loopback setup instructions."""
        system = platform.system()

        if system == "Darwin":
            if i18n:
                title = i18n.t("loopback.dialog_title", platform="macOS")
                instructions = (
                    f"{i18n.t('loopback.detected_system', system='macOS')}\n\n"
                    f"{i18n.t('loopback.purpose')}\n\n"
                    f"{i18n.t('loopback.recommended_install', method=i18n.t('loopback.macos.method_blackhole'))}"
                    "\n\n"
                    f"{i18n.t('loopback.macos.step1')}\n"
                    f"{i18n.t('loopback.macos.step1_cmd')}\n\n"
                    f"{i18n.t('loopback.macos.step2')}\n"
                    f"{i18n.t('loopback.macos.step3')}\n\n"
                    f"{i18n.t('loopback.verify_install')}\n"
                    f"{i18n.t('loopback.verify_note')}\n\n"
                    f"{i18n.t('loopback.skip_note')}"
                )
            else:
                title = "Install Loopback Input (macOS)"
                instructions = (
                    "Detected your system: macOS\n\n"
                    "To capture system playback and online meeting output, install a loopback input.\n\n"
                    "Recommended open-source option: BlackHole\n\n"
                    "1. Run in Terminal:\n"
                    "   brew install --cask blackhole-2ch\n\n"
                    "2. Reboot macOS after installation\n"
                    "3. In EchoNote, select BlackHole as input device\n\n"
                    "Verify installation: you should see BlackHole in the input device list.\n\n"
                    "Without loopback input, microphone routes usually cannot capture browser/video playback."
                )
            return title, instructions

        if system == "Windows":
            if i18n:
                title = i18n.t("loopback.dialog_title", platform="Windows")
                instructions = (
                    f"{i18n.t('loopback.detected_system', system='Windows')}\n\n"
                    f"{i18n.t('loopback.purpose')}\n\n"
                    f"{i18n.t('loopback.windows.option1')}\n"
                    f"{i18n.t('loopback.windows.option1_step1')}\n"
                    f"{i18n.t('loopback.windows.option1_step2')}\n\n"
                    f"{i18n.t('loopback.windows.option2')}\n"
                    f"{i18n.t('loopback.windows.option2_step1')}\n"
                    f"{i18n.t('loopback.windows.option2_step2')}\n\n"
                    f"{i18n.t('loopback.verify_install')}\n"
                    f"{i18n.t('loopback.verify_note')}\n\n"
                    f"{i18n.t('loopback.skip_note')}"
                )
            else:
                title = "Install Loopback Input (Windows)"
                instructions = (
                    "Detected your system: Windows\n\n"
                    "To capture system playback and online meeting output, configure a loopback input.\n\n"
                    "Option 1: Enable Stereo Mix in Sound Control Panel.\n"
                    "Option 2: Install VB-CABLE and select it as recording input.\n\n"
                    "Verify installation: loopback input appears in EchoNote input devices.\n\n"
                    "Without loopback input, microphone routes usually cannot capture system playback."
                )
            return title, instructions

        if system == "Linux":
            if i18n:
                title = i18n.t("loopback.dialog_title", platform="Linux")
                instructions = (
                    f"{i18n.t('loopback.detected_system', system='Linux')}\n\n"
                    f"{i18n.t('loopback.purpose')}\n\n"
                    f"{i18n.t('loopback.linux.option1')}\n"
                    f"{i18n.t('loopback.linux.option2')}\n\n"
                    f"{i18n.t('loopback.verify_install')}\n"
                    f"{i18n.t('loopback.verify_note')}\n\n"
                    f"{i18n.t('loopback.skip_note')}"
                )
            else:
                title = "Install Loopback Input (Linux)"
                instructions = (
                    "Detected your system: Linux\n\n"
                    "To capture system playback and online meeting output, configure a monitor/loopback source.\n\n"
                    "Option 1: Use PipeWire monitor source.\n"
                    "Option 2: Use PulseAudio monitor source or virtual sink.\n\n"
                    "Verify installation: monitor/loopback input appears in EchoNote input devices.\n\n"
                    "Without loopback input, microphone routes usually cannot capture system playback."
                )
            return title, instructions

        if i18n:
            title = i18n.t("loopback.dialog_title", platform=system)
            instructions = (
                f"{i18n.t('loopback.detected_system', system=system)}\n\n"
                f"{i18n.t('loopback.purpose')}\n\n"
                f"{i18n.t('loopback.generic.visit_docs')}\n\n"
                f"{i18n.t('loopback.verify_install')}\n"
                f"{i18n.t('loopback.verify_note')}\n\n"
                f"{i18n.t('loopback.skip_note')}"
            )
        else:
            title = "Install Loopback Input"
            instructions = (
                f"Detected your system: {system}\n\n"
                "Install or configure a loopback input for system audio capture.\n\n"
                "Verify installation: loopback input appears in EchoNote input devices.\n\n"
                "Without loopback input, microphone routes usually cannot capture system playback."
            )
        return title, instructions

    def get_status_message(self) -> str:
        """Return concise loopback status message for diagnostics."""
        loopback_devices = self.get_loopback_devices()
        if loopback_devices:
            names = ", ".join(str(device.get("name", "")).strip() for device in loopback_devices)
            return f"Loopback input detected: {names}"
        if self.is_loopback_available():
            return "Loopback driver detected, but input endpoint is not currently listed."
        return "No loopback input detected"

    def check_and_log(self) -> bool:
        """Check availability and log diagnostic details."""
        system = platform.system()
        logger.info("Loopback check running on platform: %s", system)

        loopback_devices = self.get_loopback_devices()
        if loopback_devices:
            device_names = [str(device.get("name", "")).strip() for device in loopback_devices]
            logger.info("✓ Loopback input detected: %s", ", ".join(device_names))
            return True

        if system == "Darwin" and self._has_macos_loopback_driver():
            logger.info(
                "Loopback driver appears installed on macOS, but no loopback input endpoint was listed"
            )
            return True

        logger.warning("✗ No loopback input detected")
        title, _ = self.get_installation_instructions()
        logger.info("Installation guide: %s", title)
        return False


_checker: Optional[LoopbackChecker] = None


def get_loopback_checker(audio_capture=None) -> LoopbackChecker:
    """Return global loopback checker instance."""
    global _checker
    if _checker is None:
        _checker = LoopbackChecker(audio_capture=audio_capture)
    elif audio_capture is not None:
        _checker.set_audio_capture(audio_capture)
    return _checker
