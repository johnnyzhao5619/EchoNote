# SPDX-License-Identifier: Apache-2.0
"""UI tests for timeline audio player transcript sync behavior."""

import json
from unittest.mock import Mock

import pytest
from PySide6.QtWidgets import QDialog, QSizePolicy, QVBoxLayout

from ui.constants import (
    AUDIO_PLAYER_DIALOG_DEFAULT_HEIGHT,
    AUDIO_PLAYER_DIALOG_EXPANDED_MIN_HEIGHT,
    AUDIO_PLAYER_CONTROL_BAR_MAX_HEIGHT,
    AUDIO_PLAYER_HEADER_MAX_HEIGHT,
    AUDIO_PLAYER_TRANSCRIPT_MIN_HEIGHT,
)
from ui.common.audio_player import AudioPlayer

pytestmark = pytest.mark.ui


def test_audio_player_sync_highlight_does_not_raise_with_qtextedit(qapp, mock_i18n):
    player = AudioPlayer(
        "/tmp/nonexistent.mp3",
        mock_i18n,
        auto_load=False,
    )
    player.transcript_text.setPlainText("[00:00 - 00:01] hello")
    player._segment_timeline = [(0, 1000)]
    player._segment_line_map = {0: 0}

    player._sync_transcript_with_playback(500)

    assert player._active_segment_index == 0
    player.cleanup()


def test_audio_player_mode_buttons_use_dedicated_role(qapp, mock_i18n):
    player = AudioPlayer(
        "/tmp/nonexistent.mp3",
        mock_i18n,
        auto_load=False,
    )

    assert player.mode_caption_label.property("role") == "audio-player-mode-caption"
    assert player._mode_buttons["transcript"].property("role") == "audio-player-mode-action"
    assert player._mode_buttons["translation"].property("role") == "audio-player-mode-action"
    assert player._mode_buttons["compare"].property("role") == "audio-player-mode-action"
    assert player.transcript_area.property("role") == "audio-player-transcript-panel"
    player.cleanup()


def test_audio_player_transcript_toggle_tooltip_updates_with_visibility(qapp, mock_i18n):
    player = AudioPlayer(
        "/tmp/nonexistent.mp3",
        mock_i18n,
        auto_load=False,
    )

    assert player.show_transcript_button.toolTip() == "timeline.audio_player.show_text_panel"
    player._toggle_transcript_visibility()
    assert player.show_transcript_button.toolTip() == "timeline.audio_player.hide_text_panel"
    assert player.top_fill.isHidden()
    assert player.bottom_fill.isHidden()
    player.cleanup()


def test_audio_player_seek_relative_clamps_and_updates(qapp, mock_i18n):
    player = AudioPlayer(
        "/tmp/nonexistent.mp3",
        mock_i18n,
        auto_load=False,
    )
    player._set_controls_enabled(True)
    player.progress_slider.setRange(0, 30_000)
    player.progress_slider.setValue(5_000)
    player.player.duration = Mock(return_value=30_000)
    player.player.position = Mock(return_value=5_000)
    player.player.setPosition = Mock()

    player._seek_relative(10_000)
    player.player.setPosition.assert_called_with(15_000)

    player.player.position = Mock(return_value=29_000)
    player._seek_relative(10_000)
    player.player.setPosition.assert_called_with(30_000)

    player.player.position = Mock(return_value=2_000)
    player._seek_relative(-10_000)
    player.player.setPosition.assert_called_with(0)
    player.cleanup()


def test_audio_player_update_translations_sets_seek_tooltips(qapp, mock_i18n):
    player = AudioPlayer(
        "/tmp/nonexistent.mp3",
        mock_i18n,
        auto_load=False,
    )

    assert player.rewind_button.toolTip() == "timeline.audio_player.rewind_tooltip"
    assert player.forward_button.toolTip() == "timeline.audio_player.forward_tooltip"
    player.cleanup()


