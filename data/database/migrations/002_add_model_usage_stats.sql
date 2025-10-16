-- Migration: Add Model Usage Statistics Table
-- Version: 002
-- Description: Adds table for tracking Whisper model usage statistics

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

-- Update schema version
UPDATE app_settings
SET
    value = '2',
    updated_at = CURRENT_TIMESTAMP
WHERE
    key = 'schema_version';