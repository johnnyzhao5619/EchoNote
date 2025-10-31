# SPDX-License-Identifier: Apache-2.0
"""
Unit tests for FormatConverter.

Tests conversion of internal transcription format to TXT, SRT, and MD formats.
"""

import pytest

from core.transcription.format_converter import FormatConverter


class TestFormatConverter:
    """Test suite for FormatConverter class."""

    @pytest.fixture
    def converter(self):
        """Create FormatConverter instance."""
        return FormatConverter()

    @pytest.fixture
    def sample_segments(self):
        """Sample transcription segments for testing."""
        return [
            {"start": 0.0, "end": 2.5, "text": "Hello world"},
            {"start": 2.5, "end": 5.0, "text": "This is a test"},
            {"start": 5.0, "end": 8.5, "text": "Testing transcription"},
        ]

    @pytest.fixture
    def sample_internal_format(self, sample_segments):
        """Sample internal format dict."""
        return {"segments": sample_segments}

    # TXT Format Tests
    def test_convert_to_txt_success(self, converter, sample_internal_format):
        """Test successful conversion to TXT format."""
        result = converter.convert(sample_internal_format, "txt")

        assert isinstance(result, str)
        assert "Hello world" in result
        assert "This is a test" in result
        assert "Testing transcription" in result
        assert result.count("\n") == 2  # 3 lines, 2 newlines

    def test_convert_to_txt_empty_segments(self, converter):
        """Test TXT conversion with empty segments list."""
        internal_format = {"segments": []}

        with pytest.raises(ValueError, match="Empty segments list"):
            converter.convert(internal_format, "txt")

    def test_convert_to_txt_strips_whitespace(self, converter):
        """Test that TXT conversion strips whitespace from segments."""
        internal_format = {
            "segments": [
                {"start": 0.0, "end": 1.0, "text": "  Hello  "},
                {"start": 1.0, "end": 2.0, "text": "\nWorld\n"},
            ]
        }

        result = converter.convert(internal_format, "txt")
        lines = result.split("\n")

        assert lines[0] == "Hello"
        assert lines[1] == "World"

    def test_convert_to_txt_skips_empty_text(self, converter):
        """Test that TXT conversion skips segments with empty text."""
        internal_format = {
            "segments": [
                {"start": 0.0, "end": 1.0, "text": "Hello"},
                {"start": 1.0, "end": 2.0, "text": ""},
                {"start": 2.0, "end": 3.0, "text": "World"},
            ]
        }

        result = converter.convert(internal_format, "txt")
        lines = result.split("\n")

        assert len(lines) == 2
        assert lines[0] == "Hello"
        assert lines[1] == "World"

    # SRT Format Tests
    def test_convert_to_srt_success(self, converter, sample_internal_format):
        """Test successful conversion to SRT format."""
        result = converter.convert(sample_internal_format, "srt")

        assert isinstance(result, str)
        # Check subtitle numbering
        assert "1\n" in result
        assert "2\n" in result
        assert "3\n" in result
        # Check timestamps
        assert "00:00:00,000 --> 00:00:02,500" in result
        assert "00:00:02,500 --> 00:00:05,000" in result
        # Check text
        assert "Hello world" in result
        assert "This is a test" in result

    def test_convert_to_srt_timestamp_formatting(self, converter):
        """Test SRT timestamp formatting with various durations."""
        internal_format = {
            "segments": [
                {"start": 0.0, "end": 1.5, "text": "Short"},
                {"start": 65.25, "end": 125.75, "text": "Minutes"},
                {"start": 3665.5, "end": 3725.25, "text": "Hours"},
            ]
        }

        result = converter.convert(internal_format, "srt")

        # Check various timestamp formats
        assert "00:00:00,000 --> 00:00:01,500" in result
        assert "00:01:05,250 --> 00:02:05,750" in result
        assert "01:01:05,500 --> 01:02:05,250" in result

    def test_convert_to_srt_skips_empty_text(self, converter):
        """Test that SRT conversion skips segments with empty text."""
        internal_format = {
            "segments": [
                {"start": 0.0, "end": 1.0, "text": "Hello"},
                {"start": 1.0, "end": 2.0, "text": ""},
                {"start": 2.0, "end": 3.0, "text": "World"},
            ]
        }

        result = converter.convert(internal_format, "srt")

        # Should only have 2 subtitles
        assert "1\n" in result
        assert "2\n" in result
        assert "3\n" not in result.split("\n\n")[0]  # No third subtitle block

    # MD Format Tests
    def test_convert_to_md_success(self, converter, sample_internal_format):
        """Test successful conversion to Markdown format."""
        result = converter.convert(sample_internal_format, "md")

        assert isinstance(result, str)
        # Check header
        assert "# Transcription" in result
        # Check timestamp markers
        assert "**[00:00:00]**" in result
        assert "**[00:00:02]**" in result
        assert "**[00:00:05]**" in result
        # Check text
        assert "Hello world" in result
        assert "This is a test" in result

    def test_convert_to_md_timestamp_formatting(self, converter):
        """Test MD timestamp formatting."""
        internal_format = {
            "segments": [
                {"start": 0.0, "end": 1.0, "text": "Start"},
                {"start": 65.0, "end": 66.0, "text": "One minute"},
                {"start": 3665.0, "end": 3666.0, "text": "One hour"},
            ]
        }

        result = converter.convert(internal_format, "md")

        # Check timestamp formats (MD uses HH:MM:SS without milliseconds)
        assert "**[00:00:00]**" in result
        assert "**[00:01:05]**" in result
        assert "**[01:01:05]**" in result

    def test_convert_to_md_skips_empty_text(self, converter):
        """Test that MD conversion skips segments with empty text."""
        internal_format = {
            "segments": [
                {"start": 0.0, "end": 1.0, "text": "Hello"},
                {"start": 1.0, "end": 2.0, "text": ""},
                {"start": 2.0, "end": 3.0, "text": "World"},
            ]
        }

        result = converter.convert(internal_format, "md")
        lines = [line for line in result.split("\n") if line.strip()]

        # Should have header + 2 content lines
        assert len(lines) == 3
        assert lines[0] == "# Transcription"

    # Error Handling Tests
    def test_convert_unsupported_format(self, converter, sample_internal_format):
        """Test conversion with unsupported format raises ValueError."""
        with pytest.raises(ValueError, match="Unsupported format: pdf"):
            converter.convert(sample_internal_format, "pdf")

    def test_convert_case_insensitive_format(self, converter, sample_internal_format):
        """Test that format parameter is case-insensitive."""
        result_lower = converter.convert(sample_internal_format, "txt")
        result_upper = converter.convert(sample_internal_format, "TXT")
        result_mixed = converter.convert(sample_internal_format, "TxT")

        assert result_lower == result_upper == result_mixed

    def test_convert_missing_segments_key(self, converter):
        """Test conversion with missing 'segments' key raises ValueError."""
        internal_format = {"data": []}

        with pytest.raises(ValueError):
            converter.convert(internal_format, "txt")

    def test_convert_none_internal_format(self, converter):
        """Test conversion with None internal_format raises ValueError."""
        with pytest.raises(ValueError):
            converter.convert(None, "txt")

    def test_convert_empty_internal_format(self, converter):
        """Test conversion with empty dict raises ValueError."""
        with pytest.raises(ValueError):
            converter.convert({}, "txt")

    # Edge Cases
    def test_convert_segment_missing_text_key(self, converter):
        """Test conversion handles segments missing 'text' key."""
        internal_format = {"segments": [{"start": 0.0, "end": 1.0}]}

        result = converter.convert(internal_format, "txt")
        assert result == ""  # Empty text should be skipped

    def test_convert_segment_with_none_text(self, converter):
        """Test conversion handles segments with None text."""
        internal_format = {"segments": [{"start": 0.0, "end": 1.0, "text": None}]}

        # Should handle None gracefully
        result = converter.convert(internal_format, "txt")
        assert result == ""

    def test_convert_large_timestamp(self, converter):
        """Test conversion with very large timestamps (>24 hours)."""
        internal_format = {
            "segments": [
                {"start": 90000.0, "end": 90001.0, "text": "Long recording"},  # 25 hours
            ]
        }

        result_srt = converter.convert(internal_format, "srt")
        result_md = converter.convert(internal_format, "md")

        # Should handle large timestamps without crashing
        assert "Long recording" in result_srt
        assert "Long recording" in result_md

    def test_convert_zero_duration_segment(self, converter):
        """Test conversion with zero-duration segment."""
        internal_format = {
            "segments": [
                {"start": 5.0, "end": 5.0, "text": "Instant"},
            ]
        }

        result = converter.convert(internal_format, "srt")
        assert "00:00:05,000 --> 00:00:05,000" in result
        assert "Instant" in result

    def test_convert_unicode_text(self, converter):
        """Test conversion with Unicode characters."""
        internal_format = {
            "segments": [
                {"start": 0.0, "end": 1.0, "text": "Hello 世界 🌍"},
                {"start": 1.0, "end": 2.0, "text": "Привет мир"},
                {"start": 2.0, "end": 3.0, "text": "مرحبا بالعالم"},
            ]
        }

        for fmt in ["txt", "srt", "md"]:
            result = converter.convert(internal_format, fmt)
            assert "Hello 世界 🌍" in result
            assert "Привет мир" in result
            assert "مرحبا بالعالم" in result

    def test_convert_special_characters(self, converter):
        """Test conversion with special characters."""
        internal_format = {
            "segments": [
                {"start": 0.0, "end": 1.0, "text": "Line with\nnewline"},
                {"start": 1.0, "end": 2.0, "text": "Tab\there"},
                {"start": 2.0, "end": 3.0, "text": 'Quote: "Hello"'},
            ]
        }

        for fmt in ["txt", "srt", "md"]:
            result = converter.convert(internal_format, fmt)
            # Should preserve special characters
            assert isinstance(result, str)
            assert len(result) > 0

    def test_supported_formats_constant(self, converter):
        """Test that SUPPORTED_FORMATS constant is correct."""
        assert converter.SUPPORTED_FORMATS == ["txt", "srt", "md"]
        assert isinstance(converter.SUPPORTED_FORMATS, list)
