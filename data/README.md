# EchoNote Data Layer

This directory houses persistence, encryption, and storage helpers used across the application.

## Structure
```
data/
├── database/
│   ├── connection.py       # SQLite connection manager with optional SQLCipher
│   ├── models.py           # Dataclass-style models for tasks, events, attachments, sync state
│   ├── schema.sql          # Database schema definition
│   └── encryption_helper.py# Helpers to encrypt sensitive fields before persistence
├── security/
│   ├── encryption.py       # AES-GCM encryption utilities and key management
│   ├── oauth_manager.py    # OAuth token vault backed by encryption.py
│   └── secrets_manager.py  # Secure file-based secrets helper
├── storage/
│   └── file_manager.py     # Secure file operations for transcripts and recordings
├── test_data_layer.py      # Targeted tests covering database/security/file primitives
└── README.md               # This file
```

## Components

### Database Layer
- **`database/connection.py`**: creates per-thread SQLite connections, enables foreign keys, optionally applies a SQLCipher key, exposes helpers for transactions, backups, and schema bootstrapping.
- **`database/models.py`**: dataclass models providing CRUD helpers for transcription tasks, calendar events, attachments, auto-task configs, calendar sync status, and usage metrics. Sensitive fields (such as sync tokens) delegate to `encryption_helper.py`.
- **`database/schema.sql`**: authoritative schema with indexes and initial seed values (schema version, creation timestamp).

### Security Layer
- **`security/encryption.py`**: wraps AES-256-GCM with PBKDF2-based key derivation, salt handling, and dictionary helpers.
- **`security/oauth_manager.py`**: encrypted storage for provider tokens, expiration tracking, and rotation utilities.
- **`security/secrets_manager.py`**: central place for reading/writing sensitive configuration files with strict permissions.

### Storage Layer
- **`storage/file_manager.py`**: manages directory creation, secure file permissions, temp file cleanup, and helpers to save/read/delete audio and transcript assets under `~/Documents/EchoNote/`.

### Tests
- **`test_data_layer.py`**: quick checks for encryption, OAuth storage, and file manager behaviour. Run with `pytest data/test_data_layer.py` when changing persistence primitives.

## Usage Tips
- Call `DatabaseConnection.initialize_schema()` once at startup to ensure the schema exists.
- Use the dataclass models for CRUD operations to keep SQL consistent.
- Always rely on `secrets_manager` or `oauth_manager` when dealing with credentials—avoid writing plaintext secrets manually.
- Prefer `FileManager` for all filesystem operations so permissions remain locked down (files: `0o600`, directories: `0o700`).

## Related Modules
- Runtime configuration defaults live in `config/default_config.json`.
- Calendar and transcription managers coordinate with the data layer through dependency injection in `main.py`.
