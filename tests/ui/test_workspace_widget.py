# SPDX-License-Identifier: Apache-2.0
"""UI tests for the unified workspace widget."""

from pathlib import Path
from unittest.mock import Mock, PropertyMock, patch
import wave

import pytest

import ui.workspace as workspace_module
from core.qt_imports import QMenu, QWidget, Qt
from core.workspace.manager import WorkspaceManager
from data.database.connection import DatabaseConnection
from data.database.models import CalendarEvent, TranscriptionTask, WorkspaceAsset, WorkspaceItem
from data.storage.file_manager import FileManager
from ui.common.audio_player import AudioPlayer
from ui.main_window import MainWindow
from ui.workspace_drag_payload import (
    WORKSPACE_DRAG_SOURCE_BATCH_TASK,
    build_workspace_text_drag_payload,
)
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
    assert widget.item_list is widget.library_panel
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
    assert widget.recording_panel.audio_player.presentation == "inspector"
    assert widget.recording_panel.audio_player.show_transcript_button.isHidden()
    assert widget.recording_panel.audio_player.surface.property("state") == "inspector"


def test_workspace_editor_chrome_uses_compact_title_and_asset_context(
    qapp, mock_i18n, workspace_manager
):
    item_id = workspace_manager.list_items()[0].id
    workspace_manager.save_text_asset(item_id, "translation", "translated")
    widget = WorkspaceWidget(workspace_manager, mock_i18n)
    widget.open_item(item_id)

    tab_text = widget.document_tabs.tabText(widget.document_tabs.currentIndex())

    assert tab_text == "Sprint Sync"
    assert widget.editor_panel.document_title_label.text() == "Sprint Sync"
    assert widget.editor_panel.asset_tabs.count() >= 2
    assert ":" not in widget.editor_panel.asset_tabs.tabText(0)


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


def test_workspace_widget_exposes_navigator_header_actions(
    qapp, mock_i18n, workspace_manager, transcription_manager
):
    widget = WorkspaceWidget(workspace_manager, mock_i18n, transcription_manager=transcription_manager)
    widget.show()
    qapp.processEvents()

    assert widget.library_panel.header_action_bar is not None
    assert widget.library_panel.import_document_button.isVisible()
    assert widget.library_panel.new_note_button.isVisible()
    assert widget.library_panel.new_folder_button.isVisible()
    assert widget.library_panel.rename_folder_button.isVisible()
    assert widget.library_panel.delete_folder_button.isVisible()
    assert widget.library_panel.import_document_button.toolTip()
    assert widget.library_panel.new_note_button.toolTip()
    assert widget.library_panel.new_folder_button.toolTip()
    assert widget.library_panel.rename_folder_button.toolTip()
    assert widget.library_panel.delete_folder_button.toolTip()
    assert widget.library_panel.import_document_button.text() == ""
    assert not widget.library_panel.import_document_button.icon().isNull()


def test_workspace_shell_exposes_navigator_explorer_and_document_stage(
    qapp, mock_i18n, workspace_manager
):
    widget = WorkspaceWidget(workspace_manager, mock_i18n)

    assert not hasattr(widget, "tool_rail")
    assert widget.library_panel.explorer_header is not None
    assert not hasattr(widget.library_panel, "navigator_toolbar")
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
    assert not hasattr(widget, "toolbar")


def test_workspace_navigator_header_exposes_compact_mode_shell(
    qapp, mock_i18n, workspace_manager
):
    widget = WorkspaceWidget(workspace_manager, mock_i18n)
    widget.resize(1440, 900)
    widget.show()
    qapp.processEvents()

    assert widget.library_panel.context_label is not None
    assert widget.library_panel.folder_tree.property("role") == "workspace-nav-tree"
    assert widget.content_splitter.sizes()[1] > widget.content_splitter.sizes()[2]


def test_workspace_item_list_renders_structured_row_widgets(
    qapp, mock_i18n, workspace_manager
):
    note_id = workspace_manager.create_note(title="Plan")
    widget = WorkspaceWidget(workspace_manager, mock_i18n)
    widget.show()
    qapp.processEvents()

    item_node = widget.library_panel.find_item_node(note_id)

    assert item_node is not None
    assert item_node.text(0) == "Plan"
    assert widget.library_panel.item_tooltip(note_id)


