# SPDX-License-Identifier: Apache-2.0
"""Tests for workspace AI settings page behavior."""

from unittest.mock import Mock

import pytest

from core.models.text_ai_registry import TextAIModelInfo
from ui.settings.workspace_ai_page import WorkspaceAISettingsPage

pytestmark = pytest.mark.ui


class _FakeSettingsManager:
    def __init__(self):
        self._settings = {
            "workspace_ai.default_summary_strategy": "extractive",
            "workspace_ai.default_summary_model": "flan-t5-small-int8",
            "workspace_ai.default_meeting_model": "extractive-default",
            "workspace_ai.default_meeting_template": "standard",
            "workspace_ai.gguf_runtime_command": [],
        }

    def get_workspace_ai_preferences(self):
        return {
            "default_summary_strategy": self._settings["workspace_ai.default_summary_strategy"],
            "default_summary_model": self._settings["workspace_ai.default_summary_model"],
            "default_meeting_model": self._settings["workspace_ai.default_meeting_model"],
            "default_meeting_template": self._settings["workspace_ai.default_meeting_template"],
            "gguf_runtime_command": list(self._settings["workspace_ai.gguf_runtime_command"]),
        }

    def get_setting(self, key):
        return self._settings.get(key)

    def set_setting(self, key, value):
        self._settings[key] = value
        return True


class _FakeModelManager:
    def __init__(self):
        self._models = [
            TextAIModelInfo(
                model_id="extractive-default",
                display_name="Extractive Summary",
                runtime="extractive",
                provider="builtin",
                description="fallback",
                family="summary",
                size_mb=0,
                local_path="builtin://extractive-default",
                is_downloaded=True,
            ),
            TextAIModelInfo(
                model_id="flan-t5-small-int8",
                display_name="Flan T5 Small INT8",
                runtime="onnx",
                provider="onnxruntime",
                description="summary",
                family="summary",
                size_mb=310,
                is_downloaded=True,
            ),
            TextAIModelInfo(
                model_id="gemma-3-1b-it-gguf",
                display_name="Gemma 3 1B Instruct",
                runtime="gguf",
                provider="llama_cpp",
                description="meeting",
                family="meeting",
                size_mb=1200,
                is_downloaded=True,
            ),
        ]

    def get_all_text_ai_models(self):
        return list(self._models)

    def get_text_ai_model(self, model_id: str):
        return next((model for model in self._models if model.model_id == model_id), None)


def test_workspace_ai_page_loads_workspace_defaults(qapp, mock_i18n):
    settings_manager = _FakeSettingsManager()
    page = WorkspaceAISettingsPage(
        settings_manager,
        mock_i18n,
        managers={"model_manager": _FakeModelManager()},
    )

    page.load_settings()

    assert page.summary_provider_selector.current_provider() == "extractive"
    assert page.meeting_provider_selector.current_provider() == "extractive"
    assert page.summary_model_combo.currentData() == "flan-t5-small-int8"
    assert page.meeting_model_combo.currentData() == "extractive-default"
    assert page.meeting_template_combo.currentData() == "standard"
    assert page.runtime_command_edit.text() == ""
    assert not page.summary_model_row.isVisible()
    assert not page.meeting_model_row.isVisible()


def test_workspace_ai_page_save_settings_persists_preferences(qapp, mock_i18n):
    settings_manager = _FakeSettingsManager()
    page = WorkspaceAISettingsPage(
        settings_manager,
        mock_i18n,
        managers={"model_manager": _FakeModelManager()},
    )

    page.summary_provider_selector.set_current_provider("onnx")
    page.meeting_provider_selector.set_current_provider("gguf")
    page.summary_model_combo.setCurrentIndex(
        page.summary_model_combo.findData("flan-t5-small-int8")
    )
    page.meeting_model_combo.setCurrentIndex(page.meeting_model_combo.findData("gemma-3-1b-it-gguf"))
    page.meeting_template_combo.setCurrentIndex(page.meeting_template_combo.findData("action-first"))
    page.runtime_command_edit.setText("llama-cli --ctx-size 4096")

    page.save_settings()

    assert settings_manager.get_setting("workspace_ai.default_summary_strategy") == "abstractive"
    assert settings_manager.get_setting("workspace_ai.default_summary_model") == "flan-t5-small-int8"
    assert settings_manager.get_setting("workspace_ai.default_meeting_model") == "gemma-3-1b-it-gguf"
    assert settings_manager.get_setting("workspace_ai.default_meeting_template") == "action-first"
    assert settings_manager.get_setting("workspace_ai.gguf_runtime_command") == [
        "llama-cli",
        "--ctx-size",
        "4096",
    ]


def test_workspace_ai_page_download_shortcut_uses_text_ai_tab(qapp, mock_i18n):
    settings_manager = _FakeSettingsManager()
    page = WorkspaceAISettingsPage(settings_manager, mock_i18n)

    model_page = Mock()
    model_page.focus_section = Mock()
    page._open_settings_page = Mock(return_value=model_page)

    page._on_go_to_model_management()

    page._open_settings_page.assert_called_once_with("model_management")
    model_page.focus_section.assert_called_once_with("text_ai")
