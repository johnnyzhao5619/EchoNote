"""
Transcript viewer widget for timeline.

Displays transcript text with search and export functionality.
"""

import logging
from typing import Optional
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit,
    QPushButton, QLineEdit, QLabel, QDialog,
    QFileDialog, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QTextCursor, QTextCharFormat, QColor

from utils.i18n import I18nQtManager


logger = logging.getLogger('echonote.ui.timeline.transcript_viewer')


class TranscriptViewer(QWidget):
    """
    Transcript viewer widget with search and export.
    
    Features:
    - Read-only text display
    - Search functionality with highlighting
    - Copy to clipboard
    - Export to file
    """
    
    # Signals
    export_requested = pyqtSignal(str)  # file_path
    
    def __init__(
        self,
        file_path: str,
        i18n: I18nQtManager,
        parent: Optional[QWidget] = None
    ):
        """
        Initialize transcript viewer.
        
        Args:
            file_path: Path to transcript file
            i18n: Internationalization manager
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.file_path = file_path
        self.i18n = i18n
        self.transcript_text = ""
        
        # Search state
        self.search_matches = []
        self.current_match_index = -1
        
        # Setup UI
        self.setup_ui()
        
        # Load transcript
        self.load_transcript(file_path)
        
        logger.info(f"Transcript viewer initialized: {file_path}")
    
    def setup_ui(self):
        """Set up the viewer UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # File name label
        file_name = Path(self.file_path).name
        self.file_label = QLabel(file_name)
        self.file_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        layout.addWidget(self.file_label)
        
        # Search bar
        search_layout = QHBoxLayout()
        search_layout.setSpacing(5)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(
            self.i18n.t('transcript.search_placeholder')
        )
        self.search_input.returnPressed.connect(self._on_search)
        search_layout.addWidget(self.search_input, stretch=1)
        
        self.search_button = QPushButton(self.i18n.t('transcript.search'))
        self.search_button.clicked.connect(self._on_search)
        search_layout.addWidget(self.search_button)
        
        # Previous/Next match buttons
        self.prev_button = QPushButton(
            self.i18n.t('transcript.previous_match_button')
        )
        self.prev_button.setToolTip(
            self.i18n.t('transcript.previous_match_tooltip')
        )
        self.prev_button.setMaximumWidth(40)
        self.prev_button.clicked.connect(self._on_previous_match)
        self.prev_button.setEnabled(False)
        search_layout.addWidget(self.prev_button)

        self.next_button = QPushButton(
            self.i18n.t('transcript.next_match_button')
        )
        self.next_button.setToolTip(
            self.i18n.t('transcript.next_match_tooltip')
        )
        self.next_button.setMaximumWidth(40)
        self.next_button.clicked.connect(self._on_next_match)
        self.next_button.setEnabled(False)
        search_layout.addWidget(self.next_button)
        
        self.clear_search_button = QPushButton(
            self.i18n.t('transcript.clear_search')
        )
        self.clear_search_button.clicked.connect(self._on_clear_search)
        search_layout.addWidget(self.clear_search_button)
        
        layout.addLayout(search_layout)
        
        # Text display
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setObjectName("timeline_transcript_text")
        # Styling is handled by theme files (dark.qss / light.qss)
        layout.addWidget(self.text_edit)
        
        # Action buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        
        self.copy_button = QPushButton(self.i18n.t('transcript.copy_all'))
        self.copy_button.clicked.connect(self._on_copy_all)
        self.copy_button.setObjectName("timeline_copy_btn")
        # Styling is handled by theme files (dark.qss / light.qss)
        button_layout.addWidget(self.copy_button)
        
        self.export_button = QPushButton(self.i18n.t('transcript.export'))
        self.export_button.clicked.connect(self._on_export)
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
                raise FileNotFoundError(
                    f"Transcript file not found: {file_path}"
                )
            
            # Read file
            with open(file_path, 'r', encoding='utf-8') as f:
                self.transcript_text = f.read()
            
            # Display text
            self.text_edit.setPlainText(self.transcript_text)
            
            logger.info(f"Transcript loaded: {file_path}")
            
        except Exception as e:
            error_msg = f"Failed to load transcript: {e}"
            logger.error(error_msg)
            self.text_edit.setPlainText(
                self.i18n.t('transcript.load_error') + f"\n\n{error_msg}"
            )
    
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
        highlight_format.setBackground(QColor("#FFEB3B"))
        
        # Find all occurrences and store positions
        while True:
            cursor = self.text_edit.document().find(
                query, cursor, Qt.FindFlag.FindCaseSensitive
            )
            
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
        
        logger.info(
            f"Search found {len(self.search_matches)} occurrences of '{query}'"
        )
    
    def _on_previous_match(self):
        """Handle previous match button click."""
        if not self.search_matches:
            return
        
        self.current_match_index = (
            (self.current_match_index - 1) % len(self.search_matches)
        )
        self._jump_to_match(self.current_match_index)
    
    def _on_next_match(self):
        """Handle next match button click."""
        if not self.search_matches:
            return
        
        self.current_match_index = (
            (self.current_match_index + 1) % len(self.search_matches)
        )
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
                QTextCursor.MoveOperation.Left,
                QTextCursor.MoveMode.MoveAnchor,
                len(query)
            )
            cursor.movePosition(
                QTextCursor.MoveOperation.Right,
                QTextCursor.MoveMode.KeepAnchor,
                len(query)
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
        from PyQt6.QtWidgets import QApplication
        
        clipboard = QApplication.clipboard()
        clipboard.setText(self.transcript_text)
        
        logger.info("Transcript copied to clipboard")
        
        # Show feedback (could use a toast notification)
        self.copy_button.setText(self.i18n.t('transcript.copied'))
        
        # Reset button text after 2 seconds
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(2000, lambda: self.copy_button.setText(
            self.i18n.t('transcript.copy_all')
        ))
    
    def _on_export(self):
        """Handle export button click."""
        # Get save file path
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            self.i18n.t('transcript.export_dialog_title'),
            str(Path.home() / "transcript.txt"),
            "Text Files (*.txt);;Markdown Files (*.md);;All Files (*.*)"
        )
        
        if not file_path:
            return
        
        try:
            # Write to file
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(self.transcript_text)
            
            logger.info(f"Transcript exported to: {file_path}")
            self.export_requested.emit(file_path)
            
            # Show success message
            QMessageBox.information(
                self,
                self.i18n.t('common.success'),
                self.i18n.t('transcript.export_success')
            )
            
        except Exception as e:
            error_msg = f"Failed to export transcript: {e}"
            logger.error(error_msg)
            
            QMessageBox.critical(
                self,
                self.i18n.t('common.error'),
                error_msg
            )
    
    def update_translations(self):
        """Update UI text when language changes."""
        self.search_input.setPlaceholderText(
            self.i18n.t('transcript.search_placeholder')
        )
        self.search_button.setText(self.i18n.t('transcript.search'))
        self.clear_search_button.setText(
            self.i18n.t('transcript.clear_search')
        )
        self.copy_button.setText(self.i18n.t('transcript.copy_all'))
        self.export_button.setText(self.i18n.t('transcript.export'))
        self.prev_button.setText(
            self.i18n.t('transcript.previous_match_button')
        )
        self.prev_button.setToolTip(
            self.i18n.t('transcript.previous_match_tooltip')
        )
        self.next_button.setText(
            self.i18n.t('transcript.next_match_button')
        )
        self.next_button.setToolTip(
            self.i18n.t('transcript.next_match_tooltip')
        )


class TranscriptViewerDialog(QDialog):
    """Dialog wrapper for transcript viewer."""
    
    def __init__(
        self,
        file_path: str,
        i18n: I18nQtManager,
        parent: Optional[QWidget] = None
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
        
        # Setup dialog
        self.setWindowTitle(i18n.t('transcript.viewer_title'))
        self.setMinimumSize(600, 500)
        self.setModal(False)
        
        # Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Transcript viewer
        self.viewer = TranscriptViewer(file_path, i18n, self)
        layout.addWidget(self.viewer)
        
        # Close button
        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(10, 0, 10, 10)
        button_layout.addStretch()
        
        self.close_button = QPushButton(i18n.t('common.close'))
        self.close_button.clicked.connect(self.close)
        self.close_button.setObjectName("timeline_close_btn")
        button_layout.addWidget(self.close_button)
        
        layout.addLayout(button_layout)
        
        logger.info("Transcript viewer dialog initialized")
    
    def update_translations(self):
        """Update UI text when language changes."""
        self.setWindowTitle(self.i18n.t('transcript.viewer_title'))
        self.close_button.setText(self.i18n.t('common.close'))
        
        # Update viewer translations
        if hasattr(self, 'viewer'):
            self.viewer.update_translations()
