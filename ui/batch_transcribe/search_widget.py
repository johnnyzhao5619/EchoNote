# SPDX-License-Identifier: Apache-2.0
#
# Copyright (c) 2024-2025 EchoNote Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
Search widget for transcript viewer.

Provides text search functionality with highlighting, navigation,
and case-sensitive options.
"""

import logging
import re
from typing import List, Optional

from ui.base_widgets import BaseWidget, create_button
from ui.constants import (
    LARGE_DOCUMENT_THRESHOLD,
    SEARCH_DEBOUNCE_DELAY_MS,
    SEARCH_INPUT_MIN_WIDTH,
    SEARCH_MATCH_LABEL_MIN_WIDTH,
)
from ui.qt_imports import (
    QCheckBox,
    QColor,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    Qt,
    QTextCursor,
    QTextDocument,
    QTextEdit,
    QTimer,
    QWidget,
    Signal,
)
from ui.signal_helpers import (
    connect_button_with_callback,
    connect_text_changed,
)
from utils.i18n import I18nQtManager
from ui.common.theme import ThemeManager

logger = logging.getLogger("echonote.ui.search_widget")

SEARCH_ROLE_NAV_BUTTON = "search-nav-action"
SEARCH_ROLE_CLOSE_BUTTON = "search-close-action"


class SearchWidget(BaseWidget):
    """
    Search widget for finding and highlighting text in QTextEdit.

    Features:
    - Real-time search with highlighting
    - Case-sensitive option
    - Navigation between matches
    - Match count display
    - Keyboard shortcuts (Enter, Shift+Enter, Esc)
    """

    # Signal emitted when widget should be closed
    close_requested = Signal()

    def __init__(
        self,
        text_edit: QTextEdit,
        i18n: I18nQtManager,
        settings_manager=None,
        parent: Optional[QWidget] = None,
    ):
        """
        Initialize search widget.

        Args:
            text_edit: The QTextEdit to search in
            i18n: Internationalization manager
            settings_manager: Settings manager for search behavior preferences
            parent: Parent widget
        """
        super().__init__(i18n, parent)

        self.text_edit = text_edit
        self.i18n = i18n
        self.settings_manager = settings_manager

        # Search state
        self.matches: List[QTextCursor] = []
        self.current_match = -1
        self.match_count = 0

        # Search cache for performance
        self._search_cache = {}  # {(query, case_sensitive): matches}
        self._last_query = ""
        self._last_case_sensitive = False

        # Debounce timer for incremental search
        self._search_timer = QTimer()
        self._search_timer.setSingleShot(True)
        self._search_timer.timeout.connect(self._perform_search)
        # Get debounce delay from settings or use default
        if self.settings_manager:
            self._search_delay_ms = (
                self.settings_manager.get_setting("ui.search_debounce_ms")
                or SEARCH_DEBOUNCE_DELAY_MS
            )
        else:
            self._search_delay_ms = SEARCH_DEBOUNCE_DELAY_MS

        # Initialize UI
        self._init_ui()

        # Connect i18n signals
        self.i18n.language_changed.connect(self.update_language)

        # Apply initial translations
        self.update_language()

        # Hide by default
        self.hide()

        logger.debug("SearchWidget initialized")

    def _init_ui(self):
        """Initialize the user interface."""
        # Set object name for styling
        self.setObjectName("search_widget")

        # Main layout
        layout = QHBoxLayout(self)

        # Search input
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(self.i18n.t("viewer.search_placeholder"))
        self.search_input.setClearButtonEnabled(True)

        self.search_input.setMinimumWidth(SEARCH_INPUT_MIN_WIDTH)

        # Connect search input signals
        connect_text_changed(self.search_input, self._on_search_text_changed)
        self.search_input.returnPressed.connect(self.find_next)

        layout.addWidget(self.search_input)

        # Case-sensitive checkbox
        self.case_sensitive_checkbox = QCheckBox()
        self.case_sensitive_checkbox.stateChanged.connect(self._on_case_sensitive_changed)
        layout.addWidget(self.case_sensitive_checkbox)

        # Previous button
        self.prev_button = create_button(self.i18n.t("search.previous"))
        self.prev_button.setProperty("role", SEARCH_ROLE_NAV_BUTTON)
        self.prev_button.setToolTip(self.i18n.t("search.previous"))
        connect_button_with_callback(self.prev_button, self.find_previous)
        layout.addWidget(self.prev_button)

        # Next button
        self.next_button = create_button(self.i18n.t("search.next"))
        self.next_button.setProperty("role", SEARCH_ROLE_NAV_BUTTON)
        self.next_button.setToolTip(self.i18n.t("search.next"))
        connect_button_with_callback(self.next_button, self.find_next)
        layout.addWidget(self.next_button)

        # Match count label
        self.match_label = QLabel()
        self.match_label.setMinimumWidth(SEARCH_MATCH_LABEL_MIN_WIDTH)
        layout.addWidget(self.match_label)

        # Close button
        self.close_button = create_button(self.i18n.t("search.close"))
        self.close_button.setProperty("role", SEARCH_ROLE_CLOSE_BUTTON)
        self.close_button.setToolTip(self.i18n.t("search.close"))
        connect_button_with_callback(self.close_button, self._on_close_clicked)
        layout.addWidget(self.close_button)

        layout.addStretch()

        logger.debug("SearchWidget UI initialized")

    def show_search(self):
        """Show the search widget and focus the input."""
        self.show()
        self.search_input.setFocus()
        self.search_input.selectAll()
        logger.debug("Search widget shown")

    def hide_search(self):
        """Hide the search widget and clear highlights."""
        self.hide()
        self.clear_highlights()
        self.search_input.clear()
        logger.debug("Search widget hidden")

    def keyPressEvent(self, event):
        """Handle key press events."""
        if event.key() == Qt.Key.Key_Escape:
            # Esc key closes search
            self.hide_search()
            self.close_requested.emit()
        elif event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
            # Enter/Return navigates to next match
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                self.find_previous()
            else:
                self.find_next()
        else:
            super().keyPressEvent(event)

    def _on_search_text_changed(self, text: str):
        """
        Handle search text change with debouncing for incremental search.

        Args:
            text: New search text
        """
        # Stop any pending search
        self._search_timer.stop()

        if text:
            # Start debounce timer for incremental search
            self._search_timer.start(self._search_delay_ms)
        else:
            self.clear_highlights()
            self._update_match_label()

    def _perform_search(self):
        """Perform the actual search (called after debounce delay)."""
        query = self.search_input.text()
        if query:
            self.search(query)

    def _on_case_sensitive_changed(self, state: int):
        """
        Handle case-sensitive checkbox state change.

        Args:
            state: Checkbox state
        """
        # Stop any pending search
        self._search_timer.stop()

        # Re-run search immediately with new case sensitivity
        query = self.search_input.text()
        if query:
            self.search(query)

    def _on_close_clicked(self):
        """Handle close button click."""
        self.hide_search()
        self.close_requested.emit()

    def search(self, query: str):
        """
        Search for query in text edit and highlight matches.
        Uses regex for better performance and caching for repeated searches.

        Args:
            query: Search query string
        """
        if not query:
            self.clear_highlights()
            return

        case_sensitive = self.case_sensitive_checkbox.isChecked()

        # Check cache first
        cache_key = (query, case_sensitive)
        if cache_key == (self._last_query, self._last_case_sensitive):
            # Same search, use cached results
            logger.debug(f"Using cached search results for: {query}")
            if self.matches:
                self.current_match = 0
                self._jump_to_current_match()
            self._update_match_label()
            return

        logger.debug(f"Searching for: {query}")

        # Clear previous search
        self.clear_highlights()
        self.matches = []
        self.current_match = -1

        # Use optimized regex search for large documents
        content = self.text_edit.toPlainText()

        # For very large documents, use regex for better performance
        if len(content) > LARGE_DOCUMENT_THRESHOLD:
            self.matches = self._regex_search(query, content, case_sensitive)
        else:
            # For smaller documents, use Qt's built-in search
            self.matches = self._qt_search(query, case_sensitive)

        self.match_count = len(self.matches)

        # Update cache
        self._last_query = query
        self._last_case_sensitive = case_sensitive

        logger.debug(f"Found {self.match_count} matches")

        # Highlight all matches
        if self.matches:
            self.highlight_matches()
            self.current_match = 0
            self._jump_to_current_match()

        # Update match count display
        self._update_match_label()

    def _qt_search(self, query: str, case_sensitive: bool) -> List[QTextCursor]:
        """
        Search using Qt's built-in document search.

        Args:
            query: Search query
            case_sensitive: Whether search is case-sensitive

        Returns:
            List of QTextCursor objects for matches
        """
        matches = []
        document = self.text_edit.document()

        # Set up find flags
        flags = QTextDocument.FindFlag(0)
        if case_sensitive:
            flags |= QTextDocument.FindFlag.FindCaseSensitively

        # Find all matches
        cursor = QTextCursor(document)
        while True:
            cursor = document.find(query, cursor, flags)
            if cursor.isNull():
                break
            matches.append(QTextCursor(cursor))

        return matches

    def _regex_search(self, query: str, content: str, case_sensitive: bool) -> List[QTextCursor]:
        """
        Search using regex for better performance on large documents.

        Args:
            query: Search query
            content: Document content
            case_sensitive: Whether search is case-sensitive

        Returns:
            List of QTextCursor objects for matches
        """
        matches = []

        try:
            # Escape special regex characters in query
            pattern = re.escape(query)

            # Compile regex with appropriate flags
            flags = 0 if case_sensitive else re.IGNORECASE
            regex = re.compile(pattern, flags)

            # Find all matches
            document = self.text_edit.document()

            for match in regex.finditer(content):
                # Create cursor for this match
                cursor = QTextCursor(document)
                cursor.setPosition(match.start())
                cursor.setPosition(match.end(), QTextCursor.MoveMode.KeepAnchor)
                matches.append(cursor)

        except re.error as e:
            logger.error(f"Regex search error: {e}")
            # Fall back to Qt search
            return self._qt_search(query, case_sensitive)

        return matches

    def highlight_matches(self):
        """Highlight all search matches in the text edit."""
        if not self.matches:
            return

        extra_selections = []

        # Determine highlight color based on theme
        highlight_color = self._get_highlight_color()

        for cursor in self.matches:
            selection = QTextEdit.ExtraSelection()
            selection.cursor = cursor
            selection.format.setBackground(highlight_color)
            extra_selections.append(selection)

        self.text_edit.setExtraSelections(extra_selections)
        logger.debug(f"Highlighted {len(self.matches)} matches")

    def _get_highlight_color(self) -> QColor:
        """
        Get highlight color from ThemeManager.

        Returns:
            QColor for highlighting matches
        """
        return ThemeManager().get_color("highlight")

    def update_highlight_color(self):
        """
        Update highlight colors when theme changes.

        Re-applies highlights with the new theme's color if there are
        active search matches.
        """
        if self.matches:
            # Re-highlight with new color
            self.highlight_matches()
            logger.debug("Updated highlight colors for theme change")

    def clear_highlights(self):
        """Clear all search highlights and cache."""
        self.text_edit.setExtraSelections([])
        self.matches = []
        self.current_match = -1
        self.match_count = 0

        # Clear cache
        self._last_query = ""
        self._last_case_sensitive = False

        logger.debug("Cleared highlights and cache")

    def find_next(self):
        """Navigate to the next search match."""
        if not self.matches:
            logger.debug("No matches to navigate")
            return

        self.current_match = (self.current_match + 1) % self.match_count
        self._jump_to_current_match()
        self._update_match_label()

        logger.debug(f"Navigated to match {self.current_match + 1}/{self.match_count}")

    def find_previous(self):
        """Navigate to the previous search match."""
        if not self.matches:
            logger.debug("No matches to navigate")
            return

        self.current_match = (self.current_match - 1) % self.match_count
        self._jump_to_current_match()
        self._update_match_label()

        logger.debug(f"Navigated to match {self.current_match + 1}/{self.match_count}")

    def _jump_to_current_match(self):
        """Jump to the current match and ensure it's visible."""
        if 0 <= self.current_match < len(self.matches):
            cursor = self.matches[self.current_match]
            self.text_edit.setTextCursor(cursor)
            self.text_edit.ensureCursorVisible()

    def _update_match_label(self):
        """Update the match count label."""
        if self.match_count > 0:
            # Will be translated in update_language()
            self.match_label.setText(
                self.i18n.t(
                    "viewer.match_count", current=self.current_match + 1, total=self.match_count
                )
            )
        elif self.search_input.text():
            # No matches found
            self.match_label.setText(self.i18n.t("viewer.no_matches"))
        else:
            # No search query
            self.match_label.setText("")

    def update_language(self):
        """Update UI text with current language translations."""
        # Search input placeholder
        self.search_input.setPlaceholderText(self.i18n.t("viewer.search_placeholder"))

        # Case-sensitive checkbox
        self.case_sensitive_checkbox.setText(self.i18n.t("viewer.case_sensitive"))
        self.prev_button.setText(self.i18n.t("search.previous"))
        self.next_button.setText(self.i18n.t("search.next"))
        self.close_button.setText(self.i18n.t("search.close"))
        self.prev_button.setToolTip(self.i18n.t("search.previous"))
        self.next_button.setToolTip(self.i18n.t("search.next"))
        self.close_button.setToolTip(self.i18n.t("search.close"))

        # Update match label
        self._update_match_label()

        logger.debug("SearchWidget language updated")
