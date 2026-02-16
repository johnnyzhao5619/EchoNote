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
- Marker capture button with timestamp list
- Respects global realtime preferences (`realtime.recording_format` /
  `realtime.auto_save`) provided by `SettingsManager`

**Usage:**

```python
from PySide6.QtWidgets import QApplication
from ui.realtime_record import RealtimeRecordWidget
from config.app_config import ConfigManager
from core.settings.manager import SettingsManager
from core.realtime.recorder import RealtimeRecorder
from engines.audio.capture import AudioCapture
from engines.speech.faster_whisper_engine import FasterWhisperEngine
from data.database.connection import DatabaseConnection
from data.storage.file_manager import FileManager
from utils.i18n import I18nQtManager
from utils.app_initializer import initialize_translation_engine, TranslationEngineProxy
from data.security.secrets_manager import SecretsManager

# Initialize dependencies
config_manager = ConfigManager()
audio_capture = AudioCapture()
speech_engine = FasterWhisperEngine(model_size='base')
secrets_manager = SecretsManager(config_manager)
translation_loader = initialize_translation_engine(config_manager, secrets_manager)
translation_engine = TranslationEngineProxy(translation_loader)
db = DatabaseConnection('~/.echonote/data.db')
file_manager = FileManager('~/.echonote')
i18n = I18nQtManager()
settings_manager = SettingsManager(config_manager)

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
    i18n_manager=i18n,
    settings_manager=settings_manager
)

# Show widget
widget.show()
```

> **重要提示**：要启用翻译功能，请在 Secrets 管理中配置有效的 Google API Key。应用会通过 `initialize_translation_engine(...)` 延迟加载翻译引擎；若密钥缺失，`translation_engine` 会在运行时表现为不可用，界面会自动禁用翻译相关功能。

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
from PySide6.QtWidgets import QMainWindow, QStackedWidget
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
            i18n_manager=self.i18n,
            settings_manager=self.settings_manager
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
- `marker_added(object)`: Emitted when a new marker is created

### Callbacks

The recorder uses callbacks to notify the UI:

```python
recorder.set_callbacks(
    on_transcription=lambda text: signals.transcription_updated.emit(text),
    on_translation=lambda text: signals.translation_updated.emit(text),
    on_error=lambda error: signals.error_occurred.emit(error),
    on_audio_data=lambda audio: signals.audio_data_available.emit(audio),
    on_marker=lambda marker: signals.marker_added.emit(marker)
)
```

**Available Callbacks:**

- `on_transcription`: Called when new transcription text is available
- `on_translation`: Called when new translation text is available
- `on_error`: Called when an error occurs
- `on_audio_data`: Called with raw audio data for visualization or processing
- `on_marker`: Called when a new marker is recorded (dict with index/offset/label)

## Async/Await Support

The widget dispatches coroutines to a dedicated asyncio event loop thread managed by `AsyncWorker`. 录制开关示例：

```python
def _toggle_recording(self):
    if not self.recorder.is_recording:
        request = self._prepare_start_request()  # collect UI state on main thread
        self._submit_worker_task(self._start_recording(request))
    else:
        self._submit_worker_task(self._stop_recording())
```

`_submit_worker_task` 会将协程提交到 `AsyncWorker` 的事件循环并跟踪返回的 `Future`，便于在清理阶段安全取消或等待任务完成。这一封装确保 UI 线程保持响应，并集中管理错误处理与状态反馈。

### 专用事件循环线程的生命周期

- **初始化**：`AsyncWorker` 在后台线程中构建事件循环，调用 `asyncio.new_event_loop()` 与 `loop.run_forever()`，并在启动后通知循环就绪。
- **调度执行**：`_submit_worker_task` 使用 `asyncio.run_coroutine_threadsafe` 将协程投递到该循环，并统一跟踪任务完成状态与异常日志。
- **资源回收**：`_cleanup_resources` 采用幂等清理流程，先在 worker 循环中优雅停录，再取消残留 `Future` 并停止线程，避免悬挂任务或线程泄漏。

## Internationalization

The widget supports multiple languages through the i18n system:

```python
# Change language
i18n.change_language('en_US')  # English
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
- `realtime_record.add_marker`
- `realtime_record.markers`
- `realtime_record.markers_placeholder`
- `realtime_record.marker_unavailable`
- `realtime_record.marker_failed`
- `realtime_record.marker_item`
- `realtime_record.marker_item_with_label`

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
