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
"""Reusable transcript/translation viewer with compare mode."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from core.qt_imports import (
    QButtonGroup,
    QDialog,
    QFileDialog,
    QLabel,
    QLineEdit,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QTextCharFormat,
    QTextCursor,
    QTextEdit,
    Qt,
    QVBoxLayout,
    QWidget,
)
from ui.base_widgets import BaseWidget, connect_button_with_callback, create_button, create_hbox
from ui.common.theme import ThemeManager
from ui.constants import (
    ROLE_DIALOG_NAV_ACTION,
    ROLE_DIALOG_PRIMARY_ACTION,
    ROLE_DIALOG_SECONDARY_ACTION,
    ROLE_TIMELINE_COPY_ACTION,
    ROLE_TIMELINE_EXPORT_ACTION,
    ROLE_TRANSCRIPT_FILE,
    TIMELINE_DIALOG_BUTTON_MARGINS,
    TIMELINE_SEARCH_NAV_BUTTON_MAX_WIDTH,
    TIMELINE_TRANSCRIPT_DIALOG_MIN_HEIGHT,
    TIMELINE_TRANSCRIPT_DIALOG_MIN_WIDTH,
    TIMELINE_VIEWER_ACTION_ROW_SPACING,
    TIMELINE_VIEWER_SEARCH_ROW_SPACING,
)
from utils.i18n import I18nQtManager

logger = logging.getLogger("echonote.ui.common.transcript_translation_viewer")


VIEW_MODE_TRANSCRIPT = "transcript"
VIEW_MODE_TRANSLATION = "translation"
VIEW_MODE_COMPARE = "compare"


class TranscriptTranslationViewer(BaseWidget):
    """Display transcript/translation text in single or compare mode."""

    def __init__(
        self,
        i18n: I18nQtManager,
        *,
        transcript_path: Optional[str] = None,
        translation_path: Optional[str] = None,
        initial_mode: str = VIEW_MODE_TRANSCRIPT,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(i18n, parent)
        self.i18n = i18n
        self.transcript_path = transcript_path
        self.translation_path = translation_path
        self.transcript_text = ""
        self.translation_text = ""
        self._active_mode = VIEW_MODE_TRANSCRIPT
        self._search_matches: list[tuple[QTextEdit, int]] = []
        self._search_query = ""
        self._current_match_index = -1
        self._initial_mode = initial_mode
        self._mode_buttons: dict[str, QPushButton] = {}
        self._mode_button_group: Optional[QButtonGroup] = None

        self.setup_ui()
        self._load_all_text()
        self._apply_available_modes()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        self.file_label = QLabel("")
        self.file_label.setProperty("role", ROLE_TRANSCRIPT_FILE)
        layout.addWidget(self.file_label)

        mode_layout = create_hbox(spacing=TIMELINE_VIEWER_SEARCH_ROW_SPACING)
        self.mode_caption = QLabel(self.i18n.t("viewer.view_mode"))
        mode_layout.addWidget(self.mode_caption)

        self._mode_button_group = QButtonGroup(self)
        self._mode_button_group.setExclusive(True)
        mode_definitions = (
            (VIEW_MODE_TRANSCRIPT, "viewer.mode_transcript"),
            (VIEW_MODE_TRANSLATION, "viewer.mode_translation"),
            (VIEW_MODE_COMPARE, "viewer.mode_compare"),
        )
        for mode, label_key in mode_definitions:
            button = create_button(self.i18n.t(label_key))
            button.setCheckable(True)
            button.setProperty("role", ROLE_DIALOG_NAV_ACTION)
            connect_button_with_callback(
                button,
                lambda _checked=False, selected_mode=mode: self._on_mode_button_clicked(
                    selected_mode
                ),
            )
            self._mode_button_group.addButton(button)
            self._mode_buttons[mode] = button
            mode_layout.addWidget(button)
        mode_layout.addStretch()
        layout.addLayout(mode_layout)

        search_layout = create_hbox(spacing=TIMELINE_VIEWER_SEARCH_ROW_SPACING)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(self.i18n.t("transcript.search_placeholder"))
        self.search_input.returnPressed.connect(self._on_search)
        search_layout.addWidget(self.search_input, stretch=1)

        self.search_button = create_button(self.i18n.t("transcript.search"))
        self.search_button.setProperty("role", ROLE_DIALOG_SECONDARY_ACTION)
        connect_button_with_callback(self.search_button, self._on_search)
        search_layout.addWidget(self.search_button)

        self.prev_button = create_button(self.i18n.t("transcript.previous_match_button"))
        self.prev_button.setProperty("role", ROLE_DIALOG_NAV_ACTION)
        self.prev_button.setMaximumWidth(TIMELINE_SEARCH_NAV_BUTTON_MAX_WIDTH)
        self.prev_button.setEnabled(False)
        connect_button_with_callback(self.prev_button, self._on_previous_match)
        search_layout.addWidget(self.prev_button)

        self.next_button = create_button(self.i18n.t("transcript.next_match_button"))
        self.next_button.setProperty("role", ROLE_DIALOG_NAV_ACTION)
        self.next_button.setMaximumWidth(TIMELINE_SEARCH_NAV_BUTTON_MAX_WIDTH)
        self.next_button.setEnabled(False)
        connect_button_with_callback(self.next_button, self._on_next_match)
        search_layout.addWidget(self.next_button)

        self.clear_search_button = create_button(self.i18n.t("transcript.clear_search"))
        self.clear_search_button.setProperty("role", ROLE_DIALOG_SECONDARY_ACTION)
        connect_button_with_callback(self.clear_search_button, self._on_clear_search)
        search_layout.addWidget(self.clear_search_button)
        layout.addLayout(search_layout)

        self.content_stack = QStackedWidget()

        self.single_text_edit = QTextEdit()
        self.single_text_edit.setReadOnly(True)
        self.single_text_edit.setObjectName("timeline_transcript_text")
        self.content_stack.addWidget(self.single_text_edit)

        compare_widget = QWidget()
        compare_layout = QVBoxLayout(compare_widget)
        compare_layout.setContentsMargins(0, 0, 0, 0)
        compare_splitter = QSplitter(Qt.Orientation.Horizontal)

        left_container = QWidget()
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(0, 0, 0, 0)
        self.compare_left_title = QLabel(self.i18n.t("viewer.mode_transcript"))
        left_layout.addWidget(self.compare_left_title)
        self.compare_left_text = QTextEdit()
        self.compare_left_text.setReadOnly(True)
        left_layout.addWidget(self.compare_left_text, stretch=1)

        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        self.compare_right_title = QLabel(self.i18n.t("viewer.mode_translation"))
        right_layout.addWidget(self.compare_right_title)
        self.compare_right_text = QTextEdit()
        self.compare_right_text.setReadOnly(True)
        right_layout.addWidget(self.compare_right_text, stretch=1)

        compare_splitter.addWidget(left_container)
        compare_splitter.addWidget(right_container)
        compare_splitter.setChildrenCollapsible(False)
        compare_layout.addWidget(compare_splitter, stretch=1)
        self.content_stack.addWidget(compare_widget)

        layout.addWidget(self.content_stack, stretch=1)

        button_layout = create_hbox(spacing=TIMELINE_VIEWER_ACTION_ROW_SPACING)
        self.copy_button = create_button(self.i18n.t("transcript.copy_all"))
        self.copy_button.setProperty("role", ROLE_TIMELINE_COPY_ACTION)
        connect_button_with_callback(self.copy_button, self._on_copy_all)
        button_layout.addWidget(self.copy_button)

        self.export_button = create_button(self.i18n.t("transcript.export"))
        self.export_button.setProperty("role", ROLE_TIMELINE_EXPORT_ACTION)
        connect_button_with_callback(self.export_button, self._on_export)
        button_layout.addWidget(self.export_button)

        button_layout.addStretch()
        layout.addLayout(button_layout)

    def _read_text_file(self, path: Optional[str], *, missing_message: str) -> str:
        if not path:
            return ""
        try:
            file_path = Path(path)
            if not file_path.exists():
                return missing_message
            return file_path.read_text(encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to read text file %s: %s", path, exc)
            return missing_message

    def _load_all_text(self) -> None:
        self.transcript_text = self._read_text_file(
            self.transcript_path,
            missing_message=self.i18n.t("viewer.file_not_found"),
        )
        self.translation_text = self._read_text_file(
            self.translation_path,
            missing_message=self.i18n.t("viewer.file_not_found"),
        )
        self.compare_left_text.setPlainText(self.transcript_text)
        self.compare_right_text.setPlainText(self.translation_text)

    def _available_modes(self) -> list[str]:
        modes: list[str] = []
        if self.transcript_path:
            modes.append(VIEW_MODE_TRANSCRIPT)
        if self.translation_path:
            modes.append(VIEW_MODE_TRANSLATION)
        if self.transcript_path and self.translation_path:
            modes.append(VIEW_MODE_COMPARE)
        if not modes:
            modes.append(VIEW_MODE_TRANSCRIPT)
        return modes

    def _apply_available_modes(self) -> None:
        available_modes = self._available_modes()
        selected_mode = self._initial_mode if self._initial_mode in available_modes else available_modes[0]
        show_mode_switch = len(available_modes) > 1
        self.mode_caption.setVisible(show_mode_switch)

        for mode, button in self._mode_buttons.items():
            is_available = mode in available_modes
            button.setVisible(show_mode_switch and is_available)
            button.setEnabled(is_available)
            button.setChecked(mode == selected_mode)

        self.set_view_mode(selected_mode)

    def set_view_mode(self, mode: str) -> None:
        if mode == VIEW_MODE_TRANSLATION and not self.translation_path:
            mode = VIEW_MODE_TRANSCRIPT
        if mode == VIEW_MODE_COMPARE and not (self.transcript_path and self.translation_path):
            mode = VIEW_MODE_TRANSCRIPT

        self._active_mode = mode
        if mode == VIEW_MODE_COMPARE:
            self.content_stack.setCurrentIndex(1)
        else:
            self.content_stack.setCurrentIndex(0)
            text = self.transcript_text
            if mode == VIEW_MODE_TRANSLATION:
                text = self.translation_text
            self.single_text_edit.setPlainText(text)
        self._update_file_label()
        self._on_clear_search()

        for button_mode, button in self._mode_buttons.items():
            should_check = button_mode == self._active_mode
            if button.isChecked() != should_check:
                button.setChecked(should_check)

    def _update_file_label(self) -> None:
        transcript_name = Path(self.transcript_path).name if self.transcript_path else "-"
        translation_name = Path(self.translation_path).name if self.translation_path else "-"

        if self._active_mode == VIEW_MODE_COMPARE:
            self.file_label.setText(
                self.i18n.t(
                    "viewer.compare_file_label",
                    transcript=transcript_name,
                    translation=translation_name,
                )
            )
        elif self._active_mode == VIEW_MODE_TRANSLATION:
            self.file_label.setText(translation_name)
        else:
            self.file_label.setText(transcript_name)

    def _on_mode_button_clicked(self, mode: str) -> None:
        self.set_view_mode(mode)

    def _get_active_editors(self) -> list[QTextEdit]:
        if self._active_mode == VIEW_MODE_COMPARE:
            return [self.compare_left_text, self.compare_right_text]
        return [self.single_text_edit]

    def _clear_highlights(self) -> None:
        for editor in self._get_active_editors():
            cursor = editor.textCursor()
            cursor.select(QTextCursor.SelectionType.Document)
            fmt = QTextCharFormat()
            cursor.setCharFormat(fmt)
            cursor.clearSelection()
            editor.setTextCursor(cursor)

    def _on_search(self) -> None:
        query = self.search_input.text().strip()
        if not query:
            return

        self._clear_highlights()
        self._search_matches = []
        self._current_match_index = -1
        self._search_query = query

        highlight_format = QTextCharFormat()
        highlight_format.setBackground(ThemeManager().get_color("highlight"))

        for editor in self._get_active_editors():
            cursor = editor.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.Start)
            while True:
                cursor = editor.document().find(query, cursor, Qt.FindFlag.FindCaseSensitive)
                if cursor.isNull():
                    break
                cursor.mergeCharFormat(highlight_format)
                self._search_matches.append((editor, cursor.position()))

        has_matches = bool(self._search_matches)
        self.prev_button.setEnabled(has_matches)
        self.next_button.setEnabled(has_matches)
        if has_matches:
            self._current_match_index = 0
            self._jump_to_match(0)

    def _jump_to_match(self, index: int) -> None:
        if not (0 <= index < len(self._search_matches)):
            return

        editor, end_pos = self._search_matches[index]
        cursor = editor.textCursor()
        cursor.setPosition(max(end_pos - len(self._search_query), 0))
        cursor.movePosition(
            QTextCursor.MoveOperation.Right,
            QTextCursor.MoveMode.KeepAnchor,
            len(self._search_query),
        )
        editor.setTextCursor(cursor)
        editor.ensureCursorVisible()
        editor.setFocus()

    def _on_previous_match(self) -> None:
        if not self._search_matches:
            return
        self._current_match_index = (self._current_match_index - 1) % len(self._search_matches)
        self._jump_to_match(self._current_match_index)

    def _on_next_match(self) -> None:
        if not self._search_matches:
            return
        self._current_match_index = (self._current_match_index + 1) % len(self._search_matches)
        self._jump_to_match(self._current_match_index)

    def _on_clear_search(self) -> None:
        self.search_input.clear()
        self._clear_highlights()
        self._search_matches = []
        self._search_query = ""
        self._current_match_index = -1
        self.prev_button.setEnabled(False)
        self.next_button.setEnabled(False)

    def _current_text(self) -> str:
        if self._active_mode == VIEW_MODE_COMPARE:
            return (
                f"{self.i18n.t('viewer.mode_transcript')}:\n{self.transcript_text}\n\n"
                f"{self.i18n.t('viewer.mode_translation')}:\n{self.translation_text}"
            )
        if self._active_mode == VIEW_MODE_TRANSLATION:
            return self.translation_text
        return self.transcript_text

    def _on_copy_all(self) -> None:
        from core.qt_imports import QApplication, QTimer

        text = self._current_text()
        if not text:
            return
        QApplication.clipboard().setText(text)
        self.copy_button.setText(self.i18n.t("transcript.copied"))
        QTimer.singleShot(2000, lambda: self.copy_button.setText(self.i18n.t("transcript.copy_all")))

    def _suggest_export_name(self) -> str:
        if self._active_mode == VIEW_MODE_TRANSLATION and self.translation_path:
            return Path(self.translation_path).name
        if self._active_mode == VIEW_MODE_COMPARE and self.transcript_path:
            stem = Path(self.transcript_path).stem
            return f"{stem}_compare.txt"
        if self.transcript_path:
            return Path(self.transcript_path).name
        return "transcript.txt"

    def _on_export(self) -> None:
        text = self._current_text()
        if not text:
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            self.i18n.t("transcript.export_dialog_title"),
            str(Path.home() / self._suggest_export_name()),
            "Text Files (*.txt);;Markdown Files (*.md);;All Files (*.*)",
        )
        if not file_path:
            return
        try:
            with open(file_path, "w", encoding="utf-8") as handle:
                handle.write(text)
            self.show_info(self.i18n.t("common.success"), self.i18n.t("transcript.export_success"))
        except Exception as exc:  # noqa: BLE001
            logger.error("Export viewer content failed: %s", exc, exc_info=True)
            self.show_error(self.i18n.t("common.error"), str(exc))

    def update_translations(self):
        self.mode_caption.setText(self.i18n.t("viewer.view_mode"))
        self._mode_buttons[VIEW_MODE_TRANSCRIPT].setText(self.i18n.t("viewer.mode_transcript"))
        self._mode_buttons[VIEW_MODE_TRANSLATION].setText(self.i18n.t("viewer.mode_translation"))
        self._mode_buttons[VIEW_MODE_COMPARE].setText(self.i18n.t("viewer.mode_compare"))
        self.compare_left_title.setText(self.i18n.t("viewer.mode_transcript"))
        self.compare_right_title.setText(self.i18n.t("viewer.mode_translation"))
        self.search_input.setPlaceholderText(self.i18n.t("transcript.search_placeholder"))
        self.search_button.setText(self.i18n.t("transcript.search"))
        self.prev_button.setText(self.i18n.t("transcript.previous_match_button"))
        self.next_button.setText(self.i18n.t("transcript.next_match_button"))
        self.clear_search_button.setText(self.i18n.t("transcript.clear_search"))
        self.copy_button.setText(self.i18n.t("transcript.copy_all"))
        self.export_button.setText(self.i18n.t("transcript.export"))

        current_mode = self._active_mode
        self._apply_available_modes()
        self.set_view_mode(current_mode)


class TranscriptTranslationViewerDialog(QDialog):
    """Dialog wrapper around ``TranscriptTranslationViewer``."""

    def __init__(
        self,
        i18n: I18nQtManager,
        *,
        transcript_path: Optional[str] = None,
        translation_path: Optional[str] = None,
        initial_mode: str = VIEW_MODE_TRANSCRIPT,
        title_key: str = "transcript.viewer_title",
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.i18n = i18n
        self._title_key = title_key
        self.setWindowTitle(self.i18n.t(self._title_key))
        self.setMinimumSize(TIMELINE_TRANSCRIPT_DIALOG_MIN_WIDTH, TIMELINE_TRANSCRIPT_DIALOG_MIN_HEIGHT)
        self.setWindowModality(Qt.WindowModality.NonModal)
        self.setModal(False)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)

        layout = QVBoxLayout(self)
        self.viewer = TranscriptTranslationViewer(
            i18n=i18n,
            transcript_path=transcript_path,
            translation_path=translation_path,
            initial_mode=initial_mode,
            parent=self,
        )
        layout.addWidget(self.viewer)

        button_layout = create_hbox(margins=TIMELINE_DIALOG_BUTTON_MARGINS)
        button_layout.addStretch()
        self.close_button = create_button(i18n.t("common.close"))
        self.close_button.setProperty("role", ROLE_DIALOG_PRIMARY_ACTION)
        connect_button_with_callback(self.close_button, self.close)
        button_layout.addWidget(self.close_button)
        layout.addLayout(button_layout)

        self._language_signal = getattr(self.i18n, "language_changed", None)
        self._language_signal_connected = False
        if self._language_signal is not None:
            self._language_signal.connect(self.update_translations)
            self._language_signal_connected = True
            self.destroyed.connect(self._disconnect_language_signal)

    def update_translations(self):
        self.setWindowTitle(self.i18n.t(self._title_key))
        self.close_button.setText(self.i18n.t("common.close"))
        self.viewer.update_translations()

    def _disconnect_language_signal(self, *args):
        if self._language_signal_connected and self._language_signal is not None:
            try:
                self._language_signal.disconnect(self.update_translations)
            except (TypeError, RuntimeError):
                pass
            finally:
                self._language_signal_connected = False

    def closeEvent(self, event):
        self._disconnect_language_signal()
        super().closeEvent(event)
