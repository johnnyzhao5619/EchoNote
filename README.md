<div align="center">
  <img src="resources/icons/echonote.png" alt="EchoNote Logo" width="120" height="120">
  <h1>EchoNote</h1>
  <p><em>Local-First AI Voice Notes — Tauri + Rust + React</em></p>
</div>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-Apache%202.0-2563EB.svg" alt="Apache 2.0 License"></a>
  <img src="https://img.shields.io/badge/Version-3.0.0--dev-7aa2f7.svg" alt="v3.0.0-dev">
  <img src="https://img.shields.io/badge/Desktop-Local%20First-0EA5E9.svg" alt="Local First">
  <img src="https://img.shields.io/badge/Privacy-First-10B981.svg" alt="Privacy First">
</p>

> **v3 is under active development** (Tauri + Rust rewrite).
> For the stable v2.x release (Python + PySide6), see the [`main`](../../tree/main) branch.

---

## What is EchoNote?

EchoNote is a privacy-first, local-only desktop application that:

- **Records** audio from any microphone
- **Transcribes** speech in real time using on-device Whisper models
- **Summarizes** and organizes transcripts using local LLM (no API keys, no cloud)
- **Manages** a document workspace with full-text search and export
- **Tracks** notes and events on a local timeline

Everything runs on your machine. No subscriptions. No data leaves your device.

---

## v3 Tech Stack

| Layer | Technology |
|-------|-----------|
| App framework | Tauri 2.x |
| Frontend | React 18 + TypeScript + Tailwind CSS + shadcn/ui |
| Transcription | whisper-rs (whisper.cpp) — CoreML / Metal / CUDA |
| Local LLM | llama-cpp-2 (llama.cpp) — Metal / CUDA / CPU |
| Audio | cpal + rubato (real-time resampling) |
| Database | SQLite via sqlx (WAL mode, FTS5) |

---

## Platform Support

| Platform | Status | Acceleration |
|----------|--------|-------------|
| macOS (Universal) | 🔄 In development | CoreML + Metal |
| Windows x64 | 🔄 In development | CUDA (optional) |
| Linux x64 | 🔄 In development | CUDA (optional) |

---

## Development

See [`AGENTS.md`](AGENTS.md) for the full architecture, design decisions, and
milestone-by-milestone execution guide (M1–M11).

Implementation plans are in [`docs/superpowers/plans/`](docs/superpowers/plans/).

---

## License

Apache 2.0 — see [LICENSE](LICENSE).
