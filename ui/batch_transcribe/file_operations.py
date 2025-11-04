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

        for line in lines:
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

    def export_txt(self, save_path: str, content: str):
        """
        Export as plain text (remove timestamps if present).

        Args:
            save_path: Path to save the file
            content: Content to export
        """
        try:
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
