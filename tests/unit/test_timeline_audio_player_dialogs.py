import math
from datetime import datetime, timedelta
from types import MethodType

import pytest

PyQt6 = pytest.importorskip("PyQt6")
from PyQt6.QtCore import Qt, QDate, QDateTime, QTime
from PyQt6.QtMultimedia import QMediaPlayer
from PyQt6.QtWidgets import QApplication, QDialog, QWidget

from data.database.models import CalendarEvent

from ui.timeline.audio_player import AudioPlayerDialog, AudioPlayer
from ui.timeline.event_card import CurrentTimeIndicator
from ui.timeline.widget import TimelineWidget
from utils.i18n import I18nQtManager
from core.timeline.manager import to_local_naive


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


class RecordingTimelineManager(DummyTimelineManager):
    """Timeline manager that records pagination arguments for assertions."""

    def __init__(self):
        self.calls = []

    def get_timeline_events(self, **kwargs):
        self.calls.append(kwargs)
        return super().get_timeline_events(**kwargs)


class SlowTimelineManager(DummyTimelineManager):
    """Timeline manager that triggers a refresh while loading."""

    def __init__(self):
        super().__init__()
        self.calls = []
        self.refresh_callback = None
        self._triggered = False

    def get_timeline_events(self, **kwargs):
        self.calls.append(kwargs)
        if self.refresh_callback and not self._triggered:
            self._triggered = True
            self.refresh_callback()
        return super().get_timeline_events(**kwargs)


class _Signal:
    """Minimal Qt-like signal used to observe settings updates in tests."""

    def __init__(self):
        self._callbacks = []

    def connect(self, callback):
        if callback not in self._callbacks:
            self._callbacks.append(callback)

    def disconnect(self, callback):
        try:
            self._callbacks.remove(callback)
        except ValueError:
            pass

    def emit(self, *args, **kwargs):
        for callback in list(self._callbacks):
            callback(*args, **kwargs)


class _StubSettingsManager:
    """Minimal settings facade exposing timeline preferences."""

    def __init__(self, values, *, with_signal: bool = False):
        self._values = dict(values)
        self._signal = _Signal() if with_signal else None
        if with_signal:
            self.setting_changed = self._signal

    def get_setting(self, key):
        return self._values.get(key)

    def update(self, key, value):
        self._values[key] = value
        if self._signal:
            self._signal.emit(key, value)


class FlakyTimelineManager(DummyTimelineManager):
    """Timeline manager that can simulate failures after a successful load."""

    def __init__(self, event):
        self._event = event
        self.fail_requests = False

    def get_timeline_events(self, **_):
        if self.fail_requests:
            raise RuntimeError("timeline fetch failed")

        current = datetime.now().isoformat()
        return {
            "current_time": current,
            "past_events": [
                {"event": self._event, "artifacts": {}},
            ],
            "future_events": [],
            "has_more": False,
        }


class AutoTaskFailureTimelineManager(DummyTimelineManager):
    """Timeline manager that simulates auto-task persistence failures."""

    def __init__(self, event, persisted_config=None):
        self._event = event
        self.persisted_config = persisted_config or {
            "enable_transcription": False,
            "enable_recording": False,
            "transcription_language": None,
            "enable_translation": False,
            "translation_target_language": None,
        }
        self.get_auto_task_calls = []

    def get_timeline_events(self, **_):
        current = datetime.now().isoformat()
        return {
            "current_time": current,
            "past_events": [],
            "future_events": [
                {"event": self._event, "auto_tasks": dict(self.persisted_config)},
            ],
            "has_more": False,
        }

    def set_auto_task(self, *_):
        raise RuntimeError("save failed")

    def get_auto_task(self, event_id):
        self.get_auto_task_calls.append(event_id)
        return dict(self.persisted_config)

    def _default_auto_task_config(self):
        return {
            "enable_transcription": False,
            "enable_recording": False,
            "transcription_language": None,
            "enable_translation": False,
            "translation_target_language": None,
        }


class CapturingAutoTaskTimelineManager(DummyTimelineManager):
    """Timeline manager that records auto-task updates for assertions."""

    def __init__(self, event, initial_config):
        self._event = event
        self.initial_config = dict(initial_config)
        self.saved_configs = []

    def get_timeline_events(self, **_):
        current = datetime.now().isoformat()
        return {
            "current_time": current,
            "past_events": [],
            "future_events": [
                {"event": self._event, "auto_tasks": dict(self.initial_config)},
            ],
            "has_more": False,
        }

    def set_auto_task(self, event_id, config):
        self.saved_configs.append((event_id, dict(config)))


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


