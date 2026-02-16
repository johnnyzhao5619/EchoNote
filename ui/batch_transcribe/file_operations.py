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
File operations for transcript viewer.

Extracted from transcript_viewer.py to reduce class size and improve separation of concerns.
"""

import logging
import os
import re
import shutil
from typing import List, Tuple

from PySide6.QtCore import QThread, Signal

logger = logging.getLogger("echonote.ui.file_operations")

# Constants
SMALL_FILE_THRESHOLD = 1024 * 1024  # 1MB
CHUNK_SIZE = 64 * 1024  # 64KB
DEFAULT_SEGMENT_DURATION = 5  # seconds
SECONDS_PER_HOUR = 3600
SECONDS_PER_MINUTE = 60


class FileLoadWorker(QThread):
    """
    Worker thread for loading transcript files asynchronously.

    Prevents UI blocking when loading large transcript files.
    """

    # Signals
    finished = Signal(str)  # Emits loaded content
    error = Signal(str)  # Emits error message
    progress = Signal(int)  # Emits progress percentage

    def __init__(self, file_path: str):
        """
        Initialize file load worker.

        Args:
            file_path: Path to transcript file
        """
        super().__init__()
        self.file_path = file_path
        self._is_cancelled = False

    def run(self):
        """Load file in background thread."""
        try:
            if not os.path.exists(self.file_path):
                self.error.emit(f"File not found: {self.file_path}")
                return

            # Get file size for progress tracking
            file_size = os.path.getsize(self.file_path)

            # For small files, load directly
            if file_size < SMALL_FILE_THRESHOLD:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                self.progress.emit(100)
                self.finished.emit(content)
                return

            # For large files, load in chunks with progress
            content_parts = []
            bytes_read = 0
            chunk_size = CHUNK_SIZE

            with open(self.file_path, "r", encoding="utf-8") as f:
                while not self._is_cancelled:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break

                    content_parts.append(chunk)
                    bytes_read += len(chunk.encode("utf-8"))

                    # Update progress
                    progress = min(100, int((bytes_read / file_size) * 100))
                    self.progress.emit(progress)

            if not self._is_cancelled:
                content = "".join(content_parts)
                self.finished.emit(content)

        except Exception as e:
            logger.error(f"Error loading file {self.file_path}: {e}")
            self.error.emit(f"Error loading file: {e}")

    def cancel(self):
        """Cancel the loading operation."""
        self._is_cancelled = True


class TranscriptParser:
    """Utility class for parsing transcript content."""

    @staticmethod
    def parse_transcript_content(content: str) -> List[Tuple[str, str, str]]:
        """
        Parse transcript content to extract segments with timestamps.

        Args:
            content: Raw transcript content

        Returns:
            List of tuples (start_time, end_time, text)
        """
        segments = []
        lines = content.strip().split("\n")

        simple_timestamp_pattern = re.compile(
            r"^\[(?:(\d{1,2}):)?(\d{1,2}):(\d{2})(?:\.(\d{1,3}))?\]\s*(.*)$"
        )

        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue

            # Try to parse timestamp format: [00:00:00.000 --> 00:00:05.000] Text
            if line.startswith("[") and "] " in line:
                try:
                    timestamp_part, text_part = line.split("] ", 1)
                    timestamp_part = timestamp_part[1:]  # Remove opening bracket

                    if " --> " in timestamp_part:
                        start_time, end_time = timestamp_part.split(" --> ")
                        segments.append((start_time.strip(), end_time.strip(), text_part.strip()))
                        continue
                except ValueError:
                    pass

            # Parse simple timestamp format: [MM:SS] Text or [HH:MM:SS(.mmm)] Text
            simple_match = simple_timestamp_pattern.match(line)
            if simple_match:
                hours = int(simple_match.group(1) or 0)
                minutes = int(simple_match.group(2) or 0)
                seconds = int(simple_match.group(3) or 0)
                milliseconds = int((simple_match.group(4) or "0").ljust(3, "0"))
                text_part = simple_match.group(5).strip()

                start_total = hours * SECONDS_PER_HOUR + minutes * SECONDS_PER_MINUTE + seconds
                start_time = f"{hours:02d}:{minutes:02d}:{seconds:02d}.{milliseconds:03d}"

                # Default end time is +5s, then try to align to next timestamp line.
                end_total = start_total + DEFAULT_SEGMENT_DURATION
                for next_line in lines[i + 1 :]:
                    next_line = next_line.strip()
                    next_match = simple_timestamp_pattern.match(next_line)
                    if not next_match:
                        continue
                    next_hours = int(next_match.group(1) or 0)
                    next_minutes = int(next_match.group(2) or 0)
                    next_seconds = int(next_match.group(3) or 0)
                    end_total = (
                        next_hours * SECONDS_PER_HOUR
                        + next_minutes * SECONDS_PER_MINUTE
                        + next_seconds
                    )
                    break

                end_hours = end_total // SECONDS_PER_HOUR
                end_minutes = (end_total % SECONDS_PER_HOUR) // SECONDS_PER_MINUTE
                end_seconds = end_total % SECONDS_PER_MINUTE
                end_time = f"{end_hours:02d}:{end_minutes:02d}:{end_seconds:02d}.000"

                segments.append((start_time, end_time, text_part))
                continue

            # If no timestamp found, create basic segment
            segments.append(("", "", line))

        return segments

    @staticmethod
    def create_basic_segments(content: str) -> List[Tuple[str, str, str]]:
        """
        Create basic segments without timestamps (5-second intervals).

        Args:
            content: Raw transcript content

        Returns:
            List of tuples (start_time, end_time, text)
        """
        segments = []
        lines = [line.strip() for line in content.strip().split("\n") if line.strip()]

        for i, line in enumerate(lines):
            start_seconds = i * DEFAULT_SEGMENT_DURATION
            end_seconds = (i + 1) * DEFAULT_SEGMENT_DURATION
            start_time = f"{start_seconds // SECONDS_PER_HOUR:02d}:{(start_seconds % SECONDS_PER_HOUR) // SECONDS_PER_MINUTE:02d}:{start_seconds % SECONDS_PER_MINUTE:02d}.000"
            end_time = f"{end_seconds // SECONDS_PER_HOUR:02d}:{(end_seconds % SECONDS_PER_HOUR) // SECONDS_PER_MINUTE:02d}:{end_seconds % SECONDS_PER_MINUTE:02d}.000"
            segments.append((start_time, end_time, line))

        return segments


class FileExporter:
    """Handles file export operations for different formats."""

    def __init__(self, i18n):
        """Initialize file exporter with i18n support."""
        self.i18n = i18n

    def _validate_export_target(self, save_path: str, content: str):
        """Validate export input and destination before writing files."""
        if not content or not content.strip():
            raise ValueError(self.i18n.t("exceptions.batch_transcribe_viewer.content_is_empty"))

        save_dir = os.path.dirname(save_path)
        if save_dir and not os.path.exists(save_dir):
            raise FileNotFoundError(f"Directory does not exist: {save_dir}")

        if os.path.exists(save_path) and not os.access(save_path, os.W_OK):
            raise PermissionError(f"No write permission for file: {save_path}")

        if not os.path.exists(save_path):
            check_dir = save_dir if save_dir else "."
            if not os.access(check_dir, os.W_OK):
                raise PermissionError(f"No write permission for directory: {check_dir}")

        stat = shutil.disk_usage(save_dir if save_dir else ".")
        if stat.free < SMALL_FILE_THRESHOLD:
            raise OSError(self.i18n.t("exceptions.batch_transcribe_viewer.insufficient_disk_space"))

    def export_txt(self, save_path: str, content: str):
        """
        Export as plain text (remove timestamps if present).

        Args:
            save_path: Path to save the file
            content: Content to export
        """
        try:
            self._validate_export_target(save_path, content)

            # Remove timestamp markers if present
            lines = content.split("\n")
            clean_lines = []

            for line in lines:
                line = line.strip()
                if not line:
                    continue

                # Remove timestamp format: [00:00:00.000 --> 00:00:05.000] Text
                if line.startswith("[") and "] " in line:
                    try:
                        _, text_part = line.split("] ", 1)
                        clean_lines.append(text_part.strip())
                    except ValueError:
                        clean_lines.append(line)
                else:
                    clean_lines.append(line)

            # Join with double newlines for better readability
            clean_content = "\n\n".join(clean_lines)

            with open(save_path, "w", encoding="utf-8") as f:
                f.write(clean_content)

        except PermissionError as e:
            logger.error(f"Permission error exporting TXT to {save_path}: {e}", exc_info=True)
            raise PermissionError(self.i18n.t("viewer.export_error_permission"))
        except OSError as e:
            logger.error(f"OS error exporting TXT to {save_path}: {e}", exc_info=True)
            if "disk" in str(e).lower() or "space" in str(e).lower():
                raise OSError(self.i18n.t("viewer.export_error_disk_full"))
            raise OSError(self.i18n.t("viewer.export_error_details", error=str(e)))
        except ValueError as e:
            logger.error(f"Invalid content for TXT export: {e}")
            raise ValueError(self.i18n.t("viewer.export_error_invalid_content"))
        except Exception as e:
            logger.error(f"Error exporting TXT to {save_path}: {e}")
            raise Exception(self.i18n.t("viewer.export_error_details", error=str(e)))

    def export_srt(self, save_path: str, content: str):
        """
        Export as SRT subtitle format.

        Args:
            save_path: Path to save the file
            content: Content to export
        """
        try:
            self._validate_export_target(save_path, content)
            segments = TranscriptParser.parse_transcript_content(content)

            # If no timestamps found, create basic segments
            if not any(seg[0] for seg in segments):
                segments = TranscriptParser.create_basic_segments(content)

            srt_lines = []
            for i, (start_time, end_time, text) in enumerate(segments, 1):
                if not text.strip():
                    continue

                # Convert timestamp format from HH:MM:SS.mmm to HH:MM:SS,mmm (SRT format)
                start_srt = start_time.replace(".", ",") if start_time else "00:00:00,000"
                end_srt = end_time.replace(".", ",") if end_time else "00:00:05,000"

                srt_lines.extend(
                    [
                        str(i),
                        f"{start_srt} --> {end_srt}",
                        text.strip(),
                        "",  # Empty line between subtitles
                    ]
                )

            with open(save_path, "w", encoding="utf-8") as f:
                f.write("\n".join(srt_lines))

        except PermissionError as e:
            logger.error(f"Permission error exporting SRT to {save_path}: {e}", exc_info=True)
            raise PermissionError(self.i18n.t("viewer.export_error_permission"))
        except OSError as e:
            logger.error(f"OS error exporting SRT to {save_path}: {e}", exc_info=True)
            if "disk" in str(e).lower() or "space" in str(e).lower():
                raise OSError(self.i18n.t("viewer.export_error_disk_full"))
            raise OSError(self.i18n.t("viewer.export_error_details", error=str(e)))
        except ValueError as e:
            logger.error(f"Invalid content for SRT export: {e}")
            raise ValueError(self.i18n.t("viewer.export_error_invalid_content"))
        except Exception as e:
            logger.error(f"Error exporting SRT to {save_path}: {e}")
            raise Exception(self.i18n.t("viewer.export_error_details", error=str(e)))

    def export_md(self, save_path: str, content: str):
        """
        Export as Markdown format.

        Args:
            save_path: Path to save the file
            content: Content to export
        """
        try:
            self._validate_export_target(save_path, content)
            segments = TranscriptParser.parse_transcript_content(content)

            md_lines = [
                "# Transcript",
                "",
                f"*Generated by EchoNote*",
                "",
            ]

            # If we have timestamps, create a structured format
            if any(seg[0] for seg in segments):
                md_lines.extend(
                    [
                        "## Timeline",
                        "",
                    ]
                )

                for start_time, end_time, text in segments:
                    if not text.strip():
                        continue

                    if start_time and end_time:
                        md_lines.extend(
                            [
                                f"### {start_time} - {end_time}",
                                "",
                                text.strip(),
                                "",
                            ]
                        )
                    else:
                        md_lines.extend(
                            [
                                text.strip(),
                                "",
                            ]
                        )
            else:
                # No timestamps, create basic markdown
                md_lines.extend(self._create_basic_markdown(content).split("\n"))

            with open(save_path, "w", encoding="utf-8") as f:
                f.write("\n".join(md_lines))

        except PermissionError as e:
            logger.error(f"Permission error exporting Markdown to {save_path}: {e}", exc_info=True)
            raise PermissionError(self.i18n.t("viewer.export_error_permission"))
        except OSError as e:
            logger.error(f"OS error exporting Markdown to {save_path}: {e}", exc_info=True)
            if "disk" in str(e).lower() or "space" in str(e).lower():
                raise OSError(self.i18n.t("viewer.export_error_disk_full"))
            raise OSError(self.i18n.t("viewer.export_error_details", error=str(e)))
        except ValueError as e:
            logger.error(f"Invalid content for Markdown export: {e}")
            raise ValueError(self.i18n.t("viewer.export_error_invalid_content"))
        except Exception as e:
            logger.error(f"Error exporting Markdown to {save_path}: {e}")
            raise Exception(self.i18n.t("viewer.export_error_details", error=str(e)))

    def _create_basic_markdown(self, content: str) -> str:
        """
        Create basic Markdown without timestamps.

        Args:
            content: Raw content

        Returns:
            Formatted markdown string
        """
        lines = [line.strip() for line in content.strip().split("\n") if line.strip()]
        md_lines = [
            "## Content",
            "",
        ]

        for line in lines:
            md_lines.extend([f"- {line}", ""])

        return "\n".join(md_lines)
