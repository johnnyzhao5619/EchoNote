# SPDX-License-Identifier: Apache-2.0
"""Workspace AI settings page."""

import logging
import shlex
from typing import Any, Dict, Optional, Tuple

from core.qt_imports import QComboBox, QLabel, QLineEdit, QWidget

from ui.base_widgets import create_button, create_hbox
from ui.constants import ROLE_DEVICE_INFO, ROLE_SETTINGS_INLINE_ACTION, STANDARD_LABEL_WIDTH
from ui.settings.components.provider_selector import (
    ProviderOptionSpec,
    ProviderSelectorWidget,
)
from ui.settings.components.section_card import SettingsSectionCard
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
        self._available_model_ids: dict[tuple[str, str], set[str]] = {}
        if self.model_manager is not None and hasattr(self.model_manager, "text_ai_models_updated"):
            self.model_manager.text_ai_models_updated.connect(self._on_text_ai_models_updated)
        self.setup_ui()

    def setup_ui(self) -> None:
        self.defaults_title = self.add_section_title(self.i18n.t("settings.workspace_ai.defaults"))

        self.description_label = QLabel(self.i18n.t("settings.workspace_ai.description"))
        self.description_label.setProperty("role", ROLE_DEVICE_INFO)
        self.description_label.setWordWrap(True)
        self.content_layout.addWidget(self.description_label)

        self.summary_card = SettingsSectionCard()
        self.content_layout.addWidget(self.summary_card)
        self.summary_title = self.add_section_title(
            self.i18n.t("settings.workspace_ai.default_summary_strategy"),
            layout=self.summary_card.content_layout,
        )
        self.summary_provider_selector = ProviderSelectorWidget()
        self.summary_provider_selector.provider_changed.connect(self._on_summary_provider_changed)
        self.summary_card.content_layout.addWidget(self.summary_provider_selector)
        self.summary_model_combo = QComboBox()
        self.summary_model_combo.currentIndexChanged.connect(self._emit_changed)
        self.summary_model_row, self.summary_model_label = self._create_row_widget(
            self.i18n.t("settings.workspace_ai.default_summary_model"),
            self.summary_model_combo,
            parent_layout=self.summary_card.content_layout,
        )
        self.summary_provider_hint = QLabel()
        self.summary_provider_hint.setProperty("role", ROLE_DEVICE_INFO)
        self.summary_provider_hint.setWordWrap(True)
        self.summary_card.content_layout.addWidget(self.summary_provider_hint)
        self.summary_model_management_button = create_button(
            self.i18n.t("settings.workspace_ai.go_to_model_management")
        )
        self.summary_model_management_button.setProperty("role", ROLE_SETTINGS_INLINE_ACTION)
        self.summary_model_management_button.clicked.connect(self._on_go_to_model_management)
        self.summary_card.content_layout.addWidget(self.summary_model_management_button)

        self.meeting_card = SettingsSectionCard()
        self.content_layout.addWidget(self.meeting_card)
        self.meeting_title = self.add_section_title(
            self.i18n.t("settings.workspace_ai.default_meeting_model"),
            layout=self.meeting_card.content_layout,
        )
        self.meeting_provider_selector = ProviderSelectorWidget()
        self.meeting_provider_selector.provider_changed.connect(self._on_meeting_provider_changed)
        self.meeting_card.content_layout.addWidget(self.meeting_provider_selector)
        self.meeting_model_combo = QComboBox()
        self.meeting_model_combo.currentIndexChanged.connect(self._emit_changed)
        self.meeting_model_row, self.meeting_model_label = self._create_row_widget(
            self.i18n.t("settings.workspace_ai.default_meeting_model"),
            self.meeting_model_combo,
            parent_layout=self.meeting_card.content_layout,
        )

        self.meeting_template_combo = QComboBox()
        self._populate_meeting_templates()
        self.meeting_template_combo.currentIndexChanged.connect(self._emit_changed)
        self.meeting_template_row, self.meeting_template_label = self._create_row_widget(
            self.i18n.t("settings.workspace_ai.default_meeting_template"),
            self.meeting_template_combo,
            parent_layout=self.meeting_card.content_layout,
        )

        self.runtime_command_edit = QLineEdit()
        self.runtime_command_edit.setPlaceholderText(
            self.i18n.t("settings.workspace_ai.gguf_runtime_placeholder")
        )
        self.runtime_command_edit.textChanged.connect(self._emit_changed)
        self.runtime_command_row, self.runtime_command_label = self._create_row_widget(
            self.i18n.t("settings.workspace_ai.gguf_runtime_command"),
            self.runtime_command_edit,
            parent_layout=self.meeting_card.content_layout,
        )

        self.runtime_hint_label = QLabel(self.i18n.t("settings.workspace_ai.gguf_runtime_hint"))
        self.runtime_hint_label.setProperty("role", ROLE_DEVICE_INFO)
        self.runtime_hint_label.setWordWrap(True)
        self.meeting_card.content_layout.addWidget(self.runtime_hint_label)

        self.meeting_provider_hint = QLabel()
        self.meeting_provider_hint.setProperty("role", ROLE_DEVICE_INFO)
        self.meeting_provider_hint.setWordWrap(True)
        self.meeting_card.content_layout.addWidget(self.meeting_provider_hint)
        self.meeting_model_management_button = create_button(
            self.i18n.t("settings.workspace_ai.go_to_model_management")
        )
        self.meeting_model_management_button.setProperty("role", ROLE_SETTINGS_INLINE_ACTION)
        self.meeting_model_management_button.clicked.connect(self._on_go_to_model_management)
        self.meeting_card.content_layout.addWidget(self.meeting_model_management_button)

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
        self._configure_provider_selectors()
        self._populate_model_options()

    def load_settings(self) -> None:
        preferences = self._get_preferences()
        summary_provider = (
            "extractive"
            if preferences["default_summary_strategy"] == "extractive"
            else "onnx"
        )
        meeting_provider = self._resolve_meeting_provider(preferences["default_meeting_model"])
        self.summary_provider_selector.set_current_provider(summary_provider, emit_signal=False)
        self.meeting_provider_selector.set_current_provider(meeting_provider, emit_signal=False)
        self._populate_model_options(
            summary_model_id=preferences["default_summary_model"],
            meeting_model_id=preferences["default_meeting_model"],
        )

        self._set_combo_value(self.summary_model_combo, preferences["default_summary_model"])
        self._set_combo_value(self.meeting_model_combo, preferences["default_meeting_model"])
        self._set_combo_value(
            self.meeting_template_combo,
            preferences["default_meeting_template"],
        )
        runtime_command = preferences.get("gguf_runtime_command") or []
        self.runtime_command_edit.setText(shlex.join(runtime_command) if runtime_command else "")
        self._on_summary_provider_changed(summary_provider, emit_changed=False)
        self._on_meeting_provider_changed(meeting_provider, emit_changed=False)

    def save_settings(self) -> None:
        summary_provider = self.summary_provider_selector.current_provider() or "extractive"
        meeting_provider = self.meeting_provider_selector.current_provider() or "extractive"
        self._set_setting_or_raise(
            "workspace_ai.default_summary_strategy",
            "extractive" if summary_provider == "extractive" else "abstractive",
        )
        self._set_setting_or_raise(
            "workspace_ai.default_summary_model",
            self.summary_model_combo.currentData() or "flan-t5-small-int8",
        )
        self._set_setting_or_raise(
            "workspace_ai.default_meeting_model",
            "extractive-default"
            if meeting_provider == "extractive"
            else (self.meeting_model_combo.currentData() or "extractive-default"),
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
        if (
            self.summary_provider_selector.current_provider() == "onnx"
            and not self._has_available_model(
                family="summary",
                runtime="onnx",
                model_id=self.summary_model_combo.currentData(),
            )
        ):
            return False, self.i18n.t("settings.workspace_ai.summary_model_required")
        if self.meeting_provider_selector.current_provider() == "gguf":
            if not self._has_available_model(
                family="meeting",
                runtime="gguf",
                model_id=self.meeting_model_combo.currentData(),
            ):
                return False, self.i18n.t("settings.workspace_ai.meeting_model_required")
            if not self.runtime_command_edit.text().strip():
                return False, self.i18n.t("settings.workspace_ai.gguf_runtime_required")
        return True, ""

    def update_translations(self) -> None:
        if hasattr(self, "defaults_title"):
            self.defaults_title.setText(self.i18n.t("settings.workspace_ai.defaults"))
        if hasattr(self, "description_label"):
            self.description_label.setText(self.i18n.t("settings.workspace_ai.description"))
        if hasattr(self, "summary_title"):
            self.summary_title.setText(self.i18n.t("settings.workspace_ai.default_summary_strategy"))
        if hasattr(self, "summary_model_label"):
            self.summary_model_label.setText(
                self.i18n.t("settings.workspace_ai.default_summary_model")
            )
        if hasattr(self, "meeting_title"):
            self.meeting_title.setText(self.i18n.t("settings.workspace_ai.default_meeting_model"))
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
        if hasattr(self, "summary_model_management_button"):
            self.summary_model_management_button.setText(
                self.i18n.t("settings.workspace_ai.go_to_model_management")
            )
        if hasattr(self, "meeting_model_management_button"):
            self.meeting_model_management_button.setText(
                self.i18n.t("settings.workspace_ai.go_to_model_management")
            )

        current_summary_provider = self.summary_provider_selector.current_provider()
        current_meeting_provider = self.meeting_provider_selector.current_provider()
        current_template = self.meeting_template_combo.currentData()
        current_summary_model = self.summary_model_combo.currentData()
        current_meeting_model = self.meeting_model_combo.currentData()
        self._populate_meeting_templates()
        self._configure_provider_selectors()
        self._populate_model_options(
            summary_model_id=current_summary_model,
            meeting_model_id=current_meeting_model,
        )
        self.summary_provider_selector.set_current_provider(
            current_summary_provider or "extractive",
            emit_signal=False,
        )
        self.meeting_provider_selector.set_current_provider(
            current_meeting_provider or "extractive",
            emit_signal=False,
        )
        self._set_combo_value(self.meeting_template_combo, current_template)
        self._on_summary_provider_changed(
            self.summary_provider_selector.current_provider() or "extractive",
            emit_changed=False,
        )
        self._on_meeting_provider_changed(
            self.meeting_provider_selector.current_provider() or "extractive",
            emit_changed=False,
        )

    def _configure_provider_selectors(self) -> None:
        self.summary_provider_selector.set_options(
            (
                ProviderOptionSpec(
                    provider_id="extractive",
                    title=self.i18n.t("settings.workspace_ai.provider_extractive"),
                    description=self.i18n.t("settings.workspace_ai.provider_extractive_desc"),
                    badge=self.i18n.t("settings.workspace_ai.provider_badge_builtin"),
                ),
                ProviderOptionSpec(
                    provider_id="onnx",
                    title=self.i18n.t("settings.workspace_ai.provider_onnx"),
                    description=self.i18n.t("settings.workspace_ai.provider_onnx_desc"),
                    badge=self.i18n.t("settings.workspace_ai.provider_badge_local"),
                ),
            ),
            selected_id=self.summary_provider_selector.current_provider() or "extractive",
        )
        self.meeting_provider_selector.set_options(
            (
                ProviderOptionSpec(
                    provider_id="extractive",
                    title=self.i18n.t("settings.workspace_ai.provider_extractive"),
                    description=self.i18n.t("settings.workspace_ai.provider_extractive_desc"),
                    badge=self.i18n.t("settings.workspace_ai.provider_badge_builtin"),
                ),
                ProviderOptionSpec(
                    provider_id="gguf",
                    title=self.i18n.t("settings.workspace_ai.provider_gguf"),
                    description=self.i18n.t("settings.workspace_ai.provider_gguf_desc"),
                    badge=self.i18n.t("settings.workspace_ai.provider_badge_local"),
                ),
            ),
            selected_id=self.meeting_provider_selector.current_provider() or "extractive",
        )

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
        self._populate_filtered_model_options(
            self.summary_model_combo,
            family="summary",
            runtime="onnx",
            current_model_id=current_summary,
        )
        self._populate_filtered_model_options(
            self.meeting_model_combo,
            family="meeting",
            runtime="gguf",
            current_model_id=current_meeting,
        )

    def _populate_filtered_model_options(
        self,
        combo: QComboBox,
        *,
        family: str,
        runtime: str,
        current_model_id: Optional[str],
    ) -> None:
        models = self._get_text_ai_models(family=family, runtime=runtime)
        available_ids = {model.model_id for model in models}
        self._available_model_ids[(family, runtime)] = available_ids
        combo.blockSignals(True)
        combo.clear()
        for model in models:
            combo.addItem(
                self._format_model_option_label(model.display_name, model.runtime, model.family),
                model.model_id,
            )
        if current_model_id and current_model_id not in available_ids:
            combo.addItem(current_model_id, current_model_id)
        self._set_combo_value(combo, current_model_id)
        combo.blockSignals(False)

    def _get_text_ai_models(self, *, family: str, runtime: str):
        if self.model_manager is None or not hasattr(self.model_manager, "get_all_text_ai_models"):
            return []
        try:
            models = list(self.model_manager.get_all_text_ai_models())
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to load text ai models for settings page: %s", exc)
            return []
        return [
            model
            for model in models
            if model.family == family and model.runtime == runtime and model.is_downloaded
        ]

    def _format_model_option_label(self, display_name: str, runtime: str, family: str) -> str:
        runtime_label = self.i18n.t(f"settings.workspace_ai.runtime_{runtime}")
        family_label = self.i18n.t(f"settings.workspace_ai.family_{family}")
        return f"{display_name} ({runtime_label} / {family_label})"

    def _has_available_model(
        self,
        *,
        family: str,
        runtime: str,
        model_id: Optional[str] = None,
    ) -> bool:
        available_ids = self._available_model_ids.get((family, runtime), set())
        if model_id is not None:
            return model_id in available_ids
        return bool(available_ids)

    def _set_combo_value(self, combo: QComboBox, value: Optional[str]) -> None:
        if not value:
            return
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)

    def _get_preferences(self) -> dict:
        defaults = {
            "default_summary_strategy": SUMMARY_STRATEGIES[0][0],
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
        if model_page and hasattr(model_page, "focus_section"):
            model_page.focus_section("text_ai")

    def _on_summary_provider_changed(self, provider_id: str, *, emit_changed: bool = True) -> None:
        has_summary_models = self._has_available_model(family="summary", runtime="onnx")
        use_local_models = provider_id == "onnx"
        self.summary_model_row.setVisible(use_local_models)
        self.summary_model_combo.setEnabled(has_summary_models)
        self.summary_provider_hint.setVisible(use_local_models and not has_summary_models)
        self.summary_provider_hint.setText(
            self.i18n.t("settings.workspace_ai.summary_provider_download_hint")
        )
        self.summary_model_management_button.setVisible(use_local_models and not has_summary_models)
        if emit_changed:
            self._emit_changed()

    def _on_meeting_provider_changed(self, provider_id: str, *, emit_changed: bool = True) -> None:
        has_meeting_models = self._has_available_model(family="meeting", runtime="gguf")
        use_gguf = provider_id == "gguf"
        self.meeting_model_row.setVisible(use_gguf)
        self.meeting_model_combo.setEnabled(has_meeting_models)
        self.runtime_command_row.setVisible(use_gguf)
        self.runtime_hint_label.setVisible(use_gguf)
        self.meeting_provider_hint.setVisible(use_gguf and not has_meeting_models)
        self.meeting_provider_hint.setText(
            self.i18n.t("settings.workspace_ai.meeting_provider_download_hint")
        )
        self.meeting_model_management_button.setVisible(use_gguf and not has_meeting_models)
        if emit_changed:
            self._emit_changed()

    def _resolve_meeting_provider(self, model_id: str) -> str:
        model = None
        if self.model_manager is not None:
            getter = getattr(self.model_manager, "get_text_ai_model", None)
            if callable(getter):
                model = getter(model_id)
            elif hasattr(self.model_manager, "get_all_text_ai_models"):
                try:
                    model = next(
                        (
                            item
                            for item in self.model_manager.get_all_text_ai_models()
                            if item.model_id == model_id
                        ),
                        None,
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Failed to resolve meeting provider from text ai models: %s", exc)
        if model is not None and model.runtime == "gguf":
            return "gguf"
        return "extractive"

    def _on_text_ai_models_updated(self) -> None:
        current_summary = self.summary_model_combo.currentData()
        current_meeting = self.meeting_model_combo.currentData()
        self._populate_model_options(
            summary_model_id=current_summary,
            meeting_model_id=current_meeting,
        )
        self._on_summary_provider_changed(
            self.summary_provider_selector.current_provider() or "extractive",
            emit_changed=False,
        )
        self._on_meeting_provider_changed(
            self.meeting_provider_selector.current_provider() or "extractive",
            emit_changed=False,
        )

    def _create_row_widget(self, label_text: str, control: QWidget, *, parent_layout) -> tuple[QWidget, QLabel]:
        row_widget = QWidget()
        row_layout = create_hbox()
        row_widget.setLayout(row_layout)
        label = QLabel(label_text)
        label.setMinimumWidth(STANDARD_LABEL_WIDTH)
        row_layout.addWidget(label)
        row_layout.addWidget(control)
        row_layout.addStretch()
        parent_layout.addWidget(row_widget)
        return row_widget, label