def test_timeline_uses_settings_preferences(monkeypatch, qapp):
    monkeypatch.setattr(
        "ui.timeline.widget.QTimer.singleShot",
        staticmethod(lambda *_: None),
    )

    manager = RecordingTimelineManager()
    i18n = I18nQtManager(default_language="en_US")
    settings = _StubSettingsManager(
        {
            "timeline.past_days": 7,
            "timeline.future_days": 5,
            "timeline.page_size": 12,
        }
    )

    widget = TimelineWidget(
        manager,
        i18n,
        settings_manager=settings,
    )

    try:
        assert widget.past_days == 7
        assert widget.future_days == 5
        assert widget.page_size == 12

        today = QDate.currentDate()
        assert widget.start_date_edit.date() == today.addDays(-7)
        assert widget.end_date_edit.date() == today.addDays(5)

        widget.past_days = 10.75
        widget.future_days = -3
        widget.sync_date_filters_with_preferences()

        today = QDate.currentDate()
        assert widget.start_date_edit.date() == today.addDays(-10)
        assert widget.end_date_edit.date() == today

        widget.load_timeline_events()

        assert manager.calls, "Expected timeline manager to be invoked"
        call_kwargs = manager.calls[-1]
        assert call_kwargs["past_days"] == 7
        assert call_kwargs["future_days"] == 5
        assert call_kwargs["page_size"] == 12
    finally:
        widget.deleteLater()


def test_timeline_refreshes_after_preference_update(monkeypatch, qapp):
    monkeypatch.setattr(
        "ui.timeline.widget.QTimer.singleShot",
        staticmethod(lambda *_: None),
    )

    manager = RecordingTimelineManager()
    i18n = I18nQtManager(default_language="en_US")
    settings = _StubSettingsManager(
        {
            "timeline.past_days": 3,
            "timeline.future_days": 4,
            "timeline.page_size": 10,
        },
        with_signal=True,
    )

    widget = TimelineWidget(
        manager,
        i18n,
        settings_manager=settings,
    )

    try:
        widget.load_timeline_events()
        manager.calls.clear()

        settings.update("timeline.past_days", 9)

        assert widget.past_days == 9
        today = QDate.currentDate()
        assert widget.start_date_edit.date() == today.addDays(-9)
        assert widget.end_date_edit.date() == today.addDays(4)

        expected_start = QDateTime(
            today.addDays(-9), QTime(0, 0, 0)
        ).toString(Qt.DateFormat.ISODate)
        expected_end = QDateTime(
            today.addDays(4), QTime(23, 59, 59)
        ).toString(Qt.DateFormat.ISODate)

        assert widget.current_filters["start_date"] == expected_start
        assert widget.current_filters["end_date"] == expected_end

        assert manager.calls, "Expected a timeline reload after preference change"
        call_kwargs = manager.calls[-1]
        assert call_kwargs["past_days"] == 9
        assert call_kwargs["future_days"] == 4
        assert call_kwargs["page_size"] == 10

        manager.calls.clear()
        widget.current_page = 3
        settings.update("timeline.page_size", 25)

        assert widget.page_size == 25
        assert widget.current_page == 0
        assert manager.calls, "Expected page size change to reload timeline"
        size_kwargs = manager.calls[-1]
        assert size_kwargs["page_size"] == 25
        assert size_kwargs["page"] == 0

        manager.calls.clear()
        widget.is_loading = True
        widget._pending_refresh = None
        settings.update("timeline.page_size", 30)

        assert widget.page_size == 30
        assert widget._pending_refresh is True
        assert manager.calls == []
    finally:
        widget.is_loading = False
        widget._pending_refresh = None
        widget.deleteLater()


