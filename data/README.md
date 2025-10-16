# EchoNote Data Layer

This directory contains the data layer implementation for EchoNote, including database management, security, and file storage.

## Structure

```
data/
├── database/
│   ├── connection.py          # Database connection management with SQLCipher support
│   ├── schema.sql             # Database schema definition
│   ├── models.py              # ORM-like data models
│   └── migrations/            # Database migration system
│       ├── __init__.py        # Migration manager
│       └── 001_initial_schema.sql
├── security/
│   ├── encryption.py          # AES-256-GCM encryption manager
│   └── oauth_manager.py       # OAuth token management
└── storage/
    └── file_manager.py        # File storage operations

```

## Components

### Database Layer

#### DatabaseConnection (`database/connection.py`)

- Thread-safe SQLite connection management
- Connection pooling with thread-local storage
- SQLCipher encryption support (optional)
- Context manager for cursor operations
- Schema initialization and versioning
- Database backup functionality

**Key Features:**

- Foreign key constraints enabled
- Row factory for dict-like access
- Transaction management with automatic rollback
- VACUUM support for optimization

#### Database Schema (`database/schema.sql`)

Tables:

- `transcription_tasks` - Batch transcription task tracking
- `calendar_events` - Local and synced calendar events
- `event_attachments` - Recording and transcript files
- `auto_task_configs` - Automatic task configurations
- `calendar_sync_status` - External calendar sync state
- `app_settings` - Application configuration
- `api_usage` - API usage statistics

#### Data Models (`database/models.py`)

ORM-like classes with CRUD operations:

- `TranscriptionTask` - Transcription task model
- `CalendarEvent` - Calendar event model
- `EventAttachment` - Event attachment model
- `AutoTaskConfig` - Auto task configuration model
- `CalendarSyncStatus` - Calendar sync status model
- `APIUsage` - API usage tracking model

**Features:**

- Dataclass-based models
- Automatic UUID generation
- Timestamp management
- JSON serialization for complex fields
- Static query methods (get_by_id, search, etc.)

#### Migration System (`database/migrations/`)

- Version-based migration management
- Automatic migration detection and application
- Migration file creation utility
- Safe rollback on errors

### Security Layer

#### SecurityManager (`security/encryption.py`)

- AES-256-GCM authenticated encryption
- Machine-specific key derivation using PBKDF2
- Salt management with secure storage
- Dictionary encryption/decryption
- Password hashing and verification

**Key Features:**

- 100,000 PBKDF2 iterations (OWASP recommended)
- 12-byte nonce for GCM mode
- Base64 encoding for safe storage
- Automatic salt generation and persistence
- Machine UUID-based key derivation

#### OAuthManager (`security/oauth_manager.py`)

- Encrypted OAuth token storage
- Token expiration detection
- Automatic token refresh support
- Multi-provider support (Google, Outlook, etc.)
- Secure token metadata access

**Features:**

- Encrypted storage using SecurityManager
- Token expiration buffer (5 minutes default)
- Provider-specific token management
- Non-sensitive token info retrieval
- Bulk token operations

### Storage Layer

#### FileManager (`storage/file_manager.py`)

- Secure file operations with proper permissions
- Organized directory structure
- Binary and text file support
- File operations (save, read, delete, move, copy)
- Temporary file management

**Key Features:**

- Owner-only permissions (0o600 for files, 0o700 for directories)
- Unique filename generation
- Pattern-based file listing
- Automatic directory creation
- Temporary file cleanup

**Directory Structure:**

```
~/Documents/EchoNote/
├── Recordings/     # Audio recordings
├── Transcripts/    # Transcription outputs
├── Exports/        # Exported files
└── Temp/           # Temporary files
```

## Usage Examples

### Database Connection

```python
from data.database.connection import DatabaseConnection

# Initialize connection
db = DatabaseConnection("~/.echonote/data.db", encryption_key="secret")

# Initialize schema
db.initialize_schema()

# Execute query
with db.get_cursor(commit=True) as cursor:
    cursor.execute("INSERT INTO ...")

# Close connection
db.close()
```

### Data Models

```python
from data.database.models import CalendarEvent

# Create event
event = CalendarEvent(
    title="Team Meeting",
    event_type="Event",
    start_time="2025-10-07T10:00:00",
    end_time="2025-10-07T11:00:00"
)

# Save to database
event.save(db)

# Query events
events = CalendarEvent.get_by_time_range(
    db,
    "2025-10-07T00:00:00",
    "2025-10-07T23:59:59"
)
```

### Security Manager

```python
from data.security.encryption import SecurityManager

# Initialize
security = SecurityManager()

# Encrypt data
encrypted = security.encrypt("sensitive data")

# Decrypt data
decrypted = security.decrypt(encrypted)

# Encrypt dictionary
encrypted_dict = security.encrypt_dict({
    "api_key": "sk-...",
    "token": "..."
})
```

### OAuth Manager

```python
from data.security.oauth_manager import OAuthManager

# Initialize
oauth = OAuthManager(security_manager)

# Store token
oauth.store_token(
    provider="google",
    access_token="ya29...",
    refresh_token="1//...",
    expires_in=3600
)

# Get token
token = oauth.get_access_token("google")

# Check expiration
if oauth.is_token_expired("google"):
    # Refresh token logic
    pass
```

### File Manager

```python
from data.storage.file_manager import FileManager

# Initialize
file_mgr = FileManager()

# Save file
path = file_mgr.save_text_file(
    content="Transcription text...",
    filename="transcript.txt",
    subdirectory="Transcripts"
)

# Read file
content = file_mgr.read_text_file(path)

# List files
files = file_mgr.list_files(
    subdirectory="Recordings",
    pattern="*.wav"
)
```

## Dependencies

Required Python packages:

- `cryptography` - For AES-256-GCM encryption
- `sqlite3` - Built-in SQLite support
- `pysqlcipher3` (optional) - For SQLCipher encryption

## Security Considerations

1. **Encryption Keys**: Derived from machine UUID + salt using PBKDF2
2. **File Permissions**: All files set to owner-only (0o600)
3. **OAuth Tokens**: Encrypted at rest using AES-256-GCM
4. **Database**: Optional SQLCipher encryption for entire database
5. **Salt Storage**: Securely stored with restricted permissions

## Testing

To test the data layer components:

```python
# Test database connection
from data.database.connection import DatabaseConnection
db = DatabaseConnection(":memory:")  # In-memory database for testing
db.initialize_schema()

# Test models
from data.database.models import TranscriptionTask
task = TranscriptionTask(file_path="/test.mp3", file_name="test.mp3")
task.save(db)

# Test security
from data.security.encryption import SecurityManager
security = SecurityManager()
encrypted = security.encrypt("test")
assert security.decrypt(encrypted) == "test"
```

## Migration Guide

To create a new migration:

```python
from data.database.migrations import MigrationManager

migration_mgr = MigrationManager(db)
migration_path = migration_mgr.create_migration("add_new_field")

# Edit the created SQL file, then apply:
migration_mgr.migrate()
```

## Notes

- All timestamps are stored in ISO 8601 format
- UUIDs are used for all primary keys
- JSON is used for complex fields (attendees, etc.)
- Foreign key constraints are enforced
- Indexes are created for common query patterns
