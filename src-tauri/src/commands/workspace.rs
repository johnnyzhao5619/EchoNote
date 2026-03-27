// src-tauri/src/commands/workspace.rs

use serde::{Deserialize, Serialize};
use specta::Type;
use tauri::State;

use crate::error::AppError;
use crate::state::AppState;
use crate::workspace::document::{DocumentDetail, DocumentSummary, FolderNode, SearchResult};
use crate::workspace::{exporter, parser};

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

#[tauri::command]
#[specta::specta]
pub async fn list_folder_tree(state: State<'_, AppState>) -> Result<Vec<FolderNode>, AppError> {
    state.workspace_manager.list_folders().await
}

#[tauri::command]
#[specta::specta]
pub async fn create_folder(
    state: State<'_, AppState>,
    name: String,
    parent_id: Option<String>,
) -> Result<FolderNode, AppError> {
    state
        .workspace_manager
        .create_folder(&name, parent_id.as_deref())
        .await
}

#[tauri::command]
#[specta::specta]
pub async fn rename_folder(
    state: State<'_, AppState>,
    id: String,
    name: String,
) -> Result<(), AppError> {
    state.workspace_manager.rename_folder(&id, &name).await
}

#[tauri::command]
#[specta::specta]
pub async fn delete_folder(
    state: State<'_, AppState>,
    id: String,
) -> Result<(), AppError> {
    state.workspace_manager.delete_folder(&id).await
}

#[tauri::command]
#[specta::specta]
pub async fn list_documents_in_folder(
    state: State<'_, AppState>,
    folder_id: Option<String>,
) -> Result<Vec<DocumentSummary>, AppError> {
    state
        .workspace_manager
        .list_documents_in_folder(folder_id.as_deref())
        .await
}

#[tauri::command]
#[specta::specta]
pub async fn get_document(
    state: State<'_, AppState>,
    id: String,
) -> Result<DocumentDetail, AppError> {
    state.workspace_manager.get_document(&id).await
}

#[tauri::command]
#[specta::specta]
pub async fn create_document(
    state: State<'_, AppState>,
    title: String,
    folder_id: Option<String>,
    content: String,
) -> Result<DocumentSummary, AppError> {
    let summary = state
        .workspace_manager
        .create_document(&title, folder_id.as_deref(), "note", None)
        .await?;

    if !content.is_empty() {
        state
            .workspace_manager
            .upsert_text_asset(&summary.id, "document_text", &content, None)
            .await?;
    }

    Ok(summary)
}

#[tauri::command]
#[specta::specta]
pub async fn update_document(
    state: State<'_, AppState>,
    id: String,
    title: Option<String>,
    role: Option<String>,
    content: Option<String>,
) -> Result<(), AppError> {
    if let Some(title) = title {
        state.workspace_manager.update_document_title(&id, &title).await?;
    }

    if let (Some(role), Some(content)) = (role, content) {
        state
            .workspace_manager
            .upsert_text_asset(&id, &role, &content, None)
            .await?;
    }

    Ok(())
}

#[tauri::command]
#[specta::specta]
pub async fn delete_document(
    state: State<'_, AppState>,
    id: String,
) -> Result<(), AppError> {
    state.workspace_manager.delete_document(&id).await
}

#[tauri::command]
#[specta::specta]
pub async fn search_workspace(
    state: State<'_, AppState>,
    query: String,
) -> Result<Vec<SearchResult>, AppError> {
    state.workspace_manager.search_documents(&query).await
}

#[tauri::command]
#[specta::specta]
pub async fn export_document(
    state: State<'_, AppState>,
    id: String,
    format: String,
    target_path: String,
) -> Result<(), AppError> {
    let path = std::path::Path::new(&target_path);
    match format.as_str() {
        "md" => exporter::export_as_markdown(&state.db.pool, &id, path).await,
        "txt" => exporter::export_as_txt(&state.db.pool, &id, path).await,
        "srt" => exporter::export_as_srt(&state.db.pool, &id, path).await,
        "vtt" => exporter::export_as_vtt(&state.db.pool, &id, path).await,
        _ => Err(AppError::Validation(format!("unknown export format: {format}"))),
    }
}

#[tauri::command]
#[specta::specta]
pub async fn import_file_to_workspace(
    state: State<'_, AppState>,
    file_path: String,
    folder_id: Option<String>,
) -> Result<DocumentSummary, AppError> {
    let path = std::path::PathBuf::from(&file_path);
    let parsed = tokio::task::spawn_blocking(move || parser::parse_file(&path))
        .await
        .map_err(AppError::io)??;

    let summary = state
        .workspace_manager
        .create_document(&parsed.title, folder_id.as_deref(), "import", None)
        .await?;

    state
        .workspace_manager
        .upsert_text_asset(&summary.id, "document_text", &parsed.text, None)
        .await?;

    Ok(summary)
}
