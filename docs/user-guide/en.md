# EchoNote User Guide

This guide covers the day-to-day workflows, UI navigation, and troubleshooting tips for the EchoNote desktop application.

## 1. Feature Overview
- **Batch Transcription**: Supports MP3/WAV/FLAC/MP4. Queue concurrency is configurable under Settings.
- **Real-time Recording**: Microphone capture with gain control, voice activity detection, live transcription, and optional translation.
- **Calendar Hub**: Local event CRUD, Google/Outlook synchronization, reminders, and account health monitoring.
- **Timeline View**: Explore past and upcoming events, inspect recordings/transcripts, and configure auto-tasks.
- **Settings**: Manage themes, languages, model catalog, storage paths, and security secrets.

## 2. First-time Setup
1. Launch the app and follow the wizard to select language, theme, and download a speech model.
2. EchoNote performs dependency checks (FFmpeg, PyAudio) and shows guidance if missing.
3. Configuration is stored at `~/.echonote/app_config.json`, and logs live in `~/.echonote/logs/`.

## 3. Feature Deep Dive
### 3.1 Batch Transcription
- Navigate to **Batch Transcribe** and import files or folders.
- Set per-task model, output format, and translation language as needed.
- The queue supports pause/resume/cancel/retry, and history is searchable inside the same view.

### 3.2 Real-time Recording
- Choose the input device and gain level; enable VAD to filter silence.
- Monitor live transcripts, add markers, and track elapsed time.
- When stopping, recordings and transcripts are saved to `~/Documents/EchoNote/` directories.

### 3.3 Calendar Hub
- Add Google/Outlook OAuth credentials inside Settings to enable sync.
- Create, edit, and delete events with reminders and recurrence rules.
- Sync status is persisted in the `calendar_sync_status` table and surfaced in the UI.

### 3.4 Timeline
- Jump across periods using date pickers; pagination and keyword search are available.
- Past events display linked recordings, transcripts, and notes for download or preview.
- Future events allow auto-tasks: auto-record, auto-transcribe, preset languages, and translation targets.

### 3.5 Settings Panel
- **General**: theme, language, shortcuts.
- **Transcription**: default model, concurrency, output formats, translation target.
- **Model Management**: download/verify models, inspect disk usage.
- **Calendar**: external accounts, sync cadence, conflict policies.
- **Security**: database encryption, key rotation, OAuth secrets.

## 4. Troubleshooting Matrix
| Symptom | Quick Check | Resolution |
| ------- | ----------- | ---------- |
| Cannot import file | Path accessible? Format supported? | Convert to a supported format or adjust permissions |
| Model validation failed | Model fully downloaded? | Click **Redownload** in Model Management |
| Slow transcription | CPU/GPU saturated? Resource monitor warning? | Switch to a smaller model and review `utils/resource_monitor` alerts |
| Calendar conflicts | Any sync errors in logs? | Re-authorize account or inspect `calendar_sync_status` entries |

## 5. Productivity Tips
- Use keyboard shortcuts (see Quick Start) to switch modules rapidly.
- Configure recurring auto-record policies in `core/timeline/auto_task_scheduler.py` to prepare meetings ahead of time.
- Enable the notification center to receive low-resource and completion alerts.
- Validate hardware setups with the sample assets bundled under `tests/`.

## 6. Getting Support
- Review `~/.echonote/logs/echonote.log` for stack traces and diagnostics.
- Read `../project-overview/README.md` for architectural context and data flow diagrams.
- When filing issues, include OS, Python version, model choice, and whether FFmpeg/PyAudio are installed.

Enjoy capturing and organizing your conversations!
