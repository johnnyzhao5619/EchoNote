# SPDX-License-Identifier: Apache-2.0
"""UI tests for the unified workspace widget."""

from pathlib import Path
from unittest.mock import Mock, PropertyMock, patch
import wave

import pytest

import ui.workspace as workspace_module
from core.qt_imports import QWidget
from core.workspace.manager import WorkspaceManager
from data.database.connection import DatabaseConnection
from data.database.models import CalendarEvent, TranscriptionTask, WorkspaceAsset, WorkspaceItem
from data.storage.file_manager import FileManager
from ui.common.audio_player import AudioPlayer
from ui.main_window import MainWindow
from ui.workspace.detached_document_window import DetachedDocumentWindow
from ui.workspace.widget import WorkspaceWidget

pytestmark = pytest.mark.ui


def _write_valid_wav(path: Path) -> None:
    """Create a tiny valid PCM WAV fixture for UI audio-player tests."""
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(8000)
        wav_file.writeframes(b"\x00\x00" * 800)


@pytest.fixture
def workspace_manager(tmp_path):
    db = DatabaseConnection(str(tmp_path / "workspace_ui.db"))
    db.initialize_schema()
    file_manager = FileManager(str(tmp_path / "files"))
    manager = WorkspaceManager(db, file_manager)

    item = WorkspaceItem(title="Sprint Sync", item_type="recording", source_kind="realtime_recording")
    item.save(db)

    audio_path = tmp_path / "meeting.wav"
    _write_valid_wav(audio_path)
    transcript_path = tmp_path / "meeting.txt"
    transcript_path.write_text("Team reviewed roadmap and decided to ship alpha next week.", encoding="utf-8")

    transcript_asset = WorkspaceAsset(
        item_id=item.id,
        asset_role="transcript",
        file_path=str(transcript_path),
        text_content=transcript_path.read_text(encoding="utf-8"),
        content_type="text/plain",
    )
    transcript_asset.save(db)

    audio_asset = WorkspaceAsset(
        item_id=item.id,
        asset_role="audio",
        file_path=str(audio_path),
        content_type="audio/wav",
    )
    audio_asset.save(db)

    item.primary_text_asset_id = transcript_asset.id
    item.primary_audio_asset_id = audio_asset.id
    item.save(db)

    return manager


class StubTranscriptionManager:
    """Minimal transcription manager stub for workspace UI tests."""

    def __init__(self, db):
        self.db = db
        self._listeners = []

    def add_listener(self, callback):
        self._listeners.append(callback)

    def remove_listener(self, callback):
        if callback in self._listeners:
            self._listeners.remove(callback)

    def get_all_tasks(self, status=None):
        tasks = TranscriptionTask.get_all(self.db, status=status)
        return [
            {
                **task.to_dict(),
                "task_kind": "translation" if task.engine == "translation" else "transcription",
            }
            for task in tasks
        ]

    def is_paused(self):
        return False

    def get_task_status(self, task_id):
        task = TranscriptionTask.get_by_id(self.db, task_id)
        return task.to_dict() if task is not None else None

    def emit(self, event_type, data):
        if event_type == "task_added":
            task = TranscriptionTask(
                id=data["id"],
                file_path=data["file_path"],
                file_name=data["file_name"],
                file_size=data.get("file_size"),
                status=data.get("status", "pending"),
                output_format=data.get("output_format"),
                engine="translation" if data.get("task_kind") == "translation" else "whisper",
            )
            task.save(self.db)
        for callback in list(self._listeners):
            callback(event_type, data)


@pytest.fixture
def transcription_manager(workspace_manager):
    task = TranscriptionTask(
        file_path="/tmp/demo.wav",
        file_name="demo.wav",
        file_size=1024,
        status="pending",
        output_format="txt",
    )
    task.save(workspace_manager.db)
    return StubTranscriptionManager(workspace_manager.db)


class _FakeSettingsPage(QWidget):
    def __init__(self):
        super().__init__()
        self._current_page = "appearance"

    def show_page(self, page_id: str) -> bool:
        self._current_page = page_id
        return True

    def current_page_id(self) -> str:
        return self._current_page


