# SPDX-License-Identifier: Apache-2.0
"""Workspace AI settings page."""

import logging
import shlex
from typing import Any, Dict, Optional, Tuple

from core.qt_imports import QComboBox, QLabel, QLineEdit

from ui.base_widgets import create_button, create_hbox
from ui.constants import ROLE_DEVICE_INFO, ROLE_SETTINGS_INLINE_ACTION
from ui.settings.base_page import BaseSettingsPage
from utils.i18n import I18nQtManager

logger = logging.getLogger("echonote.ui.settings.workspace_ai")

SUMMARY_STRATEGIES: Tuple[Tuple[str, str], ...] = (
    ("extractive", "settings.workspace_ai.summary_strategy_extractive"),
    ("abstractive", "settings.workspace_ai.summary_strategy_abstractive"),
)

MEETING_TEMPLATES: Tuple[Tuple[str, str], ...] = (
    ("standard", "settings.workspace_ai.template_standard"),
    ("concise", "settings.workspace_ai.template_concise"),
    ("action-first", "settings.workspace_ai.template_action_first"),
)


class WorkspaceAISettingsPage(BaseSettingsPage):
    """Settings page for workspace summary and meeting cleanup defaults."""

    def __init__(
        self,
        settings_manager,
        i18n: I18nQtManager,
        managers: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(settings_manager, i18n)
        self.managers = managers or {}
        self.model_manager = self.managers.get("model_manager")
        self.setup_ui()

    def setup_ui(self) -> None:
        self.defaults_title = self.add_section_title(self.i18n.t("settings.workspace_ai.defaults"))

        self.description_label = QLabel(self.i18n.t("settings.workspace_ai.description"))
        self.description_label.setProperty("role", ROLE_DEVICE_INFO)
        self.description_label.setWordWrap(True)
        self.content_layout.addWidget(self.description_label)

        self.summary_strategy_combo = QComboBox()
        self._populate_summary_strategies()
        self.summary_strategy_combo.currentIndexChanged.connect(self._emit_changed)
        _, self.summary_strategy_label = self.add_labeled_row(
            self.i18n.t("settings.workspace_ai.default_summary_strategy"),
            self.summary_strategy_combo,
        )

        self.summary_model_combo = QComboBox()
        self.summary_model_combo.currentIndexChanged.connect(self._emit_changed)
        _, self.summary_model_label = self.add_labeled_row(
            self.i18n.t("settings.workspace_ai.default_summary_model"),
            self.summary_model_combo,
        )

        self.meeting_model_combo = QComboBox()
        self.meeting_model_combo.currentIndexChanged.connect(self._emit_changed)
        _, self.meeting_model_label = self.add_labeled_row(
            self.i18n.t("settings.workspace_ai.default_meeting_model"),
            self.meeting_model_combo,
        )

        self.meeting_template_combo = QComboBox()
        self._populate_meeting_templates()
        self.meeting_template_combo.currentIndexChanged.connect(self._emit_changed)
        _, self.meeting_template_label = self.add_labeled_row(
            self.i18n.t("settings.workspace_ai.default_meeting_template"),
            self.meeting_template_combo,
        )

        self.runtime_command_edit = QLineEdit()
        self.runtime_command_edit.setPlaceholderText(
            self.i18n.t("settings.workspace_ai.gguf_runtime_placeholder")
        )
        self.runtime_command_edit.textChanged.connect(self._emit_changed)
        _, self.runtime_command_label = self.add_labeled_row(
            self.i18n.t("settings.workspace_ai.gguf_runtime_command"),
            self.runtime_command_edit,
        )

        self.runtime_hint_label = QLabel(self.i18n.t("settings.workspace_ai.gguf_runtime_hint"))
        self.runtime_hint_label.setProperty("role", ROLE_DEVICE_INFO)
        self.runtime_hint_label.setWordWrap(True)
        self.content_layout.addWidget(self.runtime_hint_label)

        actions_layout = create_hbox()
        self.model_management_button = create_button(
            self.i18n.t("settings.workspace_ai.go_to_model_management")
        )
        self.model_management_button.setProperty("role", ROLE_SETTINGS_INLINE_ACTION)
        self.model_management_button.clicked.connect(self._on_go_to_model_management)
        actions_layout.addWidget(self.model_management_button)
        actions_layout.addStretch()
        self.content_layout.addLayout(actions_layout)

        self.add_section_spacing()
        self.content_layout.addStretch()
        self._populate_model_options()

    def load_settings(self) -> None:
        preferences = self._get_preferences()
        self._populate_model_options(
            summary_model_id=preferences["default_summary_model"],
            meeting_model_id=preferences["default_meeting_model"],
        )

        self._set_combo_value(
            self.summary_strategy_combo,
            preferences["default_summary_strategy"],
        )
        self._set_combo_value(self.summary_model_combo, preferences["default_summary_model"])
        self._set_combo_value(self.meeting_model_combo, preferences["default_meeting_model"])
        self._set_combo_value(
            self.meeting_template_combo,
            preferences["default_meeting_template"],
        )
        runtime_command = preferences.get("gguf_runtime_command") or []
        self.runtime_command_edit.setText(shlex.join(runtime_command) if runtime_command else "")

    def save_settings(self) -> None:
        self._set_setting_or_raise(
            "workspace_ai.default_summary_strategy",
            self.summary_strategy_combo.currentData() or "extractive",
        )
        self._set_setting_or_raise(
            "workspace_ai.default_summary_model",
            self.summary_model_combo.currentData() or "extractive-default",
        )
        self._set_setting_or_raise(
            "workspace_ai.default_meeting_model",
            self.meeting_model_combo.currentData() or "extractive-default",
        )
        self._set_setting_or_raise(
            "workspace_ai.default_meeting_template",
            self.meeting_template_combo.currentData() or "standard",
        )
        command_text = self.runtime_command_edit.text().strip()
        self._set_setting_or_raise(
            "workspace_ai.gguf_runtime_command",
            shlex.split(command_text) if command_text else [],
        )

    def validate_settings(self) -> tuple[bool, str]:
        return True, ""

    def update_translations(self) -> None:
        if hasattr(self, "defaults_title"):
            self.defaults_title.setText(self.i18n.t("settings.workspace_ai.defaults"))
        if hasattr(self, "description_label"):
            self.description_label.setText(self.i18n.t("settings.workspace_ai.description"))
        if hasattr(self, "summary_strategy_label"):
            self.summary_strategy_label.setText(
                self.i18n.t("settings.workspace_ai.default_summary_strategy")
            )
        if hasattr(self, "summary_model_label"):
            self.summary_model_label.setText(
                self.i18n.t("settings.workspace_ai.default_summary_model")
            )
        if hasattr(self, "meeting_model_label"):
            self.meeting_model_label.setText(
                self.i18n.t("settings.workspace_ai.default_meeting_model")
            )
        if hasattr(self, "meeting_template_label"):
            self.meeting_template_label.setText(
                self.i18n.t("settings.workspace_ai.default_meeting_template")
            )
        if hasattr(self, "runtime_command_label"):
            self.runtime_command_label.setText(
                self.i18n.t("settings.workspace_ai.gguf_runtime_command")
            )
        if hasattr(self, "runtime_command_edit"):
            self.runtime_command_edit.setPlaceholderText(
                self.i18n.t("settings.workspace_ai.gguf_runtime_placeholder")
            )
        if hasattr(self, "runtime_hint_label"):
            self.runtime_hint_label.setText(self.i18n.t("settings.workspace_ai.gguf_runtime_hint"))
        if hasattr(self, "model_management_button"):
            self.model_management_button.setText(
                self.i18n.t("settings.workspace_ai.go_to_model_management")
            )

        current_strategy = self.summary_strategy_combo.currentData()
        current_template = self.meeting_template_combo.currentData()
        current_summary_model = self.summary_model_combo.currentData()
        current_meeting_model = self.meeting_model_combo.currentData()
        self._populate_summary_strategies()
        self._populate_meeting_templates()
        self._populate_model_options(
            summary_model_id=current_summary_model,
            meeting_model_id=current_meeting_model,
        )
        self._set_combo_value(self.summary_strategy_combo, current_strategy)
        self._set_combo_value(self.meeting_template_combo, current_template)

    def _populate_summary_strategies(self) -> None:
        current_value = self.summary_strategy_combo.currentData() if hasattr(self, "summary_strategy_combo") else None
        self.summary_strategy_combo.blockSignals(True)
        self.summary_strategy_combo.clear()
        for value, key in SUMMARY_STRATEGIES:
            self.summary_strategy_combo.addItem(self.i18n.t(key), value)
        self._set_combo_value(self.summary_strategy_combo, current_value)
        self.summary_strategy_combo.blockSignals(False)

    def _populate_meeting_templates(self) -> None:
        current_value = self.meeting_template_combo.currentData() if hasattr(self, "meeting_template_combo") else None
        self.meeting_template_combo.blockSignals(True)
        self.meeting_template_combo.clear()
        for value, key in MEETING_TEMPLATES:
            self.meeting_template_combo.addItem(self.i18n.t(key), value)
        self._set_combo_value(self.meeting_template_combo, current_value)
        self.meeting_template_combo.blockSignals(False)

    def _populate_model_options(
        self,
        *,
        summary_model_id: Optional[str] = None,
        meeting_model_id: Optional[str] = None,
    ) -> None:
        current_summary = summary_model_id or self.summary_model_combo.currentData()
        current_meeting = meeting_model_id or self.meeting_model_combo.currentData()

        models = []
        if self.model_manager is not None and hasattr(self.model_manager, "get_all_text_ai_models"):
            try:
                models = list(self.model_manager.get_all_text_ai_models())
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to load text ai models for settings page: %s", exc)

        self.summary_model_combo.blockSignals(True)
        self.meeting_model_combo.blockSignals(True)
        self.summary_model_combo.clear()
        self.meeting_model_combo.clear()

        seen_summary: set[str] = set()
        seen_meeting: set[str] = set()

        for model in models:
            summary_label = self._format_model_option_label(model.display_name, model.runtime, model.family)
            self.summary_model_combo.addItem(summary_label, model.model_id)
            self.meeting_model_combo.addItem(summary_label, model.model_id)
            seen_summary.add(model.model_id)
            seen_meeting.add(model.model_id)

        if current_summary and current_summary not in seen_summary:
            self.summary_model_combo.addItem(current_summary, current_summary)
        if current_meeting and current_meeting not in seen_meeting:
            self.meeting_model_combo.addItem(current_meeting, current_meeting)

        self._set_combo_value(self.summary_model_combo, current_summary)
        self._set_combo_value(self.meeting_model_combo, current_meeting)
        self.summary_model_combo.blockSignals(False)
        self.meeting_model_combo.blockSignals(False)

    def _format_model_option_label(self, display_name: str, runtime: str, family: str) -> str:
        runtime_label = self.i18n.t(f"settings.workspace_ai.runtime_{runtime}")
        family_label = self.i18n.t(f"settings.workspace_ai.family_{family}")
        return f"{display_name} ({runtime_label} / {family_label})"

    def _set_combo_value(self, combo: QComboBox, value: Optional[str]) -> None:
        if not value:
            return
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)

    def _get_preferences(self) -> dict:
        defaults = {
            "default_summary_strategy": "extractive",
            "default_summary_model": "flan-t5-small-int8",
            "default_meeting_model": "extractive-default",
            "default_meeting_template": "standard",
            "gguf_runtime_command": [],
        }
        loader = getattr(self.settings_manager, "get_workspace_ai_preferences", None)
        if callable(loader):
            loaded = loader()
            if isinstance(loaded, dict):
                defaults.update(loaded)
        return defaults

    def _on_go_to_model_management(self) -> None:
        model_page = self._open_settings_page("model_management")
        if model_page and hasattr(model_page, "tabs"):
            model_page.tabs.setCurrentIndex(2)
