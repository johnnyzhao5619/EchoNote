# SPDX-License-Identifier: Apache-2.0
"""Tests for workspace settings page behavior."""

from unittest.mock import patch

import pytest

from ui.settings.workspace_page import WorkspaceSettingsPage

pytestmark = pytest.mark.ui


class _FakeSettingsManager:
    def __init__(self):
        self._settings = {"workspace.storage_root": "/tmp/echonote-vault"}

    def get_workspace_preferences(self):
        return {"storage_root": self._settings["workspace.storage_root"]}

    def get_setting(self, key):
        return self._settings.get(key)

    def set_setting(self, key, value):
        self._settings[key] = value
        return True


def test_workspace_settings_page_loads_workspace_defaults(qapp, mock_i18n):
    settings_manager = _FakeSettingsManager()
    page = WorkspaceSettingsPage(settings_manager, mock_i18n)

    page.load_settings()

    assert page.storage_root_edit.text() == "/tmp/echonote-vault"


def test_workspace_settings_page_save_settings_persists_preferences(qapp, mock_i18n):
    settings_manager = _FakeSettingsManager()
    page = WorkspaceSettingsPage(settings_manager, mock_i18n)

    page.storage_root_edit.setText("/tmp/new-vault")
    page.save_settings()

    assert settings_manager.get_setting("workspace.storage_root") == "/tmp/new-vault"


def test_workspace_settings_page_browse_updates_storage_root(qapp, mock_i18n):
    settings_manager = _FakeSettingsManager()
    page = WorkspaceSettingsPage(settings_manager, mock_i18n)

    with patch(
        "ui.settings.workspace_page.QFileDialog.getExistingDirectory",
        return_value="/tmp/picked-vault",
    ):
        page._on_browse_clicked()

    assert page.storage_root_edit.text() == "/tmp/picked-vault"
