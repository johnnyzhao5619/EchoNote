# SPDX-License-Identifier: Apache-2.0
"""Workspace UI module."""

from .editor_panel import TextEditorPanel, WorkspaceEditorPanel
from .item_list import WorkspaceItemList
from .recording_control_panel import WorkspaceRecordingControlPanel
from .recording_panel import WorkspaceRecordingPanel
from .task_panel import WorkspaceTaskPanel
from .toolbar import WorkspaceToolbar
from .widget import WorkspaceWidget

__all__ = [
    "TextEditorPanel",
    "WorkspaceEditorPanel",
    "WorkspaceItemList",
    "WorkspaceRecordingControlPanel",
    "WorkspaceRecordingPanel",
    "WorkspaceTaskPanel",
    "WorkspaceToolbar",
    "WorkspaceWidget",
]
