# EchoNote User Guide

This guide covers the day-to-day workflows, UI navigation, and troubleshooting tips for the EchoNote desktop application.

## 1. Feature Overview
- **Batch Transcription**: Supports MP3/WAV/FLAC/MP4. Queue concurrency is configurable under Settings.
- **Real-time Recording**: Microphone capture with gain control, voice activity detection, live transcription, and optional translation.
- **Calendar Hub**: Local event CRUD, Google/Outlook synchronization, reminders, and account health monitoring.
- **Timeline View**: Explore past and upcoming events, inspect recordings/transcripts, and configure auto-tasks.
- **Settings**: Manage themes, languages, model catalog, storage paths, and security secrets.

## 2. First-time Setup <a id="first-time-setup"></a>
<a id="first-launch"></a>
### 2.1 First Launch Checklist
1. Launch the app and follow the wizard to select your interface language, preferred theme, and download a speech model.
2. EchoNote performs dependency checks (FFmpeg, PyAudio) and shows guidance if anything is missing.
3. Wait for initialization to finish (5–10 seconds on the first launch) before exploring other modules.

<a id="first-transcription"></a>
### 2.2 Queue Your First Transcription
1. Open **Batch Transcribe** and import an audio/video file or folder.
2. Confirm the chosen model and optional translation language, then start the queue or let auto-run kick in.
3. When the task completes, view or export results as TXT, SRT, or Markdown.

Configuration is stored at `~/.echonote/app_config.json`, and logs live in `~/.echonote/logs/`.

## 3. Feature Deep Dive
### 3.1 Batch Transcription <a id="workflow-batch"></a>
- Navigate to **Batch Transcribe** and import files or folders.
- Set per-task model, output format, and translation language as needed.
- The queue supports pause/resume/cancel/retry, and history is searchable inside the same view.

> **Quick path:** `Batch Transcribe → Import File/Folder → Pick model → Start → View/Export`

### 3.2 Real-time Recording <a id="workflow-realtime"></a>
- Choose the input device and gain level; enable VAD to filter silence.
- Monitor live transcripts, add markers, and track elapsed time.
- When stopping, recordings and transcripts are saved to `~/Documents/EchoNote/` directories.

> **Quick path:** `Real-time Record → Select microphone → Pick model → Start → Stop → Export`

### 3.3 Calendar Hub <a id="workflow-calendar"></a>
- Add Google/Outlook OAuth credentials inside Settings to enable sync.
- Create, edit, and delete events with reminders and recurrence rules.
- Sync status is persisted in the `calendar_sync_status` table and surfaced in the UI.

### 3.4 Timeline
- Jump across periods using date pickers; pagination and keyword search are available.
- Past events display linked recordings, transcripts, and notes for download or preview.
- Future events allow auto-tasks: auto-record, auto-transcribe, preset languages, and translation targets.

### 3.5 Settings Panel <a id="workflow-models"></a>
- **General**: theme, language, shortcuts.
- **Transcription**: default model, concurrency, output formats, translation target.
- **Model Management**: download/verify models, inspect disk usage.
- **Calendar**: external accounts, sync cadence, conflict policies.
- **Security**: database encryption, key rotation, OAuth secrets.

> **Quick path:** `Settings → Model Management → Available Models → Download`

## 4. Recommended Settings <a id="recommended-settings"></a>
- **Daily use**: model `base`, concurrency 2, device Auto.
- **High quality**: model `medium`/`large`, concurrency 1, device CUDA (if available), compute type `float16`.
- **Fast turnaround**: model `tiny`, concurrency 3–5, compute type `int8`.

## 5. Troubleshooting Matrix <a id="troubleshooting"></a>
| Symptom | Quick Check | Resolution |
| ------- | ----------- | ---------- |
| Cannot import file | Path accessible? Format supported? | Convert to a supported format or adjust permissions |
| Model validation failed | Model fully downloaded? | Click **Redownload** in Model Management |
| Slow transcription | CPU/GPU saturated? Resource monitor warning? | Switch to a smaller model and review `utils/resource_monitor` alerts |
| Calendar conflicts | Any sync errors in logs? | Re-authorize account or inspect `calendar_sync_status` entries |

- **Transcription failed**: verify file format, ensure the model is downloaded, and confirm sufficient disk space via **Settings → Model Management → Verify model**.
- **Cannot record**: confirm microphone connection, OS permissions, and audio input selection.
- **Calendar not syncing**: remove the account under **Settings → Calendar** and add it again after resolving OAuth prompts.

## 6. Productivity Tips
- Use keyboard shortcuts (see [Keyboard Shortcuts](#keyboard-shortcuts)) to switch modules rapidly.
- Configure recurring auto-record policies in `core/timeline/auto_task_scheduler.py` to prepare meetings ahead of time.
- Enable the notification center to receive low-resource and completion alerts.
- Validate hardware setups with the sample assets bundled under `tests/`.

## 7. Keyboard Shortcuts <a id="keyboard-shortcuts"></a>
| Feature          | Shortcut       |
| ---------------- | -------------- |
| Batch Transcribe | Ctrl+1 (⌘+1)   |
| Real-time Record | Ctrl+2 (⌘+2)   |
| Calendar Hub     | Ctrl+3 (⌘+3)   |
| Timeline         | Ctrl+4 (⌘+4)   |
| Settings         | Ctrl+, (⌘+,)   |

## 8. Data Locations <a id="data-locations"></a>
```text
Database: ~/.echonote/data.db
Recordings: ~/Documents/EchoNote/Recordings/
Transcripts: ~/Documents/EchoNote/Transcripts/
Logs: ~/.echonote/logs/echonote.log
```

## 9. Getting Support <a id="support"></a>
- Review `~/.echonote/logs/echonote.log` for stack traces and diagnostics.
- Read `../project-overview/README.md` for architectural context and data flow diagrams.
- When filing issues, include OS, Python version, model choice, and whether FFmpeg/PyAudio are installed.

Enjoy capturing and organizing your conversations!
