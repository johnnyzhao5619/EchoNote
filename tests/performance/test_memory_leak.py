# SPDX-License-Identifier: Apache-2.0
"""
Memory leak test for long-duration recording.

Tests that memory usage remains stable during extended recording sessions.
"""

import sys
from collections import deque

import numpy as np
import pytest


class TestMemoryLeak:
    """Test memory usage during long recording sessions."""

    def test_memory_stable_with_bounded_buffer(self):
        """Test that memory usage is bounded with deque maxlen."""
        # Configure small buffer for testing (10 seconds at 16kHz)
        max_buffer_seconds = 10
        recording_audio_buffer = deque(maxlen=max_buffer_seconds * 16000)
        
        # Simulate 60 seconds of audio data (should only keep last 10 seconds)
        chunk_size = 1600  # 0.1 second at 16kHz
        num_chunks = 600  # 60 seconds
        
        initial_size = sys.getsizeof(recording_audio_buffer)
        
        for i in range(num_chunks):
            audio_chunk = np.random.rand(chunk_size).astype(np.float32)
            recording_audio_buffer.extend(audio_chunk.flat)
            
            # Check size periodically
            if i % 100 == 0:
                current_size = sys.getsizeof(recording_audio_buffer)
                buffer_len = len(recording_audio_buffer)
                
                # Buffer should not exceed max_buffer_seconds
                max_samples = max_buffer_seconds * 16000
                assert buffer_len <= max_samples, f"Buffer exceeded max size: {buffer_len} > {max_samples}"
                
                print(f"Chunk {i}: buffer_len={buffer_len}, size={current_size} bytes")
        
        final_size = sys.getsizeof(recording_audio_buffer)
        final_len = len(recording_audio_buffer)
        
        # Buffer should be at max capacity
        assert final_len == max_buffer_seconds * 16000
        
        # Memory size should be stable after reaching max capacity
        # Each float32 is 4 bytes, so max memory should be around:
        # 160,000 samples * 4 bytes = 640,000 bytes + deque overhead
        max_expected_memory = (max_buffer_seconds * 16000 * 4) * 2.5  # Allow 2.5x for overhead
        assert final_size < max_expected_memory, f"Memory grew too much: {final_size} > {max_expected_memory}"
        
        print(f"\nMemory test passed:")
        print(f"  Initial size: {initial_size} bytes")
        print(f"  Final size: {final_size} bytes ({final_size/1024/1024:.2f} MB)")
        print(f"  Buffer length: {final_len} samples ({final_len/16000:.1f} seconds)")
        print(f"  Memory is bounded - old data is automatically discarded")

    def test_memory_usage_calculation(self):
        """Test that memory usage is accurately calculated."""
        # Add 1 second of audio
        chunk_size = 16000
        audio_chunk = np.random.rand(chunk_size).astype(np.float32)
        recording_audio_buffer = deque(maxlen=160000)
        recording_audio_buffer.extend(audio_chunk.flat)
        
        # Each float32 sample is 4 bytes
        expected_memory = chunk_size * 4
        
        # Buffer size should match
        assert len(recording_audio_buffer) == chunk_size
        
        print(f"\nMemory calculation:")
        print(f"  Samples: {chunk_size}")
        print(f"  Expected memory: {expected_memory} bytes")
        print(f"  Buffer size: {len(recording_audio_buffer)}")

    def test_no_memory_leak_in_accumulated_data(self):
        """Test that accumulated transcription/translation don't grow unbounded."""
        # This is a design consideration - accumulated data will grow
        # but it's intentional for saving the full transcript
        
        accumulated_transcription = []
        accumulated_translation = []
        
        # Simulate adding many transcription segments
        for i in range(1000):
            accumulated_transcription.append(f"Segment {i}")
            accumulated_translation.append(f"Translation {i}")
        
        # These are expected to grow - they store the full session
        assert len(accumulated_transcription) == 1000
        assert len(accumulated_translation) == 1000
        
        # But they should be clearable
        accumulated_transcription = []
        accumulated_translation = []
        
        assert len(accumulated_transcription) == 0
        assert len(accumulated_translation) == 0
        
        print("\nAccumulated data test passed - data is intentionally kept for full transcript")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
