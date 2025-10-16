# EchoNote

Local-first desktop assistant that unifies transcription, calendar intelligence, and a searchable timeline.

## Project Snapshot
- **Framework**: PyQt6 entry point in `main.py`
- **Core Domains**: batch/real-time transcription, calendar sync, task automation, settings management
- **Operating Principles**: privacy-first, encrypted persistence, proactive resource checks

## Feature Highlights
1. **Batch Transcription** – `core/transcription` coordinates Faster-Whisper engines, resumable queues, and export formatting.
2. **Real-time Recording** – `core/realtime` plus `engines/audio` provide capture, gain control, voice activity detection, and optional translation.
3. **Calendar Hub** – `core/calendar` stores local events while `engines/calendar_sync` integrates Google and Outlook accounts.
4. **Timeline Automation** – `core/timeline` links events with recordings, maintains auto-task rules, and exposes history queries.
5. **Secure Storage** – `data/database`, `data/security`, and `data/storage` deliver encrypted SQLite, token vaults, and file lifecycle helpers.
6. **System Health** – `utils/` centralises logging, diagnostics, resource monitoring, and FFmpeg checks.

## Repository Layout
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

## Environment Requirements
- Python 3.10 or newer
- Optional: PyAudio (microphone capture), FFmpeg (media formats), CUDA GPU (acceleration)
- First launch writes encrypted SQLite data, logs, and settings to `~/.echonote`

## Run from Source
```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

### Configuration Notes
- Defaults live in `config/default_config.json`; user overrides persist to `~/.echonote/app_config.json`.
- Recordings and transcripts are stored under `~/Documents/EchoNote/` by default.
- Provide OAuth credentials in the settings UI before enabling Google or Outlook sync.

## Quality & Testing
- `pytest tests/unit` – core logic and utilities
- `pytest tests/integration` – database, engines, and schedulers (requires local dependencies)
- Optional E2E and performance baselines reside in `tests/`

Install development extras with `pip install -r requirements-dev.txt` when running broader suites.

## Documentation
- User handbook: `docs/user-guide/en.md`
- Quick start: `docs/quick-start/en.md`
- Project overview: `docs/project-overview/README.md`
- Developer resources: `docs/DEVELOPER_GUIDE.md`, `docs/API_REFERENCE.md`

## License
Released under the [MIT License](LICENSE).
