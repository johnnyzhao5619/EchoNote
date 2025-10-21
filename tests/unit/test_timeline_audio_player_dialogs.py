from datetime import datetime, timedelta
from types import MethodType

import pytest

PyQt6 = pytest.importorskip("PyQt6")
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QDialog, QWidget

from data.database.models import CalendarEvent

from ui.timeline.event_card import CurrentTimeIndicator
from ui.timeline.widget import TimelineWidget
from utils.i18n import I18nQtManager


class DummyTimelineManager:
    """Provide the minimal timeline manager API used by the widget."""

    def get_timeline_events(self, **_):
        current = datetime.now().isoformat()
        return {
            "current_time": current,
            "past_events": [],
            "future_events": [],
            "has_more": False,
        }

    def search_events(self, *_args, **_kwargs):
        return []

    def _get_auto_task_map(self, *_):
        return {}

    def set_auto_task(self, *_):
        return None


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


class _DummyAudioDialog(QDialog):
    delete_on_close = True

    def __init__(self, file_path, _i18n, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.show_count = 0
        self.raise_count = 0
        self.activate_count = 0
        self.setWindowModality(Qt.WindowModality.NonModal)
        self.setAttribute(
            Qt.WidgetAttribute.WA_DeleteOnClose,
            self.delete_on_close,
        )

    def show(self):
        self.show_count += 1
        super().show()

    def raise_(self):  # noqa: D401 - Qt API name
        self.raise_count += 1
        super().raise_()

    def activateWindow(self):  # noqa: N802 - Qt API name
        self.activate_count += 1
        super().activateWindow()


class _StubAudioPlayer(QWidget):
    """Minimal QWidget replacement for the audio player used in dialog tests."""

    def __init__(self, *_args, parent=None, **_kwargs):
        super().__init__(parent)
        self.cleanup_calls = 0

    def cleanup(self):
        self.cleanup_calls += 1

    def update_translations(self):
        return None


def test_search_always_refreshes_timeline(monkeypatch, qapp):
    monkeypatch.setattr(
        "ui.timeline.widget.QTimer.singleShot",
        staticmethod(lambda *_: None),
    )

    i18n = I18nQtManager(default_language="en_US")
    widget = TimelineWidget(DummyTimelineManager(), i18n)

    try:
        load_calls = []

        def _counted_load(self, reset=True):
            load_calls.append(reset)

        widget.load_timeline_events = MethodType(_counted_load, widget)

        widget.search_input.setText("meeting")
        widget._on_search()
        widget._on_search()

        assert load_calls == [True, True]
        assert widget.current_query == "meeting"
    finally:
        widget.deleteLater()
        qapp.processEvents()


def test_future_event_order_keeps_nearest_next_to_indicator(monkeypatch, qapp):
    monkeypatch.setattr(
        "ui.timeline.widget.QTimer.singleShot",
        staticmethod(lambda *_: None),
    )

    now = datetime.now().astimezone()
    soon_event = CalendarEvent(
        id="event-soon",
        title="Soon meeting",
        start_time=(now + timedelta(minutes=15)).isoformat(),
        end_time=(now + timedelta(minutes=45)).isoformat(),
    )
    later_event = CalendarEvent(
        id="event-later",
        title="Later meeting",
        start_time=(now + timedelta(minutes=90)).isoformat(),
        end_time=(now + timedelta(minutes=120)).isoformat(),
    )

    class SearchTimelineManager(DummyTimelineManager):
        def search_events(self, *_args, **_kwargs):
            return [
                {"event": later_event, "auto_tasks": {}},
                {"event": soon_event, "auto_tasks": {}},
            ]

    i18n = I18nQtManager(default_language="en_US")
    widget = TimelineWidget(SearchTimelineManager(), i18n)

    try:
        widget.current_query = "meeting"
        widget.load_timeline_events(reset=True)

        indicator_index = next(
            i for i, card in enumerate(widget.event_cards)
            if isinstance(card, CurrentTimeIndicator)
        )

        assert indicator_index > 0, "indicator should follow future events"

        nearest_card = widget.event_cards[indicator_index - 1]
        assert getattr(nearest_card, "is_future", False)
        assert nearest_card.event.id == soon_event.id
    finally:
        widget.deleteLater()
        qapp.processEvents()


def test_audio_dialogs_remain_non_modal_and_cached(monkeypatch, qapp, tmp_path):
    monkeypatch.setattr(
        "ui.timeline.widget.QTimer.singleShot",
        staticmethod(lambda *_: None),
    )
    monkeypatch.setattr(
        "ui.timeline.audio_player.AudioPlayerDialog",
        _DummyAudioDialog,
    )

    i18n = I18nQtManager(default_language="en_US")
    widget = TimelineWidget(DummyTimelineManager(), i18n)

    try:
        file_one = tmp_path / "first.wav"
        file_two = tmp_path / "second.wav"

        widget._on_view_recording(str(file_one))
        dialog_one = widget._audio_player_dialogs[str(file_one)]

        assert dialog_one.windowModality() == Qt.WindowModality.NonModal
        assert dialog_one.show_count == 1
        assert widget.isEnabled()

        widget._on_view_recording(str(file_one))
        assert widget._audio_player_dialogs[str(file_one)] is dialog_one
        assert dialog_one.show_count == 2
        assert dialog_one.raise_count == 1
        assert dialog_one.activate_count == 1

        widget._on_view_recording(str(file_two))
        dialog_two = widget._audio_player_dialogs[str(file_two)]

        assert dialog_two is not dialog_one
        assert widget.isEnabled()
        assert len(widget._audio_player_dialogs) == 2

        dialog_one.close()
        qapp.processEvents()

        assert str(file_one) not in widget._audio_player_dialogs
        assert str(file_two) in widget._audio_player_dialogs
    finally:
        widget.deleteLater()
        qapp.processEvents()


def test_transcript_dialogs_are_non_modal_and_cached(monkeypatch, qapp, tmp_path):
    monkeypatch.setattr(
        "ui.timeline.widget.QTimer.singleShot",
        staticmethod(lambda *_: None),
    )

    i18n = I18nQtManager(default_language="en_US")
    widget = TimelineWidget(DummyTimelineManager(), i18n)

    try:
        transcript_path = tmp_path / "transcript.txt"
        transcript_path.write_text("sample transcript", encoding="utf-8")

        widget._on_view_transcript(str(transcript_path))
        dialog = widget._text_viewer_dialogs[str(transcript_path)]

        assert dialog.windowModality() == Qt.WindowModality.NonModal
        assert not dialog.isModal()
        assert dialog.testAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        widget._on_view_transcript(str(transcript_path))
        assert widget._text_viewer_dialogs[str(transcript_path)] is dialog

        dialog.close()
        qapp.processEvents()

        assert str(transcript_path) not in widget._text_viewer_dialogs
    finally:
        widget.deleteLater()
        qapp.processEvents()


def test_audio_dialog_cleanup_via_finished_signal(monkeypatch, qapp, tmp_path):
    monkeypatch.setattr(
        "ui.timeline.widget.QTimer.singleShot",
        staticmethod(lambda *_: None),
    )
    monkeypatch.setattr(
        "ui.timeline.audio_player.AudioPlayer",
        _StubAudioPlayer,
    )

    i18n = I18nQtManager(default_language="en_US")
    widget = TimelineWidget(DummyTimelineManager(), i18n)
    dialog = None

    try:
        file_path = tmp_path / "recording.wav"
        widget._on_view_recording(str(file_path))
        dialog = widget._audio_player_dialogs[str(file_path)]

        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        assert not dialog.testAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        finished_results = []
        destroyed_emissions = []

        dialog.finished.connect(lambda result: finished_results.append(result))
        dialog.destroyed.connect(lambda *_: destroyed_emissions.append(True))

        dialog.close_button.click()
        qapp.processEvents()

        assert finished_results, "close button should emit finished()"
        assert not destroyed_emissions, "cleanup should not rely on destroyed()"
        assert dialog.player.cleanup_calls == 1
        assert str(file_path) not in widget._audio_player_dialogs
    finally:
        if dialog is not None:
            dialog.deleteLater()
        widget.deleteLater()
        qapp.processEvents()


def test_pagination_failure_restores_state(monkeypatch, qapp):
    monkeypatch.setattr(
        "ui.timeline.widget.QTimer.singleShot",
        staticmethod(lambda *_: None),
    )

    class FailingPaginationManager(DummyTimelineManager):
        def __init__(self):
            self.calls = 0

        def get_timeline_events(self, **_kwargs):
            self.calls += 1
            if self.calls == 1:
                current = datetime.now().isoformat()
                return {
                    "current_time": current,
                    "past_events": [],
                    "future_events": [],
                    "has_more": True,
                }

            raise RuntimeError("pagination failed")

    i18n = I18nQtManager(default_language="en_US")
    manager = FailingPaginationManager()
    widget = TimelineWidget(manager, i18n)

    class _StubScrollBar:
        def maximum(self):
            return 100

    try:
        assert widget.load_timeline_events(reset=True)
        original_page = widget.current_page
        original_has_more = widget.has_more
        monkeypatch.setattr(
            widget.scroll_area,
            "verticalScrollBar",
            lambda: _StubScrollBar(),
        )

        widget._on_scroll(90)

        assert manager.calls == 2
        assert widget.current_page == original_page
        assert widget.has_more == original_has_more
    finally:
        widget.deleteLater()
        qapp.processEvents()
