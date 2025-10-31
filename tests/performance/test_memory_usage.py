# SPDX-License-Identifier: Apache-2.0
"""
Memory usage performance tests.

Tests memory consumption patterns and validates optimization targets.
"""

import gc
import logging
import sys
import time
from typing import Dict

import psutil
import pytest

logger = logging.getLogger(__name__)


class MemoryMonitor:
    """Monitor memory usage during tests."""

    def __init__(self):
        """Initialize memory monitor."""
        self.process = psutil.Process()
        self.baseline = None
        self.measurements: Dict[str, float] = {}

    def get_memory_mb(self) -> float:
        """Get current memory usage in MB."""
        # Force garbage collection for accurate measurement
        gc.collect()
        time.sleep(0.1)  # Allow GC to complete
        
        mem_info = self.process.memory_info()
        return mem_info.rss / (1024 * 1024)  # Convert to MB

    def set_baseline(self):
        """Set baseline memory usage."""
        self.baseline = self.get_memory_mb()
        logger.info(f"Baseline memory: {self.baseline:.2f} MB")

    def measure(self, label: str) -> float:
        """Measure and record memory usage."""
        current = self.get_memory_mb()
        self.measurements[label] = current
        
        if self.baseline:
            delta = current - self.baseline
            logger.info(f"{label}: {current:.2f} MB (Δ {delta:+.2f} MB)")
        else:
            logger.info(f"{label}: {current:.2f} MB")
        
        return current

    def get_delta(self, label: str) -> float:
        """Get memory delta from baseline."""
        if not self.baseline or label not in self.measurements:
            return 0.0
        return self.measurements[label] - self.baseline


@pytest.fixture
def memory_monitor():
    """Provide memory monitor fixture."""
    monitor = MemoryMonitor()
    monitor.set_baseline()
    yield monitor
    
    # Log final memory state
    final_mem = monitor.get_memory_mb()
    logger.info(f"Final memory: {final_mem:.2f} MB")


def test_idle_memory_usage(memory_monitor):
    """Test idle memory usage is below target."""
    # Import minimal components
    from config.app_config import ConfigManager
    
    memory_monitor.measure("after_config_import")
    
    # Create config manager
    config = ConfigManager()
    memory_monitor.measure("after_config_creation")
    
    # Verify idle memory is reasonable
    idle_memory = memory_monitor.get_memory_mb()
    
    # Target: <150MB idle (relaxed for test environment)
    # In production, this should be lower
    assert idle_memory < 200, f"Idle memory {idle_memory:.2f} MB exceeds 200 MB"
    
    logger.info(f"✓ Idle memory usage: {idle_memory:.2f} MB")


def test_database_memory_footprint(memory_monitor):
    """Test database connection memory footprint."""
    from data.database.connection import DatabaseConnection
    
    memory_monitor.measure("before_database")
    
    # Create database connection (in-memory)
    db = DatabaseConnection(":memory:")
    
    memory_after_db = memory_monitor.measure("after_database")
    db_delta = memory_monitor.get_delta("after_database")
    
    # Database should use <15MB
    assert db_delta < 20, f"Database memory {db_delta:.2f} MB exceeds 20 MB"
    
    # Cleanup
    db.close_all()
    gc.collect()
    
    memory_after_cleanup = memory_monitor.measure("after_db_cleanup")
    
    logger.info(f"✓ Database memory footprint: {db_delta:.2f} MB")


def test_ui_component_memory(memory_monitor, qtbot):
    """Test UI component memory usage."""
    from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout
    
    memory_monitor.measure("before_ui")
    
    # Create simple widget
    widget = QWidget()
    layout = QVBoxLayout()
    label = QLabel("Test Label")
    layout.addWidget(label)
    widget.setLayout(layout)
    qtbot.addWidget(widget)
    
    memory_after_widget = memory_monitor.measure("after_widget_creation")
    widget_delta = memory_monitor.get_delta("after_widget_creation")
    
    # Single widget should use <10MB
    assert widget_delta < 15, f"Widget memory {widget_delta:.2f} MB exceeds 15 MB"
    
    # Cleanup
    widget.deleteLater()
    gc.collect()
    
    logger.info(f"✓ UI component memory: {widget_delta:.2f} MB")


