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
"""
Startup optimization utilities.

Provides utilities for optimizing application startup time through
lazy loading and background initialization.
"""

import logging
import time
from typing import Any, Callable, Optional

from PySide6.QtCore import QThread, Signal

logger = logging.getLogger(__name__)


class BackgroundInitializer(QThread):
    """
    Background thread for initializing components after main window is shown.
    """

    # Signals
    progress = Signal(str, int)  # message, percent
    finished = Signal(dict)  # initialized components
    error = Signal(str)  # error message

    def __init__(self, init_functions: list, parent: Optional[QThread] = None):
        """
        Initialize background initializer.

        Args:
            init_functions: List of (name, function) tuples to initialize
            parent: Parent QThread
        """
        super().__init__(parent)
        self.init_functions = init_functions
        self.results = {}

    def run(self):
        """Run initialization in background thread."""
        total = len(self.init_functions)

        for i, (name, func) in enumerate(self.init_functions):
            try:
                logger.info(f"Background initializing: {name}")
                percent = int((i / total) * 100)
                self.progress.emit(f"Initializing {name}...", percent)

                start_time = time.time()
                result = func()
                elapsed = time.time() - start_time

                self.results[name] = result
                logger.info(f"Background initialized {name} in {elapsed:.2f}s")

            except Exception as e:
                logger.error(f"Error initializing {name}: {e}")
                self.error.emit(f"Failed to initialize {name}: {str(e)}")

        # Emit finished signal with results
        self.progress.emit("Initialization complete", 100)
        self.finished.emit(self.results)


class LazyLoader:
    """
    Lazy loader for deferring component initialization.

    Components are initialized only when first accessed.
    """

    def __init__(self, name: str, init_func: Callable):
        """
        Initialize lazy loader.

        Args:
            name: Component name (for logging)
            init_func: Function to call for initialization
        """
        self.name = name
        self.init_func = init_func
        self._instance = None
        self._initialized = False

    def get(self) -> Any:
        """
        Get the component, initializing if necessary.

        Returns:
            Initialized component
        """
        if not self._initialized:
            logger.info(f"Lazy loading: {self.name}")
            start_time = time.time()

            try:
                self._instance = self.init_func()
                self._initialized = True

                elapsed = time.time() - start_time
                logger.info(f"Lazy loaded {self.name} in {elapsed:.2f}s")
            except Exception as e:
                logger.error(f"Error lazy loading {self.name}: {e}")
                raise

        return self._instance

    def is_initialized(self) -> bool:
        """Check if component is initialized."""
        return self._initialized

    def reload(self) -> Any:
        """
        Force re-initialization and return the fresh instance.

        Returns:
            Re-initialized component instance
        """
        self._instance = None
        self._initialized = False
        return self.get()


class StartupTimer:
    """
    Timer for measuring startup performance.
    """

    def __init__(self):
        """Initialize startup timer."""
        self.start_time = time.time()
        self.checkpoints = {}

    def checkpoint(self, name: str):
        """
        Record a checkpoint.

        Args:
            name: Checkpoint name
        """
        elapsed = time.time() - self.start_time
        self.checkpoints[name] = elapsed
        logger.info(f"Startup checkpoint '{name}': {elapsed:.2f}s")

    def get_total_time(self) -> float:
        """Get total elapsed time since start."""
        return time.time() - self.start_time

    def get_checkpoint_time(self, name: str) -> Optional[float]:
        """
        Get time for a specific checkpoint.

        Args:
            name: Checkpoint name

        Returns:
            Elapsed time at checkpoint, or None if not found
        """
        return self.checkpoints.get(name)

    def log_summary(self):
        """Log a summary of all checkpoints."""
        total = self.get_total_time()
        logger.info("=" * 60)
        logger.info(f"Startup Performance Summary (Total: {total:.2f}s)")
        logger.info("=" * 60)

        for name, elapsed in sorted(self.checkpoints.items(), key=lambda x: x[1]):
            percent = (elapsed / total) * 100
            logger.info(f"  {name}: {elapsed:.2f}s ({percent:.1f}%)")

        logger.info("=" * 60)
