# EchoNote Project Overview

## 1. Design Goals
- Deliver an offline-first experience for transcription and calendar management.
- Keep engines pluggable so speech, translation, and calendar providers can evolve independently.
- Maintain desktop-grade security, maintainability, and predictable performance.

## 2. Architecture Summary
```
┌───────────┐      ┌──────────┐      ┌───────────┐
│    UI     │ ───▶ │   Core   │ ───▶ │  Engines  │
└───────────┘      └──────────┘      └───────────┘
        │                 │                   │
        ▼                 ▼                   ▼
     utils/          data/ layer        External services
```
- **UI layer** (`ui/`): PyQt6 widgets, dialogs, notifications, and localization assets.
- **Core layer** (`core/`): domain managers coordinating database, engines, and UI interactions.
- **Engines layer** (`engines/`): concrete implementations for audio capture, speech recognition, translation, and calendar sync.
- **Data layer** (`data/`): SQLite models, storage helpers, encryption, and filesystem management.
- **Utilities** (`utils/`): logging, error handling, resource monitoring, startup optimization, i18n.

## 3. Key Modules
| Module | Path | Responsibility |
| ------ | ---- | -------------- |
| Config Manager | `config/app_config.py` | Load defaults, validate schema, persist user overrides |
| Database Connection | `data/database/connection.py` | Encrypted SQLite access, schema bootstrapping, versioning |
| Model Manager | `core/models/manager.py` | Download, verify, and validate speech models asynchronously |
| Transcription Manager | `core/transcription/manager.py` | Maintain job queue, coordinate speech engine, emit outputs |
| Realtime Recorder | `core/realtime/recorder.py` | Orchestrate audio capture, speech engine, and translation engine |
| Calendar Sync | `core/calendar/manager.py` & `engines/calendar_sync/*` | CRUD local events and integrate external providers |
| Auto Task Scheduler | `core/timeline/auto_task_scheduler.py` | Create background jobs for recording/transcription based on events |

## 4. Data & Security
- **Database**: `~/.echonote/data.db` encrypted by default; keys managed under `data/security`.
- **File storage**: recordings and transcripts live in `~/Documents/EchoNote/` unless reconfigured.
- **Secrets**: OAuth credentials stored via the secrets manager to avoid plaintext exposure.
- **Logging**: every subsystem writes to `~/.echonote/logs/echonote.log` for unified diagnostics.

## 5. Dependency Management
- Runtime dependencies are listed in `requirements.txt`; development extras in `requirements-dev.txt`.
- Runtime checks for FFmpeg and system resources are implemented in `utils/ffmpeg_checker` and `utils/resource_monitor`.
- Model cache paths are configurable through the config manager.

## 6. Testing Strategy
- **Unit tests**: cover configuration, database models, and utilities.
- **Integration tests**: exercise transcription pipelines, calendar sync, and schedulers.
- **Performance baseline**: `tests/e2e_performance_test.py` measures throughput for regression tracking.

## 7. Maintenance Guidelines
- Follow naming and structure rules from `docs/CODE_STANDARDS.md`.
- When adding new engines, preserve existing interfaces so the core layer remains stable.
- Trim unused assets and noisy logs to keep startup fast and trace files readable.
- Rotate encryption keys periodically and confirm schema versions before release.

## 8. Future Enhancements
- Introduce more translation adapters with consistent capability detection.
- Expand cross-platform packaging scripts for official releases.
- Provide analytic dashboards to visualize usage patterns and model performance.

Contributions that keep the architecture cohesive and secure are always welcome.
