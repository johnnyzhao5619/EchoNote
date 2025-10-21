import pytest

PyQt6 = pytest.importorskip("PyQt6")
from PyQt6.QtWidgets import QApplication
from PyQt6.QtMultimedia import QMediaPlayer

from ui.timeline.audio_player import AudioPlayer, AudioPlayerDialog
from utils.i18n import I18nQtManager


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


def test_audio_player_updates_translations_on_language_change(tmp_path, qapp):
    audio_path = tmp_path / "sample.wav"
    audio_path.touch()

    i18n = I18nQtManager(default_language="zh_CN")
    player = AudioPlayer(str(audio_path), i18n)

    try:
        qapp.processEvents()

        assert player.play_button.text() == i18n.t(
            "timeline.audio_player.play_button_label"
        )
        assert player.play_button.toolTip() == i18n.t(
            "timeline.audio_player.play_tooltip"
        )
        assert player.volume_slider.toolTip() == i18n.t(
            "timeline.audio_player.volume_tooltip"
        )
        assert player.progress_slider.toolTip() == i18n.t(
            "timeline.audio_player.progress_tooltip"
        )
        assert player.volume_label.text() == i18n.t(
            "timeline.audio_player.volume_icon"
        )
        assert player.current_time_label.text() == i18n.t(
            "timeline.audio_player.initial_time"
        )
        assert player.total_time_label.text() == i18n.t(
            "timeline.audio_player.initial_time"
        )

        player._on_state_changed(QMediaPlayer.PlaybackState.PlayingState)
        i18n.change_language("en_US")
        qapp.processEvents()

        assert player.play_button.text() == i18n.t(
            "timeline.audio_player.pause_button_label"
        )
        assert player.play_button.toolTip() == i18n.t(
            "timeline.audio_player.pause_tooltip"
        )
        assert player.volume_slider.toolTip() == i18n.t(
            "timeline.audio_player.volume_tooltip"
        )
        assert player.progress_slider.toolTip() == i18n.t(
            "timeline.audio_player.progress_tooltip"
        )
        assert player.volume_label.text() == i18n.t(
            "timeline.audio_player.volume_icon"
        )
        assert player.current_time_label.text() == i18n.t(
            "timeline.audio_player.initial_time"
        )
        assert player.total_time_label.text() == i18n.t(
            "timeline.audio_player.initial_time"
        )
    finally:
        player.cleanup()
        player.deleteLater()
        qapp.processEvents()


def test_audio_player_dialog_retranslates_controls(tmp_path, qapp):
    audio_path = tmp_path / "dialog.wav"
    audio_path.touch()

    i18n = I18nQtManager(default_language="en_US")
    dialog = AudioPlayerDialog(str(audio_path), i18n)

    try:
        qapp.processEvents()

        assert dialog.windowTitle() == i18n.t("timeline.audio_player_title")
        assert dialog.close_button.text() == i18n.t("common.close")
        assert dialog.player.play_button.toolTip() == i18n.t(
            "timeline.audio_player.play_tooltip"
        )

        dialog.player._on_state_changed(QMediaPlayer.PlaybackState.PlayingState)
        i18n.change_language("zh_CN")
        qapp.processEvents()

        assert dialog.windowTitle() == i18n.t("timeline.audio_player_title")
        assert dialog.close_button.text() == i18n.t("common.close")
        assert dialog.player.play_button.toolTip() == i18n.t(
            "timeline.audio_player.pause_tooltip"
        )
        assert dialog.player.play_button.text() == i18n.t(
            "timeline.audio_player.pause_button_label"
        )
    finally:
        dialog.close()
        dialog.deleteLater()
        qapp.processEvents()
