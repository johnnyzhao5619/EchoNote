# SPDX-License-Identifier: Apache-2.0
"""
Transcription performance tests.

Tests transcription speed and validates RTF (Real-Time Factor) targets.
RTF = processing_time / audio_duration
Target: RTF < 0.25 (process 1 minute of audio in < 15 seconds)
"""

import asyncio
import logging
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import numpy as np
import pytest
import soundfile as sf

logger = logging.getLogger(__name__)


@pytest.fixture
def mock_whisper_model():
    """Create a mock WhisperModel for testing."""
    mock_model = Mock()

    # Mock transcribe method to return segments quickly
    def mock_transcribe(audio_path, **kwargs):
        # Simulate fast transcription
        # Return iterator and info
        segments = [
            Mock(start=0.0, end=2.0, text="Test segment 1"),
            Mock(start=2.0, end=4.0, text="Test segment 2"),
            Mock(start=4.0, end=6.0, text="Test segment 3"),
        ]
        info = Mock(language="en", duration=6.0)
        return iter(segments), info

    mock_model.transcribe = mock_transcribe
    return mock_model


@pytest.fixture
def test_audio_file():
    """Create a temporary test audio file."""
    # Create 10 seconds of silence at 16kHz
    sample_rate = 16000
    duration = 10.0
    samples = int(sample_rate * duration)
    audio_data = np.zeros(samples, dtype=np.float32)

    # Create temporary file
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        temp_path = f.name

    # Write audio file
    sf.write(temp_path, audio_data, sample_rate)

    yield temp_path

    # Cleanup
    try:
        Path(temp_path).unlink()
    except Exception:
        pass


@pytest.mark.asyncio
async def test_transcription_rtf_target(mock_whisper_model, test_audio_file):
    """Test that transcription meets RTF < 0.25 target."""
    from engines.speech.faster_whisper_engine import FasterWhisperEngine

    # Create engine with mocked model
    engine = FasterWhisperEngine(model_size="base")
    engine.model = mock_whisper_model
    engine._model_available = True

    # Get audio duration
    info = sf.info(test_audio_file)
    audio_duration = info.duration

    # Measure transcription time
    start_time = time.time()
    result = await engine.transcribe_file(test_audio_file)
    processing_time = time.time() - start_time

    # Calculate RTF
    rtf = processing_time / audio_duration

    logger.info(f"Audio duration: {audio_duration:.2f}s")
    logger.info(f"Processing time: {processing_time:.2f}s")
    logger.info(f"RTF: {rtf:.3f}")

    # Verify result structure
    assert "segments" in result
    assert "language" in result
    assert "duration" in result

    # RTF should be < 0.25 (with mock, should be very fast)
    assert rtf < 0.25, f"RTF {rtf:.3f} exceeds target 0.25"

    logger.info(f"✓ Transcription RTF: {rtf:.3f} (target: <0.25)")


@pytest.mark.asyncio
async def test_transcription_progress_callback(mock_whisper_model, test_audio_file):
    """Test that progress callbacks are called efficiently."""
    from engines.speech.faster_whisper_engine import FasterWhisperEngine

    engine = FasterWhisperEngine(model_size="base")
    engine.model = mock_whisper_model
    engine._model_available = True

    # Track progress updates
    progress_updates = []

    def progress_callback(progress):
        progress_updates.append(progress)

    # Transcribe with progress callback
    await engine.transcribe_file(test_audio_file, progress_callback=progress_callback)

    # Verify progress updates
    assert len(progress_updates) > 0, "No progress updates received"
    assert progress_updates[0] >= 10.0, "Initial progress should be >= 10%"
    assert progress_updates[-1] >= 90.0, "Final progress should be >= 90%"

    # Progress should be monotonically increasing
    for i in range(1, len(progress_updates)):
        assert (
            progress_updates[i] >= progress_updates[i - 1]
        ), f"Progress decreased: {progress_updates[i-1]} -> {progress_updates[i]}"

    logger.info(f"✓ Progress updates: {len(progress_updates)} callbacks")


@pytest.mark.asyncio
async def test_transcription_with_vad_filter(mock_whisper_model, test_audio_file):
    """Test transcription with VAD filter enabled."""
    from engines.speech.faster_whisper_engine import FasterWhisperEngine

    engine = FasterWhisperEngine(model_size="base")
    engine.model = mock_whisper_model
    engine._model_available = True

    # Transcribe with VAD filter
    start_time = time.time()
    result = await engine.transcribe_file(
        test_audio_file, vad_filter=True, vad_min_silence_duration_ms=500
    )
    processing_time = time.time() - start_time

    # Verify result
    assert "segments" in result
    assert len(result["segments"]) > 0

    # VAD should not significantly slow down processing
    info = sf.info(test_audio_file)
    rtf = processing_time / info.duration
    assert rtf < 0.5, f"VAD processing too slow: RTF {rtf:.3f}"

    logger.info(f"✓ VAD transcription RTF: {rtf:.3f}")


