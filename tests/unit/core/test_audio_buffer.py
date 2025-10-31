# SPDX-License-Identifier: Apache-2.0
"""
Unit tests for AudioBuffer.

Tests audio buffering, sliding windows, and thread safety.
"""

import threading

import numpy as np
import pytest

from core.realtime.audio_buffer import AudioBuffer


class TestAudioBuffer:
    """Test suite for AudioBuffer class."""

    @pytest.fixture
    def buffer(self):
        """Create AudioBuffer instance with default settings."""
        return AudioBuffer(max_duration_seconds=2, sample_rate=16000)

    @pytest.fixture
    def sample_audio(self):
        """Create sample audio data."""
        return np.array([0.1, 0.2, 0.3, 0.4, 0.5], dtype=np.float32)

    # Initialization Tests
    def test_init_default_params(self):
        """Test AudioBuffer initialization with default parameters."""
        buffer = AudioBuffer()

        assert buffer.max_duration_seconds == 60  # DEFAULT_AUDIO_BUFFER_DURATION_SECONDS
        assert buffer.sample_rate == 16000  # DEFAULT_WHISPER_SAMPLE_RATE
        assert buffer.max_samples == 60 * 16000
        assert buffer.get_size() == 0

    def test_init_custom_params(self):
        """Test AudioBuffer initialization with custom parameters."""
        buffer = AudioBuffer(max_duration_seconds=5, sample_rate=44100)

        assert buffer.max_duration_seconds == 5
        assert buffer.sample_rate == 44100
        assert buffer.max_samples == 5 * 44100

    # Append Tests
    def test_append_audio_chunk(self, buffer, sample_audio):
        """Test appending audio chunk to buffer."""
        buffer.append(sample_audio)

        assert buffer.get_size() == len(sample_audio)
        assert not buffer.is_empty()

    def test_append_multiple_chunks(self, buffer):
        """Test appending multiple audio chunks."""
        chunk1 = np.array([0.1, 0.2], dtype=np.float32)
        chunk2 = np.array([0.3, 0.4], dtype=np.float32)

        buffer.append(chunk1)
        buffer.append(chunk2)

        assert buffer.get_size() == 4
        assert buffer.total_samples_added == 4

    def test_append_exceeds_max_size(self, buffer):
        """Test that buffer respects max size (circular buffer)."""
        # Fill buffer beyond max capacity
        large_chunk = np.ones(buffer.max_samples + 1000, dtype=np.float32)
        buffer.append(large_chunk)

        # Should only keep max_samples
        assert buffer.get_size() == buffer.max_samples
        assert buffer.is_full()

    def test_append_empty_chunk(self, buffer):
        """Test appending empty audio chunk."""
        empty_chunk = np.array([], dtype=np.float32)
        buffer.append(empty_chunk)

        assert buffer.get_size() == 0
        assert buffer.is_empty()

    # Get Window Tests
    def test_get_window_basic(self, buffer):
        """Test getting a basic audio window."""
        # Add 1 second of audio (16000 samples)
        audio = np.ones(16000, dtype=np.float32)
        buffer.append(audio)

        # Get 0.5 second window
        window = buffer.get_window(duration_seconds=0.5)

        assert len(window) == 8000  # 0.5 * 16000
        assert window.dtype == np.float32

    def test_get_window_with_offset(self, buffer):
        """Test getting audio window with offset."""
        # Add 2 seconds of audio
        audio = np.arange(32000, dtype=np.float32)
        buffer.append(audio)

        # Get 0.5 second window with 0.5 second offset
        window = buffer.get_window(duration_seconds=0.5, offset_seconds=0.5)

        assert len(window) == 8000

    def test_get_window_empty_buffer(self, buffer):
        """Test getting window from empty buffer."""
        window = buffer.get_window(duration_seconds=1.0)

        assert len(window) == 0
        assert window.dtype == np.float32

    def test_get_window_exceeds_buffer_size(self, buffer):
        """Test getting window larger than buffer content."""
        # Add 0.5 second of audio
        audio = np.ones(8000, dtype=np.float32)
        buffer.append(audio)

        # Request 2 seconds (more than available)
        window = buffer.get_window(duration_seconds=2.0)

        # Should return all available data
        assert len(window) == 8000

    def test_get_latest(self, buffer):
        """Test getting latest audio data."""
        audio = np.arange(16000, dtype=np.float32)
        buffer.append(audio)

        latest = buffer.get_latest(duration_seconds=0.5)

        assert len(latest) == 8000
        # Should be the last 8000 samples
        np.testing.assert_array_equal(latest, audio[-8000:])

    def test_get_all(self, buffer, sample_audio):
        """Test getting all audio data."""
        buffer.append(sample_audio)

        all_data = buffer.get_all()

        assert len(all_data) == len(sample_audio)
        np.testing.assert_array_almost_equal(all_data, sample_audio)

    def test_get_all_empty_buffer(self, buffer):
        """Test getting all data from empty buffer."""
        all_data = buffer.get_all()

        assert len(all_data) == 0
        assert all_data.dtype == np.float32

    # Sliding Windows Tests
    def test_get_sliding_windows_basic(self, buffer):
        """Test getting sliding windows."""
        # Add 2 seconds of audio
        audio = np.arange(32000, dtype=np.float32)
        buffer.append(audio)

        # Get 0.5 second windows with 0.25 second overlap
        windows = buffer.get_sliding_windows(window_duration_seconds=0.5, overlap_seconds=0.25)

        # Should have multiple windows
        assert len(windows) > 0
        # Each window should be 0.5 seconds
        assert all(len(w) == 8000 for w in windows)

    def test_get_sliding_windows_no_overlap(self, buffer):
        """Test sliding windows with no overlap."""
        audio = np.arange(32000, dtype=np.float32)
        buffer.append(audio)

        windows = buffer.get_sliding_windows(window_duration_seconds=0.5, overlap_seconds=0.0)

        # With 2 seconds of audio and 0.5 second windows, should have 4 windows
        assert len(windows) == 4

    def test_get_sliding_windows_empty_buffer(self, buffer):
        """Test sliding windows on empty buffer."""
        windows = buffer.get_sliding_windows(window_duration_seconds=0.5)

        assert len(windows) == 0

    def test_get_sliding_windows_invalid_params(self, buffer):
        """Test sliding windows with invalid parameters."""
        audio = np.ones(16000, dtype=np.float32)
        buffer.append(audio)

        # Invalid window duration
        windows = buffer.get_sliding_windows(window_duration_seconds=0.0)
        assert len(windows) == 0

        # Overlap >= window duration
        windows = buffer.get_sliding_windows(window_duration_seconds=0.5, overlap_seconds=0.6)
        assert len(windows) == 0

    # Clear Tests
    def test_clear(self, buffer, sample_audio):
        """Test clearing the buffer."""
        buffer.append(sample_audio)
        assert not buffer.is_empty()

        buffer.clear()

        assert buffer.is_empty()
        assert buffer.get_size() == 0
        assert buffer.total_samples_added == 0

    # Status Query Tests
    def test_get_duration(self, buffer):
        """Test getting buffer duration."""
        # Add 1 second of audio
        audio = np.ones(16000, dtype=np.float32)
        buffer.append(audio)

        duration = buffer.get_duration()

        assert duration == pytest.approx(1.0, rel=0.01)

    def test_get_size(self, buffer, sample_audio):
        """Test getting buffer size."""
        buffer.append(sample_audio)

        size = buffer.get_size()

        assert size == len(sample_audio)

    def test_is_empty(self, buffer, sample_audio):
        """Test checking if buffer is empty."""
        assert buffer.is_empty()

        buffer.append(sample_audio)
        assert not buffer.is_empty()

        buffer.clear()
        assert buffer.is_empty()

    def test_is_full(self, buffer):
        """Test checking if buffer is full."""
        assert not buffer.is_full()

        # Fill to capacity
        audio = np.ones(buffer.max_samples, dtype=np.float32)
        buffer.append(audio)

        assert buffer.is_full()

    def test_get_memory_usage(self, buffer):
        """Test getting memory usage."""
        # Add 1000 samples
        audio = np.ones(1000, dtype=np.float32)
        buffer.append(audio)

        memory = buffer.get_memory_usage()

        # Each float32 sample is 4 bytes
        assert memory == 1000 * 4

    def test_get_stats(self, buffer):
        """Test getting buffer statistics."""
        audio = np.ones(8000, dtype=np.float32)
        buffer.append(audio)

        stats = buffer.get_stats()

        assert stats["current_samples"] == 8000
        assert stats["max_samples"] == buffer.max_samples
        assert stats["current_duration_seconds"] == pytest.approx(0.5, rel=0.01)
        assert stats["max_duration_seconds"] == 2
        assert stats["total_samples_added"] == 8000
        assert stats["memory_usage_bytes"] == 8000 * 4
        assert "is_full" in stats
        assert "fill_percentage" in stats

    # Thread Safety Tests
    def test_thread_safety_append(self, buffer):
        """Test thread-safe append operations."""
        num_threads = 10
        samples_per_thread = 1000

        def append_audio():
            audio = np.ones(samples_per_thread, dtype=np.float32)
            buffer.append(audio)

        threads = [threading.Thread(target=append_audio) for _ in range(num_threads)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should have all samples (or max_samples if exceeded)
        expected = min(num_threads * samples_per_thread, buffer.max_samples)
        assert buffer.get_size() == expected

    def test_thread_safety_read_write(self, buffer):
        """Test concurrent read and write operations."""
        results = []

        def writer():
            for _ in range(100):
                audio = np.ones(100, dtype=np.float32)
                buffer.append(audio)

        def reader():
            for _ in range(100):
                data = buffer.get_all()
                results.append(len(data))

        write_thread = threading.Thread(target=writer)
        read_thread = threading.Thread(target=reader)

        write_thread.start()
        read_thread.start()

        write_thread.join()
        read_thread.join()

        # Should not crash and should have some results
        assert len(results) == 100

    # Edge Cases
    def test_append_different_dtypes(self, buffer):
        """Test appending audio with different dtypes."""
        # int16 audio
        audio_int16 = np.array([100, 200, 300], dtype=np.int16)
        buffer.append(audio_int16)

        # Should convert to float32
        data = buffer.get_all()
        assert data.dtype == np.float32

    def test_large_audio_chunk(self, buffer):
        """Test appending very large audio chunk."""
        # Create chunk larger than buffer capacity
        large_chunk = np.ones(buffer.max_samples * 2, dtype=np.float32)
        buffer.append(large_chunk)

        # Should only keep max_samples (circular buffer behavior)
        assert buffer.get_size() == buffer.max_samples

    def test_get_window_boundary_conditions(self, buffer):
        """Test window retrieval at boundaries."""
        audio = np.arange(16000, dtype=np.float32)
        buffer.append(audio)

        # Window at the very end
        window = buffer.get_window(duration_seconds=0.1, offset_seconds=0.0)
        assert len(window) > 0

        # Window with large offset (beyond buffer)
        window = buffer.get_window(duration_seconds=0.1, offset_seconds=10.0)
        assert len(window) == 0

    def test_circular_buffer_behavior(self, buffer):
        """Test that buffer behaves as circular buffer."""
        # Fill buffer
        first_chunk = np.ones(buffer.max_samples, dtype=np.float32)
        buffer.append(first_chunk)

        # Add more data (should overwrite oldest)
        second_chunk = np.ones(1000, dtype=np.float32) * 2
        buffer.append(second_chunk)

        # Size should still be max_samples
        assert buffer.get_size() == buffer.max_samples

        # Latest data should be from second chunk
        latest = buffer.get_latest(duration_seconds=0.01)
        assert np.all(latest == 2.0)

    def test_zero_duration_window(self, buffer, sample_audio):
        """Test getting window with zero duration."""
        buffer.append(sample_audio)

        window = buffer.get_window(duration_seconds=0.0)

        # Should return empty array
        assert len(window) == 0
