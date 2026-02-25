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
"""Shared audio player launcher helpers for timeline-like playback entrypoints."""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Optional

from core.qt_imports import QWidget
from ui.common.dialog_launcher_utils import bind_dialog_cache_cleanup, show_and_activate_dialog
from utils.i18n import I18nQtManager

try:
    from ui.common.audio_player import AudioPlayerDialog
except Exception as exc:  # pragma: no cover - degraded multimedia/runtime environments
    AudioPlayerDialog = None
    _AUDIO_PLAYER_IMPORT_ERROR = exc
else:
    _AUDIO_PLAYER_IMPORT_ERROR = None


def _show_audio_unavailable(
    *, i18n: I18nQtManager, show_warning: Callable[[str, str], None]
) -> None:
    """Display a consistent warning when audio playback cannot be initialized."""
    show_warning(
        i18n.t("timeline.audio_player_unavailable_title"),
        i18n.t("timeline.audio_player_unavailable_message"),
    )


def open_or_activate_audio_player(
    *,
    file_path: str,
    i18n: I18nQtManager,
    parent: QWidget,
    dialog_cache: Dict[str, Any],
    logger: logging.Logger,
    show_warning: Callable[[str, str], None],
    show_error: Callable[[str, str], None],
    transcript_path: Optional[str] = None,
    translation_path: Optional[str] = None,
    cache_key: Optional[str] = None,
) -> None:
    """Open or focus the shared timeline audio player dialog."""
    if AudioPlayerDialog is None:
        if _AUDIO_PLAYER_IMPORT_ERROR is not None:
            logger.warning(
                "Audio playback component import failed for %s: %s",
                file_path,
                _AUDIO_PLAYER_IMPORT_ERROR,
            )
        _show_audio_unavailable(i18n=i18n, show_warning=show_warning)
        return

    key = cache_key or file_path

    try:
        existing_dialog = dialog_cache.get(key)
        if existing_dialog is not None:
            existing_dialog.player.load_file(file_path, transcript_path, translation_path)
            show_and_activate_dialog(existing_dialog)
            logger.info("Activated existing audio player for %s", file_path)
            return

        dialog = AudioPlayerDialog(file_path, i18n, parent, transcript_path, translation_path)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to create audio player dialog for %s", file_path)
        show_error(
            i18n.t("timeline.audio_player_open_failed_title"),
            i18n.t("timeline.audio_player_open_failed_message", error=str(exc)),
        )
        return

    dialog_cache[key] = dialog

    try:
        bind_dialog_cache_cleanup(
            dialog_cache=dialog_cache,
            cache_key=key,
            dialog=dialog,
            on_cleanup=lambda: logger.debug("Closed audio player for %s", file_path),
        )
        show_and_activate_dialog(dialog)
        logger.info("Opened audio player for %s", file_path)
    except Exception as exc:  # noqa: BLE001
        dialog_cache.pop(key, None)
        logger.exception("Failed to display audio player dialog for %s", file_path)
        show_error(
            i18n.t("timeline.audio_player_open_failed_title"),
            i18n.t("timeline.audio_player_open_failed_message", error=str(exc)),
        )
