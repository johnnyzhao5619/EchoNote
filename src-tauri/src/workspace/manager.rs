use std::collections::HashMap;
use std::time::{SystemTime, UNIX_EPOCH};

use sqlx::SqlitePool;
use uuid::Uuid;

use crate::error::AppError;
use crate::workspace::document::{
    DocumentDetail, DocumentSummary, FolderNode, SearchResult, TextAsset, WorkspaceDocumentRow,
    WorkspaceFolder, WorkspaceTextAssetRow,
};

pub struct WorkspaceManager {
    pool: SqlitePool,
}

impl WorkspaceManager {
    pub fn new(pool: SqlitePool) -> Self {
        Self { pool }
    }

    pub async fn create_folder(
        &self,
        name: &str,
        parent_id: Option<&str>,
    ) -> Result<FolderNode, AppError> {
        validate_folder_name(name)?;
        self.check_duplicate_name(parent_id, name, None).await?;

        let id = Uuid::new_v4().to_string();
        let now = now_ms();

        sqlx::query(
            "INSERT INTO workspace_folders (id, parent_id, name, folder_kind, is_system, created_at)
             VALUES (?, ?, ?, 'user', 0, ?)",
        )
        .bind(&id)
        .bind(parent_id)
        .bind(name)
        .bind(now)
        .execute(&self.pool)
        .await?;

        Ok(FolderNode {
            id,
            name: name.to_string(),
            parent_id: parent_id.map(str::to_string),
            folder_kind: "user".to_string(),
            is_system: false,
            document_count: 0,
            children: vec![],
        })
    }

    pub async fn rename_folder(&self, id: &str, name: &str) -> Result<(), AppError> {
        let folder = self.get_folder_row(id).await?;
        if folder.is_system {
            return Err(AppError::Validation(
                "workspace.system_folder_immutable".to_string(),
            ));
        }

        validate_folder_name(name)?;
        self.check_duplicate_name(folder.parent_id.as_deref(), name, Some(id))
            .await?;

        sqlx::query("UPDATE workspace_folders SET name = ? WHERE id = ?")
            .bind(name)
            .bind(id)
            .execute(&self.pool)
            .await?;

        Ok(())
    }

    pub async fn delete_folder(&self, id: &str) -> Result<(), AppError> {
        let folder = self.get_folder_row(id).await?;
        if folder.is_system {
            return Err(AppError::Validation(
                "workspace.system_folder_immutable".to_string(),
            ));
        }

        let descendant_ids = self.collect_descendant_folder_ids(id).await?;
        let mut tx = self.pool.begin().await?;

        for folder_id in &descendant_ids {
            sqlx::query("DELETE FROM workspace_documents WHERE folder_id = ?")
                .bind(folder_id)
                .execute(&mut *tx)
                .await?;
        }

        sqlx::query("DELETE FROM workspace_documents WHERE folder_id = ?")
            .bind(id)
            .execute(&mut *tx)
            .await?;

        sqlx::query("DELETE FROM workspace_folders WHERE id = ?")
            .bind(id)
            .execute(&mut *tx)
            .await?;

        tx.commit().await?;
        Ok(())
    }

    pub async fn list_folders(&self) -> Result<Vec<FolderNode>, AppError> {
        let rows = sqlx::query_as::<_, WorkspaceFolder>(
            "SELECT id, parent_id, name, folder_kind, is_system, created_at
             FROM workspace_folders
             ORDER BY is_system DESC, name ASC",
        )
        .fetch_all(&self.pool)
        .await?;

        let counts: Vec<(Option<String>, i64)> = sqlx::query_as(
            "SELECT folder_id, COUNT(*) as count
             FROM workspace_documents
             GROUP BY folder_id",
        )
        .fetch_all(&self.pool)
        .await?;

        let count_map: HashMap<String, u32> = counts
            .into_iter()
            .filter_map(|(folder_id, count)| folder_id.map(|id| (id, count as u32)))
            .collect();

        build_folder_tree(&rows, &count_map, None)
    }

    pub async fn create_document(
        &self,
        title: &str,
        folder_id: Option<&str>,
        source_type: &str,
        recording_id: Option<&str>,
    ) -> Result<DocumentSummary, AppError> {
        validate_document_title(title)?;

        let id = Uuid::new_v4().to_string();
        let now = now_ms();

        sqlx::query(
            "INSERT INTO workspace_documents
             (id, folder_id, title, source_type, recording_id, created_at, updated_at)
             VALUES (?, ?, ?, ?, ?, ?, ?)",
        )
        .bind(&id)
        .bind(folder_id)
        .bind(title)
        .bind(source_type)
        .bind(recording_id)
        .bind(now)
        .bind(now)
        .execute(&self.pool)
        .await?;

        Ok(DocumentSummary {
            id,
            title: title.to_string(),
            folder_id: folder_id.map(str::to_string),
            source_type: source_type.to_string(),
            has_transcript: false,
            has_summary: false,
            has_meeting_brief: false,
            recording_id: recording_id.map(str::to_string),
            created_at: now,
            updated_at: now,
        })
    }

