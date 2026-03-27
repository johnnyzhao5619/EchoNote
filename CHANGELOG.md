# Changelog

All notable changes to EchoNote will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

> **Note:** EchoNote v3.0.0 is a complete rewrite in Tauri + Rust.
> For v2.x (Python + PySide6) history, see the `main` branch.

## [Unreleased]

### Changed
- Recording UI now treats `get_audio_level`, `get_realtime_segments`, and `get_recording_status` as the canonical realtime update path.
- `audio:level` and `transcription:*` remain best-effort compatibility/debug events instead of the sole source of truth for the recording page.
- LLM task cancellation no longer depends on worker FIFO order; queued tasks can be cancelled before generation starts.
- `llm:error` now carries structured `kind: "failed" | "cancelled"` metadata instead of requiring frontend string matching.
- Summary, meeting brief, and translation tasks now use structured JSON output contracts with Rust-side validation/rendering to suppress repetition and format drift.
- Disabled native llama.cpp grammar constrained decoding for structured tasks on the shipped Qwen2.5-3B model because it can abort inside `llama-grammar.cpp`; structured tasks now fail gracefully through Rust-side JSON validation instead of crashing the app.
- Workspace now uses an authoring-first document flow: new notes open directly into editable `document_text`, imported files open into the editor, the left sidebar behaves as a real tree navigator, and document detail is unified around editable assets instead of read-only tabs.
- Batch transcription now normalizes imported WAV audio to Whisper's required 16kHz mono format before inference, matching the realtime audio pipeline.
- Batch transcription file intake now uses Tauri native drag-drop window events instead of browser `File.path`, and surfaces user-visible validation errors for unsupported drops.
- Specta command generation is now centralized in `src-tauri/src/bindings.rs` with a dedicated `export_bindings` binary so `src/lib/bindings.ts` stays in sync with Rust IPC additions.

## [3.0.0] - TBD

### Added
- Complete rewrite in Tauri 2.x + Rust backend + React 18 frontend
- Real-time audio recording with cpal + rubato resampling (any Hz → 16000Hz)
- Streaming transcription via whisper-rs (whisper.cpp) with CoreML/Metal/CUDA
- Local LLM inference via llama-cpp-2 (llama.cpp) with streaming token output
- AI tasks: summary, meeting brief (structured parsing), translation, Q&A
- Workspace document library with FTS5 full-text search and multi-format export
- Batch transcription queue with ffmpeg media format support
- Local timeline (no OAuth, pure local event management)
- VSCode-style theme customization with JSON token editor
- Three built-in themes: Tokyo Night, Tokyo Night Storm, Tokyo Night Light
- Internationalization: zh_CN, en_US, fr_FR
- Model download manager with progress tracking and SHA256 verification
- Cross-platform builds: macOS Universal Binary, Windows MSI, Linux AppImage/deb

### Removed
- Python + PySide6 codebase (see `main` branch for v2.x)
- Google Calendar OAuth sync (deferred to future release)
- Cloud speech engines (Azure, Google, OpenAI)
- ONNX translation engine
