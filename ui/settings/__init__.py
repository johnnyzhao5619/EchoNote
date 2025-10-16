"""Settings UI components."""

from ui.settings.widget import SettingsWidget
from ui.settings.base_page import BaseSettingsPage
from ui.settings.transcription_page import TranscriptionSettingsPage
from ui.settings.realtime_page import RealtimeSettingsPage
from ui.settings.calendar_page import CalendarSettingsPage
from ui.settings.timeline_page import TimelineSettingsPage
from ui.settings.appearance_page import AppearanceSettingsPage
from ui.settings.language_page import LanguageSettingsPage

__all__ = [
    'SettingsWidget',
    'BaseSettingsPage',
    'TranscriptionSettingsPage',
    'RealtimeSettingsPage',
    'CalendarSettingsPage',
    'TimelineSettingsPage',
    'AppearanceSettingsPage',
    'LanguageSettingsPage',
]
