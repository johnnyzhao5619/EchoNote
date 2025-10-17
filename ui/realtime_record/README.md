# Real-time Recording UI Components

## Overview

This module provides UI components for real-time audio recording, transcription, and translation.

> **Note**
> PyAudio is an optional dependency. When it is not installed, `AudioCapture`
> creation will raise an `ImportError`, the application will continue running,
> and the real-time recording UI automatically disables microphone features
> while showing installation guidance.

## Components

### RealtimeRecordWidget

Main widget for real-time recording interface.

**Features:**

- Audio input source selection
- Gain adjustment (0.1x - 2.0x)
- Source and target language selection
- Real-time transcription display
- Real-time translation display (optional)
- Audio waveform visualization
- Export functionality

**Usage:**

```python
from PyQt6.QtWidgets import QApplication
from ui.realtime_record import RealtimeRecordWidget
from core.realtime.recorder import RealtimeRecorder
from engines.audio.capture import AudioCapture
from engines.speech.faster_whisper_engine import FasterWhisperEngine
from engines.translation.google_translate import GoogleTranslateEngine
from data.database.connection import DatabaseConnection
from data.storage.file_manager import FileManager
from utils.i18n import I18nQtManager

# Initialize dependencies
audio_capture = AudioCapture()
speech_engine = FasterWhisperEngine(model_size='base')
translation_engine = GoogleTranslateEngine()
db = DatabaseConnection('~/.echonote/data.db')
file_manager = FileManager('~/.echonote')
i18n = I18nQtManager()

# Create recorder
recorder = RealtimeRecorder(
    audio_capture=audio_capture,
    speech_engine=speech_engine,
    translation_engine=translation_engine,
    db_connection=db,
    file_manager=file_manager
)

# Create widget
widget = RealtimeRecordWidget(
    recorder=recorder,
    audio_capture=audio_capture,
    i18n_manager=i18n
)

# Show widget
widget.show()
```

### AudioVisualizer

Audio waveform and volume bar visualization component.

**Features:**

- Real-time waveform display
- Volume level bar
- Color-coded volume levels (green/orange/red)
- 30 FPS refresh rate

**Usage:**

```python
from ui.realtime_record import AudioVisualizer
import numpy as np

# Create visualizer
visualizer = AudioVisualizer()

# Update with audio data
audio_chunk = np.random.randn(512).astype(np.float32) * 0.1
visualizer.update_audio_data(audio_chunk)

# Show visualizer
visualizer.show()
```

## Integration with Main Window

```python
from PyQt6.QtWidgets import QMainWindow, QStackedWidget
from ui.realtime_record import RealtimeRecordWidget

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        # Create stacked widget for pages
        self.stacked_widget = QStackedWidget()

        # Create realtime record widget
        self.realtime_widget = RealtimeRecordWidget(
            recorder=self.recorder,
            audio_capture=self.audio_capture,
            i18n_manager=self.i18n
        )

        # Add to stacked widget
        self.stacked_widget.addWidget(self.realtime_widget)

        self.setCentralWidget(self.stacked_widget)
```

## Signal-Slot Architecture

The widget uses Qt Signals for thread-safe communication between the recorder (which runs in worker threads) and the UI (which runs in the main thread).

### Signals

- `transcription_updated(str)`: Emitted when new transcription text is available
- `translation_updated(str)`: Emitted when new translation text is available
- `error_occurred(str)`: Emitted when an error occurs
- `status_changed(bool, float)`: Emitted when recording status changes
- `audio_data_available(object)`: Emitted when audio data is available for visualization

### Callbacks

The recorder uses callbacks to notify the UI:

```python
recorder.set_callbacks(
    on_transcription=lambda text: signals.transcription_updated.emit(text),
    on_translation=lambda text: signals.translation_updated.emit(text),
    on_error=lambda error: signals.error_occurred.emit(error),
    on_audio_data=lambda audio: signals.audio_data_available.emit(audio)
)
```

**Available Callbacks:**

- `on_transcription`: Called when new transcription text is available
- `on_translation`: Called when new translation text is available
- `on_error`: Called when an error occurs
- `on_audio_data`: Called with raw audio data for visualization or processing

## Async/Await Support

The widget handles async operations using `asyncio.create_task()`:

```python
def _toggle_recording(self):
    if not self.recorder.is_recording:
        asyncio.create_task(self._start_recording())
    else:
        asyncio.create_task(self._stop_recording())
```

## Internationalization

The widget supports multiple languages through the i18n system:

```python
# Change language
i18n.change_language('en_US')  # English
i18n.change_language('zh_CN')  # Chinese
i18n.change_language('fr_FR')  # French
```

Translation keys used:

- `realtime_record.title`
- `realtime_record.audio_input`
- `realtime_record.gain`
- `realtime_record.source_language`
- `realtime_record.target_language`
- `realtime_record.enable_translation`
- `realtime_record.start_recording`
- `realtime_record.stop_recording`
- `realtime_record.recording_duration`
- `realtime_record.transcription_text`
- `realtime_record.translation_text`
- `realtime_record.export_transcription`
- `realtime_record.export_translation`
- `realtime_record.save_recording`

## File Export

The widget provides export functionality for:

1. **Transcription text**: Export to .txt or .md files
2. **Translation text**: Export to .txt or .md files
3. **Recording audio**: Automatically saved on stop (configured in options)

## Automatic Calendar Event Creation

When recording stops, the widget automatically creates a calendar event with:

- Title: "录音会话 - [timestamp]"
- Type: Event
- Start/End time: Recording session duration
- Attachments: Links to recording and transcript files

## Error Handling

Errors are handled gracefully and displayed to the user:

```python
try:
    await self.recorder.start_recording(...)
except Exception as e:
    logger.error(f"Failed to start recording: {e}")
    self._show_error(f"Failed to start recording: {e}")
```

## Performance

- Audio visualization runs at 30 FPS
- Status updates every 100ms
- Audio processing in separate threads
- Non-blocking UI operations
