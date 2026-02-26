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
Calendar Hub Widget for EchoNote.

Provides the main calendar interface with view switching, date navigation,
and account management.
"""

import logging
import threading
from datetime import datetime
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlparse

from config.constants import (
    DEFAULT_TRANSLATION_TARGET_LANGUAGE,
    TRANSLATION_LANGUAGE_AUTO,
)
from core.settings.manager import resolve_translation_languages_from_settings
from core.qt_imports import (
    QButtonGroup,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
    Signal,
)

from core.calendar.constants import CalendarSource
from core.calendar.exceptions import SyncError
from ui.base_widgets import (
    BaseWidget,
    connect_button_with_callback,
    create_button,
    create_primary_button,
)
from ui.common.audio_player_launcher import open_or_activate_audio_player
from ui.common.style_utils import set_widget_state
from ui.common.text_viewer_launcher import (
    open_or_activate_text_viewer,
    resolve_text_viewer_initial_mode,
)
from ui.common.translation_task_options import (
    enqueue_event_translation_task,
    prompt_event_translation_languages,
)
from ui.constants import (
    CALENDAR_ADD_ACCOUNT_DIALOG_MIN_WIDTH,
    NAV_SYMBOL_NEXT,
    NAV_SYMBOL_PREV,
    PAGE_COMPACT_SPACING,
    PAGE_DENSE_SPACING,
    ROLE_CALENDAR_NAV_ACTION,
    ROLE_CALENDAR_PRIMARY_ACTION,
    ROLE_CALENDAR_UTILITY_ACTION,
    ROLE_CALENDAR_VIEW_TOGGLE,
    ROLE_SYNC_STATUS,
    ROLE_ACCOUNT_BADGE,
    ROLE_ACCOUNT_DISCONNECT,
    ROLE_CALENDAR_INDICATOR,
    STATUS_INDICATOR_SYMBOL,
    ZERO_MARGINS,
)
from utils.i18n import I18nQtManager
from utils.time_utils import now_local, to_local_datetime

logger = logging.getLogger("echonote.ui.calendar_hub")


class CalendarHubWidget(BaseWidget):
    """
    Main calendar hub widget with view switching and navigation.

    Provides:
    - View switching (month/week/day)
    - Date navigation
    - Connected accounts display
    - Event creation
    """

    # Signals
    view_changed = Signal(str)  # month/week/day
    date_changed = Signal(object)  # datetime
    create_event_requested = Signal()
    add_account_requested = Signal()
    manual_sync_finished = Signal(int, int, str)  # success_count, error_count, fatal_error
    oauth_connect_finished = Signal(object)  # {"provider": str, "success": bool, ...}

    def __init__(
        self,
        calendar_manager,
        oauth_manager,
        i18n: I18nQtManager,
        transcription_manager: Optional[Any] = None,
        parent: Optional[QWidget] = None,
    ):
        """
        Initialize calendar hub widget.

        Args:
            calendar_manager: CalendarManager instance
            oauth_manager: OAuthManager instance
            i18n: Internationalization manager
            parent: Parent widget
        """
        super().__init__(i18n, parent)

        self.calendar_manager = calendar_manager
        self.oauth_manager = oauth_manager
        self.transcription_manager = transcription_manager
        self._config_manager = None

        # Current view and date
        self.current_view = self._load_default_view()
        self.current_date = None  # Will be set by calendar view

        # Connected accounts
        self.connected_accounts: Dict[str, Optional[str]] = {}
        self._manual_sync_thread: Optional[threading.Thread] = None
        self._oauth_connect_thread: Optional[threading.Thread] = None
        self._audio_player_dialogs: Dict[str, QDialog] = {}
        self._text_viewer_dialogs: Dict[str, QDialog] = {}

        # Setup UI
        self.setup_ui()

        # Connect language change signal
        self.i18n.language_changed.connect(self._on_language_changed)
        self.manual_sync_finished.connect(self._on_manual_sync_finished)
        self.oauth_connect_finished.connect(self._on_oauth_connect_finished)

        # Load existing connected accounts
        self._load_connected_accounts()

        logger.debug("CalendarHubWidget initialized")

    def setup_ui(self):
        """Set up the calendar hub UI."""
        # Main layout
        layout = self.create_page_layout()

        # Title
        self.title_label = self.create_page_title("calendar_hub.title", layout)

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
        toolbar, toolbar_layout = self.create_row_container(
            margins=ZERO_MARGINS,
            spacing=PAGE_COMPACT_SPACING,
        )

        # View switching buttons
        view_group = QButtonGroup(self)
        view_group.setExclusive(True)

        self.month_btn = create_button(self.i18n.t("calendar_hub.view_month"))
        self.month_btn.setCheckable(True)
        self.month_btn.setProperty("role", ROLE_CALENDAR_VIEW_TOGGLE)
        view_group.addButton(self.month_btn)

        self.week_btn = create_button(self.i18n.t("calendar_hub.view_week"))
        self.week_btn.setCheckable(True)
        self.week_btn.setChecked(self.current_view == "week")
        self.week_btn.setProperty("role", ROLE_CALENDAR_VIEW_TOGGLE)
        view_group.addButton(self.week_btn)

        self.day_btn = create_button(self.i18n.t("calendar_hub.view_day"))
        self.day_btn.setCheckable(True)
        self.day_btn.setChecked(self.current_view == "day")
        self.day_btn.setProperty("role", ROLE_CALENDAR_VIEW_TOGGLE)
        view_group.addButton(self.day_btn)

        self.month_btn.setChecked(self.current_view == "month")

        # Connect view buttons using helper
        from ui.signal_helpers import connect_view_buttons

        connect_view_buttons(self.month_btn, self.week_btn, self.day_btn, self._on_view_changed)

        toolbar_layout.addWidget(self.month_btn)
        toolbar_layout.addWidget(self.week_btn)
        toolbar_layout.addWidget(self.day_btn)

        toolbar_layout.addSpacing(PAGE_COMPACT_SPACING)

        # Date navigation
        self.prev_btn = create_button(NAV_SYMBOL_PREV)
        self.prev_btn.setProperty("role", ROLE_CALENDAR_NAV_ACTION)
        self.prev_btn.setToolTip(self.i18n.t("calendar_hub.widget.previous"))
        self.today_btn = create_button(self.i18n.t("calendar_hub.today"))
        self.today_btn.setProperty("role", ROLE_CALENDAR_NAV_ACTION)

        self.next_btn = create_button(NAV_SYMBOL_NEXT)
        self.next_btn.setProperty("role", ROLE_CALENDAR_NAV_ACTION)
        self.next_btn.setToolTip(self.i18n.t("calendar_hub.widget.next"))

        # Connect navigation buttons using helper
        from ui.signal_helpers import connect_navigation_buttons

        connect_navigation_buttons(
            self.prev_btn,
            self.next_btn,
            self.today_btn,
            self._on_prev_clicked,
            self._on_next_clicked,
            self._on_today_clicked,
        )

        toolbar_layout.addWidget(self.prev_btn)
        toolbar_layout.addWidget(self.today_btn)
        toolbar_layout.addWidget(self.next_btn)

        toolbar_layout.addStretch()

        # Create event button
        self.create_event_btn = create_primary_button(self.i18n.t("calendar_hub.create_event"))
        self.create_event_btn.setProperty("role", ROLE_CALENDAR_PRIMARY_ACTION)
        self.create_event_btn.clicked.connect(lambda: self._show_event_dialog())
        toolbar_layout.addWidget(self.create_event_btn)

        return toolbar

    def _create_accounts_section(self) -> QWidget:
        """
        Create connected accounts display section.

        Returns:
            Accounts section widget
        """
        accounts_widget, accounts_layout = self.create_row_container(
            margins=ZERO_MARGINS,
            spacing=PAGE_COMPACT_SPACING,
        )

        # Connected accounts label
        self.accounts_label = QLabel(self.i18n.t("calendar_hub.connected_accounts") + ":")
        accounts_layout.addWidget(self.accounts_label)

        # Container for account badges
        self.accounts_container = QWidget()
        self.accounts_container_layout = QHBoxLayout(self.accounts_container)
        self.accounts_container_layout.setContentsMargins(*ZERO_MARGINS)
        self.accounts_container_layout.setSpacing(PAGE_DENSE_SPACING)
        accounts_layout.addWidget(self.accounts_container)

        accounts_layout.addStretch()

        # Sync status label
        self.sync_status_label = QLabel("")
        self.sync_status_label.setProperty("role", ROLE_SYNC_STATUS)
        accounts_layout.addWidget(self.sync_status_label)

        # Sync now button
        self.sync_now_btn = create_button(self.i18n.t("calendar_hub.sync_now"))
        self.sync_now_btn.setProperty("role", ROLE_CALENDAR_UTILITY_ACTION)
        self.sync_now_btn.setToolTip(self.i18n.t("calendar_hub.sync_now_tooltip"))
        self.sync_now_btn.clicked.connect(self._on_sync_now_clicked)
        accounts_layout.addWidget(self.sync_now_btn)

        # Add account button
        self.add_account_btn = create_button(self.i18n.t("calendar_hub.add_account"))
        self.add_account_btn.setProperty("role", ROLE_CALENDAR_UTILITY_ACTION)
        self.add_account_btn.clicked.connect(self.show_add_account_dialog)
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
        from ui.calendar_hub.calendar_view import DayView, MonthView, WeekView

        # Create actual calendar views
        self.month_view = MonthView(self.calendar_manager, self.i18n)
        self.week_view = WeekView(self.calendar_manager, self.i18n)
        self.day_view = DayView(self.calendar_manager, self.i18n)

        # Keep all views aligned to one shared date cursor.
        shared_date = self.week_view.current_date
        self.month_view.set_date(shared_date)
        self.day_view.set_date(shared_date)
        self.current_date = shared_date

        # Connect view signals
        self.month_view.date_changed.connect(self._on_date_changed)
        self.month_view.event_clicked.connect(self._on_event_clicked)
        self.month_view.date_clicked.connect(self._on_calendar_date_clicked)

        self.week_view.date_changed.connect(self._on_date_changed)
        self.week_view.event_clicked.connect(self._on_event_clicked)
        self.week_view.date_clicked.connect(self._on_calendar_date_clicked)

        self.day_view.date_changed.connect(self._on_date_changed)
        self.day_view.event_clicked.connect(self._on_event_clicked)

        # Add views to container
        container.addWidget(self.month_view)
        container.addWidget(self.week_view)
        container.addWidget(self.day_view)

        view_index = {"month": 0, "week": 1, "day": 2}
        container.setCurrentIndex(view_index.get(self.current_view, 1))

        return container

    def _load_default_view(self) -> str:
        """Load the preferred initial calendar view from config."""
        valid_views = {"month", "week", "day"}
        default_view = "week"

        try:
            if self._config_manager is None:
                from config.app_config import ConfigManager

                self._config_manager = ConfigManager()

            configured = self._config_manager.get("calendar.default_view")
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.warning("Failed to load calendar.default_view from config: %s", exc)
            return default_view

        if isinstance(configured, str):
            normalized = configured.strip().lower()
            if normalized in valid_views:
                return normalized

        if configured is not None:
            logger.warning("Invalid calendar.default_view value: %r; using week view", configured)

        return default_view

    def _on_view_changed(self, view: str):
        """
        Handle view change.

        Args:
            view: View name (month/week/day)
        """
        self.current_view = view

        # Update view container
        view_index = {"month": 0, "week": 1, "day": 2}
        self.view_container.setCurrentIndex(view_index[view])

        # Keep target view in sync with the global date cursor.
        target_view = {"month": self.month_view, "week": self.week_view, "day": self.day_view}[view]
        if self.current_date is not None:
            target_view.set_date(self.current_date)

        # Emit signal
        self.view_changed.emit(view)

        logger.debug(f"View changed to: {view}")

    def _on_prev_clicked(self):
        """Handle previous button click."""
        if self.current_view == "month":
            self.month_view.prev_month()
        elif self.current_view == "week":
            self.week_view.prev_week()
        else:  # day
            self.day_view.prev_day()

        logger.debug("Previous button clicked")

    def _on_today_clicked(self):
        """Handle today button click."""
        if self.current_view == "month":
            self.month_view.today()
        elif self.current_view == "week":
            self.week_view.today()
        else:  # day
            self.day_view.today()

        logger.debug("Today button clicked")

    def _on_next_clicked(self):
        """Handle next button click."""
        if self.current_view == "month":
            self.month_view.next_month()
        elif self.current_view == "week":
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

    def _on_calendar_date_clicked(self, date: datetime):
        """
        Handle clicking on an empty date cell to create a new event.

        Args:
            date: The datetime that was clicked
        """
        self._show_event_dialog(default_date=date)

    def _show_event_dialog(self, event=None, default_date: Optional[datetime] = None):
        """
        Show event creation/editing dialog.

        Args:
            event: Optional event data for editing
            default_date: Optional default datetime for creating a new event
        """
        from ui.calendar_hub.event_dialog import EventDialog

        # Prepare event data for dialog
        event_data = None
        if event:
            auto_transcribe = False
            enable_translation = False
            translation_target_lang = None
            try:
                from data.database.models import AutoTaskConfig

                config = AutoTaskConfig.get_by_event_id(self.calendar_manager.db, event.id)
                if config:
                    auto_transcribe = config.enable_transcription
                    enable_translation = config.enable_translation
                    translation_target_lang = config.translation_target_language
            except Exception as e:
                logger.warning(f"Failed to fetch AutoTaskConfig for event {event.id}: {e}")

            event_data = {
                "id": event.id,
                "title": event.title,
                "event_type": event.event_type,
                "start_time": event.start_time,
                "end_time": event.end_time,
                "location": event.location,
                "attendees": event.attendees,
                "description": event.description,
                "reminder_minutes": event.reminder_minutes,
                "auto_transcribe": auto_transcribe,
                "enable_translation": enable_translation,
                "translation_target_lang": translation_target_lang,
            }
        elif default_date:
            now = now_local()
            from datetime import timedelta

            if default_date.date() == now.date():
                start_dt = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
            else:
                start_dt = default_date.replace(hour=9, minute=0, second=0, microsecond=0)
            end_dt = start_dt + timedelta(hours=1)
            event_data = {
                "start_time": start_dt.isoformat(),
                "end_time": end_dt.isoformat(),
            }

        # Show dialog
        recording_path = None
        transcript_path = None
        translation_path = None
        allow_retranscribe = False
        is_past = False

        now = now_local()

        if event:
            try:
                from data.database.models import EventAttachment

                attachments = EventAttachment.get_by_event_id(self.calendar_manager.db, event.id)
                for attachment in attachments:
                    if attachment.attachment_type == "recording":
                        recording_path = attachment.file_path
                    elif attachment.attachment_type == "transcript":
                        transcript_path = attachment.file_path
                    elif attachment.attachment_type == "translation":
                        translation_path = attachment.file_path

                # Check if event is in the past
                start_time = to_local_datetime(event.start_time)
                if start_time < now:
                    is_past = True
                    if recording_path and self.transcription_manager:
                        allow_retranscribe = True

            except Exception as e:
                logger.warning(
                    f"Failed to fetch attachments or parse time for event {event.id}: {e}"
                )
        elif default_date:
            # Check if default_date is in the past for new events
            # default_date is typically naive from what I saw in calendar_view
            if default_date < now:
                is_past = True

        is_translation_available = False
        if self.transcription_manager and getattr(
            self.transcription_manager, "translation_engine", None
        ):
            is_translation_available = True

        dialog = EventDialog(
            self.i18n,
            self.connected_accounts,
            event_data,
            parent=self,
            allow_retranscribe=allow_retranscribe,
            is_past=is_past,
            is_translation_available=is_translation_available,
            recording_path=recording_path,
            transcript_path=transcript_path,
            translation_path=translation_path,
        )

        if allow_retranscribe and recording_path:
            dialog.secondary_transcribe_requested.connect(
                lambda data, p=recording_path, eid=event.id: self._on_secondary_transcribe_requested(
                    eid, p, data
                )
            )
        if event and (transcript_path or translation_path):
            dialog.view_text_requested.connect(
                lambda requester, p=transcript_path, tr=translation_path: self._open_event_text_viewer(
                    transcript_path=p,
                    translation_path=tr,
                    parent_hint=requester,
                )
            )
        if event and recording_path:
            dialog.view_recording_requested.connect(
                lambda requester, file_path, p=transcript_path, tr=translation_path: self._on_view_recording(
                    file_path=file_path,
                    transcript_path=p,
                    translation_path=tr,
                    parent_hint=requester,
                )
            )
        if event and transcript_path:
            dialog.translate_transcript_requested.connect(
                lambda eid=event.id, p=transcript_path: self._on_translate_transcript_requested(
                    event_id=eid,
                    transcript_path=p,
                )
            )

        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Get event data
            data = dialog.get_event_data()

            if data:
                try:
                    if event and dialog.is_delete_requested():
                        self._delete_event(str(data.get("id", "")))
                    elif event:
                        # Update existing event
                        self._update_event(data)
                    else:
                        # Create new event
                        self._create_event(data)

                except SyncError as e:
                    logger.warning(f"Event saved with sync errors: {e}")
                    self.show_warning(
                        self.i18n.t("common.warning"),
                        self.i18n.t("calendar.warning.sync_failed", error=str(e)),
                    )
                except Exception as e:
                    logger.error(f"Error saving event: {e}")

                    self.show_error(
                        self.i18n.t("common.error"),
                        self.i18n.t("calendar.error.save_failed", error=str(e)),
                    )

    def _create_event(self, event_data: Dict[str, Any]):
        """
        Create a new event.

        Args:
            event_data: Event data dictionary
        """
        try:
            # Extract sync_to from data
            sync_to = event_data.pop("sync_to", None)

            # Create event
            event_id = self.calendar_manager.create_event(event_data, sync_to=sync_to)

            logger.info(f"Created event: {event_id}")

            # Refresh current view
            self._refresh_current_view()

            # Show success message
            self.show_info(
                self.i18n.t("common.success"),
                self.i18n.t("calendar.success.event_created"),
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
            event_id = event_data.pop("id")

            # Remove sync_to (not used for updates)
            event_data.pop("sync_to", None)

            # Update event
            self.calendar_manager.update_event(event_id, event_data)

            logger.info(f"Updated event: {event_id}")

            # Refresh current view
            self._refresh_current_view()

            # Show success message

            self.show_info(
                self.i18n.t("common.success"),
                self.i18n.t("calendar.success.event_updated"),
            )

        except Exception as e:
            logger.error(f"Error updating event: {e}")
            raise

    def _delete_event(self, event_id: str):
        """Delete an event with confirmation and optional export."""
        if not event_id:
            self.show_warning(
                self.i18n.t("common.warning"),
                self.i18n.t("calendar.error.event_not_found"),
            )
            return

        event = self.calendar_manager.get_event(event_id)
        if not event:
            self.show_warning(
                self.i18n.t("common.warning"),
                self.i18n.t("calendar.error.event_not_found"),
            )
            return

        from ui.calendar_event_actions import confirm_and_delete_event

        confirm_and_delete_event(
            parent=self,
            i18n=self.i18n,
            calendar_manager=self.calendar_manager,
            event=event,
            on_deleted=self._refresh_current_view,
        )

    def _refresh_current_view(self):
        """Refresh the current calendar view."""
        if self.current_view == "month":
            self.month_view.refresh_view()
        elif self.current_view == "week":
            self.week_view.refresh_view()
        else:  # day
            self.day_view.refresh_view()

    def show_add_account_dialog(self):
        """Show dialog to add external calendar account."""
        # Create simple provider selection dialog
        dialog = QDialog(self)
        dialog.setWindowTitle(self.i18n.t("calendar_hub.widget.add_calendar_account"))
        dialog.setMinimumWidth(CALENDAR_ADD_ACCOUNT_DIALOG_MIN_WIDTH)

        layout = QVBoxLayout(dialog)

        # Google Calendar button
        google_btn = create_button(self.i18n.t("calendar_hub.widget.connect_google"))
        google_btn.clicked.connect(lambda: self._start_oauth_flow(CalendarSource.GOOGLE, dialog))
        layout.addWidget(google_btn)

        # Outlook Calendar button
        outlook_btn = create_button(self.i18n.t("calendar_hub.widget.connect_outlook"))
        outlook_btn.clicked.connect(lambda: self._start_oauth_flow(CalendarSource.OUTLOOK, dialog))
        layout.addWidget(outlook_btn)

        # Cancel button
        cancel_btn = create_button(self.i18n.t("common.cancel"))
        connect_button_with_callback(cancel_btn, dialog.reject)
        layout.addWidget(cancel_btn)

        dialog.exec()

    def _start_oauth_flow(self, provider: str, parent_dialog: Optional[QDialog] = None):
        """
        Start OAuth authorization flow.

        Args:
            provider: Provider name (google/outlook)
            parent_dialog: Parent dialog to close
        """
        try:
            # Get sync adapter
            if provider not in self.calendar_manager.sync_adapters:

                provider_name = self._get_provider_display_name(provider)
                self.show_warning(
                    self.i18n.t("common.error"),
                    self.i18n.t("calendar.error.sync_not_configured", provider=provider_name),
                )
                return

            adapter = self.calendar_manager.sync_adapters[provider]

            # Get authorization request parameters
            auth_request = adapter.get_authorization_url()
            if not isinstance(auth_request, dict):
                raise TypeError(
                    self.i18n.t("exceptions.calendar_hub.expected_authorization_request_payload")
                )

            authorization_url = auth_request.get("authorization_url")
            state = auth_request.get("state")
            code_verifier = auth_request.get("code_verifier")

            if not authorization_url or not state or not code_verifier:
                raise ValueError(
                    self.i18n.t("exceptions.calendar_hub.authorization_request_missing_pkce")
                )

            # Close parent dialog
            if parent_dialog is not None:
                parent_dialog.accept()

            # Show OAuth dialog
            from ui.calendar_hub.oauth_dialog import OAuthDialog

            callback_host, callback_port = self._load_oauth_callback_settings(provider)

            oauth_dialog = OAuthDialog(
                provider,
                authorization_url,
                self.i18n,
                self,
                callback_host=callback_host,
                callback_port=callback_port,
                state=state,
                code_verifier=code_verifier,
            )

            # Connect signals
            oauth_dialog.authorization_complete.connect(
                lambda code, verifier: self._complete_oauth_flow(provider, code, verifier)
            )
            oauth_dialog.authorization_failed.connect(
                lambda error: self._handle_oauth_error(provider, error)
            )

            oauth_dialog.exec()

        except Exception as e:
            logger.error(f"Error starting OAuth flow: {e}")

            self.show_error(
                self.i18n.t("common.error"),
                self.i18n.t("calendar.error.auth_failed", error=str(e)),
            )

    def start_oauth_flow(self, provider: str) -> None:
        """Public wrapper used by other pages to connect a provider account."""
        self._start_oauth_flow(provider, parent_dialog=None)

    def _load_oauth_callback_settings(self, provider: str) -> Tuple[Optional[str], Optional[int]]:
        """Load configured OAuth callback host and port."""
        host: Optional[str] = None
        port: Optional[int] = None

        try:
            if self._config_manager is None:
                from config.app_config import ConfigManager

                self._config_manager = ConfigManager()

            port_value = self._config_manager.get("calendar.oauth.callback_port")
            if port_value is not None:
                port = int(port_value)

            redirect_uri = self._config_manager.get("calendar.oauth.redirect_uri")
            if redirect_uri:
                parsed = urlparse(redirect_uri)
                host = parsed.hostname or host
                if parsed.port:
                    port = parsed.port

        except Exception as exc:
            logger.warning("Unable to load OAuth callback configuration for %s: %s", provider, exc)

        # Fall back to adapter redirect URI when config is missing
        if host is None or port is None:
            adapter = self.calendar_manager.sync_adapters.get(provider)
            redirect_uri = getattr(adapter, "redirect_uri", None) if adapter else None
            if redirect_uri:
                parsed = urlparse(redirect_uri)
                host = host or parsed.hostname
                if port is None and parsed.port:
                    port = parsed.port

        return host, port

    def _complete_oauth_flow(self, provider: str, code: str, code_verifier: str):
        """
        Complete OAuth authorization flow.

        Args:
            provider: Provider name
            code: Authorization code
            code_verifier: PKCE code verifier tied to the authorization request
        """
        if self._oauth_connect_thread and self._oauth_connect_thread.is_alive():
            logger.warning("OAuth completion already in progress; ignoring duplicate request")
            return

        # Keep account actions deterministic while OAuth token exchange is running.
        self.add_account_btn.setEnabled(False)
        self.sync_now_btn.setEnabled(False)
        self.sync_status_label.setText(self.i18n.t("calendar_hub.widget.syncing"))
        set_widget_state(self.sync_status_label, "syncing")

        try:
            self._oauth_connect_thread = threading.Thread(
                target=self._run_oauth_completion,
                args=(provider, code, code_verifier),
                daemon=True,
            )
            self._oauth_connect_thread.start()
        except Exception as exc:
            self._oauth_connect_thread = None
            self.add_account_btn.setEnabled(True)
            if not (self._manual_sync_thread and self._manual_sync_thread.is_alive()):
                self.sync_now_btn.setEnabled(True)
            self._handle_oauth_error(provider, str(exc) or repr(exc))

    def _run_oauth_completion(self, provider: str, code: str, code_verifier: str) -> None:
        """Exchange OAuth code, persist account state, and perform initial sync."""
        payload: Dict[str, Any] = {
            "provider": provider,
            "success": False,
            "email": None,
            "error": "",
            "initial_sync_error": "",
        }

        try:
            adapter = self.calendar_manager.sync_adapters[provider]
            existing_refresh_token = getattr(adapter, "refresh_token", None)

            token_data = adapter.exchange_code_for_token(code, code_verifier=code_verifier)

            expires_in = token_data.get("expires_in")
            expires_at_value = token_data.get("expires_at")
            if expires_in is None and expires_at_value:
                try:
                    expires_at_dt = to_local_datetime(expires_at_value)
                    expires_delta = int((expires_at_dt - now_local()).total_seconds())
                    expires_in = max(expires_delta, 0)
                    logger.debug(
                        "Computed expires_in=%s from expires_at for %s",
                        expires_in,
                        provider,
                    )
                except ValueError:
                    logger.warning(
                        "Invalid expires_at format received for %s: %s",
                        provider,
                        expires_at_value,
                    )

            token_type = token_data.get("token_type", "Bearer")

            logger.debug(
                "Storing %s OAuth token with expires_in=%s (expires_at=%s)",
                provider,
                expires_in,
                token_data.get("expires_at"),
            )

            self.oauth_manager.store_token(
                provider=provider,
                access_token=token_data["access_token"],
                refresh_token=token_data.get("refresh_token"),
                expires_in=expires_in,
                token_type=token_type,
            )

            adapter.access_token = token_data["access_token"]

            new_refresh_token = token_data.get("refresh_token")
            if new_refresh_token:
                adapter.refresh_token = new_refresh_token
            else:
                retained_refresh = getattr(adapter, "refresh_token", None) or existing_refresh_token
                if not retained_refresh and self.oauth_manager:
                    stored_token = self.oauth_manager.get_token(provider)
                    if stored_token:
                        retained_refresh = stored_token.get("refresh_token")

                if retained_refresh:
                    adapter.refresh_token = retained_refresh

            email = self._get_user_email(provider, adapter)

            from data.database.models import CalendarSyncStatus

            db = self.calendar_manager.db
            sync_status = CalendarSyncStatus.get_by_provider(db, provider)

            if sync_status:
                logger.debug(
                    "Reusing existing sync status for %s; resetting sync token",
                    provider,
                )
                sync_status.user_email = email
                sync_status.is_active = True
                sync_status.last_sync_time = None
                sync_status.sync_token = None
            else:
                logger.debug("Creating new sync status for %s", provider)
                sync_status = CalendarSyncStatus(
                    provider=provider,
                    user_email=email,
                    is_active=True,
                )

            sync_status.save(db)

            payload["email"] = email

            try:
                self.calendar_manager.sync_external_calendar(provider)
            except Exception as sync_error:
                sync_error_text = str(sync_error) or repr(sync_error)
                payload["initial_sync_error"] = sync_error_text
                logger.warning("Initial sync failed for %s: %s", provider, sync_error_text)

            payload["success"] = True

        except Exception as exc:  # noqa: BLE001
            payload["error"] = str(exc) or repr(exc)
            logger.error("Error completing OAuth flow for %s: %s", provider, exc, exc_info=True)

        self.oauth_connect_finished.emit(payload)

    def _on_oauth_connect_finished(self, payload: Dict[str, Any]) -> None:
        """Apply OAuth completion result on the UI thread."""
        provider = str(payload.get("provider", ""))
        success = bool(payload.get("success"))

        try:
            if not success:
                error_text = str(payload.get("error", "")) or "Unknown error"
                self._handle_oauth_error(provider, error_text)
                return

            email = payload.get("email")
            self.add_connected_account(provider, email if isinstance(email, str) else None)

            self._refresh_current_view()
            self._update_sync_status()

            provider_name = self._get_provider_display_name(provider)
            self.show_info(
                self.i18n.t("common.success"),
                self.i18n.t("calendar.success.connected", provider=provider_name),
            )

            initial_sync_error = str(payload.get("initial_sync_error", "")).strip()
            if initial_sync_error:
                self.show_warning(
                    self.i18n.t("common.warning"),
                    self.i18n.t("calendar.warning.sync_failed", error=initial_sync_error),
                )

            logger.info("OAuth flow completed for %s", provider)
        finally:
            self.add_account_btn.setEnabled(True)
            if not (self._manual_sync_thread and self._manual_sync_thread.is_alive()):
                self.sync_now_btn.setEnabled(True)
            self._oauth_connect_thread = None
            self._update_sync_status()

    def _get_user_email(self, provider: str, adapter) -> Optional[str]:
        """
        Try to resolve the authenticated user's email from the provider API.

        Args:
            provider: Provider name
            adapter: Sync adapter instance

        Returns:
            Email address if available, otherwise ``None``
        """
        try:
            import httpx
        except Exception as import_error:  # pragma: no cover - defensive branch
            logger.warning(
                "HTTP client unavailable when requesting %s user email: %s",
                provider,
                import_error,
            )
            return None

        access_token = getattr(adapter, "access_token", None)
        if not access_token:
            logger.warning("No access token provided for %s email lookup", provider)
            return None

        headers = {"Authorization": f"Bearer {access_token}"}

        try:
            if provider == CalendarSource.GOOGLE:
                with httpx.Client() as client:
                    response = client.get(
                        "https://www.googleapis.com/oauth2/v2/userinfo",
                        headers=headers,
                        timeout=10.0,
                    )

                if response.status_code == 200:
                    data = response.json()
                    email = data.get("email")
                    if email:
                        return email
                    logger.warning(
                        self.i18n.t("logging.calendar_hub.google_user_info_missing_email")
                    )
                else:
                    logger.warning(
                        "Google user info request failed with status %s",
                        response.status_code,
                    )

            elif provider == CalendarSource.OUTLOOK:
                with httpx.Client() as client:
                    response = client.get(
                        "https://graph.microsoft.com/v1.0/me",
                        headers=headers,
                        timeout=10.0,
                    )

                if response.status_code == 200:
                    data = response.json()
                    email = data.get("mail") or data.get("userPrincipalName")
                    if email:
                        return email
                    logger.warning(
                        self.i18n.t("logging.calendar_hub.outlook_user_info_missing_email")
                    )
                else:
                    logger.warning(
                        "Outlook user info request failed with status %s",
                        response.status_code,
                    )

            else:
                logger.debug("Skipping email lookup for unsupported provider: %s", provider)

        except httpx.HTTPError as http_error:
            logger.warning("HTTP error fetching %s user email: %s", provider, http_error)
        except Exception as error:  # pragma: no cover - defensive branch
            logger.warning("Unexpected error fetching %s user email: %s", provider, error)

        return None

    def _handle_oauth_error(self, provider: str, error: str):
        """
        Handle OAuth authorization error.

        Args:
            provider: Provider name
            error: Error message
        """

        provider_name = self._get_provider_display_name(provider)

        self.show_error(
            self.i18n.t("dialogs.calendar_hub.authorization_failed"),
            self.i18n.t(
                "calendar_hub.widget.connect_failed_message",
                provider=provider_name,
                error=error,
            ),
        )

        logger.error(f"OAuth error for {provider}: {error}")

    def _get_provider_display_name(self, provider: str) -> str:
        """Return the localized provider label."""
        calendar_hub_translations = {}
        if isinstance(self.i18n.translations, dict):
            calendar_hub_translations = self.i18n.translations.get("calendar_hub", {})

        if isinstance(calendar_hub_translations, dict):
            providers_map = calendar_hub_translations.get("providers", {})
            if isinstance(providers_map, dict):
                label = providers_map.get(provider)
                if isinstance(label, str) and label:
                    return label

        return provider.capitalize()

    def _format_account_label(self, provider: str, email: Optional[str]) -> str:
        """Build the account badge label text."""
        provider_name = self._get_provider_display_name(provider)

        if email:
            localized = self.i18n.t(
                "calendar_hub.account_with_email", provider=provider_name, email=email
            )
            if localized != "calendar_hub.account_with_email":
                return localized
            return f"{provider_name} ({email})"

        localized = self.i18n.t("calendar_hub.account_without_email", provider=provider_name)
        if localized != "calendar_hub.account_without_email":
            return localized
        return provider_name

    def _update_account_badge_label(self, provider: str, email: Optional[str]) -> None:
        """Update the text on an existing account badge if it exists."""
        badge_name = f"account_badge_{provider}"
        label_name = f"account_label_{provider}"

        for i in range(self.accounts_container_layout.count()):
            widget = self.accounts_container_layout.itemAt(i).widget()
            if widget and widget.objectName() == badge_name:
                layout = widget.layout()
                if not layout:
                    continue
                for j in range(layout.count()):
                    child = layout.itemAt(j).widget()
                    if child and child.objectName() == label_name:
                        child.setText(self._format_account_label(provider, email))
                    elif child and child.property("role") == ROLE_ACCOUNT_DISCONNECT:
                        child.setText(self.i18n.t("common.close"))
                return

    def add_connected_account(self, provider: str, email: Optional[str]):
        """
        Add a connected account badge.

        Args:
            provider: Provider name (google/outlook)
            email: User email if available
        """
        # Don't add if already exists
        if provider in self.connected_accounts:
            if email and self.connected_accounts[provider] != email:
                logger.debug("Updating account badge for %s with newly available email", provider)
                self.connected_accounts[provider] = email
                self._update_account_badge_label(provider, email)
            else:
                logger.debug(f"Account badge for {provider} already exists")
            return

        # Create account badge
        badge = QFrame()
        badge.setObjectName(f"account_badge_{provider}")
        badge.setProperty("role", ROLE_ACCOUNT_BADGE)
        badge_layout = QHBoxLayout(badge)

        # Status indicator
        indicator = QLabel(STATUS_INDICATOR_SYMBOL)
        indicator.setObjectName(f"indicator_{provider}")
        indicator.setProperty("role", ROLE_CALENDAR_INDICATOR)
        indicator.setProperty("provider", provider)
        badge_layout.addWidget(indicator)

        # Account info
        info_label = QLabel(self._format_account_label(provider, email))
        info_label.setObjectName(f"account_label_{provider}")
        badge_layout.addWidget(info_label)

        # Disconnect button
        disconnect_btn = create_button(self.i18n.t("common.close"))
        disconnect_btn.setProperty("role", ROLE_ACCOUNT_DISCONNECT)
        disconnect_btn.clicked.connect(lambda: self.disconnect_account(provider))
        badge_layout.addWidget(disconnect_btn)

        # Add to container
        self.accounts_container_layout.addWidget(badge)

        # Store reference
        self.connected_accounts[provider] = email

        logger.info("Added connected account: %s - %s", provider, email or "email_unavailable")

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
                badge_name = f"account_badge_{provider}"
                if widget and widget.objectName() == badge_name:
                    widget.deleteLater()
                    break

            # Remove from dict
            del self.connected_accounts[provider]

            logger.info(f"Removed connected account: {provider}")

    def disconnect_account(self, provider: str, *, confirm: bool = True):
        """
        Disconnect an external calendar account.

        Args:
            provider: Provider name (google/outlook)
        """
        try:
            provider_name = self._get_provider_display_name(provider)

            if confirm:
                if not self.show_question(
                    self.i18n.t("dialogs.calendar_hub.disconnect_account"),
                    self.i18n.t(
                        "calendar_hub.widget.disconnect_confirm_message",
                        provider=provider_name,
                    ),
                ):
                    return

            # Disconnect provider account and remove linked local data.
            self.calendar_manager.disconnect_provider_account(provider)

            # Remove account badge
            self.remove_connected_account(provider)

            # Refresh view
            self._refresh_current_view()

            # Show success message
            self.show_info(
                self.i18n.t("common.success"),
                self.i18n.t("calendar.success.disconnected", provider=provider_name),
            )

            logger.info(f"Disconnected account: {provider}")

        except Exception as e:
            logger.error(f"Error disconnecting account: {e}")

            self.show_error(
                self.i18n.t("common.error"),
                self.i18n.t("calendar.error.disconnect_failed", error=str(e)),
            )

    def _on_sync_now_clicked(self):
        """Handle sync now button click."""
        if self._manual_sync_thread and self._manual_sync_thread.is_alive():
            logger.debug("Manual sync already in progress; ignoring duplicate request")
            return

        try:
            if not self.connected_accounts:

                self.show_info(
                    self.i18n.t("dialogs.calendar_hub.no_accounts"),
                    self.i18n.t("calendar_hub.widget.no_accounts_message"),
                )
                return

            # Update UI to show syncing
            self.sync_now_btn.setEnabled(False)
            self.sync_status_label.setText(self.i18n.t("calendar_hub.widget.syncing"))
            set_widget_state(self.sync_status_label, "syncing")

            providers = list(self.connected_accounts.keys())
            self._manual_sync_thread = threading.Thread(
                target=self._run_manual_sync,
                args=(providers,),
                daemon=True,
            )
            self._manual_sync_thread.start()

        except Exception as e:
            logger.error(f"Error during manual sync: {e}")

            self.show_error(
                self.i18n.t("calendar_hub.widget.sync_error"),
                self.i18n.t("calendar_hub.widget.sync_failed_message", error=str(e)),
            )
            if not (self._oauth_connect_thread and self._oauth_connect_thread.is_alive()):
                self.sync_now_btn.setEnabled(True)
            self._update_sync_status()

    def _run_manual_sync(self, providers: list[str]) -> None:
        """Synchronize selected providers in a background thread."""
        success_count = 0
        error_count = 0
        fatal_error = ""

        try:
            for provider in providers:
                try:
                    self.calendar_manager.sync_external_calendar(provider)
                    success_count += 1
                    logger.info("Successfully synced %s", provider)
                except Exception as exc:
                    error_count += 1
                    logger.error("Failed to sync %s: %s", provider, exc)
        except Exception as exc:  # pragma: no cover - defensive guard
            fatal_error = str(exc) or repr(exc)
            logger.error("Error during manual sync thread execution: %s", exc, exc_info=True)

        self.manual_sync_finished.emit(success_count, error_count, fatal_error)

    def _on_manual_sync_finished(
        self, success_count: int, error_count: int, fatal_error: str
    ) -> None:
        """Handle manual sync completion in the UI thread."""
        try:
            if fatal_error:
                self.show_error(
                    self.i18n.t("calendar_hub.widget.sync_error"),
                    self.i18n.t("calendar_hub.widget.sync_failed_message", error=fatal_error),
                )
                return

            self._refresh_current_view()
            self._update_sync_status()

            if error_count == 0:
                self.show_info(
                    self.i18n.t("dialogs.calendar_hub.sync_complete"),
                    self.i18n.t("calendar_hub.widget.sync_success_message", count=success_count),
                )
            else:
                self.show_warning(
                    self.i18n.t("dialogs.calendar_hub.sync_completed_with_errors"),
                    self.i18n.t(
                        "calendar_hub.widget.sync_partial_message",
                        success_count=success_count,
                        error_count=error_count,
                    ),
                )
        finally:
            if not (self._oauth_connect_thread and self._oauth_connect_thread.is_alive()):
                self.sync_now_btn.setEnabled(True)
            self._manual_sync_thread = None

    def _update_sync_status(self):
        """Update sync status label with last sync time."""
        try:
            from data.database.models import CalendarSyncStatus

            # Get most recent sync time from all accounts
            sync_statuses = CalendarSyncStatus.get_all_active(self.calendar_manager.db)

            if not sync_statuses:
                self.sync_status_label.setText("")
                return

            # Find most recent sync
            most_recent = None
            for status in sync_statuses:
                if status.last_sync_time:
                    sync_time = to_local_datetime(status.last_sync_time)
                    if most_recent is None or sync_time > most_recent:
                        most_recent = sync_time

            if most_recent:
                # Calculate time ago
                now = now_local()
                delta = now - most_recent

                if delta.total_seconds() < 60:
                    time_ago = self.i18n.t("calendar_hub.widget.time_ago_just_now")
                elif delta.total_seconds() < 3600:
                    minutes = int(delta.total_seconds() / 60)
                    time_ago = self.i18n.t("calendar_hub.widget.time_ago_minutes", minutes=minutes)
                elif delta.total_seconds() < 86400:
                    hours = int(delta.total_seconds() / 3600)
                    time_ago = self.i18n.t("calendar_hub.widget.time_ago_hours", hours=hours)
                else:
                    days = int(delta.total_seconds() / 86400)
                    time_ago = self.i18n.t("calendar_hub.widget.time_ago_days", days=days)

                self.sync_status_label.setText(
                    self.i18n.t("calendar_hub.widget.last_sync", time_ago=time_ago)
                )
                set_widget_state(self.sync_status_label, None)  # Reset to default
            else:
                self.sync_status_label.setText(self.i18n.t("calendar_hub.widget.never_synced"))
                set_widget_state(self.sync_status_label, "never")

        except Exception as e:
            logger.error(f"Error updating sync status: {e}")
            self.sync_status_label.setText("")

    def update_translations(self):
        """Update all UI text when language changes."""
        # Update title
        self.title_label.setText(self.i18n.t("calendar_hub.title"))

        # Update toolbar buttons
        self.month_btn.setText(self.i18n.t("calendar_hub.view_month"))
        self.week_btn.setText(self.i18n.t("calendar_hub.view_week"))
        self.day_btn.setText(self.i18n.t("calendar_hub.view_day"))
        self.today_btn.setText(self.i18n.t("calendar_hub.today"))
        self.create_event_btn.setText(self.i18n.t("calendar_hub.create_event"))

        # Update accounts section
        self.accounts_label.setText(self.i18n.t("calendar_hub.connected_accounts") + ":")
        self.sync_now_btn.setText(self.i18n.t("calendar_hub.sync_now"))
        self.sync_now_btn.setToolTip(self.i18n.t("calendar_hub.sync_now_tooltip"))
        self.add_account_btn.setText(self.i18n.t("calendar_hub.add_account"))

        # Refresh account labels with localized provider names.
        for provider, email in self.connected_accounts.items():
            self._update_account_badge_label(provider, email)

        # Refresh child views so weekday labels and day-level text are localized.
        self.month_view.refresh_view()
        self.week_view.refresh_view()
        self.day_view.refresh_view()
        self._update_sync_status()

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
            sync_statuses = CalendarSyncStatus.get_all_active(self.calendar_manager.db)

            for status in sync_statuses:
                self.add_connected_account(status.provider, status.user_email)

            logger.info(f"Loaded {len(sync_statuses)} connected accounts")

            # Update sync status display
            self._update_sync_status()

        except Exception as e:
            logger.error(f"Error loading connected accounts: {e}")

    def _get_settings_manager(self):
        """Resolve settings manager from main window runtime context."""
        main_window = self.window()
        managers = getattr(main_window, "managers", {})
        if isinstance(managers, dict):
            return managers.get("settings_manager")
        return None

    def _get_model_manager(self):
        """Resolve model manager from main window runtime context."""
        main_window = self.window()
        managers = getattr(main_window, "managers", {})
        if isinstance(managers, dict):
            return managers.get("model_manager")
        return None

    def _open_event_text_viewer(
        self,
        *,
        transcript_path: Optional[str],
        translation_path: Optional[str],
        parent_hint: Optional[QWidget] = None,
    ) -> None:
        """Open reusable transcript/translation viewer from Calendar Hub."""
        initial_mode = resolve_text_viewer_initial_mode(
            transcript_path=transcript_path,
            translation_path=translation_path,
        )
        open_or_activate_text_viewer(
            i18n=self.i18n,
            dialog_cache=self._text_viewer_dialogs,
            parent=self,
            transcript_path=transcript_path,
            translation_path=translation_path,
            initial_mode=initial_mode,
            title_key="timeline.translation_viewer_title",
            show_warning=self.show_warning,
            parent_hint=parent_hint,
            logger=logger,
        )

    def _on_translate_transcript_requested(self, *, event_id: str, transcript_path: str) -> None:
        """Queue transcript translation task and persist result into event attachments."""
        settings_manager = self._get_settings_manager()
        selected_languages = prompt_event_translation_languages(
            parent=self,
            i18n=self.i18n,
            settings_manager=settings_manager,
        )
        if selected_languages is None:
            return

        enqueue_event_translation_task(
            transcription_manager=self.transcription_manager,
            settings_manager=settings_manager,
            event_id=event_id,
            transcript_path=transcript_path,
            logger=logger,
            context_label="calendar transcript translation",
            on_missing_transcript=lambda: self.show_warning(
                self.i18n.t("common.warning"),
                self.i18n.t("viewer.file_not_found"),
            ),
            on_translation_unavailable=lambda: self.show_warning(
                self.i18n.t("common.warning"),
                self.i18n.t("timeline.translation_not_available"),
            ),
            on_queued=lambda: self.show_info(
                self.i18n.t("common.info"),
                self.i18n.t("timeline.translation_queued"),
            ),
            on_failed=lambda exc: self.show_error(
                self.i18n.t("common.error"),
                self.i18n.t("timeline.translation_failed", error=str(exc)),
            ),
            translation_source_lang=selected_languages.get("translation_source_lang"),
            translation_target_lang=selected_languages.get("translation_target_lang"),
        )

    def _on_secondary_transcribe_requested(
        self, event_id: str, recording_path: str, dialog_data: Optional[Dict[str, Any]] = None
    ):
        """Handle request for high-quality secondary transcription of an existing event."""
        if not self.transcription_manager:
            logger.error("Transcription manager not available for re-transcription")
            return

        from ui.common.secondary_transcribe_dialog import select_secondary_transcribe_model

        selected_model = select_secondary_transcribe_model(
            parent=self,
            i18n=self.i18n,
            model_manager=self._get_model_manager(),
            settings_manager=self._get_settings_manager(),
        )
        if not selected_model:
            return

        logger.info(
            f"Submitting high-quality re-transcription from Calendar Hub for event {event_id}"
        )
        dialog_data = dialog_data or {}
        source_lang = TRANSLATION_LANGUAGE_AUTO
        target_lang = dialog_data.get("translation_target_lang")
        resolved_languages = resolve_translation_languages_from_settings(
            self._get_settings_manager(),
            target_lang=target_lang,
        )
        source_lang = resolved_languages.get(
            "translation_source_lang", TRANSLATION_LANGUAGE_AUTO
        )
        target_lang = resolved_languages.get(
            "translation_target_lang", DEFAULT_TRANSLATION_TARGET_LANGUAGE
        )

        options = {
            "event_id": event_id,
            "replace_realtime": True,
            "model_name": selected_model["model_name"],
            "model_path": selected_model["model_path"],
            "enable_translation": dialog_data.get("enable_translation", False),
            "translation_source_lang": source_lang,
            "translation_target_lang": target_lang,
        }

        self.transcription_manager.add_task(recording_path, options=options)

    def _on_view_recording(
        self,
        *,
        file_path: str,
        transcript_path: Optional[str] = None,
        translation_path: Optional[str] = None,
        parent_hint: Optional[QWidget] = None,
    ) -> None:
        """Open or focus recording playback dialog for calendar event artifacts."""
        dialog_parent = parent_hint if parent_hint is not None else self
        cache_key = file_path if parent_hint is None else f"{file_path}::{id(parent_hint)}"
        open_or_activate_audio_player(
            file_path=file_path,
            i18n=self.i18n,
            parent=dialog_parent,
            dialog_cache=self._audio_player_dialogs,
            logger=logger,
            show_warning=self.show_warning,
            show_error=self.show_error,
            transcript_path=transcript_path,
            translation_path=translation_path,
            cache_key=cache_key,
        )
