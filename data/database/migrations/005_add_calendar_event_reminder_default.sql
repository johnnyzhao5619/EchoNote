-- Migration: Add reminder_use_default column to calendar_events
-- Version: 005
-- Description: Persists whether calendar events use provider default reminders

-- ============================================================================
-- Add reminder_use_default column if it does not exist
-- ============================================================================
ALTER TABLE calendar_events
    ADD COLUMN reminder_use_default BOOLEAN;

-- Existing records will have NULL for reminder_use_default, representing
-- unknown/default behaviour prior to this migration.

-- ============================================================================
-- Update schema version
-- ============================================================================
UPDATE app_settings
SET
    value = '5',
    updated_at = CURRENT_TIMESTAMP
WHERE
    key = 'schema_version';
