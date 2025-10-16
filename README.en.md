# EchoNote

A local-first desktop assistant that unifies transcription, calendar intelligence, and timeline automation.

## Project Snapshot
- **Framework**: PyQt6 application bootstrapped through `main.py`
- **Business Domains**: batch/real-time transcription, calendar sync, timeline planning
- **Operational Principles**: privacy by default, encrypted persistence, proactive resource checks

### Feature Highlights
1. **Batch Transcription** – `core/transcription` with Faster-Whisper engines handles audio/video queues, lazy model loading, and resumable jobs.
2. **Real-time Recording** – `core/realtime` combines `engines/audio` capture, gain control, VAD, and optional translation.
3. **Calendar Hub** – `core/calendar` stores local events while `engines/calendar_sync` connects Google and Outlook accounts.
4. **Timeline Automation** – `core/timeline` links events with recordings, manages auto-tasks, and powers timeline queries.
5. **Security & Configuration** – `config/app_config.py` plus `data/security` enforce validation, encryption, and secret management.
6. **System Health** – `utils/resource_monitor` and `utils/ffmpeg_checker` guard against memory pressure and missing dependencies.

### Repository Layout
```
EchoNote/
├── main.py                # Application bootstrap & dependency wiring
├── core/                  # Domain managers (calendar, realtime, timeline, transcription)
├── engines/               # Pluggable engines (audio, speech, translation, calendar_sync)
├── data/                  # Database models, storage, and security helpers
├── ui/                    # Qt widgets, dialogs, and navigation shell
├── utils/                 # Logging, i18n, resource monitoring, error handling
└── tests/                 # Unit, integration, and performance suites
```

## Environment Requirements
- Python 3.10 or newer
- Optional: PyAudio (microphone capture), FFmpeg (video formats), CUDA GPU (acceleration)
- First launch writes encrypted SQLite data, logs, and settings to `~/.echonote`

## Run from Source
```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

Default configuration values ship with `config/default_config.json`. User overrides are persisted in `~/.echonote/app_config.json`.

## Quality & Testing
- `pytest tests/unit` – unit coverage for managers and utilities
- `pytest tests/integration` – integration checks for database, engines, and schedulers (requires local dependencies)
- `pytest tests/e2e_performance_test.py` – optional regression baseline for transcription throughput

Install development extras via `pip install -r requirements-dev.txt` and prepare microphone/calendar credentials before executing integration scenarios.

## Documentation
- User Handbook: `docs/user-guide/en.md`
- Quick Start: `docs/quick-start/en.md`
- Project Overview: `docs/project-overview/README.md`
- Developer resources: `docs/DEVELOPER_GUIDE.md`, `docs/API_REFERENCE.md`

`docs/README.md` collects every manual and reference.

## License
Released under the [MIT License](LICENSE).