def test_date_filters_expand_query_window(monkeypatch, qapp):
    monkeypatch.setattr(
        "ui.timeline.widget.QTimer.singleShot",
        staticmethod(lambda *_: None),
    )

    manager = RecordingTimelineManager()
    i18n = I18nQtManager(default_language="en_US")
    settings = _StubSettingsManager(
        {
            "timeline.past_days": 7,
            "timeline.future_days": 5,
            "timeline.page_size": 20,
        }
    )

    widget = TimelineWidget(
        manager,
        i18n,
        settings_manager=settings,
    )

    try:
        # Initial load respects preferences
        widget.load_timeline_events()
        assert manager.calls, "Expected an initial load"
        baseline = manager.calls[-1]
        assert baseline["past_days"] == 7
        assert baseline["future_days"] == 5

        today = QDate.currentDate()
        extended_start = today.addDays(-60)
        extended_end = today.addDays(45)

        prev_start_block = widget.start_date_edit.blockSignals(True)
        prev_end_block = widget.end_date_edit.blockSignals(True)
        try:
            widget.start_date_edit.setDate(extended_start)
            widget.end_date_edit.setDate(extended_end)
        finally:
            widget.start_date_edit.blockSignals(prev_start_block)
            widget.end_date_edit.blockSignals(prev_end_block)

        widget._on_filter_changed()

        assert len(manager.calls) >= 2, "Expected filter change to reload timeline"
        expanded = manager.calls[-1]
        center_time = expanded["center_time"]

        start_dt = to_local_naive(widget.current_filters["start_date"])
        end_dt = to_local_naive(widget.current_filters["end_date"])

        seconds_per_day = 24 * 60 * 60
        required_past = math.ceil(
            max(0.0, (center_time - start_dt).total_seconds()) / seconds_per_day
        )
        required_future = math.ceil(
            max(0.0, (end_dt - center_time).total_seconds()) / seconds_per_day
        )

        assert expanded["past_days"] == max(widget.past_days, required_past)
        assert expanded["future_days"] == max(widget.future_days, required_future)
    finally:
        widget.deleteLater()


def test_filter_swaps_inverted_dates(monkeypatch, qapp):
    monkeypatch.setattr(
        "ui.timeline.widget.QTimer.singleShot",
        staticmethod(lambda *_: None),
    )

    now = datetime.now()
    event = CalendarEvent(
        id="event-swapped",
        title="Order corrected",
        start_time=(now - timedelta(hours=2)).isoformat(),
        end_time=(now - timedelta(hours=1)).isoformat(),
    )

    manager = RecordingEventTimelineManager(event)
    i18n = I18nQtManager(default_language="en_US")
    widget = TimelineWidget(manager, i18n)

    try:
        later = QDate.currentDate()
        earlier = later.addDays(-5)

        prev_start_blocked = widget.start_date_edit.blockSignals(True)
        prev_end_blocked = widget.end_date_edit.blockSignals(True)
        try:
            widget.start_date_edit.setDate(later)
            widget.end_date_edit.setDate(earlier)
        finally:
            widget.start_date_edit.blockSignals(prev_start_blocked)
            widget.end_date_edit.blockSignals(prev_end_blocked)

        widget._on_filter_changed()

        assert manager.calls, "Expected timeline refresh after swapping dates"
        filters = manager.calls[-1]["filters"]
        assert filters is not None

        start_filter = to_local_naive(filters["start_date"])
        end_filter = to_local_naive(filters["end_date"])

        assert start_filter <= end_filter

        assert any(
            getattr(card, "event", None) and card.event.id == event.id
            for card in widget.event_cards
        )
    finally:
        widget.deleteLater()


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


def test_refresh_during_loading_schedules_follow_up(monkeypatch, qapp):
    scheduled_calls = []

    def fake_single_shot(delay, callback):
        scheduled_calls.append((delay, callback))
        return None

    monkeypatch.setattr(
        "ui.timeline.widget.QTimer.singleShot",
        staticmethod(fake_single_shot),
    )

    manager = SlowTimelineManager()
    i18n = I18nQtManager(default_language="en_US")
    widget = TimelineWidget(manager, i18n)

    try:
        scheduled_calls.clear()

        original_load = widget.load_timeline_events
        load_resets = []

        def counting_load(self, reset=True):
            load_resets.append(reset)
            return original_load(reset=reset)

        widget.load_timeline_events = MethodType(counting_load, widget)

        manager.refresh_callback = lambda: widget._refresh_timeline(reset=True)

        assert widget.load_timeline_events(reset=True)
        assert len(manager.calls) == 1

        zero_delay = [cb for delay, cb in scheduled_calls if delay == 0]
        assert zero_delay, "Expected pending refresh to be scheduled"

        scheduled_calls[:] = [item for item in scheduled_calls if item[0] != 0]
        for callback in zero_delay:
            callback()

        assert len(manager.calls) == 2
        assert load_resets == [True, True, True]
        assert widget._pending_refresh is None
    finally:
        widget.deleteLater()
        qapp.processEvents()


