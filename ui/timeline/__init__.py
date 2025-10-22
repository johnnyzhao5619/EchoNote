"""Timeline UI components."""

import logging

from ui.timeline.widget import TimelineWidget
from ui.timeline.event_card import EventCard, CurrentTimeIndicator

logger = logging.getLogger('echonote.ui.timeline')

try:
    from ui.timeline.audio_player import AudioPlayer, AudioPlayerDialog
except ImportError as exc:  # pragma: no cover - exercised in degraded environments
    AudioPlayer = None
    AudioPlayerDialog = None
    logger.warning(
        "Audio playback components are unavailable: %s. Timeline UI will "
        "operate without inline audio playback.",
        exc,
    )

from ui.timeline.transcript_viewer import (
    TranscriptViewer,
    TranscriptViewerDialog
)

__all__ = [
    'TimelineWidget',
    'EventCard',
    'CurrentTimeIndicator',
    'AudioPlayer',
    'AudioPlayerDialog',
    'TranscriptViewer',
    'TranscriptViewerDialog'
]