def build_main_window_with_workspace(
    qapp,
    mock_i18n,
    workspace_manager,
    *,
    transcription_manager=None,
):
    realtime_recorder = Mock()
    type(realtime_recorder).is_recording = PropertyMock(return_value=False)
    realtime_recorder.list_input_sources.return_value = [{"index": 3, "name": "Podcast Mic"}]
    realtime_recorder.get_recording_status.return_value = {"duration": 0.0}
    realtime_recorder.get_accumulated_transcription.return_value = ""
    realtime_recorder.get_accumulated_translation.return_value = ""
    realtime_recorder.get_markers.return_value = []

    settings_manager = Mock()
    settings_manager.get_setting.return_value = "light"
    settings_manager.api_keys_updated = Mock()
    settings_manager.api_keys_updated.connect = Mock()
    settings_manager.get_realtime_session_defaults.return_value = {
        "default_input_source": 3,
        "default_gain": 1.6,
        "enable_transcription": True,
        "enable_translation": False,
        "translation_target_lang": "fr",
        "auto_save": True,
        "save_transcript": True,
        "create_calendar_event": True,
    }

    managers = {
        "workspace_manager": workspace_manager,
        "realtime_recorder": realtime_recorder,
        "settings_manager": settings_manager,
        "transcription_manager": transcription_manager,
        "calendar_manager": None,
        "oauth_manager": None,
        "timeline_manager": None,
    }

    def _create_workspace_and_settings(self, content_area):
        workspace_widget = WorkspaceWidget(
            workspace_manager,
            self.i18n,
            realtime_recorder=realtime_recorder,
        )
        settings_widget = _FakeSettingsPage()
        content_area.addWidget(workspace_widget)
        self.pages["workspace"] = workspace_widget
        content_area.addWidget(settings_widget)
        self.pages["settings"] = settings_widget

    with patch.object(MainWindow, "_create_pages", _create_workspace_and_settings):
        main_window = MainWindow(managers, mock_i18n)

    main_window.show()
    qapp.processEvents()
    return main_window, realtime_recorder


def test_workspace_widget_shows_editor_audio_and_task_regions(
    qapp, mock_i18n, workspace_manager, transcription_manager
):
    widget = WorkspaceWidget(workspace_manager, mock_i18n, transcription_manager=transcription_manager)

    assert widget.library_panel is not None
    assert widget.item_list is not None
    assert widget.editor_panel is not None
    assert widget.inspector_panel is not None
    assert widget.recording_panel is not None
    assert widget.task_panel is None


def test_workspace_widget_exposes_workspace_shell(
    qapp, mock_i18n, workspace_manager, transcription_manager
):
    widget = WorkspaceWidget(workspace_manager, mock_i18n, transcription_manager=transcription_manager)
    widget.show()
    qapp.processEvents()

    assert widget.library_panel is not None
    assert widget.inspector_panel is not None
    assert widget.library_panel.item_list is widget.item_list
    assert widget.inspector_panel.recording_panel is widget.recording_panel


def test_workspace_editor_panel_save_updates_workspace_asset(qapp, mock_i18n, workspace_manager):
    widget = WorkspaceWidget(workspace_manager, mock_i18n)
    item = workspace_manager.list_items()[0]

    widget._on_item_selected(item.id)
    widget.editor_panel.show_info = Mock()
    widget.editor_panel.toggle_edit_mode()
    widget.editor_panel.text_edit.setPlainText("Updated transcript content")
    widget.editor_panel.save_changes()

    primary_asset = workspace_manager.get_primary_text_asset(item.id)
    assert workspace_manager.read_asset_text(primary_asset) == "Updated transcript content"


def test_workspace_editor_panel_generates_summary_asset(qapp, mock_i18n, workspace_manager):
    widget = WorkspaceWidget(workspace_manager, mock_i18n)
    item = workspace_manager.list_items()[0]
    widget._on_item_selected(item.id)
    widget.editor_panel.show_info = Mock()

    widget.editor_panel._generate_summary()

    roles = [asset.asset_role for asset in workspace_manager.get_assets(item.id)]
    assert "summary" in roles


def test_workspace_recording_panel_reuses_shared_audio_player(qapp, mock_i18n, workspace_manager):
    widget = WorkspaceWidget(workspace_manager, mock_i18n)

    assert isinstance(widget.recording_panel.audio_player, AudioPlayer)


def test_workspace_editor_panel_uses_stable_asset_tab_labels(qapp, mock_i18n, workspace_manager):
    widget = WorkspaceWidget(workspace_manager, mock_i18n)
    item = workspace_manager.list_items()[0]

    widget._on_item_selected(item.id)
    labels = [
        widget.editor_panel.asset_tabs.tabText(index)
        for index in range(widget.editor_panel.asset_tabs.count())
    ]

    assert any(label.startswith("Transcript:") for label in labels)