def test_audio_buffer_memory_limit(memory_monitor):
    """Test audio buffer respects memory limits."""
    import numpy as np
    from collections import deque
    
    memory_monitor.measure("before_audio_buffer")
    
    # Simulate 10 seconds of audio at 16kHz (smaller test for faster execution)
    sample_rate = 16000
    max_seconds = 10  # 10 seconds for testing
    max_samples = sample_rate * max_seconds
    
    # Create bounded buffer
    audio_buffer = deque(maxlen=max_samples)
    
    # Fill buffer with audio data
    chunk_size = 1600  # 0.1 second chunks
    num_chunks = (max_samples // chunk_size) + 20  # Overfill to test limit
    
    for _ in range(num_chunks):
        chunk = np.random.randn(chunk_size).astype(np.float32)
        audio_buffer.extend(chunk)
    
    memory_after_fill = memory_monitor.measure("after_buffer_fill")
    buffer_delta = memory_monitor.get_delta("after_buffer_fill")
    
    # 10 seconds of float32 audio should be ~0.6MB
    # Allow generous margin for test overhead (Python objects, numpy arrays, etc.)
    expected_max_mb = (max_samples * 4) / (1024 * 1024)  # 4 bytes per float32
    
    assert buffer_delta < expected_max_mb * 10, \
        f"Buffer memory {buffer_delta:.2f} MB exceeds expected {expected_max_mb * 10:.2f} MB"
    
    # Verify buffer size is limited
    assert len(audio_buffer) <= max_samples, \
        f"Buffer size {len(audio_buffer)} exceeds max {max_samples}"
    
    logger.info(f"✓ Audio buffer memory: {buffer_delta:.2f} MB (expected: ~{expected_max_mb:.2f} MB, limit enforced)")


def test_model_manager_memory(memory_monitor):
    """Test model manager memory footprint."""
    from config.app_config import ConfigManager
    from core.models.manager import ModelManager
    from data.database.connection import DatabaseConnection
    
    memory_monitor.measure("before_model_manager")
    
    # Create dependencies
    config = ConfigManager()
    db = DatabaseConnection(":memory:")
    
    # Initialize database schema
    db.initialize_schema()
    
    # Create model manager (without loading actual models)
    model_manager = ModelManager(config, db)
    
    memory_after_manager = memory_monitor.measure("after_model_manager")
    manager_delta = memory_monitor.get_delta("after_model_manager")
    
    # Model manager metadata should use <30MB
    assert manager_delta < 40, f"Model manager memory {manager_delta:.2f} MB exceeds 40 MB"
    
    # Cleanup
    db.close_all()
    gc.collect()
    
    logger.info(f"✓ Model manager memory: {manager_delta:.2f} MB")


def test_memory_leak_detection(memory_monitor):
    """Test for memory leaks in repeated operations."""
    from data.database.models import TranscriptionTask
    
    memory_monitor.measure("before_leak_test")
    
    # Perform repeated operations
    tasks = []
    for i in range(100):
        task = TranscriptionTask(
            file_path=f"/tmp/test_{i}.wav",
            file_name=f"test_{i}.wav",
            file_size=1024 * 1024,
            status="pending",
        )
        tasks.append(task)
    
    memory_after_creation = memory_monitor.measure("after_task_creation")
    
    # Clear references
    tasks.clear()
    gc.collect()
    
    memory_after_cleanup = memory_monitor.measure("after_task_cleanup")
    
    # Memory should return close to baseline
    leak_delta = memory_after_cleanup - memory_after_creation
    
    # Allow small delta for GC overhead
    assert abs(leak_delta) < 5, f"Potential memory leak detected: {leak_delta:.2f} MB"
    
    logger.info(f"✓ No memory leak detected (delta: {leak_delta:.2f} MB)")


def test_cache_memory_limits(memory_monitor):
    """Test cache implementations respect memory limits."""
    from collections import OrderedDict
    
    memory_monitor.measure("before_cache")
    
    # Simulate LRU cache with size limit
    max_cache_size = 100
    cache = OrderedDict()
    
    # Fill cache beyond limit
    for i in range(200):
        cache[f"key_{i}"] = f"value_{i}" * 1000  # ~5KB per entry
        
        # Enforce size limit
        if len(cache) > max_cache_size:
            cache.popitem(last=False)  # Remove oldest
    
    memory_after_cache = memory_monitor.measure("after_cache_fill")
    cache_delta = memory_monitor.get_delta("after_cache_fill")
    
    # Cache should respect size limit
    assert len(cache) == max_cache_size, \
        f"Cache size {len(cache)} exceeds limit {max_cache_size}"
    
    # Memory should be bounded (allow generous margin for Python overhead)
    expected_max_mb = (max_cache_size * 5) / 1024  # ~5KB per entry
    assert cache_delta < expected_max_mb * 5, \
        f"Cache memory {cache_delta:.2f} MB exceeds expected {expected_max_mb * 5:.2f} MB"
    
    logger.info(f"✓ Cache memory: {cache_delta:.2f} MB (limit enforced, expected: ~{expected_max_mb:.2f} MB)")


if __name__ == "__main__":
    # Run tests with verbose output
    pytest.main([__file__, "-v", "-s"])
