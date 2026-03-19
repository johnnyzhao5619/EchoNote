# SPDX-License-Identifier: Apache-2.0
"""
Tests for model management page semantic style hooks.
"""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PySide6.QtWidgets import QPushButton

from core.models.registry import ModelInfo
from core.models.text_ai_registry import TextAIModelInfo
from ui.settings.model_management_page import ModelManagementPage

pytestmark = pytest.mark.ui


def _make_signal_stub() -> Mock:
    signal = Mock()
    signal.connect = Mock()
    return signal


def _make_model(
    name: str,
    *,
    downloaded: bool,
    local_path: str | None = None,
) -> ModelInfo:
    return ModelInfo(
        name=name,
        full_name=f"Model {name}",
        description="desc",
        size_mb=100,
        speed="fast",
        accuracy="medium",
        languages=("multi",),
        repo_id=f"repo/{name}",
        is_downloaded=downloaded,
        local_path=local_path,
    )


@pytest.fixture
def model_manager():
    downloaded = _make_model("tiny", downloaded=True, local_path="/tmp/models/tiny")
    available = _make_model("base", downloaded=False)
    text_ai_downloaded = TextAIModelInfo(
        model_id="extractive-default",
        display_name="Extractive Summary",
        runtime="extractive",
        provider="builtin",
        description="fallback",
        family="summary",
        size_mb=0,
        local_path="builtin://extractive-default",
        is_downloaded=True,
    )
    text_ai_available = TextAIModelInfo(
        model_id="flan-t5-small-int8",
        display_name="Flan T5 Small INT8",
        runtime="onnx",
        provider="onnxruntime",
        description="summary",
        family="summary",
        size_mb=310,
        is_downloaded=False,
    )
    text_ai_meeting = TextAIModelInfo(
        model_id="gemma-3-1b-it-gguf",
        display_name="Gemma 3 1B Instruct",
        runtime="gguf",
        provider="llama_cpp",
        description="meeting",
        family="meeting",
        size_mb=1200,
        is_downloaded=False,
    )
    mapping = {downloaded.name: downloaded, available.name: available}
    text_ai_mapping = {
        text_ai_downloaded.model_id: text_ai_downloaded,
        text_ai_available.model_id: text_ai_available,
        text_ai_meeting.model_id: text_ai_meeting,
    }

    manager = Mock()
    manager.models_updated = _make_signal_stub()
    manager.model_validation_failed = _make_signal_stub()
    manager.translation_models_updated = _make_signal_stub()
    manager.text_ai_models_updated = _make_signal_stub()
    manager.downloader = SimpleNamespace(
        download_progress=_make_signal_stub(),
        download_completed=_make_signal_stub(),
        download_cancelled=_make_signal_stub(),
        download_failed=_make_signal_stub(),
        is_downloading=Mock(return_value=False),
    )
    manager.translation_downloader = SimpleNamespace(
        download_progress=_make_signal_stub(),
        download_completed=_make_signal_stub(),
        download_cancelled=_make_signal_stub(),
        download_failed=_make_signal_stub(),
        is_downloading=Mock(return_value=False),
    )
    manager.text_ai_downloader = SimpleNamespace(
        download_progress=_make_signal_stub(),
        download_completed=_make_signal_stub(),
        download_cancelled=_make_signal_stub(),
        download_failed=_make_signal_stub(),
        is_downloading=Mock(return_value=False),
    )
    manager.get_all_models = Mock(return_value=[downloaded, available])
    manager.get_all_translation_models = Mock(return_value=[])
    manager.get_all_text_ai_models = Mock(
        return_value=[text_ai_downloaded, text_ai_available, text_ai_meeting]
    )
    manager.get_model = Mock(side_effect=lambda name: mapping.get(name))
    manager.get_text_ai_model = Mock(side_effect=lambda model_id: text_ai_mapping.get(model_id))
    manager.recommend_model = Mock(return_value="base")
    manager.is_model_in_use = Mock(return_value=False)
    return manager


def test_model_management_exposes_tabs_and_grouped_text_ai_models(
    qapp, mock_i18n, mock_settings_manager, model_manager
):
    page = ModelManagementPage(mock_settings_manager, mock_i18n, model_manager)

    assert page.tabs.count() == 3
    assert page.tabs.property("role") == "model-management-tabs"
    assert page.tabs.tabText(0) == "settings.model_management.speech_tab"
    assert page.tabs.tabText(1) == "settings.model_management.translation_tab"
    assert page.tabs.tabText(2) == "settings.model_management.text_ai_tab"
    assert page.text_ai_summary_layout.itemAt(0).widget() is page.text_ai_model_cards["extractive-default"]
    assert page.text_ai_summary_layout.itemAt(1).widget() is page.text_ai_model_cards["flan-t5-small-int8"]
    assert page.text_ai_meeting_layout.itemAt(0).widget() is page.text_ai_model_cards["gemma-3-1b-it-gguf"]


def test_model_management_focus_section_switches_tabs(
    qapp, mock_i18n, mock_settings_manager, model_manager
):
    page = ModelManagementPage(mock_settings_manager, mock_i18n, model_manager)

    page.focus_section("translation")
    assert page.tabs.currentIndex() == 1

    page.focus_section("text_ai")
    assert page.tabs.currentIndex() == 2


def test_model_card_action_buttons_have_semantic_roles(
    qapp, mock_i18n, mock_settings_manager, model_manager
):
    page = ModelManagementPage(mock_settings_manager, mock_i18n, model_manager)

    available_card = page.model_cards["base"]
    download_btn = available_card.findChild(QPushButton, "download_btn_base")
    assert download_btn is not None
    assert download_btn.property("role") == "model-download"

    downloaded_card = page.model_cards["tiny"]
    delete_buttons = [
        button
        for button in downloaded_card.findChildren(QPushButton)
        if button.property("role") == "model-delete"
    ]
    assert len(delete_buttons) == 1

    text_ai_card = page.text_ai_model_cards["flan-t5-small-int8"]
    text_ai_download = text_ai_card.findChild(QPushButton, "download_btn_flan-t5-small-int8")
    assert text_ai_download is not None
    assert text_ai_download.property("role") == "model-download"


def test_model_management_related_settings_shortcuts_have_semantic_roles(
    qapp, mock_i18n, mock_settings_manager, model_manager
):
    page = ModelManagementPage(mock_settings_manager, mock_i18n, model_manager)

    assert page.go_to_transcription_button.property("role") == "settings-inline-action"
    assert page.go_to_translation_button.property("role") == "settings-inline-action"
    assert page.go_to_workspace_ai_button.property("role") == "settings-inline-action"


def test_model_management_download_error_suggestions_classify_auth_failures(
    qapp, mock_i18n, mock_settings_manager, model_manager
):
    page = ModelManagementPage(mock_settings_manager, mock_i18n, model_manager)

    suggestion = page._get_error_suggestions(
        "401 Client Error: Unauthorized for url: https://huggingface.co/api/models/private/repo"
    )

    assert suggestion == "settings.model_management.suggestion_auth"
