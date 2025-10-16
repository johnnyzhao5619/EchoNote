"""
OAuth Authorization Dialog for EchoNote Calendar.

Provides user interface for OAuth authorization flow with external
calendar services.
"""

import logging
import webbrowser
from typing import Optional, Callable
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import threading

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QProgressBar, QTextEdit, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QThread

from utils.i18n import I18nQtManager


logger = logging.getLogger('echonote.ui.oauth_dialog')


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """HTTP request handler for OAuth callback."""
    
    callback_received = None  # Will be set to a callback function
    
    def do_GET(self):
        """Handle GET request (OAuth callback)."""
        # Parse query parameters
        parsed_path = urlparse(self.path)
        query_params = parse_qs(parsed_path.query)
        
        # Get authorization code
        code = query_params.get('code', [None])[0]
        error = query_params.get('error', [None])[0]
        
        # Send response to browser
        if code:
            response = b"""
            <html>
            <head><title>Authorization Successful</title></head>
            <body>
                <h1>Authorization Successful!</h1>
                <p>You can close this window and return to EchoNote.</p>
            </body>
            </html>
            """
            self.send_response(200)
        else:
            response = b"""
            <html>
            <head><title>Authorization Failed</title></head>
            <body>
                <h1>Authorization Failed</h1>
                <p>Error: """ + (error or b'Unknown error') + b"""</p>
                <p>You can close this window and try again.</p>
            </body>
            </html>
            """
            self.send_response(400)
        
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(response)
        
        # Call callback function
        if self.callback_received:
            self.callback_received(code, error)
    
    def log_message(self, format, *args):
        """Suppress default logging."""
        pass


class OAuthDialog(QDialog):
    """
    Dialog for OAuth authorization flow.
    
    Guides user through OAuth authorization and handles callback.
    """
    
    # Signals
    authorization_complete = pyqtSignal(str)  # authorization_code
    authorization_failed = pyqtSignal(str)    # error_message
    
    def __init__(
        self,
        provider: str,
        authorization_url: str,
        i18n: I18nQtManager,
        parent: Optional[QDialog] = None
    ):
        """
        Initialize OAuth dialog.
        
        Args:
            provider: Provider name (google/outlook)
            authorization_url: OAuth authorization URL
            i18n: Internationalization manager
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.provider = provider
        self.authorization_url = authorization_url
        self.i18n = i18n
        
        # OAuth callback server
        self.callback_server: Optional[HTTPServer] = None
        self.callback_thread: Optional[threading.Thread] = None
        
        # Authorization result
        self.auth_code: Optional[str] = None
        self.auth_error: Optional[str] = None
        
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
        title_label = QLabel(
            f"<h2>Connect {self.provider.capitalize()} Calendar</h2>"
        )
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
        self.cancel_btn = QPushButton(self.i18n.t('common.cancel'))
        self.cancel_btn.clicked.connect(self._on_cancel_clicked)
        buttons_layout.addWidget(self.cancel_btn)
        
        # Start authorization button
        self.auth_btn = QPushButton("Start Authorization")
        self.auth_btn.setObjectName('primary_button')
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
                ('localhost', 8080),
                OAuthCallbackHandler
            )
            
            # Start server in separate thread
            self.callback_thread = threading.Thread(
                target=self._run_callback_server,
                daemon=True
            )
            self.callback_thread.start()
            
            logger.info("OAuth callback server started on port 8080")
            
        except Exception as e:
            logger.error(f"Error starting callback server: {e}")
            raise
    
    def _run_callback_server(self):
        """Run callback server (in separate thread)."""
        try:
            # Handle single request
            self.callback_server.handle_request()
            
        except Exception as e:
            logger.error(f"Error in callback server: {e}")
    
    def _on_callback_received(self, code: Optional[str], error: Optional[str]):
        """
        Handle OAuth callback.
        
        Args:
            code: Authorization code (if successful)
            error: Error message (if failed)
        """
        # Store result
        self.auth_code = code
        self.auth_error = error
        
        # Update UI in main thread
        QTimer.singleShot(0, self._process_callback)
    
    def _process_callback(self):
        """Process OAuth callback in main thread."""
        try:
            if self.auth_code:
                # Success
                self.status_label.setText("Authorization successful!")
                self.status_label.setStyleSheet("color: green; font-weight: bold;")
                
                # Emit signal
                self.authorization_complete.emit(self.auth_code)
                
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
                
                logger.error(
                    f"OAuth authorization failed for {self.provider}: "
                    f"{error_msg}"
                )
                
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
        QMessageBox.critical(
            self,
            "Authorization Error",
            message
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
        parent: Optional[QDialog] = None
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
        ok_btn = QPushButton(self.i18n.t('common.ok'))
        ok_btn.clicked.connect(self.accept)
        layout.addWidget(ok_btn)
