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
Theme configuration for EchoNote.
Centralized color mappings and theme settings.

This module provides:
1. Color mappings for theme conversion (Dark → Light/HC)
2. Semantic color definitions for each theme
3. Consistent color palette management
"""

# ============================================================================
# Light Theme Color Palette
# ============================================================================

LIGHT_THEME_COLORS = {
    # Background colors
    "bg_primary": "#ffffff",  # Main content background
    "bg_secondary": "#f8f9fa",  # Secondary background (sidebar, main window)
    "bg_tertiary": "#f5f5f5",  # Tertiary background
    "bg_hover": "#e9ecef",  # Hover state background
    "bg_selected": "#e3f2fd",  # Selected state background (light blue)
    "bg_pressed": "#bbdefb",  # Pressed state background
    "bg_disabled": "#e0e0e0",  # Disabled state background
    "bg_today": "#fff3e0",  # Today marker background (light orange)
    # Text colors
    "text_primary": "#212529",  # Primary text (darkest)
    "text_secondary": "#495057",  # Secondary text (dark gray)
    "text_tertiary": "#666666",  # Tertiary text (medium gray)
    "text_quaternary": "#888888",  # Quaternary text (light gray)
    "text_disabled": "#999999",  # Disabled text
    "text_selected": "#0d47a1",  # Selected text (dark blue)
    "text_inverse": "#ffffff",  # Inverse text (white on dark)
    # Border colors
    "border_light": "#e0e0e0",  # Light border
    "border_medium": "#dee2e6",  # Medium border
    "border_dark": "#adb5bd",  # Dark border
    "border_focus": "#0078d4",  # Focus border (blue)
    "border_selected": "#0078d4",  # Selected border (blue)
    "border_today": "#ff9800",  # Today border (orange)
    # Accent colors
    "accent_primary": "#0078d4",  # Primary accent (blue)
    "accent_primary_hover": "#106ebe",  # Primary accent hover
    "accent_primary_pressed": "#005a9e",  # Primary accent pressed
    "accent_success": "#28a745",  # Success (green)
    "accent_error": "#d32f2f",  # Error (red)
    "accent_warning": "#ff9800",  # Warning (orange)
    "accent_info": "#2196F3",  # Info (light blue)
}

# ============================================================================
# Color Mapping for Theme Conversion
# ============================================================================

# Color mapping for Light theme (Dark → Light)
DARK_TO_LIGHT_COLORS = {
    # Backgrounds
    "#000000": "#ffffff",
    "#1e1e1e": "#ffffff",
    "#1a1a1a": "#dee2e6",  # Sidebar border
    "#1a1d20": "#f8f9fa",
    "#212529": "#212529",
    "#252525": "#f8f9fa",
    "#2d2d2d": "#f8f9fa",
    "#2c2c2c": "#f8f9fa",  # Sidebar background
    "#2a2a2a": "#f0f0f0",
    "#353535": "#e9ecef",
    "#3a3a3a": "#e0e0e0",
    "#404040": "#0078d4",
    "#4a4a4a": "#dee2e6",
    "#5a5a5a": "#adb5bd",
    "#6a6a6a": "#6c757d",
    # Text colors
    "#e0e0e0": "#333333",
    "#e9ecef": "#212529",
    "#ffffff": "#212529",
    "#f0f0f0": "#495057",  # Sidebar text
    "#b0b0b0": "#666666",
    "#90caf9": "#1976d2",
    "#bbdefb": "#0d47a1",
    # Primary colors
    "#42a5f5": "#0078d4",
    "#64b5f6": "#106ebe",
    "#2196f3": "#005a9e",
    "#2d4a5a": "rgba(33, 150, 243, 0.1)",
    # Success colors
    "#66bb6a": "#28a745",
    "#4CAF50": "#4CAF50",
    "#a5d6a7": "#2e7d32",
    "#c8e6c9": "#1b5e20",
    "#2d5a2f": "#4CAF50",
    "#3d6a3f": "#45a049",
    # Error colors
    "#f48fb1": "#d32f2f",
    "#f44336": "#f44336",
    "#ef9a9a": "#d32f2f",
    "#ffcdd2": "#d32f2f",
    "#5a2d2d": "#f44336",
    # Warning colors
    "#ff9800": "#ff9800",
    "#ffb74d": "#ffc107",
    # Borders
    "#3a3a3a": "#dee2e6",
    "#4a4a4a": "#d0d0d0",
}

# Color mapping for High Contrast theme (Dark → High Contrast)
DARK_TO_HC_COLORS = {
    # Backgrounds - all black
    "#000000": "#000000",
    "#1e1e1e": "#000000",
    "#1a1d20": "#000000",
    "#212529": "#000000",
    "#252525": "#000000",
    "#2d2d2d": "#000000",
    "#2a2a2a": "#000000",
    "#353535": "#000000",
    "#3a3a3a": "#000000",
    "#404040": "#FFFF00",
    "#4a4a4a": "#FFFFFF",
    "#5a5a5a": "#FFFFFF",
    # Text colors - all white
    "#e0e0e0": "#FFFFFF",
    "#e9ecef": "#FFFFFF",
    "#ffffff": "#FFFFFF",
    "#b0b0b0": "#FFFFFF",
    "#90caf9": "#FFFF00",
    "#bbdefb": "#FFFF00",
    # Primary colors - yellow
    "#42a5f5": "#FFFF00",
    "#64b5f6": "#FFFF00",
    "#2196f3": "#FFFF00",
    "#2d4a5a": "#FFFF00",
    # Success colors - green
    "#66bb6a": "#00FF00",
    "#4CAF50": "#00FF00",
    "#a5d6a7": "#00FF00",
    "#c8e6c9": "#00FF00",
    "#2d5a2f": "#00FF00",
    "#3d6a3f": "#00FF00",
    # Error colors - red
    "#f48fb1": "#FF0000",
    "#f44336": "#FF0000",
    "#ef9a9a": "#FF0000",
    "#ffcdd2": "#FF0000",
    "#5a2d2d": "#FF0000",
    # Warning colors - yellow
    "#ff9800": "#FFFF00",
    "#ffb74d": "#FFFF00",
    # Borders - white and thicker
    "#3a3a3a": "#FFFFFF",
    "#4a4a4a": "#FFFFFF",
}

# Theme metadata
THEME_INFO = {
    "dark": {
        "name": "Dark",
        "description": "Dark theme with blue accents",
        "file": "dark.qss",
    },
    "light": {
        "name": "Light",
        "description": "Light theme with blue accents",
        "file": "light.qss",
        "color_map": DARK_TO_LIGHT_COLORS,
    },
    "high_contrast": {
        "name": "High Contrast",
        "description": "High contrast theme for accessibility (WCAG AAA)",
        "file": "high_contrast.qss",
        "color_map": DARK_TO_HC_COLORS,
    },
}
