#!/usr/bin/env python3
"""
End-to-End Performance Optimization Tests

This test suite verifies all performance optimization features:
- Startup optimization (splash screen, lazy loading, background init)
- GPU acceleration (device detection and selection)
- Resource monitoring (low memory detection and task pause/resume)

Test Categories:
1. Startup Tests
2. GPU Acceleration Tests
3. Resource Monitoring Tests
4. Performance Tests
5. Compatibility Tests
"""

import sys
import time
import unittest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


class StartupTests(unittest.TestCase):
    """Test startup optimization features."""
    
    def test_startup_timer_basic(self):
        """Test StartupTimer basic functionality."""
        from utils.startup_optimizer import StartupTimer
        
        timer = StartupTimer()
        self.assertIsNotNone(timer.start_time)
        
        # Add checkpoints
        timer.checkpoint("test1")
        time.sleep(0.01)
        timer.checkpoint("test2")
        
        # Verify checkpoints recorded
        self.assertIn("test1", timer.checkpoints)
        self.assertIn("test2", timer.checkpoints)
        
        # Verify timing
        elapsed = timer.get_total_time()
        self.assertGreater(elapsed, 0.01)
    
    def test_startup_timer_summary(self):
        """Test StartupTimer summary generation."""
        from utils.startup_optimizer import StartupTimer
        
        timer = StartupTimer()
        timer.checkpoint("init")
        time.sleep(0.01)
        timer.checkpoint("done")
        
        # Should not raise exception
        timer.log_summary()
    
    def test_lazy_loader_initialization(self):
        """Test LazyLoader defers initialization."""
        from utils.startup_optimizer import LazyLoader
        
        call_count = [0]
        
        def expensive_function():
            call_count[0] += 1
            return "loaded"
        
        loader = LazyLoader('test', expensive_function)
        
        # Should not be initialized yet
        self.assertFalse(loader.is_initialized())
        self.assertEqual(call_count[0], 0)
    
    def test_lazy_loader_first_access(self):
        """Test LazyLoader loads on first access."""
        from utils.startup_optimizer import LazyLoader
        
        call_count = [0]
        
        def expensive_function():
            call_count[0] += 1
            return "loaded"
        
        loader = LazyLoader('test', expensive_function)
        
        # First access should load
        result = loader.get()
        self.assertTrue(loader.is_initialized())
        self.assertEqual(call_count[0], 1)
        self.assertEqual(result, "loaded")
    
    def test_lazy_loader_caching(self):
        """Test LazyLoader caches result."""
        from utils.startup_optimizer import LazyLoader
        
        call_count = [0]
        
        def expensive_function():
            call_count[0] += 1
            return f"loaded_{call_count[0]}"
        
        loader = LazyLoader('test', expensive_function)
        
        # Multiple accesses should use cache
        result1 = loader.get()
        result2 = loader.get()
        result3 = loader.get()
        
        self.assertEqual(call_count[0], 1)  # Called only once
        self.assertEqual(result1, result2)
        self.assertEqual(result2, result3)
    
    def test_background_initializer_basic(self):
        """Test BackgroundInitializer basic functionality."""
        from utils.startup_optimizer import BackgroundInitializer
        from PyQt6.QtWidgets import QApplication
        
        # Create QApplication if not exists
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        
        results = {}
        
        def on_complete(init_results):
            results.update(init_results)
        
        # Simple initialization functions
        init_functions = [
            ('test1', lambda: "value1"),
            ('test2', lambda: "value2"),
        ]
        
        bg_init = BackgroundInitializer(init_functions)
        bg_init.finished.connect(on_complete)
        bg_init.start()
        
        # Wait for completion (max 5 seconds)
        start_time = time.time()
        while not results and time.time() - start_time < 5:
            app.processEvents()
            time.sleep(0.1)
        
        # Verify results
        self.assertIn('test1', results)
        self.assertIn('test2', results)
        self.assertEqual(results['test1'], 'value1')
        self.assertEqual(results['test2'], 'value2')