def test_workspace_editor_uses_asset_tabs_and_inspector_hosts_ai_actions(
    qapp, mock_i18n, workspace_manager
):
    widget = WorkspaceWidget(workspace_manager, mock_i18n)
    item = workspace_manager.list_items()[0]

    widget.open_item(item.id)

    assert widget.editor_panel.asset_tabs is not None
    assert widget.inspector_panel.summary_button is not None
    assert widget.inspector_panel.meeting_brief_button is not None


def test_workspace_task_window_renders_existing_tasks(
    qapp, mock_i18n, workspace_manager, transcription_manager
):
    main_window, _realtime_recorder = build_main_window_with_workspace(
        qapp,
        mock_i18n,
        workspace_manager,
        transcription_manager=transcription_manager,
    )

    try:
        main_window.task_window_button.click()
        qapp.processEvents()

        assert main_window.task_window is not None
        assert main_window.task_window.panel.task_count() == 1
        assert main_window.task_window.panel.task_items[0].filename_label.text() == "demo.wav"
    finally:
        main_window.close()


def test_workspace_task_window_updates_on_task_events(
    qapp, mock_i18n, workspace_manager, transcription_manager
):
    main_window, _realtime_recorder = build_main_window_with_workspace(
        qapp,
        mock_i18n,
        workspace_manager,
        transcription_manager=transcription_manager,
    )

    try:
        main_window.task_window_button.click()
        qapp.processEvents()

        transcription_manager.emit(
            "task_added",
            {
                "id": "task-2",
                "file_name": "translation.txt",
                "file_path": "/tmp/translation.txt",
                "file_size": 128,
                "status": "pending",
                "output_format": "txt",
                "task_kind": "translation",
            },
        )
        qapp.processEvents()

        assert main_window.task_window.panel.task_count() == 2
        assert {item.filename_label.text() for item in main_window.task_window.panel.task_items} == {
            "demo.wav",
            "translation.txt",
        }
    finally:
        main_window.close()


def test_workspace_task_view_action_routes_to_open_document_card(
    qapp, mock_i18n, workspace_manager, transcription_manager
):
    task_data = transcription_manager.get_all_tasks()[0]
    task = TranscriptionTask.get_by_id(workspace_manager.db, task_data["id"])
    assert task is not None
    workspace_item_id = workspace_manager.publish_transcription_task(task)

    main_window, _realtime_recorder = build_main_window_with_workspace(
        qapp,
        mock_i18n,
        workspace_manager,
        transcription_manager=transcription_manager,
    )

    try:
        main_window.switch_page("settings")
        qapp.processEvents()
        main_window.task_window_button.click()
        qapp.processEvents()

        main_window.task_window.panel.task_items[0].view_clicked.emit(task.id)
        qapp.processEvents()

        assert main_window.current_page_name == "workspace"
        assert main_window.pages["workspace"].document_tabs.count() >= 1
        assert main_window.pages["workspace"].current_item_id() == workspace_item_id
    finally:
        main_window.close()


def test_workspace_task_window_groups_creation_actions_and_routes_view_to_workspace(
    qapp, mock_i18n, workspace_manager, transcription_manager
):
    main_window, _ = build_main_window_with_workspace(
        qapp,
        mock_i18n,
        workspace_manager,
        transcription_manager=transcription_manager,
    )

    try:
        main_window.task_window_button.click()
        qapp.processEvents()
        task_window = main_window.task_window

        assert task_window is not None
        assert task_window.panel.creation_section is not None
        assert task_window.panel.queue_filter_section is not None
        assert task_window.panel.task_filter_tabs.count() >= 2
        assert task_window.panel.import_file_button.isVisible()
        assert task_window.panel.import_folder_button.isVisible()
    finally:
        main_window.close()


