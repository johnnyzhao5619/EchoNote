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
Window state management for transcript viewer.

Extracted from transcript_viewer.py to reduce class size and improve separation of concerns.
"""

import logging

from core.qt_imports import QObject, QPoint, QRect, QSettings, QSize, Qt
from core.qt_imports import QApplication

logger = logging.getLogger("echonote.ui.window_state_manager")


class WindowStateManager:
    """Manages window state persistence for transcript viewer."""

    def __init__(self, widget):
        """
        Initialize window state manager.

        Args:
            widget: The widget to manage state for
        """
        self.widget = widget
        self.settings = QSettings("EchoNote", "TranscriptViewer")

    def save_window_state(self):
        """Save window geometry and state to settings."""
        try:
            self.settings.setValue("geometry", self.widget.saveGeometry())
            if hasattr(self.widget, "saveState"):
                self.settings.setValue("windowState", self.widget.saveState())
            self.settings.setValue("size", self.widget.size())
            self.settings.setValue("pos", self.widget.pos())
            logger.debug("Window state saved")
        except Exception as e:
            logger.error(f"Error saving window state: {e}")

    def restore_window_state(self):
        """Restore window geometry and state from settings."""
        try:
            # Restore geometry
            geometry = self.settings.value("geometry")
            if geometry:
                self.widget.restoreGeometry(geometry)
            else:
                # Default size if no saved geometry
                self.widget.resize(QSize(1000, 700))
                self._center_window()

            # Restore window state if available
            if hasattr(self.widget, "restoreState"):
                window_state = self.settings.value("windowState")
                if window_state:
                    self.widget.restoreState(window_state)

            logger.debug("Window state restored")
        except Exception as e:
            logger.error(f"Error restoring window state: {e}")

    def _center_window(self):
        """Center the window on the screen."""
        try:
            screen = QApplication.primaryScreen()
            if screen:
                screen_geometry = screen.availableGeometry()
                window_geometry = self.widget.frameGeometry()
                center_point = screen_geometry.center()
                window_geometry.moveCenter(center_point)
                self.widget.move(window_geometry.topLeft())
        except Exception as e:
            logger.debug(f"Could not center window: {e}")
