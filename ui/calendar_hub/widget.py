"""
Calendar Hub Widget for EchoNote.

Provides the main calendar interface with view switching, date navigation,
and account management.
"""

import logging
from typing import Optional, Dict, Any

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QStackedWidget, QButtonGroup, QFrame, QDialog
)
from PyQt6.QtCore import pyqtSignal

from utils.i18n import I18nQtManager


logger = logging.getLogger('echonote.ui.calendar_hub')


class CalendarHubWidget(QWidget):
    """
    Main calendar hub widget with view switching and navigation.
    
    Provides:
    - View switching (month/week/day)
    - Date navigation
    - Connected accounts display
    - Event creation
    """
    
    # Signals
    view_changed = pyqtSignal(str)  # month/week/day
    date_changed = pyqtSignal(object)  # datetime
    create_event_requested = pyqtSignal()
    add_account_requested = pyqtSignal()
    
    def __init__(
        self,
        calendar_manager,
        oauth_manager,
        i18n: I18nQtManager,
        parent: Optional[QWidget] = None
    ):
        """
        Initialize calendar hub widget.
        
        Args:
            calendar_manager: CalendarManager instance
            oauth_manager: OAuthManager instance
            i18n: Internationalization manager
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.calendar_manager = calendar_manager
        self.oauth_manager = oauth_manager
        self.i18n = i18n
        
        # Current view and date
        self.current_view = 'week'
        self.current_date = None  # Will be set by calendar view
        
        # Connected accounts
        self.connected_accounts: Dict[str, str] = {}
        
        # Setup UI
        self.setup_ui()
        
        # Connect language change signal
        self.i18n.language_changed.connect(self._on_language_changed)
        
        # Load existing connected accounts
        self._load_connected_accounts()
        
        logger.debug("CalendarHubWidget initialized")
    
    def setup_ui(self):
        """Set up the calendar hub UI."""
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Title
        self.title_label = QLabel(self.i18n.t('calendar_hub.title'))
        self.title_label.setObjectName("page_title")
        layout.addWidget(self.title_label)
        
        # Create toolbar
        toolbar = self._create_toolbar()
        layout.addWidget(toolbar)
        
        # Create accounts section
        accounts_section = self._create_accounts_section()
        layout.addWidget(accounts_section)
        
        # Create calendar view container
        self.view_container = self._create_view_container()
        layout.addWidget(self.view_container, stretch=1)
    
    def _create_toolbar(self) -> QWidget:
        """
        Create toolbar with view switching and navigation.
        
        Returns:
            Toolbar widget
        """
        toolbar = QWidget()
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        toolbar_layout.setSpacing(10)
        
        # View switching buttons
        view_group = QButtonGroup(self)
        view_group.setExclusive(True)
        
        self.month_btn = QPushButton(self.i18n.t('calendar_hub.view_month'))
        self.month_btn.setCheckable(True)
        self.month_btn.setObjectName('view_button')
        view_group.addButton(self.month_btn)
        
        self.week_btn = QPushButton(self.i18n.t('calendar_hub.view_week'))
        self.week_btn.setCheckable(True)
        self.week_btn.setChecked(True)  # Default view
        self.week_btn.setObjectName('view_button')
        view_group.addButton(self.week_btn)
        
        self.day_btn = QPushButton(self.i18n.t('calendar_hub.view_day'))
        self.day_btn.setCheckable(True)
        self.day_btn.setObjectName('view_button')
        view_group.addButton(self.day_btn)
        
        # Connect view buttons
        self.month_btn.clicked.connect(lambda: self._on_view_changed('month'))
        self.week_btn.clicked.connect(lambda: self._on_view_changed('week'))
        self.day_btn.clicked.connect(lambda: self._on_view_changed('day'))
        
        toolbar_layout.addWidget(self.month_btn)
        toolbar_layout.addWidget(self.week_btn)
        toolbar_layout.addWidget(self.day_btn)
        
        toolbar_layout.addSpacing(20)
        
        # Date navigation
        self.prev_btn = QPushButton('<')
        self.prev_btn.setFixedWidth(40)
        self.prev_btn.clicked.connect(self._on_prev_clicked)
        
        self.today_btn = QPushButton(self.i18n.t('calendar_hub.today'))
        self.today_btn.clicked.connect(self._on_today_clicked)
        
        self.next_btn = QPushButton('>')
        self.next_btn.setFixedWidth(40)
        self.next_btn.clicked.connect(self._on_next_clicked)
        
        toolbar_layout.addWidget(self.prev_btn)
        toolbar_layout.addWidget(self.today_btn)
        toolbar_layout.addWidget(self.next_btn)
        
        toolbar_layout.addStretch()
        
        # Create event button
        self.create_event_btn = QPushButton(
            self.i18n.t('calendar_hub.create_event')
        )
        self.create_event_btn.setObjectName('primary_button')
        self.create_event_btn.clicked.connect(
            lambda: self._show_event_dialog()
        )
        toolbar_layout.addWidget(self.create_event_btn)
        
        return toolbar
    
    def _create_accounts_section(self) -> QWidget:
        """
        Create connected accounts display section.
        
        Returns:
            Accounts section widget
        """
        accounts_widget = QWidget()
        accounts_layout = QHBoxLayout(accounts_widget)
        accounts_layout.setContentsMargins(0, 0, 0, 0)
        accounts_layout.setSpacing(10)
        
        # Connected accounts label
        self.accounts_label = QLabel(
            self.i18n.t('calendar_hub.connected_accounts') + ':'
        )
        accounts_layout.addWidget(self.accounts_label)
        
        # Container for account badges
        self.accounts_container = QWidget()
        self.accounts_container_layout = QHBoxLayout(self.accounts_container)
        self.accounts_container_layout.setContentsMargins(0, 0, 0, 0)
        self.accounts_container_layout.setSpacing(5)
        accounts_layout.addWidget(self.accounts_container)
        
        accounts_layout.addStretch()
        
        # Sync status label
        self.sync_status_label = QLabel('')
        self.sync_status_label.setStyleSheet("color: #666; font-size: 11px;")
        accounts_layout.addWidget(self.sync_status_label)
        
        # Sync now button
        self.sync_now_btn = QPushButton('🔄 ' + self.i18n.t('calendar_hub.sync_now'))
        self.sync_now_btn.setToolTip(self.i18n.t('calendar_hub.sync_now_tooltip'))
        self.sync_now_btn.clicked.connect(self._on_sync_now_clicked)
        accounts_layout.addWidget(self.sync_now_btn)
        
        # Add account button
        self.add_account_btn = QPushButton(
            '+ ' + self.i18n.t('calendar_hub.add_account')
        )
        self.add_account_btn.clicked.connect(
            self.show_add_account_dialog
        )
        accounts_layout.addWidget(self.add_account_btn)
        
        return accounts_widget
    
    def _create_view_container(self) -> QStackedWidget:
        """
        Create stacked widget container for calendar views.
        
        Returns:
            Stacked widget for views
        """
        container = QStackedWidget()
        
        # Import calendar views
        from ui.calendar_hub.calendar_view import MonthView, WeekView, DayView
        
        # Create actual calendar views
        self.month_view = MonthView(self.calendar_manager, self.i18n)
        self.week_view = WeekView(self.calendar_manager, self.i18n)
        self.day_view = DayView(self.calendar_manager, self.i18n)
        
        # Connect view signals
        self.month_view.date_changed.connect(self._on_date_changed)
        self.month_view.event_clicked.connect(self._on_event_clicked)
        
        self.week_view.date_changed.connect(self._on_date_changed)
        self.week_view.event_clicked.connect(self._on_event_clicked)
        
        self.day_view.date_changed.connect(self._on_date_changed)
        self.day_view.event_clicked.connect(self._on_event_clicked)
        
        # Add views to container
        container.addWidget(self.month_view)
        container.addWidget(self.week_view)
        container.addWidget(self.day_view)
        
        # Set default view (week)
        container.setCurrentIndex(1)
        
        return container
    
    def _on_view_changed(self, view: str):
        """
        Handle view change.
        
        Args:
            view: View name (month/week/day)
        """
        self.current_view = view
        
        # Update view container
        view_index = {'month': 0, 'week': 1, 'day': 2}
        self.view_container.setCurrentIndex(view_index[view])
        
        # Emit signal
        self.view_changed.emit(view)
        
        logger.debug(f"View changed to: {view}")
    
    def _on_prev_clicked(self):
        """Handle previous button click."""
        if self.current_view == 'month':
            self.month_view.prev_month()
        elif self.current_view == 'week':
            self.week_view.prev_week()
        else:  # day
            self.day_view.prev_day()
        
        logger.debug("Previous button clicked")
    
    def _on_today_clicked(self):
        """Handle today button click."""
        if self.current_view == 'month':
            self.month_view.today()
        elif self.current_view == 'week':
            self.week_view.today()
        else:  # day
            self.day_view.today()
        
        logger.debug("Today button clicked")
    
    def _on_next_clicked(self):
        """Handle next button click."""
        if self.current_view == 'month':
            self.month_view.next_month()
        elif self.current_view == 'week':
            self.week_view.next_week()
        else:  # day
            self.day_view.next_day()
        
        logger.debug("Next button clicked")
    
    def _on_date_changed(self, date):
        """
        Handle date change from calendar views.
        
        Args:
            date: New date
        """
        self.current_date = date
        self.date_changed.emit(date)
        logger.debug(f"Date changed to: {date}")
    
    def _on_event_clicked(self, event_id: str):
        """
        Handle event click from calendar views.
        
        Args:
            event_id: Event ID
        """
        try:
            # Load event data
            event = self.calendar_manager.get_event(event_id)
            
            if event:
                # Show event dialog in edit mode
                self._show_event_dialog(event)
            else:
                logger.warning(f"Event not found: {event_id}")
                
        except Exception as e:
            logger.error(f"Error loading event: {e}")
    
    def _show_event_dialog(self, event=None):
        """
        Show event creation/editing dialog.
        
        Args:
            event: Optional event data for editing
        """
        from ui.calendar_hub.event_dialog import EventDialog
        
        # Prepare event data for dialog
        event_data = None
        if event:
            event_data = {
                'id': event.id,
                'title': event.title,
                'event_type': event.event_type,
                'start_time': event.start_time,
                'end_time': event.end_time,
                'location': event.location,
                'attendees': event.attendees,
                'description': event.description,
                'reminder_minutes': event.reminder_minutes
            }
        
        # Show dialog
        dialog = EventDialog(
            self.i18n,
            self.connected_accounts,
            event_data,
            self
        )
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Get event data
            data = dialog.get_event_data()
            
            if data:
                try:
                    if event:
                        # Update existing event
                        self._update_event(data)
                    else:
                        # Create new event
                        self._create_event(data)
                    
                except Exception as e:
                    logger.error(f"Error saving event: {e}")
                    from PyQt6.QtWidgets import QMessageBox
                    QMessageBox.critical(
                        self,
                        "Error",
                        f"Failed to save event: {str(e)}"
                    )
    
    def _create_event(self, event_data: Dict[str, Any]):
        """
        Create a new event.
        
        Args:
            event_data: Event data dictionary
        """
        try:
            # Extract sync_to from data
            sync_to = event_data.pop('sync_to', None)
            
            # Create event
            event_id = self.calendar_manager.create_event(
                event_data,
                sync_to=sync_to
            )
            
            logger.info(f"Created event: {event_id}")
            
            # Refresh current view
            self._refresh_current_view()
            
            # Show success message
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.information(
                self,
                "Success",
                "Event created successfully!"
            )
            
        except Exception as e:
            logger.error(f"Error creating event: {e}")
            raise
    
    def _update_event(self, event_data: Dict[str, Any]):
        """
        Update an existing event.
        
        Args:
            event_data: Event data dictionary
        """
        try:
            # Extract event ID
            event_id = event_data.pop('id')
            
            # Remove sync_to (not used for updates)
            event_data.pop('sync_to', None)
            
            # Update event
            self.calendar_manager.update_event(event_id, event_data)
            
            logger.info(f"Updated event: {event_id}")
            
            # Refresh current view
            self._refresh_current_view()
            
            # Show success message
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.information(
                self,
                "Success",
                "Event updated successfully!"
            )
            
        except Exception as e:
            logger.error(f"Error updating event: {e}")
            raise
    
    def _refresh_current_view(self):
        """Refresh the current calendar view."""
        if self.current_view == 'month':
            self.month_view.refresh_view()
        elif self.current_view == 'week':
            self.week_view.refresh_view()
        else:  # day
            self.day_view.refresh_view()
    
    def show_add_account_dialog(self):
        """Show dialog to add external calendar account."""
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QPushButton
        
        # Create simple provider selection dialog
        dialog = QDialog(self)
        dialog.setWindowTitle("Add Calendar Account")
        dialog.setMinimumWidth(300)
        
        layout = QVBoxLayout(dialog)
        
        # Google Calendar button
        google_btn = QPushButton("Connect Google Calendar")
        google_btn.clicked.connect(
            lambda: self._start_oauth_flow('google', dialog)
        )
        layout.addWidget(google_btn)
        
        # Outlook Calendar button
        outlook_btn = QPushButton("Connect Outlook Calendar")
        outlook_btn.clicked.connect(
            lambda: self._start_oauth_flow('outlook', dialog)
        )
        layout.addWidget(outlook_btn)
        
        # Cancel button
        cancel_btn = QPushButton(self.i18n.t('common.cancel'))
        cancel_btn.clicked.connect(dialog.reject)
        layout.addWidget(cancel_btn)
        
        dialog.exec()
    
    def _start_oauth_flow(self, provider: str, parent_dialog: QDialog):
        """
        Start OAuth authorization flow.
        
        Args:
            provider: Provider name (google/outlook)
            parent_dialog: Parent dialog to close
        """
        try:
            # Get sync adapter
            if provider not in self.calendar_manager.sync_adapters:
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.warning(
                    self,
                    "Error",
                    f"{provider.capitalize()} calendar sync is not configured."
                )
                return
            
            adapter = self.calendar_manager.sync_adapters[provider]
            
            # Get authorization URL
            auth_url = adapter.get_authorization_url()
            
            # Close parent dialog
            parent_dialog.accept()
            
            # Show OAuth dialog
            from ui.calendar_hub.oauth_dialog import OAuthDialog
            
            oauth_dialog = OAuthDialog(
                provider,
                auth_url,
                self.i18n,
                self
            )
            
            # Connect signals
            oauth_dialog.authorization_complete.connect(
                lambda code: self._complete_oauth_flow(provider, code)
            )
            oauth_dialog.authorization_failed.connect(
                lambda error: self._handle_oauth_error(provider, error)
            )
            
            oauth_dialog.exec()
            
        except Exception as e:
            logger.error(f"Error starting OAuth flow: {e}")
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to start authorization: {str(e)}"
            )
    
    def _complete_oauth_flow(self, provider: str, code: str):
        """
        Complete OAuth authorization flow.
        
        Args:
            provider: Provider name
            code: Authorization code
        """
        try:
            # Get sync adapter
            adapter = self.calendar_manager.sync_adapters[provider]
            
            # Exchange code for token
            token_data = adapter.exchange_code_for_token(code)
            
            # Store token using OAuthManager
            self.oauth_manager.store_token(
                provider=provider,
                access_token=token_data['access_token'],
                refresh_token=token_data.get('refresh_token'),
                expires_in=token_data.get('expires_in'),
                token_type=token_data.get('token_type', 'Bearer')
            )
            
            # Update adapter with stored token
            adapter.access_token = token_data['access_token']
            adapter.refresh_token = token_data.get('refresh_token')
            
            # Get user email (try to fetch from provider)
            email = self._get_user_email(provider, adapter)
            
            # Create CalendarSyncStatus record
            from data.database.models import CalendarSyncStatus
            
            sync_status = CalendarSyncStatus(
                provider=provider,
                user_email=email,
                is_active=True
            )
            sync_status.save(self.calendar_manager.db)
            
            # Add connected account badge
            self.add_connected_account(provider, email)
            
            # Trigger initial sync
            try:
                self.calendar_manager.sync_external_calendar(provider)
            except Exception as sync_error:
                logger.warning(f"Initial sync failed: {sync_error}")
            
            # Refresh view
            self._refresh_current_view()
            
            # Show success message
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.information(
                self,
                "Success",
                f"Successfully connected {provider.capitalize()} calendar!"
            )
            
            logger.info(f"OAuth flow completed for {provider}")
            
        except Exception as e:
            logger.error(f"Error completing OAuth flow: {e}")
            self._handle_oauth_error(provider, str(e))
    
    def _get_user_email(self, provider: str, adapter) -> str:
        """
        Get user email from provider.
        
        Args:
            provider: Provider name
            adapter: Sync adapter instance
            
        Returns:
            User email or default
        """
        try:
            import httpx
            
            if provider == 'google':
                # Get user info from Google
                with httpx.Client() as client:
                    response = client.get(
                        'https://www.googleapis.com/oauth2/v2/userinfo',
                        headers={'Authorization': f'Bearer {adapter.access_token}'},
                        timeout=10.0
                    )
                    if response.status_code == 200:
                        data = response.json()
                        return data.get('email', 'user@gmail.com')
            
            elif provider == 'outlook':
                # Get user info from Microsoft Graph
                with httpx.Client() as client:
                    response = client.get(
                        'https://graph.microsoft.com/v1.0/me',
                        headers={'Authorization': f'Bearer {adapter.access_token}'},
                        timeout=10.0
                    )
                    if response.status_code == 200:
                        data = response.json()
                        return data.get('mail') or data.get('userPrincipalName', 'user@outlook.com')
            
        except Exception as e:
            logger.warning(f"Could not fetch user email: {e}")
        
        return f'user@{provider}.com'
    
    def _handle_oauth_error(self, provider: str, error: str):
        """
        Handle OAuth authorization error.
        
        Args:
            provider: Provider name
            error: Error message
        """
        from PyQt6.QtWidgets import QMessageBox
        
        QMessageBox.critical(
            self,
            "Authorization Failed",
            f"Failed to connect {provider.capitalize()} calendar:\n{error}"
        )
        
        logger.error(f"OAuth error for {provider}: {error}")
    
    def add_connected_account(self, provider: str, email: str):
        """
        Add a connected account badge.
        
        Args:
            provider: Provider name (google/outlook)
            email: User email
        """
        # Don't add if already exists
        if provider in self.connected_accounts:
            logger.debug(f"Account badge for {provider} already exists")
            return
        
        # Create account badge
        badge = QFrame()
        badge.setObjectName(f'account_badge_{provider}')
        badge.setStyleSheet("""
            QFrame {
                background-color: #f0f0f0;
                border: 1px solid #ccc;
                border-radius: 4px;
            }
        """)
        badge_layout = QHBoxLayout(badge)
        badge_layout.setContentsMargins(8, 4, 8, 4)
        badge_layout.setSpacing(5)
        
        # Status indicator
        indicator = QLabel('●')
        indicator.setObjectName(f'indicator_{provider}')
        color = '#EA4335' if provider == 'google' else '#FF6F00'
        indicator.setStyleSheet(f'color: {color}; font-size: 12px;')
        badge_layout.addWidget(indicator)
        
        # Account info
        info_label = QLabel(f'{provider.capitalize()} ({email})')
        badge_layout.addWidget(info_label)
        
        # Disconnect button
        disconnect_btn = QPushButton('×')
        disconnect_btn.setFixedSize(20, 20)
        disconnect_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                color: #666;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                color: #f00;
            }
        """)
        disconnect_btn.clicked.connect(
            lambda: self.disconnect_account(provider)
        )
        badge_layout.addWidget(disconnect_btn)
        
        # Add to container
        self.accounts_container_layout.addWidget(badge)
        
        # Store reference
        self.connected_accounts[provider] = email
        
        logger.info(f"Added connected account: {provider} - {email}")
    
    def remove_connected_account(self, provider: str):
        """
        Remove a connected account badge.
        
        Args:
            provider: Provider name (google/outlook)
        """
        if provider in self.connected_accounts:
            # Find and remove badge
            for i in range(self.accounts_container_layout.count()):
                widget = self.accounts_container_layout.itemAt(i).widget()
                badge_name = f'account_badge_{provider}'
                if widget and widget.objectName() == badge_name:
                    widget.deleteLater()
                    break
            
            # Remove from dict
            del self.connected_accounts[provider]
            
            logger.info(f"Removed connected account: {provider}")
    
    def disconnect_account(self, provider: str):
        """
        Disconnect an external calendar account.
        
        Args:
            provider: Provider name (google/outlook)
        """
        try:
            from PyQt6.QtWidgets import QMessageBox
            from data.database.models import CalendarSyncStatus
            
            # Confirm with user
            reply = QMessageBox.question(
                self,
                "Disconnect Account",
                f"Are you sure you want to disconnect {provider.capitalize()} calendar?\n\n"
                f"This will:\n"
                f"- Remove all synced events from {provider.capitalize()}\n"
                f"- Delete stored OAuth tokens\n"
                f"- Stop automatic synchronization",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            
            if reply != QMessageBox.StandardButton.Yes:
                return
            
            # Delete OAuth token
            self.oauth_manager.delete_token(provider)
            
            # Delete CalendarSyncStatus
            sync_status = CalendarSyncStatus.get_by_provider(
                self.calendar_manager.db,
                provider
            )
            if sync_status:
                sync_status.delete(self.calendar_manager.db)
            
            # Delete all events from this provider
            query = "DELETE FROM calendar_events WHERE source = ?"
            self.calendar_manager.db.execute(query, (provider,), commit=True)
            
            # Revoke access with provider (if adapter supports it)
            if provider in self.calendar_manager.sync_adapters:
                try:
                    adapter = self.calendar_manager.sync_adapters[provider]
                    adapter.revoke_access()
                except Exception as e:
                    logger.warning(f"Could not revoke access: {e}")
            
            # Remove account badge
            self.remove_connected_account(provider)
            
            # Refresh view
            self._refresh_current_view()
            
            # Show success message
            QMessageBox.information(
                self,
                "Success",
                f"Successfully disconnected {provider.capitalize()} calendar."
            )
            
            logger.info(f"Disconnected account: {provider}")
            
        except Exception as e:
            logger.error(f"Error disconnecting account: {e}")
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to disconnect account: {str(e)}"
            )
    
    def _on_sync_now_clicked(self):
        """Handle sync now button click."""
        try:
            if not self.connected_accounts:
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.information(
                    self,
                    "No Accounts",
                    "No external calendar accounts connected. "
                    "Please add an account first."
                )
                return
            
            # Update UI to show syncing
            self.sync_now_btn.setEnabled(False)
            self.sync_status_label.setText("Syncing...")
            self.sync_status_label.setStyleSheet("color: #2196F3; font-size: 11px;")
            
            # Sync all connected accounts
            success_count = 0
            error_count = 0
            
            for provider in self.connected_accounts.keys():
                try:
                    self.calendar_manager.sync_external_calendar(provider)
                    success_count += 1
                    logger.info(f"Successfully synced {provider}")
                except Exception as e:
                    error_count += 1
                    logger.error(f"Failed to sync {provider}: {e}")
            
            # Refresh view
            self._refresh_current_view()
            
            # Update sync status
            self._update_sync_status()
            
            # Show result
            from PyQt6.QtWidgets import QMessageBox
            if error_count == 0:
                QMessageBox.information(
                    self,
                    "Sync Complete",
                    f"Successfully synced {success_count} calendar(s)."
                )
            else:
                QMessageBox.warning(
                    self,
                    "Sync Completed with Errors",
                    f"Synced {success_count} calendar(s), "
                    f"{error_count} failed. Check logs for details."
                )
            
        except Exception as e:
            logger.error(f"Error during manual sync: {e}")
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(
                self,
                "Sync Error",
                f"Failed to sync calendars: {str(e)}"
            )
        finally:
            # Re-enable sync button
            self.sync_now_btn.setEnabled(True)
    
    def _update_sync_status(self):
        """Update sync status label with last sync time."""
        try:
            from data.database.models import CalendarSyncStatus
            from datetime import datetime
            
            # Get most recent sync time from all accounts
            sync_statuses = CalendarSyncStatus.get_all_active(
                self.calendar_manager.db
            )
            
            if not sync_statuses:
                self.sync_status_label.setText('')
                return
            
            # Find most recent sync
            most_recent = None
            for status in sync_statuses:
                if status.last_sync_time:
                    sync_time = datetime.fromisoformat(status.last_sync_time)
                    if most_recent is None or sync_time > most_recent:
                        most_recent = sync_time
            
            if most_recent:
                # Calculate time ago
                now = datetime.now()
                delta = now - most_recent
                
                if delta.total_seconds() < 60:
                    time_ago = "just now"
                elif delta.total_seconds() < 3600:
                    minutes = int(delta.total_seconds() / 60)
                    time_ago = f"{minutes}m ago"
                elif delta.total_seconds() < 86400:
                    hours = int(delta.total_seconds() / 3600)
                    time_ago = f"{hours}h ago"
                else:
                    days = int(delta.total_seconds() / 86400)
                    time_ago = f"{days}d ago"
                
                self.sync_status_label.setText(f"Last sync: {time_ago}")
                self.sync_status_label.setStyleSheet("color: #666; font-size: 11px;")
            else:
                self.sync_status_label.setText("Never synced")
                self.sync_status_label.setStyleSheet("color: #999; font-size: 11px;")
                
        except Exception as e:
            logger.error(f"Error updating sync status: {e}")
            self.sync_status_label.setText('')
    
    def update_translations(self):
        """Update all UI text when language changes."""
        # Update title
        self.title_label.setText(self.i18n.t('calendar_hub.title'))
        
        # Update toolbar buttons
        self.month_btn.setText(self.i18n.t('calendar_hub.view_month'))
        self.week_btn.setText(self.i18n.t('calendar_hub.view_week'))
        self.day_btn.setText(self.i18n.t('calendar_hub.view_day'))
        self.today_btn.setText(self.i18n.t('calendar_hub.today'))
        self.create_event_btn.setText(self.i18n.t('calendar_hub.create_event'))
        
        # Update accounts section
        self.accounts_label.setText(
            self.i18n.t('calendar_hub.connected_accounts') + ':'
        )
        self.sync_now_btn.setText('🔄 ' + self.i18n.t('calendar_hub.sync_now'))
        self.sync_now_btn.setToolTip(self.i18n.t('calendar_hub.sync_now_tooltip'))
        self.add_account_btn.setText(
            '+ ' + self.i18n.t('calendar_hub.add_account')
        )
    
    def _on_language_changed(self, language: str):
        """
        Handle language change event.
        
        Args:
            language: New language code
        """
        logger.debug(f"Updating calendar hub text for language: {language}")
        self.update_translations()
    
    def _load_connected_accounts(self):
        """Load existing connected accounts from database."""
        try:
            from data.database.models import CalendarSyncStatus
            
            # Get all active sync statuses
            sync_statuses = CalendarSyncStatus.get_all_active(
                self.calendar_manager.db
            )
            
            for status in sync_statuses:
                email = status.user_email or 'user@example.com'
                self.add_connected_account(status.provider, email)
                
            logger.info(f"Loaded {len(sync_statuses)} connected accounts")
            
            # Update sync status display
            self._update_sync_status()
            
        except Exception as e:
            logger.error(f"Error loading connected accounts: {e}")
