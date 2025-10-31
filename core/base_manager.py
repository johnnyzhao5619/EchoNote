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
Base manager class for EchoNote application.

Provides common functionality and patterns for all manager classes.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from PySide6.QtCore import QObject


class BaseManager(QObject, ABC):
    """
    Abstract base class for all manager classes in EchoNote.

    Provides common initialization patterns, logging setup, and
    standardized error handling for manager classes.
    """

    def __init__(self, name: Optional[str] = None):
        """
        Initialize the base manager.

        Args:
            name: Optional name for the manager (used in logging)
        """
        super().__init__()
        self._name = name or self.__class__.__name__
        self._logger = logging.getLogger(f"echonote.{self._name.lower()}")
        self._initialized = False

    @property
    def name(self) -> str:
        """Get the manager name."""
        return self._name

    @property
    def logger(self) -> logging.Logger:
        """Get the manager's logger."""
        return self._logger

    @property
    def is_initialized(self) -> bool:
        """Check if the manager is initialized."""
        return self._initialized

    def _mark_initialized(self) -> None:
        """Mark the manager as initialized."""
        self._initialized = True
        self._logger.info(f"{self._name} initialized successfully")

    @abstractmethod
    def initialize(self) -> bool:
        """
        Initialize the manager.

        Returns:
            True if initialization was successful, False otherwise
        """
        pass

    def cleanup(self) -> None:
        """
        Cleanup resources used by the manager.

        Default implementation does nothing. Override in subclasses as needed.
        """
        self._logger.debug(f"Cleaning up {self._name}")

    def get_status(self) -> Dict[str, Any]:
        """
        Get the current status of the manager.

        Returns:
            Dictionary containing status information
        """
        return {
            "name": self._name,
            "initialized": self._initialized,
            "class": self.__class__.__name__,
        }

    def _handle_error(self, operation: str, error: Exception) -> None:
        """
        Handle errors in a standardized way.

        Args:
            operation: Description of the operation that failed
            error: The exception that occurred
        """
        self._logger.error(f"Error in {operation}: {error}", exc_info=True)
