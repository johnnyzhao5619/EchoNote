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
"""Dialog for selecting secondary transcription model."""

from __future__ import annotations

import logging
from typing import Any, Dict, Iterable, List, Optional

from core.qt_imports import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from ui.base_widgets import connect_button_with_callback, create_button, create_primary_button

logger = logging.getLogger("echonote.ui.common.secondary_transcribe_dialog")


def list_downloaded_transcription_models(model_manager=None) -> List[Any]:
    """Return downloaded transcription model objects from the shared model manager."""
    if model_manager is None or not hasattr(model_manager, "get_downloaded_models"):
        return []
    try:
        models = model_manager.get_downloaded_models()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to load downloaded transcription models: %s", exc)
        return []
    if not isinstance(models, (list, tuple)):
        return []
    return [model for model in models if getattr(model, "name", None)]


def build_transcription_model_payload(model_info: Any) -> Optional[Dict[str, str]]:
    """Normalize a model-manager record into lightweight runtime options."""
    if model_info is None:
        return None
    model_name = str(getattr(model_info, "name", "") or "").strip()
    if not model_name:
        return None
    return {
        "model_name": model_name,
        "model_path": str(getattr(model_info, "local_path", "") or ""),
    }


def resolve_preferred_downloaded_transcription_model(
    model_manager=None,
    *,
    preferred_names: Optional[Iterable[str]] = None,
) -> Optional[Dict[str, str]]:
    """Pick the first downloaded model matching preferred names, otherwise the first download."""
    downloaded_models = list_downloaded_transcription_models(model_manager)
    if not downloaded_models:
        return None

    downloaded_by_name = {
        str(getattr(model, "name", "") or "").strip(): model for model in downloaded_models
    }
    for preferred_name in preferred_names or ():
        normalized = str(preferred_name or "").strip()
        if normalized and normalized in downloaded_by_name:
            return build_transcription_model_payload(downloaded_by_name[normalized])
    return build_transcription_model_payload(downloaded_models[0])


class SecondaryTranscribeDialog(QDialog):
    """Prompt user to choose a model for secondary transcription."""

    def __init__(
        self,
        *,
        i18n,
        model_manager=None,
        settings_manager=None,
        preferred_model_name: str = "",
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.i18n = i18n
        self.model_manager = model_manager
        self.settings_manager = settings_manager
        self.preferred_model_name = str(preferred_model_name or "").strip()
        self.model_combo: Optional[QComboBox] = None
        self._confirm_button: Optional[QPushButton] = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setWindowTitle(self.i18n.t("realtime_record.secondary_transcription_prompt_title"))
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)

        message = QLabel(self.i18n.t("realtime_record.secondary_transcription_prompt_message"))
        message.setWordWrap(True)
        layout.addWidget(message)

        model_row = QHBoxLayout()
        model_label = QLabel(self.i18n.t("settings.transcription.secondary_model_size"))
        model_row.addWidget(model_label)

        self.model_combo = QComboBox()
        model_row.addWidget(self.model_combo, 1)
        layout.addLayout(model_row)

        actions = QHBoxLayout()
        actions.addStretch()
        cancel_button = create_button(self.i18n.t("common.cancel"))
        confirm_button = create_primary_button(self.i18n.t("common.ok"))
        connect_button_with_callback(cancel_button, self.reject)
        connect_button_with_callback(confirm_button, self.accept)
        actions.addWidget(cancel_button)
        actions.addWidget(confirm_button)
        layout.addLayout(actions)
        self._confirm_button = confirm_button

        self._populate_models()

    def _populate_models(self) -> None:
        if self.model_combo is None:
            return

        self.model_combo.clear()
        downloaded_models = list_downloaded_transcription_models(self.model_manager)

        if not downloaded_models:
            self.model_combo.addItem(self.i18n.t("realtime_record.no_models_available"), None)
            self.model_combo.setEnabled(False)
            if self._confirm_button is not None:
                self._confirm_button.setEnabled(False)
            return

        preferred_model = None
        if self.preferred_model_name:
            preferred_model = self.preferred_model_name
        elif self.settings_manager is not None and hasattr(self.settings_manager, "get_setting"):
            preferred_model = self.settings_manager.get_setting("transcription.secondary_model_size")
            if not preferred_model:
                preferred_model = self.settings_manager.get_setting(
                    "transcription.faster_whisper.model_size"
                )

        for model in downloaded_models:
            self.model_combo.addItem(model.name, model)

        if preferred_model:
            index = self.model_combo.findText(preferred_model)
            if index >= 0:
                self.model_combo.setCurrentIndex(index)

    def get_selected_model(self) -> Optional[Dict[str, str]]:
        if self.model_combo is None or not self.model_combo.isEnabled():
            return None

        model_info = self.model_combo.currentData()
        return build_transcription_model_payload(model_info)


def select_secondary_transcribe_model(
    *,
    parent: Optional[QWidget],
    i18n,
    model_manager=None,
    settings_manager=None,
    preferred_model_name: str = "",
) -> Optional[Dict[str, str]]:
    """Show model-selection dialog and return selected model options."""
    dialog = SecondaryTranscribeDialog(
        i18n=i18n,
        model_manager=model_manager,
        settings_manager=settings_manager,
        preferred_model_name=preferred_model_name,
        parent=parent,
    )
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None
    return dialog.get_selected_model()
