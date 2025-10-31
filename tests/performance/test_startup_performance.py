# SPDX-License-Identifier: Apache-2.0
"""
Startup performance tests.

Tests to measure and validate application startup time.
"""

import time
import pytest
from unittest.mock import Mock, patch, MagicMock


class TestStartupOptimizer:
    """Tests for startup optimization utilities."""

    def test_startup_timer_checkpoint(self):
        """Test startup timer checkpoint recording."""
        from utils.startup_optimizer import StartupTimer
        
        timer = StartupTimer()
        time.sleep(0.01)  # Small delay
        timer.checkpoint("test_checkpoint")
        
        assert "test_checkpoint" in timer.checkpoints
        assert timer.checkpoints["test_checkpoint"] > 0

    def test_startup_timer_total_time(self):
        """Test startup timer total time calculation."""
        from utils.startup_optimizer import StartupTimer
        
        timer = StartupTimer()
        time.sleep(0.01)
        total = timer.get_total_time()
        
        assert total > 0

    def test_startup_timer_get_checkpoint_time(self):
        """Test getting specific checkpoint time."""
        from utils.startup_optimizer import StartupTimer
        
        timer = StartupTimer()
        timer.checkpoint("test")
        
        checkpoint_time = timer.get_checkpoint_time("test")
        assert checkpoint_time is not None
        assert checkpoint_time > 0

    def test_startup_timer_nonexistent_checkpoint(self):
        """Test getting nonexistent checkpoint returns None."""
        from utils.startup_optimizer import StartupTimer
        
        timer = StartupTimer()
        result = timer.get_checkpoint_time("nonexistent")
        
        assert result is None


class TestLazyLoader:
    """Tests for lazy loading functionality."""

    def test_lazy_loader_initialization(self):
        """Test lazy loader initialization."""
        from utils.startup_optimizer import LazyLoader
        
        init_func = Mock(return_value="test_value")
        loader = LazyLoader("test_component", init_func)
        
        assert not loader.is_initialized()
        assert init_func.call_count == 0

    def test_lazy_loader_get(self):
        """Test lazy loader get method."""
        from utils.startup_optimizer import LazyLoader
        
        init_func = Mock(return_value="test_value")
        loader = LazyLoader("test_component", init_func)
        
        result = loader.get()
        
        assert result == "test_value"
        assert loader.is_initialized()
        assert init_func.call_count == 1

    def test_lazy_loader_get_cached(self):
        """Test lazy loader caches result."""
        from utils.startup_optimizer import LazyLoader
        
        init_func = Mock(return_value="test_value")
        loader = LazyLoader("test_component", init_func)
        
        result1 = loader.get()
        result2 = loader.get()
        
        assert result1 == result2
        assert init_func.call_count == 1  # Only called once

    def test_lazy_loader_error_handling(self):
        """Test lazy loader error handling."""
        from utils.startup_optimizer import LazyLoader
        
        def failing_init():
            raise ValueError("Test error")
        
        loader = LazyLoader("test_component", failing_init)
        
        with pytest.raises(ValueError, match="Test error"):
            loader.get()
        
        assert not loader.is_initialized()


class TestBackgroundInitializer:
    """Tests for background initialization."""

    def test_background_initializer_creation(self, qapp):
        """Test background initializer can be created."""
        from utils.startup_optimizer import BackgroundInitializer
        
        init_functions = [
            ("component1", lambda: "value1"),
            ("component2", lambda: "value2"),
        ]
        
        initializer = BackgroundInitializer(init_functions)
        
        assert initializer is not None
        assert len(initializer.init_functions) == 2

    def test_background_initializer_signals(self, qapp):
        """Test background initializer has required signals."""
        from utils.startup_optimizer import BackgroundInitializer
        
        initializer = BackgroundInitializer([])
        
        assert hasattr(initializer, 'progress')
        assert hasattr(initializer, 'finished')
        assert hasattr(initializer, 'error')


class TestImportPerformance:
    """Tests for import performance."""

    def test_top_level_imports_minimal(self):
        """Test that main.py has minimal top-level imports."""
        import ast
        import pathlib
        
        main_py = pathlib.Path("main.py")
        if not main_py.exists():
            pytest.skip("main.py not found")
        
        with open(main_py) as f:
            tree = ast.parse(f.read())
        
        # Count only module-level imports (not inside functions)
        top_level_imports = 0
        for node in tree.body:  # Only check module body, not nested
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                top_level_imports += 1
        
        # We expect very few top-level imports (< 10)
        # Most imports should be inside the main() function
        assert top_level_imports < 10, f"Too many top-level imports: {top_level_imports}"

    def test_lazy_loading_used(self):
        """Test that lazy loading is used for heavy components."""
        import pathlib
        
        main_py = pathlib.Path("main.py")
        if not main_py.exists():
            pytest.skip("main.py not found")
        
        with open(main_py) as f:
            content = f.read()
        
        # Check for lazy loading patterns
        assert "LazyLoader" in content or "lazy loading" in content.lower()
        assert "EngineProxy" in content or "initialize_speech_engine" in content

    def test_background_initialization_used(self):
        """Test that background initialization is used."""
        import pathlib
        
        main_py = pathlib.Path("main.py")
        if not main_py.exists():
            pytest.skip("main.py not found")
        
        with open(main_py) as f:
            content = f.read()
        
        # Check for background initialization
        assert "BackgroundInitializer" in content
        assert "background" in content.lower()


class TestStartupConstants:
    """Tests for startup-related constants."""

    def test_startup_progress_steps_defined(self):
        """Test that startup progress steps are defined."""
        from config.constants import STARTUP_PROGRESS_STEPS
        
        assert isinstance(STARTUP_PROGRESS_STEPS, dict)
        assert len(STARTUP_PROGRESS_STEPS) > 0
        
        # Check for key steps
        assert "configuration" in STARTUP_PROGRESS_STEPS
        assert "database" in STARTUP_PROGRESS_STEPS
        assert "main_window" in STARTUP_PROGRESS_STEPS

    def test_splash_screen_delay_defined(self):
        """Test that splash screen delay is defined."""
        from config.constants import SPLASH_SCREEN_DELAY_MS
        
        assert isinstance(SPLASH_SCREEN_DELAY_MS, int)
        assert SPLASH_SCREEN_DELAY_MS > 0
        assert SPLASH_SCREEN_DELAY_MS < 5000  # Should be reasonable
