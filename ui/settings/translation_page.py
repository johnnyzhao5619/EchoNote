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
"""Translation settings page.

Provides UI for configuring shared translation defaults used by batch and
realtime workflows.
"""

import logging
from typing import Any, Dict, Optional, Tuple

from core.qt_imports import QComboBox, QLabel

from config.constants import (
    DEFAULT_TRANSLATION_TARGET_LANGUAGE,
    SUPPORTED_REALTIME_TRANSLATION_ENGINES,
    TRANSLATION_ENGINE_NONE,
    TRANSLATION_ENGINE_GOOGLE,
    TRANSLATION_ENGINE_OPUS_MT,
    TRANSLATION_LANGUAGE_AUTO,
)
from core.settings.manager import resolve_translation_languages_from_settings
from ui.base_widgets import create_button, create_hbox
from ui.constants import ROLE_DEVICE_INFO, ROLE_SETTINGS_INLINE_ACTION, STANDARD_LABEL_WIDTH
from ui.settings.components.provider_selector import ProviderOptionSpec, ProviderSelectorWidget
from ui.settings.base_page import BaseSettingsPage
from utils.i18n import I18nQtManager, LANGUAGE_OPTION_KEYS

logger = logging.getLogger("echonote.ui.settings.translation")


class TranslationSettingsPage(BaseSettingsPage):
    """Settings page for shared translation defaults."""

    def __init__(
        self,
        settings_manager,
        i18n: I18nQtManager,
        managers: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(settings_manager, i18n)
        self.managers = managers or {}
        self.setup_ui()

    def setup_ui(self) -> None:
        self.defaults_title = self.add_section_title(self.i18n.t("settings.translation.defaults"))

        self.description_label = QLabel(self.i18n.t("settings.translation.description"))
        self.description_label.setProperty("role", ROLE_DEVICE_INFO)
        self.description_label.setWordWrap(True)
        self.content_layout.addWidget(self.description_label)

        self.engine_label = QLabel(self.i18n.t("settings.translation.provider"))
        self.engine_label.setMinimumWidth(STANDARD_LABEL_WIDTH)
        self.content_layout.addWidget(self.engine_label)

        self.engine_combo = QComboBox()
        self._populate_engine_options()
        self.engine_combo.currentIndexChanged.connect(self._on_translation_engine_changed)
        self.engine_combo.currentTextChanged.connect(self._emit_changed)
        self.engine_combo.hide()
        self.content_layout.addWidget(self.engine_combo)

        self.provider_selector = ProviderSelectorWidget()
        self.provider_selector.provider_changed.connect(self._on_provider_selected)
        self.content_layout.addWidget(self.provider_selector)
        self._configure_provider_selector()

        source_target_layout = create_hbox()
        self.source_label = QLabel(self.i18n.t("settings.translation.source_language"))
        self.source_label.setMinimumWidth(STANDARD_LABEL_WIDTH)
        self.source_combo = QComboBox()
        self.target_label = QLabel(self.i18n.t("settings.translation.target_language"))
        self.target_combo = QComboBox()
        source_target_layout.addWidget(self.source_label)
        source_target_layout.addWidget(self.source_combo)
        source_target_layout.addWidget(self.target_label)
        source_target_layout.addWidget(self.target_combo)
        source_target_layout.addStretch()
        self.content_layout.addLayout(source_target_layout)

        self.opus_mt_status_label = QLabel()
        self.opus_mt_status_label.setProperty("role", ROLE_DEVICE_INFO)
        self.opus_mt_status_label.setWordWrap(True)
        self.content_layout.addWidget(self.opus_mt_status_label)

        self.provider_status_label = QLabel()
        self.provider_status_label.setProperty("role", ROLE_DEVICE_INFO)
        self.provider_status_label.setWordWrap(True)
        self.content_layout.addWidget(self.provider_status_label)

        actions_layout = create_hbox()
        self.download_button = create_button(self.i18n.t("batch_transcribe.go_to_download"))
        self.download_button.setProperty("role", ROLE_SETTINGS_INLINE_ACTION)
        self.download_button.clicked.connect(self._on_go_to_model_management)
        actions_layout.addWidget(self.download_button)

        self.credentials_button = create_button(
            self.i18n.t("settings.translation.configure_google_credentials")
        )
        self.credentials_button.setProperty("role", ROLE_SETTINGS_INLINE_ACTION)
        self.credentials_button.clicked.connect(self._on_go_to_transcription_settings)
        actions_layout.addWidget(self.credentials_button)
        actions_layout.addStretch()
        self.content_layout.addLayout(actions_layout)

        self._populate_language_options()
        self.source_combo.currentIndexChanged.connect(self._emit_changed)
        self.source_combo.currentIndexChanged.connect(self._update_opus_mt_status)
        self.target_combo.currentIndexChanged.connect(self._emit_changed)
        self.target_combo.currentIndexChanged.connect(self._update_opus_mt_status)

        self.add_section_spacing()
        self.content_layout.addStretch()

    def _configure_provider_selector(self) -> None:
        current_provider = self.engine_combo.currentData() or TRANSLATION_ENGINE_NONE
        self.provider_selector.set_options(
            (
                ProviderOptionSpec(
                    provider_id=TRANSLATION_ENGINE_NONE,
                    title=self.i18n.t("settings.translation.provider_none"),
                    description=self.i18n.t("settings.translation.provider_none_desc"),
                    badge=self.i18n.t("settings.translation.provider_badge_off"),
                ),
                ProviderOptionSpec(
                    provider_id=TRANSLATION_ENGINE_OPUS_MT,
                    title=self.i18n.t("settings.translation.provider_opus_mt"),
                    description=self.i18n.t("settings.translation.provider_opus_mt_desc"),
                    badge=self.i18n.t("settings.translation.provider_badge_local"),
                ),
                ProviderOptionSpec(
                    provider_id=TRANSLATION_ENGINE_GOOGLE,
                    title=self.i18n.t("settings.translation.provider_google"),
                    description=self.i18n.t("settings.translation.provider_google_desc"),
                    badge=self.i18n.t("settings.translation.provider_badge_cloud"),
                ),
            ),
            selected_id=current_provider,
        )

    def _on_provider_selected(self, provider_id: str) -> None:
        index = self.engine_combo.findData(provider_id)
        if index >= 0 and self.engine_combo.currentIndex() != index:
            self.engine_combo.setCurrentIndex(index)
            return
        self._on_translation_engine_changed()

    def load_settings(self) -> None:
        try:
            preferences: Dict[str, Any] = {}
            if hasattr(self.settings_manager, "get_translation_preferences"):
                loaded = self.settings_manager.get_translation_preferences()
                if isinstance(loaded, dict):
                    preferences = loaded

            selected_engine = preferences.get(
                "translation_engine",
                self.settings_manager.get_setting("translation.translation_engine"),
            )
            if selected_engine in SUPPORTED_REALTIME_TRANSLATION_ENGINES:
                index = self.engine_combo.findData(selected_engine)
                if index >= 0:
                    self.engine_combo.setCurrentIndex(index)

            resolved_languages = resolve_translation_languages_from_settings(self.settings_manager)
            source_lang = resolved_languages.get("translation_source_lang")
            if source_lang:
                index = self.source_combo.findData(source_lang)
                if index >= 0:
                    self.source_combo.setCurrentIndex(index)

            target_lang = resolved_languages.get("translation_target_lang")
            if target_lang:
                index = self.target_combo.findData(target_lang)
                if index >= 0:
                    self.target_combo.setCurrentIndex(index)

            self._on_translation_engine_changed()
            logger.debug("Translation settings loaded")
        except Exception as exc:  # noqa: BLE001
            logger.error("Error loading translation settings: %s", exc)

    def save_settings(self) -> None:
        try:
            translation_engine = self.engine_combo.currentData()
            if translation_engine is None:
                translation_engine = TRANSLATION_ENGINE_NONE
            self._set_setting_or_raise("translation.translation_engine", translation_engine)

            source_lang = self.source_combo.currentData() or TRANSLATION_LANGUAGE_AUTO
            target_lang = self.target_combo.currentData() or DEFAULT_TRANSLATION_TARGET_LANGUAGE
            self._set_setting_or_raise("translation.translation_source_lang", source_lang)
            self._set_setting_or_raise("translation.translation_target_lang", target_lang)
        except Exception as exc:  # noqa: BLE001
            logger.error("Error saving translation settings: %s", exc)
            raise

    def validate_settings(self) -> Tuple[bool, str]:
        return True, ""

    def update_translations(self) -> None:
        if hasattr(self, "defaults_title"):
            self.defaults_title.setText(self.i18n.t("settings.translation.defaults"))
        if hasattr(self, "description_label"):
            self.description_label.setText(self.i18n.t("settings.translation.description"))
        if hasattr(self, "engine_label"):
            self.engine_label.setText(self.i18n.t("settings.translation.provider"))
        if hasattr(self, "provider_selector"):
            self._configure_provider_selector()
        if hasattr(self, "source_label"):
            self.source_label.setText(self.i18n.t("settings.translation.source_language"))
        if hasattr(self, "target_label"):
            self.target_label.setText(self.i18n.t("settings.translation.target_language"))
        if hasattr(self, "download_button"):
            self.download_button.setText(self.i18n.t("batch_transcribe.go_to_download"))
        if hasattr(self, "credentials_button"):
            self.credentials_button.setText(
                self.i18n.t("settings.translation.configure_google_credentials")
            )

        if hasattr(self, "engine_combo"):
            current_engine = self.engine_combo.currentData()
            self.engine_combo.blockSignals(True)
            self._populate_engine_options()
            index = self.engine_combo.findData(current_engine)
            if index >= 0:
                self.engine_combo.setCurrentIndex(index)
            self.engine_combo.blockSignals(False)

        if hasattr(self, "source_combo") and hasattr(self, "target_combo"):
            current_source = self.source_combo.currentData()
            current_target = self.target_combo.currentData()
            self._populate_language_options()
            source_index = self.source_combo.findData(current_source)
            if source_index >= 0:
                self.source_combo.setCurrentIndex(source_index)
            target_index = self.target_combo.findData(current_target)
            if target_index >= 0:
                self.target_combo.setCurrentIndex(target_index)

        self._update_opus_mt_status()

    def _populate_engine_options(self) -> None:
        if not hasattr(self, "engine_combo"):
            return

        self.engine_combo.clear()
        for engine in SUPPORTED_REALTIME_TRANSLATION_ENGINES:
            label = self.i18n.t(f"settings.translation.engine_{engine}")
            self.engine_combo.addItem(label, engine)

    def _populate_language_options(self) -> None:
        self.source_combo.blockSignals(True)
        self.target_combo.blockSignals(True)

        current_source = self.source_combo.currentData() or TRANSLATION_LANGUAGE_AUTO
        current_target = self.target_combo.currentData() or DEFAULT_TRANSLATION_TARGET_LANGUAGE

        self.source_combo.clear()
        self.target_combo.clear()

        self.source_combo.addItem(
            self.i18n.t("settings.translation.auto_detect"), TRANSLATION_LANGUAGE_AUTO
        )
        for code, label_key in LANGUAGE_OPTION_KEYS:
            self.source_combo.addItem(self.i18n.t(label_key), code)
            self.target_combo.addItem(self.i18n.t(label_key), code)

        source_index = self.source_combo.findData(current_source)
        if source_index >= 0:
            self.source_combo.setCurrentIndex(source_index)

        target_index = self.target_combo.findData(current_target)
        if target_index >= 0:
            self.target_combo.setCurrentIndex(target_index)

        self.source_combo.blockSignals(False)
        self.target_combo.blockSignals(False)

    def _update_opus_mt_status(self) -> None:
        if not hasattr(self, "opus_mt_status_label"):
            return

        if self.engine_combo.currentData() != TRANSLATION_ENGINE_OPUS_MT:
            self.opus_mt_status_label.clear()
            return

        source = self.source_combo.currentData() or TRANSLATION_LANGUAGE_AUTO
        target = self.target_combo.currentData() or DEFAULT_TRANSLATION_TARGET_LANGUAGE
        model_manager = self.managers.get("model_manager") if hasattr(self, "managers") else None
        if not model_manager:
            self.opus_mt_status_label.clear()
            return

        model_info = model_manager.get_best_translation_model(
            source,
            target,
            auto_detect=(source == TRANSLATION_LANGUAGE_AUTO),
        )

        if model_info and model_info.is_downloaded:
            self.opus_mt_status_label.setText(
                self.i18n.t("settings.translation.opus_mt_ready", model=model_info.model_id)
            )
        elif model_info:
            self.opus_mt_status_label.setText(
                self.i18n.t(
                    "settings.translation.opus_mt_not_downloaded",
                    model=model_info.model_id,
                )
            )
        else:
            self.opus_mt_status_label.clear()

    def _update_provider_status(self) -> None:
        selected_provider = self.engine_combo.currentData()
        if selected_provider == TRANSLATION_ENGINE_GOOGLE:
            secrets_manager = self.managers.get("secrets_manager") if hasattr(self, "managers") else None
            api_key = ""
            if secrets_manager is not None:
                getter = getattr(secrets_manager, "get_api_key", None)
                if callable(getter):
                    try:
                        api_key = str(getter("google") or "").strip()
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("Failed to load shared Google credential status: %s", exc)
            if api_key:
                self.provider_status_label.setText(
                    self.i18n.t("settings.translation.google_credentials_ready")
                )
            else:
                self.provider_status_label.setText(
                    self.i18n.t("settings.translation.google_credentials_missing")
                )
            return

        if selected_provider == TRANSLATION_ENGINE_OPUS_MT:
            self.provider_status_label.setText(
                self.i18n.t("settings.translation.opus_mt_provider_hint")
            )
            return

        self.provider_status_label.setText(self.i18n.t("settings.translation.provider_none_hint"))

    def _on_translation_engine_changed(self) -> None:
        selected_engine = self.engine_combo.currentData()
        if hasattr(self, "provider_selector") and selected_engine:
            self.provider_selector.set_current_provider(selected_engine, emit_signal=False)
        is_opus = selected_engine == TRANSLATION_ENGINE_OPUS_MT
        is_google = selected_engine == TRANSLATION_ENGINE_GOOGLE
        self.opus_mt_status_label.setVisible(is_opus)
        self.download_button.setVisible(is_opus)
        self.credentials_button.setVisible(is_google)
        self._update_provider_status()
        if is_opus:
            self._update_opus_mt_status()
        else:
            self.opus_mt_status_label.clear()

    def _on_go_to_model_management(self) -> None:
        model_page = self._open_settings_page("model_management")
        if model_page and hasattr(model_page, "focus_section"):
            model_page.focus_section("translation")

    def _on_go_to_transcription_settings(self) -> None:
        self._open_settings_page("transcription")
