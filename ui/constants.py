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
UI Constants for EchoNote application.

Centralized constants to avoid hardcoding values throughout the UI layer.
"""

# Search widget constants
SEARCH_DEBOUNCE_DELAY_MS = 300
SEARCH_INPUT_MIN_WIDTH = 200
LARGE_DOCUMENT_THRESHOLD = 50000

# Button size constants
BUTTON_FIXED_WIDTH_SMALL = 30
BUTTON_FIXED_WIDTH_MEDIUM = 60
BUTTON_FIXED_WIDTH_LARGE = 80

# Notification constants
NOTIFICATION_RESET_DELAY_MS = 2000

# Layout constants
DEFAULT_SPACING = 8
DEFAULT_MARGINS = (12, 12, 12, 12)

# Performance constants
MAX_SEARCH_RESULTS = 1000
PAGINATION_THRESHOLD = 0.8

# Theme constants
HIGHLIGHT_COLORS = {"light": "#FFEB3B", "dark": "#FF9800", "high_contrast": "#FFFF00"}

# Sidebar constants
SIDEBAR_WIDTH = 200
SIDEBAR_BUTTON_MIN_HEIGHT = 50

# Layout constants (extended)
DEFAULT_LAYOUT_SPACING = 8
LABEL_MIN_WIDTH = 120