class GPUAccelerationTests(unittest.TestCase):
    """Test GPU acceleration features."""
    
    def test_gpu_detector_cpu_always_available(self):
        """Test that CPU is always detected as available."""
        from utils.gpu_detector import GPUDetector
        
        devices = GPUDetector.detect_available_devices()
        
        # CPU should always be available
        self.assertIn('cpu', devices)
        self.assertTrue(devices['cpu'])
    
    def test_gpu_detector_cuda_detection(self):
        """Test CUDA detection logic."""
        from utils.gpu_detector import GPUDetector
        
        devices = GPUDetector.detect_available_devices()
        
        # CUDA should be bool
        self.assertIn('cuda', devices)
        self.assertIsInstance(devices['cuda'], bool)
    
    def test_gpu_detector_recommended_device(self):
        """Test recommended device selection."""
        from utils.gpu_detector import GPUDetector
        
        device, reason = GPUDetector.get_recommended_device()
        
        # Should return valid device
        self.assertIn(device, ['cpu', 'cuda'])
        self.assertIsInstance(reason, str)
        self.assertGreater(len(reason), 0)
    
    def test_gpu_detector_device_options(self):
        """Test device options for UI."""
        from utils.gpu_detector import GPUDetector
        
        options = GPUDetector.get_available_device_options()
        
        # Should contain at least auto and cpu
        self.assertGreater(len(options), 0)
        
        # First option should be auto
        self.assertEqual(options[0][0], 'auto')
        
        # Should contain cpu
        device_ids = [opt[0] for opt in options]
        self.assertIn('cpu', device_ids)
    
    def test_gpu_detector_validate_device_config(self):
        """Test device configuration validation."""
        from utils.gpu_detector import GPUDetector
        
        # Test auto device
        device, compute_type, warning = GPUDetector.validate_device_config('auto', 'int8')
        self.assertIn(device, ['cpu', 'cuda'])
        self.assertIn(compute_type, ['int8', 'float16'])
        self.assertEqual(warning, "")
        
        # Test CPU device
        device, compute_type, warning = GPUDetector.validate_device_config('cpu', 'int8')
        self.assertEqual(device, 'cpu')
        self.assertEqual(compute_type, 'int8')
    
    def test_gpu_detector_display_names(self):
        """Test device display names."""
        from utils.gpu_detector import GPUDetector
        
        # Test display names
        self.assertEqual(GPUDetector.get_device_display_name('cpu'), 'CPU')
        self.assertEqual(GPUDetector.get_device_display_name('cuda'), 'CUDA (NVIDIA GPU)')
        self.assertEqual(GPUDetector.get_device_display_name('auto'), 'Auto (Recommended)')


