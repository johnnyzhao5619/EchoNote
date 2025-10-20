"""
Base class for external calendar synchronization adapters.

Defines the interface that all calendar sync adapters must implement.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from data.database.models import CalendarEvent


class CalendarSyncAdapter(ABC):
    """
    Abstract base class for calendar synchronization adapters.

    All external calendar sync implementations (Google, Outlook, etc.)
    must inherit from this class and implement all abstract methods.
    """

    @abstractmethod
    def authenticate(self, credentials: dict) -> dict:
        """
        Perform OAuth authentication with the calendar provider.

        Args:
            credentials: Dictionary containing authentication credentials
                        (e.g., client_id, client_secret, redirect_uri)

        Returns:
            Dictionary containing authentication tokens:
            {
                'access_token': str,
                'refresh_token': str,
                'expires_at': str (ISO format timestamp)
            }

        Raises:
            Exception: If authentication fails
        """
        pass

    @abstractmethod
    def fetch_events(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        last_sync_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Fetch events from the external calendar.

        Supports incremental synchronization using sync tokens.

        Args:
            start_date: Optional start date in ISO format
            end_date: Optional end date in ISO format
            last_sync_token: Optional token for incremental sync

        Returns:
            Dictionary containing:
            {
                'events': [
                    {
                        'id': str,
                        'title': str,
                        'event_type': str,
                        'start_time': str (ISO format),
                        'end_time': str (ISO format),
                        'location': Optional[str],
                        'attendees': List[str],
                        'description': Optional[str],
                        'reminder_minutes': Optional[int],
                        'recurrence_rule': Optional[str]
                    },
                    ...
                ],
                'sync_token': Optional[str]  # For next incremental sync
            }

        Raises:
            Exception: If fetching events fails
        """
        pass

    @abstractmethod
    def push_event(self, event: CalendarEvent) -> str:
        """
        Push a local event to the external calendar.

        Args:
            event: CalendarEvent instance to push

        Returns:
            External event ID (string)

        Raises:
            Exception: If pushing event fails
        """
        pass

    @abstractmethod
    def update_event(self, event: CalendarEvent, external_id: str) -> None:
        """
        Update an existing event on the external calendar.

        Args:
            event: CalendarEvent instance with latest local data
            external_id: Provider-specific identifier for the event

        Raises:
            Exception: If updating the external event fails
        """
        pass

    @abstractmethod
    def delete_event(self, event: CalendarEvent, external_id: str) -> None:
        """
        Delete an event from the external calendar.

        Args:
            event: CalendarEvent instance scheduled for deletion
            external_id: Provider-specific identifier for the event

        Raises:
            Exception: If deleting the external event fails
        """
        pass

    @abstractmethod
    def revoke_access(self):
        """
        Revoke access to the external calendar.

        This should invalidate the OAuth tokens and disconnect
        the calendar integration.

        Raises:
            Exception: If revoking access fails
        """
        pass

    def get_name(self) -> str:
        """
        Get the name of the calendar provider.

        Returns:
            Provider name (e.g., 'google', 'outlook')
        """
        return self.__class__.__name__.lower().replace('adapter', '')

    def get_supported_features(self) -> Dict[str, bool]:
        """
        Get the features supported by this adapter.

        Returns:
            Dictionary of feature flags:
            {
                'incremental_sync': bool,
                'push_events': bool,
                'recurrence': bool,
                'reminders': bool
            }
        """
        return {
            'incremental_sync': True,
            'push_events': True,
            'recurrence': True,
            'reminders': True
        }
