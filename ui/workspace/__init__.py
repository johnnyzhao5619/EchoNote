# SPDX-License-Identifier: Apache-2.0
"""Workspace UI module."""

from .editor_panel import TextEditorPanel, WorkspaceEditorPanel
from .item_list import WorkspaceItemList
from .recording_panel import WorkspaceRecordingPanel
from .task_panel import WorkspaceTaskPanel
from .task_window import WorkspaceTaskWindow
from .tool_rail import WorkspaceToolRail
from .toolbar import WorkspaceToolbar
from .widget import WorkspaceWidget

__all__ = [
    "TextEditorPanel",
    "WorkspaceEditorPanel",
    "WorkspaceItemList",
    "WorkspaceRecordingPanel",
    "WorkspaceTaskPanel",
    "WorkspaceTaskWindow",
    "WorkspaceToolRail",
    "WorkspaceToolbar",
    "WorkspaceWidget",
]
