-- FTS5 automatic maintenance triggers for workspace_documents content table mode.

CREATE TRIGGER fts_docs_insert
AFTER INSERT ON workspace_documents
BEGIN
    INSERT INTO workspace_fts(rowid, title, content_text)
    VALUES (NEW.rowid, NEW.title, NEW.content_text);
END;

CREATE TRIGGER fts_docs_update
AFTER UPDATE ON workspace_documents
BEGIN
    INSERT INTO workspace_fts(workspace_fts, rowid, title, content_text)
    VALUES ('delete', OLD.rowid, OLD.title, OLD.content_text);
    INSERT INTO workspace_fts(rowid, title, content_text)
    VALUES (NEW.rowid, NEW.title, NEW.content_text);
END;

CREATE TRIGGER fts_docs_delete
AFTER DELETE ON workspace_documents
BEGIN
    INSERT INTO workspace_fts(workspace_fts, rowid, title, content_text)
    VALUES ('delete', OLD.rowid, OLD.title, OLD.content_text);
END;
