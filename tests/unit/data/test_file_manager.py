# SPDX-License-Identifier: Apache-2.0
"""
Unit tests for FileManager class.

Tests file storage operations, permissions, and directory management.
"""

import os
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from data.storage.file_manager import FileManager


class TestFileManagerInitialization:
    """Test FileManager initialization."""

    def test_init_default_base_dir(self):
        """Test initialization with default base directory."""
        fm = FileManager()

        expected_dir = Path.home() / "Documents" / "EchoNote"
        assert fm.base_dir == expected_dir

    def test_init_custom_base_dir(self, tmp_path):
        """Test initialization with custom base directory."""
        custom_dir = tmp_path / "custom"
        fm = FileManager(str(custom_dir))

        assert fm.base_dir == custom_dir

    def test_init_creates_directory_structure(self, tmp_path):
        """Test that initialization creates directory structure."""
        base_dir = tmp_path / "echonote"
        fm = FileManager(str(base_dir))

        assert (base_dir / "Recordings").exists()
        assert (base_dir / "Transcripts").exists()
        assert (base_dir / "Exports").exists()
        assert (base_dir / "Temp").exists()

    def test_init_with_custom_recordings_dir(self, tmp_path):
        """Custom recordings directory should be used for recording files only."""
        base_dir = tmp_path / "echonote"
        recordings_dir = tmp_path / "custom_recordings"
        fm = FileManager(str(base_dir), recordings_dir=str(recordings_dir))

        assert fm.base_dir == base_dir
        assert fm.recordings_dir == recordings_dir
        assert recordings_dir.exists()
        assert (base_dir / "Transcripts").exists()

        file_path = fm.save_file(b"audio", "sample.wav", subdirectory="Recordings")
        assert Path(file_path).parent == recordings_dir


class TestFileSaveOperations:
    """Test file saving operations."""

    def test_save_file_basic(self, tmp_path):
        """Test basic file saving."""
        fm = FileManager(str(tmp_path))

        content = b"Hello, World!"
        file_path = fm.save_file(content, "test.txt")

        assert Path(file_path).exists()
        assert Path(file_path).read_bytes() == content

    def test_save_file_with_subdirectory(self, tmp_path):
        """Test saving file in subdirectory."""
        fm = FileManager(str(tmp_path))

        content = b"Test content"
        file_path = fm.save_file(content, "test.txt", subdirectory="Recordings")

        assert Path(file_path).exists()
        assert "Recordings" in file_path

    def test_save_file_creates_subdirectory(self, tmp_path):
        """Test that saving file creates subdirectory if needed."""
        fm = FileManager(str(tmp_path))

        content = b"Test content"
        file_path = fm.save_file(content, "test.txt", subdirectory="NewFolder")

        assert (tmp_path / "NewFolder").exists()
        assert Path(file_path).exists()

    def test_save_file_overwrite_false(self, tmp_path):
        """Test that saving existing file raises error when overwrite=False."""
        fm = FileManager(str(tmp_path))

        content = b"Test content"
        fm.save_file(content, "test.txt")

        with pytest.raises(FileExistsError):
            fm.save_file(content, "test.txt", overwrite=False)

    def test_save_file_overwrite_true(self, tmp_path):
        """Test overwriting existing file."""
        fm = FileManager(str(tmp_path))

        fm.save_file(b"Old content", "test.txt")
        file_path = fm.save_file(b"New content", "test.txt", overwrite=True)

        assert Path(file_path).read_bytes() == b"New content"

    def test_save_text_file(self, tmp_path):
        """Test saving text file."""
        fm = FileManager(str(tmp_path))

        content = "Hello, World!"
        file_path = fm.save_text_file(content, "test.txt")

        assert Path(file_path).exists()
        assert Path(file_path).read_text() == content

    def test_save_text_file_unicode(self, tmp_path):
        """Test saving text file with Unicode."""
        fm = FileManager(str(tmp_path))

        content = "Hello 世界 🌍"
        file_path = fm.save_text_file(content, "test.txt")

        assert Path(file_path).read_text(encoding="utf-8") == content

    def test_save_text_file_custom_encoding(self, tmp_path):
        """Test saving text file with custom encoding."""
        fm = FileManager(str(tmp_path))

        content = "Test content"
        file_path = fm.save_text_file(content, "test.txt", encoding="ascii")

        assert Path(file_path).exists()


