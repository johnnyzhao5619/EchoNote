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
Transcript viewer widget for timeline.

Displays transcript text with search and export functionality.
"""

import logging
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QLabel,
    QLineEdit,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ui.base_widgets import BaseWidget, connect_button_with_callback, create_button, create_hbox
from ui.common.theme import ThemeManager
from ui.constants import TIMELINE_SEARCH_NAV_BUTTON_MAX_WIDTH
from utils.i18n import I18nQtManager

logger = logging.getLogger("echonote.ui.timeline.transcript_viewer")


class TranscriptViewer(BaseWidget):
    """
    Transcript viewer widget with search and export.

    Features:
    - Read-only text display
    - Search functionality with highlighting
    - Copy to clipboard
    - Export to file
    """

    # Signals
    export_requested = Signal(str)  # file_path

    def __init__(self, file_path: str, i18n: I18nQtManager, parent: Optional[QWidget] = None):
        """
        Initialize transcript viewer.

        Args:
            file_path: Path to transcript file
            i18n: Internationalization manager
            parent: Parent widget
        """
        super().__init__(i18n, parent)

        self.file_path = file_path
        self.i18n = i18n
        self.transcript_text = ""

        # Search state
        self.search_matches = []
        self.current_match_index = -1

        # Language change handling
        self._language_signal = getattr(self.i18n, "language_changed", None)
        self._language_signal_connected = False
        if self._language_signal is not None:
            self._language_signal.connect(self.update_translations)
            self._language_signal_connected = True
            self.destroyed.connect(self._disconnect_language_signal)

        # Setup UI
        self.setup_ui()

        # Load transcript
        self.load_transcript(file_path)

        logger.info(f"Transcript viewer initialized: {file_path}")

    def setup_ui(self):
        """Set up the viewer UI."""
        layout = QVBoxLayout(self)

        # File name label
        file_name = Path(self.file_path).name
        self.file_label = QLabel(file_name)
        self.file_label.setProperty("role", "transcript-file")
        layout.addWidget(self.file_label)

        # Search bar
        search_layout = create_hbox(spacing=5)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(self.i18n.t("transcript.search_placeholder"))
        self.search_input.returnPressed.connect(self._on_search)
        search_layout.addWidget(self.search_input, stretch=1)

        self.search_button = create_button(self.i18n.t("transcript.search"))
        connect_button_with_callback(self.search_button, self._on_search)
        search_layout.addWidget(self.search_button)

        # Previous/Next match buttons
        self.prev_button = create_button(self.i18n.t("transcript.previous_match_button"))
        self.prev_button.setToolTip(self.i18n.t("transcript.previous_match_tooltip"))
        self.prev_button.setMaximumWidth(TIMELINE_SEARCH_NAV_BUTTON_MAX_WIDTH)
        connect_button_with_callback(self.prev_button, self._on_previous_match)
        self.prev_button.setEnabled(False)
        search_layout.addWidget(self.prev_button)

        self.next_button = create_button(self.i18n.t("transcript.next_match_button"))
        self.next_button.setToolTip(self.i18n.t("transcript.next_match_tooltip"))
        self.next_button.setMaximumWidth(TIMELINE_SEARCH_NAV_BUTTON_MAX_WIDTH)
        connect_button_with_callback(self.next_button, self._on_next_match)
        self.next_button.setEnabled(False)
        search_layout.addWidget(self.next_button)

        self.clear_search_button = create_button(self.i18n.t("transcript.clear_search"))
        connect_button_with_callback(self.clear_search_button, self._on_clear_search)
        search_layout.addWidget(self.clear_search_button)

        layout.addLayout(search_layout)

        # Text display
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setObjectName("timeline_transcript_text")
        # Styling is handled by theme files (dark.qss / light.qss)
        layout.addWidget(self.text_edit)

        # Action buttons
        button_layout = create_hbox(spacing=10)

        self.copy_button = create_button(self.i18n.t("transcript.copy_all"))
        connect_button_with_callback(self.copy_button, self._on_copy_all)
        self.copy_button.setObjectName("timeline_copy_btn")
        # Styling is handled by theme files (dark.qss / light.qss)
        button_layout.addWidget(self.copy_button)

        self.export_button = create_button(self.i18n.t("transcript.export"))
        connect_button_with_callback(self.export_button, self._on_export)
        self.export_button.setObjectName("timeline_export_btn")
        # Styling is handled by theme files (dark.qss / light.qss)
        button_layout.addWidget(self.export_button)

        button_layout.addStretch()

        layout.addLayout(button_layout)

    def load_transcript(self, file_path: str):
        """
        Load transcript from file.

        Args:
            file_path: Path to transcript file
        """
        try:
            # Check if file exists
            if not Path(file_path).exists():
                raise FileNotFoundError(f"Transcript file not found: {file_path}")

            # Read file
            with open(file_path, "r", encoding="utf-8") as f:
                self.transcript_text = f.read()

            # Display text
            self.text_edit.setPlainText(self.transcript_text)

            logger.info(f"Transcript loaded: {file_path}")

        except Exception as e:
            error_msg = f"Failed to load transcript: {e}"
            logger.error(error_msg)
            self.text_edit.setPlainText(self.i18n.t("transcript.load_error") + f"\n\n{error_msg}")

    def _on_search(self):
        """Handle search button click."""
        query = self.search_input.text().strip()

        if not query:
            return

        # Clear previous highlights and matches
        self._clear_highlights()
        self.search_matches = []
        self.current_match_index = -1

        # Search and highlight
        cursor = self.text_edit.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.Start)

        # Highlight format
        highlight_format = QTextCharFormat()
        highlight_format.setBackground(self._get_theme_highlight_color())

        # Find all occurrences and store positions
        while True:
            cursor = self.text_edit.document().find(query, cursor, Qt.FindFlag.FindCaseSensitive)

            if cursor.isNull():
                break

            cursor.mergeCharFormat(highlight_format)
            self.search_matches.append(cursor.position())

        # Enable/disable navigation buttons
        has_matches = len(self.search_matches) > 0
        self.prev_button.setEnabled(has_matches)
        self.next_button.setEnabled(has_matches)

        # Move to first occurrence
        if has_matches:
            self.current_match_index = 0
            self._jump_to_match(0)

        logger.info(f"Search found {len(self.search_matches)} occurrences of '{query}'")

    def _on_previous_match(self):
        """Handle previous match button click."""
        if not self.search_matches:
            return

        self.current_match_index = (self.current_match_index - 1) % len(self.search_matches)
        self._jump_to_match(self.current_match_index)

    def _on_next_match(self):
        """Handle next match button click."""
        if not self.search_matches:
            return

        self.current_match_index = (self.current_match_index + 1) % len(self.search_matches)
        self._jump_to_match(self.current_match_index)

    def _jump_to_match(self, index: int):
        """
        Jump to a specific match.

        Args:
            index: Index of the match to jump to
        """
        if 0 <= index < len(self.search_matches):
            cursor = self.text_edit.textCursor()
            cursor.setPosition(self.search_matches[index])

            # Select the match for visibility
            query = self.search_input.text().strip()
            cursor.movePosition(
                QTextCursor.MoveOperation.Left, QTextCursor.MoveMode.MoveAnchor, len(query)
            )
            cursor.movePosition(
                QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.KeepAnchor, len(query)
            )

            self.text_edit.setTextCursor(cursor)
            self.text_edit.ensureCursorVisible()

    def _on_clear_search(self):
        """Handle clear search button click."""
        self.search_input.clear()
        self._clear_highlights()
        self.search_matches = []
        self.current_match_index = -1
        self.prev_button.setEnabled(False)
        self.next_button.setEnabled(False)

    def _get_theme_highlight_color(self) -> QColor:
        """Get theme-appropriate highlight color for search results."""
        return ThemeManager().get_color("highlight")

    def _clear_highlights(self):
        """Clear all search highlights."""
        cursor = self.text_edit.textCursor()
        cursor.select(QTextCursor.SelectionType.Document)

        # Reset format
        format = QTextCharFormat()
        cursor.setCharFormat(format)

        # Reset cursor position
        cursor.clearSelection()
        self.text_edit.setTextCursor(cursor)

    def _on_copy_all(self):
        """Handle copy all button click."""
        from PySide6.QtWidgets import QApplication

        clipboard = QApplication.clipboard()
        clipboard.setText(self.transcript_text)

        logger.info(self.i18n.t("logging.timeline.transcript_copied_to_clipboard"))

        # Show feedback (could use a toast notification)
        self.copy_button.setText(self.i18n.t("transcript.copied"))

        # Reset button text after 2 seconds
        from PySide6.QtCore import QTimer

        QTimer.singleShot(
            2000, lambda: self.copy_button.setText(self.i18n.t("transcript.copy_all"))
        )

    def _on_export(self):
        """Handle export button click."""
        # Get save file path
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            self.i18n.t("transcript.export_dialog_title"),
            str(Path.home() / "transcript.txt"),
            "Text Files (*.txt);;Markdown Files (*.md);;All Files (*.*)",
        )

        if not file_path:
            return

        try:
            # Write to file
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(self.transcript_text)

            logger.info(f"Transcript exported to: {file_path}")
            self.export_requested.emit(file_path)

            # Show success message
            self.show_info(self.i18n.t("common.success"), self.i18n.t("transcript.export_success"))

        except Exception as e:
            error_msg = f"Failed to export transcript: {e}"
            logger.error(error_msg)

            self.show_error(self.i18n.t("common.error"), error_msg)

    def update_translations(self):
        """Update UI text when language changes."""
        self.search_input.setPlaceholderText(self.i18n.t("transcript.search_placeholder"))
        self.search_button.setText(self.i18n.t("transcript.search"))
        self.clear_search_button.setText(self.i18n.t("transcript.clear_search"))
        self.copy_button.setText(self.i18n.t("transcript.copy_all"))
        self.export_button.setText(self.i18n.t("transcript.export"))
        self.prev_button.setText(self.i18n.t("transcript.previous_match_button"))
        self.prev_button.setToolTip(self.i18n.t("transcript.previous_match_tooltip"))
        self.next_button.setText(self.i18n.t("transcript.next_match_button"))
        self.next_button.setToolTip(self.i18n.t("transcript.next_match_tooltip"))

    def _disconnect_language_signal(self, *args):
        """Disconnect language change signal if connected."""
        if self._language_signal_connected and self._language_signal is not None:
            try:
                self._language_signal.disconnect(self.update_translations)
            except (TypeError, RuntimeError):
                pass
            finally:
                self._language_signal_connected = False

    def closeEvent(self, event):
        """Handle widget close to cleanup signal connections."""
        self._disconnect_language_signal()
        super().closeEvent(event)


class TranscriptViewerDialog(QDialog):
    """Dialog wrapper for transcript viewer."""

    def __init__(
        self,
        file_path: str,
        i18n: I18nQtManager,
        parent: Optional[QWidget] = None,
        *,
        title_key: Optional[str] = None,
    ):
        """
        Initialize transcript viewer dialog.

        Args:
            file_path: Path to transcript file
            i18n: Internationalization manager
            parent: Parent widget
        """
        super().__init__(parent)

        self.i18n = i18n
        self._title_key = title_key or "transcript.viewer_title"

        # Setup dialog
        self.setWindowTitle(i18n.t(self._title_key))
        self.setMinimumSize(600, 500)
        self.setWindowModality(Qt.WindowModality.NonModal)
        self.setModal(False)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)

        # Layout
        layout = QVBoxLayout(self)

        # Transcript viewer
        self.viewer = TranscriptViewer(file_path, i18n, self)
        layout.addWidget(self.viewer)

        # Close button
        button_layout = create_hbox(margins=(10, 0, 10, 10))
        button_layout.addStretch()

        self.close_button = create_button(i18n.t("common.close"))
        connect_button_with_callback(self.close_button, self.close)
        self.close_button.setObjectName("timeline_close_btn")
        button_layout.addWidget(self.close_button)

        layout.addLayout(button_layout)

        logger.info(self.i18n.t("logging.timeline.transcript_viewer_dialog_initialized"))

        # Language change handling
        self._language_signal = getattr(self.i18n, "language_changed", None)
        self._language_signal_connected = False
        if self._language_signal is not None:
            self._language_signal.connect(self.update_translations)
            self._language_signal_connected = True
            self.destroyed.connect(self._disconnect_language_signal)

    def update_translations(self):
        """Update UI text when language changes."""
        self.setWindowTitle(self.i18n.t(self._title_key))
        self.close_button.setText(self.i18n.t("common.close"))

        # Update viewer translations
        if hasattr(self, "viewer"):
            self.viewer.update_translations()

    def _disconnect_language_signal(self, *args):
        """Disconnect language change signal if connected."""
        if self._language_signal_connected and self._language_signal is not None:
            try:
                self._language_signal.disconnect(self.update_translations)
            except (TypeError, RuntimeError):
                pass
            finally:
                self._language_signal_connected = False

    def closeEvent(self, event):
        """Handle dialog close to cleanup signal connections."""
        self._disconnect_language_signal()
        super().closeEvent(event)
