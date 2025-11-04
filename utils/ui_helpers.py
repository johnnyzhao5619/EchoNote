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
UI helper utilities for EchoNote application.

Provides functions for consistent styling, animations, and responsive layouts.
"""

import logging
from typing import Optional

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QSize, Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QFrame, QGraphicsOpacityEffect, QLabel, QWidget

logger = logging.getLogger("echonote.utils.ui_helpers")


class UIHelper:
    """
    Helper class for UI operations.

    Provides methods for animations, styling, and responsive layouts.
    """

    @staticmethod
    def fade_in(widget: QWidget, duration: int = 300):
        """
        Fade in a widget.

        Args:
            widget: Widget to fade in
            duration: Animation duration in milliseconds
        """
        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)

        animation = QPropertyAnimation(effect, b"opacity")
        animation.setDuration(duration)
        animation.setStartValue(0.0)
        animation.setEndValue(1.0)
        animation.setEasingCurve(QEasingCurve.Type.InOutQuad)
        animation.start()

        # Store animation reference to prevent garbage collection
        widget._fade_animation = animation

        logger.debug(f"Fade in animation started for {widget.__class__.__name__}")

    @staticmethod
    def fade_out(widget: QWidget, duration: int = 300, callback: Optional[callable] = None):
        """
        Fade out a widget.

        Args:
            widget: Widget to fade out
            duration: Animation duration in milliseconds
            callback: Optional callback to call after animation completes
        """
        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)

        animation = QPropertyAnimation(effect, b"opacity")
        animation.setDuration(duration)
        animation.setStartValue(1.0)
        animation.setEndValue(0.0)
        animation.setEasingCurve(QEasingCurve.Type.InOutQuad)

        if callback:
            animation.finished.connect(callback)

        animation.start()

        # Store animation reference to prevent garbage collection
        widget._fade_animation = animation

        logger.debug(f"Fade out animation started for {widget.__class__.__name__}")

    @staticmethod
    def slide_in(widget: QWidget, direction: str = "left", duration: int = 300):
        """
        Slide in a widget from a direction.

        Args:
            widget: Widget to slide in
            direction: Direction to slide from ('left', 'right', 'top', 'bottom')
            duration: Animation duration in milliseconds
        """
        # Get widget geometry
        start_pos = widget.pos()

        # Calculate start position based on direction
        if direction == "left":
            widget.move(start_pos.x() - widget.width(), start_pos.y())
        elif direction == "right":
            widget.move(start_pos.x() + widget.width(), start_pos.y())
        elif direction == "top":
            widget.move(start_pos.x(), start_pos.y() - widget.height())
        elif direction == "bottom":
            widget.move(start_pos.x(), start_pos.y() + widget.height())

        # Create animation
        animation = QPropertyAnimation(widget, b"pos")
        animation.setDuration(duration)
        animation.setEndValue(start_pos)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        animation.start()

        # Store animation reference
        widget._slide_animation = animation

        logger.debug(f"Slide in animation started for {widget.__class__.__name__}")

    @staticmethod
    def create_loading_label(text: str = "Loading...") -> QLabel:
        """
        Create a loading label with animation.

        Args:
            text: Loading text

        Returns:
            Animated loading label
        """
        label = QLabel(text)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Add animation
        timer = QTimer(label)
        dots = [".", "..", "..."]
        current_dot = [0]

        def update_text():
            current_dot[0] = (current_dot[0] + 1) % len(dots)
            label.setText(f"{text.rstrip('.')}{dots[current_dot[0]]}")

        timer.timeout.connect(update_text)
        timer.start(500)

        # Store timer reference
        label._loading_timer = timer

        return label

    @staticmethod
    def create_empty_state_widget(icon_text: str, title: str, description: str) -> QWidget:
        """
        Create an empty state widget.

        Args:
            icon_text: Icon or emoji text
            title: Empty state title
            description: Empty state description

        Returns:
            Empty state widget
        """
        from PySide6.QtWidgets import QVBoxLayout

        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(15)

        # Icon
        icon_label = QLabel(icon_text)
        icon_font = QFont()
        icon_font.setPointSize(48)
        icon_label.setFont(icon_font)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon_label)

        # Title
        title_label = QLabel(title)
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)

        # Description
        desc_label = QLabel(description)
        desc_label.setWordWrap(True)
        desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc_label.setProperty("role", "time-display")
        layout.addWidget(desc_label)

        return widget

    @staticmethod
    def set_responsive_size(widget: QWidget, base_width: int, base_height: int):
        """
        Set responsive size for a widget based on screen size.

        Args:
            widget: Widget to set size for
            base_width: Base width
            base_height: Base height
        """
        from PySide6.QtWidgets import QApplication

        screen = QApplication.primaryScreen()
        if screen:
            screen_size = screen.size()

            # Calculate responsive size (max 90% of screen)
            max_width = int(screen_size.width() * 0.9)
            max_height = int(screen_size.height() * 0.9)

            width = min(base_width, max_width)
            height = min(base_height, max_height)

            widget.resize(width, height)

            logger.debug(f"Set responsive size: {width}x{height}")

    @staticmethod
    def add_separator(parent_layout, margin: int = 10):
        """
        Add a horizontal separator line to a layout.

        Args:
            parent_layout: Layout to add separator to
            margin: Margin around separator
        """
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        separator.setContentsMargins(margin, margin, margin, margin)
        parent_layout.addWidget(separator)

    @staticmethod
    def create_section_title(text: str) -> QLabel:
        """
        Create a styled section title label.

        Args:
            text: Title text

        Returns:
            Styled title label
        """
        label = QLabel(text)
        label.setObjectName("section_title")

        font = QFont()
        font.setPointSize(16)
        font.setBold(True)
        label.setFont(font)

        return label

    @staticmethod
    def create_page_title(text: str) -> QLabel:
        """
        Create a styled page title label.

        Args:
            text: Title text

        Returns:
            Styled title label
        """
        label = QLabel(text)
        label.setObjectName("page_title")

        font = QFont()
        font.setPointSize(20)
        font.setBold(True)
        label.setFont(font)

        return label

    @staticmethod
    def show_tooltip(widget: QWidget, text: str, duration: int = 3000):
        """
        Show a temporary tooltip on a widget.

        Args:
            widget: Widget to show tooltip on
            text: Tooltip text
            duration: Duration to show tooltip in milliseconds
        """
        widget.setToolTip(text)

        # Clear tooltip after duration
        QTimer.singleShot(duration, lambda: widget.setToolTip(""))

        logger.debug(f"Showed tooltip: {text}")

    @staticmethod
    def apply_card_style(widget: QWidget):
        """
        Apply card-like styling to a widget.

        Args:
            widget: Widget to style
        """
        widget.setProperty("role", "card")

    @staticmethod
    def apply_hover_effect(widget: QWidget):
        """
        Apply hover effect to a widget.

        Args:
            widget: Widget to apply effect to
        """
        widget.setProperty("hoverEffect", True)
        widget.style().unpolish(widget)
        widget.style().polish(widget)


def create_icon_button(icon_text: str, tooltip: str = ""):
    """
    Create an icon button with emoji or text.

    Args:
        icon_text: Icon text (emoji or character)
        tooltip: Tooltip text

    Returns:
        Icon button
    """
    from PySide6.QtWidgets import QPushButton

    button = QPushButton(icon_text)
    button.setFixedSize(QSize(40, 40))

    if tooltip:
        button.setToolTip(tooltip)

    font = QFont()
    font.setPointSize(16)
    button.setFont(font)

    return button


def create_badge(text: str, color: str = None) -> QLabel:
    """
    Create a badge label.

    Args:
        text: Badge text
        color: Badge background color

    Returns:
        Badge label
    """
    badge = QLabel(text)
    badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
    badge.setProperty("role", "badge")
    badge.setFixedHeight(20)

    return badge


def show_success_message(parent: QWidget, message: str, i18n=None):
    """
    Show a success message to the user.

    Args:
        parent: Parent widget
        message: Success message
        i18n: Optional i18n manager for translations
    """
    from PySide6.QtWidgets import QMessageBox

    msg_box = QMessageBox(parent)
    msg_box.setIcon(QMessageBox.Icon.Information)
    msg_box.setWindowTitle(i18n.t("common.success") if i18n else "Success")
    msg_box.setText(message)
    msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
    msg_box.exec()


def show_error_message(parent: QWidget, message: str, details: Optional[str] = None):
    """
    Show an error message to the user.

    Args:
        parent: Parent widget
        message: Error message
        details: Optional error details
    """
    from ui.common.error_dialog import show_error_dialog

    show_error_dialog("Error", message, details, parent=parent)


def confirm_action(parent: QWidget, title: str, message: str) -> bool:
    """
    Show a confirmation dialog.

    Args:
        parent: Parent widget
        title: Dialog title
        message: Confirmation message

    Returns:
        True if user confirmed
    """
    from PySide6.QtWidgets import QMessageBox

    reply = QMessageBox.question(
        parent,
        title,
        message,
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.No,
    )

    return reply == QMessageBox.StandardButton.Yes
