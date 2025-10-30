#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""
Centralized benchmark configuration and baselines.
"""

import platform
from typing import Dict

import psutil

class BenchmarkConfig:
    """Centralized benchmark configuration."""

    # PyQt6 baseline values from requirements
    BASELINES = {
        "startup_time_cold": 5.0,  # seconds
        "startup_time_hot": 3.0,  # seconds
        "ui_response_button": 0.1,  # seconds
        "ui_response_menu": 0.05,  # seconds
        "ui_response_dialog": 0.1,  # seconds
        "ui_scroll_frame_time": 16.67,  # ms (60 FPS)
        "memory_idle": 300.0,  # MB
        "memory_transcription": 500.0,  # MB
        "memory_leak_threshold": 50.0,  # MB
        "transcription_speed": 2.0,  # times real-time
        "calendar_sync_speed": 100.0,  # events/second
    }

    # Test parameters
    TEST_PARAMS = {
        "startup_runs": 5,
        "ui_button_iterations": 100,
        "ui_menu_iterations": 50,
        "ui_dialog_iterations": 50,
        "ui_scroll_items": 1000,
        "ui_scroll_operations": 100,
        "memory_monitor_duration": 60,  # seconds
        "memory_monitor_interval": 2,  # seconds
        "calendar_test_events": 1000,
        "database_test_records": 10000,
        "file_test_count": 1000,
    }

    @staticmethod
    def get_system_info() -> Dict:
        """Get system information."""
        return {
            "platform": platform.platform(),
            "system": platform.system(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "python_version": platform.python_version(),
            "cpu_count": psutil.cpu_count(),
            "memory_total": psutil.virtual_memory().total / 1024 / 1024,  # MB
        }

    @staticmethod
    def get_tolerance(metric: str) -> float:
        """Get tolerance for pass/fail comparison."""
        # Memory metrics allow 10% tolerance
        if "memory" in metric:
            return 1.1
        # Performance metrics require 80% of baseline
        elif metric in ["transcription_speed", "calendar_sync_speed"]:
            return 0.8
        # Time-based metrics must not exceed baseline
        else:
            return 1.0
