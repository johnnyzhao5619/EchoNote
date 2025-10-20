import pytest

PyQt6 = pytest.importorskip("PyQt6")
from PyQt6.QtWidgets import QApplication, QLabel

from data.database.models import CalendarEvent
from ui.timeline.event_card import EventCard
from utils.i18n import I18nQtManager
from core.timeline.manager import to_local_naive


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


def test_event_card_time_label_handles_z_suffix(qapp):
    i18n = I18nQtManager(default_language="en_US")
    event = CalendarEvent(
        id="event-123",
        title="Test Event",
        event_type="Meeting",
        start_time="2024-01-01T10:00:00Z",
        end_time="2024-01-01T11:30:00Z",
        source="local",
    )

    event_data = {
        "event": event,
        "source_colors": {"local": "#2196F3"},
    }

    card = EventCard(event_data, is_future=False, i18n=i18n)

    try:
        time_label = card.findChild(QLabel, "time_label")
        assert time_label is not None

        expected_start = to_local_naive(event.start_time)
        expected_end = to_local_naive(event.end_time)
        expected_text = (
            f"{expected_start.strftime('%Y-%m-%d %H:%M')} - "
            f"{expected_end.strftime('%H:%M')}"
        )

        assert time_label.text() == expected_text
    finally:
        card.deleteLater()
        qapp.processEvents()


def test_event_card_badges_update_with_language_change(qapp):
    i18n = I18nQtManager(default_language="en_US")
    event = CalendarEvent(
        id="event-456",
        title="Badge Event",
        event_type="Event",
        start_time="2024-01-02T09:00:00Z",
        end_time="2024-01-02T10:00:00Z",
        source="google",
    )

    event_data = {
        "event": event,
        "source_colors": {"google": "#EA4335"},
    }

    card = EventCard(event_data, is_future=False, i18n=i18n)

    try:
        type_badge = card.findChild(QLabel, "type_badge")
        source_badge = card.findChild(QLabel, "source_badge")

        assert type_badge is not None
        assert source_badge is not None

        assert type_badge.text() == i18n.t("timeline.filter_event")
        assert source_badge.text() == i18n.t("timeline.source_google")

        i18n.change_language("zh_CN")
        card.update_translations()

        assert type_badge.text() == i18n.t("timeline.filter_event")
        assert source_badge.text() == i18n.t("timeline.source_google")
    finally:
        card.deleteLater()
        qapp.processEvents()