class TestFileReadOperations:
    """Test file reading operations."""

    def test_read_file_absolute_path(self, tmp_path):
        """Test reading file with absolute path."""
        fm = FileManager(str(tmp_path))

        content = b"Test content"
        file_path = fm.save_file(content, "test.txt")

        read_content = fm.read_file(file_path)
        assert read_content == content

    def test_read_file_relative_path(self, tmp_path):
        """Test reading file with relative path."""
        fm = FileManager(str(tmp_path))

        content = b"Test content"
        fm.save_file(content, "test.txt")

        read_content = fm.read_file("test.txt")
        assert read_content == content

    def test_read_file_not_exists(self, tmp_path):
        """Test reading non-existent file raises error."""
        fm = FileManager(str(tmp_path))

        with pytest.raises(FileNotFoundError):
            fm.read_file("nonexistent.txt")

    def test_read_text_file(self, tmp_path):
        """Test reading text file."""
        fm = FileManager(str(tmp_path))

        content = "Hello, World!"
        file_path = fm.save_text_file(content, "test.txt")

        read_content = fm.read_text_file(file_path)
        assert read_content == content

    def test_read_text_file_unicode(self, tmp_path):
        """Test reading text file with Unicode."""
        fm = FileManager(str(tmp_path))

        content = "Hello 世界 🌍"
        fm.save_text_file(content, "test.txt")

        read_content = fm.read_text_file("test.txt")
        assert read_content == content


class TestFileDeleteOperations:
    """Test file deletion operations."""

    def test_delete_file(self, tmp_path):
        """Test deleting file."""
        fm = FileManager(str(tmp_path))

        file_path = fm.save_file(b"Test", "test.txt")
        fm.delete_file(file_path)

        assert not Path(file_path).exists()

    def test_delete_file_relative_path(self, tmp_path):
        """Test deleting file with relative path."""
        fm = FileManager(str(tmp_path))

        fm.save_file(b"Test", "test.txt")
        fm.delete_file("test.txt")

        assert not (tmp_path / "test.txt").exists()

    def test_delete_file_not_exists(self, tmp_path):
        """Test deleting non-existent file raises error."""
        fm = FileManager(str(tmp_path))

        with pytest.raises(FileNotFoundError):
            fm.delete_file("nonexistent.txt")


class TestFileMoveOperations:
    """Test file move operations."""

    def test_move_file(self, tmp_path):
        """Test moving file."""
        fm = FileManager(str(tmp_path))

        content = b"Test content"
        source = fm.save_file(content, "source.txt")
        dest = fm.move_file(source, "dest.txt")

        assert not Path(source).exists()
        assert Path(dest).exists()
        assert Path(dest).read_bytes() == content

    def test_move_file_to_subdirectory(self, tmp_path):
        """Test moving file to subdirectory."""
        fm = FileManager(str(tmp_path))

        source = fm.save_file(b"Test", "source.txt")
        dest = fm.move_file(source, "Recordings/dest.txt")

        assert not Path(source).exists()
        assert Path(dest).exists()
        assert "Recordings" in dest

    def test_move_file_overwrite_false(self, tmp_path):
        """Test moving file when destination exists and overwrite=False."""
        fm = FileManager(str(tmp_path))

        source = fm.save_file(b"Source", "source.txt")
        fm.save_file(b"Dest", "dest.txt")

        with pytest.raises(FileExistsError):
            fm.move_file(source, "dest.txt", overwrite=False)

    def test_move_file_overwrite_true(self, tmp_path):
        """Test moving file with overwrite."""
        fm = FileManager(str(tmp_path))

        source = fm.save_file(b"Source", "source.txt")
        fm.save_file(b"Dest", "dest.txt")

        dest = fm.move_file(source, "dest.txt", overwrite=True)

        assert not Path(source).exists()
        assert Path(dest).read_bytes() == b"Source"

    def test_move_file_source_not_exists(self, tmp_path):
        """Test moving non-existent file raises error."""
        fm = FileManager(str(tmp_path))

        with pytest.raises(FileNotFoundError):
            fm.move_file("nonexistent.txt", "dest.txt")


class TestFileCopyOperations:
    """Test file copy operations."""

    def test_copy_file(self, tmp_path):
        """Test copying file."""
        fm = FileManager(str(tmp_path))

        content = b"Test content"
        source = fm.save_file(content, "source.txt")
        dest = fm.copy_file(source, "dest.txt")

        assert Path(source).exists()
        assert Path(dest).exists()
        assert Path(dest).read_bytes() == content

    def test_copy_file_to_subdirectory(self, tmp_path):
        """Test copying file to subdirectory."""
        fm = FileManager(str(tmp_path))

        source = fm.save_file(b"Test", "source.txt")
        dest = fm.copy_file(source, "Recordings/dest.txt")

        assert Path(source).exists()
        assert Path(dest).exists()

    def test_copy_file_overwrite_false(self, tmp_path):
        """Test copying file when destination exists and overwrite=False."""
        fm = FileManager(str(tmp_path))

        source = fm.save_file(b"Source", "source.txt")
        fm.save_file(b"Dest", "dest.txt")

        with pytest.raises(FileExistsError):
            fm.copy_file(source, "dest.txt", overwrite=False)

    def test_copy_file_overwrite_true(self, tmp_path):
        """Test copying file with overwrite."""
        fm = FileManager(str(tmp_path))

        source = fm.save_file(b"Source", "source.txt")
        fm.save_file(b"Dest", "dest.txt")

        dest = fm.copy_file(source, "dest.txt", overwrite=True)

        assert Path(source).exists()
        assert Path(dest).read_bytes() == b"Source"

    def test_copy_file_source_not_exists(self, tmp_path):
        """Test copying non-existent file raises error."""
        fm = FileManager(str(tmp_path))

        with pytest.raises(FileNotFoundError):
            fm.copy_file("nonexistent.txt", "dest.txt")


