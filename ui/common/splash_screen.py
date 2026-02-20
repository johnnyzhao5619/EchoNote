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
Splash screen for application startup.

Displays a splash screen with progress updates during initialization.
"""

import logging

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QPainter, QPixmap
from PySide6.QtWidgets import QSplashScreen

from config.constants import SPLASH_SCREEN_DELAY_MS
from ui.common.theme import ThemeManager
from ui.constants import (
    SPLASH_BAR_HEIGHT,
    SPLASH_HORIZONTAL_MARGIN,
    SPLASH_PERCENT_RESERVED_WIDTH,
    SPLASH_PROGRESS_FONT_SIZE,
    SPLASH_TITLE_FONT_SIZE,
    SPLASH_VERSION_FONT_SIZE,
)

logger = logging.getLogger(__name__)


class SplashScreen(QSplashScreen):
    """
    Splash screen displayed during application startup.

    Shows application name, version, and initialization progress.
    """

    def __init__(self, width: int = 500, height: int = 300, version: str | None = None):
        """
        Initialize splash screen.

        Args:
            width: Splash screen width
            height: Splash screen height
            version: Application version label displayed on the splash screen
        """
        # Create a simple pixmap for the splash screen
        pixmap = QPixmap(width, height)

        # Use theme semantic colors for splash rendering.
        self._theme = ThemeManager()
        primary_color = self._theme.get_color("primary")
        self._text_color = self._theme.get_color("splash_text")
        self._progress_track_color = self._theme.get_color("splash_progress_track")
        self._progress_fill_color = self._theme.get_color("splash_progress_fill")
        pixmap.fill(primary_color)

        super().__init__(pixmap)

        self.width = width
        self.height = height
        self._version = self._format_version(version)

        # Set window flags
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.FramelessWindowHint)

        # Initialize progress text
        self._progress_text = "Initializing..."
        self._progress_percent = 0

        logger.debug("Splash screen initialized")

    @staticmethod
    def _format_version(version: str | None) -> str:
        """
        Return formatted version label for display.

        Args:
            version: Version string to format

        Returns:
            Formatted version string with 'v' prefix, or empty string if invalid
        """
        if not version:
            return ""

        normalized = version.strip()
        if not normalized:
            return ""

        # If already has 'v' prefix, return as-is
        if normalized.lower().startswith("v"):
            return normalized

        # Add 'v' prefix for display
        return f"v{normalized}"

    @property
    def version(self) -> str:
        """Return formatted version label displayed on the splash screen."""
        return self._version

    def drawContents(self, painter: QPainter):
        """
        Draw splash screen contents.

        Args:
            painter: QPainter instance
        """
        painter.setPen(self._text_color)

        # Draw application name
        title_font = QFont()
        title_font.setPointSize(SPLASH_TITLE_FONT_SIZE)
        title_font.setWeight(QFont.Weight.Bold)
        painter.setFont(title_font)
        painter.drawText(SPLASH_HORIZONTAL_MARGIN, 80, "EchoNote")

        # Draw version (if available)
        if self._version:
            version_font = QFont()
            version_font.setPointSize(SPLASH_VERSION_FONT_SIZE)
            painter.setFont(version_font)
            painter.drawText(SPLASH_HORIZONTAL_MARGIN, 110, self._version)

        # Draw progress text
        progress_font = QFont()
        progress_font.setPointSize(SPLASH_PROGRESS_FONT_SIZE)
        painter.setFont(progress_font)
        painter.drawText(SPLASH_HORIZONTAL_MARGIN, self.height - 60, self._progress_text)

        # Draw progress bar
        # Reserve space for percentage text (60px)
        bar_width = self.width - (2 * SPLASH_HORIZONTAL_MARGIN) - SPLASH_PERCENT_RESERVED_WIDTH
        bar_height = SPLASH_BAR_HEIGHT
        bar_x = SPLASH_HORIZONTAL_MARGIN
        bar_y = self.height - 40

        # Background
        painter.fillRect(bar_x, bar_y, bar_width, bar_height, self._progress_track_color)

        # Progress
        progress_width = int(bar_width * (self._progress_percent / 100))
        painter.fillRect(bar_x, bar_y, progress_width, bar_height, self._progress_fill_color)

        # Progress percentage (right-aligned)
        percent_text = f"{self._progress_percent}%"
        percent_font = QFont()
        percent_font.setPointSize(SPLASH_PROGRESS_FONT_SIZE)
        percent_font.setWeight(QFont.Weight.Bold)
        painter.setFont(percent_font)

        # Calculate text width for right alignment
        from PySide6.QtGui import QFontMetrics

        metrics = QFontMetrics(percent_font)
        text_width = metrics.horizontalAdvance(percent_text)

        # Draw percentage at the right edge
        painter.drawText(
            self.width - text_width - SPLASH_HORIZONTAL_MARGIN, bar_y + 15, percent_text
        )

    def show_progress(self, message: str, percent: int = None):
        """
        Update progress message and percentage.

        Args:
            message: Progress message
            percent: Progress percentage (0-100), optional
        """
        self._progress_text = message
        if percent is not None:
            self._progress_percent = max(0, min(100, percent))

        # Force repaint
        self.repaint()

        # Process events to keep UI responsive
        from PySide6.QtWidgets import QApplication

        QApplication.processEvents()

        logger.debug(f"Splash progress: {message} ({self._progress_percent}%)")

    def finish_with_delay(self, main_window, delay_ms: int = SPLASH_SCREEN_DELAY_MS):
        """
        Finish splash screen with a delay.

        Args:
            main_window: Main window to show after splash
            delay_ms: Delay in milliseconds before closing splash
        """

        def close_splash():
            self.finish(main_window)
            logger.info("Splash screen closed")

        QTimer.singleShot(delay_ms, close_splash)
