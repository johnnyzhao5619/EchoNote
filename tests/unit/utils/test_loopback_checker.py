# SPDX-License-Identifier: Apache-2.0
"""Unit tests for loopback checker."""

from unittest.mock import Mock, patch

from utils.loopback_checker import LoopbackChecker


def test_loopback_checker_detects_loopback_input_devices():
    audio_capture = Mock()
    audio_capture.get_input_devices.return_value = [
        {"index": 1, "name": "MacBook Pro Microphone"},
        {"index": 2, "name": "BlackHole 2ch"},
    ]

    checker = LoopbackChecker(audio_capture=audio_capture)
    devices = checker.get_loopback_devices()

    assert len(devices) == 1
    assert devices[0]["name"] == "BlackHole 2ch"
    assert checker.is_loopback_available() is True


def test_loopback_checker_returns_false_when_no_loopback_input():
    audio_capture = Mock()
    audio_capture.get_input_devices.return_value = [
        {"index": 1, "name": "MacBook Pro Microphone"},
        {"index": 3, "name": "USB Microphone"},
    ]

    checker = LoopbackChecker(audio_capture=audio_capture)
    with patch("platform.system", return_value="Linux"):
        assert checker.is_loopback_available() is False


def test_loopback_checker_accepts_macos_driver_fallback():
    checker = LoopbackChecker(audio_capture=None)
    with (
        patch("platform.system", return_value="Darwin"),
        patch.object(checker, "_has_macos_loopback_driver", return_value=True),
    ):
        assert checker.is_loopback_available() is True


def test_loopback_checker_macos_instructions_include_blackhole():
    checker = LoopbackChecker(audio_capture=None)
    with patch("platform.system", return_value="Darwin"):
        title, instructions = checker.get_installation_instructions()

    assert "macOS" in title
    assert "blackhole-2ch" in instructions.lower()
