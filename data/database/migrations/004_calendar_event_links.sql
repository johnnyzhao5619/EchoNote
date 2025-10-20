-- Migration: Add calendar_event_links table for multi-provider sync
-- Version: 004
-- Description: Stores provider-specific external IDs for calendar events

-- ============================================================================
-- Create calendar_event_links table
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
-- Migrate existing external_id values into the new table
-- ============================================================================
INSERT OR IGNORE INTO calendar_event_links (
    event_id,
    provider,
    external_id,
    last_synced_at
)
SELECT
    id AS event_id,
    CASE
        WHEN source IS NOT NULL AND source != '' AND source != 'local' THEN source
        WHEN is_readonly = 1 AND source IS NOT NULL AND source != '' THEN source
        ELSE 'default'
    END AS provider,
    external_id,
    COALESCE(updated_at, CURRENT_TIMESTAMP) AS last_synced_at
FROM calendar_events
WHERE external_id IS NOT NULL
  AND TRIM(external_id) != '';

-- Clear migrated external IDs from calendar_events to avoid divergence
UPDATE calendar_events
SET external_id = NULL
WHERE external_id IS NOT NULL
  AND TRIM(external_id) != '';

-- ============================================================================
-- Update schema version
-- ============================================================================
UPDATE app_settings
SET
    value = '4',
    updated_at = CURRENT_TIMESTAMP
WHERE
    key = 'schema_version';
