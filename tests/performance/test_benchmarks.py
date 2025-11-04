# SPDX-License-Identifier: Apache-2.0
"""
Performance benchmark tests.

Establishes baseline performance metrics for regression testing.
These tests measure actual performance and can be used for CI/CD integration.
"""

import asyncio
import logging
import tempfile
import time
from pathlib import Path
from unittest.mock import Mock

import numpy as np
import pytest
import soundfile as sf

logger = logging.getLogger(__name__)


class PerformanceBenchmark:
    """Track and report performance benchmarks."""

    def __init__(self):
        self.results = {}

    def record(self, name: str, value: float, unit: str = "ms"):
        """Record a benchmark result."""
        self.results[name] = {"value": value, "unit": unit}
        logger.info(f"📊 {name}: {value:.2f} {unit}")

    def report(self):
        """Generate benchmark report."""
        logger.info("=" * 60)
        logger.info("Performance Benchmark Report")
        logger.info("=" * 60)
        for name, data in sorted(self.results.items()):
            logger.info(f"  {name}: {data['value']:.2f} {data['unit']}")
        logger.info("=" * 60)


@pytest.fixture
def benchmark():
    """Provide benchmark tracker."""
    bench = PerformanceBenchmark()
    yield bench
    bench.report()


@pytest.fixture
def test_audio_10s():
    """Create 10-second test audio file."""
    sample_rate = 16000
    duration = 10.0
    samples = int(sample_rate * duration)
    audio_data = np.random.randn(samples).astype(np.float32) * 0.1

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        temp_path = f.name

    sf.write(temp_path, audio_data, sample_rate)
    yield temp_path

    try:
        Path(temp_path).unlink()
    except Exception:
        pass


def test_benchmark_database_operations(benchmark):
    """Benchmark database operations."""
    from data.database.connection import DatabaseConnection

    db = DatabaseConnection(":memory:")
    db.initialize_schema()

    # Benchmark: Create connection
    start = time.time()
    conn = db._get_connection()
    benchmark.record("db_connection_create", (time.time() - start) * 1000)

    # Benchmark: Simple query
    start = time.time()
    db.execute("SELECT 1")
    benchmark.record("db_simple_query", (time.time() - start) * 1000)

    # Benchmark: Insert operation
    start = time.time()
    db.execute(
        "INSERT INTO transcription_tasks (id, file_path, file_name, file_size, status, engine) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ("test-id", "/tmp/test.wav", "test.wav", 1024, "pending", "faster-whisper"),
        commit=True,
    )
    benchmark.record("db_insert", (time.time() - start) * 1000)

    # Benchmark: Select operation
    start = time.time()
    db.execute("SELECT * FROM transcription_tasks WHERE id = ?", ("test-id",))
    benchmark.record("db_select", (time.time() - start) * 1000)

    # Benchmark: Update operation
    start = time.time()
    db.execute(
        "UPDATE transcription_tasks SET status = ? WHERE id = ?",
        ("completed", "test-id"),
        commit=True,
    )
    benchmark.record("db_update", (time.time() - start) * 1000)

    # Benchmark: Delete operation
    start = time.time()
    db.execute("DELETE FROM transcription_tasks WHERE id = ?", ("test-id",), commit=True)
    benchmark.record("db_delete", (time.time() - start) * 1000)

    db.close_all()


def test_benchmark_audio_processing(benchmark, test_audio_10s):
    """Benchmark audio processing operations."""
    # Benchmark: Audio file reading
    start = time.time()
    data, rate = sf.read(test_audio_10s)
    read_time = (time.time() - start) * 1000
    benchmark.record("audio_read_10s", read_time)

    # Benchmark: Audio info reading
    start = time.time()
    info = sf.info(test_audio_10s)
    benchmark.record("audio_info", (time.time() - start) * 1000)

    # Benchmark: Sample rate conversion (48kHz -> 16kHz)
    from engines.speech.base import ensure_audio_sample_rate

    audio_48k = np.random.randn(48000).astype(np.float32)
    start = time.time()
    resampled, _ = ensure_audio_sample_rate(audio_48k, 48000, 16000)
    benchmark.record("resample_48k_to_16k", (time.time() - start) * 1000)

    # Benchmark: Sample rate conversion (44.1kHz -> 16kHz)
    audio_44k = np.random.randn(44100).astype(np.float32)
    start = time.time()
    resampled, _ = ensure_audio_sample_rate(audio_44k, 44100, 16000)
    benchmark.record("resample_44k_to_16k", (time.time() - start) * 1000)


def test_benchmark_encryption(benchmark):
    """Benchmark encryption operations."""
    from data.security.encryption import SecurityManager

    security = SecurityManager()

    # Benchmark: Password hashing
    start = time.time()
    security.hash_password("test_password_123")
    benchmark.record("password_hash", (time.time() - start) * 1000)

    # Benchmark: Password verification
    hashed = security.hash_password("test_password_123")
    start = time.time()
    security.verify_password("test_password_123", hashed)
    benchmark.record("password_verify", (time.time() - start) * 1000)

    # Benchmark: Dictionary encryption (small)
    data_dict = {"key": "value", "number": 42}
    start = time.time()
    encrypted = security.encrypt_dict(data_dict)
    benchmark.record("encrypt_dict_small", (time.time() - start) * 1000)

    # Benchmark: Dictionary decryption (small)
    start = time.time()
    security.decrypt_dict(encrypted)
    benchmark.record("decrypt_dict_small", (time.time() - start) * 1000)

    # Benchmark: Dictionary encryption (large)
    data_dict_large = {f"key_{i}": f"value_{i}" for i in range(100)}
    start = time.time()
    encrypted = security.encrypt_dict(data_dict_large)
    benchmark.record("encrypt_dict_large", (time.time() - start) * 1000)

    # Benchmark: Dictionary decryption (large)
    start = time.time()
    security.decrypt_dict(encrypted)
    benchmark.record("decrypt_dict_large", (time.time() - start) * 1000)


