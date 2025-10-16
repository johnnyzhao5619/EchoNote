# EchoNote Project Overview

Review this overview before modifying core modules to understand dependency boundaries.

## Translation Index
- [中文 / Chinese](zh-CN.md)
- [Français](fr.md)

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
- **UI layer** (`ui/`): PyQt6 widgets, dialogs, notifications, and localisation assets.
- **Core layer** (`core/`): domain managers coordinating database, engines, and UI interactions.
- **Engines layer** (`engines/`): concrete implementations for audio capture, speech recognition, translation, and calendar sync.
- **Data layer** (`data/`): SQLite schema, models, encryption, storage utilities, and secrets management.
- **Utilities** (`utils/`): logging, error handling, resource monitoring, startup optimisation, and i18n.

## 3. Key Modules
| Module | Path | Responsibility |
| ------ | ---- | -------------- |
| Config Manager | `config/app_config.py` | Load defaults, validate schema, persist user overrides |
| Database Connection | `data/database/connection.py` | Thread-safe SQLite access, schema initialisation, optional SQLCipher key |
| Database Models | `data/database/models.py` | CRUD helpers for tasks, calendar events, attachments, auto-task configs, sync status |
| Encryption & Tokens | `data/security/` | AES-GCM utilities, OAuth token vault, secrets helper |
| Transcription Manager | `core/transcription/manager.py` | Queue orchestration, engine coordination, format conversion |
| Task Queue | `core/transcription/task_queue.py` | Async worker pool with retry/backoff and pause/resume support |
| Realtime Recorder | `core/realtime/recorder.py` | Microphone capture, streaming transcription, translation dispatch, file persistence |
| Calendar Manager | `core/calendar/manager.py` | Local CRUD, sync scheduling, colour policies, provider state tracking |
| Timeline Manager | `core/timeline/manager.py` | Timeline queries, pagination, linking attachments to events |
| Auto Task Scheduler | `core/timeline/auto_task_scheduler.py` | Prepare and trigger meeting recordings/transcriptions based on calendar rules |

## 4. Data & Security
- **Database**: `~/.echonote/data.db` encrypted when SQLCipher is available; keys managed under `data/security`.
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
- Provide analytic dashboards to visualise usage patterns and model performance.

Contributions that keep the architecture cohesive and secure are always welcome.
