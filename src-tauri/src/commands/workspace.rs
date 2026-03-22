// src-tauri/src/commands/workspace.rs

use serde::{Deserialize, Serialize};
use specta::Type;
use tauri::State;

use crate::error::AppError;
use crate::state::AppState;

/// 单条录音摘要（用于 Workspace 列表）
#[derive(Debug, Serialize, Deserialize, Clone, Type)]
pub struct RecordingItem {
    pub id: String,
    pub title: String,
    pub file_path: String,
    pub duration_ms: i64,
    pub language: String,
    pub created_at: i64,
    /// 转写全文拼接（来自 workspace_text_assets.content），无则空串
    pub transcript: String,
    /// workspace_documents.id for this recording (None if not yet indexed)
    pub document_id: Option<String>,
}

/// 列出所有录音，按创建时间倒序
#[tauri::command]
#[specta::specta]
pub async fn list_recordings(
    state: State<'_, AppState>,
) -> Result<Vec<RecordingItem>, AppError> {
    let rows: Vec<(String, String, String, i64, String, i64, Option<String>, Option<String>)> =
        sqlx::query_as(
            "SELECT r.id, r.title, r.file_path, r.duration_ms, r.language, r.created_at,
                    wta.content,
                    wd.id as document_id
             FROM recordings r
             LEFT JOIN workspace_documents wd ON wd.recording_id = r.id
             LEFT JOIN workspace_text_assets wta
               ON wta.document_id = wd.id AND wta.role = 'transcript'
             ORDER BY r.created_at DESC",
        )
        .fetch_all(&state.db.pool)
        .await?;

    Ok(rows
        .into_iter()
        .map(|(id, title, file_path, duration_ms, language, created_at, transcript, document_id)| {
            RecordingItem {
                id,
                title,
                file_path,
                duration_ms,
                language,
                created_at,
                transcript: transcript.unwrap_or_default(),
                document_id,
            }
        })
        .collect())
}

/// Single document text asset (transcript, summary, meeting_brief, etc.)
#[derive(Debug, Serialize, Deserialize, Clone, Type)]
pub struct DocumentAsset {
    pub id: String,
    pub document_id: String,
    pub role: String,
    pub content: String,
    pub created_at: i64,
    pub updated_at: i64,
}

/// Get all text assets for a document, ordered by role priority
#[tauri::command]
#[specta::specta]
pub async fn get_document_assets(
    document_id: String,
    state: State<'_, AppState>,
) -> Result<Vec<DocumentAsset>, AppError> {
    let rows: Vec<(String, String, String, String, i64, i64)> = sqlx::query_as(
        "SELECT id, document_id, role, content, created_at, updated_at
         FROM workspace_text_assets
         WHERE document_id = ?
         ORDER BY CASE role
           WHEN 'transcript'    THEN 0
           WHEN 'document_text' THEN 1
           WHEN 'summary'       THEN 2
           WHEN 'meeting_brief' THEN 3
           WHEN 'translation'   THEN 4
           WHEN 'decisions'     THEN 5
           WHEN 'action_items'  THEN 6
           WHEN 'next_steps'    THEN 7
           ELSE 99 END",
    )
    .bind(&document_id)
    .fetch_all(&state.db.pool)
    .await?;

    Ok(rows.into_iter().map(|(id, document_id, role, content, created_at, updated_at)| {
        DocumentAsset { id, document_id, role, content, created_at, updated_at }
    }).collect())
}
