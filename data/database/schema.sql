-- EchoNote Database Schema
-- Version: 1.0.0

-- Enable foreign key constraints
PRAGMA foreign_keys = ON;

-- ============================================================================
-- Transcription Tasks Table
-- ============================================================================
CREATE TABLE IF NOT EXISTS transcription_tasks (
    id TEXT PRIMARY KEY, -- UUID
    file_path TEXT NOT NULL,
    file_name TEXT NOT NULL,
    file_size INTEGER,
    audio_duration REAL, -- Duration in seconds
    status TEXT NOT NULL, -- pending/processing/completed/failed
    progress REAL DEFAULT 0, -- Progress 0-100
    language TEXT,
    engine TEXT NOT NULL,
    output_format TEXT, -- txt/srt/md
    output_path TEXT,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_tasks_status ON transcription_tasks (status);

CREATE INDEX IF NOT EXISTS idx_tasks_created ON transcription_tasks (created_at);

-- ============================================================================
-- Calendar Events Table
-- ============================================================================
CREATE TABLE IF NOT EXISTS calendar_events (
    id TEXT PRIMARY KEY, -- UUID
    title TEXT NOT NULL,
    event_type TEXT NOT NULL, -- Event/Task/Appointment
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP NOT NULL,
    location TEXT,
    attendees TEXT, -- JSON array
    description TEXT,
    reminder_minutes INTEGER,
    reminder_use_default BOOLEAN,
    recurrence_rule TEXT, -- iCalendar RRULE format
    source TEXT NOT NULL DEFAULT 'local', -- local/google/outlook
    external_id TEXT, -- External calendar event ID
    is_readonly BOOLEAN DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_events_time ON calendar_events (start_time, end_time);

CREATE INDEX IF NOT EXISTS idx_events_source ON calendar_events (source);

CREATE INDEX IF NOT EXISTS idx_events_external_id ON calendar_events (external_id);

-- ============================================================================
-- Calendar Event Links Table
-- ============================================================================
CREATE TABLE IF NOT EXISTS calendar_event_links (
    event_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    external_id TEXT NOT NULL,
    last_synced_at TIMESTAMP,
    PRIMARY KEY (provider, external_id),
    UNIQUE (event_id, provider),
    FOREIGN KEY (event_id) REFERENCES calendar_events (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_event_links_event ON calendar_event_links (event_id);

-- ============================================================================
-- Event Attachments Table
-- ============================================================================
CREATE TABLE IF NOT EXISTS event_attachments (
    id TEXT PRIMARY KEY,
    event_id TEXT NOT NULL,
    attachment_type TEXT NOT NULL, -- recording/transcript
    file_path TEXT NOT NULL,
    file_size INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (event_id) REFERENCES calendar_events (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_attachments_event ON event_attachments (event_id);

-- ============================================================================
-- Workspace Items Table
-- ============================================================================
CREATE TABLE IF NOT EXISTS workspace_items (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    item_type TEXT NOT NULL, -- recording/document/meeting_note/summary
    source_kind TEXT, -- batch_transcription/realtime_recording/manual_import/ai_generated
    source_event_id TEXT,
    source_task_id TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    primary_text_asset_id TEXT,
    primary_audio_asset_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (source_event_id) REFERENCES calendar_events (id) ON DELETE SET NULL,
    FOREIGN KEY (source_task_id) REFERENCES transcription_tasks (id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_workspace_items_type ON workspace_items (item_type);
CREATE INDEX IF NOT EXISTS idx_workspace_items_source_event ON workspace_items (source_event_id);
CREATE INDEX IF NOT EXISTS idx_workspace_items_source_task ON workspace_items (source_task_id);
CREATE INDEX IF NOT EXISTS idx_workspace_items_updated_at ON workspace_items (updated_at);

-- ============================================================================
-- Workspace Assets Table
-- ============================================================================
CREATE TABLE IF NOT EXISTS workspace_assets (
    id TEXT PRIMARY KEY,
    item_id TEXT NOT NULL,
    asset_role TEXT NOT NULL, -- audio/transcript/translation/summary/meeting_brief/etc.
    file_path TEXT,
    content_type TEXT,
    text_content TEXT,
    metadata_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (item_id) REFERENCES workspace_items (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_workspace_assets_item_id ON workspace_assets (item_id);
CREATE INDEX IF NOT EXISTS idx_workspace_assets_role ON workspace_assets (asset_role);
CREATE INDEX IF NOT EXISTS idx_workspace_assets_item_role ON workspace_assets (item_id, asset_role);

-- ============================================================================
-- Auto Task Configurations Table
-- ============================================================================
CREATE TABLE IF NOT EXISTS auto_task_configs (
    id TEXT PRIMARY KEY,
    event_id TEXT NOT NULL,
    enable_transcription BOOLEAN DEFAULT 0,
    enable_recording BOOLEAN DEFAULT 0,
    transcription_language TEXT,
    enable_translation BOOLEAN DEFAULT 0,
    translation_target_language TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (event_id) REFERENCES calendar_events (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_auto_tasks_event ON auto_task_configs (event_id);

-- ============================================================================
-- Calendar Sync Status Table
-- ============================================================================
CREATE TABLE IF NOT EXISTS calendar_sync_status (
    id TEXT PRIMARY KEY,
    provider TEXT NOT NULL, -- google/outlook
    user_email TEXT,
    last_sync_time TIMESTAMP,
    sync_token TEXT, -- Incremental sync token
    is_active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_sync_provider ON calendar_sync_status (provider);

-- ============================================================================
-- Application Settings Table
-- ============================================================================
CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- API Usage Statistics Table
-- ============================================================================
CREATE TABLE IF NOT EXISTS api_usage (
    id TEXT PRIMARY KEY,
    engine TEXT NOT NULL, -- openai/google/azure
    duration_seconds REAL NOT NULL,
    cost REAL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_usage_engine_time ON api_usage (engine, timestamp);

-- ============================================================================
-- Model Usage Statistics Table
-- ============================================================================
CREATE TABLE IF NOT EXISTS model_usage_stats (
    id TEXT PRIMARY KEY,
    model_name TEXT NOT NULL,
    usage_count INTEGER DEFAULT 0,
    last_used TIMESTAMP,
    total_transcription_duration REAL DEFAULT 0, -- Total transcription duration in seconds
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_model_usage_name ON model_usage_stats (model_name);

-- ============================================================================
-- Translation Model Downloads Table
-- ============================================================================
CREATE TABLE IF NOT EXISTS translation_model_downloads (
    model_id       TEXT PRIMARY KEY,        -- e.g. "opus-mt-zh-en"
    source_lang    TEXT NOT NULL,           -- ISO 639-1 code, e.g. "zh"
    target_lang    TEXT NOT NULL,           -- ISO 639-1 code, e.g. "en"
    status         TEXT NOT NULL DEFAULT 'not_downloaded', -- not_downloaded/downloading/downloaded/failed
    download_path  TEXT,
    size_bytes     INTEGER,
    downloaded_at  TIMESTAMP,
    last_used      TIMESTAMP,
    use_count      INTEGER DEFAULT 0,
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_trans_model_status
    ON translation_model_downloads (status);

-- ============================================================================
-- Initial Data
-- ============================================================================

-- Set initial schema version
INSERT
    OR IGNORE INTO app_settings (key, value, updated_at)
VALUES (
        'schema_version',
        '3',
        CURRENT_TIMESTAMP
    );

-- Set database creation timestamp
INSERT
    OR IGNORE INTO app_settings (key, value, updated_at)
VALUES (
        'created_at',
        datetime('now'),
        CURRENT_TIMESTAMP
    );
