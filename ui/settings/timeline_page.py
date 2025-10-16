"""
Timeline settings page.

Provides UI for configuring timeline view and auto-task settings.
"""

import logging
from typing import Tuple

from PyQt6.QtWidgets import (
    QLabel, QComboBox, QSpinBox, QCheckBox, QHBoxLayout
)
from PyQt6.QtCore import Qt

from ui.settings.base_page import BaseSettingsPage
from utils.i18n import I18nQtManager


logger = logging.getLogger('echonote.ui.settings.timeline')


class TimelineSettingsPage(BaseSettingsPage):
    """Settings page for timeline configuration."""
    
    def __init__(self, settings_manager, i18n: I18nQtManager):
        """
        Initialize timeline settings page.
        
        Args:
            settings_manager: SettingsManager instance
            i18n: Internationalization manager
        """
        super().__init__(settings_manager, i18n)
        
        # Setup UI
        self.setup_ui()
        
        logger.debug("Timeline settings page initialized")
    
    def setup_ui(self):
        """Set up the timeline settings UI."""
        # View range section
        from PyQt6.QtGui import QFont
        font = QFont()
        font.setPointSize(12)
        font.setBold(True)
        
        self.view_range_title = QLabel(self.i18n.t('settings.timeline.view_range'))
        self.view_range_title.setFont(font)
        self.content_layout.addWidget(self.view_range_title)
        
        # Past days
        past_layout = QHBoxLayout()
        self.past_label = QLabel(self.i18n.t('settings.timeline.past_days'))
        self.past_label.setMinimumWidth(200)
        self.past_days_spin = QSpinBox()
        self.past_days_spin.setMinimum(1)
        self.past_days_spin.setMaximum(365)
        self.past_days_spin.setValue(30)
        self.past_days_spin.setSuffix(" " + self.i18n.t('settings.timeline.days'))
        self.past_days_spin.valueChanged.connect(self._emit_changed)
        past_layout.addWidget(self.past_label)
        past_layout.addWidget(self.past_days_spin)
        past_layout.addStretch()
        self.content_layout.addLayout(past_layout)
        
        # Future days
        future_layout = QHBoxLayout()
        self.future_label = QLabel(self.i18n.t('settings.timeline.future_days'))
        self.future_label.setMinimumWidth(200)
        self.future_days_spin = QSpinBox()
        self.future_days_spin.setMinimum(1)
        self.future_days_spin.setMaximum(365)
        self.future_days_spin.setValue(30)
        self.future_days_spin.setSuffix(" " + self.i18n.t('settings.timeline.days'))
        self.future_days_spin.valueChanged.connect(self._emit_changed)
        future_layout.addWidget(self.future_label)
        future_layout.addWidget(self.future_days_spin)
        future_layout.addStretch()
        self.content_layout.addLayout(future_layout)
        
        self.add_spacing(20)
        
        # Notification settings section
        self.notifications_title = QLabel(self.i18n.t('settings.timeline.notifications'))
        self.notifications_title.setFont(font)
        self.content_layout.addWidget(self.notifications_title)
        
        # Reminder time
        reminder_layout = QHBoxLayout()
        self.reminder_label = QLabel(
            self.i18n.t('settings.timeline.reminder_time')
        )
        self.reminder_label.setMinimumWidth(200)
        self.reminder_combo = QComboBox()
        self.reminder_combo.addItems(['5', '10', '15', '30'])
        self.reminder_combo.currentTextChanged.connect(self._emit_changed)
        self.reminder_suffix = QLabel(self.i18n.t('settings.timeline.minutes'))
        reminder_layout.addWidget(self.reminder_label)
        reminder_layout.addWidget(self.reminder_combo)
        reminder_layout.addWidget(self.reminder_suffix)
        reminder_layout.addStretch()
        self.content_layout.addLayout(reminder_layout)
        
        self.add_spacing(20)
        
        # Auto-start settings section
        self.auto_start_title = QLabel(self.i18n.t('settings.timeline.auto_start'))
        self.auto_start_title.setFont(font)
        self.content_layout.addWidget(self.auto_start_title)
        
        # Enable auto-start
        self.auto_start_check = QCheckBox(
            self.i18n.t('settings.timeline.enable_auto_start')
        )
        self.auto_start_check.stateChanged.connect(self._emit_changed)
        self.content_layout.addWidget(self.auto_start_check)
        
        # Description
        self.auto_start_desc = QLabel(
            self.i18n.t('settings.timeline.auto_start_description')
        )
        self.auto_start_desc.setWordWrap(True)
        self.auto_start_desc.setStyleSheet("color: #666; font-style: italic;")
        self.content_layout.addWidget(self.auto_start_desc)
        
        # Add stretch at the end
        self.content_layout.addStretch()
    
    def load_settings(self):
        """Load timeline settings into UI."""
        try:
            # View range
            past_days = self.settings_manager.get_setting('timeline.past_days')
            if past_days:
                self.past_days_spin.setValue(past_days)
            
            future_days = self.settings_manager.get_setting('timeline.future_days')
            if future_days:
                self.future_days_spin.setValue(future_days)
            
            # Reminder time
            reminder_minutes = self.settings_manager.get_setting(
                'timeline.reminder_minutes'
            )
            if reminder_minutes:
                index = self.reminder_combo.findText(str(reminder_minutes))
                if index >= 0:
                    self.reminder_combo.setCurrentIndex(index)
            
            # Auto-start (if this setting exists)
            auto_start = self.settings_manager.get_setting(
                'timeline.auto_start_enabled'
            )
            if auto_start is not None:
                self.auto_start_check.setChecked(auto_start)
            
            logger.debug("Timeline settings loaded")
            
        except Exception as e:
            logger.error(f"Error loading timeline settings: {e}")
    
    def save_settings(self):
        """Save timeline settings from UI."""
        try:
            # View range
            self.settings_manager.set_setting(
                'timeline.past_days',
                self.past_days_spin.value()
            )
            
            self.settings_manager.set_setting(
                'timeline.future_days',
                self.future_days_spin.value()
            )
            
            # Reminder time
            reminder_minutes = int(self.reminder_combo.currentText())
            self.settings_manager.set_setting(
                'timeline.reminder_minutes',
                reminder_minutes
            )
            
            # Auto-start
            self.settings_manager.set_setting(
                'timeline.auto_start_enabled',
                self.auto_start_check.isChecked()
            )
            
            logger.debug("Timeline settings saved")
            
        except Exception as e:
            logger.error(f"Error saving timeline settings: {e}")
            raise
    
    def validate_settings(self) -> Tuple[bool, str]:
        """
        Validate timeline settings.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        # All settings have valid ranges enforced by spinboxes/combos
        return True, ""
    
    def update_translations(self):
        """Update UI text after language change."""
        # Update section titles
        if hasattr(self, 'view_range_title'):
            self.view_range_title.setText(
                self.i18n.t('settings.timeline.view_range')
            )
        if hasattr(self, 'notifications_title'):
            self.notifications_title.setText(
                self.i18n.t('settings.timeline.notifications')
            )
        if hasattr(self, 'auto_start_title'):
            self.auto_start_title.setText(
                self.i18n.t('settings.timeline.auto_start')
            )
        
        # Update labels
        if hasattr(self, 'past_label'):
            self.past_label.setText(
                self.i18n.t('settings.timeline.past_days')
            )
        if hasattr(self, 'future_label'):
            self.future_label.setText(
                self.i18n.t('settings.timeline.future_days')
            )
        if hasattr(self, 'reminder_label'):
            self.reminder_label.setText(
                self.i18n.t('settings.timeline.reminder_time')
            )
        if hasattr(self, 'reminder_suffix'):
            self.reminder_suffix.setText(
                self.i18n.t('settings.timeline.minutes')
            )
        
        # Update checkbox
        if hasattr(self, 'auto_start_check'):
            self.auto_start_check.setText(
                self.i18n.t('settings.timeline.enable_auto_start')
            )
        
        # Update description
        if hasattr(self, 'auto_start_desc'):
            self.auto_start_desc.setText(
                self.i18n.t('settings.timeline.auto_start_description')
            )
        
        # Update spinbox suffixes
        if hasattr(self, 'past_days_spin'):
            self.past_days_spin.setSuffix(
                " " + self.i18n.t('settings.timeline.days')
            )
        if hasattr(self, 'future_days_spin'):
            self.future_days_spin.setSuffix(
                " " + self.i18n.t('settings.timeline.days')
            )
