# EchoNote Developer Guide

**Version**: 1.0.0  
**Last Updated**: Oct 2025

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
12. [Architecture Review Notes (2025-02)](#12-architecture-review-notes-2025-02)

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

### Credential storage strategy
- Password-like secrets (e.g., cached service credentials) use the `SecurityManager` in `data/security/encryption.py`.
- Each hash now stores a **per-password 16-byte random salt** alongside a PBKDF2-HMAC(SHA-256) digest with 200k iterations.
- Hashes are encoded as `salt$hash` (both segments Base64). Verification understands both the new and legacy formats so existing data can be migrated lazily on first successful login.
- Call `verify_password(..., return_new_hash=True)` to detect legacy entries and persist the returned migrated hash. Legacy hashes are SHA-256 of the password plus the historical machine salt and should be replaced as soon as feasible.

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
  - 后台事件循环在关闭时会捕获 `TaskQueue.stop()` 的异常：管理器会记录失败、重试一次并在必要时强制取消剩余协程，随后关闭事件循环线程，避免遗留僵尸线程。

- **Real-time recording (`core/realtime/`)**
  - `RealtimeRecorder` streams audio frames from `engines/audio/capture.py`, applies voice-activity detection with the default thresholds, and dispatches transcripts to listeners. VAD currently runs automatically with no user-facing toggle; a forthcoming control will live under **Settings → Real-time Recording → Voice Activity Detection** once exposed in the UI.
  - 每次调用 `RealtimeRecorder.start_recording` 都会重新构建内部转录、翻译及流式输出队列，确保它们在各自事件循环内首次消费时才绑定，避免 “bound to a different event loop” 错误。
  - `audio_buffer.py` maintains rolling buffers for low-latency playback or streaming transcripts.
  - `SettingsManager.get_realtime_preferences()` centralizes the default recording format and auto-save toggle. UI (`ui/realtime_record/widget.py`) and background schedulers (`core/timeline/auto_task_scheduler.py`) both consult it before starting a session so that changing settings propagates immediately.

- **Calendar (`core/calendar/`)**
  - `CalendarManager` exposes CRUD methods (`create_event`, `update_event`, `delete_event`, `get_event`, `get_events`) and synchronization entrypoints (`sync_external_calendar`).
  - Provider-specific identifiers now live in `calendar_event_links`, allowing the same event to sync with multiple services. Migration `004_calendar_event_links.sql` copies legacy `calendar_events.external_id` values and tags ambiguous records with `provider='default'` so older data remains addressable.
  - Local updates persist first, then each linked provider adapter receives the change via `update_event`. Failures are logged and surfaced back to the caller with the provider list, while successful calls refresh the mapping timestamp. Deletions follow the reverse order: adapters are asked to `delete_event` before the local record and links are removed, preventing silent drifts when an API call is rejected.
  - `SyncScheduler` polls external providers on an interval, tracks sync tokens, and reconciles conflicts.

- **Timeline (`core/timeline/`)**
  - `TimelineManager` aggregates events and artifacts (`get_timeline_events`, `search_events`, `get_event_artifacts`).
  - `TimelineManager.get_search_snippet` records a warning when the transcript file referenced by an event attachment cannot be found and returns a user-facing "Transcript unavailable" message. Corrupted UTF-8 transcripts emit an error with the file path so you can locate and regenerate the artifact quickly.
  - `AutoTaskScheduler` observes upcoming events and can trigger `RealtimeRecorder` or transcription tasks automatically.
  - Auto task startup waits for explicit confirmation from the `RealtimeRecorder` thread. If microphone capture or other dependencies fail during startup, the scheduler clears any pending state and emits an error notification—ensure audio drivers and required binaries are ready before enabling automatic recording. 自动任务会在独立线程中运行新的 asyncio 事件循环；录制器会为每次会话重建队列，因此可以在 UI 事件循环与自动任务循环之间无缝切换。

- **Settings (`core/settings/manager.py`)**
  - Centralizes user preferences, theme toggles, language selection, API credentials, and persists values through `ConfigManager` and the secrets store.

### 6.3 Engine Layer
Engine adapters isolate third-party APIs and hardware concerns.

- **Speech (`engines/speech/`)**
  - `SpeechEngine` defines the contract (`get_name`, `get_supported_languages`, `transcribe_file`, `transcribe_stream`, `get_config_schema`).
  - `faster_whisper_engine.py` provides the default local transcription implementation with GPU detection.
  - `openai_engine.py`, `google_engine.py`, and `azure_engine.py` integrate cloud services and reuse `api_validator.py` and `usage_tracker.py` for quota management.
  - Streaming adapters now accept the recorder's `sample_rate`; local whisper models resample to 16 kHz, while cloud engines keep the original rate and pass it to their APIs.

- **Audio (`engines/audio/`)**
  - `capture.py` wraps PyAudio streams and exposes async iteration for live capture.
  - `vad.py` provides voice-activity detection utilities consumed by both realtime and batch flows.

- **Translation (`engines/translation/`)**
  - `base.py` defines the translator interface; `google_translate.py` implements it through Google Translate APIs.

- **Calendar sync (`engines/calendar_sync/`)**
  - `base.py` standardizes methods such as `fetch_events`, `create_event`, `update_event`, `delete_event`.
  - `google_calendar.py` and `outlook_calendar.py` translate between provider APIs and local models, relying on credentials issued via the settings UI.
  - Remote deletions now flow back into the local store: adapters surface cancelled or missing events through a `deleted` payload, and `CalendarManager.sync_external_calendar` removes the event record, provider link, and attachments so no orphaned data lingers after an external change.

### 6.4 UI Layer
UI code under `ui/` follows Qt best practices:
- `main_window.py` wires the sidebar, central stacked widgets, and orchestrates manager interactions.
- Feature-specific packages (`batch_transcribe`, `realtime_record`, `calendar_hub`, `timeline`, `settings`) contain views, dialogs, and presenters dedicated to each domain.
- Shared components and dialogs live in `ui/common/` and `ui/dialogs/` (e.g., splash screen, notifications, error handling).
- Qt styles reside in `resources/themes/`, translations in `resources/translations/`, and icons in `resources/icons/`.

#### UI/线程与异步事件循环
- `ui/realtime_record/widget.py` 为实时录制场景专门启动了一个 asyncio 事件循环线程，用于驱动录制/翻译协程。该线程在控件构造时创建，必须在控件关闭时显式停止：调用 `self._async_loop.call_soon_threadsafe(self._async_loop.stop)`，并在同一清理例程里 `join` 线程，防止线程泄漏。
- `core/realtime/recorder.py` 在启动录音失败时会自动回滚内部状态：取消已调度的任务、清空音频缓冲与队列，并恢复 `is_recording` 等标记。调用方一旦收到异常或 `on_error` 回调即可安全重试，无需手动清理。
- 清理由三个步骤组成：1) 停止 `QTimer`（如状态轮询器）并断开其 `timeout` 回调，避免 Qt 保留悬挂引用；2) 若录制仍在进行，通过 `asyncio.run_coroutine_threadsafe` 提交 `RealtimeRecorder.stop_recording()`，等待结果或在超时时取消；3) 在事件循环停止后将 `set_callbacks()` 设为默认，确保控件被销毁后不会再访问已经释放的 UI 对象。
- 如需销毁控件，请使用 `close()` 或 `deleteLater()`，它们都会触发上述清理逻辑。不要跳过 `closeEvent`，也不要直接丢弃实例，否则后台线程和回调将保持活动状态并干扰后续页面创建。

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
- Calendar re-authorization always overwrites the existing `CalendarSyncStatus` row for the provider. `_complete_oauth_flow` reuses the record, clears any stale `sync_token`, and marks it active again. The `save()` helper enforces a single active row per provider by deactivating older entries, so keep this uniqueness assumption in mind when writing migrations or manual data fixes.
- 日历重新授权会覆盖该提供商现有的 `CalendarSyncStatus` 记录：`_complete_oauth_flow` 会复用原有行、清空过期的 `sync_token` 并重新激活，`save()` 通过停用旧行保证每个提供商仅存在一条活跃记录。编写迁移或手动修复数据时必须遵循这一唯一性约定。
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