    pub async fn get_document(&self, id: &str) -> Result<DocumentDetail, AppError> {
        let doc = sqlx::query_as::<_, WorkspaceDocumentRow>(
            "SELECT id, folder_id, title, file_path, content_text, source_type, recording_id, created_at, updated_at
             FROM workspace_documents
             WHERE id = ?",
        )
        .bind(id)
        .fetch_optional(&self.pool)
        .await?
        .ok_or_else(|| AppError::NotFound(format!("document {id}")))?;

        let asset_rows = sqlx::query_as::<_, WorkspaceTextAssetRow>(
            "SELECT id, document_id, role, NULL as language, content, file_path, created_at, updated_at
             FROM workspace_text_assets
             WHERE document_id = ?
             ORDER BY created_at ASC",
        )
        .bind(id)
        .fetch_all(&self.pool)
        .await?;

        let assets = asset_rows
            .into_iter()
            .map(|row| TextAsset {
                id: row.id,
                role: row.role,
                language: None,
                content: row.content,
                updated_at: row.updated_at,
            })
            .collect();

        Ok(DocumentDetail {
            id: doc.id,
            title: doc.title,
            folder_id: doc.folder_id,
            source_type: doc.source_type,
            recording_id: doc.recording_id,
            assets,
            created_at: doc.created_at,
            updated_at: doc.updated_at,
        })
    }

    pub async fn update_document_title(&self, id: &str, title: &str) -> Result<(), AppError> {
        validate_document_title(title)?;

        let affected = sqlx::query(
            "UPDATE workspace_documents
             SET title = ?, updated_at = ?
             WHERE id = ?",
        )
        .bind(title)
        .bind(now_ms())
        .bind(id)
        .execute(&self.pool)
        .await?
        .rows_affected();

        if affected == 0 {
            return Err(AppError::NotFound(format!("document {id}")));
        }

        Ok(())
    }

    pub async fn upsert_text_asset(
        &self,
        document_id: &str,
        role: &str,
        content: &str,
        _language: Option<&str>,
    ) -> Result<String, AppError> {
        let now = now_ms();
        let id = Uuid::new_v4().to_string();

        sqlx::query(
            "INSERT INTO workspace_text_assets
             (id, document_id, role, content, created_at, updated_at)
             VALUES (?, ?, ?, ?, ?, ?)
             ON CONFLICT(document_id, role)
             DO UPDATE SET
               content = excluded.content,
               updated_at = excluded.updated_at",
        )
        .bind(&id)
        .bind(document_id)
        .bind(role)
        .bind(content)
        .bind(now)
        .bind(now)
        .execute(&self.pool)
        .await?;

        sqlx::query("UPDATE workspace_documents SET updated_at = ? WHERE id = ?")
            .bind(now)
            .bind(document_id)
            .execute(&self.pool)
            .await?;

        Ok(id)
    }

    pub async fn delete_document(&self, id: &str) -> Result<(), AppError> {
        let affected = sqlx::query("DELETE FROM workspace_documents WHERE id = ?")
            .bind(id)
            .execute(&self.pool)
            .await?
            .rows_affected();

        if affected == 0 {
            return Err(AppError::NotFound(format!("document {id}")));
        }

        Ok(())
    }

    pub async fn list_documents_in_folder(
        &self,
        folder_id: Option<&str>,
    ) -> Result<Vec<DocumentSummary>, AppError> {
        let rows = sqlx::query_as::<_, WorkspaceDocumentRow>(
            "SELECT id, folder_id, title, file_path, content_text, source_type, recording_id, created_at, updated_at
             FROM workspace_documents
             WHERE ((? IS NULL AND folder_id IS NULL) OR folder_id = ?)
             ORDER BY updated_at DESC",
        )
        .bind(folder_id)
        .bind(folder_id)
        .fetch_all(&self.pool)
        .await?;

        let mut docs = Vec::with_capacity(rows.len());
        for doc in rows {
            let (has_transcript, has_summary, has_meeting_brief) =
                self.fetch_asset_flags(&doc.id).await?;
            docs.push(DocumentSummary {
                id: doc.id,
                title: doc.title,
                folder_id: doc.folder_id,
                source_type: doc.source_type,
                has_transcript,
                has_summary,
                has_meeting_brief,
                recording_id: doc.recording_id,
                created_at: doc.created_at,
                updated_at: doc.updated_at,
            });
        }

        Ok(docs)
    }

