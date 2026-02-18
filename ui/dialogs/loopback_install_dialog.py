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
"""Loopback installation guidance dialog."""

import logging
import platform
from typing import Optional

from PySide6.QtWidgets import QCheckBox, QDialog, QLabel, QMessageBox, QTextEdit, QVBoxLayout

from ui.base_widgets import connect_button_with_callback, create_button, create_hbox
from ui.constants import (
    LOOPBACK_DIALOG_MIN_HEIGHT,
    LOOPBACK_DIALOG_MIN_WIDTH,
)
from utils.i18n import I18nQtManager
from utils.loopback_installer import LoopbackInstaller

logger = logging.getLogger("echonote.ui.dialogs.loopback_install")


class LoopbackInstallDialog(QDialog):
    """Dialog showing loopback setup instructions."""

    def __init__(
        self, title: str, instructions: str, i18n: I18nQtManager, parent: Optional[QDialog] = None
    ):
        super().__init__(parent)

        self.i18n = i18n
        self.dont_show_again = False
        self._installer = LoopbackInstaller(i18n=i18n)

        system_name = platform.system()
        self.platform_display = {"Darwin": "macOS", "Linux": "Linux", "Windows": "Windows"}.get(
            system_name, system_name
        )

        dialog_title = self.i18n.t("loopback.dialog_title", platform=self.platform_display)
        self.setWindowTitle(dialog_title or title)
        self.setMinimumWidth(LOOPBACK_DIALOG_MIN_WIDTH)
        self.setMinimumHeight(LOOPBACK_DIALOG_MIN_HEIGHT)

        self.setup_ui(instructions)
        logger.debug("Loopback installation dialog initialized")

    def setup_ui(self, instructions: str):
        """Build dialog UI."""
        layout = QVBoxLayout(self)

        header_layout = create_hbox()

        title_text = self.i18n.t("loopback.not_installed_title", platform=self.platform_display)
        title_label = QLabel(title_text)
        title_label.setObjectName("section_title")
        header_layout.addWidget(title_label)

        header_layout.addStretch()
        layout.addLayout(header_layout)

        desc_text = (
            f"{self.i18n.t('loopback.description')}\n"
            f"{self.i18n.t('loopback.benefits_title')}\n"
            f"• {self.i18n.t('loopback.benefit_system_audio')}\n"
            f"• {self.i18n.t('loopback.benefit_meeting_capture')}\n"
            f"• {self.i18n.t('loopback.benefit_mic_isolation')}"
        )
        desc_label = QLabel(desc_text)
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)

        instructions_label = QLabel(self.i18n.t("loopback.installation_instructions"))
        instructions_label.setProperty("role", "audio-file")
        layout.addWidget(instructions_label)

        instructions_text = QTextEdit()
        instructions_text.setPlainText(instructions)
        instructions_text.setReadOnly(True)
        instructions_text.setObjectName("loopback_instructions_text")
        layout.addWidget(instructions_text)

        note_label = QLabel(self.i18n.t("loopback.note"))
        note_label.setWordWrap(True)
        note_label.setObjectName("loopback_note_label")
        layout.addWidget(note_label)

        self.dont_show_checkbox = QCheckBox(self.i18n.t("loopback.dont_show_again"))
        layout.addWidget(self.dont_show_checkbox)

        admin_note = QLabel(self._installer.get_authorization_note())
        admin_note.setWordWrap(True)
        admin_note.setObjectName("loopback_admin_note_label")
        layout.addWidget(admin_note)

        button_layout = create_hbox()
        button_layout.addStretch()

        self.install_btn = create_button(self.i18n.t("loopback.install_now"))
        self.install_btn.setEnabled(self._installer.supports_one_click_install())
        connect_button_with_callback(self.install_btn, self.install_now)
        button_layout.addWidget(self.install_btn)

        later_btn = create_button(self.i18n.t("loopback.install_later"))
        connect_button_with_callback(later_btn, self.on_later)
        button_layout.addWidget(later_btn)

        ok_btn = create_button(self.i18n.t("loopback.got_it"))
        ok_btn.setDefault(True)
        connect_button_with_callback(ok_btn, self.accept)
        button_layout.addWidget(ok_btn)

        layout.addLayout(button_layout)

    def on_later(self):
        """Handle later action."""
        self.dont_show_again = False
        self.reject()

    def install_now(self):
        """Run one-click installation with native authorization prompts."""
        title = self.i18n.t("loopback.install_confirm_title")
        message = self._installer.get_install_confirm_message()
        choice = QMessageBox.question(
            self,
            title,
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Yes,
        )
        if choice != QMessageBox.StandardButton.Yes:
            return

        self.install_btn.setEnabled(False)
        try:
            result = self._installer.install_loopback_input()
        finally:
            self.install_btn.setEnabled(self._installer.supports_one_click_install())

        if result.success:
            QMessageBox.information(
                self,
                self.i18n.t("loopback.install_success_title"),
                result.message,
                QMessageBox.StandardButton.Ok,
            )
            self.dont_show_checkbox.setChecked(True)
            return

        dialog_title = (
            self.i18n.t("loopback.install_cancelled_title")
            if result.cancelled
            else self.i18n.t("loopback.install_failed_title")
        )
        QMessageBox.warning(
            self,
            dialog_title,
            result.message,
            QMessageBox.StandardButton.Ok,
        )

    def accept(self):
        """Handle acceptance and preference persistence flag."""
        self.dont_show_again = self.dont_show_checkbox.isChecked()
        super().accept()

    def should_show_again(self) -> bool:
        """Return whether dialog should continue appearing."""
        return not self.dont_show_again
