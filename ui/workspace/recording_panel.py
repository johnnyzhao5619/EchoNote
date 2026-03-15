# SPDX-License-Identifier: Apache-2.0
"""Workspace recording playback panel."""

from __future__ import annotations

from core.qt_imports import QLabel, QVBoxLayout
from ui.base_widgets import BaseWidget
from ui.common.audio_player import AudioPlayer
from ui.constants import (
    ROLE_WORKSPACE_PLACEHOLDER,
    ROLE_WORKSPACE_RECORDING_PANEL,
)
from utils.i18n import I18nQtManager


class WorkspaceRecordingPanel(BaseWidget):
    """Playback panel backed by the shared audio player widget."""

    def __init__(self, workspace_manager, i18n: I18nQtManager, parent=None):
        super().__init__(i18n, parent)
        self.workspace_manager = workspace_manager
        self.audio_player = None
        self._init_ui()

    def _init_ui(self) -> None:
        self.setProperty("role", ROLE_WORKSPACE_RECORDING_PANEL)
        layout = QVBoxLayout(self)
        self.placeholder_label = QLabel(self.i18n.t("workspace.no_audio_asset"))
        self.placeholder_label.setProperty("role", ROLE_WORKSPACE_PLACEHOLDER)
        layout.addWidget(self.placeholder_label)
        self.audio_player = AudioPlayer("", self.i18n, self, auto_load=False)
        self.audio_player.hide()
        layout.addWidget(self.audio_player, 1)

    def update_translations(self) -> None:
        self.placeholder_label.setText(self.i18n.t("workspace.no_audio_asset"))

    def set_item(self, item) -> None:
        if item is None:
            self.audio_player.clear_media()
            self.audio_player.hide()
            self.placeholder_label.show()
            return

        assets = self.workspace_manager.get_assets(item.id)
        asset_map = {asset.asset_role: asset for asset in assets}
        audio_asset = asset_map.get("audio")
        if audio_asset is None or not audio_asset.file_path:
            self.audio_player.clear_media()
            self.audio_player.hide()
            self.placeholder_label.show()
            return

        transcript_path = asset_map.get("transcript").file_path if asset_map.get("transcript") else None
        translation_path = asset_map.get("translation").file_path if asset_map.get("translation") else None
        self.audio_player.show()
        self.placeholder_label.hide()
        self.audio_player.load_file(
            audio_asset.file_path,
            transcript_path=transcript_path,
            translation_path=translation_path,
        )