def test_workspace_item_row_uses_dense_title_meta_and_badge_roles(
    qapp, mock_i18n, workspace_manager
):
    widget = WorkspaceWidget(workspace_manager, mock_i18n)

    assert widget.library_panel.folder_tree.property("role") == "workspace-nav-tree"
    assert widget.library_panel.folder_tree.textElideMode() == Qt.TextElideMode.ElideRight
    assert widget.library_panel.folder_tree.uniformRowHeights()


def test_workspace_item_row_surfaces_event_task_and_original_file_context(
    qapp, mock_i18n, workspace_manager
):
    translations = {
        "workspace.item_meta_event": "事件 {value}",
        "workspace.item_meta_task": "任务 {value}",
        "workspace.item_meta_original_file": "原文件 {value}",
        "workspace.item_meta_updated": "更新于 {value}",
        "workspace.item_badge_event_linked": "关联事件",
        "workspace.item_badge_task_linked": "批量任务",
    }
    mock_i18n.t.side_effect = lambda key, **kwargs: translations.get(key, key).format(**kwargs)

    event = CalendarEvent(
        title="Planning Session",
        start_time="2026-03-15T15:00:00+00:00",
        end_time="2026-03-15T16:00:00+00:00",
    )
    event.save(workspace_manager.db)

    task = TranscriptionTask(
        id="task-ui-context-1",
        file_path="/tmp/planning.wav",
        file_name="planning.wav",
        status="completed",
    )
    task.save(workspace_manager.db)

    item = workspace_manager.get_item(workspace_manager.list_items()[0].id)
    assert item is not None
    item.source_event_id = event.id
    item.source_task_id = task.id
    item.save(workspace_manager.db)

    widget = WorkspaceWidget(workspace_manager, mock_i18n)
    widget.show()
    qapp.processEvents()

    tooltip = widget.library_panel.item_tooltip(item.id)

    assert "任务 task-ui-context-1" in tooltip
    assert "planning.wav" in tooltip
    assert "关联事件" in tooltip
    assert "批量任务" in tooltip


def test_workspace_inspector_exposes_section_titles_and_user_facing_metadata(
    qapp, mock_i18n, workspace_manager
):
    widget = WorkspaceWidget(workspace_manager, mock_i18n)
    item = workspace_manager.list_items()[0]
    widget.open_item(item.id)

    assert widget.inspector_panel.ai_section_title.text()
    assert widget.inspector_panel.media_section_title.text()
    assert widget.inspector_panel.metadata_section_title.text()
    assert widget.inspector_panel.source_value_label.property("role") == "workspace-meta-value"
    assert "T" not in widget.inspector_panel.updated_value_label.text()


def test_workspace_inspector_surfaces_event_task_and_original_file_context(
    qapp, mock_i18n, workspace_manager
):
    translations = {
        "workspace.inspector_event": "关联事件：{value}",
        "workspace.inspector_task": "来源任务：{value}",
        "workspace.inspector_original_file": "原文件：{value}",
        "workspace.inspector_source": "来源：{value}",
        "workspace.inspector_updated": "更新时间：{value}",
    }
    mock_i18n.t.side_effect = lambda key, **kwargs: translations.get(key, key).format(**kwargs)

    event = CalendarEvent(
        title="Design Review",
        start_time="2026-03-15T09:00:00+00:00",
        end_time="2026-03-15T10:00:00+00:00",
    )
    event.save(workspace_manager.db)
    task = TranscriptionTask(
        id="task-inspector-1",
        file_path="/tmp/design-review.wav",
        file_name="design-review.wav",
        status="completed",
    )
    task.save(workspace_manager.db)

    item = workspace_manager.list_items()[0]
    item.source_event_id = event.id
    item.source_task_id = task.id
    item.save(workspace_manager.db)

    widget = WorkspaceWidget(workspace_manager, mock_i18n)
    widget.open_item(item.id)

    assert "Design Review" in widget.inspector_panel.event_value_label.text()
    assert "task-inspector-1" in widget.inspector_panel.task_value_label.text()
    assert "design-review.wav" in widget.inspector_panel.original_file_value_label.text()


def test_workspace_editor_keeps_blank_note_asset_tab_editable(
    qapp, mock_i18n, workspace_manager
):
    note_id = workspace_manager.create_note(title="Blank Note", text_content="")
    widget = WorkspaceWidget(workspace_manager, mock_i18n)

    widget.open_item(note_id)

    assert widget.editor_panel.asset_tabs.count() == 1
    assert not widget.editor_panel.asset_tabs.isVisible()
    assert widget.editor_panel.edit_button.isEnabled()
    assert widget.editor_panel.text_edit.toPlainText() == ""


