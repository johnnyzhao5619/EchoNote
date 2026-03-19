# SPDX-License-Identifier: Apache-2.0
"""Workspace storage settings page."""

from __future__ import annotations

from pathlib import Path

from core.qt_imports import QFileDialog, QLabel, QLineEdit

from ui.base_widgets import create_button, create_hbox
from ui.constants import ROLE_DEVICE_INFO, ROLE_SETTINGS_INLINE_ACTION
from ui.settings.base_page import BaseSettingsPage


class WorkspaceSettingsPage(BaseSettingsPage):
    """Settings page for workspace vault storage preferences."""

    def __init__(self, settings_manager, i18n, parent=None):
        super().__init__(settings_manager, i18n, parent)
        self.setup_ui()

    def setup_ui(self) -> None:
        self.title_label = self.add_section_title(self.i18n.t("settings.workspace.title"))

        self.description_label = QLabel(self.i18n.t("settings.workspace.description"))
        self.description_label.setProperty("role", ROLE_DEVICE_INFO)
        self.description_label.setWordWrap(True)
        self.content_layout.addWidget(self.description_label)

        path_layout = create_hbox()
        self.storage_root_label = QLabel(self.i18n.t("settings.workspace.storage_root"))
        self.storage_root_edit = QLineEdit()
        self.storage_root_edit.textChanged.connect(self._emit_changed)
        self.browse_button = create_button(self.i18n.t("settings.workspace.browse"))
        self.browse_button.setProperty("role", ROLE_SETTINGS_INLINE_ACTION)
        self.browse_button.clicked.connect(self._on_browse_clicked)
        path_layout.addWidget(self.storage_root_label)
        path_layout.addWidget(self.storage_root_edit, stretch=1)
        path_layout.addWidget(self.browse_button)
        self.content_layout.addLayout(path_layout)

        self.hint_label = QLabel(self.i18n.t("settings.workspace.storage_root_hint"))
        self.hint_label.setProperty("role", ROLE_DEVICE_INFO)
        self.hint_label.setWordWrap(True)
        self.content_layout.addWidget(self.hint_label)

        self.restart_hint_label = QLabel(self.i18n.t("settings.workspace.restart_hint"))
        self.restart_hint_label.setProperty("role", ROLE_DEVICE_INFO)
        self.restart_hint_label.setWordWrap(True)
        self.content_layout.addWidget(self.restart_hint_label)

        self.content_layout.addStretch()

    def load_settings(self) -> None:
        preferences = self._get_preferences()
        self.storage_root_edit.setText(preferences["storage_root"])

    def save_settings(self) -> None:
        self._set_setting_or_raise(
            "workspace.storage_root",
            self.storage_root_edit.text().strip(),
        )

    def validate_settings(self) -> tuple[bool, str]:
        storage_root = self.storage_root_edit.text().strip()
        if not storage_root:
            return False, self.i18n.t("settings.workspace.error.empty_path")
        return True, ""

    def update_translations(self) -> None:
        self.title_label.setText(self.i18n.t("settings.workspace.title"))
        self.description_label.setText(self.i18n.t("settings.workspace.description"))
        self.storage_root_label.setText(self.i18n.t("settings.workspace.storage_root"))
        self.browse_button.setText(self.i18n.t("settings.workspace.browse"))
        self.hint_label.setText(self.i18n.t("settings.workspace.storage_root_hint"))
        self.restart_hint_label.setText(self.i18n.t("settings.workspace.restart_hint"))

    def _on_browse_clicked(self) -> None:
        current_path = self.storage_root_edit.text().strip()
        if not current_path:
            current_path = str(Path.home() / "Documents" / "EchoNote" / "WorkspaceVault")
        directory = QFileDialog.getExistingDirectory(
            self,
            self.i18n.t("settings.workspace.select_directory"),
            current_path,
        )
        if directory:
            self.storage_root_edit.setText(directory)

    def _get_preferences(self) -> dict:
        resolver = getattr(self.settings_manager, "get_workspace_preferences", None)
        if callable(resolver):
            return resolver()
        return {
            "storage_root": self.settings_manager.get_setting("workspace.storage_root")
            or str(Path.home() / "Documents" / "EchoNote" / "WorkspaceVault")
        }
