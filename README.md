# EchoNote

> Local-first transcription, calendar orchestration, and timeline insights for desktop knowledge workers.

## 🌐 Language Navigation
- [中文说明 / Chinese Guide](README.zh-CN.md)
- [English Guide](README.en.md)
- [Français](README.fr.md)

## Overview
EchoNote is a PyQt6 desktop application that blends batch and real-time transcription with calendar automation and a searchable timeline. The codebase is organised around small, testable managers that coordinate pluggable engines and a Qt-based interface.

### Key Capabilities
- Batch transcription for audio and video sources with resumable jobs and multi-format export handled by `core/transcription`.
- Real-time recording with voice activity detection, optional translation, and waveform callbacks powered by `core/realtime` and `engines/audio`.
- Local calendar storage with optional Google/Outlook synchronisation plus automatic meeting tasks in `core/calendar` and `core/timeline`.
- Encrypted persistence backed by `data/database`, `data/security`, and configurable storage paths.
- Resource, dependency, and notification utilities consolidated under `utils/`.

## Architecture at a Glance
```
EchoNote/
├── main.py                # Application bootstrap & dependency wiring
├── config/                # Default configuration and runtime manager
├── core/                  # Feature managers (calendar, realtime, timeline, transcription, settings)
├── engines/               # Pluggable engines (audio capture, speech, translation, calendar sync)
├── data/                  # Database schema/models, encrypted storage, file management
├── ui/                    # Qt widgets, dialogs, and navigation shell
├── utils/                 # Logging, i18n, diagnostics, resource monitoring
└── tests/                 # Unit and integration suites
```

### Core Modules
| Module | Path | Responsibility |
| ------ | ---- | -------------- |
| Config Manager | `config/app_config.py` | Load defaults, validate schema, persist user overrides |
| Database Connection | `data/database/connection.py` | Thread-safe SQLite access, optional SQLCipher keying, schema tooling |
| Database Models | `data/database/models.py` | CRUD helpers for transcription tasks, calendar events, attachments, sync status |
| Security Toolkit | `data/security/` | AES-GCM encryption, OAuth token vault, secrets management |
| Transcription Manager | `core/transcription/manager.py` | Queue orchestration, engine coordination, export handling |
| Realtime Recorder | `core/realtime/recorder.py` | Microphone capture, streaming transcription, translation dispatch |
| Calendar Manager | `core/calendar/manager.py` | Local event CRUD, sync scheduling, colour and account policies |
| Timeline Manager | `core/timeline/manager.py` | History queries, auto-task configuration, reminder hooks |

## Getting Started
The project targets Python 3.10 or newer.

```bash
# Clone the repository
git clone https://github.com/johnnyzhao5619/echonote.git
cd EchoNote

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# or
.venv\Scripts\activate    # Windows

# Install dependencies
pip install -r requirements.txt

# Launch the desktop application
python main.py
```

### Configuration Notes
- Default values ship in `config/default_config.json`; user overrides are written to `~/.echonote/app_config.json`.
- Transcripts and recordings default to `~/Documents/EchoNote/` and can be customised in the Settings panel.
- OAuth credentials for calendar providers must be supplied before synchronisation; see `docs/user-guide/` for guidance.

## Testing
Run the suites that match your change scope:

```bash
pytest tests/unit
pytest tests/integration
```

Additional end-to-end and performance scenarios live alongside sample fixtures in `tests/`.

## Documentation
Curated manuals live under `docs/`:
- User guides: `docs/user-guide/`
- Quick start: `docs/quick-start/`
- Project overview: `docs/project-overview/`
- Developer and API references: `docs/DEVELOPER_GUIDE.md`, `docs/API_REFERENCE.md`

## License
This project is licensed under the [MIT License](LICENSE).