def test_workspace_structure_view_surfaces_system_folders_and_inbox_items(
    qapp, mock_i18n, workspace_manager
):
    note_id = workspace_manager.create_note(title="Plan")
    widget = WorkspaceWidget(workspace_manager, mock_i18n)
    widget.show()
    qapp.processEvents()

    top_level_labels = [
        widget.library_panel.folder_tree.topLevelItem(index).text(0)
        for index in range(widget.library_panel.folder_tree.topLevelItemCount())
    ]
    note_node = widget.library_panel.find_item_node(note_id)

    assert top_level_labels[0] == "工作台条目"
    assert top_level_labels[-2:] == ["事件", "批量任务"]
    assert note_node is not None
    assert note_node.parent() is not None
    assert note_node.parent().text(0) == "工作台条目"


def test_workspace_library_panel_can_switch_between_structure_and_event_modes(
    qapp, mock_i18n, workspace_manager
):
    event = CalendarEvent(
        title="Design Review",
        start_time="2026-03-18T09:00:00+00:00",
        end_time="2026-03-18T10:00:00+00:00",
    )
    event.save(workspace_manager.db)
    event_note_id = workspace_manager.create_note(title="Review Notes", event_id=event.id)

    widget = WorkspaceWidget(workspace_manager, mock_i18n)
    widget.library_panel.event_view_button.click()
    qapp.processEvents()

    assert widget.library_panel.current_view_mode() == "event"
    assert widget.library_panel.find_event_node(event.id) is not None

    widget.library_panel.select_event(event.id)
    qapp.processEvents()

    assert widget.current_item_id() == event_note_id
    assert not widget.library_panel.new_folder_button.isEnabled()


def test_workspace_structure_drag_moves_items_without_menu_action(
    qapp, mock_i18n, workspace_manager
):
    folder_id = workspace_manager.create_folder("Archive")
    note_id = workspace_manager.create_note(title="Plan")
    widget = WorkspaceWidget(workspace_manager, mock_i18n)
    widget.show()
    qapp.processEvents()

    widget.library_panel._on_tree_drop_requested("item", note_id, "folder", folder_id)
    moved = workspace_manager.get_item(note_id)
    moved_asset = workspace_manager.get_primary_text_asset(note_id)

    assert moved is not None
    assert moved_asset is not None
    assert moved.folder_id == folder_id
    assert moved_asset.file_path.endswith("工作台条目/Archive/Plan.md")


def test_workspace_item_context_menu_surfaces_expected_actions(
    qapp, mock_i18n, workspace_manager
):
    note_id = workspace_manager.create_note(title="Plan")
    widget = WorkspaceWidget(workspace_manager, mock_i18n)

    menu = QMenu(widget)
    widget.library_panel._populate_item_context_menu(menu, note_id)
    action_texts = [action.text() for action in menu.actions() if action.text()]

    assert mock_i18n.t("workspace.open_item") in action_texts
    assert mock_i18n.t("workspace.open_in_new_window") in action_texts
    assert mock_i18n.t("workspace.copy_local_path") in action_texts
    assert mock_i18n.t("common.rename") in action_texts
    assert mock_i18n.t("common.delete") in action_texts


def test_workspace_structure_drag_blocks_non_text_system_item_move(
    qapp, mock_i18n, workspace_manager
):
    archive_folder_id = workspace_manager.create_folder("Archive")
    event = CalendarEvent(
        title="Audio Only Session",
        start_time="2026-03-18T10:00:00+00:00",
        end_time="2026-03-18T11:00:00+00:00",
    )
    event.save(workspace_manager.db)
    event_folder_id = workspace_manager.resolve_default_folder_id(event_id=event.id)

    item = WorkspaceItem(
        title="Audio Only Session",
        item_type="recording",
        folder_id=event_folder_id,
        source_kind="realtime_recording",
        source_event_id=event.id,
        status="completed",
    )
    item.save(workspace_manager.db)
    audio_path = workspace_manager.file_manager.get_workspace_path("fixtures", "audio-only.wav")
    Path(audio_path).parent.mkdir(parents=True, exist_ok=True)
    _write_valid_wav(Path(audio_path))
    audio_asset = WorkspaceAsset(
        item_id=item.id,
        asset_role="audio",
        file_path=audio_path,
        content_type="audio/wav",
    )
    audio_asset.save(workspace_manager.db)

    widget = WorkspaceWidget(workspace_manager, mock_i18n)
    widget.show()
    qapp.processEvents()

    with patch.object(widget.library_panel, "show_warning") as show_warning:
        widget.library_panel._on_tree_drop_requested("item", item.id, "folder", archive_folder_id)
        qapp.processEvents()

    unchanged_item = workspace_manager.get_item(item.id)

    assert unchanged_item is not None
    assert unchanged_item.folder_id == event_folder_id
    show_warning.assert_called()


