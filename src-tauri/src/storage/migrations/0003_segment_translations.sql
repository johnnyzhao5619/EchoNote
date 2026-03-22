-- 0003_segment_translations.sql
-- Per-segment translation storage for subtitle editing and export.

CREATE TABLE segment_translations (
    id          TEXT PRIMARY KEY,
    segment_id  INTEGER NOT NULL REFERENCES transcription_segments(id) ON DELETE CASCADE,
    language    TEXT NOT NULL,    -- language code: 'en' | 'ja' | 'ko' | 'fr' | 'de' | 'es' | 'ru'
    text        TEXT NOT NULL,
    created_at  INTEGER NOT NULL,
    UNIQUE(segment_id, language)  -- one translation per language per segment
);

CREATE INDEX idx_seg_translations ON segment_translations(segment_id, language);
