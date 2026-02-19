# SPDX-License-Identifier: Apache-2.0
"""
Tests for model management page semantic style hooks.
"""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PySide6.QtWidgets import QLabel, QPushButton

from core.models.registry import ModelInfo
from ui.settings.model_management_page import ModelConfigDialog, ModelManagementPage


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
    mapping = {downloaded.name: downloaded, available.name: available}

    manager = Mock()
    manager.models_updated = _make_signal_stub()
    manager.model_validation_failed = _make_signal_stub()
    manager.downloader = SimpleNamespace(
        download_progress=_make_signal_stub(),
        download_completed=_make_signal_stub(),
        download_cancelled=_make_signal_stub(),
        download_failed=_make_signal_stub(),
    )
    manager.get_all_models = Mock(return_value=[downloaded, available])
    manager.get_model = Mock(side_effect=lambda name: mapping.get(name))
    manager.recommend_model = Mock(return_value="base")
    manager.is_model_in_use = Mock(return_value=False)
    return manager


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


def test_model_config_dialog_field_labels_have_semantic_role(
    qapp, mock_i18n, mock_settings_manager
):
    model = _make_model("base", downloaded=False)
    mock_settings_manager.get_setting = Mock(return_value=None)
    mock_settings_manager.set_setting = Mock(return_value=True)
    mock_settings_manager.config_manager.save = Mock()

    dialog = ModelConfigDialog(model, mock_settings_manager, mock_i18n)
    field_labels = [
        label
        for label in dialog.findChildren(QLabel)
        if label.property("role") == "model-config-field-label"
    ]

    assert len(field_labels) == 4
