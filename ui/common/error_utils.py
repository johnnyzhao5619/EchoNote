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
Error handling utilities for UI components.

Provides common error handling patterns to reduce code duplication.
"""

import logging
from typing import Callable, Optional

from ui.qt_imports import QMessageBox, QWidget

logger = logging.getLogger(__name__)


def handle_ui_error(
    parent: QWidget,
    operation: Callable,
    error_title: str = "Error",
    success_message: Optional[str] = None,
    log_context: str = "UI operation",
) -> bool:
    """
    Standard error handling pattern for UI operations.

    Args:
        parent: Parent widget for error dialogs
        operation: Function to execute
        error_title: Title for error dialog
        success_message: Optional success message to log
        log_context: Context for logging

    Returns:
        True if operation succeeded, False otherwise
    """
    try:
        result = operation()
        if success_message:
            logger.info(f"{log_context}: {success_message}")
        return True
    except Exception as e:
        logger.error(f"{log_context} failed: {e}")
        QMessageBox.critical(parent, error_title, str(e))
        return False


def safe_operation(operation: Callable, default_value=None, log_context: str = "Operation"):
    """
    Execute operation safely with logging, returning default on error.

    Args:
        operation: Function to execute
        default_value: Value to return on error
        log_context: Context for logging

    Returns:
        Operation result or default_value on error
    """
    try:
        return operation()
    except Exception as e:
        logger.error(f"{log_context} failed: {e}")
        return default_value
