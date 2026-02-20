# SPDX-License-Identifier: Apache-2.0
"""
Tests for batch transcript search widget semantic style hooks.
"""

import pytest
from PySide6.QtWidgets import QTextEdit

from ui.batch_transcribe.search_widget import SearchWidget

pytestmark = pytest.mark.ui


def test_search_widget_buttons_use_semantic_roles(qapp, mock_i18n):
    """Search widget buttons should expose semantic roles for unified styling."""
    widget = SearchWidget(text_edit=QTextEdit(), i18n=mock_i18n)

    assert widget.prev_button.property("role") == "search-nav-action"
    assert widget.next_button.property("role") == "search-nav-action"
    assert widget.close_button.property("role") == "search-close-action"
