# SPDX-License-Identifier: Apache-2.0
"""Tests for main window shell status and shortcuts."""

from unittest.mock import Mock, PropertyMock, patch

import ui.main_window as main_window_module
from core.qt_imports import QApplication
from core.workspace.manager import WorkspaceManager
from data.database.connection import DatabaseConnection
from data.storage.file_manager import FileManager
from ui.main_window import MainWindow
from ui.common.realtime_recording_dock import RealtimeRecordingDock
from ui.workspace.widget import WorkspaceWidget


def _build_i18n():
    i18n = Mock()

    def _t(key: str, **kwargs):
        mapping = {
            "app_shell.tasks_running": "Tasks: {count} running",
            "app_shell.recording_on": "Recording: active",
            "app_shell.recording_off": "Recording: idle",
            "logging.main_window.keyboard_shortcuts_configured": "shortcuts configured",
        }
        template = mapping.get(key, key)
        try:
            return template.format(**kwargs)
        except Exception:
            return template

    i18n.t = Mock(side_effect=_t)
    return i18n


def build_main_window_with_workspace(tmp_path):
    app = QApplication.instance() or QApplication([])
    db = DatabaseConnection(str(tmp_path / "main_window_shell.db"))
    db.initialize_schema()
    file_manager = FileManager(str(tmp_path / "files"))
    workspace_manager = WorkspaceManager(db, file_manager)

    realtime_recorder = Mock()
    type(realtime_recorder).is_recording = PropertyMock(return_value=False)

    managers = {
        "workspace_manager": workspace_manager,
        "realtime_recorder": realtime_recorder,
        "transcription_manager": None,
        "calendar_manager": None,
        "oauth_manager": None,
        "timeline_manager": None,
        "settings_manager": None,
    }

    def _create_workspace_only(self, content_area):
        workspace_widget = WorkspaceWidget(
            workspace_manager,
            self.i18n,
            realtime_recorder=realtime_recorder,
        )
        content_area.addWidget(workspace_widget)
        self.pages["workspace"] = workspace_widget

    with patch.object(MainWindow, "_create_pages", _create_workspace_only):
        window = MainWindow(managers, _build_i18n())

    window.show()
    app.processEvents()
    return window


def test_update_shell_status_sets_runtime_labels():
    fake_window = Mock()
    fake_window.task_status_label = Mock()
    fake_window.record_status_label = Mock()
    fake_window.i18n = _build_i18n()
    fake_window.managers = {"realtime_recorder": Mock(is_recording=True)}
    fake_window.theme_manager = Mock()
    fake_window.theme_manager.get_current_theme.return_value = "dark"
    fake_window._get_running_task_count = Mock(return_value=3)
    fake_window._update_resource_usage_status = Mock()

    MainWindow._update_shell_status(fake_window)

    fake_window.task_status_label.setText.assert_called_once_with("Tasks: 3 running")
    fake_window.record_status_label.setText.assert_called_once_with("Recording: active")
    fake_window._update_resource_usage_status.assert_called_once()


def test_update_shell_status_handles_idle_recording_state():
    fake_window = Mock()
    fake_window.task_status_label = Mock()
    fake_window.record_status_label = Mock()
    fake_window.i18n = _build_i18n()
    fake_window.managers = {"realtime_recorder": Mock(is_recording=False)}
    fake_window.theme_manager = Mock()
    fake_window.theme_manager.get_current_theme.return_value = "light"
    fake_window._get_running_task_count = Mock(return_value=0)
    fake_window._update_resource_usage_status = Mock()

    MainWindow._update_shell_status(fake_window)

    fake_window.record_status_label.setText.assert_called_once_with("Recording: idle")
    fake_window._update_resource_usage_status.assert_called_once()


def test_get_active_transcription_task_count_prefers_manager_runtime_count():
    fake_window = Mock()
    manager = Mock()
    manager.get_active_task_count.return_value = 2
    fake_window.managers = {
        "transcription_manager": manager,
        "db_connection": Mock(),
    }

    result = MainWindow._get_active_transcription_task_count(fake_window)

    assert result == 2
    manager.get_active_task_count.assert_called_once()


def test_setup_keyboard_shortcuts_registers_expected_sequences(monkeypatch):
    created = []

    class _FakeActivated:
        def connect(self, callback):
            self.callback = callback

    class _FakeShortcut:
        def __init__(self, key_sequence, _parent):
            created.append(key_sequence.toString())
            self.activated = _FakeActivated()

    monkeypatch.setattr(main_window_module, "QShortcut", _FakeShortcut)

    fake_window = Mock()
    fake_window._shortcuts = []
    fake_window.i18n = _build_i18n()
    fake_window.switch_page = Mock()
    fake_window._focus_global_search = Mock()
    fake_window.close = Mock()
    fake_window._bind_shortcut = lambda sequence, callback: MainWindow._bind_shortcut(
        fake_window, sequence, callback
    )

    MainWindow._setup_keyboard_shortcuts(fake_window)

    assert created == [
        "Ctrl+1",
        "Ctrl+2",
        "Ctrl+3",
        "Ctrl+4",
        "Ctrl+,",
        "Ctrl+K",
        "Ctrl+Q",
    ]
    assert len(fake_window._shortcuts) == 7


def test_main_window_exposes_persistent_recording_dock_and_workspace_shell(tmp_path):
    main_window = build_main_window_with_workspace(tmp_path)

    try:
        assert main_window.recording_dock is not None
        assert main_window.recording_dock.isVisible()
        assert main_window.pages["workspace"].library_panel is not None
        assert main_window.pages["workspace"].inspector_panel is not None
    finally:
        main_window.close()


def test_recording_dock_supports_compact_and_full_modes():
    app = QApplication.instance() or QApplication([])
    realtime_recorder = Mock()
    type(realtime_recorder).is_recording = PropertyMock(return_value=False)
    realtime_recorder.list_input_sources.return_value = []
    realtime_recorder.get_recording_status.return_value = {"duration": 0.0}
    realtime_recorder.get_accumulated_transcription.return_value = ""
    realtime_recorder.get_accumulated_translation.return_value = ""
    dock = RealtimeRecordingDock(realtime_recorder, _build_i18n())
    dock.show()
    app.processEvents()

    assert dock.compact_panel.start_button.isVisible()
    assert dock.compact_panel.stop_button.isVisible()
    assert dock.expand_button.isVisible()

    dock.expand_button.click()
    app.processEvents()

    assert dock.full_panel.input_source_combo is not None
    assert dock.full_panel.marker_button.isVisible()
