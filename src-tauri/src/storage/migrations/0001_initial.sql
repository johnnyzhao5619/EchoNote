-- recordings: audio file metadata
CREATE TABLE recordings (
    id          TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    file_path   TEXT NOT NULL,
    duration_ms INTEGER NOT NULL DEFAULT 0,
    language    TEXT,
    created_at  INTEGER NOT NULL,
    updated_at  INTEGER NOT NULL
);

-- transcription_segments: word/sentence segments from whisper
CREATE TABLE transcription_segments (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    recording_id TEXT NOT NULL REFERENCES recordings(id) ON DELETE CASCADE,
    start_ms     INTEGER NOT NULL,
    end_ms       INTEGER NOT NULL,
    text         TEXT NOT NULL,
    language     TEXT,
    confidence   REAL
);
CREATE INDEX idx_segments_recording ON transcription_segments(recording_id);

-- workspace_folders: hierarchical folder tree
CREATE TABLE workspace_folders (
    id          TEXT PRIMARY KEY,
    parent_id   TEXT REFERENCES workspace_folders(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    folder_kind TEXT NOT NULL DEFAULT 'user',  -- 'user' | 'inbox' | 'system_root' | 'event' | 'batch_task'
    is_system   INTEGER NOT NULL DEFAULT 0,     -- 1 = cannot rename/delete/move
    created_at  INTEGER NOT NULL
);

-- workspace_documents: document records (transcripts, imports, notes)
CREATE TABLE workspace_documents (
    id           TEXT PRIMARY KEY,
    folder_id    TEXT REFERENCES workspace_folders(id) ON DELETE SET NULL,
    title        TEXT NOT NULL,
    file_path    TEXT,
    content_text TEXT,                          -- maintained by trigger; do NOT write directly
    source_type  TEXT NOT NULL,                 -- 'recording' | 'import' | 'manual' | 'batch_task'
    recording_id TEXT REFERENCES recordings(id) ON DELETE SET NULL,
    created_at   INTEGER NOT NULL,
    updated_at   INTEGER NOT NULL
);

-- workspace_fts: full-text search virtual table over workspace_documents
CREATE VIRTUAL TABLE workspace_fts USING fts5(
    title,
    content_text,
    content=workspace_documents,
    content_rowid=rowid
);

-- workspace_text_assets: versioned text content per document per role
CREATE TABLE workspace_text_assets (
    id          TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES workspace_documents(id) ON DELETE CASCADE,
    role        TEXT NOT NULL,   -- 'document_text'|'transcript'|'meeting_brief'|'summary'|
                                 -- 'translation'|'decisions'|'action_items'|'next_steps'
    content     TEXT NOT NULL,
    file_path   TEXT,            -- optional disk path of the corresponding .md file
    created_at  INTEGER NOT NULL,
    updated_at  INTEGER NOT NULL,
    UNIQUE(document_id, role)    -- one record per role per document
);
CREATE INDEX idx_assets_document ON workspace_text_assets(document_id, role);

-- Trigger: after INSERT on workspace_text_assets, sync content_text on parent document
CREATE TRIGGER sync_content_text_on_asset_insert
AFTER INSERT ON workspace_text_assets
BEGIN
    UPDATE workspace_documents
    SET content_text = (
        SELECT content FROM workspace_text_assets
        WHERE document_id = NEW.document_id
        ORDER BY CASE role
            WHEN 'document_text' THEN 0
            WHEN 'transcript'    THEN 1
            WHEN 'meeting_brief' THEN 2
            WHEN 'summary'       THEN 3
            WHEN 'translation'   THEN 4
            WHEN 'decisions'     THEN 5
            WHEN 'action_items'  THEN 6
            WHEN 'next_steps'    THEN 7
            ELSE 99 END
        LIMIT 1
    )
    WHERE id = NEW.document_id;
END;

-- Trigger: after UPDATE on workspace_text_assets, sync content_text on parent document
CREATE TRIGGER sync_content_text_on_asset_update
AFTER UPDATE ON workspace_text_assets
BEGIN
    UPDATE workspace_documents
    SET content_text = (
        SELECT content FROM workspace_text_assets
        WHERE document_id = NEW.document_id
        ORDER BY CASE role
            WHEN 'document_text' THEN 0
            WHEN 'transcript'    THEN 1
            WHEN 'meeting_brief' THEN 2
            WHEN 'summary'       THEN 3
            WHEN 'translation'   THEN 4
            WHEN 'decisions'     THEN 5
            WHEN 'action_items'  THEN 6
            WHEN 'next_steps'    THEN 7
            ELSE 99 END
        LIMIT 1
    )
    WHERE id = NEW.document_id;
END;

-- timeline_events: local calendar events (no OAuth)
CREATE TABLE timeline_events (
    id           TEXT PRIMARY KEY,
    title        TEXT NOT NULL,
    start_at     INTEGER NOT NULL,
    end_at       INTEGER NOT NULL,
    description  TEXT,
    tags         TEXT,                          -- JSON array of strings
    recording_id TEXT REFERENCES recordings(id) ON DELETE SET NULL,
    document_id  TEXT REFERENCES workspace_documents(id) ON DELETE SET NULL,
    created_at   INTEGER NOT NULL
);

-- model_registry: tracks downloaded AI model files
CREATE TABLE model_registry (
    model_id      TEXT PRIMARY KEY,             -- e.g. 'whisper/base' | 'llm/qwen2.5-7b-q4'
    file_path     TEXT NOT NULL,
    sha256        TEXT NOT NULL,
    size_bytes    INTEGER NOT NULL,
    downloaded_at INTEGER NOT NULL
);

-- app_settings: key-value store for application configuration
CREATE TABLE app_settings (
    key        TEXT PRIMARY KEY,
    value      TEXT NOT NULL,                   -- JSON-serialized value
    updated_at INTEGER NOT NULL
);
