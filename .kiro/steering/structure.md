---
inclusion: always
---

# Project Structure

## Expected Organization

```
echonote/
├── main.py                    # Application entry point
├── requirements.txt           # Python dependencies
├── ui/                        # PyQt UI components
│   ├── main_window.py        # Main application window
│   ├── sidebar.py            # Navigation sidebar
│   ├── transcription/        # Batch transcription UI
│   ├── realtime/             # Real-time transcription UI
│   ├── calendar/             # Calendar hub UI
│   ├── timeline/             # Timeline view UI
│   └── settings/             # Settings UI
├── core/                      # Business logic
│   ├── transcription/        # Transcription engine management
│   ├── translation/          # Translation services
│   ├── calendar/             # Calendar sync logic
│   ├── audio/                # Audio capture and processing
│   └── storage/              # Local database operations
├── engines/                   # Speech recognition engines
│   ├── base.py               # Abstract engine interface
│   ├── faster_whisper.py     # Default local engine
│   ├── openai.py             # OpenAI API integration
│   └── ...                   # Other engine implementations
├── integrations/              # External service integrations
│   ├── google_calendar.py    # Google Calendar OAuth & sync
│   └── outlook_calendar.py   # Outlook Calendar OAuth & sync
├── utils/                     # Shared utilities
│   ├── i18n.py               # Internationalization
│   ├── security.py           # Encryption for sensitive data
│   └── notifications.py      # Desktop notifications
├── resources/                 # Static assets
│   ├── icons/
│   ├── themes/
│   └── translations/
└── tests/                     # Test suite
```

## Module Responsibilities

### UI Layer

- PyQt-based interface components
- Event handling and user interactions
- Theme and language switching

### Core Layer

- Business logic independent of UI
- Task queue management for batch transcription
- Calendar event CRUD operations
- Audio input source management

### Engines Layer

- Pluggable speech recognition implementations
- Common interface for all engines
- Engine-specific configuration

### Integrations Layer

- OAuth 2.0 flows for external services
- API communication with Google/Outlook
- Unidirectional sync (read external, optional push local)

### Utils Layer

- Cross-cutting concerns
- Reusable helper functions
- Security and encryption utilities

## Key Design Patterns

- **Strategy Pattern**: For pluggable speech engines
- **Observer Pattern**: For real-time transcription updates
- **Repository Pattern**: For data access abstraction
- **Factory Pattern**: For engine instantiation