def test_refresh_failure_keeps_existing_cards(monkeypatch, qapp):
    monkeypatch.setattr(
        "ui.timeline.widget.QTimer.singleShot",
        staticmethod(lambda *_: None),
    )

    past_start = datetime.now() - timedelta(hours=2)
    past_end = past_start + timedelta(hours=1)
    event = CalendarEvent(
        id="event-past",
        title="Completed meeting",
        start_time=past_start.isoformat(),
        end_time=past_end.isoformat(),
    )

    manager = FlakyTimelineManager(event)
    i18n = I18nQtManager(default_language="en_US")
    widget = TimelineWidget(manager, i18n)

    try:
        assert widget.load_timeline_events(reset=True)
        qapp.processEvents()

        original_cards = list(widget.event_cards)
        original_event_ids = [
            card.event.id for card in original_cards if hasattr(card, "event")
        ]

        assert original_event_ids, "Expected at least one event card after load"

        manager.fail_requests = True

        assert not widget.load_timeline_events(reset=True)
        qapp.processEvents()

        remaining_event_ids = [
            card.event.id for card in widget.event_cards if hasattr(card, "event")
        ]

        assert remaining_event_ids == original_event_ids
        assert any(
            isinstance(card, CurrentTimeIndicator) for card in widget.event_cards
        )
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

        # The top of the future event stack should be the soonest meeting.
        top_card = widget.event_cards[0]
        assert getattr(top_card, "is_future", False)
        assert top_card.event.id == soon_event.id

        nearest_card = widget.event_cards[indicator_index - 1]
        assert getattr(nearest_card, "is_future", False)
        assert nearest_card.event.id == soon_event.id

        # Confirm indicator alignment inside the layout matches the list order.
        layout_index = widget.timeline_layout.indexOf(
            widget.event_cards[indicator_index]
        )
        assert layout_index == indicator_index
    finally:
        widget.deleteLater()
        qapp.processEvents()


def test_auto_task_failure_restores_ui(monkeypatch, qapp):
    monkeypatch.setattr(
        "ui.timeline.widget.QTimer.singleShot",
        staticmethod(lambda *_: None),
    )

    now = datetime.now().astimezone()
    future_event = CalendarEvent(
        id="event-future",
        title="Upcoming meeting",
        start_time=(now + timedelta(hours=1)).isoformat(),
        end_time=(now + timedelta(hours=2)).isoformat(),
    )

    manager = AutoTaskFailureTimelineManager(future_event)
    i18n = I18nQtManager(default_language="en_US")
    widget = TimelineWidget(manager, i18n)

    try:
        assert widget.load_timeline_events(reset=True)
        qapp.processEvents()

        card = widget.get_event_card_by_id(future_event.id)
        assert card is not None, "Expected future event card to be created"
        assert not card.transcription_checkbox.isChecked()

        warnings = []

        def fake_warning(parent, title, message):
            warnings.append((parent, title, message))
            return None

        monkeypatch.setattr(
            "ui.timeline.widget.QMessageBox.warning",
            staticmethod(fake_warning),
        )

        card.transcription_checkbox.setChecked(True)
        qapp.processEvents()

        assert not card.transcription_checkbox.isChecked()
        assert not card.recording_checkbox.isChecked()
        assert not card.translation_checkbox.isChecked()
        assert manager.get_auto_task_calls == [future_event.id]

        assert warnings, "Expected user-facing warning when saving fails"
        _, title, message = warnings[0]
        assert title == i18n.t("timeline.auto_task_save_failed_title")
        expected_prefix = i18n.t("timeline.auto_task_save_failed_message").split("\n")[0]
        assert expected_prefix in message
        assert "save failed" in message
    finally:
        widget.deleteLater()
        qapp.processEvents()


