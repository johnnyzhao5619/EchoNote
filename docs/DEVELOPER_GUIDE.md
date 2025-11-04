# EchoNote Developer Guide

**Version**: 1.2.0
**Last Updated**: Nov 2025

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [Architecture at a Glance](#2-architecture-at-a-glance)
3. [Local Environment Setup](#3-local-environment-setup)
4. [Configuration & Secrets](#4-configuration--secrets)
5. [Project Map](#5-project-map)
6. [Domain Deep-Dives](#6-domain-deep-dives)
7. [Data Persistence & Migrations](#7-data-persistence--migrations)
8. [Quality Toolkit](#8-quality-toolkit)
9. [Runbook & Troubleshooting](#9-runbook--troubleshooting)
10. [Contribution Workflow](#10-contribution-workflow)
11. [Reference Resources](#11-reference-resources)
12. [Architecture Review Notes](#12-architecture-review-notes)

---

## 1. Introduction

EchoNote is a local-first desktop application that combines batch and real-time transcription, calendar coordination, and an interactive timeline. The goal of this guide is to give contributors a cohesive mental model of the system, clarify day-to-day development tasks, and highlight the practices that keep the codebase maintainable.

### Design Principles

- **Local-first privacy** – the application runs without a cloud dependency; encrypted persistence and secrets management protect user data.
- **Composable modules** – each feature has a focused manager inside `core/` with clear boundaries to UI widgets and engine adapters.
- **Pluggable engines** – speech, translation, audio capture, and calendar sync adapters live in `engines/` and expose consistent interfaces so that alternatives can be added without ripple effects.
- **Operational empathy** – diagnostic tools, dependency checks, and resource monitors are built into the startup sequence to make field issues debuggable.

---

## 2. Architecture at a Glance

The project follows a layered architecture where UI widgets orchestrate feature managers, which in turn talk to engine adapters and the data layer.

```
┌────────────────────────────────────────────┐
│                UI Layer (`ui/`)            │
│  Qt widgets, dialogs, navigation shell     │
└───────────────────────┬────────────────────┘
                        │ signals/slots
┌───────────────────────┴────────────────────┐
│          Core Services (`core/`)           │
│  Domain managers, schedulers, task queues  │
└───────────────────────┬────────────────────┘
                        │ contracts
┌───────────────────────┴────────────────────┐
│           Engine Layer (`engines/`)        │
│  Speech, audio, translation, calendar APIs │
└───────────────────────┬────────────────────┘
                        │ persistence
┌───────────────────────┴────────────────────┐
│            Data Layer (`data/`)            │
│  SQLite access, storage, secrets, crypto   │
└────────────────────────────────────────────┘
```

Supporting modules under `utils/` provide logging, diagnostics, async helpers, and environment checks that are reused across layers.

---

## 3. Local Environment Setup

### Prerequisites

- Python **3.10+** (3.11 recommended)
- Git
- pip / venv tooling
- Optional runtime dependencies: FFmpeg (media support), PortAudio (microphone capture), CUDA drivers (GPU acceleration)
- **PySide6 licensing** – The desktop UI uses PySide6 (LGPL v3), which is fully compatible with EchoNote's Apache 2.0 license. PySide6 is dynamically linked, allowing commercial distribution without additional licensing requirements.

### Step-by-step setup

```bash
# 1. Clone the repository
git clone https://github.com/johnnyzhao5619/echonote.git
cd EchoNote

# 2. Create an isolated environment
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 3. Install runtime dependencies
pip install --upgrade pip
pip install -r requirements.txt

# 4. Install development extras (linters, type-checkers, tests)
pip install -r requirements-dev.txt

# 5. Install pre-commit hooks (runs Black, isort, flake8, mypy, bandit, interrogate)
pre-commit install

# 6. Launch the app
python main.py
```

The first launch triggers `utils.first_run_setup.FirstRunSetup` which creates the application directories under `~/.echonote`, initializes the SQLite schema, and writes default configuration files.

---

## 4. Configuration & Secrets

Configuration is managed by `config/app_config.py`.

- **Defaults** live in `config/default_config.json` (version, paths, scheduler cadence, engine defaults).
- **User overrides** are persisted to `~/.echonote/app_config.json`.
- **Resource monitor thresholds** ship as `resource_monitor.low_memory_mb=500` and `resource_monitor.high_cpu_percent=90`.
- Secrets such as OAuth credentials and encryption keys are stored via `data/security/secrets_manager.py` and encrypted when possible.
- Engine API keys should be set via the settings UI, which delegates to the `SettingsManager` to persist encrypted values.

### Credential storage strategy

- Password-like secrets use the `SecurityManager` in `data/security/encryption.py`.
- Each hash now stores a **per-password 16-byte random salt** alongside a PBKDF2-HMAC(SHA-256) digest with 200k iterations.
- Hashes are encoded as `salt$hash` (both segments Base64). Verification understands both new and legacy formats.

---

## 5. Project Map

```
EchoNote/
├── main.py                     # Application bootstrap & dependency wiring
├── config/
│   ├── __init__.py
│   ├── app_config.py          # ConfigManager implementation
│   └── default_config.json    # Baseline configuration
├── core/
│   ├── transcription/         # Batch transcription managers and task queue
│   ├── realtime/              # Live recording pipeline
│   ├── calendar/              # Calendar CRUD + sync scheduler
│   ├── timeline/              # Timeline aggregation & automation
│   └── settings/              # User preference management
├── data/
│   ├── database/              # SQLite access, schema, models
│   ├── security/              # Encryption, secrets, OAuth helpers
│   └── storage/               # File lifecycle helpers
├── engines/
│   ├── speech/                # Speech recognition adapters
│   ├── audio/                 # Microphone capture & VAD
│   ├── translation/           # Translation engines
│   └── calendar_sync/         # Google & Outlook sync adapters
├── resources/                 # Icons, QSS themes, translations
├── ui/                        # PySide6 widgets, dialogs, navigation shell
├── utils/                     # Logging, diagnostics, async helpers
└── tests/                     # Unit, integration, and E2E scaffolding
```

---

## 6. Domain Deep-Dives

### 6.1 Application Bootstrap

`main.py` orchestrates startup:

1. Configure logging via `utils/logger.py`.
2. Install a global exception hook that surfaces crashes with `ui/common/error_dialog.py`.
3. Initialize the Qt application, splash screen, and first-run setup.
4. Load configuration (`ConfigManager`), ensure FFmpeg availability, and open the encrypted database.
5. Instantiate managers and wire engine adapters.
6. Initialize background services.
7. Construct the main window and hand control to the Qt event loop.

### 6.2 Core Services

Each subpackage inside `core/` houses a manager that encapsulates domain logic and exposes a thin API to the UI.

- **Transcription (`core/transcription/`)**

  - `TranscriptionManager` handles task creation, background processing, and progress callbacks.
  - `TaskQueue` provides coroutine scheduling with retry logic.
  - `FormatConverter` exports transcripts to TXT/SRT/Markdown and attaches metadata.
  - Background event loops handle `TaskQueue.stop()` exceptions during shutdown.

- **Real-time recording (`core/realtime/`)**

  - `RealtimeRecorder` streams audio frames, applies voice-activity detection, and dispatches transcripts.
  - Each call to `RealtimeRecorder.start_recording` rebuilds internal queues to avoid event loop binding errors.
  - `audio_buffer.py` maintains rolling buffers for low-latency playback.
  - `SettingsManager.get_realtime_preferences()` centralizes recording format and auto-save settings.

- **Calendar (`core/calendar/`)**

  - `CalendarManager` exposes CRUD methods and synchronization entrypoints.
  - Provider-specific identifiers live in `calendar_event_links` for multi-service sync.
  - `SyncScheduler` polls external providers and reconciles conflicts.

- **Timeline (`core/timeline/`)**

  - `TimelineManager` aggregates events and artifacts with search capabilities.
  - `AutoTaskScheduler` observes upcoming events and triggers automatic recording.
  - Auto tasks run in separate asyncio event loops with seamless UI integration.

- **Settings (`core/settings/manager.py`)**
  - Centralizes user preferences, theme toggles, language selection, and API credentials.

### 6.3 Engine Layer

Engine adapters isolate third-party APIs and hardware concerns.

- **Speech (`engines/speech/`)**

  - `SpeechEngine` defines the contract for transcription services.
  - `faster_whisper_engine.py` provides local transcription with GPU detection.
  - Cloud engines integrate with OpenAI, Google, and Azure services.

- **Audio (`engines/audio/`)**

  - `capture.py` wraps PyAudio streams for live capture.
  - `vad.py` provides voice-activity detection utilities.

- **Translation (`engines/translation/`)**

  - `base.py` defines the translator interface.
  - `google_translate.py` implements Google Translate integration.

- **Calendar sync (`engines/calendar_sync/`)**
  - `base.py` standardizes OAuth flows and API methods.
  - Provider-specific adapters handle Google Calendar and Outlook integration.

### 6.4 UI Layer

UI code under `ui/` follows Qt best practices:

- `main_window.py` wires the sidebar and central widgets.
- Feature-specific packages contain dedicated views and dialogs.
- Shared components live in `ui/common/` and `ui/dialogs/`.
- Qt styles, translations, and icons reside in `resources/`.
- Icon assets include platform-specific formats for build packaging.

#### PySide6 Migration

- Successfully migrated from PyQt to PySide6 with zero functionality regression.
- Updated all imports, API differences, and packaging requirements.
- Maintained LGPL compliance through dynamic linking.

#### UI Threading and Async Event Loops

- `ui/realtime_record/widget.py` starts dedicated asyncio threads for recording scenarios.
- `core/realtime/recorder.py` automatically rolls back state on startup failures.
- Proper cleanup prevents thread leaks and dangling references.
- Widget destruction requires explicit cleanup through `close()` or `deleteLater()`.

### 6.5 Utilities

Reusable helpers under `utils/`:

- `logger.py` sets up structured logging across modules.
- `ffmpeg_checker.py`, `gpu_detector.py`, and `resource_monitor.py` collect system diagnostics.
- `first_run_setup.py` provisions configuration and database schema.
- `qt_async.py` bridges asyncio tasks with Qt's event loop.
- `error_handler.py` and `network_error_handler.py` normalize error reporting.

---

## 7. Data Persistence & Migrations

The data layer is anchored by `data/database`:

- `connection.py` offers thread-local connection pool with optional encryption.
- `models.py` contains dataclass-backed models with persistence helpers.
- Calendar re-authorization overwrites existing `CalendarSyncStatus` records with proper uniqueness constraints.
- `schema.sql` is the authoritative schema definition.

Additional support modules:

- `data/security/encryption.py` and `secrets_manager.py` manage symmetric keys and secure storage.
- `data/storage/file_manager.py` handles transcript paths, cleanup, and disk quotas.
- `tests/data/test_data_layer.py` provides integration tests covering database schema, encryption, and file storage.

---

## 8. Quality Toolkit

### Tests

```bash
# Run all tests
pytest tests

# Run unit tests only
pytest tests/unit

# Run integration tests
pytest tests/integration

# Execute performance tests
pytest tests/e2e_performance_test.py
```

### Performance Notes

- **Audio buffer operations** – `AudioBuffer` uses `deque.extend` and `numpy.fromiter` to avoid lock contention.
- **Window sizing** – Calculations use sample rate conversion with proper overlap validation.
- **Thread safety** – All public methods are locked; larger batch writes reduce lock occupation time.

### Linters & Formatters

```bash
# Run the full pre-commit suite
pre-commit run --all-files

# Individual tools
black .
isort .
flake8
mypy
bandit -c pyproject.toml
interrogate
```

### Coverage

```bash
pytest --cov=core --cov=engines --cov=data --cov=utils --cov=ui --cov-report=term-missing
```

---

## 9. Runbook & Troubleshooting

| Symptom                   | Likely Cause           | Mitigation                                |
| ------------------------- | ---------------------- | ----------------------------------------- |
| No media support          | FFmpeg missing         | Install FFmpeg via package manager        |
| Microphone unavailable    | PortAudio missing/busy | Install PortAudio, check exclusive access |
| GPU acceleration disabled | No compatible device   | Check drivers, adjust device config       |
| Calendar sync stops       | Expired OAuth tokens   | Refresh credentials through settings UI   |
| Schema mismatch           | Outdated database      | Delete/backup database, trigger migration |

Enable debug logging with `ECHO_NOTE_LOG_LEVEL=DEBUG` for verbose traces.

---

## 10. Contribution Workflow

1. **Review open issues** and existing documentation before making structural changes.
2. **Create a topic branch** from `main`.
3. **Keep changes focused** – avoid unrelated refactors in the same pull request.
4. **Follow code standards** defined in `docs/CODE_STANDARDS.md`.
5. **Run pre-commit and tests** before opening a PR.
6. **Write clear commit messages** with issue references when applicable.
7. **Update documentation** when introducing new modules or workflows.

---

## 11. Reference Resources

- `docs/README.md` – documentation index
- `docs/project-overview/README.md` – product vision and personas
- `docs/user-guide/README.md` – end-user guide
- `docs/quick-start/README.md` – environment and installation specifics
- `docs/API_REFERENCE.md` – module-by-module API details
- `docs/CODE_STANDARDS.md` – formatting and error-handling expectations
- `docs/ACCESSIBILITY.md` – accessibility checklist for UI changes

---

## 12. Architecture Review Notes

### 12.1 Delivered Improvements

- **Batch pause and real-time recording feedback**: Enhanced UI feedback with synchronized button states and system notifications, covered by unit tests for regression safety.
- **Calendar entry data validation**: Strengthened validation for titles, start/end times, and timezone handling to prevent database corruption.
- **OAuth token expiration calculation**: More robust refresh logic using consistent timezone baselines to avoid TypeError exceptions.
- **Timeline scheduling window configuration**: Configurable before/after windows in minute dimensions with timezone-specific calculations.
- **Timeline interface type correction**: Updated to accept floating-point days for fine-grained window control.
- **Timeline search snippet internationalization**: Integrated with global I18nQtManager for multilingual support with fallback logic.
- **Reminder notification time localization**: Unified event start time conversion for consistent local time display.
- **Auto task notification internationalization**: Multilingual desktop notifications with immediate language switching support.
- **Data layer script testing**: Migrated validation to pytest-based integration tests covering database, encryption, OAuth, and file lifecycle.

### 12.2 Key Items to Follow Up

- **Timestamp and timezone unification strategy**: Establish unified specification for ISO string formats in database to prevent comparison errors across modules. Consider standardizing on UTC storage with UI-layer localization.