class TestFileQueryOperations:
    """Test file query operations."""

    def test_file_exists_true(self, tmp_path):
        """Test checking if file exists."""
        fm = FileManager(str(tmp_path))

        fm.save_file(b"Test", "test.txt")

        assert fm.file_exists("test.txt")

    def test_file_exists_false(self, tmp_path):
        """Test checking if non-existent file exists."""
        fm = FileManager(str(tmp_path))

        assert not fm.file_exists("nonexistent.txt")

    def test_get_file_size(self, tmp_path):
        """Test getting file size."""
        fm = FileManager(str(tmp_path))

        content = b"Test content"
        fm.save_file(content, "test.txt")

        size = fm.get_file_size("test.txt")
        assert size == len(content)

    def test_get_file_size_not_exists(self, tmp_path):
        """Test getting size of non-existent file raises error."""
        fm = FileManager(str(tmp_path))

        with pytest.raises(FileNotFoundError):
            fm.get_file_size("nonexistent.txt")


class TestFileListingOperations:
    """Test file listing operations."""

    def test_list_files_basic(self, tmp_path):
        """Test listing files in base directory."""
        fm = FileManager(str(tmp_path))

        fm.save_file(b"1", "file1.txt")
        fm.save_file(b"2", "file2.txt")
        fm.save_file(b"3", "file3.txt")

        files = fm.list_files()

        assert len(files) >= 3
        assert any("file1.txt" in f for f in files)

    def test_list_files_subdirectory(self, tmp_path):
        """Test listing files in subdirectory."""
        fm = FileManager(str(tmp_path))

        fm.save_file(b"1", "file1.txt", subdirectory="Recordings")
        fm.save_file(b"2", "file2.txt", subdirectory="Recordings")

        files = fm.list_files(subdirectory="Recordings")

        assert len(files) == 2

    def test_list_files_pattern(self, tmp_path):
        """Test listing files with pattern."""
        fm = FileManager(str(tmp_path))

        fm.save_file(b"1", "file1.txt")
        fm.save_file(b"2", "file2.txt")
        fm.save_file(b"3", "file1.mp3")

        files = fm.list_files(pattern="*.txt")

        assert all(f.endswith(".txt") for f in files)

    def test_list_files_recursive(self, tmp_path):
        """Test listing files recursively."""
        fm = FileManager(str(tmp_path))

        fm.save_file(b"1", "file1.txt")
        fm.save_file(b"2", "file2.txt", subdirectory="Recordings")
        fm.save_file(b"3", "file3.txt", subdirectory="Recordings/Sub")

        files = fm.list_files(recursive=True)

        assert len(files) >= 3

    def test_list_files_empty_directory(self, tmp_path):
        """Test listing files in empty directory."""
        fm = FileManager(str(tmp_path))

        files = fm.list_files(subdirectory="Recordings")

        assert len(files) == 0

    def test_list_files_nonexistent_directory(self, tmp_path):
        """Test listing files in non-existent directory."""
        fm = FileManager(str(tmp_path))

        files = fm.list_files(subdirectory="NonExistent")

        assert len(files) == 0


