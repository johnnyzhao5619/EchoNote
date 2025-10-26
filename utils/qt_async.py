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
Qt async helper utilities.

Provides utilities for running async code in Qt applications.
"""

import asyncio
import logging
from typing import Coroutine, Any, Callable, Optional
from concurrent.futures import ThreadPoolExecutor
from PySide6.QtCore import QObject, Signal


logger = logging.getLogger('echonote.utils.qt_async')


class AsyncRunner(QObject):
    """
    Helper class to run async coroutines in a Qt application.
    
    Runs async code in a separate thread with its own event loop.
    """
    
    # Signal emitted when async task completes
    finished = Signal(object)  # result
    error = Signal(Exception)  # exception
    
    def __init__(self, parent: Optional[QObject] = None):
        """
        Initialize async runner.
        
        Args:
            parent: Parent QObject
        """
        super().__init__(parent)
        self.executor = ThreadPoolExecutor(max_workers=1)
    
    def run_async(
        self,
        coro: Coroutine,
        on_success: Optional[Callable[[Any], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None
    ):
        """
        Run an async coroutine in a separate thread.
        
        Args:
            coro: Coroutine to run
            on_success: Optional callback for successful completion
            on_error: Optional callback for errors
        """
        # Connect callbacks if provided
        if on_success:
            self.finished.connect(on_success)
        if on_error:
            self.error.connect(on_error)
        
        # Submit to executor
        self.executor.submit(self._run_in_thread, coro)
    
    def _run_in_thread(self, coro: Coroutine):
        """
        Run coroutine in thread with new event loop.
        
        Args:
            coro: Coroutine to run
        """
        try:
            # Create new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                # Run coroutine
                result = loop.run_until_complete(coro)
                
                # Emit success signal
                self.finished.emit(result)
                
                return result
                
            finally:
                # Clean up loop
                loop.close()
                
        except Exception as e:
            logger.error(f"Error running async task: {e}")
            self.error.emit(e)
            raise
    
    def cleanup(self):
        """Clean up resources."""
        self.executor.shutdown(wait=False)


# Global async runner instance
_async_runner: Optional[AsyncRunner] = None


def get_async_runner() -> AsyncRunner:
    """
    Get global async runner instance.
    
    Returns:
        AsyncRunner instance
    """
    global _async_runner
    
    if _async_runner is None:
        _async_runner = AsyncRunner()
    
    return _async_runner


def run_async(
    coro: Coroutine,
    on_success: Optional[Callable[[Any], None]] = None,
    on_error: Optional[Callable[[Exception], None]] = None
):
    """
    Run an async coroutine from Qt code.
    
    This is a convenience function that uses the global async runner.
    
    Args:
        coro: Coroutine to run
        on_success: Optional callback for successful completion
        on_error: Optional callback for errors
    
    Example:
        ```python
        def on_task_added(task_id):
            print(f"Task added: {task_id}")
        
        def on_error(error):
            print(f"Error: {error}")
        
        run_async(
            manager.add_task("/path/to/file.mp3"),
            on_success=on_task_added,
            on_error=on_error
        )
        ```
    """
    runner = get_async_runner()
    runner.run_async(coro, on_success, on_error)