def test_transcription_language_preserved_on_toggle(monkeypatch, qapp):
    monkeypatch.setattr(
        "ui.timeline.widget.QTimer.singleShot",
        staticmethod(lambda *_: None),
    )

    now = datetime.now().astimezone()
    future_event = CalendarEvent(
        id="event-transcription",
        title="Language capture meeting",
        start_time=(now + timedelta(hours=3)).isoformat(),
        end_time=(now + timedelta(hours=4)).isoformat(),
    )

    i18n = I18nQtManager(default_language="en_US")
    initial_config = {
        "enable_transcription": True,
        "enable_recording": False,
        "transcription_language": i18n.default_language,
        "enable_translation": False,
        "translation_target_language": None,
    }

    manager = CapturingAutoTaskTimelineManager(future_event, initial_config)
    widget = TimelineWidget(manager, i18n)

    try:
        assert widget.load_timeline_events(reset=True)
        qapp.processEvents()

        card = widget.get_event_card_by_id(future_event.id)
        assert card is not None, "Expected future event card to be created"
        assert card.event_data["auto_tasks"]["transcription_language"] == i18n.default_language

        # Toggle recording to trigger an auto-task change emission.
        card.recording_checkbox.setChecked(True)
        qapp.processEvents()

        assert manager.saved_configs, "Expected auto-task update to be persisted"
        _, saved_config = manager.saved_configs[-1]
        assert saved_config["transcription_language"] == i18n.default_language
        assert card.event_data["auto_tasks"]["transcription_language"] == i18n.default_language
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


def test_view_recording_warns_when_audio_unavailable(monkeypatch, qapp, tmp_path):
    monkeypatch.setattr(
        "ui.timeline.widget.QTimer.singleShot",
        staticmethod(lambda *_: None),
    )

    def _raise_import_error(_name):
        raise ImportError("QtMultimedia is missing")

    monkeypatch.setattr(
        "ui.timeline.widget.importlib.import_module",
        _raise_import_error,
    )

    captured = []

    def _capture_warning(parent, title, message):
        captured.append((parent, title, message))

    monkeypatch.setattr(
        "ui.timeline.widget.QMessageBox.warning",
        _capture_warning,
    )

    i18n = I18nQtManager(default_language="en_US")
    widget = TimelineWidget(DummyTimelineManager(), i18n)

    try:
        file_path = tmp_path / "recording.wav"
        widget._on_view_recording(str(file_path))

        assert not widget._audio_player_dialogs
        assert captured, "Expected a warning dialog when audio is unavailable"
        _, title, message = captured[0]
        assert title == i18n.t('timeline.audio_player_unavailable_title')
        assert message == i18n.t('timeline.audio_player_unavailable_message')
    finally:
        widget.deleteLater()
        qapp.processEvents()


def test_view_recording_surfaces_creation_errors(monkeypatch, qapp, tmp_path):
    monkeypatch.setattr(
        "ui.timeline.widget.QTimer.singleShot",
        staticmethod(lambda *_: None),
    )

    class _FailingAudioDialog:
        def __init__(self, *_args, **_kwargs):
            raise RuntimeError("dialog crashed")

    monkeypatch.setattr(
        "ui.timeline.audio_player.AudioPlayerDialog",
        _FailingAudioDialog,
    )

    captured = []

    def _capture_critical(parent, title, message):
        captured.append((parent, title, message))

    monkeypatch.setattr(
        "ui.timeline.widget.QMessageBox.critical",
        staticmethod(_capture_critical),
    )

    i18n = I18nQtManager(default_language="en_US")
    widget = TimelineWidget(DummyTimelineManager(), i18n)

    try:
        file_path = tmp_path / "broken.wav"
        widget._on_view_recording(str(file_path))

        assert not widget._audio_player_dialogs
        assert captured, "Expected an error dialog when audio dialog creation fails"
        _, title, message = captured[0]
        assert title == i18n.t('timeline.audio_player_open_failed_title')
        assert message == i18n.t('timeline.audio_player_open_failed_message').format(
            error="dialog crashed"
        )
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


