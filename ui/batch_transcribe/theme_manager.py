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
Theme management for transcript viewer.

Extracted from transcript_viewer.py to reduce class size and improve separation of concerns.
"""

import logging
import platform
from pathlib import Path

from PySide6.QtWidgets import QApplication

logger = logging.getLogger("echonote.ui.theme_manager")


class TranscriptViewerThemeManager:
    """Manages theme application for transcript viewer."""

    def __init__(self, widget, settings_manager=None):
        """
        Initialize theme manager.

        Args:
            widget: The widget to apply themes to
            settings_manager: Settings manager for theme detection
        """
        self.widget = widget
        self.settings_manager = settings_manager

    def apply_theme(self, theme: str = None):
        """
        Apply theme to the viewer.

        Args:
            theme: Theme name ('light', 'dark', 'high_contrast', 'auto')
        """
        try:
            if not theme:
                if self.settings_manager:
                    theme = self.settings_manager.get_setting("ui.theme") or "auto"
                else:
                    theme = "auto"

            if theme == "auto":
                theme = self._detect_system_theme()

            # Load theme stylesheet
            theme_path = Path("resources/themes") / f"{theme}.qss"

            if theme_path.exists():
                with open(theme_path, "r", encoding="utf-8") as f:
                    stylesheet = f.read()
                self.widget.setStyleSheet(stylesheet)
                logger.debug(f"Applied theme: {theme}")
            else:
                logger.warning(f"Theme file not found: {theme_path}")
                # Apply default light theme
                self.widget.setStyleSheet("")

        except Exception as e:
            logger.error(f"Error applying theme: {e}")

    def _detect_system_theme(self) -> str:
        """
        Detect system theme preference.

        Returns:
            Theme name ('light' or 'dark')
        """
        try:
            # Try to detect system theme
            if platform.system() == "Darwin":  # macOS
                try:
                    import subprocess

                    result = subprocess.run(
                        ["defaults", "read", "-g", "AppleInterfaceStyle"],
                        capture_output=True,
                        text=True,
                        timeout=5,
                    )
                    if result.returncode == 0 and "Dark" in result.stdout:
                        return "dark"
                except Exception:
                    pass

            elif platform.system() == "Windows":  # Windows
                try:
                    import winreg

                    registry = winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER)
                    key = winreg.OpenKey(
                        registry, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
                    )
                    value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
                    winreg.CloseKey(key)
                    return "light" if value else "dark"
                except Exception:
                    pass

            elif platform.system() == "Linux":  # Linux
                try:
                    # Try to read GTK theme
                    gtk_settings = Path.home() / ".config" / "gtk-3.0" / "settings.ini"
                    if gtk_settings.exists():
                        with open(gtk_settings, "r") as f:
                            content = f.read()
                            if "gtk-application-prefer-dark-theme=1" in content:
                                return "dark"
                except Exception:
                    pass

            # Check Qt application palette as fallback
            app = QApplication.instance()
            if app:
                palette = app.palette()
                # If window color is darker than text color, assume dark theme
                window_color = palette.color(palette.ColorRole.Window)
                text_color = palette.color(palette.ColorRole.WindowText)

                window_brightness = (
                    window_color.red() * 0.299
                    + window_color.green() * 0.587
                    + window_color.blue() * 0.114
                )
                text_brightness = (
                    text_color.red() * 0.299
                    + text_color.green() * 0.587
                    + text_color.blue() * 0.114
                )

                if window_brightness < text_brightness:
                    return "dark"

        except Exception as e:
            logger.debug(f"Error detecting system theme: {e}")

        # Default to light theme
        return "light"