def test_workspace_structure_accepts_external_batch_task_payload_move(
    qapp, mock_i18n, workspace_manager
):
    archive_folder_id = workspace_manager.create_folder("Archive")
    batch_root_folder = workspace_manager.ensure_batch_task_root_folder()
    task = TranscriptionTask(
        id="task-external-drag",
        file_path="/tmp/imported-notes.wav",
        file_name="imported-notes.wav",
        status="completed",
    )
    task.save(workspace_manager.db)
    item = WorkspaceItem(
        title="Imported Notes",
        item_type="document",
        folder_id=batch_root_folder.id,
        source_kind="batch_transcription",
        source_task_id="task-external-drag",
        status="completed",
    )
    item.save(workspace_manager.db)
    text_path = Path(workspace_manager.file_manager.get_workspace_path("Batch Notes.md"))
    text_path.parent.mkdir(parents=True, exist_ok=True)
    text_path.write_text("batch notes", encoding="utf-8")
    text_asset = WorkspaceAsset(
        item_id=item.id,
        asset_role="transcript",
        file_path=str(text_path),
        content_type="text/markdown",
    )
    text_asset.save(workspace_manager.db)
    item.primary_text_asset_id = text_asset.id
    item.save(workspace_manager.db)

    widget = WorkspaceWidget(workspace_manager, mock_i18n)
    widget.show()
    qapp.processEvents()

    payload = build_workspace_text_drag_payload(item.id, WORKSPACE_DRAG_SOURCE_BATCH_TASK)
    with patch.object(widget.library_panel, "_confirm_system_item_transfer", return_value="move"):
        widget.library_panel._on_external_workspace_drop_requested(payload, "folder", archive_folder_id)
        qapp.processEvents()

    moved_item = workspace_manager.get_item(item.id)
    moved_asset = workspace_manager.get_primary_text_asset(item.id)

    assert moved_item is not None
    assert moved_asset is not None
    assert moved_item.folder_id == archive_folder_id
    assert moved_asset.file_path.endswith("工作台条目/Archive/Imported Notes/Batch Notes.md")


def test_workspace_structure_drag_keeps_moved_item_visible_and_selected(
    qapp, mock_i18n, workspace_manager
):
    folder_id = workspace_manager.create_folder("Archive")
    note_id = workspace_manager.create_note(title="Plan")
    widget = WorkspaceWidget(workspace_manager, mock_i18n)
    widget.show()
    qapp.processEvents()
    widget.open_item(note_id)
    qapp.processEvents()

    widget.library_panel._on_tree_drop_requested("item", note_id, "folder", folder_id)
    qapp.processEvents()

    moved_item = workspace_manager.get_item(note_id)
    moved_node = widget.library_panel.find_item_node(note_id)

    assert moved_item is not None
    assert moved_item.folder_id == folder_id
    assert widget.current_item_id() == note_id
    assert moved_node is not None
    assert moved_node.parent() is not None
    assert moved_node.parent().data(0, Qt.ItemDataRole.UserRole) == "folder"
    assert moved_node.parent().data(0, Qt.ItemDataRole.UserRole + 1) == folder_id


def test_workspace_structure_drag_reparents_item_drop_onto_item_target(
    qapp, mock_i18n, workspace_manager
):
    folder_id = workspace_manager.create_folder("Archive")
    first_note_id = workspace_manager.create_note(title="Plan")
    second_note_id = workspace_manager.create_note(title="Spec")
    workspace_manager.move_item_to_folder(second_note_id, folder_id)
    widget = WorkspaceWidget(workspace_manager, mock_i18n)
    widget.show()
    qapp.processEvents()

    source_item = workspace_manager.get_item(first_note_id)
    widget.library_panel._on_tree_drop_requested("item", first_note_id, "item", second_note_id)
    qapp.processEvents()
    moved_item = workspace_manager.get_item(first_note_id)
    target_item = workspace_manager.get_item(second_note_id)

    assert source_item is not None
    assert moved_item is not None
    assert moved_item.folder_id == target_item.folder_id