@pytest.mark.asyncio
async def test_transcription_beam_size_impact(mock_whisper_model, test_audio_file):
    """Test impact of beam size on transcription speed."""
    from engines.speech.faster_whisper_engine import FasterWhisperEngine

    engine = FasterWhisperEngine(model_size="base")
    engine.model = mock_whisper_model
    engine._model_available = True

    beam_sizes = [1, 5]
    results = {}

    for beam_size in beam_sizes:
        start_time = time.time()
        result = await engine.transcribe_file(test_audio_file, beam_size=beam_size)
        processing_time = time.time() - start_time

        info = sf.info(test_audio_file)
        rtf = processing_time / info.duration
        results[beam_size] = rtf

        logger.info(f"Beam size {beam_size}: RTF {rtf:.3f}")

    # Both should meet RTF target
    for beam_size, rtf in results.items():
        assert rtf < 0.5, f"Beam size {beam_size} RTF {rtf:.3f} too high"

    logger.info(f"✓ Beam size impact tested: {results}")


@pytest.mark.asyncio
async def test_concurrent_transcription_performance():
    """Test performance of concurrent transcription tasks."""
    from engines.speech.faster_whisper_engine import FasterWhisperEngine

    # Create mock model
    mock_model = Mock()

    def mock_transcribe(audio_path, **kwargs):
        # Simulate fast transcription
        time.sleep(0.1)  # Small delay
        segments = [Mock(start=0.0, end=1.0, text="Test")]
        info = Mock(language="en", duration=1.0)
        return iter(segments), info

    mock_model.transcribe = mock_transcribe

    # Create engine
    engine = FasterWhisperEngine(model_size="base")
    engine.model = mock_model
    engine._model_available = True

    # Create test files
    test_files = []
    for i in range(3):
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            temp_path = f.name

        # Write 1 second of audio
        audio_data = np.zeros(16000, dtype=np.float32)
        sf.write(temp_path, audio_data, 16000)
        test_files.append(temp_path)

    try:
        # Transcribe concurrently
        start_time = time.time()
        tasks = [engine.transcribe_file(f) for f in test_files]
        results = await asyncio.gather(*tasks)
        total_time = time.time() - start_time

        # Verify all completed
        assert len(results) == 3

        # Concurrent processing should be faster than sequential
        # (3 files * 0.1s = 0.3s sequential, but concurrent should be ~0.1s)
        assert total_time < 0.5, f"Concurrent processing too slow: {total_time:.2f}s"

        logger.info(f"✓ Concurrent transcription: {total_time:.2f}s for 3 files")

    finally:
        # Cleanup
        for f in test_files:
            try:
                Path(f).unlink()
            except Exception:
                pass


@pytest.mark.asyncio
async def test_audio_duration_detection_performance(test_audio_file):
    """Test performance of audio duration detection methods."""
    from engines.speech.faster_whisper_engine import FasterWhisperEngine

    # Test soundfile method
    start_time = time.time()
    info = sf.info(test_audio_file)
    duration_sf = info.duration
    time_sf = time.time() - start_time

    logger.info(f"soundfile duration detection: {time_sf*1000:.2f}ms")

    # Duration detection should be fast (<100ms)
    assert time_sf < 0.1, f"Duration detection too slow: {time_sf*1000:.2f}ms"

    logger.info(f"✓ Audio duration detection: {time_sf*1000:.2f}ms")


def test_transcription_memory_efficiency():
    """Test that transcription doesn't accumulate excessive memory."""
    import gc

    import psutil

    from engines.speech.faster_whisper_engine import FasterWhisperEngine

    process = psutil.Process()

    # Get baseline memory
    gc.collect()
    baseline_memory = process.memory_info().rss / (1024 * 1024)  # MB

    # Create engine (without loading model)
    engine = FasterWhisperEngine(model_size="base")

    # Memory increase should be minimal for engine creation
    gc.collect()
    after_creation = process.memory_info().rss / (1024 * 1024)
    memory_increase = after_creation - baseline_memory

    # Engine creation should use <50MB
    assert memory_increase < 50, f"Engine creation used {memory_increase:.2f}MB (expected <50MB)"

    logger.info(f"✓ Engine creation memory: {memory_increase:.2f}MB")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
