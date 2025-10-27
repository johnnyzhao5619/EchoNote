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
Layout utility functions for common UI patterns.

This module provides utility functions for common layout patterns to reduce
code duplication across the UI layer.
"""

from ui.constants import DEFAULT_LAYOUT_SPACING, LABEL_MIN_WIDTH
from ui.qt_imports import QHBoxLayout, QLabel, QVBoxLayout, QWidget


def create_horizontal_layout(spacing: int = None, margins: tuple = (0, 0, 0, 0)) -> QHBoxLayout:
    """Create a horizontal layout with standard settings."""
    if spacing is None:
        spacing = DEFAULT_LAYOUT_SPACING

    layout = QHBoxLayout()
    layout.setSpacing(spacing)
    layout.setContentsMargins(*margins)
    return layout


def create_vertical_layout(spacing: int = None, margins: tuple = (0, 0, 0, 0)) -> QVBoxLayout:
    """Create a vertical layout with standard settings."""
    if spacing is None:
        spacing = DEFAULT_LAYOUT_SPACING

    layout = QVBoxLayout()
    layout.setSpacing(spacing)
    layout.setContentsMargins(*margins)
    return layout


def create_label_control_row(
    label_text: str, control_widget: QWidget, label_width: int = None, spacing: int = None
) -> QHBoxLayout:
    """
    Create a horizontal layout with label and control widget.

    Common pattern used in settings pages.
    """
    if spacing is None:
        spacing = DEFAULT_LAYOUT_SPACING

    layout = create_horizontal_layout(spacing=spacing)

    label = QLabel(label_text)
    if label_width is None:
        label_width = LABEL_MIN_WIDTH
    label.setMinimumWidth(label_width)
    layout.addWidget(label)
    layout.addWidget(control_widget)
    layout.addStretch()

    return layout