def test_workspace_task_window_exposes_summary_counts(
    qapp, mock_i18n, workspace_manager, transcription_manager
):
    failed_task = TranscriptionTask(
        file_path="/tmp/failed.wav",
        file_name="failed.wav",
        file_size=2048,
        status="failed",
        output_format="txt",
    )
    failed_task.save(workspace_manager.db)

    main_window, _ = build_main_window_with_workspace(
        qapp,
        mock_i18n,
        workspace_manager,
        transcription_manager=transcription_manager,
    )

    try:
        main_window.task_window_button.click()
        qapp.processEvents()
        task_window = main_window.task_window

        assert task_window is not None
        assert task_window.panel.summary_section is not None
        assert task_window.panel.summary_total_value_label.text() == "2"
        assert task_window.panel.summary_active_value_label.text() == "1"
        assert task_window.panel.summary_failed_value_label.text() == "1"
    finally:
        main_window.close()


def test_workspace_task_window_groups_creation_actions_publish_unpublished_result(
    qapp, mock_i18n, workspace_manager, transcription_manager, tmp_path
):
    task_data = transcription_manager.get_all_tasks()[0]
    task = TranscriptionTask.get_by_id(workspace_manager.db, task_data["id"])
    assert task is not None

    output_path = tmp_path / "demo-output.txt"
    output_path.write_text("Published transcript", encoding="utf-8")
    task.status = "completed"
    task.output_path = str(output_path)
    task.save(workspace_manager.db)

    main_window, _ = build_main_window_with_workspace(
        qapp,
        mock_i18n,
        workspace_manager,
        transcription_manager=transcription_manager,
    )

    try:
        assert workspace_manager.get_item_id_by_task_id(task.id) is None

        main_window.switch_page("settings")
        qapp.processEvents()
        main_window.task_window_button.click()
        qapp.processEvents()
        main_window.task_window.panel.show_warning = Mock(return_value=False)

        main_window.task_window.panel.task_items[0].view_clicked.emit(task.id)
        qapp.processEvents()

        published_item_id = workspace_manager.get_item_id_by_task_id(task.id)
        assert published_item_id is not None
        assert main_window.current_page_name == "workspace"
        assert main_window.pages["workspace"].current_item_id() == published_item_id
    finally:
        main_window.close()


def test_workspace_widget_exposes_unified_create_toolbar(
    qapp, mock_i18n, workspace_manager, transcription_manager
):
    widget = WorkspaceWidget(workspace_manager, mock_i18n, transcription_manager=transcription_manager)
    widget.show()
    qapp.processEvents()

    assert widget.toolbar is not None
    assert widget.toolbar.import_document_button.isVisible()
    assert widget.toolbar.new_note_button.isVisible()
    assert not hasattr(widget.toolbar, "start_recording_button")


def test_workspace_shell_exposes_tool_rail_explorer_and_document_stage(
    qapp, mock_i18n, workspace_manager
):
    widget = WorkspaceWidget(workspace_manager, mock_i18n)

    assert widget.tool_rail is not None
    assert widget.library_panel.explorer_header is not None
    assert widget.library_panel.item_list is not None
    assert widget.document_tabs is not None


def test_workspace_shell_uses_single_view_mode_entry_and_document_first_splitter(
    qapp, mock_i18n, workspace_manager
):
    widget = WorkspaceWidget(workspace_manager, mock_i18n)
    widget.resize(1440, 900)
    widget.show()
    qapp.processEvents()

    assert not hasattr(widget.library_panel, "view_mode_combo")
    assert widget.content_splitter.sizes()[1] > widget.content_splitter.sizes()[2]
    assert not hasattr(widget.toolbar, "start_recording_button")


def test_workspace_tool_rail_and_explorer_header_expose_compact_mode_shell(
    qapp, mock_i18n, workspace_manager
):
    widget = WorkspaceWidget(workspace_manager, mock_i18n)
    widget.resize(1440, 900)
    widget.show()
    qapp.processEvents()

    assert widget.tool_rail.mode_button_group is not None
    assert widget.library_panel.context_label is not None
    assert widget.content_splitter.sizes()[1] > widget.content_splitter.sizes()[2]


def test_workspace_item_list_renders_structured_row_widgets(
    qapp, mock_i18n, workspace_manager
):
    note_id = workspace_manager.create_note(title="Plan")
    widget = WorkspaceWidget(workspace_manager, mock_i18n)
    widget.show()
    qapp.processEvents()

    row_item = None
    for row in range(widget.item_list.list_widget.count()):
        candidate = widget.item_list.list_widget.item(row)
        if candidate.data(0x0100) == note_id:
            row_item = candidate
            break

    assert row_item is not None
    row_widget = widget.item_list.list_widget.itemWidget(row_item)

    assert row_widget.title_label.text() == "Plan"
    assert row_widget.meta_label.text()
    assert row_widget.status_badges_layout.count() >= 1


