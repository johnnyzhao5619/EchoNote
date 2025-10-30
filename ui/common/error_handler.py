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
UI Error Handler - Enhanced error handling for UI components.

Provides unified error handling for UI components with internationalized
error messages, standardized error dialogs, and consistent error reporting.
"""

import logging
from typing import Any, Callable, Dict, Optional

from ui.qt_imports import QMessageBox, QWidget
from utils.error_handler import ErrorHandler as BaseErrorHandler
from utils.i18n import I18nQtManager

logger = logging.getLogger(__name__)


class UIErrorHandler:
    """
    Enhanced error handler for UI components.

    Provides standardized error dialogs, internationalized messages,
    and consistent error handling patterns for UI components.
    """

    def __init__(self, parent_widget: Optional[QWidget] = None):
        """
        Initialize the UI error handler.

        Args:
            parent_widget: Parent widget for error dialogs
        """
        self.parent_widget = parent_widget
        # Note: i18n should be passed as parameter in real usage
        # This is a fallback for backward compatibility
        try:
            self.i18n = I18nQtManager()
        except Exception:
            self.i18n = None

    def handle_error(
        self,
        error: Exception,
        context: Optional[Dict[str, Any]] = None,
        show_dialog: bool = True,
        dialog_title: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Handle an error with UI feedback.

        Args:
            error: Exception to handle
            context: Additional context information
            show_dialog: Whether to show error dialog
            dialog_title: Custom dialog title

        Returns:
            Error information dictionary
        """
        # Use base error handler to process the error
        error_info = BaseErrorHandler.handle_error(error, context)

        # Internationalize the error messages
        error_info = self._internationalize_error_info(error_info)

        # Show error dialog if requested
        if show_dialog:
            self.show_error_dialog(error_info, dialog_title)

        # Log the error
        self._log_error(error, error_info, context)

        return error_info

    def show_error_dialog(self, error_info: Dict[str, Any], title: Optional[str] = None) -> None:
        """
        Show standardized error dialog.

        Args:
            error_info: Error information from handle_error
            title: Custom dialog title
        """
        if not title:
            title = self._get_dialog_title(error_info)

        message = self._format_dialog_message(error_info)

        # Create message box
        msg_box = QMessageBox(self.parent_widget)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.setIcon(self._get_message_box_icon(error_info))

        # Add retry button if error is retryable
        if error_info.get("retry_possible", False):
            retry_button = msg_box.addButton(
                self.i18n.t("common.retry") if self.i18n else "Retry",
                QMessageBox.ButtonRole.ActionRole,
            )
            msg_box.addButton(QMessageBox.StandardButton.Ok)
        else:
            msg_box.addButton(QMessageBox.StandardButton.Ok)

        # Show details if available
        if error_info.get("technical_details"):
            msg_box.setDetailedText(error_info["technical_details"])

        msg_box.exec()

    def show_warning_dialog(self, message: str, title: Optional[str] = None) -> None:
        """
        Show warning dialog.

        Args:
            message: Warning message
            title: Dialog title
        """
        if not title:
            title = self.i18n.t("common.warning") if self.i18n else "Warning"

        QMessageBox.warning(self.parent_widget, title, message)

    def show_info_dialog(self, message: str, title: Optional[str] = None) -> None:
        """
        Show information dialog.

        Args:
            message: Information message
            title: Dialog title
        """
        if not title:
            title = self.i18n.t("common.information") if self.i18n else "Information"

        QMessageBox.information(self.parent_widget, title, message)

    def show_question_dialog(self, message: str, title: Optional[str] = None) -> bool:
        """
        Show question dialog with Yes/No buttons.

        Args:
            message: Question message
            title: Dialog title

        Returns:
            True if user clicked Yes, False otherwise
        """
        if not title:
            title = self.i18n.t("common.confirm") if self.i18n else "Confirm"

        reply = QMessageBox.question(
            self.parent_widget,
            title,
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        return reply == QMessageBox.StandardButton.Yes

    def handle_async_error(
        self,
        error: Exception,
        context: Optional[Dict[str, Any]] = None,
        callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> None:
        """
        Handle error from async operations.

        Args:
            error: Exception to handle
            context: Additional context information
            callback: Optional callback to handle the error info
        """
        error_info = self.handle_error(error, context, show_dialog=False)

        if callback:
            callback(error_info)
        else:
            # Default: show dialog in main thread
            self.show_error_dialog(error_info)

    def create_error_callback(
        self, context: Optional[Dict[str, Any]] = None, show_dialog: bool = True
    ) -> Callable[[Exception], None]:
        """
        Create an error callback function for async operations.

        Args:
            context: Context information to include
            show_dialog: Whether to show error dialog

        Returns:
            Error callback function
        """

        def error_callback(error: Exception) -> None:
            self.handle_error(error, context, show_dialog)

        return error_callback

    def _internationalize_error_info(self, error_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Internationalize error messages.

        Args:
            error_info: Error information dictionary

        Returns:
            Error info with internationalized messages
        """
        if not self.i18n:
            return error_info

        category = error_info.get("category", "unknown")

        # Try to get internationalized messages
        try:
            # Get category-specific error message
            user_message_key = f"errors.{category}.message"
            user_message = self.i18n.t(user_message_key)

            # If translation exists, use it
            if user_message != user_message_key:
                error_info["user_message"] = user_message

            # Get category-specific suggested action
            action_key = f"errors.{category}.suggested_action"
            suggested_action = self.i18n.t(action_key)

            if suggested_action != action_key:
                error_info["suggested_action"] = suggested_action

        except Exception as e:
            logger.debug(f"Failed to internationalize error: {e}")

        return error_info

    def _get_dialog_title(self, error_info: Dict[str, Any]) -> str:
        """
        Get appropriate dialog title for error.

        Args:
            error_info: Error information

        Returns:
            Dialog title
        """
        category = error_info.get("category", "unknown")

        if self.i18n:
            title_key = f"errors.{category}.title"
            title = self.i18n.t(title_key)
            if title != title_key:
                return title

            # Fallback to generic error title
            return self.i18n.t("common.error")

        # English fallback
        return "Error"

    def _format_dialog_message(self, error_info: Dict[str, Any]) -> str:
        """
        Format message for error dialog.

        Args:
            error_info: Error information

        Returns:
            Formatted message
        """
        message = error_info.get("user_message", "An error occurred")

        suggested_action = error_info.get("suggested_action")
        if suggested_action:
            message += f"\n\n{suggested_action}"

        return message

    def _get_message_box_icon(self, error_info: Dict[str, Any]) -> QMessageBox.Icon:
        """
        Get appropriate icon for message box.

        Args:
            error_info: Error information

        Returns:
            Message box icon
        """
        category = error_info.get("category", "unknown")

        # Map categories to icons
        icon_map = {
            "network": QMessageBox.Icon.Warning,
            "authentication": QMessageBox.Icon.Warning,
            "api_limit": QMessageBox.Icon.Warning,
            "permission": QMessageBox.Icon.Critical,
            "resource": QMessageBox.Icon.Warning,
            "validation": QMessageBox.Icon.Information,
            "file_format": QMessageBox.Icon.Warning,
        }

        return icon_map.get(category, QMessageBox.Icon.Critical)

    def _log_error(
        self, error: Exception, error_info: Dict[str, Any], context: Optional[Dict[str, Any]]
    ) -> None:
        """
        Log error information.

        Args:
            error: Original exception
            error_info: Processed error information
            context: Additional context
        """
        log_context = {
            "category": error_info.get("category"),
            "retry_possible": error_info.get("retry_possible"),
            "user_context": context or {},
        }

        logger.error(
            f"UI Error: {error_info.get('user_message')}",
            exc_info=error,
            extra={"error_context": log_context},
        )


# Convenience functions for common error handling patterns


def show_error(
    parent: QWidget,
    error: Exception,
    context: Optional[Dict[str, Any]] = None,
    title: Optional[str] = None,
) -> None:
    """
    Convenience function to show error dialog.

    Args:
        parent: Parent widget
        error: Exception to show
        context: Additional context
        title: Custom dialog title
    """
    handler = UIErrorHandler(parent)
    handler.handle_error(error, context, show_dialog=True, dialog_title=title)


def show_warning(parent: QWidget, message: str, title: Optional[str] = None) -> None:
    """
    Convenience function to show warning dialog.

    Args:
        parent: Parent widget
        message: Warning message
        title: Dialog title
    """
    handler = UIErrorHandler(parent)
    handler.show_warning_dialog(message, title)


def show_info(parent: QWidget, message: str, title: Optional[str] = None) -> None:
    """
    Convenience function to show info dialog.

    Args:
        parent: Parent widget
        message: Information message
        title: Dialog title
    """
    handler = UIErrorHandler(parent)
    handler.show_info_dialog(message, title)


def ask_question(parent: QWidget, message: str, title: Optional[str] = None) -> bool:
    """
    Convenience function to show question dialog.

    Args:
        parent: Parent widget
        message: Question message
        title: Dialog title

    Returns:
        True if user clicked Yes, False otherwise
    """
    handler = UIErrorHandler(parent)
    return handler.show_question_dialog(message, title)


def create_error_handler(parent: QWidget) -> UIErrorHandler:
    """
    Convenience function to create error handler.

    Args:
        parent: Parent widget

    Returns:
        UIErrorHandler instance
    """
    return UIErrorHandler(parent)
