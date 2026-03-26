// src-tauri/src/commands/workspace.rs

use serde::{Deserialize, Serialize};
use specta::Type;
use tauri::State;

use crate::error::AppError;
use crate::state::AppState;

type RecordingRow = (
    String,
    String,
    String,
    i64,
    String,
    i64,
    Option<String>,
    Option<String>,
);

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
    let rows: Vec<RecordingRow> = sqlx::query_as(
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

/// 按需为录音创建 workspace_document（幂等）。
/// 若已存在则直接返回 document_id；否则创建新的 document + transcript asset（从分段拼接）。
#[tauri::command]
#[specta::specta]
pub async fn ensure_document_for_recording(
    recording_id: String,
    state: State<'_, AppState>,
) -> Result<String, AppError> {
    // Check existing
    let existing: Option<String> = sqlx::query_scalar(
        "SELECT id FROM workspace_documents WHERE recording_id = ? LIMIT 1",
    )
    .bind(&recording_id)
    .fetch_optional(&state.db.pool)
    .await?;

    if let Some(doc_id) = existing {
        return Ok(doc_id);
    }

    // Get recording metadata
    let (title, created_at): (String, i64) = sqlx::query_as(
        "SELECT title, created_at FROM recordings WHERE id = ?",
    )
    .bind(&recording_id)
    .fetch_one(&state.db.pool)
    .await?;

    let now = chrono::Utc::now().timestamp();
    let doc_id = uuid::Uuid::new_v4().to_string();

    let mut tx = state.db.pool.begin().await?;

    sqlx::query(
        "INSERT INTO workspace_documents (id, title, source_type, recording_id, created_at, updated_at)
         VALUES (?, ?, 'recording', ?, ?, ?)",
    )
    .bind(&doc_id)
    .bind(&title)
    .bind(&recording_id)
    .bind(created_at)
    .bind(now)
    .execute(&mut *tx)
    .await?;

    // Build transcript from segments if any
    let segments: Vec<String> = sqlx::query_scalar(
        "SELECT text FROM transcription_segments WHERE recording_id = ? ORDER BY start_ms",
    )
    .bind(&recording_id)
    .fetch_all(&mut *tx)
    .await?;

    if !segments.is_empty() {
        let transcript = segments.join(" ");
        let asset_id = uuid::Uuid::new_v4().to_string();
        sqlx::query(
            "INSERT OR IGNORE INTO workspace_text_assets
             (id, document_id, role, content, created_at, updated_at)
             VALUES (?, ?, 'transcript', ?, ?, ?)",
        )
        .bind(&asset_id)
        .bind(&doc_id)
        .bind(&transcript)
        .bind(now)
        .bind(now)
        .execute(&mut *tx)
        .await?;
    }

    tx.commit().await?;
    Ok(doc_id)
}

/// 清洗文件名：只保留字母、数字、空格、连字符、下划线
fn sanitize_filename(s: &str) -> String {
    s.chars()
        .map(|c| {
            if c.is_alphanumeric() || c == '-' || c == '_' || c == ' ' {
                c
            } else {
                '_'
            }
        })
        .collect::<String>()
        .trim()
        .to_string()
}

/// UPSERT 一条 text asset，同时将内容写入本地 .md 文件（vault_path/notes/{title}/{role}.md）。
#[tauri::command]
#[specta::specta]
pub async fn update_document_asset(
    document_id: String,
    role: String,
    content: String,
    state: State<'_, AppState>,
) -> Result<(), AppError> {
    let now = chrono::Utc::now().timestamp();
    let asset_id = uuid::Uuid::new_v4().to_string();

    sqlx::query(
        "INSERT INTO workspace_text_assets (id, document_id, role, content, created_at, updated_at)
         VALUES (?, ?, ?, ?, ?, ?)
         ON CONFLICT(document_id, role)
         DO UPDATE SET content = excluded.content, updated_at = excluded.updated_at",
    )
    .bind(&asset_id)
    .bind(&document_id)
    .bind(&role)
    .bind(&content)
    .bind(now)
    .bind(now)
    .execute(&state.db.pool)
    .await?;

    // Write .md file to vault (non-fatal; skip if vault_path is empty)
    let vault_path = {
        let cfg = state.config.read().await;
        cfg.vault_path.clone()
    };

    if !vault_path.is_empty() {
        let title: Option<String> = sqlx::query_scalar(
            "SELECT title FROM workspace_documents WHERE id = ?",
        )
        .bind(&document_id)
        .fetch_optional(&state.db.pool)
        .await
        .unwrap_or(None);

        if let Some(title) = title {
            let safe_title = sanitize_filename(&title);
            let dir = std::path::Path::new(&vault_path)
                .join("notes")
                .join(&safe_title);
            if tokio::fs::create_dir_all(&dir).await.is_ok() {
                let file_path = dir.join(format!("{}.md", role));
                if tokio::fs::write(&file_path, &content).await.is_ok() {
                    // Update file_path in DB (best-effort)
                    sqlx::query(
                        "UPDATE workspace_text_assets SET file_path = ?
                         WHERE document_id = ? AND role = ?",
                    )
                    .bind(file_path.to_string_lossy().as_ref())
                    .bind(&document_id)
                    .bind(&role)
                    .execute(&state.db.pool)
                    .await
                    .ok();
                }
            }
        }
    }

    Ok(())
}

/// 删除录音。also_delete_document=true 时同时删除关联的 workspace_document（级联删除 assets）。
/// 同时删除磁盘上的 WAV 文件（失败不报错）。
#[tauri::command]
#[specta::specta]
pub async fn delete_recording(
    recording_id: String,
    also_delete_document: bool,
    state: State<'_, AppState>,
) -> Result<(), AppError> {
    // Get file path before deletion
    let file_path: Option<String> = sqlx::query_scalar(
        "SELECT file_path FROM recordings WHERE id = ?",
    )
    .bind(&recording_id)
    .fetch_optional(&state.db.pool)
    .await?;

    if also_delete_document {
        sqlx::query("DELETE FROM workspace_documents WHERE recording_id = ?")
            .bind(&recording_id)
            .execute(&state.db.pool)
            .await?;
    }

    sqlx::query("DELETE FROM recordings WHERE id = ?")
        .bind(&recording_id)
        .execute(&state.db.pool)
        .await?;

    // Delete audio file (non-fatal)
    if let Some(path) = file_path {
        tokio::fs::remove_file(&path).await.ok();
    }

    Ok(())
}
