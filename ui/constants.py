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
UI-specific constants for EchoNote application.

This module contains constants that are specific to the user interface layer,
including visual elements, layouts, and UI-specific timing values.
For application-wide constants, see config.constants.
"""

# ============================================================================
# Visual Display Constants
# ============================================================================

# Progress and Time Display
DEFAULT_PROGRESS_PERCENTAGE = "0%"
DEFAULT_TIME_FORMAT = "00:00:00"

# Gain Control Display
DEFAULT_GAIN_MULTIPLIER = "1.0x"
MIN_GAIN_MULTIPLIER = "0.1x"
MAX_GAIN_MULTIPLIER = "2.0x"

# ============================================================================
# UI Symbols and Icons
# ============================================================================

# Navigation Symbols (consider using proper icons instead)
PREVIOUS_SYMBOL = "↑"
NEXT_SYMBOL = "↓"
CLOSE_SYMBOL = "×"
LEFT_ARROW = "<"
RIGHT_ARROW = ">"

# Icon Symbols (consider using proper icons instead)
LOCATION_ICON = "📍"
ATTENDEES_ICON = "👥"
WARNING_ICON = "⚠️"
INDICATOR_SYMBOL = "●"
EYE_ICON = "👁"
PLAY_SYMBOL = "▶"
PAUSE_SYMBOL = "⏸"
VOLUME_ICON = "🔊"

# ============================================================================
# File Dialog Filters
# ============================================================================

AUDIO_FILE_FILTER = "Audio Files (*.wav *.mp3 *.flac *.m4a *.ogg);;All Files (*)"
TEXT_FILE_FILTER = "Text Files (*.txt);;Markdown Files (*.md);;All Files (*)"
EXPORT_FILE_FILTER = "Text Files (*.txt);;Markdown Files (*.md);;All Files (*)"

# ============================================================================
# UI Layout and Sizing Constants
# ============================================================================

# Layout Spacing
DEFAULT_LAYOUT_SPACING = 10

# Button Sizes
BUTTON_FIXED_WIDTH_SMALL = 20
BUTTON_FIXED_WIDTH_MEDIUM = 30
BUTTON_FIXED_WIDTH_LARGE = 40
BUTTON_FIXED_WIDTH_XLARGE = 50

# Component Widths
SIDEBAR_WIDTH = 200
SEARCH_INPUT_MIN_WIDTH = 250
COMBO_BOX_MIN_WIDTH = 150
COMBO_BOX_MAX_WIDTH = 200
GAIN_SLIDER_MIN_WIDTH = 150
GAIN_SLIDER_MAX_WIDTH = 250
GAIN_VALUE_MIN_WIDTH = 50
LABEL_MIN_WIDTH = 100

# Window and Dialog Sizes
MINIMUM_WINDOW_WIDTH = 1024
MINIMUM_WINDOW_HEIGHT = 768
DIALOG_MIN_WIDTH_SMALL = 300
DIALOG_MIN_WIDTH_MEDIUM = 400
DIALOG_MIN_WIDTH_LARGE = 500
DIALOG_MIN_WIDTH_XLARGE = 600
DIALOG_MIN_HEIGHT_SMALL = 150
DIALOG_MIN_HEIGHT_MEDIUM = 400

# Component Heights
BUTTON_MIN_HEIGHT = 36
BUTTON_MIN_HEIGHT_LARGE = 40
SIDEBAR_BUTTON_MIN_HEIGHT = 50
TASK_ITEM_MIN_HEIGHT = 150
AUDIO_VISUALIZER_MIN_HEIGHT = 50
AUDIO_VISUALIZER_MAX_HEIGHT = 70
TEXT_AREA_MIN_HEIGHT = 150
CALENDAR_CELL_MIN_HEIGHT = 80
PREVIEW_FRAME_MIN_HEIGHT = 150

# Visual Elements
SEPARATOR_LINE_HEIGHT = 2

# ============================================================================
# UI Color Constants - DEPRECATED
# ============================================================================
# Note: All colors have been moved to QSS theme files for proper theming support.
# Use setProperty() and setObjectName() with semantic role/state attributes instead.
#
# Example migration:
#   OLD: label.setProperty("role", "time-display")
#   NEW: label.setProperty("role", "description")
#        # Then define in QSS: QLabel[role="description"] { color: #666; }
#
# This ensures proper theming across light/dark/high-contrast themes.

# ============================================================================
# UI-Specific Timing Constants (milliseconds)
# ============================================================================

# User Feedback Delays
NOTIFICATION_RESET_DELAY_MS = 2000  # 2 seconds
OAUTH_RESET_DELAY_MS = 2000  # 2 seconds
OAUTH_CLOSE_DELAY_MS = 1000  # 1 second

# UI Responsiveness
STARTUP_DELAY_MS = 100  # 100 milliseconds
TIMER_SINGLE_SHOT_DELAY_MS = 100  # 100 milliseconds

# ============================================================================
# UI Operation Timeouts (seconds)
# ============================================================================
# Note: These are UI-specific timeouts for user operations

DATABASE_TIMEOUT_SECONDS = 30.0
HTTP_TIMEOUT_SECONDS = 30.0
HTTP_DOWNLOAD_TIMEOUT_SECONDS = 60.0
TASK_STOP_TIMEOUT_SECONDS = 5.0
THREAD_JOIN_TIMEOUT_SECONDS = 2.0
PROCESSING_TIMEOUT_SECONDS = 5.0
ASYNC_WAIT_TIMEOUT_SECONDS = 0.5
QUEUE_GET_TIMEOUT_SECONDS = 0.2

# ============================================================================
# Default Paths
# ============================================================================
# Note: These are fallback defaults. Actual paths should come from configuration.
# Import from config constants to avoid duplication - done at runtime to avoid circular imports
