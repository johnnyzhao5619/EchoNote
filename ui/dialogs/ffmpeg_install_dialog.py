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
FFmpeg installation dialog.

Shows installation instructions for ffmpeg when it's not available.
"""

import logging
import platform
from typing import Optional

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QCheckBox,
)
from PySide6.QtGui import QFont

from utils.i18n import I18nQtManager


logger = logging.getLogger("echonote.ui.dialogs.ffmpeg_install")


class FFmpegInstallDialog(QDialog):
    """
    Dialog showing FFmpeg installation instructions.

    Displays platform-specific installation instructions and allows
    users to dismiss or not show again.
    """

    def __init__(
        self, title: str, instructions: str, i18n: I18nQtManager, parent: Optional[QDialog] = None
    ):
        """
        Initialize FFmpeg installation dialog.

        Args:
            title: Dialog title
            instructions: Installation instructions text
            i18n: Internationalization manager
            parent: Parent widget
        """
        super().__init__(parent)

        self.i18n = i18n
        self.dont_show_again = False

        # Get platform info
        system_name = platform.system()
        self.platform_display = {"Darwin": "macOS", "Linux": "Linux", "Windows": "Windows"}.get(
            system_name, system_name
        )

        # Setup dialog
        dialog_title = self.i18n.t("ffmpeg.dialog_title", platform=self.platform_display)
        self.setWindowTitle(dialog_title)
        self.setMinimumWidth(600)
        self.setMinimumHeight(400)

        # Setup UI
        self.setup_ui(instructions)

        logger.debug("FFmpeg installation dialog initialized")

    def setup_ui(self, instructions: str):
        """
        Setup the user interface.

        Args:
            instructions: Installation instructions text
        """
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # Icon and title
        header_layout = QHBoxLayout()

        # Warning icon (using emoji for simplicity)
        icon_label = QLabel("⚠️")
        icon_font = QFont()
        icon_font.setPointSize(32)
        icon_label.setFont(icon_font)
        header_layout.addWidget(icon_label)

        # Title with system info
        title_text = self.i18n.t("ffmpeg.not_installed_title", platform=self.platform_display)
        title_label = QLabel(title_text)
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        header_layout.addWidget(title_label)

        header_layout.addStretch()
        layout.addLayout(header_layout)

        # Description
        desc_text = (
            f"{self.i18n.t('ffmpeg.description')}\n"
            f"{self.i18n.t('ffmpeg.benefits_title')}\n"
            f"• {self.i18n.t('ffmpeg.benefit_video_formats')}\n"
            f"• {self.i18n.t('ffmpeg.benefit_duration')}\n"
            f"• {self.i18n.t('ffmpeg.benefit_experience')}"
        )
        desc_label = QLabel(desc_text)
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)

        # Instructions text area
        instructions_label = QLabel(self.i18n.t("ffmpeg.installation_instructions"))
        instructions_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(instructions_label)

        instructions_text = QTextEdit()
        instructions_text.setPlainText(instructions)
        instructions_text.setReadOnly(True)
        # Use object name for theme-aware styling
        instructions_text.setObjectName("ffmpeg_instructions_text")
        layout.addWidget(instructions_text)

        # Note
        note_label = QLabel(self.i18n.t("ffmpeg.note"))
        note_label.setWordWrap(True)
        note_label.setObjectName("ffmpeg_note_label")
        layout.addWidget(note_label)

        # Don't show again checkbox
        self.dont_show_checkbox = QCheckBox(self.i18n.t("ffmpeg.dont_show_again"))
        layout.addWidget(self.dont_show_checkbox)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        # Later button
        later_btn = QPushButton(self.i18n.t("ffmpeg.install_later"))
        later_btn.clicked.connect(self.on_later)
        button_layout.addWidget(later_btn)

        # OK button
        ok_btn = QPushButton(self.i18n.t("ffmpeg.got_it"))
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(self.accept)
        button_layout.addWidget(ok_btn)

        layout.addLayout(button_layout)

    def on_later(self):
        """Handle 'Later' button click."""
        self.dont_show_again = False
        self.reject()

    def accept(self):
        """Handle dialog acceptance."""
        self.dont_show_again = self.dont_show_checkbox.isChecked()
        super().accept()

    def should_show_again(self) -> bool:
        """
        Check if dialog should be shown again.

        Returns:
            True if dialog should be shown again, False otherwise
        """
        return not self.dont_show_again
