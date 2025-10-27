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
"""
File storage management for EchoNote application.

Handles secure file operations with proper permissions and organization.
"""

import logging
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger("echonote.storage")


class FileManager:
    """
    Manages file storage operations with security and organization.

    Provides methods for saving, reading, and deleting files with
    proper permission settings and directory management.
    """

    def __init__(self, base_dir: Optional[str] = None):
        """
        Initialize file manager.

        Args:
            base_dir: Base directory for file storage.
                     Defaults to ~/Documents/EchoNote
        """
        if base_dir is None:
            self.base_dir = Path.home() / "Documents" / "EchoNote"
        else:
            self.base_dir = Path(base_dir).expanduser()

        # Create base directory structure
        self._initialize_directories()

        logger.info(f"File manager initialized: {self.base_dir}")

    def _initialize_directories(self):
        """Create base directory structure."""
        directories = [
            self.base_dir,
            self.base_dir / "Recordings",
            self.base_dir / "Transcripts",
            self.base_dir / "Exports",
            self.base_dir / "Temp",
        ]

        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
            # Set directory permissions (owner read/write/execute only)
            self._set_directory_permissions(directory)

        logger.debug("Initialized directory structure")

    def _set_file_permissions(self, file_path: Path):
        """
        Set secure file permissions (owner read/write only).

        Args:
            file_path: Path to file
        """
        try:
            os.chmod(file_path, 0o600)
            logger.debug(f"Set secure permissions for: {file_path}")
        except (PermissionError, OSError) as e:
            logger.warning(f"Could not set file permissions for {file_path}: {e}")

    def _set_directory_permissions(self, directory: Path):
        """Set secure directory permissions (owner read/write/execute only)."""
        try:
            os.chmod(directory, 0o700)
            logger.debug(f"Set secure permissions for directory: {directory}")
        except (PermissionError, OSError) as e:
            logger.warning(f"Could not set directory permissions for {directory}: {e}")

    def save_file(
        self,
        content: bytes,
        filename: str,
        subdirectory: Optional[str] = None,
        overwrite: bool = False,
    ) -> str:
        """
        Save binary content to a file.

        Args:
            content: Binary content to save
            filename: Name of the file
            subdirectory: Optional subdirectory within base_dir
            overwrite: Whether to overwrite existing file

        Returns:
            Absolute path to saved file

        Raises:
            FileExistsError: If file exists and overwrite is False
        """
        # Determine target directory
        if subdirectory:
            target_dir = self.base_dir / subdirectory
            target_dir.mkdir(parents=True, exist_ok=True)
            self._set_directory_permissions(target_dir)
        else:
            target_dir = self.base_dir

        # Create file path
        file_path = target_dir / filename

        # Check if file exists
        if file_path.exists() and not overwrite:
            raise FileExistsError(f"File already exists: {file_path}")

        try:
            # Write content
            with open(file_path, "wb") as f:
                f.write(content)

            # Set secure permissions
            self._set_file_permissions(file_path)

            logger.info(f"Saved file: {file_path}")
            return str(file_path)

        except Exception as e:
            logger.error(f"Failed to save file: {e}")
            raise

    def save_text_file(
        self,
        content: str,
        filename: str,
        subdirectory: Optional[str] = None,
        overwrite: bool = False,
        encoding: str = "utf-8",
    ) -> str:
        """
        Save text content to a file.

        Args:
            content: Text content to save
            filename: Name of the file
            subdirectory: Optional subdirectory within base_dir
            overwrite: Whether to overwrite existing file
            encoding: Text encoding (default: utf-8)

        Returns:
            Absolute path to saved file
        """
        return self.save_file(content.encode(encoding), filename, subdirectory, overwrite)

    def read_file(self, file_path: str) -> bytes:
        """
        Read binary content from a file.

        Args:
            file_path: Path to file (absolute or relative to base_dir)

        Returns:
            Binary content

        Raises:
            FileNotFoundError: If file does not exist
        """
        path = self._resolve_path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        try:
            with open(path, "rb") as f:
                content = f.read()

            logger.debug(f"Read file: {path}")
            return content

        except Exception as e:
            logger.error(f"Failed to read file: {e}")
            raise

    def read_text_file(self, file_path: str, encoding: str = "utf-8") -> str:
        """
        Read text content from a file.

        Args:
            file_path: Path to file (absolute or relative to base_dir)
            encoding: Text encoding (default: utf-8)

        Returns:
            Text content
        """
        content = self.read_file(file_path)
        return content.decode(encoding)

    def delete_file(self, file_path: str):
        """
        Delete a file.

        Args:
            file_path: Path to file (absolute or relative to base_dir)

        Raises:
            FileNotFoundError: If file does not exist
        """
        path = self._resolve_path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        try:
            path.unlink()
            logger.info(f"Deleted file: {path}")

        except Exception as e:
            logger.error(f"Failed to delete file: {e}")
            raise

    def move_file(self, source_path: str, dest_path: str, overwrite: bool = False) -> str:
        """
        Move a file to a new location.

        Args:
            source_path: Source file path
            dest_path: Destination file path
            overwrite: Whether to overwrite existing file

        Returns:
            Absolute path to moved file

        Raises:
            FileNotFoundError: If source file does not exist
            FileExistsError: If destination exists and overwrite is False
        """
        source = self._resolve_path(source_path)
        dest = self._resolve_path(dest_path)

        if not source.exists():
            raise FileNotFoundError(f"Source file not found: {source}")

        if dest.exists() and not overwrite:
            raise FileExistsError(f"Destination file already exists: {dest}")

        try:
            # Ensure destination directory exists
            dest.parent.mkdir(parents=True, exist_ok=True)

            # Move file
            shutil.move(str(source), str(dest))

            # Set secure permissions
            self._set_file_permissions(dest)

            logger.info(f"Moved file: {source} -> {dest}")
            return str(dest)

        except Exception as e:
            logger.error(f"Failed to move file: {e}")
            raise

    def copy_file(self, source_path: str, dest_path: str, overwrite: bool = False) -> str:
        """
        Copy a file to a new location.

        Args:
            source_path: Source file path
            dest_path: Destination file path
            overwrite: Whether to overwrite existing file

        Returns:
            Absolute path to copied file

        Raises:
            FileNotFoundError: If source file does not exist
            FileExistsError: If destination exists and overwrite is False
        """
        source = self._resolve_path(source_path)
        dest = self._resolve_path(dest_path)

        if not source.exists():
            raise FileNotFoundError(f"Source file not found: {source}")

        if dest.exists() and not overwrite:
            raise FileExistsError(f"Destination file already exists: {dest}")

        try:
            # Ensure destination directory exists
            dest.parent.mkdir(parents=True, exist_ok=True)

            # Copy file
            shutil.copy2(str(source), str(dest))

            # Set secure permissions
            self._set_file_permissions(dest)

            logger.info(f"Copied file: {source} -> {dest}")
            return str(dest)

        except Exception as e:
            logger.error(f"Failed to copy file: {e}")
            raise

    def file_exists(self, file_path: str) -> bool:
        """
        Check if a file exists.

        Args:
            file_path: Path to file (absolute or relative to base_dir)

        Returns:
            True if file exists
        """
        path = self._resolve_path(file_path)
        return path.exists() and path.is_file()

    def get_file_size(self, file_path: str) -> int:
        """
        Get file size in bytes.

        Args:
            file_path: Path to file (absolute or relative to base_dir)

        Returns:
            File size in bytes

        Raises:
            FileNotFoundError: If file does not exist
        """
        path = self._resolve_path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        return path.stat().st_size

    def list_files(
        self, subdirectory: Optional[str] = None, pattern: str = "*", recursive: bool = False
    ) -> List[str]:
        """
        List files in a directory.

        Args:
            subdirectory: Optional subdirectory within base_dir
            pattern: Glob pattern for filtering (default: "*")
            recursive: Whether to search recursively

        Returns:
            List of absolute file paths
        """
        if subdirectory:
            search_dir = self.base_dir / subdirectory
        else:
            search_dir = self.base_dir

        if not search_dir.exists():
            return []

        if recursive:
            files = search_dir.rglob(pattern)
        else:
            files = search_dir.glob(pattern)

        # Filter to only files (not directories)
        file_paths = [str(f) for f in files if f.is_file()]

        logger.debug(f"Listed {len(file_paths)} file(s) in {search_dir}")
        return file_paths

    def create_unique_filename(
        self, base_name: str, extension: str, subdirectory: Optional[str] = None
    ) -> str:
        """
        Create a unique filename by adding a counter if needed.

        Args:
            base_name: Base name for the file
            extension: File extension (with or without dot)
            subdirectory: Optional subdirectory within base_dir

        Returns:
            Unique filename (not full path)
        """
        # Ensure extension starts with dot
        if not extension.startswith("."):
            extension = "." + extension

        # Determine target directory
        if subdirectory:
            target_dir = self.base_dir / subdirectory
        else:
            target_dir = self.base_dir

        # Try base name first
        filename = f"{base_name}{extension}"
        file_path = target_dir / filename

        if not file_path.exists():
            return filename

        # Add counter if file exists
        counter = 1
        while True:
            filename = f"{base_name}_{counter}{extension}"
            file_path = target_dir / filename

            if not file_path.exists():
                return filename

            counter += 1

    def get_temp_path(self, filename: str) -> str:
        """
        Get path for a temporary file.

        Args:
            filename: Name of temporary file

        Returns:
            Absolute path in temp directory
        """
        temp_dir = self.base_dir / "Temp"
        temp_dir.mkdir(parents=True, exist_ok=True)
        return str(temp_dir / filename)

    def cleanup_temp_files(self, older_than_days: int = 7):
        """
        Delete temporary files older than specified days.

        Args:
            older_than_days: Delete files older than this many days
        """
        temp_dir = self.base_dir / "Temp"

        if not temp_dir.exists():
            return

        from config.constants import SECONDS_PER_DAY

        cutoff_time = datetime.now().timestamp() - (older_than_days * SECONDS_PER_DAY)
        deleted_count = 0

        for file_path in temp_dir.glob("*"):
            if file_path.is_file():
                if file_path.stat().st_mtime < cutoff_time:
                    try:
                        file_path.unlink()
                        deleted_count += 1
                    except Exception as e:
                        logger.warning(f"Could not delete temp file {file_path}: {e}")

        logger.info(f"Cleaned up {deleted_count} temporary file(s)")

    def ensure_directory(self, dir_path: str):
        """
        Ensure a directory exists, creating it if necessary.

        Args:
            dir_path: Directory path (absolute or relative to base_dir)
        """
        path = self._resolve_path(dir_path)
        path.mkdir(parents=True, exist_ok=True)
        os.chmod(path, 0o700)
        logger.debug(f"Ensured directory exists: {path}")

    def set_file_permissions(self, file_path: str, mode: int = None):
        """
        Set file permissions.

        Args:
            file_path: Path to file (absolute or relative to base_dir)
            mode: Permission mode (default: FILE_PERMISSION_OWNER_RW - owner read/write only)

        Raises:
            FileNotFoundError: If file does not exist
        """
        if mode is None:
            mode = 0o600  # Owner read/write only

        path = self._resolve_path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        os.chmod(path, mode)
        logger.debug(f"Set permissions {oct(mode)} for: {path}")

    def _resolve_path(self, file_path: str) -> Path:
        """
        Resolve file path (handle both absolute and relative paths).

        Args:
            file_path: File path string

        Returns:
            Resolved Path object
        """
        path = Path(file_path).expanduser()

        # If path is not absolute, treat it as relative to base_dir
        if not path.is_absolute():
            path = self.base_dir / path

        return path
