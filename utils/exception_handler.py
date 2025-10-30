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
Global exception handling utilities.

Extracted from main.py to improve separation of concerns.
"""

import sys
import traceback
from typing import Optional

from utils.error_handler import ErrorHandler

# Global logger for exception hook
_logger: Optional[object] = None

def set_global_logger(logger):
    """Set the global logger for exception handling."""
    global _logger
    _logger = logger

def exception_hook(exctype, value, tb):
    """
    Global exception handler for uncaught exceptions.

    This function is called for all uncaught exceptions. It logs the error
    and displays a user-friendly error dialog.

    Args:
        exctype: Exception type
        value: Exception value
        tb: Traceback object
    """
    # Format the full traceback
    error_msg = "".join(traceback.format_exception(exctype, value, tb))

    # Log the error
    if _logger:
        _logger.critical(
            f"Uncaught exception: {exctype.__name__}: {value}",
            exc_info=(exctype, value, tb),
        )
    else:
        # Fallback if logger not initialized
        print(f"CRITICAL ERROR: {error_msg}", file=sys.stderr)

    # Try to show error dialog if PySide6 is available
    try:
        from PySide6.QtWidgets import QApplication

        from ui.common.error_dialog import show_error_dialog

        # Check if QApplication exists
        app = QApplication.instance()
        if app:
            # Get error info from error handler
            error_info = ErrorHandler.handle_error(value)

            # Show error dialog
            show_error_dialog(
                title="应用程序错误 / Application Error",
                message=error_info["user_message"],
                details=error_msg,
                i18n=None,  # No i18n available in crash scenario
                parent=None,
            )
    except Exception as dialog_error:
        # If dialog fails, just print to stderr
        print(f"Failed to show error dialog: {dialog_error}", file=sys.stderr)
        print(f"Original error:\n{error_msg}", file=sys.stderr)

def install_exception_hook(logger):
    """Install the global exception hook with the given logger."""
    set_global_logger(logger)
    sys.excepthook = exception_hook
