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
"""Shared helpers for widget style refresh operations."""

from __future__ import annotations

from typing import Optional

from core.qt_imports import QWidget


def refresh_widget_style(widget: Optional[QWidget]) -> None:
    """Re-apply style for a widget after semantic property changes."""
    if widget is None:
        return

    style = widget.style()
    if style is not None:
        style.unpolish(widget)
        style.polish(widget)
    widget.update()


def set_widget_dynamic_property(widget: Optional[QWidget], name: str, value: object) -> None:
    """Set dynamic property and immediately refresh theme-dependent style."""
    if widget is None:
        return
    widget.setProperty(name, value)
    refresh_widget_style(widget)


def set_widget_state(widget: Optional[QWidget], state: object) -> None:
    """Set semantic ``state`` property and refresh style."""
    set_widget_dynamic_property(widget, "state", state)
