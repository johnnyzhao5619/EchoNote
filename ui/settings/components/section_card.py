# SPDX-License-Identifier: Apache-2.0
"""Reusable settings surface container."""

from core.qt_imports import QFrame

from ui.base_widgets import create_vbox
from ui.constants import (
    ROLE_SETTINGS_SECTION_CARD,
    SETTINGS_SECTION_CARD_MARGINS,
    SETTINGS_SECTION_CARD_SPACING,
)


class SettingsSectionCard(QFrame):
    """Reusable surface container for settings sections."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setProperty("role", ROLE_SETTINGS_SECTION_CARD)
        self._layout = create_vbox(
            spacing=SETTINGS_SECTION_CARD_SPACING,
            margins=SETTINGS_SECTION_CARD_MARGINS,
        )
        self.setLayout(self._layout)

    @property
    def content_layout(self):
        return self._layout
