# SPDX-License-Identifier: Apache-2.0
"""
Constants for Calendar Hub.

Defines event types, sources, and sync status to avoid hardcoded strings.
"""


class EventType:
    """Enumeration of supported event types."""

    EVENT = "Event"
    TASK = "Task"
    APPOINTMENT = "Appointment"

    @classmethod
    def list(cls):
        """Return list of all event types."""
        return [cls.EVENT, cls.TASK, cls.APPOINTMENT]


class CalendarSource:
    """Enumeration of calendar event sources."""

    LOCAL = "local"
    GOOGLE = "google"
    OUTLOOK = "outlook"

    @classmethod
    def list_external(cls):
        """Return list of external providers."""
        return [cls.GOOGLE, cls.OUTLOOK]


class SyncStatus:
    """Enumeration of synchronization statuses."""

    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"