def test_audio_player_chrome_area_has_height_caps(qapp, mock_i18n):
    player = AudioPlayer(
        "/tmp/nonexistent.mp3",
        mock_i18n,
        auto_load=False,
    )

    assert player.info_container.maximumHeight() == AUDIO_PLAYER_HEADER_MAX_HEIGHT
    assert player.control_bar.maximumHeight() == AUDIO_PLAYER_CONTROL_BAR_MAX_HEIGHT
    player.cleanup()


def test_audio_player_transcript_area_is_expandable(qapp, mock_i18n):
    player = AudioPlayer(
        "/tmp/nonexistent.mp3",
        mock_i18n,
        auto_load=False,
    )

    assert player.transcript_area.minimumHeight() == AUDIO_PLAYER_TRANSCRIPT_MIN_HEIGHT
    assert player.transcript_area.sizePolicy().verticalPolicy() == QSizePolicy.Policy.Expanding
    player.cleanup()


def test_audio_player_default_layout_centers_chrome_when_transcript_hidden(qapp, mock_i18n):
    player = AudioPlayer(
        "/tmp/nonexistent.mp3",
        mock_i18n,
        auto_load=False,
    )

    assert not player.top_fill.isHidden()
    assert not player.bottom_fill.isHidden()
    assert player.transcript_area.isHidden()
    assert player.transcript_divider.isHidden()
    player.cleanup()


def test_audio_player_inspector_presentation_hides_transcript_toggle_and_center_fill(
    qapp, mock_i18n
):
    player = AudioPlayer(
        "/tmp/nonexistent.mp3",
        mock_i18n,
        auto_load=False,
        presentation="inspector",
    )

    assert player.presentation == "inspector"
    assert player.show_transcript_button.isHidden()
    assert player.transcript_area.isHidden()
    assert player.top_fill.isHidden()
    assert player.bottom_fill.isHidden()
    assert player.surface.property("state") == "inspector"
    assert player.play_button.property("state") == "inspector"
    assert player.volume_slider.property("state") == "inspector"
    player.cleanup()


def test_audio_player_layout_mode_resizes_parent_dialog(qapp, mock_i18n):
    dialog = QDialog()
    dialog.resize(640, AUDIO_PLAYER_DIALOG_DEFAULT_HEIGHT)
    layout = QVBoxLayout(dialog)

    player = AudioPlayer(
        "/tmp/nonexistent.mp3",
        mock_i18n,
        auto_load=False,
    )
    layout.addWidget(player)

    player._resize_dialog_for_layout_mode(show_transcript=True)
    assert dialog.height() >= AUDIO_PLAYER_DIALOG_EXPANDED_MIN_HEIGHT

    player._resize_dialog_for_layout_mode(show_transcript=False)
    assert dialog.height() == AUDIO_PLAYER_DIALOG_DEFAULT_HEIGHT
    player.cleanup()


def test_audio_player_clear_media_resets_labels_and_controls(qapp, mock_i18n):
    player = AudioPlayer(
        "/tmp/nonexistent.mp3",
        mock_i18n,
        auto_load=False,
    )
    player._set_controls_enabled(True)
    player.file_label.setText("meeting.wav")

    player.clear_media()

    assert player.file_label.text() == ""
    assert player.play_button.isEnabled() is False
    player.cleanup()


def test_audio_player_prefers_adjacent_segment_json_for_synced_transcript(
    qapp, mock_i18n, tmp_path
):
    audio_path = tmp_path / "session.wav"
    audio_path.write_bytes(b"RIFF")
    transcript_txt = tmp_path / "transcript_session.txt"
    transcript_txt.write_text("plain transcript", encoding="utf-8")
    transcript_json = tmp_path / "transcript_session.json"
    transcript_json.write_text(
        json.dumps(
            {
                "text": "plain transcript",
                "segments": [{"start": 0.0, "end": 1.0, "text": "plain transcript"}],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    player = AudioPlayer(
        str(audio_path),
        mock_i18n,
        auto_load=False,
    )

    player.load_file(str(audio_path), transcript_path=str(transcript_txt))

    assert player._transcript_format == "segments"
    assert player._segment_timeline == [(0, 1000)]
    player.cleanup()
