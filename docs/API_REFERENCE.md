# EchoNote API Reference

**Version**: 1.0.0  
**Last Updated**: October 2025

---

## Table of Contents

1. [Core Managers](#core-managers)
2. [Speech Engines](#speech-engines)
3. [Translation Engines](#translation-engines)
4. [Calendar System](#calendar-system)
5. [Database Models](#database-models)
6. [Utilities](#utilities)

---

## Core Managers

### TranscriptionManager

**Location**: `core/transcription/manager.py`

Manages batch transcription tasks with queue orchestration, export handling, and progress callbacks.

#### Constructor

```python
TranscriptionManager(db_connection, speech_engine, config)
```

**Parameters:**

- `db_connection` (DatabaseConnection): Database connection instance
- `speech_engine` (SpeechEngine): Speech recognition engine
- `config` (dict): Namespaced configuration for transcription behaviour

#### Methods

##### add_task

```python
def add_task(file_path: str, options: dict | None = None) -> str
```

Register a single file for transcription. The task record is persisted immediately and queued when processing is running.

**Parameters:**

- `file_path` (str): Path to audio/video file
- `options` (dict, optional): Overrides such as `language`, `output_format`, and `output_path`

**Returns:**

- `str`: Task ID (UUID)

**Raises:**

- `FileNotFoundError`: File missing
- `ValueError`: Unsupported extension

##### add_tasks_from_folder

```python
def add_tasks_from_folder(folder_path: str, options: dict | None = None) -> list[str]
```

Recursively discover supported media files in a folder and enqueue each one.

##### start_processing / stop_processing

```python
def start_processing() -> None
def stop_processing() -> None
```

Spin up (or tear down) the background worker loop that drains the task queue.

##### pause_processing / resume_processing

```python
def pause_processing() -> None
def resume_processing() -> None
```

Temporarily suspend queue intake without dropping tasks. `is_paused()` reports the current state.

##### get_task_status

```python
def get_task_status(task_id: str) -> dict | None
```

Fetch the latest status row from the database for UI updates.

##### cancel_task / retry_task / delete_task

```python
def cancel_task(task_id: str) -> bool
def retry_task(task_id: str) -> bool
def delete_task(task_id: str) -> bool
```

Cancel pending work, clone a failed task for another attempt, or remove a completed record.

##### export_result

```python
def export_result(task_id: str, output_dir: str | None = None, fmt: str | None = None) -> dict
```

Convert the internal transcript into the requested format (`txt`, `srt`, or `md`) and return filesystem paths.

##### register_progress_callback / unregister_progress_callback

```python
def register_progress_callback(task_id: str, callback: Callable[[float, str], None]) -> None
def unregister_progress_callback(task_id: str) -> None
```

Subscribe UI handlers to receive granular progress updates as the speech engine reports them.

### RealtimeRecorder

**Location**: `core/realtime/recorder.py`

Manages real-time audio recording, transcription, and translation.

#### Constructor

```python
RealtimeRecorder(audio_capture, speech_engine, translation_engine, db_connection, file_manager)
```

**Parameters:**

- `audio_capture` (Optional[AudioCapture]): Audio capture instance. Pass `None`
  when PyAudio is unavailable; real-time recording UI will remain disabled but
  the rest of the application continues to work.
- `speech_engine` (SpeechEngine): Speech recognition engine
- `translation_engine` (TranslationEngine, optional): Translation engine
- `db_connection` (DatabaseConnection): Database connection
- `file_manager` (FileManager): File manager instance

#### Methods

##### start_recording

```python
async def start_recording(
    input_source: Optional[int] = None,
    options: dict | None = None,
    event_loop: asyncio.AbstractEventLoop | None = None,
)
```

Start real-time recording, streaming transcription, and optional translation.

**Parameters:**

- `input_source` (Optional[int]) – Audio device index passed to `AudioCapture`. Use
  `None` to rely on the default device configured by the capture backend.
- `options` (dict, optional) – Recording options:
  - `language` (str): Source language code used for transcription.
  - `enable_translation` (bool): Enable translation dispatch.
  - `target_language` (str): Target language for translation jobs.
  - `recording_format` (str): `'wav'` or `'mp3'` export format. MP3 output
    requires a reachable FFmpeg binary; without it the recorder falls back to
    WAV and reports a warning through the `on_error` callback. When this option
    is omitted, `SettingsManager.get_realtime_preferences()` supplies the
    default chosen in the settings UI.
  - `sample_rate` (int): Override microphone sample rate before capture.
  - `save_recording` (bool): Persist raw audio to disk. Defaults to the
    realtime auto-save toggle exposed in the settings UI.
  - `save_transcript` (bool): Persist aggregated transcript text (default `True`).
  - `create_calendar_event` (bool): Create a calendar event with attachments (default `True`).
    Requires a configured database connection; when the database is unavailable the
    recorder automatically skips this step.
- `event_loop` (asyncio.AbstractEventLoop, optional) – Explicit loop reference used
  when bridging from GUI threads (e.g., Qt) into the recorder coroutine.

**Example:**

```python
await recorder.start_recording(
    input_source=0,
    options={
        "language": "zh",
        "enable_translation": True,
        "target_language": "en",
        "recording_format": "wav",
        "sample_rate": 48000,
        "save_transcript": True,
        "create_calendar_event": False,
    },
)
```

##### stop_recording

```python
async def stop_recording() -> dict
```

Stop recording and save files.

**Returns:**

- `dict`: Recording result
  - `duration` (float): Total recording time in seconds.
  - `start_time` (str): ISO 8601 timestamp when capture began.
  - `end_time` (str): ISO 8601 timestamp when capture finished.
  - `recording_path` (str, optional): Saved recording path when `save_recording`
    is enabled and audio data exists.
  - `transcript_path` (str, optional): Transcript file path when
    `save_transcript` is enabled and transcription text was produced.
  - `translation_path` (str, optional): Translation file path when
    `enable_translation` is true and translated text exists.
  - `markers` (list[dict], optional): In-memory markers captured during the
    session. Present only when at least one marker was recorded.
  - `markers_path` (str, optional): JSON export of markers when markers exist and
    saving succeeds.
- `event_id` (str, optional): Created calendar event ID when
    `create_calendar_event` succeeds. Absent when no database connection is configured.

**Note:** When multiple recordings finish within the same second, EchoNote automatically appends a counter or millisecond suffix to every exported filename (audio, transcript, translation, and markers) to avoid collisions.

##### get_transcription_stream

```python
def get_transcription_stream() -> AsyncIterator[str]
```

Get real-time transcription text stream.

**Returns:**

- `AsyncIterator[str]`: Stream of transcription text. The iterator produces
  each new transcription segment as soon as it becomes available and stops
  automatically after `stop_recording()` is awaited.

**Note:**

- For Qt/UI integrations prefer `set_callbacks()` so updates can be delivered
  via signals.
- 该生成器主要用于需要纯异步文本流的服务或后端任务。

**Example:**

```python
async def consume_transcription(recorder):
    async for text in recorder.get_transcription_stream():
        if text:
            print(f"Transcription: {text}")

await recorder.start_recording(options={"save_recording": False})

consumer = asyncio.create_task(consume_transcription(recorder))

# ... feed audio or wait for callbacks ...

await recorder.stop_recording()
await consumer
```

##### get_translation_stream

```python
def get_translation_stream() -> AsyncIterator[str]
```

Get real-time translation text stream.

**Returns:**

- `AsyncIterator[str]`: Stream of translation text. Requires
  `enable_translation=True` when starting the recorder.

**Note:**

- 同样推荐使用 `set_callbacks()` 让 UI 订阅翻译结果；生成器更适合后端任务或测试。

**Example:**

```python
async def consume_translation(recorder):
    async for text in recorder.get_translation_stream():
        print(f"Translation: {text}")

await recorder.start_recording(options={
    "enable_translation": True,
    "save_recording": False,
    "save_transcript": False,
})

translation_task = asyncio.create_task(consume_translation(recorder))

# ... feed audio or wait for callbacks ...

await recorder.stop_recording()
await translation_task
```

---

### CalendarManager

**Location**: `core/calendar/manager.py`

Handles local calendar CRUD and coordinates optional sync adapters (Google, Outlook, etc.).

#### Constructor

```python
CalendarManager(db_connection, sync_adapters: dict | None = None)
```

**Parameters:**

- `db_connection` (DatabaseConnection): Database connection
- `sync_adapters` (dict, optional): Mapping of provider name → sync adapter implementing push/pull operations

#### Methods

##### create_event

```python
def create_event(event_data: dict, sync_to: list[str] | None = None) -> str
```

Create and persist a local event, optionally pushing to configured providers. Returns the new event ID.

##### update_event

```python
def update_event(event_id: str, event_data: dict) -> None
```

Modify mutable fields on a local event. Readonly (synced) events raise an error.

##### delete_event

```python
def delete_event(event_id: str) -> None
```

Remove a local event. Readonly events cannot be deleted.

##### get_event

```python
def get_event(event_id: str) -> CalendarEvent | None
```

Retrieve a single event by ID.

##### get_events

```python
def get_events(
    start_date: str,
    end_date: str,
    filters: dict | None = None
) -> list[CalendarEvent]
```

List events in a time window with optional filters (`source`, `event_type`, text search).

##### sync_external_calendar

```python
def sync_external_calendar(provider: str) -> None
```

Delegate a pull operation to the registered adapter and persist results locally.

### TimelineManager

**Location**: `core/timeline/manager.py`

Provides timeline data, auto-task configuration, and artifact lookups for past recordings.

#### Constructor

```python
TimelineManager(calendar_manager, db_connection)
```

#### Methods

##### get_timeline_events

```python
def get_timeline_events(
    center_time: datetime,
    past_days: int,
    future_days: int,
    page: int = 0,
    page_size: int = 50
) -> dict
```

Return paginated past/future events surrounding the supplied timestamp. Past entries include attachments; future entries include auto-task defaults.

##### set_auto_task / get_auto_task

```python
def set_auto_task(event_id: str, task_config: dict) -> None
def get_auto_task(event_id: str) -> dict | None
```

Persist user preferences for auto-recording/transcription and retrieve them when rendering the timeline.

##### search_events

```python
def search_events(query: str, filters: dict | None = None) -> list[dict]
```

Search titles, descriptions, attendee lists, and transcript contents for the supplied keyword. Optional filters include `start_date`, `end_date`, `attendees`, `event_type`, and `source`.

##### get_event_artifacts

```python
def get_event_artifacts(event_id: str) -> dict
```

Collect recordings and transcript attachments related to a specific event.

### SettingsManager

**Location**: `core/settings/manager.py`

Manages application settings.

#### Constructor

```python
SettingsManager(config_manager)
```

#### Methods

##### get

```python
def get(key: str, default=None)
```

Get a setting value.

##### set

```python
def set(key: str, value)
```

Set a setting value.

##### save

```python
def save()
```

Save settings to disk.

##### validate

```python
def validate(key: str, value) -> bool
```

Validate a setting value.

---

## Speech Engines

### SpeechEngine (Base Class)

**Location**: `engines/speech/base.py`

Abstract base class for all speech recognition engines.

#### Methods

##### get_name

```python
@abstractmethod
def get_name(self) -> str
```

Get engine name.

##### get_supported_languages

```python
@abstractmethod
def get_supported_languages(self) -> list
```

Get list of supported language codes.

##### transcribe_file

```python
@abstractmethod
async def transcribe_file(audio_path: str, language: str = None) -> dict
```

Transcribe an audio file.

**Parameters:**

- `audio_path` (str): Path to audio file
- `language` (str, optional): Language code

**Returns:**

- `dict`: Transcription result
  - `segments` (list): List of segments
    - `start` (float): Start time in seconds
    - `end` (float): End time in seconds
    - `text` (str): Transcribed text
  - `language` (str): Detected/used language

##### transcribe_stream

```python
@abstractmethod
async def transcribe_stream(
    audio_chunk: np.ndarray,
    language: str = None,
    *,
    sample_rate: int | None = None,
    **kwargs,
) -> str
```

Transcribe audio stream chunk.

**Parameters:**

- `audio_chunk` (np.ndarray): Audio data (mono)
- `language` (str, optional): Language code
- `sample_rate` (int, optional): Actual sampling rate passed through to engines

**Returns:**

- `str`: Transcribed text

##### get_config_schema

```python
@abstractmethod
def get_config_schema(self) -> dict
```

Get configuration schema (JSON Schema format).

---

### FasterWhisperEngine

**Location**: `engines/speech/faster_whisper_engine.py`

Local speech recognition using faster-whisper.

#### Constructor

```python
FasterWhisperEngine(
    model_size: str = "base",
    device: str = "auto",
    compute_type: str = "int8",
    model_manager = None
)
```

**Parameters:**

- `model_size` (str): Model size ('tiny', 'base', 'small', 'medium', 'large')
- `device` (str): Device ('cpu', 'cuda', 'auto')
- `compute_type` (str): Compute type ('int8', 'float16', 'float32')
- `model_manager` (ModelManager, optional): Model manager instance

#### Additional Methods

##### is_model_available

```python
def is_model_available(self) -> bool
```

Check if model is downloaded and available.

##### get_model_info

```python
def get_model_info(self) -> dict
```

Get model information.

**Returns:**

- `dict`: Model info
  - `size` (str): Model size
  - `device` (str): Device
  - `compute_type` (str): Compute type
  - `available` (bool): Whether model is available

---

### OpenAIEngine

**Location**: `engines/speech/openai_engine.py`

OpenAI Whisper API integration.

#### Constructor

```python
OpenAIEngine(api_key: str)
```

**Parameters:**

- `api_key` (str): OpenAI API key

---

## Translation Engines

### TranslationEngine (Base Class)

**Location**: `engines/translation/base.py`

Abstract base class for translation engines.

#### Methods

##### translate

```python
@abstractmethod
async def translate(text: str, source_lang: str, target_lang: str) -> str
```

Translate text.

**Parameters:**

- `text` (str): Text to translate
- `source_lang` (str): Source language code
- `target_lang` (str): Target language code

**Returns:**

- `str`: Translated text

##### get_supported_languages

```python
@abstractmethod
def get_supported_languages(self) -> list
```

Get supported language codes.

---

### GoogleTranslateEngine

**Location**: `engines/translation/google_translate.py`

Google Cloud Translation API integration.

#### Constructor

```python
GoogleTranslateEngine(api_key: str)
```

---

## Calendar System

### CalendarSyncAdapter (Base Class)

**Location**: `engines/calendar_sync/base.py`

Abstract base class for calendar sync adapters.

#### Methods

##### authenticate

```python
@abstractmethod
def authenticate(credentials: dict) -> dict
```

Perform OAuth authentication and return token payloads.

##### fetch_events

```python
@abstractmethod
def fetch_events(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    last_sync_token: Optional[str] = None,
) -> dict
```

Fetch events from the external calendar provider. Implementations may support incremental sync via `last_sync_token`.

##### push_event

```python
@abstractmethod
def push_event(event: CalendarEvent) -> str
```

Create a new event remotely and return the provider specific identifier.

##### update_event

```python
@abstractmethod
def update_event(event: CalendarEvent, external_id: str) -> None
```

Persist local changes to an already linked remote event.

##### delete_event

```python
@abstractmethod
def delete_event(event: CalendarEvent, external_id: str) -> None
```

Remove the remote counterpart for a local event.

##### revoke_access

```python
@abstractmethod
def revoke_access() -> None
```

Revoke OAuth access and clean up provider tokens.

---

## Database Models

### TranscriptionTask

**Location**: `data/database/models.py`

Represents a batch transcription task.

#### Attributes

- `id` (str): Task ID (UUID)
- `file_path` (str): Audio file path
- `file_name` (str): File name
- `file_size` (int): File size in bytes
- `audio_duration` (float): Duration in seconds
- `status` (str): 'pending', 'processing', 'completed', 'failed'
- `progress` (float): Progress (0-100)
- `language` (str): Language code
- `engine` (str): Engine name
- `output_format` (str): Output format
- `output_path` (str): Output file path
- `error_message` (str): Error message if failed
- `created_at` (datetime): Creation time
- `started_at` (datetime): Start time
- `completed_at` (datetime): Completion time

#### Methods

##### save

```python
def save(db_connection)
```

Save to database.

##### delete

```python
def delete(db_connection)
```

Delete from database.

##### from_db_row

```python
@classmethod
def from_db_row(cls, row: dict) -> TranscriptionTask
```

Create instance from database row.

---

### CalendarEvent

**Location**: `data/database/models.py`

Represents a calendar event.

#### Attributes

- `id` (str): Event ID (UUID)
- `title` (str): Event title
- `event_type` (str): 'Event', 'Task', 'Appointment'
- `start_time` (datetime): Start time
- `end_time` (datetime): End time
- `location` (str): Location
- `attendees` (list): List of attendee emails
- `description` (str): Description
- `reminder_minutes` (int): Reminder time
- `recurrence_rule` (str): iCalendar RRULE
- `source` (str): 'local', 'google', 'outlook'
- `external_id` (str): **Deprecated** legacy column retained for backward compatibility.
- Provider-specific identifiers are stored in `calendar_event_links` (see below).
- `is_readonly` (bool): Whether event is read-only
- `created_at` (datetime): Creation time
- `updated_at` (datetime): Last update time

---

### CalendarEventLink

**Location**: `data/database/models.py`

Represents the mapping between a local calendar event and an external provider.

#### Attributes

- `event_id` (str): Linked calendar event ID
- `provider` (str): Provider key (e.g., 'google', 'outlook', 'default')
- `external_id` (str): Provider-specific identifier
- `last_synced_at` (datetime): Timestamp of the latest successful sync for this mapping

#### Methods

- `save(db_connection)`: Create or update the link record.
- `get_by_provider_and_external_id(db_connection, provider, external_id) -> CalendarEventLink | None`
- `get_by_event_and_provider(db_connection, event_id, provider) -> CalendarEventLink | None`
- `list_for_event(db_connection, event_id) -> list[CalendarEventLink]`

---

## Utilities

### I18nQtManager

**Location**: `utils/i18n.py`

Internationalization manager for Qt applications.

#### Constructor

```python
I18nQtManager(default_language: str = "en_US")
```

#### Methods

##### t

```python
def t(key: str, **kwargs) -> str
```

Translate a key.

**Parameters:**

- `key` (str): Translation key (dot notation)
- `**kwargs`: Variables for interpolation

**Returns:**

- `str`: Translated text

**Example:**

```python
text = i18n.t("notification.low_memory.message", memory="500MB")
```

##### set_language

```python
def set_language(language: str)
```

Change current language.

---

### SecurityManager

**Location**: `data/security/encryption.py`

Manages encryption and security.

#### Methods

##### encrypt

```python
def encrypt(data: str) -> str
```

Encrypt data.

##### decrypt

```python
def decrypt(encrypted_data: str) -> str
```

Decrypt data.

---

### FileManager

**Location**: `data/storage/file_manager.py`

Manages file operations.

#### Methods

##### save_file

```python
def save_file(data: bytes, filename: str, subdirectory: str = None) -> str
```

Save file to storage.

**Returns:**

- `str`: File path

##### delete_file

```python
def delete_file(file_path: str)
```

Delete file.

##### get_file_path

```python
def get_file_path(filename: str, subdirectory: str = None) -> str
```

Get full file path.

---

## Error Handling

### ErrorHandler

**Location**: `utils/error_handler.py`

Centralized error handling.

#### Methods

##### handle_error

```python
@staticmethod
def handle_error(exception: Exception) -> dict
```

Handle an exception and return error info.

**Returns:**

- `dict`: Error information
  - `user_message` (str): User-friendly message
  - `technical_details` (str): Technical details
  - `suggestions` (list): Suggested actions

---

## Signals and Events

### Qt Signals

EchoNote uses Qt signals for event communication:

#### TranscriptionManager Signals

- `task_added(task_id: str)`: Task added to queue
- `task_started(task_id: str)`: Task processing started
- `task_progress(task_id: str, progress: float)`: Progress updated
- `task_completed(task_id: str)`: Task completed
- `task_failed(task_id: str, error: str)`: Task failed

#### RealtimeRecorder Signals

- `recording_started()`: Recording started
- `recording_stopped()`: Recording stopped
- `transcription_updated(text: str)`: New transcription text
- `translation_updated(text: str)`: New translation text

#### ResourceMonitor Signals

- `low_memory_warning(available_mb: float)`: Low memory detected
- `high_cpu_warning(usage_percent: float)`: High CPU usage
- `resources_recovered()`: Resources recovered

---

## Configuration

### Configuration Keys

Configuration is stored in JSON format. Key paths use dot notation.

#### Transcription

- `transcription.default_engine`: Default speech engine
- `transcription.default_output_format`: Default output format
- `transcription.max_concurrent_tasks`: Max concurrent tasks
- `transcription.faster_whisper.model_size`: Model size
- `transcription.faster_whisper.device`: Device
- `transcription.faster_whisper.compute_type`: Compute type

#### Real-time

- `realtime.default_input_source`: Default audio input
- `realtime.recording_format`: Recording format
- `realtime.vad_threshold`: VAD threshold
- `realtime.silence_duration_ms`: Silence duration

#### Calendar

- `calendar.default_view`: Default view ('month', 'week', 'day')
- `calendar.sync_interval_minutes`: Sync interval
- `calendar.colors.local`: Local event color
- `calendar.colors.google`: Google event color
- `calendar.colors.outlook`: Outlook event color

#### Timeline

- `timeline.past_days`: Days to show in past
- `timeline.future_days`: Days to show in future
- `timeline.reminder_minutes`: Reminder time
- `timeline.page_size`: Events per page

#### UI

- `ui.theme`: Theme ('light', 'dark', 'system')
- `ui.language`: Language ('zh_CN', 'en_US', 'fr_FR')

---

## Examples

### Complete Transcription Workflow

```python
from core.transcription.manager import TranscriptionManager
from engines.speech.faster_whisper_engine import FasterWhisperEngine
from data.database.connection import DatabaseConnection
from config.app_config import ConfigManager

# Initialize
config = ConfigManager()
db = DatabaseConnection("~/.echonote/data.db")
engine = FasterWhisperEngine(model_size="base")
manager = TranscriptionManager(db, engine, config)

# Add task
task_id = await manager.add_task(
    file_path="/path/to/audio.mp3",
    options={"language": "zh", "output_format": "txt"}
)

# Start processing
await manager.start_processing()

# Monitor progress
while True:
    status = manager.get_task_status(task_id)
    print(f"Progress: {status['progress']}%")

    if status['status'] in ['completed', 'failed']:
        break

    await asyncio.sleep(1)

# Get result
if status['status'] == 'completed':
    print(f"Output: {status['output_path']}")
```

### Real-time Recording with Translation

```python
from core.realtime.recorder import RealtimeRecorder
from engines.audio.capture import AudioCapture
from engines.speech.faster_whisper_engine import FasterWhisperEngine
from engines.translation.google_translate import GoogleTranslateEngine

# Initialize
try:
    audio_capture = AudioCapture()
except ImportError:
    audio_capture = None  # PyAudio missing; realtime recording will be disabled
speech_engine = FasterWhisperEngine()
translation_engine = GoogleTranslateEngine(api_key="your-key")
recorder = RealtimeRecorder(
    audio_capture, speech_engine, translation_engine, db, file_manager
)

# Start recording
await recorder.start_recording(
    input_source=0,
    options={
        "language": "zh",
        "enable_translation": True,
        "target_language": "en",
        "recording_format": "wav",
        "save_recording": True,
    },
)

# Get streams
async def display_transcription():
    async for text in recorder.get_transcription_stream():
        print(f"Transcription: {text}")

async def display_translation():
    async for text in recorder.get_translation_stream():
        print(f"Translation: {text}")

# Run both streams concurrently
await asyncio.gather(
    display_transcription(),
    display_translation()
)

# Stop recording
result = await recorder.stop_recording()
print(
    "Duration:", result["duration"],
    "Recording:", result.get("recording_path", ""),
    "Markers:", len(result.get("markers", [])),
)
```

---

**For more examples, see the [Developer Guide](DEVELOPER_GUIDE.md).**

---

**Last Updated**: October 2025  
**Version**: 1.0.0
