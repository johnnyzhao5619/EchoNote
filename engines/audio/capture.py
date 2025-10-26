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
"""Audio capture module implemented with PyAudio."""

import importlib
import logging
import queue
import threading
from typing import Callable, Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)


class AudioCapture:
    """High-level wrapper for microphone capture using PyAudio."""

    def __init__(
        self, sample_rate: int = 16000, channels: int = 1, chunk_size: int = 512, gain: float = 1.0
    ):
        """Initialize the capture interface.

        PyAudio is imported and instantiated lazily so the optional dependency
        is only required when microphone capture is enabled.

        Args:
            sample_rate: Sampling rate in Hz. Defaults to 16 kHz (Whisper
                baseline).
            channels: Number of input channels. Defaults to mono.
            chunk_size: Number of samples per read. Defaults to 512 samples
                (~32 ms at 16 kHz).
            gain: Linear gain factor applied to captured audio. Defaults to 1.0.
        """
        self.sample_rate = sample_rate
        self.channels = channels
        self.chunk_size = chunk_size
        self.gain = gain

        self.pyaudio = None
        self.stream = None
        self.is_capturing = False
        self.capture_thread = None
        self.audio_queue = queue.Queue()

        self._pyaudio_module = None
        self._pyaudio_error: Optional[Exception] = None

        # Check dependency availability without instantiating PyAudio yet.
        self._ensure_module_available()

        logger.info(
            "Audio capture configured: sample_rate=%s, channels=%s, chunk_size=%s. "
            "PyAudio instance will be created on first use.",
            sample_rate,
            channels,
            chunk_size,
        )

    def _ensure_module_available(self):
        """Ensure that the PyAudio module can be imported."""
        if self._pyaudio_module is not None:
            return self._pyaudio_module

        try:
            self._pyaudio_module = importlib.import_module("pyaudio")
            return self._pyaudio_module
        except ImportError as exc:
            self._pyaudio_error = exc
            logger.warning(
                "PyAudio module not found; microphone capture is disabled until installation."
            )
            raise ImportError(
                "PyAudio is not installed. Please install it with: pip install pyaudio"
            ) from exc

    def _ensure_pyaudio_instance(self):
        """Create the PyAudio instance on demand."""
        if self.pyaudio is not None:
            return self.pyaudio

        if self._pyaudio_error is not None:
            raise self._pyaudio_error

        try:
            pyaudio_module = self._ensure_module_available()
            self.pyaudio = pyaudio_module.PyAudio()
            logger.info("PyAudio initialized successfully")
        except Exception as exc:  # noqa: BLE001
            self._pyaudio_error = exc
            logger.error("Failed to initialize PyAudio: %s", exc)
            raise

        return self.pyaudio

    def get_input_devices(self) -> List[Dict]:
        """Return a list of available audio input devices.

        Returns:
            List[Dict]: Each entry contains the device ``index``, ``name``,
            ``max_input_channels``, and ``default_sample_rate``.
        """
        try:
            pyaudio_instance = self._ensure_pyaudio_instance()
        except ImportError:
            logger.warning("PyAudio not installed; audio input listing unavailable")
            return []
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to access audio input devices: %s", exc)
            return []

        devices = []
        device_count = pyaudio_instance.get_device_count()

        for i in range(device_count):
            try:
                device_info = pyaudio_instance.get_device_info_by_index(i)

                # Only return devices with input capability.
                if device_info.get("maxInputChannels", 0) > 0:
                    devices.append(
                        {
                            "index": i,
                            "name": device_info.get("name", "Unknown"),
                            "max_input_channels": device_info.get("maxInputChannels", 0),
                            "default_sample_rate": device_info.get("defaultSampleRate", 0),
                        }
                    )
            except Exception as e:
                logger.warning(f"Failed to get info for device {i}: {e}")

        logger.info(f"Found {len(devices)} input devices")
        return devices

    def list_input_devices(self) -> list:
        """Alias for :meth:`get_input_devices` kept for API compatibility."""
        return self.get_input_devices()

    def get_default_input_device(self) -> Optional[Dict]:
        """Return the system default input device if available."""
        try:
            pyaudio_instance = self._ensure_pyaudio_instance()
            device_info = pyaudio_instance.get_default_input_device_info()
            return {
                "index": device_info.get("index", 0),
                "name": device_info.get("name", "Unknown"),
                "max_input_channels": device_info.get("maxInputChannels", 0),
                "default_sample_rate": device_info.get("defaultSampleRate", 0),
            }
        except Exception as e:
            logger.error(f"Failed to get default input device: {e}")
            return None

    def start_capture(
        self,
        device_index: Optional[int] = None,
        callback: Optional[Callable[[np.ndarray], None]] = None,
    ):
        """Start streaming audio from the selected input device.

        Args:
            device_index: Optional input device index. ``None`` selects the
                default device.
            callback: Optional callable invoked with each captured ``numpy``
                array of samples.
        """
        if self.is_capturing:
            logger.warning("Audio capture is already running")
            return

        pyaudio_instance = self._ensure_pyaudio_instance()
        pyaudio_module = self._ensure_module_available()

        try:
            # Open the input stream in blocking mode.
            self.stream = pyaudio_instance.open(
                format=pyaudio_module.paInt16,
                channels=self.channels,
                rate=self.sample_rate,
                input=True,
                input_device_index=device_index,
                frames_per_buffer=self.chunk_size,
                stream_callback=None,  # Use blocking mode.
            )

            self.is_capturing = True

            # Launch the capture loop in a dedicated thread.
            self.capture_thread = threading.Thread(
                target=self._capture_loop, args=(callback,), daemon=True
            )
            self.capture_thread.start()

            logger.info(f"Audio capture started (device_index={device_index})")

        except Exception as e:
            logger.error(f"Failed to start audio capture: {e}")
            raise

    def _capture_loop(self, callback: Optional[Callable[[np.ndarray], None]]):
        """Capture loop executed on the background thread."""
        logger.info("Audio capture loop started")

        while self.is_capturing:
            try:
                # Read raw audio data from the stream.
                audio_data = self.stream.read(self.chunk_size, exception_on_overflow=False)

                # Convert to a numpy array.
                audio_array = np.frombuffer(audio_data, dtype=np.int16)

                # Normalize to float32 samples in the [-1, 1] range.
                audio_float = audio_array.astype(np.float32) / 32768.0

                # Apply gain adjustment.
                audio_float = audio_float * self.gain

                # Limit the amplitude to [-1, 1].
                audio_float = np.clip(audio_float, -1.0, 1.0)

                # Push into the queue for downstream consumers.
                self.audio_queue.put(audio_float)

                # Invoke the optional callback.
                if callback:
                    callback(audio_float)

            except Exception as e:
                if self.is_capturing:
                    logger.error(f"Error in capture loop: {e}")

        logger.info("Audio capture loop stopped")

    def stop_capture(self):
        """Stop the capture loop and release stream resources."""
        if not self.is_capturing:
            logger.warning("Audio capture is not running")
            return

        logger.info("Stopping audio capture...")
        self.is_capturing = False

        # Wait for the capture thread to terminate.
        if self.capture_thread:
            self.capture_thread.join(timeout=2.0)

        # Stop and close the underlying PyAudio stream.
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
            self.stream = None

        # Flush remaining audio from the queue.
        while not self.audio_queue.empty():
            try:
                self.audio_queue.get_nowait()
            except queue.Empty:
                break

        logger.info("Audio capture stopped")

    def get_audio_chunk(self, timeout: float = 1.0) -> Optional[np.ndarray]:
        """Retrieve an audio chunk from the queue with an optional timeout."""
        try:
            return self.audio_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def set_gain(self, gain: float):
        """Update the gain factor applied to captured audio samples."""
        if gain < 0.0 or gain > 10.0:
            logger.warning(f"Gain value {gain} is out of range [0.0, 10.0]")
            gain = np.clip(gain, 0.0, 10.0)

        self.gain = gain
        logger.info(f"Gain set to {gain}")

    def get_volume_level(self) -> float:
        """Return the RMS volume estimate for the most recent chunk."""
        if self.audio_queue.empty():
            return 0.0

        try:
            # Fetch the most recent audio chunk without blocking.
            audio_chunk = self.audio_queue.get_nowait()

            # Compute the RMS value.
            rms = np.sqrt(np.mean(audio_chunk**2))

            # Return the chunk to the queue.
            self.audio_queue.put(audio_chunk)

            return float(rms)

        except queue.Empty:
            return 0.0

    def close(self):
        """Close the capture interface and release resources."""
        logger.info("Closing audio capture...")

        # Stop active capture if running.
        if self.is_capturing:
            self.stop_capture()

        # Terminate the PyAudio instance.
        if self.pyaudio:
            self.pyaudio.terminate()
            self.pyaudio = None

        logger.info("Audio capture closed")

    def __enter__(self):
        """Context manager entry hook."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit hook."""
        self.close()
