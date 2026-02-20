# SPDX-License-Identifier: Apache-2.0
"""
Exceptions for Calendar Hub.

Defines specific exceptions for calendar operations and synchronization.
"""

from typing import List, Optional


class CalendarError(Exception):
    """Base exception for calendar operations."""

    pass


class EventNotFoundError(CalendarError):
    """Raised when an operation is performed on a non-existent event."""

    def __init__(self, event_id: str):
        super().__init__(f"Event not found: {event_id}")
        self.event_id = event_id


class SyncError(CalendarError):
    """Raised when synchronization with external providers fails."""

    def __init__(self, message: str, failed_providers: Optional[List[str]] = None):
        super().__init__(message)
        self.failed_providers = failed_providers or []
