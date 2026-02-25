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
"""Shared helpers for calendar/timeline translation task options."""

import logging
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from config.constants import DEFAULT_TRANSLATION_TARGET_LANGUAGE, TRANSLATION_LANGUAGE_AUTO
from core.qt_imports import QApplication, QComboBox, QDialog, QFormLayout, QVBoxLayout, QWidget
from core.settings.manager import resolve_translation_languages_from_settings
from ui.base_widgets import (
    connect_button_with_callback,
    create_button,
    create_hbox,
    create_primary_button,
)
from ui.constants import ROLE_DIALOG_PRIMARY_ACTION, ROLE_DIALOG_SECONDARY_ACTION
from utils.i18n import I18nQtManager, LANGUAGE_OPTION_KEYS


def _build_language_combo(i18n: I18nQtManager, selected_code: str) -> QComboBox:
    """Create language combo initialized with localized labels and selected code."""
    combo = QComboBox()
    for code, label_key in LANGUAGE_OPTION_KEYS:
        combo.addItem(i18n.t(label_key), code)

    selected_index = combo.findData(selected_code)
    if selected_index < 0 and combo.count() > 0:
        selected_index = 0
    if selected_index >= 0:
        combo.setCurrentIndex(selected_index)
    return combo


def prompt_event_translation_languages(
    *,
    parent: Optional[QWidget],
    i18n: I18nQtManager,
    settings_manager: Optional[object],
) -> Optional[Dict[str, str]]:
    """Prompt source/target languages before scheduling event translation."""
    defaults = resolve_translation_languages_from_settings(settings_manager)
    source_lang = defaults.get("translation_source_lang", TRANSLATION_LANGUAGE_AUTO)
    target_lang = defaults.get("translation_target_lang", DEFAULT_TRANSLATION_TARGET_LANGUAGE)

    dialog_parent = QApplication.activeModalWidget() or parent
    dialog = QDialog(dialog_parent)
    dialog.setWindowTitle(i18n.t("timeline.translate_transcript"))
    dialog.setMinimumWidth(420)

    layout = QVBoxLayout(dialog)

    form_layout = QFormLayout()
    source_combo = _build_language_combo(i18n, source_lang)
    target_combo = _build_language_combo(i18n, target_lang)
    form_layout.addRow(i18n.t("settings.translation.source_language"), source_combo)
    form_layout.addRow(i18n.t("settings.translation.target_language"), target_combo)
    layout.addLayout(form_layout)

    action_layout = create_hbox()
    action_layout.addStretch()

    cancel_btn = create_button(i18n.t("common.cancel"))
    cancel_btn.setProperty("role", ROLE_DIALOG_SECONDARY_ACTION)
    connect_button_with_callback(cancel_btn, dialog.reject)

    confirm_btn = create_primary_button(i18n.t("common.ok"))
    confirm_btn.setProperty("role", ROLE_DIALOG_PRIMARY_ACTION)
    connect_button_with_callback(confirm_btn, dialog.accept)

    action_layout.addWidget(cancel_btn)
    action_layout.addWidget(confirm_btn)
    layout.addLayout(action_layout)

    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None

    return resolve_translation_languages_from_settings(
        settings_manager,
        source_lang=source_combo.currentData(),
        target_lang=target_combo.currentData(),
    )


def build_event_translation_task_options(
    *,
    settings_manager: Optional[object],
    event_id: str,
    transcript_path: str,
    source_lang: Optional[str] = None,
    target_lang: Optional[str] = None,
) -> Dict[str, Any]:
    """Build normalized translation task options for event transcript translation."""
    resolved_languages = resolve_translation_languages_from_settings(
        settings_manager,
        source_lang=source_lang,
        target_lang=target_lang,
    )
    source_lang = resolved_languages.get("translation_source_lang", TRANSLATION_LANGUAGE_AUTO)
    target_lang = resolved_languages.get(
        "translation_target_lang", DEFAULT_TRANSLATION_TARGET_LANGUAGE
    )

    output_suffix = Path(transcript_path).suffix.lower()
    output_format = "md" if output_suffix == ".md" else "txt"

    return {
        "event_id": event_id,
        "translation_source_lang": source_lang,
        "translation_target_lang": target_lang,
        "output_format": output_format,
    }


def enqueue_event_translation_task(
    *,
    transcription_manager: Optional[Any],
    settings_manager: Optional[object],
    event_id: str,
    transcript_path: str,
    logger: logging.Logger,
    context_label: str,
    on_missing_transcript: Optional[Callable[[], None]] = None,
    on_translation_unavailable: Optional[Callable[[], None]] = None,
    on_queued: Optional[Callable[[], None]] = None,
    on_failed: Optional[Callable[[Exception], None]] = None,
    translation_source_lang: Optional[str] = None,
    translation_target_lang: Optional[str] = None,
) -> bool:
    """Queue event-bound translation task with shared validation and error handling."""
    if not transcription_manager:
        return False

    if not transcript_path:
        if on_missing_transcript:
            on_missing_transcript()
        return False

    if getattr(transcription_manager, "translation_engine", None) is None:
        if on_translation_unavailable:
            on_translation_unavailable()
        return False

    options = build_event_translation_task_options(
        settings_manager=settings_manager,
        event_id=event_id,
        transcript_path=transcript_path,
        source_lang=translation_source_lang,
        target_lang=translation_target_lang,
    )

    try:
        transcription_manager.add_translation_task(transcript_path, options=options)
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "Failed to queue %s for event %s: %s",
            context_label,
            event_id,
            exc,
            exc_info=True,
        )
        if on_failed:
            on_failed(exc)
        return False

    if on_queued:
        on_queued()
    return True
