import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

pytest.importorskip("PyQt6")

from utils.i18n import I18nQtManager
from ui.timeline.transcript_viewer import TranscriptViewer, TranscriptViewerDialog


def test_transcript_viewer_updates_on_language_change(qtbot, tmp_path):
    transcript_file = tmp_path / "sample.txt"
    transcript_file.write_text("Sample transcript", encoding="utf-8")

    i18n = I18nQtManager(default_language="en_US")
    viewer = TranscriptViewer(str(transcript_file), i18n)
    qtbot.addWidget(viewer)

    assert viewer.search_button.text() == i18n.t('transcript.search')
    assert viewer.prev_button.toolTip() == i18n.t('transcript.previous_match_tooltip')

    i18n.change_language('zh_CN')
    qtbot.waitUntil(lambda: viewer.search_button.text() == i18n.t('transcript.search'))

    assert viewer.search_input.placeholderText() == i18n.t('transcript.search_placeholder')
    assert viewer.clear_search_button.text() == i18n.t('transcript.clear_search')
    assert viewer.prev_button.toolTip() == i18n.t('transcript.previous_match_tooltip')
    assert viewer.next_button.text() == i18n.t('transcript.next_match_button')


def test_transcript_viewer_dialog_updates_on_language_change(qtbot, tmp_path):
    transcript_file = tmp_path / "sample.txt"
    transcript_file.write_text("Sample transcript", encoding="utf-8")

    i18n = I18nQtManager(default_language="zh_CN")
    dialog = TranscriptViewerDialog(str(transcript_file), i18n)
    qtbot.addWidget(dialog)
    dialog.show()

    assert dialog.windowTitle() == i18n.t('transcript.viewer_title')
    assert dialog.close_button.text() == i18n.t('common.close')

    i18n.change_language('en_US')
    qtbot.waitUntil(lambda: dialog.windowTitle() == i18n.t('transcript.viewer_title'))

    assert dialog.close_button.text() == i18n.t('common.close')
    assert dialog.viewer.search_input.placeholderText() == i18n.t('transcript.search_placeholder')
    assert dialog.viewer.search_button.text() == i18n.t('transcript.search')
