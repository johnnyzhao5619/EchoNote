# Real-time Recording UI Components

## Overview

`ui/realtime_record/` now only contains the reusable floating overlay and audio visualization pieces for realtime capture.

- Primary recording entry: `ui/common/realtime_recording_dock.py`
- Shared full recording form: `ui/workspace/recording_session_panel.py`
- Floating overlay window: `ui/realtime_record/floating_overlay.py`
- Audio waveform component: `ui/realtime_record/audio_visualizer.py`

This directory no longer owns a standalone realtime-record page. The application shell keeps recording controls mounted persistently, and the workspace consumes the same session state.

## Components

### `RealtimeFloatingOverlay`

Always-on-top overlay for compact runtime visibility while recording continues in the shell dock.

Responsibilities:

- Show recording status and duration
- Preview transcript and translation snippets
- Offer quick actions to reopen the main window or toggle pin-on-top
- Reuse semantic theme roles from `ui/constants.py`

### `AudioVisualizer`

Reusable waveform/level visualization for realtime capture surfaces.

Responsibilities:

- Render live waveform updates
- Show audio level changes without owning recorder state
- Stay embeddable in future recording-related widgets

## Integration Notes

- `MainWindow` owns the persistent dock and refreshes it from the shared realtime recorder.
- `WorkspaceRecordingSessionPanel` is the single full-featured form for source selection, language options, markers, and live transcript/translation state.
- `RealtimeFloatingOverlay` is an auxiliary visibility surface, not a second recording workflow.

## Theme And I18n

- Theme selectors live in `resources/themes/light.qss`, `resources/themes/dark.qss`, and `resources/themes/theme_outline.json`.
- Translation keys stay under the `realtime_record` section in `resources/translations/*.json`.
- Shell dock text that belongs to the workspace/realtime workflow lives under `workspace.*`; the task utility window title uses `workspace.task_window_title`, and the full recording console section labels use `workspace.recording_console.section_*`.

## Maintenance Rules

- Do not reintroduce a second standalone realtime recording page here.
- If a new floating overlay role is added, update both QSS themes and `theme_outline.json` in the same change.
- If a new realtime-record or shared workspace recording key is added, update `i18n_outline.json` and all locales together.
