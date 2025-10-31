<h1 align="center">EchoNote</h1>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-Apache%202.0-2563EB.svg" alt="Apache 2.0 License badge"></a>
  <img src="https://img.shields.io/badge/Python-3.10%2B-4B5563.svg" alt="Python 3.10+ badge">
  <img src="https://img.shields.io/badge/Desktop-Local%20First-0EA5E9.svg" alt="Desktop local-first badge">
</p>

<p align="center">
  <strong>Local-first desktop application for intelligent voice transcription and calendar management</strong>
</p>

<p align="center">
  <a href="#english">English</a> •
  <a href="README.zh-CN.md">中文</a> •
  <a href="README.fr.md">Français</a>
</p>

> **📖 Language-specific READMEs**: For detailed documentation in your preferred language, see [README.zh-CN.md](README.zh-CN.md) (Chinese) or [README.fr.md](README.fr.md) (French).

---

## English

### 🚀 Quick Start

**EchoNote** is a privacy-first desktop application that provides intelligent voice transcription and calendar management with local processing capabilities.

#### Installation & Setup

```bash
# 1. Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Launch application
python main.py
```

#### First Launch Setup

1. **Storage Configuration**: Choose paths for recordings and transcripts
2. **Model Download**: Download a Faster-Whisper model (recommend `base` for most users)
3. **FFmpeg Check**: Verify FFmpeg installation for media format support
4. **Optional**: Configure calendar sync (Google/Outlook OAuth)

### 🎯 Key Features

- **🎙️ Batch & Real-time Transcription**: Process audio/video files or capture live recordings
- **📅 Calendar Integration**: Sync with Google Calendar and Outlook, manage local events
- **⏰ Timeline Intelligence**: Correlate events with recordings, automated task scheduling
- **🔒 Privacy-First**: Encrypted local storage, no cloud dependency required
- **🌍 Multi-language**: Built-in internationalization (English, Chinese, French)
- **🎨 Accessibility**: Keyboard navigation, screen reader support, multiple themes

### 📋 System Requirements

- **Python**: 3.10 or newer
- **Operating System**: macOS, Linux, Windows
- **Optional Dependencies**:
  - PyAudio (microphone capture)
  - FFmpeg (media format support)
  - CUDA GPU (Faster-Whisper acceleration)

### 🏗️ Architecture Overview

```
EchoNote/
├── main.py                # Application entry point
├── config/                # Configuration management & version control
├── core/                  # Business logic domains
├── engines/               # External service integrations
├── data/                  # Database, security, storage
├── ui/                    # PySide6 desktop interface
├── utils/                 # Cross-cutting utilities
└── tests/                 # Test suites
```

### 📚 Documentation

| Audience         | Resource           | Location                                                   |
| ---------------- | ------------------ | ---------------------------------------------------------- |
| **New Users**    | Quick start guide  | [`docs/quick-start/README.md`](docs/quick-start/README.md) |
| **End Users**    | User manual        | [`docs/user-guide/README.md`](docs/user-guide/README.md)   |
| **Developers**   | API reference      | [`docs/DEVELOPER_GUIDE.md`](docs/DEVELOPER_GUIDE.md)       |
| **Contributors** | Coding standards   | [`docs/CODE_STANDARDS.md`](docs/CODE_STANDARDS.md)         |
| **Maintainers**  | Version management | [`docs/VERSION_MANAGEMENT.md`](docs/VERSION_MANAGEMENT.md) |

### 🧪 Development & Testing

```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Run tests
pytest tests/unit                    # Unit tests
pytest tests/integration             # Integration tests
pytest tests/e2e_performance_test.py # Performance tests

# Code quality checks
python scripts/sync_version.py       # Version consistency
pre-commit run --all-files          # Code formatting & linting
```

### 📄 License

Released under the [Apache 2.0 License](LICENSE). PySide6 (LGPL v3) is used for the UI layer and is fully compatible through dynamic linking.

---

## 🌍 Other Languages

For comprehensive documentation in other languages:

- **中文 (Chinese)**: See [README.zh-CN.md](README.zh-CN.md) for detailed Chinese documentation
- **Français (French)**: See [README.fr.md](README.fr.md) for detailed French documentation

These language-specific READMEs include:

- Complete setup instructions
- Detailed feature descriptions
- Troubleshooting guides
- Configuration examples
- Development workflows

---

## 📊 Project Status

- **Version**: v1.2.0 (Latest maintenance release)
- **Test Coverage**: 607 tests, 100% pass rate
- **Code Quality**: Excellent (PEP 8 compliant, type-annotated)
- **Documentation**: Complete and restructured
- **License**: Apache 2.0 (fully compliant)

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](docs/CONTRIBUTING.md) for details on:

- Code standards and style guide
- Development workflow
- Testing requirements
- Documentation guidelines

## 📞 Support

- **Documentation**: [`docs/`](docs/) directory
- **Issues**: [GitHub Issues](https://github.com/your-org/echonote/issues)
- **Discussions**: [GitHub Discussions](https://github.com/your-org/echonote/discussions)

---

<p align="center">
  Made with ❤️ by the EchoNote team
</p>
