"""Tests for the transcription format converter."""

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.transcription.format_converter import FormatConverter


def test_srt_sequence_starts_at_one_when_first_segment_empty():
    """Ensure subtitle numbering starts at 1 even if the first segment is empty."""

    converter = FormatConverter()
    segments = [
        {"start": 0.0, "end": 0.5, "text": "   "},
        {"start": 0.5, "end": 1.5, "text": "第一句"},
        {"start": 1.5, "end": 2.5, "text": "第二句"},
    ]

    result = converter.convert({"segments": segments}, "srt")

    subtitle_blocks = [block for block in result.split("\n\n") if block]
    assert subtitle_blocks, "应当至少生成一个字幕块"
    assert subtitle_blocks[0].startswith("1\n"), "首个字幕块序号应为 1"
    if len(subtitle_blocks) > 1:
        assert subtitle_blocks[1].startswith("2\n"), "字幕序号应当连续递增"
