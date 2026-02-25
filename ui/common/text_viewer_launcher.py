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
"""Shared launcher for transcript/translation viewer dialogs."""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Optional

from core.qt_imports import QWidget
from ui.common.dialog_launcher_utils import bind_dialog_cache_cleanup, show_and_activate_dialog
from ui.common.transcript_translation_viewer import (
    VIEW_MODE_COMPARE,
    VIEW_MODE_TRANSCRIPT,
    VIEW_MODE_TRANSLATION,
    TranscriptTranslationViewerDialog,
)
from utils.i18n import I18nQtManager


def resolve_text_viewer_initial_mode(
    *,
    transcript_path: Optional[str],
    translation_path: Optional[str],
    preferred_mode: Optional[str] = None,
) -> str:
    """Resolve initial text viewer mode from available artifacts."""
    if preferred_mode == VIEW_MODE_TRANSLATION and translation_path:
        return VIEW_MODE_TRANSLATION
    if transcript_path and translation_path:
        return VIEW_MODE_COMPARE
    if translation_path:
        return VIEW_MODE_TRANSLATION
    return VIEW_MODE_TRANSCRIPT


def open_or_activate_text_viewer(
    *,
    i18n: I18nQtManager,
    dialog_cache: Dict[str, Any],
    parent: QWidget,
    transcript_path: Optional[str],
    translation_path: Optional[str],
    initial_mode: str,
    title_key: str,
    show_warning: Callable[[str, str], None],
    parent_hint: Optional[QWidget] = None,
    logger: Optional[logging.Logger] = None,
) -> None:
    """Open or focus transcript/translation viewer dialog with cache reuse."""
    if not transcript_path and not translation_path:
        show_warning(i18n.t("common.warning"), i18n.t("viewer.file_not_found"))
        return

    cache_key = f"{transcript_path or ''}|{translation_path or ''}"
    existing_dialog = dialog_cache.get(cache_key)
    if existing_dialog:
        viewer = getattr(existing_dialog, "viewer", None)
        if viewer is not None:
            viewer.set_view_mode(initial_mode)
        existing_dialog._title_key = title_key
        existing_dialog.setWindowTitle(i18n.t(title_key))
        show_and_activate_dialog(existing_dialog)
        if logger:
            logger.info("Activated text viewer for %s", cache_key)
        return

    dialog_parent = parent_hint if parent_hint is not None else parent
    dialog = TranscriptTranslationViewerDialog(
        i18n=i18n,
        transcript_path=transcript_path,
        translation_path=translation_path,
        initial_mode=initial_mode,
        title_key=title_key,
        parent=dialog_parent,
    )
    dialog_cache[cache_key] = dialog

    bind_dialog_cache_cleanup(
        dialog_cache=dialog_cache,
        cache_key=cache_key,
        dialog=dialog,
        on_cleanup=(lambda: logger.debug("Closed text viewer for %s", cache_key)) if logger else None,
    )
    show_and_activate_dialog(dialog)
    if logger:
        logger.info("Opened text viewer for %s", cache_key)
