# SPDX-License-Identifier: Apache-2.0
"""Tests for main window shell status and shortcuts."""

import asyncio
import time
from unittest.mock import Mock, PropertyMock, patch

import ui.main_window as main_window_module
from core.qt_imports import QApplication, QSettings
from core.workspace.manager import WorkspaceManager
from data.database.connection import DatabaseConnection
from data.storage.file_manager import FileManager
from ui.constants import APP_TOP_BAR_CONTROL_HEIGHT
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
            "workspace.recording_console.default_input_source": "System Input",
            "workspace.recording_console.session_options_title": "Session Options",
            "workspace.recording_console.input_section": "Input",
            "workspace.recording_console.realtime_processing_section": "Live Processing",
            "workspace.recording_console.recording_output_section": "Recording Output",
            "workspace.recording_console.secondary_processing_section": "Secondary Processing",
            "workspace.recording_console.translation_target_language_label": "Translation Target",
            "workspace.recording_console.realtime_transcription_model_label": "Live Transcription Model",
            "workspace.recording_console.secondary_default_model_label": "Default Secondary Model",
            "workspace.recording_console.enable_transcription": "Enable Live Transcription",
            "workspace.recording_console.enable_translation": "Enable Live Translation",
            "workspace.recording_console.settings_tooltip": "Recording Settings",
            "workspace.recording_console.enable_transcription_tooltip": "Enable Live Transcription",
            "workspace.recording_console.disable_transcription_tooltip": "Disable Live Transcription",
            "workspace.recording_console.enable_translation_tooltip": "Enable Live Translation",
            "workspace.recording_console.disable_translation_tooltip": "Disable Live Translation",
            "workspace.recording_console.show_overlay_tooltip": "Show Floating Overlay",
            "workspace.recording_console.hide_overlay_tooltip": "Hide Floating Overlay",
            "workspace.recording_console.open_latest_document_tooltip": "Open Latest Document",
            "workspace.recording_console.secondary_process_tooltip": "Run Secondary Processing",
            "workspace.recording_console.auto_secondary_processing": "Auto Secondary Processing",
            "workspace.recording_console.enable_auto_secondary_tooltip": "Enable Auto Secondary",
            "workspace.recording_console.disable_auto_secondary_tooltip": "Disable Auto Secondary",
            "workspace.recording_console.mode_record_only": "Audio Only",
            "workspace.recording_console.mode_transcription_only": "Live Transcription",
            "workspace.recording_console.mode_translation_target": "Translate to {language}",
            "workspace.recording_console.target_language_auto": "Automatic",
            "workspace.recording_console.target_language_en": "English",
            "workspace.recording_console.target_language_zh": "Chinese",
            "workspace.recording_console.target_language_fr": "French",
            "workspace.record_button": "Record",
            "workspace.record_button_active": "Recording",
            "workspace.record_button_busy": "Processing",
            "workspace.stop_button": "Stop",
            "logging.main_window.keyboard_shortcuts_configured": "shortcuts configured",
        }
        template = mapping.get(key, key)
        try:
            return template.format(**kwargs)
        except Exception:
            return template

    i18n.t = Mock(side_effect=_t)
    return i18n


def _build_transcription_manager():
    manager = Mock()
    manager.get_all_tasks.return_value = []
    manager.add_listener = Mock()
    manager.remove_listener = Mock()
    manager.is_paused.return_value = False
    manager.get_active_task_count.return_value = 0
    manager._running = False
    return manager


