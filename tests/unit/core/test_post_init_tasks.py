# SPDX-License-Identifier: Apache-2.0
"""Unit tests for post-initialization task helpers."""

from unittest.mock import Mock, patch

from config.constants import ENGINE_FASTER_WHISPER
from utils.post_init_tasks import check_loopback_availability, check_model_availability


def _build_config(default_engine: str):
    config = Mock()

    def _get(key, default=None):
        if key == "transcription.default_engine":
            return default_engine
        return default

    config.get.side_effect = _get
    return config


def test_check_model_availability_skips_when_download_active():
    config = _build_config(ENGINE_FASTER_WHISPER)
    model_manager = Mock()
    model_manager.get_downloaded_models.return_value = []
    model_manager.has_active_downloads.return_value = True

    with patch(
        "utils.first_run_setup.FirstRunSetup.show_model_recommendation_dialog"
    ) as show_dialog:
        check_model_availability(config, model_manager, Mock(), Mock())

    show_dialog.assert_not_called()


def test_check_model_availability_shows_dialog_when_no_model_and_no_download():
    config = _build_config(ENGINE_FASTER_WHISPER)
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


def test_check_loopback_availability_skips_when_not_first_run():
    config = Mock()

    check_loopback_availability(
        config,
        Mock(),
        Mock(),
        audio_capture=Mock(),
        is_first_run=False,
    )

    config.get.assert_not_called()


def test_check_loopback_availability_shows_dialog_on_first_run_when_missing():
    config = Mock()

    def _get(key, default=None):
        if key == "ui.show_loopback_install_dialog":
            return True
        return default

    config.get.side_effect = _get
    checker = Mock()
    checker.check_and_log.return_value = False
    checker.get_installation_instructions.return_value = ("title", "instructions")

    dialog = Mock()
    dialog.should_show_again.return_value = False

    with (
        patch("utils.loopback_checker.get_loopback_checker", return_value=checker),
        patch("ui.dialogs.loopback_install_dialog.LoopbackInstallDialog", return_value=dialog),
    ):
        check_loopback_availability(
            config,
            Mock(),
            Mock(),
            audio_capture=Mock(),
            is_first_run=True,
        )

    checker.check_and_log.assert_called_once()
    dialog.exec.assert_called_once()
    config.set.assert_called_once_with("ui.show_loopback_install_dialog", False)
    config.save.assert_called_once()


def test_check_loopback_availability_skips_dialog_when_loopback_present():
    config = Mock()

    def _get(key, default=None):
        if key == "ui.show_loopback_install_dialog":
            return True
        return default

    config.get.side_effect = _get
    checker = Mock()
    checker.check_and_log.return_value = True

    with (
        patch("utils.loopback_checker.get_loopback_checker", return_value=checker),
        patch("ui.dialogs.loopback_install_dialog.LoopbackInstallDialog") as dialog_cls,
    ):
        check_loopback_availability(
            config,
            Mock(),
            Mock(),
            audio_capture=Mock(),
            is_first_run=True,
        )

    dialog_cls.assert_not_called()
