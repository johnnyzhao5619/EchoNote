# SPDX-License-Identifier: Apache-2.0
"""Tests for translation settings page behavior."""

from unittest.mock import Mock

import pytest

from ui.settings.translation_page import TranslationSettingsPage

pytestmark = pytest.mark.ui


class _FakeSettingsManager:
    def __init__(self):
        self._settings = {
            "translation.translation_engine": "none",
            "translation.translation_source_lang": "auto",
            "translation.translation_target_lang": "en",
        }

    def get_setting(self, key):
        return self._settings.get(key)

    def set_setting(self, key, value):
        self._settings[key] = value
        return True


class _FakeModelInfo:
    def __init__(self, model_id: str, is_downloaded: bool):
        self.model_id = model_id
        self.is_downloaded = is_downloaded


class _FakeModelManager:
    def get_best_translation_model(self, _source, _target, *, auto_detect=False):
        if auto_detect:
            return _FakeModelInfo("opus-mt-en-zh", True)
        return _FakeModelInfo("opus-mt-zh-en", False)


def test_load_settings_populates_translation_defaults(qapp, mock_i18n):
    settings_manager = _FakeSettingsManager()
    page = TranslationSettingsPage(
        settings_manager,
        mock_i18n,
        managers={"model_manager": _FakeModelManager()},
    )

    page.load_settings()

    assert page.engine_combo.currentData() == "none"
    assert page.source_combo.currentData() == "auto"
    assert page.target_combo.currentData() == "en"


def test_save_settings_persists_translation_defaults(qapp, mock_i18n):
    settings_manager = _FakeSettingsManager()
    page = TranslationSettingsPage(
        settings_manager,
        mock_i18n,
        managers={"model_manager": _FakeModelManager()},
    )

    engine_index = page.engine_combo.findData("google")
    target_index = page.target_combo.findData("fr")
    assert engine_index >= 0
    assert target_index >= 0

    page.engine_combo.setCurrentIndex(engine_index)
    page.target_combo.setCurrentIndex(target_index)
    page.save_settings()

    assert settings_manager.get_setting("translation.translation_engine") == "google"
    assert settings_manager.get_setting("translation.translation_source_lang") == "auto"
    assert settings_manager.get_setting("translation.translation_target_lang") == "fr"


def test_translation_page_download_shortcut_uses_model_management_tab(qapp, mock_i18n):
    settings_manager = _FakeSettingsManager()
    page = TranslationSettingsPage(settings_manager, mock_i18n)
    model_page = Mock()
    model_page.tabs = Mock()
    page._open_settings_page = Mock(return_value=model_page)

    page._on_go_to_model_management()

    page._open_settings_page.assert_called_once_with("model_management")
    model_page.tabs.setCurrentIndex.assert_called_once_with(1)


def test_translation_page_download_button_has_semantic_role(qapp, mock_i18n):
    settings_manager = _FakeSettingsManager()
    page = TranslationSettingsPage(settings_manager, mock_i18n)

    assert page.download_button.property("role") == "settings-inline-action"
