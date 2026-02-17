# SPDX-License-Identifier: Apache-2.0
"""Tests for explicit-save behavior in settings pages."""

from unittest.mock import Mock

from ui.settings.appearance_page import AppearanceSettingsPage
from ui.settings.language_page import LanguageSettingsPage


class _FakeSettingsManager:
    def __init__(self):
        self._settings = {
            "ui.theme": "light",
            "ui.language": "en_US",
        }

    def get_setting(self, key):
        return self._settings.get(key)

    def set_setting(self, key, value):
        self._settings[key] = value
        return True


def test_appearance_page_does_not_apply_theme_directly(qapp, mock_i18n):
    settings_manager = _FakeSettingsManager()
    main_window = Mock()
    page = AppearanceSettingsPage(
        settings_manager=settings_manager, i18n=mock_i18n, managers={"main_window": main_window}
    )

    page.theme_combo.setCurrentIndex(1)  # dark
    main_window.apply_theme.assert_not_called()

    page.save_settings()
    main_window.apply_theme.assert_not_called()


def test_language_page_does_not_change_language_directly(qapp, mock_i18n):
    settings_manager = _FakeSettingsManager()
    mock_i18n.change_language = Mock()
    page = LanguageSettingsPage(settings_manager=settings_manager, i18n=mock_i18n)

    index = page.language_combo.findData("zh_CN")
    assert index >= 0
    page.language_combo.setCurrentIndex(index)
    mock_i18n.change_language.assert_not_called()

    page.save_settings()
    mock_i18n.change_language.assert_not_called()
