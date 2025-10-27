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
Desktop notification manager for EchoNote application.

Provides cross-platform desktop notifications using system-native APIs.
"""

import logging
import platform
from typing import Optional

logger = logging.getLogger("echonote.ui.notification")


class NotificationManager:
    """
    Manages desktop notifications across different platforms.

    Provides a unified interface for sending notifications on Windows,
    macOS, and Linux.
    """

    def __init__(self):
        """Initialize notification manager."""
        self.system = platform.system()
        self._check_availability()

        logger.info(f"Notification manager initialized for {self.system}")

    def _check_availability(self):
        """Check if notifications are available on this platform."""
        if self.system == "Windows":
            try:
                pass

                self.windows_available = True
            except ImportError:
                self.windows_available = False
                logger.warning("win10toast not installed, Windows notifications unavailable")
        elif self.system == "Linux":
            # Check if notify-send is available
            import subprocess

            try:
                result = subprocess.run(["which", "notify-send"], capture_output=True, timeout=2)
                self.linux_available = result.returncode == 0
                if not self.linux_available:
                    logger.warning("notify-send not found, Linux notifications unavailable")
            except Exception as e:
                self.linux_available = False
                logger.warning(f"Could not check for notify-send: {e}")

    def send_notification(
        self, title: str, message: str, notification_type: str = "info", duration: int = 5
    ):
        """
        Send a desktop notification.

        Args:
            title: Notification title
            message: Notification message
            notification_type: Type of notification (info/success/warning/error)
            duration: Duration in seconds (default: 5)
        """
        try:
            if self.system == "Darwin":  # macOS
                self._send_macos_notification(title, message, duration)
            elif self.system == "Windows":
                self._send_windows_notification(title, message, duration)
            elif self.system == "Linux":
                self._send_linux_notification(title, message, notification_type, duration)
            else:
                logger.warning(f"Notifications not supported on {self.system}")
                logger.info(f"Notification: {title} - {message}")

        except Exception as e:
            logger.error(f"Error sending notification: {e}")
            # Fallback to logging
            logger.info(f"Notification ({notification_type}): {title} - {message}")

    def _send_macos_notification(self, title: str, message: str, duration: int):
        """
        Send notification on macOS using osascript.

        Args:
            title: Notification title
            message: Notification message
            duration: Duration in seconds (not used on macOS)
        """
        import subprocess

        # Escape quotes in title and message
        title = title.replace('"', '\\"')
        message = message.replace('"', '\\"')

        script = f'display notification "{message}" with title "{title}"'

        try:
            subprocess.run(["osascript", "-e", script], capture_output=True, timeout=5, check=True)
            logger.debug(f"macOS notification sent: {title}")
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to send macOS notification: {e}")
        except subprocess.TimeoutExpired:
            logger.error("macOS notification timed out")

    def _send_windows_notification(self, title: str, message: str, duration: int):
        """
        Send notification on Windows using win10toast.

        Args:
            title: Notification title
            message: Notification message
            duration: Duration in seconds
        """
        if not hasattr(self, "windows_available") or not self.windows_available:
            logger.warning("Windows notifications not available")
            logger.info(f"Notification: {title} - {message}")
            return

        try:
            from win10toast import ToastNotifier

            toaster = ToastNotifier()
            toaster.show_toast(title, message, duration=duration, threaded=True)
            logger.debug(f"Windows notification sent: {title}")

        except Exception as e:
            logger.error(f"Failed to send Windows notification: {e}")

    def _send_linux_notification(
        self, title: str, message: str, notification_type: str, duration: int
    ):
        """
        Send notification on Linux using notify-send.

        Args:
            title: Notification title
            message: Notification message
            notification_type: Type of notification (info/success/warning/error)
            duration: Duration in milliseconds
        """
        if not hasattr(self, "linux_available") or not self.linux_available:
            logger.warning("Linux notifications not available")
            logger.info(f"Notification: {title} - {message}")
            return

        import subprocess

        # Map notification type to urgency level
        urgency_map = {
            "info": "normal",
            "success": "normal",
            "warning": "normal",
            "error": "critical",
        }
        urgency = urgency_map.get(notification_type, "normal")

        # Convert duration to milliseconds
        duration_ms = duration * 1000

        try:
            subprocess.run(
                [
                    "notify-send",
                    f"--urgency={urgency}",
                    f"--expire-time={duration_ms}",
                    title,
                    message,
                ],
                capture_output=True,
                timeout=5,
                check=True,
            )
            logger.debug(f"Linux notification sent: {title}")

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to send Linux notification: {e}")
        except subprocess.TimeoutExpired:
            logger.error("Linux notification timed out")

    def send_success(self, title: str, message: str):
        """
        Send a success notification.

        Args:
            title: Notification title
            message: Notification message
        """
        self.send_notification(title, message, "success")

    def send_error(self, title: str, message: str):
        """
        Send an error notification.

        Args:
            title: Notification title
            message: Notification message
        """
        self.send_notification(title, message, "error")

    def send_warning(self, title: str, message: str):
        """
        Send a warning notification.

        Args:
            title: Notification title
            message: Notification message
        """
        self.send_notification(title, message, "warning")

    def send_info(self, title: str, message: str):
        """
        Send an info notification.

        Args:
            title: Notification title
            message: Notification message
        """
        self.send_notification(title, message, "info")


# Global notification manager instance
_notification_manager: Optional[NotificationManager] = None


def get_notification_manager() -> NotificationManager:
    """
    Get the global notification manager instance.

    Returns:
        NotificationManager instance
    """
    global _notification_manager

    if _notification_manager is None:
        _notification_manager = NotificationManager()

    return _notification_manager
