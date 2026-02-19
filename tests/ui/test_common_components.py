# SPDX-License-Identifier: Apache-2.0
"""
Tests for common UI components.
"""

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from ui.common.error_dialog import ErrorDialog
from ui.common.notification import NotificationManager
from ui.constants import ERROR_DIALOG_DETAILS_MAX_HEIGHT


class TestErrorDialog:
    """Tests for ErrorDialog component."""

    def test_error_dialog_creation(self, qapp, mock_i18n):
        """Test error dialog can be created."""
        dialog = ErrorDialog(
            title="Test Error", message="Test message", details="Test details", i18n=mock_i18n
        )

        assert dialog is not None
        assert dialog.error_title == "Test Error"
        assert dialog.error_message == "Test message"
        assert dialog.error_details == "Test details"

    def test_error_dialog_without_details(self, qapp, mock_i18n):
        """Test error dialog without details."""
        dialog = ErrorDialog(title="Test Error", message="Test message", i18n=mock_i18n)

        assert dialog is not None
        assert dialog.error_details is None

    def test_error_dialog_modal(self, qapp, mock_i18n):
        """Test error dialog is modal."""
        dialog = ErrorDialog(title="Test Error", message="Test message", i18n=mock_i18n)

        assert dialog.isModal()

    def test_error_dialog_minimum_width(self, qapp, mock_i18n):
        """Test error dialog has minimum width."""
        dialog = ErrorDialog(title="Test Error", message="Test message", i18n=mock_i18n)

        assert dialog.minimumWidth() >= 500

    def test_error_dialog_details_height_uses_constant(self, qapp, mock_i18n):
        """Details section height should use centralized UI constant."""
        dialog = ErrorDialog(
            title="Test Error", message="Test message", details="Detail line", i18n=mock_i18n
        )
        assert dialog.details_text.maximumHeight() == ERROR_DIALOG_DETAILS_MAX_HEIGHT


class TestNotificationManager:
    """Tests for NotificationManager component."""

    def test_notification_manager_creation(self, qapp, mock_i18n):
        """Test notification manager can be created."""
        manager = NotificationManager(i18n=mock_i18n)

        assert manager is not None
        assert manager.i18n == mock_i18n
        assert manager.system in ["Windows", "Darwin", "Linux"]

    def test_send_notification_info(self, qapp, mock_i18n):
        """Test sending info notification."""
        manager = NotificationManager(i18n=mock_i18n)

        # Should not raise exception
        manager.send_notification(title="Test", message="Test message", notification_type="info")

    def test_send_notification_success(self, qapp, mock_i18n):
        """Test sending success notification."""
        manager = NotificationManager(i18n=mock_i18n)

        manager.send_notification(
            title="Success", message="Operation completed", notification_type="success"
        )

    def test_send_notification_warning(self, qapp, mock_i18n):
        """Test sending warning notification."""
        manager = NotificationManager(i18n=mock_i18n)

        manager.send_notification(
            title="Warning", message="Warning message", notification_type="warning"
        )

    def test_send_notification_error(self, qapp, mock_i18n):
        """Test sending error notification."""
        manager = NotificationManager(i18n=mock_i18n)

        manager.send_notification(title="Error", message="Error message", notification_type="error")

    def test_send_notification_with_duration(self, qapp, mock_i18n):
        """Test sending notification with custom duration."""
        manager = NotificationManager(i18n=mock_i18n)

        manager.send_notification(title="Test", message="Test message", duration=10)
