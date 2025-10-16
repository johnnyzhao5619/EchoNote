"""
Language settings page.

Provides UI for configuring language preferences.
"""

import logging
from typing import Tuple

from PyQt6.QtWidgets import (
    QLabel, QComboBox, QHBoxLayout
)
from PyQt6.QtCore import Qt

from ui.settings.base_page import BaseSettingsPage
from utils.i18n import I18nQtManager


logger = logging.getLogger('echonote.ui.settings.language')


class LanguageSettingsPage(BaseSettingsPage):
    """Settings page for language configuration."""
    
    def __init__(self, settings_manager, i18n: I18nQtManager):
        """
        Initialize language settings page.
        
        Args:
            settings_manager: SettingsManager instance
            i18n: Internationalization manager
        """
        super().__init__(settings_manager, i18n)
        
        # Setup UI
        self.setup_ui()
        
        logger.debug("Language settings page initialized")
    
    def setup_ui(self):
        """Set up the language settings UI."""
        # Language section
        from PyQt6.QtGui import QFont
        font = QFont()
        font.setPointSize(12)
        font.setBold(True)
        
        self.language_title = QLabel(self.i18n.t('settings.language.title'))
        self.language_title.setFont(font)
        self.content_layout.addWidget(self.language_title)
        
        # Language selection
        language_layout = QHBoxLayout()
        self.language_label = QLabel(
            self.i18n.t('settings.language.select')
        )
        self.language_label.setMinimumWidth(200)
        self.language_combo = QComboBox()
        
        # Add language options
        self.language_combo.addItem(
            self.i18n.t('settings.language.chinese'),
            'zh_CN'
        )
        self.language_combo.addItem(
            self.i18n.t('settings.language.english'),
            'en_US'
        )
        self.language_combo.addItem(
            self.i18n.t('settings.language.french'),
            'fr_FR'
        )
        
        self.language_combo.currentIndexChanged.connect(
            self._on_language_changed
        )
        
        language_layout.addWidget(self.language_label)
        language_layout.addWidget(self.language_combo)
        language_layout.addStretch()
        self.content_layout.addLayout(language_layout)
        
        self.add_spacing(10)
        
        # Language info
        self.info_label = QLabel(
            self.i18n.t('settings.language.change_info')
        )
        self.info_label.setWordWrap(True)
        self.info_label.setStyleSheet("color: #666; font-style: italic;")
        self.content_layout.addWidget(self.info_label)
        
        # Add stretch at the end
        self.content_layout.addStretch()
    
    def _on_language_changed(self, index: int):
        """
        Handle language selection change.
        
        Args:
            index: Selected language index
        """
        language_code = self.language_combo.itemData(index)
        
        # Apply language change immediately
        self.i18n.change_language(language_code)
        
        self._emit_changed()
        
        logger.debug(f"Language changed to: {language_code}")
    
    def load_settings(self):
        """Load language settings into UI."""
        try:
            # Language
            language = self.settings_manager.get_setting('ui.language')
            if language:
                # Find index by language code
                for i in range(self.language_combo.count()):
                    if self.language_combo.itemData(i) == language:
                        self.language_combo.setCurrentIndex(i)
                        break
            
            logger.debug("Language settings loaded")
            
        except Exception as e:
            logger.error(f"Error loading language settings: {e}")
    
    def save_settings(self):
        """Save language settings from UI."""
        try:
            # Language
            language_code = self.language_combo.currentData()
            self.settings_manager.set_setting('ui.language', language_code)
            
            logger.debug("Language settings saved")
            
        except Exception as e:
            logger.error(f"Error saving language settings: {e}")
            raise
    
    def validate_settings(self) -> Tuple[bool, str]:
        """
        Validate language settings.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        # No validation needed
        return True, ""
    
    def update_translations(self):
        """Update UI text after language change."""
        # Update section title
        if hasattr(self, 'language_title'):
            self.language_title.setText(
                self.i18n.t('settings.language.title')
            )
        
        # Update labels
        if hasattr(self, 'language_label'):
            self.language_label.setText(
                self.i18n.t('settings.language.select')
            )
        if hasattr(self, 'info_label'):
            self.info_label.setText(
                self.i18n.t('settings.language.change_info')
            )
        
        # Update language combo items while preserving selection
        if hasattr(self, 'language_combo'):
            current_code = self.language_combo.currentData()
            
            self.language_combo.blockSignals(True)
            self.language_combo.clear()
            
            self.language_combo.addItem(
                self.i18n.t('settings.language.chinese'),
                'zh_CN'
            )
            self.language_combo.addItem(
                self.i18n.t('settings.language.english'),
                'en_US'
            )
            self.language_combo.addItem(
                self.i18n.t('settings.language.french'),
                'fr_FR'
            )
            
            # Restore selection
            for i in range(self.language_combo.count()):
                if self.language_combo.itemData(i) == current_code:
                    self.language_combo.setCurrentIndex(i)
                    break
            
            self.language_combo.blockSignals(False)
