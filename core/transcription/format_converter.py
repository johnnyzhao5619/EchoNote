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
Format converter for transcription results.

Converts internal transcription format to various output formats (TXT, SRT, MD).
"""

import logging
from typing import Dict, List

logger = logging.getLogger("echonote.transcription.format_converter")


class FormatConverter:
    """
    Converts internal transcription format to various output formats.

    Supported formats:
    - TXT: Plain text, one segment per line
    - SRT: SubRip subtitle format with timestamps
    - MD: Markdown format with timestamp markers
    """

    SUPPORTED_FORMATS = ["txt", "srt", "md"]

    def convert(self, internal_format: dict, output_format: str) -> str:
        """
        Convert internal format to specified output format.

        Args:
            internal_format: Dict with 'segments' list containing
                           {'start': float, 'end': float, 'text': str}
            output_format: Target format ('txt', 'srt', or 'md')

        Returns:
            Formatted string in the requested format

        Raises:
            ValueError: If format is invalid or data is empty
        """
        # Validate format
        output_format = output_format.lower()
        if output_format not in self.SUPPORTED_FORMATS:
            raise ValueError(
                f"Unsupported format: {output_format}. "
                f"Supported formats: {', '.join(self.SUPPORTED_FORMATS)}"
            )

        # Validate data
        if not internal_format or "segments" not in internal_format:
            raise ValueError("Invalid internal format: missing 'segments' key")

        segments = internal_format["segments"]
        if not segments:
            raise ValueError("Empty segments list")

        # Convert based on format
        if output_format == "txt":
            return self._to_txt(segments)
        elif output_format == "srt":
            return self._to_srt(segments)
        elif output_format == "md":
            return self._to_md(segments)

    def _to_txt(self, segments: List[Dict]) -> str:
        """
        Convert to plain text format.

        Args:
            segments: List of segment dicts

        Returns:
            Plain text with one segment per line
        """
        lines = []
        for segment in segments:
            text = segment.get("text", "").strip()
            if text:
                lines.append(text)

        result = "\n".join(lines)
        logger.debug(f"Converted to TXT format: {len(lines)} lines")
        return result

    def _to_srt(self, segments: List[Dict]) -> str:
        """
        Convert to SRT subtitle format.

        Format:
        1
        00:00:00,000 --> 00:00:02,500
        Hello world

        2
        00:00:02,500 --> 00:00:05,000
        This is a test

        Args:
            segments: List of segment dicts

        Returns:
            SRT formatted string
        """
        srt_blocks = []

        subtitle_index = 1
        for segment in segments:
            text = segment.get("text", "").strip()
            if not text:
                continue

            start_time = segment.get("start", 0.0)
            end_time = segment.get("end", 0.0)

            # Format timestamps
            start_ts = self._format_timestamp_srt(start_time)
            end_ts = self._format_timestamp_srt(end_time)

            # Build SRT block
            srt_block = f"{subtitle_index}\n{start_ts} --> {end_ts}\n{text}\n"
            srt_blocks.append(srt_block)
            subtitle_index += 1

        result = "\n".join(srt_blocks)
        logger.debug(f"Converted to SRT format: {len(srt_blocks)} subtitles")
        return result

    def _to_md(self, segments: List[Dict]) -> str:
        """
        Convert to Markdown format with timestamp markers.

        Format:
        ## Transcription

        **[00:00:00]** Hello world

        **[00:00:02]** This is a test

        Args:
            segments: List of segment dicts

        Returns:
            Markdown formatted string
        """
        lines = ["# Transcription\n"]

        for segment in segments:
            text = segment.get("text", "").strip()
            if not text:
                continue

            start_time = segment.get("start", 0.0)
            timestamp = self._format_timestamp_md(start_time)

            # Format as markdown with bold timestamp
            line = f"**[{timestamp}]** {text}\n"
            lines.append(line)

        result = "\n".join(lines)
        logger.debug(f"Converted to MD format: {len(lines) - 1} segments")
        return result

    def _format_timestamp_srt(self, seconds: float) -> str:
        """
        Format timestamp for SRT format (HH:MM:SS,mmm).

        Args:
            seconds: Time in seconds

        Returns:
            Formatted timestamp string
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        milliseconds = int((seconds % 1) * 1000)

        return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"

    def _format_timestamp_md(self, seconds: float) -> str:
        """
        Format timestamp for Markdown format (HH:MM:SS).

        Args:
            seconds: Time in seconds

        Returns:
            Formatted timestamp string
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)

        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
