import pytest

PyQt6 = pytest.importorskip("PyQt6")
from PyQt6.QtWidgets import QApplication, QFileDialog, QMessageBox

from ui.batch_transcribe.task_item import TaskItem
from ui.batch_transcribe.widget import BatchTranscribeWidget
from utils.i18n import I18nQtManager


class _DummyEngine:
    def get_name(self):
        return "Dummy Engine"


class DummyTranscriptionManager:
    def __init__(self):
        self.db = None
        self.speech_engine = _DummyEngine()
        self.export_calls = []

    def start_processing(self):
        return None

    def add_tasks_from_folder(self, folder_path):
        return []

    def delete_task(self, task_id):
        return None

    def add_task(self, file_path, options):
        return "dummy-task"

    def get_all_tasks(self):
        return []

    def get_task_status(self, task_id):
        return {
            "id": task_id,
            "file_name": "example.wav",
            "status": "completed",
        }

    def is_paused(self):
        return False

    def resume_processing(self):
        return None

    def pause_processing(self):
        return None

    def cancel_task(self, task_id):
        return True

    def export_result(self, task_id, output_format, file_path):
        self.export_calls.append((task_id, output_format, file_path))

    def retry_task(self, task_id):
        return True


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


def test_dialog_translations_follow_language(monkeypatch, tmp_path, qapp):
    i18n = I18nQtManager(default_language="zh_CN")
    manager = DummyTranscriptionManager()
    widget = BatchTranscribeWidget(manager, i18n)

    try:
        widget.refresh_timer.stop()

        captured_confirm = {}

        def fake_question(parent, title, text, buttons, default_button):
            captured_confirm["title"] = title
            captured_confirm["text"] = text
            return QMessageBox.StandardButton.Yes

        monkeypatch.setattr(QMessageBox, "question", staticmethod(fake_question))

        widget._on_clear_queue()
        assert captured_confirm["text"] == i18n.t("batch_transcribe.confirm_clear_queue")
        assert captured_confirm["title"] == i18n.t("batch_transcribe.clear_queue")

        i18n.change_language("en_US")
        qapp.processEvents()
        widget._on_clear_queue()
        assert captured_confirm["text"] == i18n.t("batch_transcribe.confirm_clear_queue")
        assert captured_confirm["title"] == i18n.t("batch_transcribe.clear_queue")

        export_path = tmp_path / "export.txt"

        def fake_get_save(parent, title, default_name, file_filter):
            return str(export_path), "Text Files (*.txt)"

        monkeypatch.setattr(
            QFileDialog,
            "getSaveFileName",
            staticmethod(fake_get_save),
        )

        captured_info = {}

        def fake_info(parent, title, text):
            captured_info["title"] = title
            captured_info["text"] = text

        monkeypatch.setattr(
            QMessageBox,
            "information",
            staticmethod(fake_info),
        )

        widget._on_task_export("task-123")
        assert captured_info["title"] == i18n.t("common.success")
        assert captured_info["text"] == i18n.t(
            "batch_transcribe.export_success",
            path=str(export_path),
        )
        assert manager.export_calls[-1] == ("task-123", "txt", str(export_path))

    finally:
        widget.refresh_timer.stop()
        widget.deleteLater()
        qapp.processEvents()


def test_task_item_metadata_rendering(qapp):
    i18n = I18nQtManager(default_language="en_US")
    task_data = {
        "id": "task-1",
        "file_name": "audio.wav",
        "status": "failed",
        "file_size": 5 * 1024 * 1024,
        "audio_duration": 125,
        "language": "English",
        "error_message": "Network failure",
    }

    task_item = TaskItem(task_data, i18n)

    try:
        task_item.update_display()
        task_item.update_translations()
        qapp.processEvents()

        expected_info_en = " | ".join([
            i18n.t("batch_transcribe.info.size", size="5.0 MB"),
            i18n.t("batch_transcribe.info.duration", duration="2:05"),
            i18n.t("batch_transcribe.info.language", language="English"),
        ])
        expected_error_en = i18n.t(
            "batch_transcribe.info.error", error="Network failure"
        )

        assert task_item.info_label.text() == expected_info_en
        assert task_item.error_label.isVisible()
        assert task_item.error_label.text() == expected_error_en

        # Trigger translation refresh and ensure formatting remains correct
        i18n.change_language("zh_CN")
        qapp.processEvents()
        task_item.update_translations()

        expected_info_cn = " | ".join([
            i18n.t("batch_transcribe.info.size", size="5.0 MB"),
            i18n.t("batch_transcribe.info.duration", duration="2:05"),
            i18n.t("batch_transcribe.info.language", language="English"),
        ])
        expected_error_cn = i18n.t(
            "batch_transcribe.info.error", error="Network failure"
        )

        assert task_item.info_label.text() == expected_info_cn
        assert task_item.error_label.isVisible()
        assert task_item.error_label.text() == expected_error_cn

    finally:
        task_item.deleteLater()
        qapp.processEvents()