class ResourceMonitoringTests(unittest.TestCase):
    """Test resource monitoring features."""
    
    def test_resource_monitor_singleton(self):
        """Test ResourceMonitor is a singleton."""
        from utils.resource_monitor import get_resource_monitor
        
        monitor1 = get_resource_monitor()
        monitor2 = get_resource_monitor()
        
        # Should be same instance
        self.assertIs(monitor1, monitor2)
    
    def test_resource_monitor_get_stats(self):
        """Test ResourceMonitor can get current stats."""
        from utils.resource_monitor import get_resource_monitor
        
        monitor = get_resource_monitor()
        stats = monitor.get_current_stats()
        
        # Should contain required keys
        self.assertIn('memory_available_mb', stats)
        self.assertIn('memory_total_mb', stats)
        self.assertIn('memory_used_percent', stats)
        self.assertIn('cpu_percent', stats)
        
        # Values should be reasonable
        self.assertGreater(stats['memory_available_mb'], 0)
        self.assertGreater(stats['memory_total_mb'], 0)
        self.assertGreaterEqual(stats['memory_used_percent'], 0)
        self.assertLessEqual(stats['memory_used_percent'], 100)
        self.assertGreaterEqual(stats['cpu_percent'], 0)
        self.assertLessEqual(stats['cpu_percent'], 100)
    
    def test_resource_monitor_format_memory(self):
        """Test memory size formatting."""
        from utils.resource_monitor import ResourceMonitor
        
        # Test various sizes
        self.assertEqual(ResourceMonitor.format_memory_size(512), "512 MB")
        self.assertEqual(ResourceMonitor.format_memory_size(1024), "1.0 GB")
        self.assertEqual(ResourceMonitor.format_memory_size(2048), "2.0 GB")
        self.assertEqual(ResourceMonitor.format_memory_size(100), "100 MB")
    
    def test_resource_monitor_low_memory_detection(self):
        """Test low memory detection."""
        from utils.resource_monitor import get_resource_monitor
        
        monitor = get_resource_monitor()
        
        # Get current state
        is_low = monitor.is_low_memory()
        
        # Should return boolean
        self.assertIsInstance(is_low, bool)
    
    def test_resource_monitor_high_cpu_detection(self):
        """Test high CPU detection."""
        from utils.resource_monitor import get_resource_monitor
        
        monitor = get_resource_monitor()
        
        # Get current state
        is_high = monitor.is_high_cpu()
        
        # Should return boolean
        self.assertIsInstance(is_high, bool)
    
    @patch('utils.resource_monitor.psutil.virtual_memory')
    def test_resource_monitor_low_memory_signal(self, mock_memory):
        """Test low memory signal emission."""
        from utils.resource_monitor import ResourceMonitor
        from PyQt6.QtWidgets import QApplication
        
        # Create QApplication if not exists
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        
        # Mock low memory condition
        mock_memory.return_value = Mock(
            available=400 * 1024 * 1024,  # 400MB
            total=8 * 1024 * 1024 * 1024,  # 8GB
            percent=95.0
        )
        
        monitor = ResourceMonitor()
        
        # Track signal emissions
        signal_emitted = []
        
        def on_low_memory(available_mb):
            signal_emitted.append(available_mb)
        
        monitor.low_memory_warning.connect(on_low_memory)
        
        # Trigger check
        monitor._check_resources()
        
        # Process events
        app.processEvents()
        
        # Should emit signal
        self.assertEqual(len(signal_emitted), 1)
        self.assertLess(signal_emitted[0], 500)


class PerformanceTests(unittest.TestCase):
    """Test actual performance improvements."""
    
    def test_lazy_loader_performance(self):
        """Test LazyLoader improves startup time."""
        from utils.startup_optimizer import LazyLoader
        
        # Simulate expensive initialization
        def expensive_init():
            time.sleep(0.1)
            return "loaded"
        
        # Without lazy loading
        start = time.time()
        result1 = expensive_init()
        eager_time = time.time() - start
        
        # With lazy loading
        start = time.time()
        loader = LazyLoader('test', expensive_init)
        lazy_time = time.time() - start
        
        # Lazy loading should be much faster
        self.assertLess(lazy_time, eager_time / 10)
        
        # But result should be same when accessed
        result2 = loader.get()
        self.assertEqual(result1, result2)
    
    def test_background_init_performance(self):
        """Test BackgroundInitializer doesn't block main thread."""
        from utils.startup_optimizer import BackgroundInitializer
        from PyQt6.QtWidgets import QApplication
        
        # Create QApplication if not exists
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        
        # Simulate slow initialization
        def slow_init():
            time.sleep(0.2)
            return "done"
        
        init_functions = [
            ('slow1', slow_init),
            ('slow2', slow_init),
        ]
        
        # Start background initialization
        start = time.time()
        bg_init = BackgroundInitializer(init_functions)
        bg_init.start()
        init_time = time.time() - start
        
        # Should return immediately (< 0.1s)
        self.assertLess(init_time, 0.1)


