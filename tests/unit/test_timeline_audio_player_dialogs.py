from datetime import datetime

import pytest

PyQt6 = pytest.importorskip("PyQt6")
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QDialog

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
    def __init__(self, file_path, _i18n, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.show_count = 0
        self.raise_count = 0
        self.activate_count = 0
        self.setWindowModality(Qt.WindowModality.NonModal)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)

    def show(self):
        self.show_count += 1
        super().show()

    def raise_(self):  # noqa: D401 - Qt API name
        self.raise_count += 1
        super().raise_()

    def activateWindow(self):  # noqa: N802 - Qt API name
        self.activate_count += 1
        super().activateWindow()


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
