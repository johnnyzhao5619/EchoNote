"""数据层关键组件的集成测试。"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

pytest.importorskip("cryptography")

from data.database.connection import DatabaseConnection
from data.database.models import (
    CalendarEvent,
    EventAttachment,
    TranscriptionTask,
)
from data.security.encryption import SecurityManager
from data.security.oauth_manager import OAuthManager
from data.storage.file_manager import FileManager


@pytest.fixture()
def in_memory_db():
    """提供初始化完成的内存数据库，并在测试结束后关闭连接。"""
    db = DatabaseConnection(":memory:")
    db.initialize_schema()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture()
def security_manager(tmp_path: Path) -> SecurityManager:
    """使用临时目录创建安全管理器，避免污染用户目录。"""
    return SecurityManager(str(tmp_path / "security"))


@pytest.fixture()
def oauth_manager(security_manager: SecurityManager, tmp_path: Path) -> OAuthManager:
    """基于临时目录构建 OAuth 管理器。"""
    oauth_dir = tmp_path / "oauth"
    return OAuthManager(security_manager, str(oauth_dir))


@pytest.fixture()
def file_manager(tmp_path: Path) -> FileManager:
    """基于临时目录构建文件管理器。"""
    storage_dir = tmp_path / "storage"
    return FileManager(str(storage_dir))


def test_database_initialization_creates_schema(in_memory_db: DatabaseConnection):
    """验证数据库初始化后 schema 版本及基础表结构。"""
    version = in_memory_db.get_version()
    assert version >= 1

    tables = in_memory_db.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )
    table_names = {row["name"] for row in tables}
    expected_tables = {"app_settings", "transcription_tasks", "calendar_events"}
    assert expected_tables.issubset(table_names)


def test_data_models_crud_roundtrip(in_memory_db: DatabaseConnection):
    """验证任务、事件与附件模型的基本 CRUD 能力。"""
    task = TranscriptionTask(
        file_path="/test/audio.mp3",
        file_name="audio.mp3",
        file_size=1024000,
        status="pending",
        engine="faster-whisper",
    )
    task.save(in_memory_db)

    retrieved_task = TranscriptionTask.get_by_id(in_memory_db, task.id)
    assert retrieved_task is not None
    assert retrieved_task.file_name == "audio.mp3"

    event = CalendarEvent(
        title="Test Meeting",
        event_type="Event",
        start_time="2025-10-07T10:00:00",
        end_time="2025-10-07T11:00:00",
        attendees=["user1@example.com", "user2@example.com"],
    )
    event.save(in_memory_db)

    retrieved_event = CalendarEvent.get_by_id(in_memory_db, event.id)
    assert retrieved_event is not None
    assert retrieved_event.title == "Test Meeting"
    assert len(retrieved_event.attendees) == 2

    attachment = EventAttachment(
        event_id=event.id,
        attachment_type="recording",
        file_path="/recordings/test.wav",
        file_size=5_000_000,
    )
    attachment.save(in_memory_db)

    attachments = EventAttachment.get_by_event_id(in_memory_db, event.id)
    assert len(attachments) == 1
    assert attachments[0].file_path.endswith("test.wav")


def test_security_manager_end_to_end(security_manager: SecurityManager):
    """验证加解密、字典加解密以及密码哈希流程。"""
    plaintext = "This is sensitive data!"
    encrypted = security_manager.encrypt(plaintext)
    assert encrypted and encrypted != plaintext
    decrypted = security_manager.decrypt(encrypted)
    assert decrypted == plaintext

    data = {"api_key": "sk-test123", "token": "abc123xyz"}
    encrypted_dict = security_manager.encrypt_dict(data)
    decrypted_dict = security_manager.decrypt_dict(encrypted_dict)
    assert decrypted_dict == data

    password = "mypassword123"
    hashed = security_manager.hash_password(password)
    assert security_manager.verify_password(password, hashed)
    assert not security_manager.verify_password("wrongpassword", hashed)


def test_oauth_manager_token_lifecycle(oauth_manager: OAuthManager):
    """验证 OAuthManager 的令牌存储、读取、过期检测与删除。"""
    oauth_manager.store_token(
        provider="google",
        access_token="ya29.test",
        refresh_token="1//test",
        expires_in=3600,
    )

    assert oauth_manager.has_token("google")
    assert oauth_manager.get_access_token("google") == "ya29.test"
    assert oauth_manager.is_token_expired("google") is False

    oauth_manager.store_token(
        provider="test",
        access_token="old_token",
        refresh_token="refresh_token",
        expires_in=3600,
    )

    def refresh_callback(refresh_token: str) -> dict[str, str]:
        return {"access_token": "new_token", "expires_in": 3600}

    refreshed = oauth_manager.refresh_token_if_needed("test", refresh_callback)
    assert refreshed["access_token"] == "old_token"

    oauth_manager.delete_token("google")
    oauth_manager.delete_token("test")
    assert oauth_manager.has_token("google") is False


def test_file_manager_operations(file_manager: FileManager):
    """验证文件保存、读取、权限、列举与删除流程。"""
    content = "This is a test file."
    path = file_manager.save_text_file(
        content=content,
        filename="test.txt",
        subdirectory="Transcripts",
    )

    read_content = file_manager.read_text_file(path)
    assert read_content == content
    assert file_manager.file_exists(path)

    size = file_manager.get_file_size(path)
    assert size == len(content.encode("utf-8"))

    files = file_manager.list_files(subdirectory="Transcripts")
    assert Path(path) in {Path(f) for f in files}

    file_manager.ensure_directory("CustomDir")
    custom_dir = Path(file_manager.base_dir) / "CustomDir"
    assert custom_dir.exists()

    file_manager.set_file_permissions(path, 0o644)
    mode = os.stat(path).st_mode & 0o777
    assert mode == 0o644

    file_manager.delete_file(path)
    assert not file_manager.file_exists(path)