def test_workspace_item_row_uses_dense_title_meta_and_badge_roles(
    qapp, mock_i18n, workspace_manager
):
    widget = WorkspaceWidget(workspace_manager, mock_i18n)
    row = widget.item_list.list_widget.itemWidget(widget.item_list.list_widget.item(0))

    assert row.title_label.property("role") == "workspace-item-title"
    assert row.meta_label.property("role") == "workspace-item-meta"
    assert row.badges_widget.property("role") == "workspace-item-badges"


def test_workspace_inspector_exposes_section_titles_and_user_facing_metadata(
    qapp, mock_i18n, workspace_manager
):
    widget = WorkspaceWidget(workspace_manager, mock_i18n)
    item = workspace_manager.list_items()[0]
    widget.open_item(item.id)

    assert widget.inspector_panel.ai_section_title.text()
    assert widget.inspector_panel.media_section_title.text()
    assert widget.inspector_panel.metadata_section_title.text()
    assert "T" not in widget.inspector_panel.updated_value_label.text()


def test_workspace_editor_keeps_blank_note_asset_tab_editable(
    qapp, mock_i18n, workspace_manager
):
    note_id = workspace_manager.create_note(title="Blank Note", text_content="")
    widget = WorkspaceWidget(workspace_manager, mock_i18n)

    widget.open_item(note_id)

    assert widget.editor_panel.asset_tabs.count() == 1
    assert widget.editor_panel.edit_button.isEnabled()
    assert widget.editor_panel.text_edit.toPlainText() == ""


def test_detached_document_window_matches_workspace_context_stack(
    qapp, mock_i18n, workspace_manager
):
    note_id = workspace_manager.create_note(title="Plan")
    window = DetachedDocumentWindow(workspace_manager, mock_i18n, note_id)
    window.show()
    qapp.processEvents()

    assert window.inspector_panel is not None
    assert window.inspector_panel.recording_panel is not None
    assert hasattr(window.editor_panel, "generate_summary")


def test_workspace_toolbar_new_note_creates_workspace_item(
    qapp, mock_i18n, workspace_manager, transcription_manager
):
    widget = WorkspaceWidget(workspace_manager, mock_i18n, transcription_manager=transcription_manager)
    before_ids = {item.id for item in workspace_manager.list_items()}

    widget.toolbar.new_note_button.click()

    after_items = workspace_manager.list_items()
    created_items = [item for item in after_items if item.id not in before_ids]

    assert len(created_items) == 1
    assert created_items[0].source_kind == "workspace_note"
    assert workspace_manager.get_primary_text_asset(created_items[0].id) is not None
    assert widget.item_list.current_item_id() == created_items[0].id


def test_workspace_widget_moves_recording_controls_out_of_workspace_shell(
    qapp, mock_i18n, workspace_manager, transcription_manager
):
    widget = WorkspaceWidget(
        workspace_manager,
        mock_i18n,
        transcription_manager=transcription_manager,
        realtime_recorder=Mock(),
    )
    widget.show()
    qapp.processEvents()

    assert widget.inspector_panel.recording_panel.isVisible()
    assert not hasattr(widget, "recording_control_panel")


def test_workspace_library_panel_supports_structure_and_event_views(
    qapp, mock_i18n, workspace_manager, transcription_manager
):
    folder_id = workspace_manager.create_folder("Projects")
    note_id = workspace_manager.create_note(title="Plan")
    event = CalendarEvent(
        title="Planning Session",
        start_time="2026-03-15T15:00:00+00:00",
        end_time="2026-03-15T16:00:00+00:00",
    )
    event.save(workspace_manager.db)

    note = workspace_manager.get_item(note_id)
    assert note is not None
    note.source_event_id = event.id
    note.save(workspace_manager.db)
    workspace_manager.move_item_to_folder(note_id, folder_id)

    widget = WorkspaceWidget(
        workspace_manager,
        mock_i18n,
        transcription_manager=transcription_manager,
    )
    widget.show()
    qapp.processEvents()

    widget.library_panel.select_folder(folder_id)
    qapp.processEvents()

    assert widget.library_panel.current_view_mode() == "structure"
    assert widget.item_list.current_item_id() == note_id

    widget.library_panel.set_view_mode("event")
    qapp.processEvents()

    assert widget.library_panel.current_view_mode() == "event"
    assert widget.item_list.list_widget.count() >= 1


