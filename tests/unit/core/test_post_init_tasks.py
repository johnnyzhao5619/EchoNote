# SPDX-License-Identifier: Apache-2.0
"""Unit tests for post-initialization task helpers."""

from unittest.mock import Mock, patch

from utils.post_init_tasks import check_model_availability


def _build_config(default_engine: str):
    config = Mock()

    def _get(key, default=None):
        if key == "transcription.default_engine":
            return default_engine
        return default

    config.get.side_effect = _get
    return config


def test_check_model_availability_skips_when_download_active():
    config = _build_config("faster-whisper")
    model_manager = Mock()
    model_manager.get_downloaded_models.return_value = []
    model_manager.has_active_downloads.return_value = True

    with patch("utils.first_run_setup.FirstRunSetup.show_model_recommendation_dialog") as show_dialog:
        check_model_availability(config, model_manager, Mock(), Mock())

    show_dialog.assert_not_called()


def test_check_model_availability_shows_dialog_when_no_model_and_no_download():
    config = _build_config("faster-whisper")
    model_manager = Mock()
    model_manager.get_downloaded_models.return_value = []
    model_manager.has_active_downloads.return_value = False

    with (
        patch(
            "utils.first_run_setup.FirstRunSetup.show_model_recommendation_dialog",
            return_value=True,
        ) as show_dialog,
    ):
        check_model_availability(config, model_manager, Mock(), Mock())

    show_dialog.assert_called_once()
