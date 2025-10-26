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
Accessibility utilities for EchoNote application.

Provides functions and helpers to improve accessibility including
keyboard navigation, screen reader support, and focus management.
"""

import logging
from typing import Optional, List
from PySide6.QtWidgets import QWidget, QPushButton, QLineEdit, QTextEdit, QComboBox
from PySide6.QtCore import Qt, QEvent
from PySide6.QtGui import QKeyEvent, QFocusEvent


logger = logging.getLogger('echonote.utils.accessibility')


class AccessibilityHelper:
    """
    Helper class for managing accessibility features.
    
    Provides methods to enhance keyboard navigation, screen reader support,
    and focus management across the application.
    """
    
    @staticmethod
    def set_accessible_name(widget: QWidget, name: str):
        """
        Set accessible name for screen readers.
        
        Args:
            widget: Widget to set accessible name for
            name: Accessible name
        """
        widget.setAccessibleName(name)
        logger.debug(f"Set accessible name '{name}' for {widget.__class__.__name__}")
    
    @staticmethod
    def set_accessible_description(widget: QWidget, description: str):
        """
        Set accessible description for screen readers.
        
        Args:
            widget: Widget to set accessible description for
            description: Accessible description
        """
        widget.setAccessibleDescription(description)
        logger.debug(f"Set accessible description for {widget.__class__.__name__}")
    
    @staticmethod
    def enable_keyboard_navigation(widget: QWidget):
        """
        Enable keyboard navigation for a widget.
        
        Args:
            widget: Widget to enable keyboard navigation for
        """
        widget.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        widget.setTabOrder(widget, widget)
    
    @staticmethod
    def set_tab_order(widgets: List[QWidget]):
        """
        Set tab order for a list of widgets.
        
        Args:
            widgets: List of widgets in desired tab order
        """
        for i in range(len(widgets) - 1):
            QWidget.setTabOrder(widgets[i], widgets[i + 1])
        
        logger.debug(f"Set tab order for {len(widgets)} widgets")
    
    @staticmethod
    def add_keyboard_shortcut(
        widget: QWidget,
        key: Qt.Key,
        modifier: Qt.KeyboardModifier = Qt.KeyboardModifier.NoModifier,
        callback: callable = None
    ):
        """
        Add keyboard shortcut to a widget.
        
        Args:
            widget: Widget to add shortcut to
            key: Key for shortcut
            modifier: Keyboard modifier (Ctrl, Alt, etc.)
            callback: Function to call when shortcut is triggered
        """
        # Install event filter for keyboard shortcuts
        if not hasattr(widget, '_keyboard_shortcuts'):
            widget._keyboard_shortcuts = {}
            widget.installEventFilter(KeyboardShortcutFilter(widget))
        
        shortcut_key = (key, modifier)
        widget._keyboard_shortcuts[shortcut_key] = callback
        
        logger.debug(f"Added keyboard shortcut {key} to {widget.__class__.__name__}")
    
    @staticmethod
    def set_focus_indicator(widget: QWidget, enabled: bool = True):
        """
        Enable or disable focus indicator for a widget.
        
        Args:
            widget: Widget to set focus indicator for
            enabled: Whether to enable focus indicator
        """
        if enabled:
            widget.setProperty("showFocusIndicator", True)
        else:
            widget.setProperty("showFocusIndicator", False)
        
        # Force style update
        widget.style().unpolish(widget)
        widget.style().polish(widget)
    
    @staticmethod
    def announce_to_screen_reader(widget: QWidget, message: str):
        """
        Announce a message to screen readers.
        
        Args:
            widget: Widget context for announcement
            message: Message to announce
        """
        # Set accessible description temporarily for announcement
        original_desc = widget.accessibleDescription()
        widget.setAccessibleDescription(message)
        
        # Reset after a short delay
        from PySide6.QtCore import QTimer
        QTimer.singleShot(100, lambda: widget.setAccessibleDescription(original_desc))
        
        logger.debug(f"Announced to screen reader: {message}")


class KeyboardShortcutFilter(QEvent):
    """Event filter for handling keyboard shortcuts."""
    
    def __init__(self, parent: QWidget):
        """
        Initialize keyboard shortcut filter.
        
        Args:
            parent: Parent widget
        """
        super().__init__(QEvent.Type.KeyPress)
        self.parent = parent
    
    def eventFilter(self, obj: QWidget, event: QEvent) -> bool:
        """
        Filter keyboard events for shortcuts.
        
        Args:
            obj: Object receiving event
            event: Event to filter
        
        Returns:
            True if event was handled
        """
        if event.type() == QEvent.Type.KeyPress and hasattr(self.parent, '_keyboard_shortcuts'):
            key_event = QKeyEvent(event)
            shortcut_key = (key_event.key(), key_event.modifiers())
            
            if shortcut_key in self.parent._keyboard_shortcuts:
                callback = self.parent._keyboard_shortcuts[shortcut_key]
                if callback:
                    callback()
                return True
        
        return False


class FocusManager:
    """
    Manager for focus handling and navigation.
    
    Provides methods to manage focus order, focus trapping,
    and focus restoration.
    """
    
    def __init__(self):
        """Initialize focus manager."""
        self.focus_stack: List[QWidget] = []
    
    def save_focus(self, widget: QWidget):
        """
        Save current focus widget.
        
        Args:
            widget: Widget to save focus for
        """
        focused = widget.focusWidget()
        if focused:
            self.focus_stack.append(focused)
            logger.debug(f"Saved focus for {focused.__class__.__name__}")
    
    def restore_focus(self):
        """Restore previously saved focus."""
        if self.focus_stack:
            widget = self.focus_stack.pop()
            widget.setFocus()
            logger.debug(f"Restored focus to {widget.__class__.__name__}")
    
    def trap_focus(self, container: QWidget, widgets: List[QWidget]):
        """
        Trap focus within a container (e.g., for modal dialogs).
        
        Args:
            container: Container widget
            widgets: List of focusable widgets in container
        """
        if not widgets:
            return
        
        # Set tab order to cycle within container
        for i in range(len(widgets)):
            next_widget = widgets[(i + 1) % len(widgets)]
            QWidget.setTabOrder(widgets[i], next_widget)
        
        logger.debug(f"Trapped focus in {container.__class__.__name__}")


def make_accessible_button(
    button: QPushButton,
    name: str,
    description: Optional[str] = None,
    shortcut: Optional[str] = None
) -> QPushButton:
    """
    Make a button accessible with proper attributes.
    
    Args:
        button: Button to make accessible
        name: Accessible name
        description: Optional accessible description
        shortcut: Optional keyboard shortcut
    
    Returns:
        Enhanced button
    """
    button.setAccessibleName(name)
    
    if description:
        button.setAccessibleDescription(description)
    
    if shortcut:
        button.setShortcut(shortcut)
        button.setToolTip(f"{button.toolTip() or name} ({shortcut})")
    
    # Enable keyboard focus
    button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    
    return button


def make_accessible_input(
    input_widget: QWidget,
    label_text: str,
    description: Optional[str] = None,
    placeholder: Optional[str] = None
) -> QWidget:
    """
    Make an input widget accessible.
    
    Args:
        input_widget: Input widget (QLineEdit, QTextEdit, etc.)
        label_text: Label text for the input
        description: Optional accessible description
        placeholder: Optional placeholder text
    
    Returns:
        Enhanced input widget
    """
    input_widget.setAccessibleName(label_text)
    
    if description:
        input_widget.setAccessibleDescription(description)
    
    if placeholder and isinstance(input_widget, (QLineEdit, QTextEdit)):
        input_widget.setPlaceholderText(placeholder)
    
    # Enable keyboard focus
    input_widget.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    
    return input_widget


def make_accessible_combobox(
    combobox: QComboBox,
    label_text: str,
    description: Optional[str] = None
) -> QComboBox:
    """
    Make a combobox accessible.
    
    Args:
        combobox: Combobox to make accessible
        label_text: Label text for the combobox
        description: Optional accessible description
    
    Returns:
        Enhanced combobox
    """
    combobox.setAccessibleName(label_text)
    
    if description:
        combobox.setAccessibleDescription(description)
    
    # Enable keyboard focus
    combobox.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    
    return combobox


# Global focus manager instance
focus_manager = FocusManager()