def test_audio_player_resets_ui_on_error(monkeypatch, qapp):
    import ui.timeline.audio_player as audio_player_module

    original_media_player = audio_player_module.QMediaPlayer

    class _StubAudioOutput:
        def __init__(self, *_args, **_kwargs):
            self.volume = 1.0

        def setVolume(self, volume):
            self.volume = volume

    class _StubMediaPlayer:
        PlaybackState = original_media_player.PlaybackState
        MediaStatus = original_media_player.MediaStatus
        Error = original_media_player.Error

        def __init__(self, *_args, **_kwargs):
            self._state = self.PlaybackState.StoppedState
            self._duration = 0
            self._position = 0
            self._audio_output = None
            self.positionChanged = _Signal()
            self.durationChanged = _Signal()
            self.playbackStateChanged = _Signal()
            self.errorOccurred = _Signal()
            self.mediaStatusChanged = _Signal()

        def setAudioOutput(self, output):
            self._audio_output = output

        def playbackState(self):
            return self._state

        def stop(self):
            self._state = self.PlaybackState.StoppedState
            self.playbackStateChanged.emit(self._state)

        def duration(self):
            return self._duration

        def setPosition(self, position):
            self._position = position
            self.positionChanged.emit(position)

    monkeypatch.setattr(audio_player_module, "QMediaPlayer", _StubMediaPlayer)
    monkeypatch.setattr(audio_player_module, "QAudioOutput", _StubAudioOutput)

    i18n = I18nQtManager(default_language="en_US")
    player = AudioPlayer("fake.wav", i18n, auto_load=False)

    try:
        initial_time = i18n.t("timeline.audio_player.initial_time")

        player._on_duration_changed(120000)
        player._on_position_changed(60000)
        assert player.progress_slider.value() == 60000
        assert player.current_time_label.text() != initial_time

        player._playback_state = original_media_player.PlaybackState.PlayingState
        player.update_translations()
        assert player.play_button.text() == i18n.t("timeline.audio_player.pause_button_label")

        player._on_error(original_media_player.Error.FormatError, "decode failed")

        assert player.progress_slider.value() == 0
        assert player.current_time_label.text() == initial_time
        assert player.total_time_label.text() == initial_time
        assert player.play_button.text() == i18n.t("timeline.audio_player.play_button_label")
        assert (
            player.player.playbackState()
            == original_media_player.PlaybackState.StoppedState
        )
    finally:
        player.deleteLater()
        qapp.processEvents()


def test_audio_player_dialog_surfaces_missing_file_error(monkeypatch, qapp, tmp_path):
    missing_file = tmp_path / "missing.wav"

    captured_errors = []

    original_handler = AudioPlayerDialog._on_playback_error

    def capturing_handler(self, error_msg):
        captured_errors.append(error_msg)
        return original_handler(self, error_msg)

    monkeypatch.setattr(
        AudioPlayerDialog,
        "_on_playback_error",
        capturing_handler,
    )

    message_calls = []

    def fake_critical(parent, title, message):
        message_calls.append((parent, title, message))
        return None

    monkeypatch.setattr(
        "ui.timeline.audio_player.QMessageBox.critical",
        staticmethod(fake_critical),
    )

    i18n = I18nQtManager(default_language="en_US")
    dialog = AudioPlayerDialog(str(missing_file), i18n)

    try:
        qapp.processEvents()

        assert captured_errors, "Expected dialog to receive playback_error signal"
        error_msg = captured_errors[-1]
        assert str(missing_file) in error_msg

        assert message_calls, "Expected critical message box to be shown"
        _, title, body = message_calls[-1]
        assert title == i18n.t("common.error")
        assert error_msg in body
    finally:
        dialog.close()
        dialog.deleteLater()
        qapp.processEvents()


@pytest.mark.parametrize(
    "error_enum, translation_key",
    [
        (
            QMediaPlayer.Error.ServiceMissingError,
            "timeline.audio_player.errors.service_missing",
        ),
        (
            QMediaPlayer.Error.FormatError,
            "timeline.audio_player.errors.format_error",
        ),
    ],
)
def test_audio_player_emits_localized_qt_errors(qapp, tmp_path, error_enum, translation_key):
    detail = "mock detail"
    i18n = I18nQtManager(default_language="en_US")
    player = AudioPlayer(str(tmp_path / "dummy.wav"), i18n, auto_load=False)

    messages = []
    player.playback_error.connect(messages.append)

    try:
        player._on_error(error_enum, detail)
        assert messages, "Expected localized error message to be emitted"
        assert messages[-1] == i18n.t(translation_key, details=detail)
    finally:
        player.deleteLater()
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
