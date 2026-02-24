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
"""Timeline viewer compatibility wrapper.

The reusable implementation lives in ``ui.common.transcript_translation_viewer``.
This module keeps legacy imports stable.
"""

from typing import Optional

from core.qt_imports import QWidget
from ui.common.transcript_translation_viewer import (
    VIEW_MODE_TRANSCRIPT,
    VIEW_MODE_TRANSLATION,
    TranscriptTranslationViewer,
    TranscriptTranslationViewerDialog,
)
from utils.i18n import I18nQtManager


class TranscriptViewer(TranscriptTranslationViewer):
    """Backward-compatible transcript-only viewer class."""

    def __init__(self, file_path: str, i18n: I18nQtManager, parent: Optional[QWidget] = None):
        super().__init__(
            i18n=i18n,
            transcript_path=file_path,
            translation_path=None,
            initial_mode=VIEW_MODE_TRANSCRIPT,
            parent=parent,
        )


class TranscriptViewerDialog(TranscriptTranslationViewerDialog):
    """Backward-compatible dialog wrapper used by timeline callers."""

    def __init__(
        self,
        file_path: str,
        i18n: I18nQtManager,
        parent: Optional[QWidget] = None,
        *,
        title_key: Optional[str] = None,
    ):
        resolved_title_key = title_key or "transcript.viewer_title"
        initial_mode = VIEW_MODE_TRANSCRIPT
        transcript_path = file_path
        translation_path = None
        if resolved_title_key == "timeline.translation_viewer_title":
            initial_mode = VIEW_MODE_TRANSLATION
            transcript_path = None
            translation_path = file_path

        super().__init__(
            i18n=i18n,
            transcript_path=transcript_path,
            translation_path=translation_path,
            initial_mode=initial_mode,
            title_key=resolved_title_key,
            parent=parent,
        )
