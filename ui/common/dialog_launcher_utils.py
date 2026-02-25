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
"""Shared helpers for cache-aware dialog launchers."""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional


def show_and_activate_dialog(dialog: Any) -> None:
    """Show a dialog and bring it to the foreground."""
    dialog.show()
    dialog.raise_()
    dialog.activateWindow()


def bind_dialog_cache_cleanup(
    *,
    dialog_cache: Dict[str, Any],
    cache_key: str,
    dialog: Any,
    on_cleanup: Optional[Callable[[], None]] = None,
) -> None:
    """Remove cached dialog entry once the dialog is finished or destroyed."""

    def _cleanup_dialog(*_) -> None:
        tracked_dialog = dialog_cache.get(cache_key)
        if tracked_dialog is dialog:
            dialog_cache.pop(cache_key, None)
            if on_cleanup is not None:
                on_cleanup()

    dialog.finished.connect(_cleanup_dialog)
    dialog.destroyed.connect(_cleanup_dialog)
