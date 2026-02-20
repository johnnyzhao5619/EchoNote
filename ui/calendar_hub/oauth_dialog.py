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
OAuth Authorization Dialog for EchoNote Calendar.

Provides user interface for OAuth authorization flow with external
calendar services.
"""

import errno
import logging
import threading
import webbrowser
from html import escape
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Optional, Tuple
from urllib.parse import parse_qs, urlparse

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QTextEdit,
    QVBoxLayout,
)

from ui.base_widgets import (
    connect_button_with_callback,
    create_button,
    create_hbox,
    create_primary_button,
)
from ui.constants import (
    CALENDAR_OAUTH_DIALOG_MIN_WIDTH,
    CALENDAR_OAUTH_INSTRUCTIONS_MAX_HEIGHT,
    CALENDAR_OAUTH_RESULT_DIALOG_MIN_WIDTH,
)
from utils.i18n import I18nQtManager

logger = logging.getLogger("echonote.ui.oauth_dialog")


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """HTTP request handler for OAuth callback."""

    callback_received = None  # Will be set to a callback function
    i18n = None  # Will be set to I18nQtManager instance

    def do_GET(self):
        """Handle GET request (OAuth callback)."""
        # Parse query parameters
        parsed_path = urlparse(self.path)
        query_params = parse_qs(parsed_path.query)

        # Get authorization code
        code = query_params.get("code", [None])[0]
        error = query_params.get("error", [None])[0]
        state = query_params.get("state", [None])[0]

        # Send response to browser
        html_template = (
            "<html>"
            "<head><title>{title}</title></head>"
            "<body>"
            "    <h1>{heading}</h1>"
            "    {content}"
            "</body>"
            "</html>"
        )

        if code:
            response_body = html_template.format(
                title=self.i18n.t("calendar_hub.oauth_dialog.auth_success_title"),
                heading=self.i18n.t("calendar_hub.oauth_dialog.auth_success_heading"),
                content=self.i18n.t("calendar_hub.oauth_dialog.auth_success_content"),
            )
            self.send_response(200)
        else:
            error_message = str(error or self.i18n.t("calendar_hub.oauth_dialog.unknown_error"))
            response_body = html_template.format(
                title=self.i18n.t("calendar_hub.oauth_dialog.auth_failed_title"),
                heading=self.i18n.t("calendar_hub.oauth_dialog.auth_failed_heading"),
                content=self.i18n.t(
                    "calendar_hub.oauth_dialog.auth_failed_content", error=escape(error_message)
                ),
            )
            self.send_response(400)

        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(response_body.encode("utf-8"))

        # Call callback function
        if self.callback_received:
            self.callback_received(code, error, state)

    def log_message(self, format, *args):
        """Suppress default logging."""


class OAuthDialog(QDialog):
    """
    Dialog for OAuth authorization flow.

    Guides user through OAuth authorization and handles callback.
    """

    # Signals
    authorization_complete = Signal(str, str)  # authorization_code, code_verifier
    authorization_failed = Signal(str)  # error_message

    def __init__(
        self,
        provider: str,
        authorization_url: str,
        i18n: I18nQtManager,
        parent: Optional[QDialog] = None,
        callback_host: Optional[str] = None,
        callback_port: Optional[int] = None,
        *,
        state: str,
        code_verifier: str,
    ):
        """
        Initialize OAuth dialog.

        Args:
            provider: Provider name (google/outlook)
            authorization_url: OAuth authorization URL
            i18n: Internationalization manager
            parent: Parent widget
            callback_host: Hostname for local callback server (optional)
            callback_port: Port for local callback server (optional)
            state: OAuth state parameter tied to the authorization request
            code_verifier: PKCE code verifier tied to the authorization request
        """
        super().__init__(parent)

        self.provider = provider
        self.authorization_url = authorization_url
        self.i18n = i18n
        self.callback_host, self.callback_port = self._resolve_callback_endpoint(
            callback_host, callback_port
        )

        if not state or not code_verifier:
            raise ValueError(
                self.i18n.t("exceptions.calendar_hub.state_and_code_verifier_required")
            )

        self.expected_state = state
        self.code_verifier = code_verifier

        # OAuth callback server
        self.callback_server: Optional[HTTPServer] = None
        self.callback_thread: Optional[threading.Thread] = None
        self._callback_stop_event = threading.Event()

        # Authorization result
        self.auth_code: Optional[str] = None
        self.auth_error: Optional[str] = None
        self.callback_state: Optional[str] = None

        self.setup_ui()

        logger.debug(f"OAuthDialog initialized for provider: {provider}")

    def setup_ui(self):
        """Set up the dialog UI."""
        # Set dialog properties
        self.setWindowTitle(
            self.i18n.t(
                "calendar_hub.oauth_dialog.connect_title", provider=self.provider.capitalize()
            )
        )
        self.setMinimumWidth(CALENDAR_OAUTH_DIALOG_MIN_WIDTH)
        self.setModal(True)

        # Main layout
        layout = QVBoxLayout(self)

        # Title
        title_text = self.i18n.t(
            "calendar_hub.oauth_dialog.connect_title", provider=self.provider.capitalize()
        )
        title_label = QLabel(f"<h2>{title_text}</h2>")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)

        # Instructions
        instructions = self._create_instructions()
        layout.addWidget(instructions)

        # Progress indicator
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # Indeterminate
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Status label
        self.status_label = QLabel(self.i18n.t("calendar_hub.oauth_dialog.ready_to_authorize"))
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setProperty("role", "oauth-status")
        layout.addWidget(self.status_label)

        # Buttons
        buttons = self._create_buttons()
        layout.addLayout(buttons)

    def _create_instructions(self) -> QTextEdit:
        """
        Create instructions text.

        Returns:
            Instructions widget
        """
        instructions = QTextEdit()
        instructions.setReadOnly(True)
        instructions.setMaximumHeight(CALENDAR_OAUTH_INSTRUCTIONS_MAX_HEIGHT)

        text = self.i18n.t(
            "calendar_hub.oauth_dialog.instructions_html", provider=self.provider.capitalize()
        )

        instructions.setHtml(text)

        return instructions

    def _create_buttons(self) -> QHBoxLayout:
        """
        Create dialog buttons.

        Returns:
            Buttons layout
        """
        buttons_layout = create_hbox()
        buttons_layout.addStretch()

        # Cancel button
        self.cancel_btn = create_button(self.i18n.t("common.cancel"))
        self.cancel_btn.clicked.connect(self._on_cancel_clicked)
        buttons_layout.addWidget(self.cancel_btn)

        # Start authorization button
        self.auth_btn = create_button(self.i18n.t("calendar_hub.oauth_dialog.start_authorization"))
        self.auth_btn = create_primary_button(self.auth_btn.text())
        self.auth_btn.clicked.connect(self._on_auth_clicked)
        buttons_layout.addWidget(self.auth_btn)

        return buttons_layout

    def _on_auth_clicked(self):
        """Handle authorization button click."""
        try:
            # Update UI
            self.auth_btn.setEnabled(False)
            self.progress_bar.setVisible(True)
            self.status_label.setText(
                self.i18n.t("calendar_hub.oauth_dialog.waiting_authorization")
            )

            # Start callback server
            self._start_callback_server()

            # Open browser
            webbrowser.open(self.authorization_url)

            logger.info(f"Opened authorization URL for {self.provider}")

        except Exception as e:
            logger.error(f"Error starting authorization: {e}")
            self._show_error(
                self.i18n.t("calendar_hub.oauth_dialog.start_authorization_failed", error=str(e))
            )
            self._reset_ui()

    def _start_callback_server(self):
        """Start local HTTP server to receive OAuth callback."""
        try:
            self._callback_stop_event.clear()

            # Bind callback context to a per-dialog handler class to avoid cross-dialog races.
            handler_cls = type("DialogOAuthCallbackHandler", (OAuthCallbackHandler,), {})
            handler_cls.callback_received = self._on_callback_received
            handler_cls.i18n = self.i18n

            # Create server
            self.callback_server = HTTPServer((self.callback_host, self.callback_port), handler_cls)
            # Keep request loop interruptible so cancellation can stop quickly.
            self.callback_server.timeout = 0.5

            # Start server in separate thread
            self.callback_thread = threading.Thread(target=self._run_callback_server, daemon=True)
            self.callback_thread.start()

            logger.info(
                "OAuth callback server started on %s:%s", self.callback_host, self.callback_port
            )

        except Exception as e:
            if isinstance(e, OSError) and e.errno in {errno.EADDRINUSE, errno.EACCES}:
                logger.error(
                    "Callback server port unavailable (%s:%s): %s",
                    self.callback_host,
                    self.callback_port,
                    e,
                )
                raise ValueError(f"Callback port {self.callback_port} is not available.") from e

            logger.error(
                "Error starting callback server on %s:%s: %s",
                self.callback_host,
                self.callback_port,
                e,
            )
            raise

    def _resolve_callback_endpoint(
        self, host: Optional[str], port: Optional[int]
    ) -> Tuple[str, int]:
        """Resolve callback server host and port with fallbacks."""

        resolved_host = host
        resolved_port: Optional[int] = self._normalize_port(port)

        if resolved_host is None or resolved_port is None:
            redirect_host, redirect_port = self._parse_redirect_from_authorization()
            if resolved_host is None and redirect_host:
                resolved_host = redirect_host
            if resolved_port is None and redirect_port is not None:
                resolved_port = redirect_port

        if resolved_host is None or resolved_port is None:
            config_host, config_port = self._load_configured_callback()
            if resolved_host is None and config_host:
                resolved_host = config_host
            if resolved_port is None and config_port is not None:
                resolved_port = config_port

        resolved_host = resolved_host or "localhost"
        if resolved_port is None:
            resolved_port = 8080

        normalized_port = self._normalize_port(resolved_port)
        if normalized_port is None:
            message = f"Invalid callback port configured: {resolved_port}."
            logger.error(message)
            raise ValueError(message)

        return resolved_host, normalized_port

    def _normalize_port(self, port: Optional[int]) -> Optional[int]:
        """Validate and normalize callback port."""
        if port is None:
            return None

        try:
            value = int(port)
        except (TypeError, ValueError):
            logger.error("Failed to parse callback port value: %s", port)
            raise ValueError(f"Invalid callback port: {port}")

        if not (1 <= value <= 65535):
            logger.error("Callback port out of range: %s", value)
            raise ValueError(f"Invalid callback port: {value}")

        return value

    def _parse_redirect_from_authorization(self) -> Tuple[Optional[str], Optional[int]]:
        """Extract callback host/port from authorization URL redirect parameter."""
        try:
            parsed_auth = urlparse(self.authorization_url)
            query_params = parse_qs(parsed_auth.query)
            redirect_uri = query_params.get("redirect_uri", [None])[0]
            if not redirect_uri:
                return None, None

            redirect_parsed = urlparse(redirect_uri)
            host = redirect_parsed.hostname
            port: Optional[int]
            try:
                port = redirect_parsed.port
            except ValueError:
                logger.error("Invalid port detected in redirect URI: %s", redirect_uri)
                raise ValueError(
                    self.i18n.t("exceptions.calendar_hub.invalid_port_in_redirect_uri")
                )

            return host, port

        except ValueError as exc:
            logger.error("Failed to parse authorization redirect URI: %s", exc)
            raise ValueError(self.i18n.t("exceptions.calendar_hub.failed_to_parse_redirect_uri"))

        except Exception:
            logger.exception("Unexpected error while parsing redirect URI")
            return None, None

    def _load_configured_callback(self) -> Tuple[Optional[str], Optional[int]]:
        """Load callback host/port from application configuration."""
        try:
            from config.app_config import ConfigManager

            config = ConfigManager()
            redirect_uri = config.get("calendar.oauth.redirect_uri")
            host = None
            port = None

            if redirect_uri:
                redirect_parsed = urlparse(redirect_uri)
                host = redirect_parsed.hostname
                try:
                    port = redirect_parsed.port
                except ValueError:
                    logger.error("Invalid port in configured redirect URI: %s", redirect_uri)
                    raise ValueError(
                        self.i18n.t(
                            "exceptions.calendar_hub.invalid_port_in_configured_redirect_uri"
                        )
                    )

            config_port = config.get("calendar.oauth.callback_port")
            if config_port is not None:
                port = self._normalize_port(config_port)

            return host, port

        except ValueError:
            raise

        except Exception as exc:
            logger.warning("Unable to load callback configuration: %s", exc)
            return None, None

    def _run_callback_server(self):
        """Run callback server (in separate thread)."""
        server = self.callback_server
        if server is None:
            return

        try:
            while not self._callback_stop_event.is_set():
                server.handle_request()
        except OSError as exc:
            if not self._callback_stop_event.is_set():
                logger.error("OAuth callback server socket error: %s", exc)
        except Exception as e:
            if not self._callback_stop_event.is_set():
                logger.error(f"Error in callback server: {e}")

    def _on_callback_received(
        self, code: Optional[str], error: Optional[str], state: Optional[str]
    ):
        """
        Handle OAuth callback.

        Args:
            code: Authorization code (if successful)
            error: Error message (if failed)
            state: State value returned by the provider
        """
        # Store result
        self.auth_code = code
        self.auth_error = error
        self.callback_state = state

        # Update UI in main thread
        QTimer.singleShot(0, self._process_callback)

    def _process_callback(self):
        """Process OAuth callback in main thread."""
        try:
            if self.auth_code:
                if self.callback_state != self.expected_state:
                    mismatch_message = self.i18n.t(
                        "calendar_hub.oauth_dialog.state_mismatch_message"
                    )
                    self.status_label.setText(
                        self.i18n.t("calendar_hub.oauth_dialog.authorization_failed")
                    )
                    self.status_label.setProperty("role", "oauth-status")
                    self.status_label.setProperty("state", "error")
                    self._show_error(mismatch_message)
                    self.authorization_failed.emit(mismatch_message)
                    QTimer.singleShot(2000, self._reset_ui)
                    logger.warning(
                        "State mismatch for provider %s (expected=%s, received=%s)",
                        self.provider,
                        self.expected_state,
                        self.callback_state,
                    )
                    return

                # Success
                self.status_label.setText(
                    self.i18n.t("calendar_hub.oauth_dialog.authorization_successful")
                )
                self.status_label.setProperty("role", "oauth-status")
                self.status_label.setProperty("state", "success")

                # Emit signal
                self.authorization_complete.emit(self.auth_code, self.code_verifier)

                # Close dialog after short delay
                QTimer.singleShot(1000, self.accept)

                logger.info(f"OAuth authorization successful for {self.provider}")

            else:
                # Failed
                error_msg = self.auth_error or "Unknown error"
                self.status_label.setText(
                    self.i18n.t("calendar_hub.oauth_dialog.authorization_failed", error=error_msg)
                )
                self.status_label.setProperty("role", "oauth-status")
                self.status_label.setProperty("state", "error")

                # Emit signal
                self.authorization_failed.emit(error_msg)

                # Reset UI
                QTimer.singleShot(2000, self._reset_ui)

                logger.error(f"OAuth authorization failed for {self.provider}: " f"{error_msg}")

        except Exception as e:
            logger.error(f"Error processing callback: {e}")
            self._show_error(
                self.i18n.t("calendar_hub.oauth_dialog.process_authorization_failed", error=str(e))
            )
            self._reset_ui()

        finally:
            # Stop callback server
            self._stop_callback_server()

    def _stop_callback_server(self):
        """Stop callback server."""
        try:
            self._callback_stop_event.set()

            server = self.callback_server
            thread = self.callback_thread

            if server:
                try:
                    server.server_close()
                except Exception as exc:
                    logger.debug("Error while closing OAuth callback server socket: %s", exc)

            if thread and thread.is_alive():
                thread.join(timeout=1)

            self.callback_server = None
            self.callback_thread = None

            logger.debug("OAuth callback server stopped")

        except Exception as e:
            logger.error(f"Error stopping callback server: {e}")

    def _reset_ui(self):
        """Reset UI to initial state."""
        self.auth_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.status_label.setText(self.i18n.t("calendar_hub.oauth_dialog.ready_to_authorize"))
        # Style is already set via property

    def _on_cancel_clicked(self):
        """Handle cancel button click."""
        # Stop callback server
        self._stop_callback_server()

        # Reject dialog
        self.reject()

        logger.debug("OAuth authorization cancelled")

    def _show_error(self, message: str):
        """
        Show error message.

        Args:
            message: Error message
        """
        QMessageBox.critical(
            self,
            self.i18n.t("calendar_hub.oauth_dialog.authorization_error"),
            message,
        )

    def closeEvent(self, event):
        """Handle dialog close event."""
        # Stop callback server
        self._stop_callback_server()

        super().closeEvent(event)


class OAuthResultDialog(QDialog):
    """
    Dialog for showing OAuth authorization result.
    """

    def __init__(
        self,
        provider: str,
        success: bool,
        message: str,
        i18n: I18nQtManager,
        parent: Optional[QDialog] = None,
    ):
        """
        Initialize result dialog.

        Args:
            provider: Provider name
            success: Whether authorization was successful
            message: Result message
            i18n: Internationalization manager
            parent: Parent widget
        """
        super().__init__(parent)

        self.provider = provider
        self.success = success
        self.message = message
        self.i18n = i18n

        self.setup_ui()

    def setup_ui(self):
        """Set up the dialog UI."""
        # Set dialog properties
        title = (
            self.i18n.t("calendar_hub.oauth_dialog.auth_success_title")
            if self.success
            else self.i18n.t("calendar_hub.oauth_dialog.auth_failed_title")
        )
        self.setWindowTitle(title)
        self.setMinimumWidth(CALENDAR_OAUTH_RESULT_DIALOG_MIN_WIDTH)

        # Main layout
        layout = QVBoxLayout(self)

        # Icon and message
        status_text = self.i18n.t("common.success") if self.success else self.i18n.t("common.error")
        icon_label = QLabel(f"<h2>{status_text}</h2>")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setProperty("role", "oauth-status")
        icon_label.setProperty("state", "success" if self.success else "error")
        layout.addWidget(icon_label)

        message_label = QLabel(self.message)
        message_label.setWordWrap(True)
        message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(message_label)

        # OK button
        ok_btn = create_button(self.i18n.t("common.ok"))
        connect_button_with_callback(ok_btn, self.accept)
        layout.addWidget(ok_btn)