class CompatibilityTests(unittest.TestCase):
    """Test compatibility across different configurations."""
    
    def test_lazy_loader_proxy_compatibility(self):
        """Test LazyLoader proxy maintains compatibility."""
        from utils.startup_optimizer import LazyLoader
        
        # Create a mock object with methods
        class MockEngine:
            def transcribe(self, text):
                return f"transcribed: {text}"
            
            def get_name(self):
                return "MockEngine"
        
        loader = LazyLoader('engine', lambda: MockEngine())
        
        # Create proxy
        class EngineProxy:
            def __getattr__(self, name):
                return getattr(loader.get(), name)
        
        proxy = EngineProxy()
        
        # Should work like original object
        self.assertEqual(proxy.get_name(), "MockEngine")
        self.assertEqual(proxy.transcribe("test"), "transcribed: test")
    
    def test_resource_monitor_cross_platform(self):
        """Test ResourceMonitor works on current platform."""
        from utils.resource_monitor import get_resource_monitor
        import platform
        
        monitor = get_resource_monitor()
        stats = monitor.get_current_stats()
        
        # Should work on any platform
        self.assertIsNotNone(stats)
        self.assertGreater(stats['memory_available_mb'], 0)
        
        # Log platform info
        print(f"\nPlatform: {platform.system()}")
        print(f"Memory available: {stats['memory_available_mb']:.1f}MB")
        print(f"CPU usage: {stats['cpu_percent']:.1f}%")
    
    def test_gpu_detector_cross_platform(self):
        """Test GPUDetector works on current platform."""
        from utils.gpu_detector import GPUDetector
        import platform
        
        devices = GPUDetector.detect_available_devices()
        recommended, reason = GPUDetector.get_recommended_device()
        
        # Should work on any platform
        self.assertIsNotNone(devices)
        self.assertIn('cpu', devices)
        self.assertTrue(devices['cpu'])
        
        # Log platform info
        print(f"\nPlatform: {platform.system()}")
        print(f"Available devices: {devices}")
        print(f"Recommended: {recommended} ({reason})")


class IntegrationTests(unittest.TestCase):
    """Test integration of all performance features."""
    
    def test_translations_exist(self):
        """Test that all required translations exist."""
        import json
        
        languages = ['zh_CN', 'en_US', 'fr_FR']
        required_keys = [
            'notification.low_memory.title',
            'notification.low_memory.message',
            'notification.resources_recovered.title',
            'notification.resources_recovered.message',
        ]
        
        for lang in languages:
            with open(f'resources/translations/{lang}.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            for key_path in required_keys:
                keys = key_path.split('.')
                current = data
                
                for key in keys:
                    self.assertIn(key, current, f"Missing key '{key_path}' in {lang}")
                    current = current[key]
                
                # Value should be non-empty string
                self.assertIsInstance(current, str)
                self.assertGreater(len(current), 0)
    
    def test_config_default_device(self):
        """Test that default device is set to 'auto'."""
        import json
        
        # Read default config directly
        with open('config/default_config.json', 'r') as f:
            config = json.load(f)
        
        device = config['transcription']['faster_whisper']['device']
        
        # Should be 'auto' for optimal performance
        self.assertEqual(device, 'auto')


def run_test_suite():
    """Run the complete test suite with detailed output."""
    print("=" * 70)
    print("EchoNote Performance Optimization - End-to-End Test Suite")
    print("=" * 70)
    print()
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    test_classes = [
        StartupTests,
        GPUAccelerationTests,
        ResourceMonitoringTests,
        PerformanceTests,
        CompatibilityTests,
        IntegrationTests,
    ]
    
    for test_class in test_classes:
        tests = loader.loadTestsFromTestCase(test_class)
        suite.addTests(tests)
    
    # Run tests with verbose output
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print()
    print("=" * 70)
    print("Test Summary")
    print("=" * 70)
    print(f"Tests run: {result.testsRun}")
    print(f"Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print("=" * 70)
    
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    sys.exit(run_test_suite())
