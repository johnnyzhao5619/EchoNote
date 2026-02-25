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
from core.settings.manager import resolve_translation_languages_from_settings


def build_event_translation_task_options(
    *,
    settings_manager: Optional[object],
    event_id: str,
    transcript_path: str,
) -> Dict[str, Any]:
    """Build normalized translation task options for event transcript translation."""
    resolved_languages = resolve_translation_languages_from_settings(settings_manager)
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