def test_benchmark_file_operations(benchmark):
    """Benchmark file operations."""
    from data.storage.file_manager import FileManager

    with tempfile.TemporaryDirectory() as tmpdir:
        file_manager = FileManager(tmpdir)

        # Benchmark: Save file (1KB)
        data_1kb = b"x" * 1024
        start = time.time()
        path_1kb = file_manager.save_file(data_1kb, "test_1kb.txt")
        benchmark.record("file_save_1kb", (time.time() - start) * 1000)

        # Benchmark: Read file (1KB)
        start = time.time()
        file_manager.read_file(path_1kb)
        benchmark.record("file_read_1kb", (time.time() - start) * 1000)

        # Benchmark: Save file (1MB)
        data_1mb = b"x" * (1024 * 1024)
        start = time.time()
        path_1mb = file_manager.save_file(data_1mb, "test_1mb.txt")
        benchmark.record("file_save_1mb", (time.time() - start) * 1000)

        # Benchmark: Read file (1MB)
        start = time.time()
        file_manager.read_file(path_1mb)
        benchmark.record("file_read_1mb", (time.time() - start) * 1000)

        # Benchmark: Delete file
        start = time.time()
        file_manager.delete_file(path_1kb)
        benchmark.record("file_delete", (time.time() - start) * 1000)


@pytest.mark.asyncio
async def test_benchmark_async_operations(benchmark):
    """Benchmark async operations."""

    # Benchmark: Async task creation
    async def dummy_task():
        await asyncio.sleep(0.001)

    start = time.time()
    tasks = [asyncio.create_task(dummy_task()) for _ in range(100)]
    await asyncio.gather(*tasks)
    benchmark.record("async_100_tasks", (time.time() - start) * 1000)

    # Benchmark: Queue operations
    queue = asyncio.Queue()

    start = time.time()
    for i in range(1000):
        await queue.put(i)
    benchmark.record("queue_put_1000", (time.time() - start) * 1000)

    start = time.time()
    for i in range(1000):
        await queue.get()
    benchmark.record("queue_get_1000", (time.time() - start) * 1000)


def test_benchmark_model_operations(benchmark):
    """Benchmark model operations."""
    from data.database.models import CalendarEvent, TranscriptionTask

    # Benchmark: TranscriptionTask creation
    start = time.time()
    for i in range(100):
        task = TranscriptionTask(
            file_path=f"/tmp/test_{i}.wav",
            file_name=f"test_{i}.wav",
            file_size=1024 * 1024,
            status="pending",
        )
    benchmark.record("model_create_100_tasks", (time.time() - start) * 1000)

    # Benchmark: CalendarEvent creation
    start = time.time()
    for i in range(100):
        event = CalendarEvent(
            title=f"Event {i}", start_time="2025-01-01T10:00:00", end_time="2025-01-01T11:00:00"
        )
    benchmark.record("model_create_100_events", (time.time() - start) * 1000)


def test_benchmark_json_operations(benchmark):
    """Benchmark JSON operations."""
    import json

    # Create test data
    small_data = {"key": "value", "number": 42, "list": [1, 2, 3]}
    large_data = {f"key_{i}": f"value_{i}" for i in range(1000)}

    # Benchmark: JSON encode (small)
    start = time.time()
    for _ in range(1000):
        json.dumps(small_data)
    benchmark.record("json_encode_small_1000x", (time.time() - start) * 1000)

    # Benchmark: JSON decode (small)
    json_str = json.dumps(small_data)
    start = time.time()
    for _ in range(1000):
        json.loads(json_str)
    benchmark.record("json_decode_small_1000x", (time.time() - start) * 1000)

    # Benchmark: JSON encode (large)
    start = time.time()
    for _ in range(100):
        json.dumps(large_data)
    benchmark.record("json_encode_large_100x", (time.time() - start) * 1000)

    # Benchmark: JSON decode (large)
    json_str = json.dumps(large_data)
    start = time.time()
    for _ in range(100):
        json.loads(json_str)
    benchmark.record("json_decode_large_100x", (time.time() - start) * 1000)


def test_benchmark_numpy_operations(benchmark):
    """Benchmark numpy operations."""
    # Benchmark: Array creation
    start = time.time()
    for _ in range(1000):
        np.zeros(1000, dtype=np.float32)
    benchmark.record("numpy_zeros_1000x", (time.time() - start) * 1000)

    # Benchmark: Array operations
    arr1 = np.random.randn(10000).astype(np.float32)
    arr2 = np.random.randn(10000).astype(np.float32)

    start = time.time()
    for _ in range(1000):
        result = arr1 + arr2
    benchmark.record("numpy_add_1000x", (time.time() - start) * 1000)

    start = time.time()
    for _ in range(1000):
        result = arr1 * arr2
    benchmark.record("numpy_multiply_1000x", (time.time() - start) * 1000)

    # Benchmark: Statistical operations
    start = time.time()
    for _ in range(1000):
        mean = np.mean(arr1)
    benchmark.record("numpy_mean_1000x", (time.time() - start) * 1000)

    start = time.time()
    for _ in range(1000):
        std = np.std(arr1)
    benchmark.record("numpy_std_1000x", (time.time() - start) * 1000)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
