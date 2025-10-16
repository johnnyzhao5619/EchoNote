---
inclusion: always
---

# Technology Stack

## Frontend

- **Framework**: PyQt (Qt for Python)
- **Layout**: Sidebar navigation + main content area
- **Design Reference**: Microsoft Teams / Slack style
- **Internationalization**: Support for Chinese, English, French

## Backend

- **Language**: Python
- **Architecture**: Modular, pluggable design

## Speech Recognition Engines

### Default (Local)

- **Primary**: faster-whisper
- **Reference Implementations**:
  - https://github.com/QuentinFuxa/WhisperLiveKit
  - https://github.com/SYSTRAN/faster-whisper

### Optional Extensions

- **Cloud Services**: OpenAI, Google, Azure (user-provided API keys)
- **Other Local Models**: Vosk, Coqui STT

## External Integrations

- **Calendar Services**: Google Calendar, Outlook Calendar (OAuth 2.0)
- **Audio Capture**: System audio loopback, physical microphone input

## Data Storage

- **Local Database**: For calendar events, transcription history, and settings
- **Security**: Encrypted storage for API keys and OAuth tokens

## Build & Distribution

### Packaging

- **Windows**: Standalone .exe
- **macOS**: Standalone .app
- **Code Signing**: Required for both platforms to avoid security warnings

### Common Commands

```bash
# Development setup
pip install -r requirements.txt

# Run application
python main.py

# Build for distribution
# (specific commands depend on packaging tool - PyInstaller, py2app, etc.)
```

## Architecture Principles

- **DRY**: Don't Repeat Yourself
- **Modularity**: Clear separation of concerns
- **Extensibility**: Plugin architecture for speech engines
- **Performance**: Non-blocking operations, efficient resource usage
- **Error Handling**: Graceful handling of unsupported formats and edge cases