def _wait_until(app, predicate, timeout=2.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        app.processEvents()
        if predicate():
            return True
        time.sleep(0.01)
    app.processEvents()
    return predicate()


def build_main_window_with_workspace(tmp_path, *, transcription_manager=None, settings_file=None):
    app = QApplication.instance() or QApplication([])
    db = DatabaseConnection(str(tmp_path / "main_window_shell.db"))
    db.initialize_schema()
    file_manager = FileManager(str(tmp_path / "files"))
    workspace_manager = WorkspaceManager(db, file_manager)
    settings_file = settings_file or (tmp_path / "main_window_shell.ini")

    realtime_recorder = Mock()
    type(realtime_recorder).is_recording = PropertyMock(return_value=False)

    managers = {
        "workspace_manager": workspace_manager,
        "realtime_recorder": realtime_recorder,
        "transcription_manager": transcription_manager,
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

    def _build_test_settings(*_args, **_kwargs):
        return QSettings(str(settings_file), QSettings.Format.IniFormat)

    with patch.object(MainWindow, "_create_pages", _create_workspace_only), patch.object(
        main_window_module, "QSettings", _build_test_settings
    ):
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


def test_main_window_opens_singleton_workspace_task_window(tmp_path):
    transcription_manager = _build_transcription_manager()
    main_window = build_main_window_with_workspace(
        tmp_path,
        transcription_manager=transcription_manager,
    )

    try:
        main_window.task_window_button.click()
        first_window = main_window.task_window

        main_window.task_window_button.click()

        assert main_window.task_window is not None
        assert main_window.task_window is first_window
        assert main_window.task_window.isVisible()
        assert not hasattr(main_window.recording_dock, "task_drawer_host")
    finally:
        main_window.close()


def test_main_window_task_window_persists_geometry_and_drops_shell_auxiliary_host(tmp_path):
    transcription_manager = _build_transcription_manager()
    settings_file = tmp_path / "task_window_geometry.ini"
    main_window = build_main_window_with_workspace(
        tmp_path,
        transcription_manager=transcription_manager,
        settings_file=settings_file,
    )
    app = QApplication.instance() or QApplication([])

    try:
        main_window.task_window_button.click()
        app.processEvents()

        task_window = main_window.task_window
        assert task_window is not None

        task_window.resize(840, 610)
        task_window.move(120, 160)
        app.processEvents()
        task_window.close()
        app.processEvents()
    finally:
        main_window.close()

    reopened = build_main_window_with_workspace(
        tmp_path,
        transcription_manager=transcription_manager,
        settings_file=settings_file,
    )
    try:
        reopened.task_window_button.click()
        app.processEvents()

        assert not hasattr(reopened, "shell_auxiliary_host")
        assert reopened.task_window is not None
        assert reopened.task_window.size().width() == 840
        assert reopened.task_window.size().height() == 610
    finally:
        reopened.close()


def test_main_window_task_entry_exposes_backlog_badge(tmp_path):
    transcription_manager = _build_transcription_manager()
    transcription_manager.get_active_task_count.return_value = 3
    main_window = build_main_window_with_workspace(
        tmp_path,
        transcription_manager=transcription_manager,
    )

    try:
        MainWindow._update_shell_status(main_window)

        assert main_window.task_window_badge.text() == "3"
        assert main_window.task_window_badge.isVisible()
    finally:
        transcription_manager.get_active_task_count.return_value = 0
        main_window.close()


def test_main_window_top_bar_groups_search_hint_and_task_entry(tmp_path):
    main_window = build_main_window_with_workspace(tmp_path)

    try:
        assert main_window.top_bar_right_tools is not None
        assert main_window.top_bar_right_tools.property("role") == "app-topbar-tools"
        assert main_window.task_window_button.minimumHeight() == APP_TOP_BAR_CONTROL_HEIGHT
        assert main_window.task_window_badge.parent() is main_window.task_window_button
    finally:
        main_window.close()


def test_recording_dock_supports_compact_transport_and_popup_settings():
    app = QApplication.instance() or QApplication([])
    realtime_recorder = Mock()
    type(realtime_recorder).is_recording = PropertyMock(return_value=False)
    realtime_recorder.set_callbacks = Mock()
    realtime_recorder.list_input_sources.return_value = []
    realtime_recorder.get_recording_status.return_value = {"duration": 0.0}
    realtime_recorder.get_accumulated_transcription.return_value = ""
    realtime_recorder.get_accumulated_translation.return_value = ""
    dock = RealtimeRecordingDock(realtime_recorder, _build_i18n())
    dock.show()
    app.processEvents()

    assert dock.compact_panel.start_button.isVisible()
    assert dock.compact_panel.stop_button.isVisible()
    assert dock.compact_panel.settings_button.isVisible()
    assert dock.compact_panel.overlay_button.isVisible()
    assert dock.compact_panel.open_document_button.isVisible()
    assert dock.compact_panel.secondary_button.isVisible()
    assert dock.compact_panel.auto_secondary_button.isVisible()
    assert dock.compact_panel.transcription_button.isVisible()
    assert dock.compact_panel.translation_button.isVisible()
    realtime_recorder.set_callbacks.assert_called()

    dock.compact_panel.settings_button.click()
    app.processEvents()

    assert dock.settings_popup.isVisible()
    assert dock.settings_panel.input_source_combo is not None
    assert dock.settings_panel.more_settings_button.isVisible()


def test_recording_dock_settings_popup_exposes_compact_controls():
    app = QApplication.instance() or QApplication([])
    realtime_recorder = Mock()
    type(realtime_recorder).is_recording = PropertyMock(return_value=False)
    realtime_recorder.list_input_sources.return_value = []
    realtime_recorder.get_recording_status.return_value = {"duration": 0.0}
    realtime_recorder.get_accumulated_transcription.return_value = ""
    realtime_recorder.get_accumulated_translation.return_value = ""
    realtime_recorder.get_markers.return_value = []
    dock = RealtimeRecordingDock(realtime_recorder, _build_i18n())
    dock.show()
    app.processEvents()

    dock.compact_panel.settings_button.click()
    app.processEvents()

    assert dock.settings_panel.input_source_combo is not None
    assert dock.settings_panel.gain_spin is not None
    assert dock.settings_panel.translation_language_combo is not None
    assert dock.settings_panel.model_combo is not None
    assert dock.settings_panel.secondary_model_combo is not None
    assert dock.settings_panel.input_section_label.text() == "Input"
    assert dock.settings_panel.realtime_section_label.text() == "Live Processing"
    assert dock.settings_panel.recording_output_section_label.text() == "Recording Output"
    assert dock.settings_panel.secondary_section_label.text() == "Secondary Processing"
    assert dock.settings_panel.transcribe_check.isVisible()
    assert dock.settings_panel.translate_check.isVisible()
    assert dock.settings_panel.more_settings_button.isVisible()


def test_recording_dock_uses_single_transport_summary_and_popup_settings_panel():
    app = QApplication.instance() or QApplication([])
    realtime_recorder = Mock()
    type(realtime_recorder).is_recording = PropertyMock(return_value=False)
    realtime_recorder.list_input_sources.return_value = []
    realtime_recorder.get_recording_status.return_value = {
        "duration": 0.0,
        "input_device_name": "default",
    }
    realtime_recorder.get_accumulated_transcription.return_value = ""
    realtime_recorder.get_accumulated_translation.return_value = ""
    realtime_recorder.get_markers.return_value = []
    dock = RealtimeRecordingDock(realtime_recorder, _build_i18n())
    dock.show()
    app.processEvents()

    assert dock.compact_panel.summary_group is not None
    assert dock.settings_popup is not None
    assert dock.settings_panel.title_label.text() == "Session Options"
    assert not hasattr(dock, "expand_button")
    assert not hasattr(dock.settings_panel, "session_tabs")
    assert dock.compact_panel.open_document_button.isEnabled() is False


def test_recording_dock_localizes_summary_labels_and_overlay_toggle():
    app = QApplication.instance() or QApplication([])
    realtime_recorder = Mock()
    type(realtime_recorder).is_recording = PropertyMock(return_value=False)
    realtime_recorder.list_input_sources.return_value = []
    realtime_recorder.get_recording_status.return_value = {
        "duration": 0.0,
        "input_device_name": "default",
    }
    realtime_recorder.get_accumulated_transcription.return_value = ""
    realtime_recorder.get_accumulated_translation.return_value = ""
    realtime_recorder.get_markers.return_value = []
    dock = RealtimeRecordingDock(realtime_recorder, _build_i18n())
    dock.show()
    app.processEvents()

    assert dock.settings_panel.gain_spin.property("role") == "realtime-field-control"
    assert "default" not in dock.compact_panel.input_label.text().lower()
    assert dock.compact_panel.target_label.text() == "Live Transcription"
    assert dock.compact_panel.overlay_button.toolTip() == "Show Floating Overlay"


def test_recording_dock_transcription_and_translation_toggles_stay_in_sync():
    app = QApplication.instance() or QApplication([])
    realtime_recorder = Mock()
    type(realtime_recorder).is_recording = PropertyMock(return_value=False)
    realtime_recorder.list_input_sources.return_value = []
    realtime_recorder.get_recording_status.return_value = {
        "duration": 0.0,
        "input_device_name": "default",
    }
    dock = RealtimeRecordingDock(realtime_recorder, _build_i18n())
    dock.show()
    app.processEvents()

    dock.compact_panel.translation_button.setChecked(True)
    app.processEvents()
    assert dock.settings_panel.transcription_enabled() is True
    assert dock.settings_panel.translation_enabled() is True
    assert dock.compact_panel.target_label.text() == "Translate to English"

    dock.compact_panel.transcription_button.setChecked(False)
    app.processEvents()
    assert dock.settings_panel.transcription_enabled() is False
    assert dock.settings_panel.translation_enabled() is False
    assert dock.compact_panel.translation_button.isChecked() is False
    assert dock.compact_panel.target_label.text() == "Audio Only"


def test_recording_dock_floating_overlay_tracks_live_preview():
    app = QApplication.instance() or QApplication([])
    realtime_recorder = Mock()
    realtime_recorder.current_options = {"floating_window_enabled": True}
    type(realtime_recorder).is_recording = PropertyMock(return_value=True)
    realtime_recorder.list_input_sources.return_value = []
    realtime_recorder.get_recording_status.return_value = {
        "duration": 65.0,
        "input_device_name": "Built-in Mic",
    }
    realtime_recorder.get_accumulated_transcription.return_value = "hello world"
    realtime_recorder.get_accumulated_translation.return_value = "bonjour le monde"
    settings_manager = Mock()
    settings_manager.get_realtime_session_defaults.return_value = {"floating_window_enabled": True}
    settings_manager.get_setting.side_effect = lambda key: {
        "realtime.hide_main_window_when_floating": False,
        "realtime.floating_window_always_on_top": True,
    }.get(key, False)
    dock = RealtimeRecordingDock(realtime_recorder, _build_i18n(), settings_manager=settings_manager)
    dock.show()
    app.processEvents()

    dock._handle_start_completed({})
    dock.refresh_status()
    app.processEvents()

    assert dock.floating_overlay.isVisible()
    assert dock.floating_overlay.transcript_preview_label.text() == "hello world"
    assert dock.floating_overlay.translation_preview_label.text() == "bonjour le monde"

    type(realtime_recorder).is_recording = PropertyMock(return_value=False)
    dock._handle_stop_completed({"recording_path": "/tmp/session.wav"})
    app.processEvents()
    assert not dock.floating_overlay.isVisible()


def test_recording_dock_recorder_callbacks_push_live_preview_immediately():
    app = QApplication.instance() or QApplication([])
    realtime_recorder = Mock()
    type(realtime_recorder).is_recording = PropertyMock(return_value=True)
    realtime_recorder.list_input_sources.return_value = []
    realtime_recorder.get_recording_status.return_value = {"duration": 2.0, "input_device_name": "Mic"}
    realtime_recorder.get_accumulated_transcription.return_value = ""
    realtime_recorder.get_accumulated_translation.return_value = ""
    realtime_recorder.set_callbacks = Mock()

    dock = RealtimeRecordingDock(realtime_recorder, _build_i18n())
    dock.show()
    app.processEvents()

    callback_kwargs = realtime_recorder.set_callbacks.call_args.kwargs
    callback_kwargs["on_transcription"]("live transcript")
    callback_kwargs["on_translation"]("live translation")
    app.processEvents()

    assert dock.floating_overlay.transcript_preview_label.text() == "live transcript"
    assert dock.floating_overlay.translation_preview_label.text() == "live translation"


def test_recording_dock_secondary_transcription_reuses_task_pipeline():
    realtime_recorder = Mock()
    type(realtime_recorder).is_recording = PropertyMock(return_value=False)
    realtime_recorder.list_input_sources.return_value = []
    transcription_manager = Mock()
    dock = RealtimeRecordingDock(
        realtime_recorder,
        _build_i18n(),
        transcription_manager=transcription_manager,
        model_manager=Mock(),
    )
    dock._latest_session_result = {
        "recording_path": "/tmp/session.wav",
        "event_id": "evt-1",
        "session_options": {
            "enable_translation": True,
            "target_language": "fr",
        },
    }

    with patch(
        "ui.common.realtime_recording_dock.select_secondary_transcribe_model",
        return_value={"model_name": "base", "model_path": "/models/base"},
    ) as select_model:
        dock._on_secondary_transcription_requested()

    assert select_model.call_args.kwargs["preferred_model_name"] == ""
    transcription_manager.add_task.assert_called_once_with(
        "/tmp/session.wav",
        options={
            "replace_realtime": True,
            "model_name": "base",
            "model_path": "/models/base",
            "event_id": "evt-1",
            "enable_translation": True,
            "translation_target_lang": "fr",
        },
    )


def test_recording_dock_secondary_button_uses_recorder_last_session_result_fallback():
    app = QApplication.instance() or QApplication([])
    realtime_recorder = Mock()
    type(realtime_recorder).is_recording = PropertyMock(return_value=False)
    realtime_recorder.list_input_sources.return_value = []
    realtime_recorder.get_recording_status.return_value = {"duration": 0.0}
    realtime_recorder.last_session_result = {"recording_path": "/tmp/fallback.wav"}
    dock = RealtimeRecordingDock(realtime_recorder, _build_i18n())
    dock.show()
    app.processEvents()

    dock.refresh_status()

    assert dock.compact_panel.secondary_button.isEnabled()


def test_recording_dock_start_button_switches_to_recording_copy_and_reuses_single_loop():
    app = QApplication.instance() or QApplication([])

    class _AsyncRecorder:
        def __init__(self):
            self.is_recording = False
            self.current_options = {}
            self.last_session_result = None
            self.last_workspace_item_id = None
            self.start_event_loop = None
            self.stop_event_loop = None

        def list_input_sources(self):
            return []

        def get_recording_status(self):
            return {"duration": 0.0, "input_device_name": "default"}

        def get_accumulated_transcription(self):
            return ""

        def get_accumulated_translation(self):
            return ""

        async def start_recording(self, input_source=None, options=None, event_loop=None):
            self.start_event_loop = event_loop
            self.current_options = dict(options or {})
            self.is_recording = True
            return {}

        async def stop_recording(self):
            self.stop_event_loop = asyncio.get_running_loop()
            self.is_recording = False
            self.last_session_result = {
                "recording_path": "/tmp/session.wav",
                "workspace_item_id": "item-1",
                "session_options": dict(self.current_options),
            }
            self.last_workspace_item_id = "item-1"
            return dict(self.last_session_result)

    recorder = _AsyncRecorder()
    dock = RealtimeRecordingDock(recorder, _build_i18n())
    dock.show()
    app.processEvents()

    dock.compact_panel.start_button.click()
    assert _wait_until(app, lambda: recorder.is_recording)
    assert recorder.start_event_loop is not None
    assert dock.compact_panel.start_button.text() == "Recording"

    dock.compact_panel.stop_button.click()
    assert _wait_until(app, lambda: recorder.stop_event_loop is not None)
    assert recorder.stop_event_loop is recorder.start_event_loop

    dock.close()


def test_recording_dock_auto_secondary_toggle_queues_latest_recording_with_default_model():
    realtime_recorder = Mock()
    type(realtime_recorder).is_recording = PropertyMock(return_value=False)
    realtime_recorder.list_input_sources.return_value = []
    transcription_manager = Mock()
    model_manager = Mock()
    base_model = Mock()
    base_model.name = "base"
    base_model.local_path = "/models/base"
    small_model = Mock()
    small_model.name = "small"
    small_model.local_path = "/models/small"
    model_manager.get_downloaded_models.return_value = [base_model, small_model]
    settings_manager = Mock()
    settings_manager.get_realtime_session_defaults.return_value = {
        "auto_secondary_processing": False,
        "transcription_model_name": "small",
    }
    settings_manager.get_setting.side_effect = lambda key: {
        "transcription.secondary_model_size": "base",
        "transcription.faster_whisper.model_size": "base",
        "realtime.transcription_model_name": "small",
    }.get(key)

    dock = RealtimeRecordingDock(
        realtime_recorder,
        _build_i18n(),
        transcription_manager=transcription_manager,
        model_manager=model_manager,
        settings_manager=settings_manager,
    )
    dock.settings_panel.auto_secondary_check.setChecked(True)
    with patch(
        "ui.common.realtime_recording_dock.select_secondary_transcribe_model",
        return_value={"model_name": "base", "model_path": "/models/base"},
    ) as select_model:
        dock._handle_stop_completed(
            {
                "recording_path": "/tmp/session.wav",
                "event_id": "evt-9",
                "workspace_item_id": "item-9",
                "session_options": {
                    "model_name": "small",
                    "model_path": "/models/small",
                    "secondary_model_name": "base",
                    "secondary_model_path": "/models/base",
                    "enable_translation": True,
                    "translation_target_lang": "fr",
                },
            }
        )

    assert select_model.call_args.kwargs["preferred_model_name"] == "base"

    transcription_manager.add_task.assert_called_once_with(
        "/tmp/session.wav",
        options={
            "replace_realtime": True,
            "model_name": "base",
            "model_path": "/models/base",
            "event_id": "evt-9",
            "enable_translation": True,
            "translation_target_lang": "fr",
        },
    )


def test_recording_dock_session_options_include_selected_downloaded_model():
    app = QApplication.instance() or QApplication([])
    realtime_recorder = Mock()
    type(realtime_recorder).is_recording = PropertyMock(return_value=False)
    realtime_recorder.list_input_sources.return_value = []
    model_manager = Mock()
    base_model = Mock()
    base_model.name = "base"
    base_model.local_path = "/models/base"
    small_model = Mock()
    small_model.name = "small"
    small_model.local_path = "/models/small"
    model_manager.get_downloaded_models.return_value = [base_model, small_model]
    settings_manager = Mock()
    settings_manager.get_realtime_session_defaults.return_value = {
        "transcription_model_name": "small",
    }
    settings_manager.get_setting.side_effect = lambda key: {
        "transcription.secondary_model_size": "base",
        "transcription.faster_whisper.model_size": "base",
    }.get(key)
    dock = RealtimeRecordingDock(
        realtime_recorder,
        _build_i18n(),
        settings_manager=settings_manager,
        model_manager=model_manager,
    )
    dock.show()
    app.processEvents()

    options = dock.build_realtime_session_options()

    assert options["model_name"] == "small"
    assert options["model_path"] == "/models/small"
    assert options["secondary_model_name"] == "base"
    assert options["secondary_model_path"] == "/models/base"
