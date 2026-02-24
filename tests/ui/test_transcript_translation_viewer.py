# SPDX-License-Identifier: Apache-2.0
"""UI tests for reusable transcript/translation viewer."""

import pytest

from ui.common.transcript_translation_viewer import (
    VIEW_MODE_COMPARE,
    VIEW_MODE_TRANSCRIPT,
    VIEW_MODE_TRANSLATION,
    TranscriptTranslationViewer,
)

pytestmark = pytest.mark.ui


def test_viewer_shows_mode_switch_when_both_artifacts_exist(qapp, mock_i18n, tmp_path):
    transcript_path = tmp_path / "transcript.txt"
    translation_path = tmp_path / "translation.txt"
    transcript_path.write_text("hello", encoding="utf-8")
    translation_path.write_text("nihao", encoding="utf-8")

    viewer = TranscriptTranslationViewer(
        i18n=mock_i18n,
        transcript_path=str(transcript_path),
        translation_path=str(translation_path),
        initial_mode=VIEW_MODE_COMPARE,
    )

    assert not viewer.mode_caption.isHidden()
    assert not viewer._mode_buttons[VIEW_MODE_TRANSCRIPT].isHidden()
    assert not viewer._mode_buttons[VIEW_MODE_TRANSLATION].isHidden()
    assert not viewer._mode_buttons[VIEW_MODE_COMPARE].isHidden()
    assert viewer.content_stack.currentIndex() == 1


def test_viewer_hides_mode_switch_when_only_transcript_exists(qapp, mock_i18n, tmp_path):
    transcript_path = tmp_path / "transcript.txt"
    transcript_path.write_text("hello", encoding="utf-8")

    viewer = TranscriptTranslationViewer(
        i18n=mock_i18n,
        transcript_path=str(transcript_path),
        translation_path=None,
        initial_mode=VIEW_MODE_TRANSCRIPT,
    )

    assert viewer.mode_caption.isHidden()
    assert viewer._mode_buttons[VIEW_MODE_TRANSLATION].isHidden()
    assert viewer._mode_buttons[VIEW_MODE_COMPARE].isHidden()
    assert viewer.content_stack.currentIndex() == 0


def test_viewer_translation_only_mode_uses_single_panel(qapp, mock_i18n, tmp_path):
    translation_path = tmp_path / "translation.txt"
    translation_path.write_text("nihao", encoding="utf-8")

    viewer = TranscriptTranslationViewer(
        i18n=mock_i18n,
        transcript_path=None,
        translation_path=str(translation_path),
        initial_mode=VIEW_MODE_TRANSLATION,
    )

    assert viewer.content_stack.currentIndex() == 0
    assert viewer.single_text_edit.toPlainText() == "nihao"
