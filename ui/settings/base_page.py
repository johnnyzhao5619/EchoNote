"""
Base class for settings pages.

Provides common functionality for all settings pages.
"""

import logging
from typing import Tuple

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QScrollArea
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QFont

from utils.i18n import I18nQtManager


logger = logging.getLogger('echonote.ui.settings.base')


class BaseSettingsPage(QWidget):
    """
    Base class for settings pages.
    
    Provides common layout and functionality for all settings pages.
    """
    
    # Signal emitted when settings change
    settings_changed = pyqtSignal()
    
    def __init__(self, settings_manager, i18n: I18nQtManager):
        """
        Initialize base settings page.
        
        Args:
            settings_manager: SettingsManager instance
            i18n: Internationalization manager
        """
        super().__init__()
        
        self.settings_manager = settings_manager
        self.i18n = i18n
        
        # Main layout
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(20, 20, 20, 20)
        self.main_layout.setSpacing(15)
        
        # Create scroll area for content
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
        
        # Content widget
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setSpacing(15)
        
        scroll_area.setWidget(self.content_widget)
        self.main_layout.addWidget(scroll_area)
    
    def add_section_title(self, title: str):
        """
        Add a section title to the page.
        
        Args:
            title: Section title text
        """
        label = QLabel(title)
        font = QFont()
        font.setPointSize(12)
        font.setBold(True)
        label.setFont(font)
        self.content_layout.addWidget(label)
    
    def add_spacing(self, height: int = 10):
        """
        Add vertical spacing.
        
        Args:
            height: Spacing height in pixels
        """
        self.content_layout.addSpacing(height)
    
    def load_settings(self):
        """
        Load settings into the page.
        
        Should be overridden by subclasses.
        """
        pass
    
    def save_settings(self):
        """
        Save settings from the page.
        
        Should be overridden by subclasses.
        """
        pass
    
    def validate_settings(self) -> Tuple[bool, str]:
        """
        Validate settings before saving.
        
        Should be overridden by subclasses if validation is needed.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        return True, ""
    
    def update_translations(self):
        """
        Update UI text after language change.
        
        Should be overridden by subclasses.
        """
        pass
    
    def _emit_changed(self):
        """Emit settings changed signal."""
        self.settings_changed.emit()
