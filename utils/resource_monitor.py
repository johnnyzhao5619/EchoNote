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
"""Resource monitoring utility for EchoNote."""

import logging
from typing import Any, Dict, Optional

import psutil
from PySide6.QtCore import QObject, QTimer, Signal

logger = logging.getLogger(__name__)


class ResourceMonitor(QObject):
    """Monitor system resources and emit signals when thresholds are exceeded."""

    # Signals
    low_memory_warning = Signal(float)  # Available memory in MB
    high_cpu_warning = Signal(float)  # CPU usage percentage
    resources_recovered = Signal()  # Resources back to normal

    # Constants
    BYTES_TO_MB = 1024 * 1024  # Conversion factor from bytes to megabytes

    def __init__(
        self,
        check_interval_ms: int = None,  # Check every 30 seconds
        parent: Optional[QObject] = None,
        *,
        config_manager: Optional[Any] = None,
        settings_manager: Optional[Any] = None,
    ):
        """
        Initialize resource monitor.

        Args:
            check_interval_ms: Interval between checks in milliseconds
            parent: Parent QObject
            config_manager: Optional ConfigManager supplying thresholds
            settings_manager: Optional SettingsManager supplying thresholds
        """
        from config.constants import RESOURCE_CHECK_INTERVAL_MS

        if check_interval_ms is None:
            check_interval_ms = RESOURCE_CHECK_INTERVAL_MS

        super().__init__(parent)

        self._threshold_source = settings_manager or config_manager

        # Import constants
        from config.constants import (
            HIGH_CPU_THRESHOLD_PERCENT,
            LOW_MEMORY_THRESHOLD_MB,
            MAX_CPU_THRESHOLD_PERCENT,
            MAX_MEMORY_THRESHOLD_MB,
            MIN_CPU_THRESHOLD_PERCENT,
            MIN_MEMORY_THRESHOLD_MB,
        )

        self.low_memory_threshold_mb = self._resolve_threshold(
            key="resource_monitor.low_memory_mb",
            default=float(LOW_MEMORY_THRESHOLD_MB),
            minimum=MIN_MEMORY_THRESHOLD_MB,
            maximum=MAX_MEMORY_THRESHOLD_MB,
        )

        self.high_cpu_threshold_percent = self._resolve_threshold(
            key="resource_monitor.high_cpu_percent",
            default=float(HIGH_CPU_THRESHOLD_PERCENT),
            minimum=MIN_CPU_THRESHOLD_PERCENT,
            maximum=MAX_CPU_THRESHOLD_PERCENT,
        )

        self.check_interval_ms = check_interval_ms
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._check_resources)

        # State tracking
        self._low_memory_warned = False
        self._high_cpu_warned = False
        self._last_memory_mb = 0
        self._last_cpu_percent = 0
        self._is_checking = False
        self._cpu_percent_initialized = False

        self._prime_cpu_percent()

        logger.info(
            "ResourceMonitor initialized with check_interval=%sms, "
            "low_memory_threshold=%.1fMB, high_cpu_threshold=%.1f%%",
            check_interval_ms,
            self.low_memory_threshold_mb,
            self.high_cpu_threshold_percent,
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
        if self._is_checking:
            logger.debug("Resource check already in progress; skipping this cycle")
            return

        self._is_checking = True

        try:
            # Get memory info
            memory = psutil.virtual_memory()
            available_mb = memory.available / self.BYTES_TO_MB
            self._last_memory_mb = available_mb

            cpu_percent = self._get_cpu_percent()
            self._last_cpu_percent = cpu_percent

            logger.debug(
                f"Resources: Memory={available_mb:.1f}MB available, " f"CPU={cpu_percent:.1f}%"
            )

            # Check memory threshold
            if available_mb < self.low_memory_threshold_mb:
                if not self._low_memory_warned:
                    logger.warning(
                        "Low memory warning: %.1fMB available (threshold: %.1fMB)",
                        available_mb,
                        self.low_memory_threshold_mb,
                    )
                    self.low_memory_warning.emit(available_mb)
                    self._low_memory_warned = True
            else:
                if self._low_memory_warned:
                    logger.info(f"Memory recovered: {available_mb:.1f}MB available")
                    self._low_memory_warned = False
                    self.resources_recovered.emit()

            # Check CPU threshold
            if cpu_percent > self.high_cpu_threshold_percent:
                if not self._high_cpu_warned:
                    logger.warning(
                        "High CPU warning: %.1f%% (threshold: %.1f%%)",
                        cpu_percent,
                        self.high_cpu_threshold_percent,
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
        finally:
            self._is_checking = False

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
            cpu_percent = self._get_cpu_percent()

            return {
                "memory_available_mb": memory.available / self.BYTES_TO_MB,
                "memory_used_percent": memory.percent,
                "memory_total_mb": memory.total / self.BYTES_TO_MB,
                "cpu_percent": cpu_percent,
                "cpu_count": psutil.cpu_count(),
            }
        except Exception as e:
            logger.error(f"Error getting resource stats: {e}")
            return {
                "memory_available_mb": 0,
                "memory_used_percent": 0,
                "memory_total_mb": 0,
                "cpu_percent": 0,
                "cpu_count": 0,
            }

    def get_last_check_stats(self) -> Dict[str, float]:
        """
        Get statistics from last check.

        Returns:
            Dict with last check stats
        """
        return {"memory_available_mb": self._last_memory_mb, "cpu_percent": self._last_cpu_percent}

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
        from config.constants import MB_TO_GB_THRESHOLD

        if size_mb >= MB_TO_GB_THRESHOLD:
            return f"{size_mb / MB_TO_GB_THRESHOLD:.1f} GB"
        else:
            return f"{size_mb:.0f} MB"

    def _prime_cpu_percent(self) -> None:
        """Prime psutil CPU sampling to enable non-blocking reads."""
        try:
            psutil.cpu_percent(interval=None)
        except Exception as exc:
            logger.debug(f"Unable to prime CPU percent sampling: {exc}")
            self._cpu_percent_initialized = False
        else:
            self._cpu_percent_initialized = True

    def _get_cpu_percent(self) -> float:
        """Retrieve CPU usage using non-blocking sampling."""
        if not self._cpu_percent_initialized:
            self._prime_cpu_percent()

        try:
            cpu_percent = psutil.cpu_percent(interval=None)
        except Exception as exc:
            logger.error(f"Error getting CPU percent: {exc}")
            return self._last_cpu_percent

        return cpu_percent

    def _resolve_threshold(
        self,
        *,
        key: str,
        default: float,
        minimum: Optional[float] = None,
        maximum: Optional[float] = None,
    ) -> float:
        """Resolve threshold from configuration with fallback to default."""

        value = self._get_config_value(key)
        if value is None:
            return default

        try:
            numeric = float(value)
        except (TypeError, ValueError):
            logger.warning("Invalid value '%s' for %s; using default %.1f", value, key, default)
            return default

        if minimum is not None and numeric < minimum:
            logger.warning(
                "%s=%.1f below minimum %.1f; using default %.1f", key, numeric, minimum, default
            )
            return default

        if maximum is not None and numeric > maximum:
            logger.warning(
                "%s=%.1f above maximum %.1f; using default %.1f", key, numeric, maximum, default
            )
            return default

        return numeric

    def _get_config_value(self, key: str) -> Optional[Any]:
        """Retrieve a configuration value from the injected settings provider."""

        if self._threshold_source is None:
            return None

        getter = getattr(self._threshold_source, "get_setting", None)
        if callable(getter):
            try:
                return getter(key)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to read %s via get_setting: %s", key, exc)

        getter = getattr(self._threshold_source, "get", None)
        if callable(getter):
            try:
                return getter(key)
            except TypeError:
                try:
                    return getter(key, None)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Failed to read %s via get(key, default): %s", key, exc)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to read %s via get: %s", key, exc)

        return None


# Singleton instance
_resource_monitor_instance: Optional[ResourceMonitor] = None


def get_resource_monitor(
    config_manager: Optional[Any] = None, settings_manager: Optional[Any] = None
) -> ResourceMonitor:
    """
    Get the singleton ResourceMonitor instance.

    Returns:
        ResourceMonitor instance
    """
    global _resource_monitor_instance
    if _resource_monitor_instance is None:
        threshold_source = settings_manager or config_manager
        if threshold_source is None:
            from config.app_config import ConfigManager  # Local import to avoid cycles

            threshold_source = ConfigManager()
            _resource_monitor_instance = ResourceMonitor(config_manager=threshold_source)
        elif settings_manager is not None:
            _resource_monitor_instance = ResourceMonitor(settings_manager=settings_manager)
        else:
            _resource_monitor_instance = ResourceMonitor(config_manager=config_manager)
    return _resource_monitor_instance