def test_workspace_structure_drag_moves_user_folder_under_user_folder(
    qapp, mock_i18n, workspace_manager
):
    parent_folder_id = workspace_manager.create_folder("Projects")
    child_folder_id = workspace_manager.create_folder("Drafts")
    widget = WorkspaceWidget(workspace_manager, mock_i18n)
    widget.show()
    qapp.processEvents()

    widget.library_panel._on_tree_drop_requested("folder", child_folder_id, "folder", parent_folder_id)
    moved_folder = workspace_manager.get_folder(child_folder_id)

    assert moved_folder is not None
    assert moved_folder.parent_id == parent_folder_id
    current_folder = widget.library_panel.current_folder_id()
    selected_folder = widget.library_panel.folder_tree.currentItem()

    assert current_folder == child_folder_id
    assert selected_folder is not None
    assert selected_folder.data(0, Qt.ItemDataRole.UserRole) == "folder"
    assert selected_folder.data(0, Qt.ItemDataRole.UserRole + 1) == child_folder_id


def test_workspace_rename_button_renames_selected_item(
    qapp, mock_i18n, workspace_manager
):
    note_id = workspace_manager.create_note(title="Plan")
    widget = WorkspaceWidget(workspace_manager, mock_i18n)
    widget.show()
    qapp.processEvents()
    widget.library_panel.select_item(note_id)
    qapp.processEvents()

    with patch("ui.workspace.library_panel.QInputDialog.getText", return_value=("Renamed Plan", True)):
        widget.library_panel.rename_folder_button.click()
        qapp.processEvents()

    renamed_item = workspace_manager.get_item(note_id)
    renamed_node = widget.library_panel.find_item_node(note_id)

    assert renamed_item is not None
    assert renamed_item.title == "Renamed Plan"
    assert renamed_node is not None
    assert renamed_node.text(0) == "Renamed Plan"


def test_workspace_editor_edit_mode_saves_title_and_content_together(
    qapp, mock_i18n, workspace_manager
):
    note_id = workspace_manager.create_note(title="Plan", text_content="Old content")
    widget = WorkspaceWidget(workspace_manager, mock_i18n)
    widget.show()
    qapp.processEvents()
    widget.open_item(note_id)
    qapp.processEvents()

    widget.editor_panel.show_info = Mock()
    widget.editor_panel.toggle_edit_mode()
    widget.editor_panel.document_title_edit.setText("Renamed Plan")
    widget.editor_panel.text_edit.setPlainText("Updated content")
    widget.editor_panel.save_changes()
    qapp.processEvents()

    renamed_item = workspace_manager.get_item(note_id)
    renamed_node = widget.library_panel.find_item_node(note_id)
    renamed_asset = workspace_manager.get_primary_text_asset(note_id)

    assert renamed_item is not None
    assert renamed_asset is not None
    assert renamed_item.title == "Renamed Plan"
    assert widget.editor_panel.document_title_label.text() == "Renamed Plan"
    assert renamed_node is not None
    assert renamed_node.text(0) == "Renamed Plan"
    assert renamed_asset.file_path.endswith("工作台条目/Renamed Plan.md")
    assert workspace_manager.get_item_text_content(note_id) == "Updated content"


def test_workspace_delete_button_confirms_once_and_deletes_selected_item(
    qapp, mock_i18n, workspace_manager
):
    note_id = workspace_manager.create_note(title="Delete Me")
    widget = WorkspaceWidget(workspace_manager, mock_i18n)
    widget.show()
    qapp.processEvents()
    widget.library_panel.select_item(note_id)
    qapp.processEvents()

    with patch.object(widget.library_panel, "show_question", return_value=True) as confirm_dialog:
        widget.library_panel.delete_folder_button.click()
        qapp.processEvents()

    assert confirm_dialog.call_count == 1
    assert workspace_manager.get_item(note_id) is None


