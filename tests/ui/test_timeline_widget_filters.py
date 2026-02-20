# SPDX-License-Identifier: Apache-2.0
"""
Tests for timeline widget filter controls.
"""

from unittest.mock import MagicMock, patch

import pytest

from core.calendar.constants import CalendarSource, EventType
from ui.timeline.widget import TimelineWidget

pytestmark = pytest.mark.ui


@pytest.fixture
def widget(qapp, mock_i18n, mock_settings_manager):
    """Create timeline widget without scheduling async data loading."""
    timeline_manager = MagicMock()
    transcription_manager = MagicMock()
    with patch("ui.timeline.widget.QTimer.singleShot", side_effect=lambda _ms, _cb: None):
        created = TimelineWidget(
            timeline_manager=timeline_manager,
            transcription_manager=transcription_manager,
            i18n=mock_i18n,
            settings_manager=mock_settings_manager,
        )
    return created


def test_filter_options_initialized(widget):
    """Type/source filter options should match expected values."""
    assert widget.search_input.property("role") == "timeline-search-input"
    assert widget.search_button.property("role") == "timeline-search-action"
    assert widget.start_date_edit.property("role") == "timeline-filter-control"
    assert widget.end_date_edit.property("role") == "timeline-filter-control"
    assert widget.type_filter.property("role") == "timeline-filter-control"
    assert widget.source_filter.property("role") == "timeline-filter-control"

    assert widget.type_filter.count() == 4
    assert widget.type_filter.itemData(0) is None
    assert widget.type_filter.itemData(1) == EventType.EVENT
    assert widget.type_filter.itemData(2) == EventType.TASK
    assert widget.type_filter.itemData(3) == EventType.APPOINTMENT

    assert widget.source_filter.count() == 4
    assert widget.source_filter.itemData(0) is None
    assert widget.source_filter.itemData(1) == CalendarSource.LOCAL
    assert widget.source_filter.itemData(2) == CalendarSource.GOOGLE
    assert widget.source_filter.itemData(3) == CalendarSource.OUTLOOK


def test_update_translations_preserves_selected_filters(widget):
    """Language refresh should keep selected filter values unchanged."""
    widget.type_filter.setCurrentIndex(2)
    widget.source_filter.setCurrentIndex(3)

    selected_type = widget.type_filter.currentData()
    selected_source = widget.source_filter.currentData()

    widget.update_translations()

    assert widget.type_filter.currentData() == selected_type
    assert widget.source_filter.currentData() == selected_source
    assert widget.type_filter.itemText(0) == "timeline.filter_all"
    assert widget.source_filter.itemText(0) == "timeline.source_all"


def test_future_cards_insert_farthest_first(widget):
    """未来事件卡片应按最远->最近靠近当前时间线。"""

    def _build_event(event_id: str, start_time: str):
        event = MagicMock()
        event.id = event_id
        event.title = event_id
        event.start_time = start_time
        event.end_time = start_time
        event.event_type = EventType.EVENT
        event.source = CalendarSource.LOCAL
        event.location = None
        event.attendees = []
        event.description = None
        return event

    widget.clear_timeline()
    widget._add_current_time_indicator()

    near_event = _build_event("near", "2026-02-19T11:00:00")
    far_event = _build_event("far", "2026-02-19T14:00:00")

    widget._add_event_card({"event": near_event, "auto_tasks": {}}, is_future=True)
    widget._add_event_card({"event": far_event, "auto_tasks": {}}, is_future=True)

    ordered_ids = [
        card.calendar_event.id for card in widget.event_cards if hasattr(card, "calendar_event")
    ]
    assert ordered_ids[:2] == ["far", "near"]
