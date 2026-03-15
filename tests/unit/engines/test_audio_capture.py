# SPDX-License-Identifier: Apache-2.0
"""Unit tests for AudioCapture shutdown behavior."""

import queue
from unittest.mock import Mock

import numpy as np

from engines.audio.capture import AudioCapture


def _build_capture_for_stop() -> AudioCapture:
    capture = AudioCapture.__new__(AudioCapture)
    capture.is_capturing = True
    capture.stream = Mock()
    capture.capture_thread = Mock()
    capture.audio_queue = queue.Queue()
    capture.audio_queue.put_nowait([0.1, 0.2, 0.3])
    return capture


def test_stop_capture_closes_stream_before_joining_thread():
    capture = _build_capture_for_stop()

    order = []
    capture.stream.stop_stream.side_effect = lambda: order.append("stop_stream")
    capture.stream.close.side_effect = lambda: order.append("close")
    capture.capture_thread.join.side_effect = lambda timeout: order.append("join")
    capture.capture_thread.is_alive.return_value = False

    capture.stop_capture()

    assert order == ["stop_stream", "close", "join"]
    assert capture.is_capturing is False
    assert capture.stream is None
    assert capture.capture_thread is None
    assert capture.audio_queue.empty()


def test_stop_capture_handles_non_terminating_capture_thread():
    capture = _build_capture_for_stop()
    thread = capture.capture_thread
    thread.is_alive.return_value = True

    capture.stop_capture()

    thread.join.assert_called_once()
    thread.is_alive.assert_called_once()
    assert capture.capture_thread is None


def test_downmix_to_mono_averages_channels():
    capture = AudioCapture.__new__(AudioCapture)
    capture._warned_partial_frame = False
    audio = np.array([1, 3, 5, 7], dtype=np.int16)

    mixed = capture._downmix_to_mono(audio, 2)

    assert mixed.dtype == np.float64 or mixed.dtype == np.float32
    assert mixed.tolist() == [2.0, 6.0]
