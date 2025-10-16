"""
Resource monitoring utility for EchoNote.

Monitors system resources (CPU, memory) and provides warnings when
resources are low.
"""

import logging
import psutil
from typing import Dict, Optional
from PyQt6.QtCore import QObject, QTimer, pyqtSignal


logger = logging.getLogger(__name__)


class ResourceMonitor(QObject):
    """
    Monitors system resources and emits signals when thresholds are exceeded.
    """

    # Signals
    low_memory_warning = pyqtSignal(float)  # Available memory in MB
    high_cpu_warning = pyqtSignal(float)  # CPU usage percentage
    resources_recovered = pyqtSignal()  # Resources back to normal

    # Thresholds
    LOW_MEMORY_THRESHOLD_MB = 500  # Warn if available memory < 500MB
    HIGH_CPU_THRESHOLD_PERCENT = 90  # Warn if CPU usage > 90%

    def __init__(
        self,
        check_interval_ms: int = 30000,  # Check every 30 seconds
        parent: Optional[QObject] = None
    ):
        """
        Initialize resource monitor.

        Args:
            check_interval_ms: Interval between checks in milliseconds
            parent: Parent QObject
        """
        super().__init__(parent)

        self.check_interval_ms = check_interval_ms
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._check_resources)

        # State tracking
        self._low_memory_warned = False
        self._high_cpu_warned = False
        self._last_memory_mb = 0
        self._last_cpu_percent = 0

        logger.info(
            f"ResourceMonitor initialized with "
            f"check_interval={check_interval_ms}ms"
        )

    def start(self):
        """Start monitoring resources."""
        if not self._timer.isActive():
            self._timer.start(self.check_interval_ms)
            logger.info("Resource monitoring started")
            # Do an immediate check
            self._check_resources()

    def stop(self):
        """Stop monitoring resources."""
        if self._timer.isActive():
            self._timer.stop()
            logger.info("Resource monitoring stopped")

    def is_monitoring(self) -> bool:
        """Check if monitoring is active."""
        return self._timer.isActive()

    def _check_resources(self):
        """Check system resources and emit warnings if needed."""
        try:
            # Get memory info
            memory = psutil.virtual_memory()
            available_mb = memory.available / (1024 * 1024)
            self._last_memory_mb = available_mb

            # Get CPU usage (averaged over 1 second)
            cpu_percent = psutil.cpu_percent(interval=1)
            self._last_cpu_percent = cpu_percent

            logger.debug(
                f"Resources: Memory={available_mb:.1f}MB available, "
                f"CPU={cpu_percent:.1f}%"
            )

            # Check memory threshold
            if available_mb < self.LOW_MEMORY_THRESHOLD_MB:
                if not self._low_memory_warned:
                    logger.warning(
                        f"Low memory warning: {available_mb:.1f}MB available "
                        f"(threshold: {self.LOW_MEMORY_THRESHOLD_MB}MB)"
                    )
                    self.low_memory_warning.emit(available_mb)
                    self._low_memory_warned = True
            else:
                if self._low_memory_warned:
                    logger.info(
                        f"Memory recovered: {available_mb:.1f}MB available"
                    )
                    self._low_memory_warned = False
                    self.resources_recovered.emit()

            # Check CPU threshold
            if cpu_percent > self.HIGH_CPU_THRESHOLD_PERCENT:
                if not self._high_cpu_warned:
                    logger.warning(
                        f"High CPU warning: {cpu_percent:.1f}% "
                        f"(threshold: {self.HIGH_CPU_THRESHOLD_PERCENT}%)"
                    )
                    self.high_cpu_warning.emit(cpu_percent)
                    self._high_cpu_warned = True
            else:
                if self._high_cpu_warned:
                    logger.info(f"CPU usage normalized: {cpu_percent:.1f}%")
                    self._high_cpu_warned = False
                    # Don't emit resources_recovered here to avoid duplicate

        except Exception as e:
            logger.error(f"Error checking resources: {e}")

    def get_current_stats(self) -> Dict[str, float]:
        """
        Get current resource statistics.

        Returns:
            Dict with current stats:
            {
                'memory_available_mb': float,
                'memory_used_percent': float,
                'memory_total_mb': float,
                'cpu_percent': float,
                'cpu_count': int
            }
        """
        try:
            memory = psutil.virtual_memory()
            cpu_percent = psutil.cpu_percent(interval=0.1)

            return {
                'memory_available_mb': memory.available / (1024 * 1024),
                'memory_used_percent': memory.percent,
                'memory_total_mb': memory.total / (1024 * 1024),
                'cpu_percent': cpu_percent,
                'cpu_count': psutil.cpu_count()
            }
        except Exception as e:
            logger.error(f"Error getting resource stats: {e}")
            return {
                'memory_available_mb': 0,
                'memory_used_percent': 0,
                'memory_total_mb': 0,
                'cpu_percent': 0,
                'cpu_count': 0
            }

    def get_last_check_stats(self) -> Dict[str, float]:
        """
        Get statistics from last check.

        Returns:
            Dict with last check stats
        """
        return {
            'memory_available_mb': self._last_memory_mb,
            'cpu_percent': self._last_cpu_percent
        }

    def is_low_memory(self) -> bool:
        """Check if system is currently in low memory state."""
        return self._low_memory_warned

    def is_high_cpu(self) -> bool:
        """Check if system is currently in high CPU state."""
        return self._high_cpu_warned

    @staticmethod
    def format_memory_size(size_mb: float) -> str:
        """
        Format memory size for display.

        Args:
            size_mb: Size in megabytes

        Returns:
            Formatted string (e.g., "1.5 GB", "512 MB")
        """
        if size_mb >= 1024:
            return f"{size_mb / 1024:.1f} GB"
        else:
            return f"{size_mb:.0f} MB"


# Singleton instance
_resource_monitor_instance: Optional[ResourceMonitor] = None


def get_resource_monitor() -> ResourceMonitor:
    """
    Get the singleton ResourceMonitor instance.

    Returns:
        ResourceMonitor instance
    """
    global _resource_monitor_instance
    if _resource_monitor_instance is None:
        _resource_monitor_instance = ResourceMonitor()
    return _resource_monitor_instance
