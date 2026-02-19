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
"""Shared navigation definitions for the desktop UI shell."""

from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class NavigationItem:
    """Navigation metadata used by sidebar and main window shell."""

    page_name: str
    text_key: str
    icon_name: str
    shortcut_index: int
    aliases: Tuple[str, ...] = ()


NAV_ITEMS: Tuple[NavigationItem, ...] = (
    NavigationItem(
        page_name="batch_transcribe",
        text_key="sidebar.batch_transcribe",
        icon_name="file_list",
        shortcut_index=1,
        aliases=("batch", "transcribe", "queue"),
    ),
    NavigationItem(
        page_name="realtime_record",
        text_key="sidebar.realtime_record",
        icon_name="record",
        shortcut_index=2,
        aliases=("record", "realtime", "mic"),
    ),
    NavigationItem(
        page_name="calendar_hub",
        text_key="sidebar.calendar_hub",
        icon_name="calendar",
        shortcut_index=3,
        aliases=("calendar", "schedule"),
    ),
    NavigationItem(
        page_name="timeline",
        text_key="sidebar.timeline",
        icon_name="timeline",
        shortcut_index=4,
        aliases=("timeline", "history"),
    ),
    NavigationItem(
        page_name="settings",
        text_key="sidebar.settings",
        icon_name="settings",
        shortcut_index=5,
        aliases=("settings", "preferences", "config"),
    ),
)

NAV_PAGE_ORDER: Tuple[str, ...] = tuple(item.page_name for item in NAV_ITEMS)