class TestUniqueFilenameGeneration:
    """Test unique filename generation."""

    def test_create_unique_filename_no_conflict(self, tmp_path):
        """Test creating unique filename when no conflict."""
        fm = FileManager(str(tmp_path))

        filename = fm.create_unique_filename("test", ".txt")

        assert filename == "test.txt"

    def test_create_unique_filename_with_conflict(self, tmp_path):
        """Test creating unique filename when file exists."""
        fm = FileManager(str(tmp_path))

        fm.save_file(b"Test", "test.txt")
        filename = fm.create_unique_filename("test", ".txt")

        assert filename == "test_1.txt"

    def test_create_unique_filename_multiple_conflicts(self, tmp_path):
        """Test creating unique filename with multiple conflicts."""
        fm = FileManager(str(tmp_path))

        fm.save_file(b"1", "test.txt")
        fm.save_file(b"2", "test_1.txt")
        fm.save_file(b"3", "test_2.txt")

        filename = fm.create_unique_filename("test", ".txt")

        assert filename == "test_3.txt"

    def test_create_unique_filename_extension_without_dot(self, tmp_path):
        """Test creating unique filename with extension without dot."""
        fm = FileManager(str(tmp_path))

        filename = fm.create_unique_filename("test", "txt")

        assert filename == "test.txt"

    def test_create_unique_filename_in_subdirectory(self, tmp_path):
        """Test creating unique filename in subdirectory."""
        fm = FileManager(str(tmp_path))

        fm.save_file(b"Test", "test.txt", subdirectory="Recordings")
        filename = fm.create_unique_filename("test", ".txt", subdirectory="Recordings")

        assert filename == "test_1.txt"


class TestTempFileOperations:
    """Test temporary file operations."""

    def test_get_temp_path(self, tmp_path):
        """Test getting temporary file path."""
        fm = FileManager(str(tmp_path))

        temp_path = fm.get_temp_path("temp.txt")

        assert "Temp" in temp_path
        assert "temp.txt" in temp_path

    def test_cleanup_temp_files(self, tmp_path):
        """Test cleaning up old temporary files."""
        fm = FileManager(str(tmp_path))

        # Create old temp file
        old_file = Path(fm.get_temp_path("old.txt"))
        old_file.write_bytes(b"old")

        # Set modification time to 10 days ago
        old_time = (datetime.now() - timedelta(days=10)).timestamp()
        os.utime(old_file, (old_time, old_time))

        # Create recent temp file
        recent_file = Path(fm.get_temp_path("recent.txt"))
        recent_file.write_bytes(b"recent")

        # Cleanup files older than 7 days
        fm.cleanup_temp_files(older_than_days=7)

        # Old file should be deleted, recent file should remain
        assert not old_file.exists()
        assert recent_file.exists()

    def test_cleanup_temp_files_no_temp_dir(self, tmp_path):
        """Test cleanup when temp directory doesn't exist."""
        fm = FileManager(str(tmp_path))

        # Remove temp directory
        temp_dir = tmp_path / "Temp"
        if temp_dir.exists():
            import shutil

            shutil.rmtree(temp_dir)

        # Should not raise error
        fm.cleanup_temp_files()


class TestDirectoryOperations:
    """Test directory operations."""

    def test_ensure_directory(self, tmp_path):
        """Test ensuring directory exists."""
        fm = FileManager(str(tmp_path))

        fm.ensure_directory("NewFolder")

        assert (tmp_path / "NewFolder").exists()

    def test_ensure_directory_already_exists(self, tmp_path):
        """Test ensuring directory that already exists."""
        fm = FileManager(str(tmp_path))

        (tmp_path / "ExistingFolder").mkdir()

        # Should not raise error
        fm.ensure_directory("ExistingFolder")

    def test_ensure_directory_nested(self, tmp_path):
        """Test ensuring nested directory."""
        fm = FileManager(str(tmp_path))

        fm.ensure_directory("Parent/Child/GrandChild")

        assert (tmp_path / "Parent" / "Child" / "GrandChild").exists()


class TestFilePermissions:
    """Test file permission operations."""

    def test_set_file_permissions(self, tmp_path):
        """Test setting file permissions."""
        fm = FileManager(str(tmp_path))

        file_path = fm.save_file(b"Test", "test.txt")

        # Set custom permissions
        fm.set_file_permissions(file_path, mode=0o644)

        # File should still exist
        assert Path(file_path).exists()

    def test_set_file_permissions_not_exists(self, tmp_path):
        """Test setting permissions on non-existent file raises error."""
        fm = FileManager(str(tmp_path))

        with pytest.raises(FileNotFoundError):
            fm.set_file_permissions("nonexistent.txt")


class TestPathResolution:
    """Test path resolution."""

    def test_resolve_path_absolute(self, tmp_path):
        """Test resolving absolute path."""
        fm = FileManager(str(tmp_path))

        absolute_path = tmp_path / "test.txt"
        resolved = fm._resolve_path(str(absolute_path))

        assert resolved == absolute_path

    def test_resolve_path_relative(self, tmp_path):
        """Test resolving relative path."""
        fm = FileManager(str(tmp_path))

        resolved = fm._resolve_path("test.txt")

        assert resolved == tmp_path / "test.txt"

    def test_resolve_path_with_tilde(self, tmp_path):
        """Test resolving path with tilde."""
        fm = FileManager(str(tmp_path))

        # This will expand to user's home directory
        resolved = fm._resolve_path("~/test.txt")

        assert resolved.is_absolute()