def test_workspace_delete_button_deletes_selected_event_folder_group(
    qapp, mock_i18n, workspace_manager
):
    event = CalendarEvent(
        title="Recording Session",
        start_time="2026-03-16T19:30:00+00:00",
        end_time="2026-03-16T20:00:00+00:00",
    )
    event.save(workspace_manager.db)
    note_id = workspace_manager.create_note(title="Session Note", event_id=event.id)
    folder_id = workspace_manager.resolve_default_folder_id(event_id=event.id)
    widget = WorkspaceWidget(workspace_manager, mock_i18n)
    widget.show()
    qapp.processEvents()
    widget.library_panel.select_folder(folder_id)
    qapp.processEvents()

    with patch.object(widget.library_panel, "show_question", return_value=True) as confirm_dialog:
        widget.library_panel.delete_folder_button.click()
        qapp.processEvents()

    assert confirm_dialog.call_count == 1
    assert workspace_manager.get_item(note_id) is None
    assert workspace_manager.get_folder(folder_id) is None


def test_workspace_drag_duplicate_item_name_shows_validation_warning(
    qapp, mock_i18n, workspace_manager
):
    folder_id = workspace_manager.create_folder("Archive")
    drafts_folder_id = workspace_manager.create_folder("Drafts")
    first_note_id = workspace_manager.create_note(title="Plan")
    second_note_id = workspace_manager.create_note(title="Plan")
    workspace_manager.move_item_to_folder(first_note_id, folder_id)
    workspace_manager.move_item_to_folder(second_note_id, drafts_folder_id)
    workspace_manager.rename_item(second_note_id, "Plan")
    widget = WorkspaceWidget(workspace_manager, mock_i18n)
    widget.show()
    qapp.processEvents()

    with patch.object(widget.library_panel, "show_warning") as warning_dialog:
        widget.library_panel._on_tree_drop_requested("item", second_note_id, "folder", folder_id)
        qapp.processEvents()

    moved_item = workspace_manager.get_item(second_note_id)
    assert moved_item is not None
    assert moved_item.folder_id != folder_id
    warning_dialog.assert_called_once()


def test_workspace_select_item_recovers_from_stale_tree_node_cache(
    qapp, mock_i18n, workspace_manager
):
    folder_id = workspace_manager.create_folder("Archive")
    note_id = workspace_manager.create_note(title="Plan")
    widget = WorkspaceWidget(workspace_manager, mock_i18n)
    widget.show()
    qapp.processEvents()

    stale_node = widget.library_panel.find_item_node(note_id)
    assert stale_node is not None

    workspace_manager.move_item_to_folder(note_id, folder_id)
    widget.refresh_items()
    qapp.processEvents()

    widget.library_panel._item_nodes[note_id] = stale_node
    widget.library_panel.select_item(note_id)
    qapp.processEvents()

    selected_node = widget.library_panel.find_item_node(note_id)

    assert selected_node is not None
    assert widget.library_panel.current_item_id() == note_id
    assert selected_node.parent() is not None
    assert selected_node.parent().data(0, Qt.ItemDataRole.UserRole + 1) == folder_id


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


def test_workspace_header_new_note_creates_workspace_item(
    qapp, mock_i18n, workspace_manager, transcription_manager
):
    widget = WorkspaceWidget(workspace_manager, mock_i18n, transcription_manager=transcription_manager)
    before_ids = {item.id for item in workspace_manager.list_items()}

    widget.library_panel.new_note_button.click()

    after_items = workspace_manager.list_items()
    created_items = [item for item in after_items if item.id not in before_ids]

    assert len(created_items) == 1
    assert created_items[0].source_kind == "workspace_note"
    assert workspace_manager.get_primary_text_asset(created_items[0].id) is not None
    assert widget.library_panel.current_item_id() == created_items[0].id


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


def test_workspace_tab_strip_exposes_stacked_tabs_menu_and_batch_close_actions(
    qapp, mock_i18n, workspace_manager
):
    first_id = workspace_manager.list_items()[0].id
    second_id = workspace_manager.create_note(title="Plan")
    third_id = workspace_manager.create_note(title="Spec")

    widget = WorkspaceWidget(workspace_manager, mock_i18n)
    widget.open_item(first_id)
    widget.open_item(second_id)
    widget.open_item(third_id)

    menu = widget._build_tab_stack_menu()
    action_texts = [action.text() for action in menu.actions() if action.text()]

    assert widget.tab_stack_button is not None
    assert "Plan" in action_texts
    assert "Spec" in action_texts
    assert mock_i18n.t("workspace.close_other_tabs") in action_texts
    assert mock_i18n.t("workspace.close_all_tabs") in action_texts


