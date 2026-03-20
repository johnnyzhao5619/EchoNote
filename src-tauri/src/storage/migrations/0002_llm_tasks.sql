-- llm_tasks: tracks AI processing tasks per document
CREATE TABLE llm_tasks (
    id           TEXT PRIMARY KEY,
    document_id  TEXT REFERENCES workspace_documents(id) ON DELETE CASCADE,
    task_type    TEXT NOT NULL,                 -- 'summary' | 'translation' | 'meeting_brief' | 'qa'
    status       TEXT NOT NULL DEFAULT 'pending', -- 'pending' | 'running' | 'done' | 'error' | 'cancelled'
    result_text  TEXT,
    error_msg    TEXT,
    created_at   INTEGER NOT NULL,
    completed_at INTEGER
);
CREATE INDEX idx_llm_tasks_document ON llm_tasks(document_id, status);
