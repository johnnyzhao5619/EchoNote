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
Theme Manager for EchoNote.

Centralizes color definitions and theme state management to ensure consistency
between QSS stylesheets and custom-painted widgets.
"""

import logging
from typing import Dict, Optional
from PySide6.QtGui import QColor

logger = logging.getLogger(__name__)


class ThemeManager:
    """
    Manages application theme colors and state.
    Provides a single source of truth for UI colors.
    """

    THEMES = ("light", "dark", "system")
    THEME_TO_INDEX = {"light": 0, "dark": 1, "system": 2}
    INDEX_TO_THEME = {index: name for name, index in THEME_TO_INDEX.items()}

    # Color palettes
    # Based on Material Design Blue (#2196F3) for primary brand color
    PALETTES = {
        "light": {
            "primary": "#2196F3",  # Blue 500
            "primary_hover": "#1976D2",  # Blue 700
            "primary_pressed": "#0D47A1",  # Blue 900
            "background": "#FFFFFF",
            "surface": "#F5F5F5",
            "text": "#212121",
            "text_secondary": "#757575",
            "border": "#E0E0E0",
            "success": "#4CAF50",
            "warning": "#FF9800",
            "error": "#F44336",
            "info": "#2196F3",
            "highlight": "#BBDEFB",  # Blue 100 (for search highlights)
            "splash_text": "#FFFFFF",
            "splash_progress_track": "#80FFFFFF",
            "splash_progress_fill": "#FFFFFF",
        },
        "dark": {
            "primary": "#2196F3",  # Blue 500
            "primary_hover": "#64B5F6",  # Blue 300
            "primary_pressed": "#90CAF9",  # Blue 200
            "background": "#212121",  # Modified slightly from pure black
            "surface": "#424242",
            "text": "#FAFAFA",
            "text_secondary": "#BDBDBD",
            "border": "#616161",
            "success": "#81C784",
            "warning": "#FFB74D",
            "error": "#E57373",
            "info": "#64B5F6",
            "highlight": "#1565C0",  # Blue 800 (for search highlights)
            "splash_text": "#FFFFFF",
            "splash_progress_track": "#80FFFFFF",
            "splash_progress_fill": "#FFFFFF",
        },
    }

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ThemeManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._current_theme = "light"
        self._initialized = True
        logger.info("ThemeManager initialized")

    @classmethod
    def normalize_theme_name(cls, theme_name: Optional[str], default: str = "light") -> str:
        """Normalize theme name to supported values."""
        if not isinstance(theme_name, str):
            return default
        normalized = theme_name.strip().lower()
        return normalized if normalized in cls.THEMES else default

    @classmethod
    def theme_to_index(cls, theme_name: Optional[str]) -> int:
        """Convert theme name to appearance combo index."""
        normalized = cls.normalize_theme_name(theme_name, default="light")
        return cls.THEME_TO_INDEX.get(normalized, cls.THEME_TO_INDEX["light"])

    @classmethod
    def index_to_theme(cls, index: int, default: str = "light") -> str:
        """Convert appearance combo index to theme name."""
        return cls.INDEX_TO_THEME.get(index, default)

    def set_theme(self, theme_name: str):
        """
        Set the current active theme.
        
        Args:
            theme_name: 'light' or 'dark'. If 'system', it should be resolved
                       to 'light' or 'dark' before calling this method.
        """
        normalized = self.normalize_theme_name(theme_name, default="light")
        if normalized != theme_name:
            logger.warning("Unknown theme '%s', defaulting to 'light'", theme_name)
        self._current_theme = normalized
        logger.debug("Theme set to: %s", normalized)

    def get_color(self, color_name: str, theme: Optional[str] = None) -> QColor:
        """
        Get a QColor object for a semantic color name.
        
        Args:
            color_name: Name of the color (e.g., 'primary', 'background')
            theme: Optional override for theme name
            
        Returns:
            QColor object corresponding to the color
        """
        target_theme = self.normalize_theme_name(theme or self._current_theme, default="light")
        if target_theme == "system":
            # In a real app we might detect system theme, but here we assume caller resolves it
            # or we default to light if not resolved
            target_theme = "light"

        palette = self.PALETTES.get(target_theme, self.PALETTES["light"])
        color_hex = palette.get(color_name)
        if color_hex is None:
            logger.warning(
                "Unknown color token '%s' for theme '%s', using primary fallback",
                color_name,
                target_theme,
            )
            color_hex = palette["primary"]

        return QColor(color_hex)

    def get_palette(self, theme: Optional[str] = None) -> Dict[str, str]:
        """Get the full palette dictionary for a theme."""
        target_theme = self.normalize_theme_name(theme or self._current_theme, default="light")
        if target_theme == "system":
            target_theme = "light"
        return self.PALETTES.get(target_theme, self.PALETTES["light"])