def test_workspace_document_tabs_expose_semantic_roles(qapp, mock_i18n, workspace_manager):
    widget = WorkspaceWidget(workspace_manager, mock_i18n)

    assert widget.document_tabs.property("role") == "workspace-document-tabs"
    assert widget.open_in_window_button.property("role") == "workspace-tab-action"
    assert widget.inspector_toggle_button.property("role") == "workspace-tab-action"
    close_button = widget.document_tabs.tabBar().tabButton(0, widget.document_tabs.tabBar().ButtonPosition.RightSide)
    assert close_button is not None
    assert close_button.property("role") == "workspace-tab-close"


def test_workspace_shell_uses_svg_icons_instead_of_text_glyphs(
    qapp, mock_i18n, workspace_manager
):
    widget = WorkspaceWidget(workspace_manager, mock_i18n)

    close_button = widget.document_tabs.tabBar().tabButton(
        0,
        widget.document_tabs.tabBar().ButtonPosition.RightSide,
    )

    assert not widget.library_panel.import_document_button.icon().isNull()
    assert not widget.open_in_window_button.icon().isNull()
    assert not widget.inspector_toggle_button.icon().isNull()
    assert close_button is not None
    assert not close_button.icon().isNull()
    assert close_button.text() == ""
    assert widget.open_in_window_button.text() == ""
    assert widget.inspector_toggle_button.text() == ""


def test_workspace_detached_window_is_top_level_and_preserves_current_asset_tab(
    qapp, mock_i18n, workspace_manager
):
    item_id = workspace_manager.list_items()[0].id
    workspace_manager.save_text_asset(item_id, "translation", "已翻译文本")
    widget = WorkspaceWidget(workspace_manager, mock_i18n)
    widget.open_item(item_id)
    widget.editor_panel.select_asset_role("translation")
    qapp.processEvents()

    widget.open_current_item_in_window_action.trigger()
    qapp.processEvents()

    detached_window = widget._detached_windows[item_id]
    assert detached_window.isWindow()
    assert detached_window.editor_panel.current_asset_role() == "translation"
    assert not hasattr(detached_window, "document_title_label")


def test_workspace_and_detached_window_can_toggle_inspector_panel(
    qapp, mock_i18n, workspace_manager
):
    item_id = workspace_manager.list_items()[0].id
    widget = WorkspaceWidget(workspace_manager, mock_i18n)
    widget.open_item(item_id)

    assert not widget.inspector_panel.isHidden()
    widget.inspector_toggle_button.click()
    qapp.processEvents()
    assert widget.inspector_panel.isHidden()
    widget.inspector_toggle_button.click()
    qapp.processEvents()
    assert not widget.inspector_panel.isHidden()

    widget.open_current_item_in_window_action.trigger()
    qapp.processEvents()
    detached_window = widget._detached_windows[item_id]

    assert not detached_window.inspector_panel.isHidden()
    detached_window.inspector_toggle_button.click()
    qapp.processEvents()
    assert detached_window.inspector_panel.isHidden()
    detached_window.inspector_toggle_button.click()
    qapp.processEvents()
    assert not detached_window.inspector_panel.isHidden()


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
        main_window.recording_dock.compact_panel.settings_button.click()
        qapp.processEvents()
        main_window.recording_dock.settings_panel.more_settings_button.click()
        qapp.processEvents()

        realtime_recorder.start_recording.assert_called_once()
        call_kwargs = realtime_recorder.start_recording.call_args.kwargs
        assert call_kwargs["input_source"] == 3
        assert call_kwargs["options"]["default_gain"] == 1.6
        assert main_window.current_page_name == "settings"
        assert main_window.pages["settings"].current_page_id() == "realtime"
    finally:
        main_window.close()


def test_recording_dock_exposes_compact_transport_and_popup_settings_in_main_window(
    qapp, mock_i18n, workspace_manager
):
    main_window, _ = build_main_window_with_workspace(
        qapp,
        mock_i18n,
        workspace_manager,
    )

    try:
        main_window.recording_dock.compact_panel.settings_button.click()
        qapp.processEvents()

        assert main_window.recording_dock.compact_panel.start_button.isVisible()
        assert main_window.recording_dock.compact_panel.overlay_button.isVisible()
        assert main_window.recording_dock.settings_popup.isVisible()
        assert main_window.recording_dock.settings_panel.input_source_combo is not None
        assert not hasattr(main_window.recording_dock.settings_panel, "session_tabs")
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