def test_workspace_supports_document_tabs_and_detached_window(
    qapp, mock_i18n, workspace_manager
):
    first_existing_id = workspace_manager.list_items()[0].id
    second_id = workspace_manager.create_note(title="Plan")
    widget = WorkspaceWidget(workspace_manager, mock_i18n)

    widget.open_item(first_existing_id)
    widget.open_item(second_id)

    assert widget.document_tabs.count() == 2
    assert widget.open_current_item_in_window_action is not None

    widget.open_current_item_in_window_action.trigger()
    qapp.processEvents()

    assert second_id in widget._detached_windows


def test_workspace_module_does_not_export_legacy_recording_control_panel():
    assert "WorkspaceRecordingControlPanel" not in workspace_module.__all__
    assert not hasattr(workspace_module, "WorkspaceRecordingControlPanel")


def test_workspace_update_translations_refreshes_detached_window_editor(
    qapp, mock_i18n, workspace_manager
):
    note_id = workspace_manager.create_note(title="Plan")
    widget = WorkspaceWidget(workspace_manager, mock_i18n)

    widget.open_item(note_id)
    widget.open_current_item_in_window_action.trigger()
    qapp.processEvents()

    detached_window = widget._detached_windows[note_id]
    assert detached_window.editor_panel.search_button.text() == "transcript.search"

    translations = {
        "common.edit": "编辑",
        "viewer.copy_all": "复制全部",
        "viewer.export": "导出",
        "viewer.export_txt": "导出 TXT",
        "viewer.export_md": "导出 MD",
        "transcript.search": "搜索",
        "workspace.open_in_new_window": "在新窗口打开",
        "workspace.library_title": "工作台条目",
    }
    mock_i18n.t.side_effect = lambda key, **kwargs: translations.get(key, key)

    widget.update_translations()
    qapp.processEvents()

    assert widget.open_current_item_in_window_action.text() == "在新窗口打开"
    assert detached_window.editor_panel.search_button.text() == "搜索"


def test_recording_dock_quick_start_uses_defaults_and_more_settings_routes_to_realtime_page(
    qapp, mock_i18n, workspace_manager
):
    main_window, realtime_recorder = build_main_window_with_workspace(
        qapp,
        mock_i18n,
        workspace_manager,
    )

    try:
        main_window.recording_dock.compact_panel.start_button.click()
        main_window.recording_dock.expand_button.click()
        qapp.processEvents()
        main_window.recording_dock.full_panel.more_settings_button.click()
        qapp.processEvents()

        realtime_recorder.start_recording.assert_called_once()
        call_kwargs = realtime_recorder.start_recording.call_args.kwargs
        assert call_kwargs["input_source"] == 3
        assert call_kwargs["options"]["default_gain"] == 1.6
        assert main_window.current_page_name == "settings"
        assert main_window.pages["settings"].current_page_id() == "realtime"
    finally:
        main_window.close()


def test_recording_dock_full_panel_grouped_console_sections_in_main_window(
    qapp, mock_i18n, workspace_manager
):
    main_window, _ = build_main_window_with_workspace(
        qapp,
        mock_i18n,
        workspace_manager,
    )

    try:
        main_window.recording_dock.set_expanded(True)
        qapp.processEvents()

        assert main_window.recording_dock.full_panel.session_summary_section is not None
        assert main_window.recording_dock.full_panel.capture_section is not None
        assert main_window.recording_dock.full_panel.processing_section is not None
        assert main_window.recording_dock.full_panel.output_section is not None
        assert main_window.recording_dock.full_panel.live_results_section is not None
    finally:
        main_window.close()


def test_recording_dock_workspace_item_routes_generated_item_into_workspace(
    qapp, mock_i18n, workspace_manager
):
    main_window, _realtime_recorder = build_main_window_with_workspace(
        qapp,
        mock_i18n,
        workspace_manager,
    )
    note_id = workspace_manager.create_note(title="Captured Session")

    try:
        main_window.switch_page("settings")
        qapp.processEvents()

        main_window.recording_dock._handle_stop_completed({"workspace_item_id": note_id})
        qapp.processEvents()

        assert main_window.current_page_name == "workspace"
        assert main_window.pages["workspace"].current_item_id() == note_id
    finally:
        main_window.close()
