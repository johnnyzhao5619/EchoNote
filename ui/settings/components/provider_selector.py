# SPDX-License-Identifier: Apache-2.0
"""Shared provider selection widgets for settings pages."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from core.qt_imports import QLabel, QFrame, QWidget, Qt, Signal

from ui.base_widgets import create_hbox, create_vbox
from ui.constants import (
    ROLE_SETTINGS_PROVIDER_BADGE,
    ROLE_SETTINGS_PROVIDER_DESCRIPTION,
    ROLE_SETTINGS_PROVIDER_OPTION,
    ROLE_SETTINGS_PROVIDER_SELECTOR,
    ROLE_SETTINGS_PROVIDER_TITLE,
    SETTINGS_PROVIDER_OPTION_MARGINS,
    SETTINGS_PROVIDER_OPTION_SPACING,
    SETTINGS_PROVIDER_SELECTOR_SPACING,
    ZERO_MARGINS,
)


@dataclass(frozen=True)
class ProviderOptionSpec:
    """Display metadata for a selectable provider."""

    provider_id: str
    title: str
    description: str
    badge: str = ""


class ProviderOptionCard(QFrame):
    """Clickable provider card with title, description, and optional badge."""

    clicked = Signal(str)

    def __init__(self, spec: ProviderOptionSpec, parent=None):
        super().__init__(parent)
        self.spec = spec
        self._selected = False
        self._hovered = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setProperty("role", ROLE_SETTINGS_PROVIDER_OPTION)
        self.setProperty("state", "default")
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)

        layout = create_vbox(
            spacing=SETTINGS_PROVIDER_OPTION_SPACING,
            margins=SETTINGS_PROVIDER_OPTION_MARGINS,
        )
        self.setLayout(layout)

        header_layout = create_hbox(margins=ZERO_MARGINS, spacing=8)
        self.title_label = QLabel(spec.title)
        self.title_label.setProperty("role", ROLE_SETTINGS_PROVIDER_TITLE)
        header_layout.addWidget(self.title_label, stretch=1)

        self.badge_label = QLabel(spec.badge)
        self.badge_label.setProperty("role", ROLE_SETTINGS_PROVIDER_BADGE)
        self.badge_label.setVisible(bool(spec.badge))
        header_layout.addWidget(self.badge_label)

        layout.addLayout(header_layout)

        self.description_label = QLabel(spec.description)
        self.description_label.setWordWrap(True)
        self.description_label.setProperty("role", ROLE_SETTINGS_PROVIDER_DESCRIPTION)
        layout.addWidget(self.description_label)

    def provider_id(self) -> str:
        return self.spec.provider_id

    def set_selected(self, selected: bool) -> None:
        self._selected = bool(selected)
        self._apply_state()

    def set_badge_text(self, text: str) -> None:
        self.badge_label.setText(text)
        self.badge_label.setVisible(bool(text))

    def enterEvent(self, event) -> None:  # noqa: N802
        self._hovered = True
        self._apply_state()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._hovered = False
        self._apply_state()
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton and self.isEnabled():
            self.clicked.emit(self.spec.provider_id)
            event.accept()
            return
        super().mousePressEvent(event)

    def _apply_state(self) -> None:
        if not self.isEnabled():
            state = "disabled"
        elif self._selected:
            state = "selected"
        elif self._hovered:
            state = "hover"
        else:
            state = "default"
        if self.property("state") == state:
            return
        self.setProperty("state", state)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()


class ProviderSelectorWidget(QWidget):
    """Vertical list of provider cards with single selection semantics."""

    provider_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setProperty("role", ROLE_SETTINGS_PROVIDER_SELECTOR)
        self._cards: dict[str, ProviderOptionCard] = {}
        self._current_provider_id = ""
        self._layout = create_vbox(
            spacing=SETTINGS_PROVIDER_SELECTOR_SPACING,
            margins=ZERO_MARGINS,
        )
        self.setLayout(self._layout)

    def clear(self) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._cards.clear()
        self._current_provider_id = ""

    def set_options(
        self,
        options: Iterable[ProviderOptionSpec],
        *,
        selected_id: str = "",
    ) -> None:
        self.clear()
        normalized = [option for option in options]
        for option in normalized:
            card = ProviderOptionCard(option, self)
            card.clicked.connect(self.set_current_provider)
            self._layout.addWidget(card)
            self._cards[option.provider_id] = card
        self._layout.addStretch()
        if normalized:
            default_provider = selected_id or normalized[0].provider_id
            self.set_current_provider(default_provider, emit_signal=False)

    def current_provider(self) -> str:
        return self._current_provider_id

    def set_current_provider(self, provider_id: str, *, emit_signal: bool = True) -> None:
        if provider_id not in self._cards:
            return
        if provider_id == self._current_provider_id and emit_signal:
            return
        self._current_provider_id = provider_id
        for current_id, card in self._cards.items():
            card.set_selected(current_id == provider_id)
        if emit_signal:
            self.provider_changed.emit(provider_id)

    def set_badge(self, provider_id: str, badge: str) -> None:
        card = self._cards.get(provider_id)
        if card is not None:
            card.set_badge_text(badge)
