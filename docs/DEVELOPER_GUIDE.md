# EchoNote Developer Guide

**Version**: 1.0.0  
**Last Updated**: May 2024

---

## Table of Contents
1. [Introduction](#1-introduction)
2. [Architecture at a Glance](#2-architecture-at-a-glance)
3. [Local Environment Setup](#3-local-environment-setup)
4. [Configuration & Secrets](#4-configuration--secrets)
5. [Project Map](#5-project-map)
6. [Domain Deep-Dives](#6-domain-deep-dives)
    1. [Application Bootstrap](#61-application-bootstrap)
    2. [Core Services](#62-core-services)
    3. [Engine Layer](#63-engine-layer)
    4. [UI Layer](#64-ui-layer)
    5. [Utilities](#65-utilities)
7. [Data Persistence & Migrations](#7-data-persistence--migrations)
8. [Quality Toolkit](#8-quality-toolkit)
9. [Runbook & Troubleshooting](#9-runbook--troubleshooting)
10. [Contribution Workflow](#10-contribution-workflow)
11. [Reference Resources](#11-reference-resources)

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

Follow the platform-specific instructions in `docs/quick-start/README.md` if you need package manager commands.

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
- Secrets such as OAuth credentials and encryption keys are stored via `data/security/secrets_manager.py` and encrypted when possible.
- Engine API keys should be set via the settings UI, which delegates to the `SettingsManager` to persist encrypted values.

When adding new settings:
1. Extend the schema in `config/default_config.json`.
2. Update `ConfigManager` getters/setters.
3. Surface changes through `core/settings/manager.py` and the relevant UI component.
4. Provide migration defaults in `utils/first_run_setup.py` so existing users receive sane values.

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
├── ui/                        # PyQt6 widgets, dialogs, navigation shell
├── utils/                     # Logging, diagnostics, async helpers
└── tests/                     # Unit, integration, and E2E scaffolding
```
Supplementary documentation lives under `docs/` (see [Reference Resources](#11-reference-resources)).

---

## 6. Domain Deep-Dives
### 6.1 Application Bootstrap
`main.py` orchestrates startup:
1. Configure logging via `utils/logger.py`.
2. Install a global exception hook that surfaces crashes with `ui/common/error_dialog.py`.
3. Initialize the Qt application, splash screen, and first-run setup.
4. Load configuration (`ConfigManager`), ensure FFmpeg availability (`utils/ffmpeg_checker.py`), and open the encrypted database (`data/database/connection.py`).
5. Instantiate managers: transcription, realtime, calendar, timeline, and settings; wire engine adapters from `engines/`.
6. Initialize background services (`core/calendar/sync_scheduler.py`, `core/timeline/auto_task_scheduler.py`).
7. Construct the main window (`ui/main_window.py`) and hand control to the Qt event loop.

### 6.2 Core Services
Each subpackage inside `core/` houses a manager that encapsulates domain logic and exposes a thin API to the UI.

- **Transcription (`core/transcription/`)**
  - `TranscriptionManager` handles task creation (`add_task`, `add_tasks_from_folder`), background processing (`start_processing`, `pause_processing`, `resume_processing`, `stop_all_tasks`), and progress callbacks.
  - `TaskQueue` provides coroutine scheduling with retry logic (`start`, `add_task`, `pause`, `resume`, `stop`).
  - `FormatConverter` exports transcripts to TXT/SRT/Markdown and attaches metadata.

- **Real-time recording (`core/realtime/`)**
  - `RealtimeRecorder` streams audio frames from `engines/audio/capture.py`, applies voice-activity detection, and dispatches transcripts to listeners.
  - `audio_buffer.py` maintains rolling buffers for low-latency playback or streaming transcripts.

- **Calendar (`core/calendar/`)**
  - `CalendarManager` exposes CRUD methods (`create_event`, `update_event`, `delete_event`, `get_event`, `get_events`) and synchronization entrypoints (`sync_external_calendar`).
  - `SyncScheduler` polls external providers on an interval, tracks sync tokens, and reconciles conflicts.

- **Timeline (`core/timeline/`)**
  - `TimelineManager` aggregates events and artifacts (`get_timeline_events`, `search_events`, `get_event_artifacts`).
  - `AutoTaskScheduler` observes upcoming events and can trigger `RealtimeRecorder` or transcription tasks automatically.

- **Settings (`core/settings/manager.py`)**
  - Centralizes user preferences, theme toggles, language selection, API credentials, and persists values through `ConfigManager` and the secrets store.

### 6.3 Engine Layer
Engine adapters isolate third-party APIs and hardware concerns.

- **Speech (`engines/speech/`)**
  - `SpeechEngine` defines the contract (`get_name`, `get_supported_languages`, `transcribe_file`, `transcribe_stream`, `get_config_schema`).
  - `faster_whisper_engine.py` provides the default local transcription implementation with GPU detection.
  - `openai_engine.py`, `google_engine.py`, and `azure_engine.py` integrate cloud services and reuse `api_validator.py` and `usage_tracker.py` for quota management.

- **Audio (`engines/audio/`)**
  - `capture.py` wraps PyAudio streams and exposes async iteration for live capture.
  - `vad.py` provides voice-activity detection utilities consumed by both realtime and batch flows.

- **Translation (`engines/translation/`)**
  - `base.py` defines the translator interface; `google_translate.py` implements it through Google Translate APIs.

- **Calendar sync (`engines/calendar_sync/`)**
  - `base.py` standardizes methods such as `fetch_events`, `create_event`, `update_event`, `delete_event`.
  - `google_calendar.py` and `outlook_calendar.py` translate between provider APIs and local models, relying on credentials issued via the settings UI.

### 6.4 UI Layer
UI code under `ui/` follows Qt best practices:
- `main_window.py` wires the sidebar, central stacked widgets, and orchestrates manager interactions.
- Feature-specific packages (`batch_transcribe`, `realtime_record`, `calendar_hub`, `timeline`, `settings`) contain views, dialogs, and presenters dedicated to each domain.
- Shared components and dialogs live in `ui/common/` and `ui/dialogs/` (e.g., splash screen, notifications, error handling).
- Qt styles reside in `resources/themes/`, translations in `resources/translations/`, and icons in `resources/icons/`.

### 6.5 Utilities
Reusable helpers live under `utils/`:
- `logger.py` sets up structured logging across modules.
- `ffmpeg_checker.py`, `gpu_detector.py`, and `resource_monitor.py` collect system diagnostics.
- `first_run_setup.py` provisions configuration, database schema, and sample folders.
- `qt_async.py` bridges asyncio tasks with Qt's event loop.
- `error_handler.py` and `network_error_handler.py` normalize error reporting for UI dialogs.
- `http_client.py` wraps shared HTTP session settings, including retries and timeouts.

---

## 7. Data Persistence & Migrations
The data layer is anchored by `data/database`:
- `connection.py` offers a thread-local connection pool with optional SQLCipher encryption (`initialize_schema` applies `schema.sql`).
- `models.py` contains dataclass-backed models (`TranscriptionTask`, `CalendarEvent`, `EventAttachment`, `AutoTaskConfig`, `CalendarSyncStatus`, etc.) with helpers to persist and query records.
- `schema.sql` is the authoritative schema. Update it when adding tables or columns and bump the schema migration logic in `utils/first_run_setup.py` accordingly.

Additional support modules:
- `data/security/encryption.py` and `secrets_manager.py` manage symmetric keys and secure storage.
- `data/storage/file_manager.py` handles transcript/export paths, cleanup, and disk quotas.
- `data/test_data_layer.py` contains fixtures to validate schema changes; extend it with regression tests when altering database structure.

When evolving the schema:
1. Update `schema.sql`.
2. Extend models in `models.py` (fields, serialization helpers).
3. Provide backfill logic inside `FirstRunSetup` (e.g., default values, migrations).
4. Add unit tests that exercise new fields or relationships.

---

## 8. Quality Toolkit
### Tests
```bash
# Run all tests
pytest tests

# Run unit tests only
pytest tests/unit

# Run integration scaffolding (requires configured services)
pytest tests/integration

# Execute the end-to-end/performance harness
pytest tests/e2e_performance_test.py
```
Add new tests under `tests/unit/` or `tests/integration/` alongside fixtures in `tests/fixtures/`. Prefer deterministic inputs; rely on the existing secrets abstraction rather than hard-coding credentials.

### Linters & Formatters
```bash
# Run the full pre-commit suite on staged changes
pre-commit run --all-files

# Or invoke individual tools
black .
isort .
flake8
mypy
bandit -c pyproject.toml
interrogate
```
CI runs the same hooks, so keeping a clean `pre-commit` state locally avoids surprises.

### Coverage
```bash
pytest --cov=core --cov=engines --cov=data --cov=utils --cov=ui --cov-report=term-missing
```
Aim for ≥80% coverage on core logic. Investigate any newly introduced gaps.

---

## 9. Runbook & Troubleshooting
| Symptom | Likely Cause | Mitigation |
| --- | --- | --- |
| Application launches without media support | FFmpeg missing | Run `utils.ffmpeg_checker.get_ffmpeg_checker().get_installation_instructions()` or install FFmpeg via your package manager. |
| Microphone input unavailable | PortAudio backend missing or busy | Install PortAudio (`brew install portaudio`, `apt install portaudio19-dev`) and ensure no other application has exclusive access. |
| GPU acceleration disabled | No compatible CUDA/CoreML device detected | Check `utils/gpu_detector.py` logs; adjust `config['transcription']['faster_whisper']['device']` or install appropriate drivers. |
| Calendar sync silently stops | Expired OAuth tokens | Refresh credentials through the settings UI; `CalendarSyncStatus` rows will update once a new token is stored. |
| Schema mismatch errors | Local database predates schema change | Delete/backup `~/.echonote/data.db` and rerun `DatabaseConnection.initialize_schema()` via `FirstRunSetup.setup()` or start the app to trigger automatic migration. |

Enable debug logging (set `ECHO_NOTE_LOG_LEVEL=DEBUG` before launch) to get verbose traces from managers and engine adapters.

---

## 10. Contribution Workflow
1. **Review open issues** and existing documentation (`docs/project-overview/README.md`) before making structural changes.
2. **Create a topic branch** from `main`: `git checkout -b feature/<concise-summary>`.
3. **Keep changes focused** – avoid unrelated refactors in the same pull request.
4. **Follow code standards** defined in `docs/CODE_STANDARDS.md` (naming, docstrings, error handling).
5. **Run `pre-commit run --all-files` and the relevant `pytest` suites** before opening a PR.
6. **Write clear commit messages** describing intent and scope; reference issue IDs when applicable.
7. **Update documentation** (including this guide) whenever you introduce new modules, settings, or workflows.

---

## 11. Reference Resources
- `docs/README.md` – documentation index
- `docs/project-overview/README.md` – product vision and personas
- `docs/user-guide/README.md` – end-user guide
- `docs/quick-start/README.md` – environment and installation specifics
- `docs/API_REFERENCE.md` – module-by-module API details
- `docs/CODE_STANDARDS.md` – formatting, logging, error-handling expectations
- `docs/ACCESSIBILITY.md` – accessibility checklist for UI changes
- `docs/GOOGLE_OAUTH_SETUP.md` – configuring Google API credentials

For unresolved questions, open a GitHub issue or start a discussion thread so decisions remain discoverable.
