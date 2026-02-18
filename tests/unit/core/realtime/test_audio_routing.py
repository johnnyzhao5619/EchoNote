# SPDX-License-Identifier: Apache-2.0
"""Unit tests for audio routing helpers."""

from core.realtime.audio_routing import (
    detect_app_scoped_system_audio_device,
    is_loopback_device_name,
    is_loopback_input_device,
    is_system_audio_device_name,
    is_system_audio_input_device,
)


def test_is_loopback_device_name_detects_common_virtual_devices():
    assert is_loopback_device_name("BlackHole 2ch")
    assert is_loopback_device_name("VB-CABLE Output")
    assert is_loopback_device_name("Monitor of Built-in Audio")


def test_is_loopback_device_name_rejects_regular_microphone():
    assert not is_loopback_device_name("MacBook Pro Microphone")


def test_is_loopback_input_device_uses_name_field():
    assert is_loopback_input_device({"name": "Soundflower (2ch)"})
    assert not is_loopback_input_device({"name": "USB Microphone"})


def test_is_system_audio_device_name_detects_meeting_virtual_inputs():
    assert is_system_audio_device_name("Microsoft Teams Audio")
    assert is_system_audio_device_name("ZoomAudio Device")
    assert is_system_audio_device_name("MICROSOFT_TEAMS-AUDIO")


def test_is_system_audio_input_device_uses_name_field():
    assert is_system_audio_input_device({"name": "Microsoft Teams Audio"})
    assert not is_system_audio_input_device({"name": "MacBook Pro Microphone"})


def test_detect_app_scoped_system_audio_device_returns_app_name():
    assert detect_app_scoped_system_audio_device("Microsoft Teams Audio") == "Microsoft Teams"
    assert detect_app_scoped_system_audio_device("ZoomAudio Device") == "Zoom"
    assert detect_app_scoped_system_audio_device("BlackHole 2ch") == ""
