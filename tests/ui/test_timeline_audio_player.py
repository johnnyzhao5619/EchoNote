# SPDX-License-Identifier: Apache-2.0
"""UI tests for timeline audio player transcript sync behavior."""

from unittest.mock import Mock

import pytest
from PySide6.QtWidgets import QSizePolicy

from ui.constants import (
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