    pub async fn search_documents(&self, query: &str) -> Result<Vec<SearchResult>, AppError> {
        if query.trim().is_empty() {
            return Ok(vec![]);
        }

        let rows: Vec<(String, String, Option<String>, i64, Option<String>, f64)> = sqlx::query_as(
            "SELECT
                d.id as document_id,
                d.title,
                d.folder_id,
                d.updated_at,
                snippet(workspace_fts, 1, '<mark>', '</mark>', '…', 32) as snippet,
                bm25(workspace_fts) as rank
             FROM workspace_fts
             JOIN workspace_documents d ON workspace_fts.rowid = d.rowid
             WHERE workspace_fts MATCH ?
             ORDER BY rank ASC
             LIMIT 20",
        )
        .bind(query)
        .fetch_all(&self.pool)
        .await?;

        Ok(rows
            .into_iter()
            .map(|(document_id, title, folder_id, updated_at, snippet, rank)| SearchResult {
                document_id,
                title,
                snippet: snippet.unwrap_or_default(),
                rank,
                folder_id,
                updated_at,
            })
            .collect())
    }

    async fn get_folder_row(&self, id: &str) -> Result<WorkspaceFolder, AppError> {
        sqlx::query_as::<_, WorkspaceFolder>(
            "SELECT id, parent_id, name, folder_kind, is_system, created_at
             FROM workspace_folders
             WHERE id = ?",
        )
        .bind(id)
        .fetch_optional(&self.pool)
        .await?
        .ok_or_else(|| AppError::NotFound(format!("folder {id}")))
    }

    async fn check_duplicate_name(
        &self,
        parent_id: Option<&str>,
        name: &str,
        exclude_id: Option<&str>,
    ) -> Result<(), AppError> {
        let existing: Option<(String,)> = sqlx::query_as(
            "SELECT id
             FROM workspace_folders
             WHERE ((?1 IS NULL AND parent_id IS NULL) OR parent_id = ?1)
               AND name = ?2
               AND (?3 IS NULL OR id != ?3)
             LIMIT 1",
        )
        .bind(parent_id)
        .bind(name)
        .bind(exclude_id)
        .fetch_optional(&self.pool)
        .await?;

        if existing.is_some() {
            return Err(AppError::Validation(
                "workspace.duplicate_name".to_string(),
            ));
        }

        Ok(())
    }

    async fn collect_descendant_folder_ids(&self, root_id: &str) -> Result<Vec<String>, AppError> {
        let rows: Vec<(String,)> = sqlx::query_as(
            "WITH RECURSIVE sub(id) AS (
                 SELECT id FROM workspace_folders WHERE parent_id = ?
                 UNION ALL
                 SELECT f.id FROM workspace_folders f
                 JOIN sub s ON f.parent_id = s.id
             )
             SELECT id FROM sub",
        )
        .bind(root_id)
        .fetch_all(&self.pool)
        .await?;

        Ok(rows.into_iter().map(|(id,)| id).collect())
    }

    async fn fetch_asset_flags(&self, doc_id: &str) -> Result<(bool, bool, bool), AppError> {
        let roles: Vec<(String,)> = sqlx::query_as(
            "SELECT role FROM workspace_text_assets WHERE document_id = ?",
        )
        .bind(doc_id)
        .fetch_all(&self.pool)
        .await?;

        let has_transcript = roles.iter().any(|(role,)| role == "transcript");
        let has_summary = roles.iter().any(|(role,)| role == "summary");
        let has_meeting_brief = roles.iter().any(|(role,)| role == "meeting_brief");

        Ok((has_transcript, has_summary, has_meeting_brief))
    }
}

fn now_ms() -> i64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_millis() as i64
}

fn validate_folder_name(name: &str) -> Result<(), AppError> {
    if name.trim().is_empty() {
        return Err(AppError::Validation("workspace.invalid_name".to_string()));
    }

    let invalid_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|'];
    if name.chars().any(|ch| invalid_chars.contains(&ch)) {
        return Err(AppError::Validation("workspace.invalid_name".to_string()));
    }

    Ok(())
}

fn validate_document_title(title: &str) -> Result<(), AppError> {
    if title.trim().is_empty() || title.len() > 255 {
        return Err(AppError::Validation("workspace.invalid_title".to_string()));
    }
    Ok(())
}

fn build_folder_tree(
    rows: &[WorkspaceFolder],
    count_map: &HashMap<String, u32>,
    parent_id: Option<&str>,
) -> Result<Vec<FolderNode>, AppError> {
    let mut nodes = Vec::new();

    for row in rows.iter().filter(|row| row.parent_id.as_deref() == parent_id) {
        nodes.push(FolderNode {
            id: row.id.clone(),
            name: row.name.clone(),
            parent_id: row.parent_id.clone(),
            folder_kind: row.folder_kind.clone(),
            is_system: row.is_system,
            document_count: count_map.get(&row.id).copied().unwrap_or(0),
            children: build_folder_tree(rows, count_map, Some(&row.id))?,
        });
    }

    Ok(nodes)
}
