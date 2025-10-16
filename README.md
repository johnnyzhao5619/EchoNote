# EchoNote

> Intelligent transcription, calendar orchestration, and timeline insights for desktop knowledge workers.

## 🌐 Language Navigation
- [中文说明 / Chinese Guide](README.zh-CN.md)
- [English Guide](README.en.md)

## Overview
EchoNote is a PyQt6 desktop application that combines local-first speech transcription, calendar integration, and timeline automation. The codebase is structured around modular managers (`core/`), reusable engines (`engines/`), and a Qt-based interface (`ui/`). Fast initialization, background schedulers, and defensive error handling are built directly into `main.py`.

### Key Capabilities
- Batch transcription for audio and video assets using Faster-Whisper models with lazy-loading to preserve memory.
- Real-time recording, optional streaming translation, and voice activity detection powered by `engines/audio` and `core/realtime`.
- Secure storage backed by an encrypted SQLite database, managed by `data/database` and `config/app_config.py`.
- Calendar hub with Google and Outlook synchronization plus automatic task orchestration (`core/calendar`, `core/timeline`).
- Resource monitoring, FFmpeg dependency checks, and centralized notification utilities to protect the user experience.

## Getting Started
The project runs from source on Python 3.10+.

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

Useful developer scripts and fixtures live under the `tests/` directory. Integration, end-to-end, and performance tests are available but may require PyAudio-compatible hardware and calendar credentials.

## Documentation Map
Comprehensive documentation in Chinese, English, and French lives inside the `docs/` directory:

- User Guides (`docs/user-guide/`)
- Quick Start handbooks (`docs/quick-start/`)
- Project Overview and architecture (`docs/project-overview/`)
- Developer and API references (`docs/DEVELOPER_GUIDE.md`, `docs/API_REFERENCE.md`)

Refer to `docs/README.md` for a curated index across all materials.

## Contributing
Contribution guidelines, code standards, accessibility notes, and governance files are located inside the `docs/` folder. Please follow the DRY principle, respect the modular architecture, and coordinate calendar engine credentials securely via the secrets manager.

## License
This project is licensed under the [MIT License](LICENSE).
