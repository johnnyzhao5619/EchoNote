# SPDX-License-Identifier: Apache-2.0
"""UI tests for shared dialog launcher helpers."""

from unittest.mock import Mock

import pytest
from PySide6.QtWidgets import QDialog

import ui.common.audio_player_launcher as audio_player_launcher
import ui.common.text_viewer_launcher as text_viewer_launcher

pytestmark = pytest.mark.ui


class _DummyPlayer:
    def __init__(self):
        self.load_calls = []

    def load_file(self, file_path, transcript_path, translation_path):
        self.load_calls.append((file_path, transcript_path, translation_path))


class _DummyAudioDialog(QDialog):
    created = []

    def __init__(self, file_path, i18n, parent, transcript_path, translation_path):
        super().__init__(parent)
        self.file_path = file_path
        self.transcript_path = transcript_path
        self.translation_path = translation_path
        self.player = _DummyPlayer()
        _DummyAudioDialog.created.append(self)


class _DummyViewer:
    def __init__(self):
        self.mode_changes = []

    def set_view_mode(self, mode):
        self.mode_changes.append(mode)


class _DummyTextDialog(QDialog):
    created = []

    def __init__(
        self,
        *,
        i18n,
        transcript_path,
        translation_path,
        initial_mode,
        title_key,
        parent,
    ):
        super().__init__(parent)
        self.viewer = _DummyViewer()
        self.transcript_path = transcript_path
        self.translation_path = translation_path
        self.initial_mode = initial_mode
        self._title_key = title_key
        _DummyTextDialog.created.append(self)


def test_audio_launcher_reuses_cached_dialog_and_refreshes_loaded_file(qapp, mock_i18n, monkeypatch):
    _DummyAudioDialog.created = []
    dialog_cache = {}
    parent = QDialog()
    activate_mock = Mock()
    warning_mock = Mock()
    error_mock = Mock()
    logger = Mock()

    monkeypatch.setattr(audio_player_launcher, "AudioPlayerDialog", _DummyAudioDialog)
    monkeypatch.setattr(audio_player_launcher, "show_and_activate_dialog", activate_mock)

    audio_player_launcher.open_or_activate_audio_player(
        file_path="/tmp/demo.wav",
        i18n=mock_i18n,
        parent=parent,
        dialog_cache=dialog_cache,
        logger=logger,
        show_warning=warning_mock,
        show_error=error_mock,
        transcript_path="/tmp/demo.txt",
        translation_path="/tmp/demo.translated.txt",
    )
    audio_player_launcher.open_or_activate_audio_player(
        file_path="/tmp/demo.wav",
        i18n=mock_i18n,
        parent=parent,
        dialog_cache=dialog_cache,
        logger=logger,
        show_warning=warning_mock,
        show_error=error_mock,
        transcript_path="/tmp/new.txt",
        translation_path="/tmp/new.translated.txt",
    )

    assert len(_DummyAudioDialog.created) == 1
    assert _DummyAudioDialog.created[0].player.load_calls == [
        ("/tmp/demo.wav", "/tmp/new.txt", "/tmp/new.translated.txt")
    ]
    assert activate_mock.call_count == 2
    warning_mock.assert_not_called()
    error_mock.assert_not_called()


def test_audio_launcher_clears_cache_when_dialog_finishes(qapp, mock_i18n, monkeypatch):
    _DummyAudioDialog.created = []
    dialog_cache = {}
    parent = QDialog()
    monkeypatch.setattr(audio_player_launcher, "AudioPlayerDialog", _DummyAudioDialog)
    monkeypatch.setattr(audio_player_launcher, "show_and_activate_dialog", Mock())

    audio_player_launcher.open_or_activate_audio_player(
        file_path="/tmp/demo.wav",
        i18n=mock_i18n,
        parent=parent,
        dialog_cache=dialog_cache,
        logger=Mock(),
        show_warning=Mock(),
        show_error=Mock(),
    )
    dialog = dialog_cache["/tmp/demo.wav"]
    dialog.finished.emit(0)

    assert "/tmp/demo.wav" not in dialog_cache


def test_text_viewer_launcher_reuses_cached_dialog_and_updates_mode(qapp, mock_i18n, monkeypatch):
    _DummyTextDialog.created = []
    dialog_cache = {}
    parent = QDialog()
    activate_mock = Mock()
    warning_mock = Mock()
    logger = Mock()

    monkeypatch.setattr(text_viewer_launcher, "TranscriptTranslationViewerDialog", _DummyTextDialog)
    monkeypatch.setattr(text_viewer_launcher, "show_and_activate_dialog", activate_mock)

    text_viewer_launcher.open_or_activate_text_viewer(
        i18n=mock_i18n,
        dialog_cache=dialog_cache,
        parent=parent,
        transcript_path="/tmp/demo.txt",
        translation_path="/tmp/demo.translated.txt",
        initial_mode="compare",
        title_key="transcript.viewer_title",
        show_warning=warning_mock,
        logger=logger,
    )
    text_viewer_launcher.open_or_activate_text_viewer(
        i18n=mock_i18n,
        dialog_cache=dialog_cache,
        parent=parent,
        transcript_path="/tmp/demo.txt",
        translation_path="/tmp/demo.translated.txt",
        initial_mode="translation",
        title_key="timeline.translation_viewer_title",
        show_warning=warning_mock,
        logger=logger,
    )

    assert len(_DummyTextDialog.created) == 1
    reused_dialog = _DummyTextDialog.created[0]
    assert reused_dialog.viewer.mode_changes == ["translation"]
    assert reused_dialog.windowTitle() == "timeline.translation_viewer_title"
    assert activate_mock.call_count == 2


def test_text_viewer_launcher_warns_when_no_files_available(qapp, mock_i18n):
    warning_mock = Mock()
    text_viewer_launcher.open_or_activate_text_viewer(
        i18n=mock_i18n,
        dialog_cache={},
        parent=QDialog(),
        transcript_path=None,
        translation_path=None,
        initial_mode="transcript",
        title_key="transcript.viewer_title",
        show_warning=warning_mock,
    )

    warning_mock.assert_called_once_with("common.warning", "viewer.file_not_found")


def test_resolve_text_viewer_initial_mode_prefers_compare_when_both_paths_exist():
    mode = text_viewer_launcher.resolve_text_viewer_initial_mode(
        transcript_path="/tmp/demo.txt",
        translation_path="/tmp/demo.translated.txt",
    )

    assert mode == text_viewer_launcher.VIEW_MODE_COMPARE


def test_resolve_text_viewer_initial_mode_supports_translation_preference():
    mode = text_viewer_launcher.resolve_text_viewer_initial_mode(
        transcript_path="/tmp/demo.txt",
        translation_path="/tmp/demo.translated.txt",
        preferred_mode=text_viewer_launcher.VIEW_MODE_TRANSLATION,
    )

    assert mode == text_viewer_launcher.VIEW_MODE_TRANSLATION