### Performance Notes
- **Audio buffer operations** – `core/realtime/audio_buffer.AudioBuffer` 使用 `deque.extend` 和 `numpy.fromiter` 避免逐样本锁竞争与整缓冲复制。追加数据时务必传入一维 `numpy.ndarray`，窗口读取应优先通过 `get_window`/`get_sliding_windows`，让内部仅对所需片段迭代。
- **Window sizing** – 窗口长度和重叠计算使用采样率转换为样本数，确保 `overlap_seconds < window_duration_seconds`，否则内部会直接返回空列表并记录警告。
- **线程安全** – `AudioBuffer` 对所有公共方法加锁，批量写入越大，锁的占用时间越短；如果需要更高吞吐量，优先合并小帧后再调用 `append`。

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

---

## 12. Architecture Review Notes (2025-02)

### 12.1 已交付的改进
- **日历入口数据校验强化**：`CalendarManager.create_event` 现在会验证标题与起止时间、并在必要时统一时区后比较时间顺序，防止脏数据写入数据库并避免后续 UI/自动化流程崩溃。【F:core/calendar/manager.py†L68-L140】【F:core/calendar/manager.py†L603-L655】
- **OAuth 令牌过期计算更健壮**：刷新逻辑会在有时区信息时使用相同的时区基准计算 `expires_in`，规避天真地减法导致的 `TypeError` 并减少无谓的重试。【F:core/calendar/manager.py†L316-L348】
- **时间线调度窗口可配置**：自动任务调度器以分钟维度定义前后窗口并转换为天数传递给时间线查询，移除硬编码常数，也新增了针对不同时区的秒数计算辅助方法。【F:core/timeline/auto_task_scheduler.py†L55-L198】【F:core/timeline/auto_task_scheduler.py†L641-L655】
- **时间线接口类型修正**：`TimelineManager.get_timeline_events` 接受浮点天数并更新文档，明确允许使用细粒度窗口，提高调用方的可读性与类型一致性。【F:core/timeline/manager.py†L44-L106】

### 12.2 待跟进的重点事项
- **实时与批量 UI 待完成交互**：批量转录暂停按钮、实时录制错误/成功提示仍为 TODO，建议补齐用户反馈与状态同步逻辑以避免功能缺失。【F:ui/batch_transcribe/widget.py†L655-L678】【F:ui/realtime_record/widget.py†L1052-L1079】【F:ui/realtime_record/widget.py†L1282-L1306】
- **时间戳与时区统一策略**：目前数据库保存的 ISO 字符串可能混合无时区和含时区两种格式（例如事件与 OAuth 令牌），后续应制定统一规范（例如统一转换为 UTC 并在 UI 层进行本地化），以免不同模块再度引入比较错误。【F:core/calendar/manager.py†L68-L140】【F:core/timeline/auto_task_scheduler.py†L147-L206】
- **数据层脚本测试化**：`data/test_data_layer.py` 仍以脚本方式运行并依赖 `print`，建议迁移到 `pytest` 体系，复用现有夹具以保持自动化测试一致性。【F:data/test_data_layer.py†L1-L80】
