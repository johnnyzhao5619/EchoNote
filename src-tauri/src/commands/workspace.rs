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
}

/// 列出所有录音，按创建时间倒序
#[tauri::command]
#[specta::specta]
pub async fn list_recordings(
    state: State<'_, AppState>,
) -> Result<Vec<RecordingItem>, AppError> {
    let rows: Vec<(String, String, String, i64, String, i64, Option<String>)> =
        sqlx::query_as(
            "SELECT r.id, r.title, r.file_path, r.duration_ms, r.language, r.created_at,
                    wta.content
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
        .map(|(id, title, file_path, duration_ms, language, created_at, transcript)| {
            RecordingItem {
                id,
                title,
                file_path,
                duration_ms,
                language,
                created_at,
                transcript: transcript.unwrap_or_default(),
            }
        })
        .collect())
}
