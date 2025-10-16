# EchoNote Developer Guide

**Version**: 1.0.0  
**Last Updated**: October 2025

---

## Table of Contents

1. [Introduction](#introduction)
2. [Architecture Overview](#architecture-overview)
3. [Development Environment Setup](#development-environment-setup)
4. [Project Structure](#project-structure)
5. [Core Components](#core-components)
6. [API Reference](#api-reference)
7. [Contributing Guidelines](#contributing-guidelines)
8. [Code Standards](#code-standards)
9. [Testing](#testing)
10. [Build and Deployment](#build-and-deployment)

---

## Introduction

Welcome to the EchoNote developer documentation! This guide provides comprehensive information for developers who want to contribute to, extend, or understand the EchoNote codebase.

### What is EchoNote?

EchoNote is a cross-platform desktop application for intelligent voice transcription, translation, and calendar management. Built with Python and PyQt6, it follows a local-first philosophy while offering optional cloud service integration.

### Key Technologies

- **UI Framework**: PyQt6
- **Speech Recognition**: faster-whisper (default), OpenAI/Google/Azure (optional)
- **Database**: SQLite with application-level encryption
- **Audio Processing**: PyAudio, soundfile, librosa
- **HTTP Client**: httpx
- **Task Scheduling**: APScheduler

### Design Philosophy

1. **Local-First**: Core functionality works offline
2. **Modular Architecture**: Clear separation of concerns
3. **Pluggable Engines**: Easy to add new speech/translation engines
4. **Security**: Encrypted storage for sensitive data
5. **Performance**: Optimized for resource efficiency

---

## Architecture Overview

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         UI Layer (PyQt6)                    │
│  ┌──────────┬──────────┬──────────┬──────────┬──────────┐   │
│  │ Sidebar  │  Batch   │ Realtime │ Calendar │ Timeline │   │
│  │          │Transcribe│  Record  │   Hub    │   View   │   │
│  └──────────┴──────────┴──────────┴──────────┴──────────┘   │
└─────────────────────────────────────────────────────────────┘


                              │

┌─────────────────────────────────────────────────────────────┐
│ Core Business Logic                                         │
│ ┌──────────────┬──────────────┬──────────┬───────────────┐  │
│ │ Transcription│ Calendar     │ Timeline │ Setting       │  │
│ │ Manager      │ Manager      │ Manager  │ Manager       │  │
│ └──────────────┴──────────────┴──────────┴───────────────┘  │
└─────────────────────────────────────────────────────────────┘
│
┌─────────────────────────────────────────────────────────────┐
│ Engine Layer                                                │
│ ┌──────────────┬──────────────┬──────────┬───────────────┐  │
│ │ Speech       │ Translation  │ Audio    │ Calendar      │  │
│ │ Engines      │ Engines      │ Capture  │ Sync          │  │
│ └──────────────┴──────────────┴──────────┴───────────────┘  │
└─────────────────────────────────────────────────────────────┘
│
┌─────────────────────────────────────────────────────────────┐
│ Data Layer                                                  │
│ ┌──────────────┬──────────────┬──────────┬───────────────┐  │
│ │ Database     │ File System  │ Config   │ Security      │  │
│ │ (SQLite)     │ Storage      │ Manager  │ Manager       │  │
│ └──────────────┴──────────────┴──────────┴───────────────┘  │
└─────────────────────────────────────────────────────────────┘

````

### Layer Responsibilities

#### UI Layer (`ui/`)
- PyQt6-based user interface components
- Event handling and user interactions
- Theme and language switching
- No direct database access (uses managers)

#### Core Layer (`core/`)
- Business logic independent of UI
- Manager classes for each feature domain
- Task queue and scheduling
- Coordinates between UI and engines

#### Engine Layer (`engines/`)
- Pluggable speech recognition implementations
- Translation service adapters
- Audio capture and processing
- Calendar sync adapters

#### Data Layer (`data/`)
- Database connection and ORM models
- File system operations
- Configuration management
- Security and encryption

---

## Development Environment Setup

### Prerequisites

- **Python**: 3.8 or higher
- **pip**: Latest version
- **Git**: For version control
- **FFmpeg**: For audio/video processing (optional but recommended)

### Platform-Specific Requirements

#### macOS
```bash
# Install Homebrew (if not installed)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install Python
brew install python@3.11

# Install FFmpeg
brew install ffmpeg

# Install PortAudio (for PyAudio)
brew install portaudio
````

#### Windows

```bash
# Install Python from python.org
# Download and install FFmpeg from ffmpeg.org

# Install Visual C++ Build Tools (for some dependencies)
# Download from: https://visualstudio.microsoft.com/visual-cpp-build-tools/
```

#### Linux (Ubuntu/Debian)

```bash
# Install Python and dependencies
sudo apt update
sudo apt install python3.11 python3.11-venv python3-pip

# Install FFmpeg
sudo apt install ffmpeg

# Install PortAudio
sudo apt install portaudio19-dev

# Install Qt dependencies
sudo apt install libxcb-xinerama0
```

### Setting Up the Development Environment

1. **Clone the Repository**

```bash
git clone https://github.com/johnnyzhao5619/echonote.git
cd echonote
```

2. **Create Virtual Environment**

```bash
python -m venv venv

# Activate on macOS/Linux
source venv/bin/activate

# Activate on Windows
venv\Scripts\activate
```

3. **Install Dependencies**

```bash
# Install production dependencies
pip install -r requirements.txt

# Install development dependencies
pip install -r requirements-dev.txt
```

4. **Configure the Application**

```bash
# Copy default configuration
cp config/default_config.json ~/.echonote/config.json

# Edit configuration as needed
# (API keys, paths, etc.)
```

5. **Run the Application**

```bash
python main.py
```

### IDE Setup

#### VS Code (Recommended)

```json
// .vscode/settings.json
{
  "python.defaultInterpreterPath": "${workspaceFolder}/venv/bin/python",
  "python.linting.enabled": true,
  "python.linting.pylintEnabled": true,
  "python.formatting.provider": "black",
  "editor.formatOnSave": true,
  "python.testing.pytestEnabled": true
}
```

#### PyCharm

1. Open project in PyCharm
2. Configure Python interpreter: Settings → Project → Python Interpreter
3. Select the virtual environment: `<project>/venv`
4. Enable pytest: Settings → Tools → Python Integrated Tools → Testing

---

## Project Structure

### Directory Layout

```
echonote/
├── main.py                          # Application entry point
├── requirements.txt                 # Production dependencies
├── requirements-dev.txt             # Development dependencies
├── config/
│   ├── __init__.py
│   ├── default_config.json         # Default configuration
│   └── app_config.py               # Configuration loader
├── ui/                              # UI Layer
│   ├── __init__.py
│   ├── main_window.py              # Main application window
│   ├── sidebar.py                  # Navigation sidebar
│   ├── batch_transcribe/           # Batch transcription UI
│   ├── realtime_record/            # Real-time recording UI
│   ├── calendar_hub/               # Calendar hub UI
│   ├── timeline/                   # Timeline view UI
│   ├── settings/                   # Settings UI
│   ├── common/                     # Shared UI components
│   └── dialogs/                    # Dialog windows
├── core/                            # Core Business Logic
│   ├── __init__.py
│   ├── transcription/              # Transcription management
│   │   ├── __init__.py
│   │   ├── manager.py
│   │   ├── task_queue.py
│   │   └── format_converter.py
│   ├── realtime/                   # Real-time recording
│   │   ├── __init__.py
│   │   ├── recorder.py
│   │   └── audio_buffer.py
│   ├── calendar/                   # Calendar management
│   │   ├── __init__.py
│   │   ├── manager.py
│   │   └── sync_scheduler.py
│   ├── timeline/                   # Timeline management
│   │   ├── __init__.py
│   │   ├── manager.py
│   │   └── auto_task_scheduler.py
│   ├── settings/                   # Settings management
│   │   ├── __init__.py
│   │   └── manager.py
│   └── models/                     # Model management
│       ├── __init__.py
│       ├── manager.py
│       ├── downloader.py
│       ├── registry.py
│       └── validator.py
```

├── engines/ # Engine Layer
│ ├── **init**.py
│ ├── speech/ # Speech recognition engines
│ │ ├── **init**.py
│ │ ├── base.py # Abstract base class
│ │ ├── faster_whisper_engine.py
│ │ ├── openai_engine.py
│ │ ├── google_engine.py
│ │ ├── azure_engine.py
│ │ ├── usage_tracker.py
│ │ └── api_validator.py
│ ├── translation/ # Translation engines
│ │ ├── **init**.py
│ │ ├── base.py
│ │ └── google_translate.py
│ ├── audio/ # Audio processing
│ │ ├── **init**.py
│ │ ├── capture.py
│ │ └── vad.py
│ └── calendar_sync/ # Calendar sync adapters
│ ├── **init**.py
│ ├── base.py
│ ├── google_calendar.py
│ └── outlook_calendar.py
├── data/ # Data Layer
│ ├── **init**.py
│ ├── database/ # Database operations
│ │ ├── **init**.py
│ │ ├── connection.py
│ │ ├── models.py
│ │ ├── schema.sql
│ │ ├── encryption_helper.py
│ │ └── migrations/
│ ├── storage/ # File system operations
│ │ ├── **init**.py
│ │ └── file_manager.py
│ └── security/ # Security and encryption
│ ├── **init**.py
│ ├── encryption.py
│ ├── oauth_manager.py
│ └── secrets_manager.py
├── utils/ # Utilities
│ ├── **init**.py
│ ├── i18n.py # Internationalization
│ ├── logger.py # Logging
│ ├── validators.py # Input validation
│ ├── error_handler.py # Error handling
│ ├── ffmpeg_checker.py # FFmpeg detection
│ ├── gpu_detector.py # GPU detection
│ ├── resource_monitor.py # Resource monitoring
│ ├── startup_optimizer.py # Startup optimization
│ ├── first_run_setup.py # First run setup
│ ├── http_client.py # HTTP client utilities
│ ├── network_error_handler.py # Network error handling
│ ├── qt_async.py # Qt async utilities
│ ├── user_feedback.py # User feedback
│ └── data_cleanup.py # Data cleanup
├── resources/ # Static Resources
│ ├── icons/
│ ├── themes/
│ │ ├── light.qss
│ │ └── dark.qss
│ └── translations/
│ ├── en_US.json
│ ├── zh_CN.json
│ └── fr_FR.json
├── docs/ # Documentation
│ ├── README.md
│ ├── USER_GUIDE.md
│ ├── QUICK_START.md
│ ├── DEVELOPER_GUIDE.md # This file
│ ├── API_REFERENCE.md
│ ├── CONTRIBUTING.md
│ └── CODE_STANDARDS.md
└── tests/ # Tests
├── **init**.py
├── unit/
├── integration/
└── fixtures/

````

### Key Files

- **`main.py`**: Application entry point, initializes all managers and starts the Qt event loop
- **`config/app_config.py`**: Configuration management system
- **`data/database/models.py`**: ORM models for all database entities
- **`ui/main_window.py`**: Main application window with sidebar navigation
- **`core/*/manager.py`**: Manager classes for each feature domain

---

## Core Components

### 1. Transcription System

#### TranscriptionManager (`core/transcription/manager.py`)

Manages batch transcription tasks with queue management and progress tracking.

**Key Methods:**
```python
async def add_task(file_path: str, options: dict) -> str
async def start_processing()
async def process_task(task_id: str)
def get_task_status(task_id: str) -> dict
def cancel_task(task_id: str)
def pause_processing()
def resume_processing()
````

**Usage Example:**

```python
from core.transcription.manager import TranscriptionManager

# Initialize
manager = TranscriptionManager(db, speech_engine, config)

# Add task
task_id = await manager.add_task(
    file_path="/path/to/audio.mp3",
    options={
        "language": "zh",
        "output_format": "txt"
    }
)

# Start processing
await manager.start_processing()

# Check status
status = manager.get_task_status(task_id)
print(f"Progress: {status['progress']}%")
```

#### TaskQueue (`core/transcription/task_queue.py`)

Asynchronous task queue with concurrency control.

**Features:**

- Concurrent task execution with semaphore
- Priority queue support
- Retry mechanism with exponential backoff
- Progress callbacks

#### FormatConverter (`core/transcription/format_converter.py`)

Converts transcription results to various output formats.

**Supported Formats:**

- **TXT**: Plain text
- **SRT**: SubRip subtitle format
- **MD**: Markdown with timestamps

### 2. Real-time Recording System

#### RealtimeRecorder (`core/realtime/recorder.py`)

Manages real-time audio recording, transcription, and translation.

**Key Methods:**

```python
async def start_recording(input_source: str, options: dict)
async def stop_recording() -> dict
def get_transcription_stream() -> AsyncIterator[str]
def get_translation_stream() -> AsyncIterator[str]
```

**Usage Example:**

```python
from core.realtime.recorder import RealtimeRecorder

# Initialize
recorder = RealtimeRecorder(
    audio_capture=audio_capture,
    speech_engine=speech_engine,
    translation_engine=translation_engine,
    db_connection=db,
    file_manager=file_manager
)

# Start recording
await recorder.start_recording(
    input_source="default",
    options={
        "language": "zh",
        "enable_translation": True,
        "target_language": "en"
    }
)

# Get transcription stream
async for text in recorder.get_transcription_stream():
    print(f"Transcription: {text}")

# Stop recording
result = await recorder.stop_recording()
print(f"Recording saved to: {result['recording_path']}")
```

#### AudioBuffer (`core/realtime/audio_buffer.py`)

Circular buffer for real-time audio data with sliding window support.

**Features:**

- Fixed-size circular buffer
- Sliding window access
- Memory-efficient
- Thread-safe

### 3. Calendar System

#### CalendarManager (`core/calendar/manager.py`)

Manages local and external calendar events.

**Key Methods:**

```python
async def create_event(event_data: dict, sync_to: list = None) -> str
async def update_event(event_id: str, event_data: dict)
async def delete_event(event_id: str)
def get_events(start_date, end_date, filters: dict = None) -> list
async def sync_external_calendar(provider: str)
```

**Usage Example:**

```python
from core.calendar.manager import CalendarManager

# Initialize
manager = CalendarManager(db, sync_adapters)

# Create event
event_id = await manager.create_event(
    event_data={
        "title": "Team Meeting",
        "event_type": "Event",
        "start_time": datetime(2025, 10, 15, 10, 0),
        "end_time": datetime(2025, 10, 15, 11, 0),
        "location": "Conference Room A"
    },
    sync_to=["google"]  # Optional: sync to Google Calendar
)

# Get events
events = manager.get_events(
    start_date=datetime(2025, 10, 1),
    end_date=datetime(2025, 10, 31)
)
```

#### SyncScheduler (`core/calendar/sync_scheduler.py`)

Periodically syncs external calendars in the background.

**Features:**

- Automatic periodic sync (default: 15 minutes)
- Incremental sync using sync tokens
- Error handling and retry logic
- Manual sync trigger

### 4. Timeline System

#### TimelineManager (`core/timeline/manager.py`)

Provides timeline view data with past and future events.

**Key Methods:**

```python
def get_timeline_events(center_time, past_days, future_days, page, page_size) -> dict
async def set_auto_task(event_id: str, task_config: dict)
def search_events(query: str, filters: dict) -> list
def get_event_artifacts(event_id: str) -> dict
```

#### AutoTaskScheduler (`core/timeline/auto_task_scheduler.py`)

Automatically starts recording/transcription for scheduled events.

**Features:**

- Monitors upcoming events
- Sends reminder notifications (5 minutes before)
- Auto-starts configured tasks
- Saves artifacts to event attachments

### 5. Speech Engine System

#### SpeechEngine Base Class (`engines/speech/base.py`)

Abstract base class for all speech recognition engines.

**Interface:**

```python
class SpeechEngine(ABC):
    @abstractmethod
    def get_name(self) -> str:
        """Engine name"""

    @abstractmethod
    def get_supported_languages(self) -> list:
        """Supported language codes"""

    @abstractmethod
    async def transcribe_file(self, audio_path: str, language: str = None) -> dict:
        """Transcribe audio file"""

    @abstractmethod
    async def transcribe_stream(self, audio_chunk: np.ndarray, language: str = None) -> str:
        """Transcribe audio stream"""

    @abstractmethod
    def get_config_schema(self) -> dict:
        """Configuration schema"""
```

#### FasterWhisperEngine (`engines/speech/faster_whisper_engine.py`)

Default local speech recognition engine using faster-whisper.

**Features:**

- Multiple model sizes (tiny, base, small, medium, large)
- GPU acceleration (CUDA, CoreML)
- VAD integration
- Batch and streaming modes

**Usage Example:**

```python
from engines.speech.faster_whisper_engine import FasterWhisperEngine

# Initialize
engine = FasterWhisperEngine(
    model_size="base",
    device="auto",  # auto-detect GPU
    compute_type="int8"
)

# Transcribe file
result = await engine.transcribe_file(
    audio_path="/path/to/audio.mp3",
    language="zh"
)

# Result format
{
    "segments": [
        {"start": 0.0, "end": 2.5, "text": "Hello world"},
        {"start": 2.5, "end": 5.0, "text": "This is a test"}
    ],
    "language": "zh"
}
```

### 6. Database System

#### DatabaseConnection (`data/database/connection.py`)

SQLite database connection with encryption support.

**Features:**

- Connection pooling
- Transaction management
- Application-level encryption for sensitive fields
- Migration system

**Usage Example:**

```python
from data.database.connection import DatabaseConnection

# Initialize with encryption
db = DatabaseConnection(
    db_path="~/.echonote/data.db",
    encryption_key="your-encryption-key"
)

# Execute query
results = db.execute(
    "SELECT * FROM transcription_tasks WHERE status = ?",
    ("completed",)
)

# Transaction
with db.transaction():
    db.execute("INSERT INTO ...", (...))
    db.execute("UPDATE ...", (...))
```

#### ORM Models (`data/database/models.py`)

Object-relational mapping for database entities.

**Key Models:**

- `TranscriptionTask`: Batch transcription tasks
- `CalendarEvent`: Calendar events
- `EventAttachment`: Event attachments (recordings, transcripts)
- `AutoTaskConfig`: Auto-task configurations
- `CalendarSyncStatus`: External calendar sync status
- `APIUsage`: API usage tracking
- `ModelUsageStats`: Model usage statistics

---

## API Reference

For detailed API documentation, see [API_REFERENCE.md](API_REFERENCE.md).

### Quick Reference

#### Manager Classes

| Class                  | Location                        | Purpose             |
| ---------------------- | ------------------------------- | ------------------- |
| `TranscriptionManager` | `core/transcription/manager.py` | Batch transcription |
| `RealtimeRecorder`     | `core/realtime/recorder.py`     | Real-time recording |
| `CalendarManager`      | `core/calendar/manager.py`      | Calendar management |
| `TimelineManager`      | `core/timeline/manager.py`      | Timeline view       |
| `SettingsManager`      | `core/settings/manager.py`      | Settings management |
| `ModelManager`         | `core/models/manager.py`        | Model management    |

#### Engine Classes

| Class                   | Location                                   | Purpose                  |
| ----------------------- | ------------------------------------------ | ------------------------ |
| `FasterWhisperEngine`   | `engines/speech/faster_whisper_engine.py`  | Local speech recognition |
| `OpenAIEngine`          | `engines/speech/openai_engine.py`          | OpenAI Whisper API       |
| `GoogleTranslateEngine` | `engines/translation/google_translate.py`  | Google Translate         |
| `AudioCapture`          | `engines/audio/capture.py`                 | Audio capture            |
| `GoogleCalendarAdapter` | `engines/calendar_sync/google_calendar.py` | Google Calendar sync     |

#### Utility Classes

| Class             | Location                         | Purpose                |
| ----------------- | -------------------------------- | ---------------------- |
| `I18nQtManager`   | `utils/i18n.py`                  | Internationalization   |
| `SecurityManager` | `data/security/encryption.py`    | Encryption             |
| `OAuthManager`    | `data/security/oauth_manager.py` | OAuth token management |
| `FileManager`     | `data/storage/file_manager.py`   | File operations        |
| `ResourceMonitor` | `utils/resource_monitor.py`      | Resource monitoring    |

---

## Contributing Guidelines

For detailed contribution guidelines, see [CONTRIBUTING.md](CONTRIBUTING.md).

### Quick Start for Contributors

1. **Fork the Repository**
2. **Create a Feature Branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```
3. **Make Your Changes**
4. **Write Tests**
5. **Run Tests**
   ```bash
   pytest tests/
   ```
6. **Commit Your Changes**
   ```bash
   git commit -m "Add: your feature description"
   ```
7. **Push to Your Fork**
   ```bash
   git push origin feature/your-feature-name
   ```
8. **Create a Pull Request**

### Commit Message Convention

Use conventional commit format:

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types:**

- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

**Example:**

```
feat(transcription): add support for MP4 video files

- Add MP4 to supported formats list
- Update file validation logic
- Add tests for MP4 transcription

Closes #123
```

---

## Code Standards

For detailed code standards, see [CODE_STANDARDS.md](CODE_STANDARDS.md).

### Python Style Guide

We follow [PEP 8](https://pep8.org/) with some modifications:

- **Line Length**: 100 characters (not 79)
- **Indentation**: 4 spaces
- **Quotes**: Double quotes for strings
- **Imports**: Grouped and sorted (stdlib, third-party, local)

### Code Formatting

Use `black` for automatic formatting:

```bash
black echonote/
```

### Linting

Use `pylint` for code quality checks:

```bash
pylint echonote/
```

### Type Hints

Use type hints for function signatures:

```python
def process_audio(file_path: str, language: str = "en") -> dict:
    """Process audio file and return transcription."""
    pass
```

### Docstrings

Use Google-style docstrings:

```python
def transcribe_file(audio_path: str, language: str = None) -> dict:
    """
    Transcribe an audio file.

    Args:
        audio_path: Path to the audio file
        language: Language code (e.g., 'en', 'zh'). If None, auto-detect.

    Returns:
        Dictionary containing transcription segments and metadata.

    Raises:
        FileNotFoundError: If audio file doesn't exist
        ValueError: If audio format is not supported

    Example:
        >>> result = transcribe_file("/path/to/audio.mp3", "en")
        >>> print(result["segments"])
    """
    pass
```

### Error Handling

Always use specific exception types:

```python
# Good
try:
    result = process_file(path)
except FileNotFoundError:
    logger.error(f"File not found: {path}")
except ValueError as e:
    logger.error(f"Invalid file format: {e}")

# Bad
try:
    result = process_file(path)
except Exception as e:
    logger.error(f"Error: {e}")
```

### Logging

Use the application logger:

```python
import logging

logger = logging.getLogger(__name__)

logger.debug("Debug message")
logger.info("Info message")
logger.warning("Warning message")
logger.error("Error message")
logger.critical("Critical message")
```

---

## Testing

### Running Tests

```bash
# Run all tests
pytest tests/

# Run specific test file
pytest tests/unit/test_transcription_manager.py

# Run with coverage
pytest --cov=echonote tests/

# Run with verbose output
pytest -v tests/
```

### Writing Tests

#### Unit Tests

```python
import pytest
from core.transcription.manager import TranscriptionManager

class TestTranscriptionManager:
    @pytest.fixture
    def manager(self, mock_db, mock_engine, mock_config):
        return TranscriptionManager(mock_db, mock_engine, mock_config)

    def test_add_task(self, manager):
        """Test adding a transcription task."""
        task_id = manager.add_task("/path/to/audio.mp3", {})
        assert task_id is not None
        assert len(task_id) == 36  # UUID length

    def test_invalid_file_format(self, manager):
        """Test handling of invalid file format."""
        with pytest.raises(ValueError):
            manager.add_task("/path/to/file.xyz", {})
```

#### Integration Tests

```python
import pytest
from data.database.connection import DatabaseConnection
from core.transcription.manager import TranscriptionManager

class TestTranscriptionIntegration:
    @pytest.fixture
    def db(self, tmp_path):
        db_path = tmp_path / "test.db"
        db = DatabaseConnection(str(db_path))
        db.initialize_schema()
        yield db
        db.close_all()

    def test_full_transcription_workflow(self, db, speech_engine, config):
        """Test complete transcription workflow."""
        manager = TranscriptionManager(db, speech_engine, config)

        # Add task
        task_id = manager.add_task("/path/to/audio.mp3", {})

        # Process task
        await manager.process_task(task_id)

        # Verify result
        status = manager.get_task_status(task_id)
        assert status["status"] == "completed"
        assert status["progress"] == 100
```

### Test Coverage

Aim for at least 80% code coverage:

```bash
pytest --cov=echonote --cov-report=html tests/
```

View coverage report:

```bash
open htmlcov/index.html
```

---

## Build and Deployment

### Building for Distribution

#### Windows (.exe)

```bash
# Install PyInstaller
pip install pyinstaller

# Build
pyinstaller --name EchoNote \
    --windowed \
    --icon=resources/icons/app.ico \
    --add-data "resources:resources" \
    --add-data "config:config" \
    main.py

# Output: dist/EchoNote.exe
```

#### macOS (.app)

```bash
# Install py2app
pip install py2app

# Create setup.py
python setup.py py2app

# Output: dist/EchoNote.app
```

#### Linux (AppImage)

```bash
# Use PyInstaller
pyinstaller echonote.spec

# Create AppImage
# (requires appimagetool)
```

### Code Signing

#### Windows

```bash
signtool sign /f certificate.pfx /p password /t http://timestamp.digicert.com dist/EchoNote.exe
```

#### macOS

```bash
codesign --deep --force --verify --verbose --sign "Developer ID Application: Your Name" dist/EchoNote.app
```

### Release Process

1. **Update Version**

   - Update version in `config/default_config.json`
   - Update version in `README.md`
   - Update `CHANGELOG.md`

2. **Run Tests**

   ```bash
   pytest tests/
   ```

3. **Build Packages**

   ```bash
   ./scripts/build_all.sh
   ```

4. **Create Release**
   - Tag the release: `git tag v1.0.0`
   - Push tag: `git push origin v1.0.0`
   - Create GitHub release
   - Upload build artifacts

---

## Additional Resources

### Documentation

- [User Guide](USER_GUIDE.md) - End-user documentation
- [Quick Start](QUICK_START.md) - Getting started guide
- [API Reference](API_REFERENCE.md) - Detailed API documentation
- [FAQ](FAQ.md) - Frequently asked questions
- [Troubleshooting](TROUBLESHOOTING.md) - Common issues and solutions

### External Resources

- [PyQt6 Documentation](https://www.riverbankcomputing.com/static/Docs/PyQt6/)
- [faster-whisper GitHub](https://github.com/SYSTRAN/faster-whisper)
- [OpenAI Whisper](https://github.com/openai/whisper)
- [SQLite Documentation](https://www.sqlite.org/docs.html)

### Community

- **GitHub Issues**: Report bugs and request features
- **GitHub Discussions**: Ask questions and share ideas
- **Discord**: Join our community (link TBD)

---

## License

EchoNote is licensed under the MIT License. See [LICENSE](../LICENSE) for details.

---

**Last Updated**: October 2025  
**Maintainers**: EchoNote Development Team

For questions or support, please open an issue on GitHub.
