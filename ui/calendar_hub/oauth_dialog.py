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

import logging
import webbrowser
from typing import Dict, Optional, Tuple
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import errno
import threading
from html import escape

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QProgressBar,
    QTextEdit,
    QMessageBox,
)
from PySide6.QtCore import Qt, Signal, QTimer, QThread

from utils.i18n import I18nQtManager


logger = logging.getLogger("echonote.ui.oauth_dialog")


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """HTTP request handler for OAuth callback."""

    callback_received = None  # Will be set to a callback function

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
                title="Authorization Successful",
                heading="Authorization Successful!",
                content="<p>You can close this window and return to EchoNote.</p>",
            )
            self.send_response(200)
        else:
            error_message = str(error or "Unknown error")
            response_body = html_template.format(
                title="Authorization Failed",
                heading="Authorization Failed",
                content=(
                    f"<p>Error: {escape(error_message)}</p>"
                    "<p>You can close this window and try again.</p>"
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
        pass


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
            raise ValueError("State and code_verifier must be provided for OAuth dialog")

        self.expected_state = state
        self.code_verifier = code_verifier
        self._authorization_context: Dict[str, str] = {
            "provider": provider,
            "state": state,
            "code_verifier": code_verifier,
        }

        # OAuth callback server
        self.callback_server: Optional[HTTPServer] = None
        self.callback_thread: Optional[threading.Thread] = None

        # Authorization result
        self.auth_code: Optional[str] = None
        self.auth_error: Optional[str] = None
        self.callback_state: Optional[str] = None

        self.setup_ui()

        logger.debug(f"OAuthDialog initialized for provider: {provider}")

    def setup_ui(self):
        """Set up the dialog UI."""
        # Set dialog properties
        self.setWindowTitle(f"Connect {self.provider.capitalize()} Calendar")
        self.setMinimumWidth(500)
        self.setModal(True)

        # Main layout
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # Title
        title_label = QLabel(f"<h2>Connect {self.provider.capitalize()} Calendar</h2>")
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
        self.status_label = QLabel("Ready to authorize")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("color: #666; font-style: italic;")
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
        instructions.setMaximumHeight(150)

        text = f"""
        <p>To connect your {self.provider.capitalize()} calendar:</p>
        <ol>
            <li>Click the "Start Authorization" button below</li>
            <li>Your browser will open to {self.provider.capitalize()}'s authorization page</li>
            <li>Sign in to your {self.provider.capitalize()} account if needed</li>
            <li>Grant EchoNote permission to access your calendar</li>
            <li>You will be redirected back to EchoNote automatically</li>
        </ol>
        <p><strong>Note:</strong> EchoNote will only access your calendar data. 
        We never store your password.</p>
        """

        instructions.setHtml(text)

        return instructions

    def _create_buttons(self) -> QHBoxLayout:
        """
        Create dialog buttons.

        Returns:
            Buttons layout
        """
        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch()

        # Cancel button
        self.cancel_btn = QPushButton(self.i18n.t("common.cancel"))
        self.cancel_btn.clicked.connect(self._on_cancel_clicked)
        buttons_layout.addWidget(self.cancel_btn)

        # Start authorization button
        self.auth_btn = QPushButton("Start Authorization")
        self.auth_btn.setObjectName("primary_button")
        self.auth_btn.clicked.connect(self._on_auth_clicked)
        buttons_layout.addWidget(self.auth_btn)

        return buttons_layout

    def _on_auth_clicked(self):
        """Handle authorization button click."""
        try:
            # Update UI
            self.auth_btn.setEnabled(False)
            self.progress_bar.setVisible(True)
            self.status_label.setText("Waiting for authorization...")

            # Start callback server
            self._start_callback_server()

            # Open browser
            webbrowser.open(self.authorization_url)

            logger.info(f"Opened authorization URL for {self.provider}")

        except Exception as e:
            logger.error(f"Error starting authorization: {e}")
            self._show_error(f"Failed to start authorization: {str(e)}")
            self._reset_ui()

    def _start_callback_server(self):
        """Start local HTTP server to receive OAuth callback."""
        try:
            # Set callback handler
            OAuthCallbackHandler.callback_received = self._on_callback_received

            # Create server
            self.callback_server = HTTPServer(
                (self.callback_host, self.callback_port), OAuthCallbackHandler
            )

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
                raise ValueError("Invalid port specified in redirect URI.")

            return host, port

        except ValueError as exc:
            logger.error("Failed to parse authorization redirect URI: %s", exc)
            raise ValueError("Failed to parse redirect URI for callback port.")

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
                    raise ValueError("Invalid port specified in configured redirect URI.")

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
        try:
            # Handle single request
            self.callback_server.handle_request()

        except Exception as e:
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
                    mismatch_message = "Authorization state mismatch detected. The flow was cancelled for your safety."
                    self.status_label.setText("Authorization failed: state mismatch")
                    self.status_label.setStyleSheet("color: red; font-weight: bold;")
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
                self.status_label.setText("Authorization successful!")
                self.status_label.setStyleSheet("color: green; font-weight: bold;")

                # Emit signal
                self.authorization_complete.emit(self.auth_code, self.code_verifier)

                # Close dialog after short delay
                QTimer.singleShot(1000, self.accept)

                logger.info(f"OAuth authorization successful for {self.provider}")

            else:
                # Failed
                error_msg = self.auth_error or "Unknown error"
                self.status_label.setText(f"Authorization failed: {error_msg}")
                self.status_label.setStyleSheet("color: red; font-weight: bold;")

                # Emit signal
                self.authorization_failed.emit(error_msg)

                # Reset UI
                QTimer.singleShot(2000, self._reset_ui)

                logger.error(f"OAuth authorization failed for {self.provider}: " f"{error_msg}")

        except Exception as e:
            logger.error(f"Error processing callback: {e}")
            self._show_error(f"Error processing authorization: {str(e)}")
            self._reset_ui()

        finally:
            # Stop callback server
            self._stop_callback_server()

    def _stop_callback_server(self):
        """Stop callback server."""
        try:
            if self.callback_server:
                self.callback_server.shutdown()
                self.callback_server = None

            if self.callback_thread:
                self.callback_thread.join(timeout=1)
                self.callback_thread = None

            logger.debug("OAuth callback server stopped")

        except Exception as e:
            logger.error(f"Error stopping callback server: {e}")

    def _reset_ui(self):
        """Reset UI to initial state."""
        self.auth_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.status_label.setText("Ready to authorize")
        self.status_label.setStyleSheet("color: #666; font-style: italic;")

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
        QMessageBox.critical(self, "Authorization Error", message)

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
        title = "Authorization Successful" if self.success else "Authorization Failed"
        self.setWindowTitle(title)
        self.setMinimumWidth(400)

        # Main layout
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # Icon and message
        icon = "✓" if self.success else "✗"
        color = "green" if self.success else "red"

        icon_label = QLabel(f"<h1 style='color: {color};'>{icon}</h1>")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon_label)

        message_label = QLabel(self.message)
        message_label.setWordWrap(True)
        message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(message_label)

        # OK button
        ok_btn = QPushButton(self.i18n.t("common.ok"))
        ok_btn.clicked.connect(self.accept)
        layout.addWidget(ok_btn)
