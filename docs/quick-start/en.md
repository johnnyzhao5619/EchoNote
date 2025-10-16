# EchoNote Quick Start

This handbook gets you from first launch to your first transcription in five minutes.

## 1. First Launch (≈2 minutes)
1. Double-click the EchoNote icon to open the app.
2. Follow the setup wizard:
   - Select your interface language (Chinese, English, or French).
   - Choose a theme (Light, Dark, or Follow system).
   - Download the recommended `base` model (~145 MB) by clicking **Download Now**.
3. Wait for initialization to finish (5–10 seconds on the first launch).

## 2. First Transcription (≈3 minutes)
1. Import an audio/video file:
   ```text
   Batch Transcribe → Import File → choose media file
   ```
2. Once queued, press **Start** or let EchoNote auto-run the job.
3. When complete, select **View** or **Export** to produce TXT, SRT, or Markdown outputs.

## Quick Reference
### Batch Transcription
```text
Batch Transcribe → Import File/Folder → Pick model → Wait → View/Export
```

### Real-time Recording
```text
Real-time Record → Select microphone → Pick model → Start → Stop → Export text
```

### Connect Google Calendar
```text
Settings → Calendar → Add Google Account → Authorize in browser → Events sync automatically
```

### Download Additional Models
```text
Settings → Model Management → Available Models → Download → Wait for completion
```

## Recommended Settings
- **Daily use**: model `base`, concurrency 2, device Auto.
- **High quality**: model `medium`/`large`, concurrency 1, device CUDA (if available), compute type `float16`.
- **Fast turnaround**: model `tiny`, concurrency 3–5, compute type `int8`.

## Rapid Troubleshooting
- **Transcription failed**: verify file format, ensure model downloaded, check disk space → Settings → Model Management → Verify model.
- **Slow transcription**: Settings → Transcription Settings → choose a smaller model.
- **Cannot record**: confirm microphone connection, OS permissions, and audio input selection.
- **Calendar not syncing**: Settings → Calendar → Remove account → Re-add.

## Keyboard Shortcuts
| Feature          | Shortcut       |
| ---------------- | -------------- |
| Batch Transcribe | Ctrl+1 (⌘+1)   |
| Real-time Record | Ctrl+2 (⌘+2)   |
| Calendar Hub     | Ctrl+3 (⌘+3)   |
| Timeline         | Ctrl+4 (⌘+4)   |
| Settings         | Ctrl+, (⌘+,)   |

## Data Locations
```text
Database: ~/.echonote/data.db
Recordings: ~/Documents/EchoNote/Recordings/
Transcripts: ~/Documents/EchoNote/Transcripts/
Logs: ~/.echonote/logs/echonote.log
```

See `../user-guide/en.md` for full details.
