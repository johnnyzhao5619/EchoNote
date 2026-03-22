// src-tauri/src/commands/llm.rs

use tauri::State;
use uuid::Uuid;

use crate::{
    error::AppError,
    llm::{
        LlmEngineStatus, LlmTaskRequest, LlmTaskRow,
        worker::LlmTaskMessage,
    },
    state::AppState,
};

/// 提交 LLM 任务，立即返回 task_id
#[tauri::command]
#[specta::specta]
pub async fn submit_llm_task(
    request: LlmTaskRequest,
    state: State<'_, AppState>,
) -> Result<String, AppError> {
    let task_id = Uuid::new_v4().to_string();
    let now_ms = chrono::Utc::now().timestamp_millis();

    let task_type_str = serde_json::to_string(&request.task_type)
        .map_err(|e| AppError::Llm(format!("serialize task_type: {e}")))?;

    let pool = &state.db.pool;

    // Write task to DB (status = pending)
    sqlx::query(
        r#"INSERT INTO llm_tasks (id, document_id, task_type, status, created_at)
           VALUES (?, ?, ?, 'pending', ?)"#,
    )
    .bind(&task_id)
    .bind(&request.document_id)
    .bind(&task_type_str)
    .bind(now_ms)
    .execute(pool)
    .await
    .map_err(|e| AppError::Storage(e.to_string()))?;

    // Query document assets
    let asset_rows = sqlx::query(
        "SELECT role, content FROM workspace_text_assets WHERE document_id = ? ORDER BY rowid",
    )
    .bind(&request.document_id)
    .fetch_all(pool)
    .await
    .map_err(|e| AppError::Storage(e.to_string()))?;

    let assets: Vec<(String, String)> = asset_rows
        .into_iter()
        .map(|r| {
            use sqlx::Row;
            (r.get::<String, _>("role"), r.get::<String, _>("content"))
        })
        .collect();

    // Send to LlmWorker channel
    state
        .llm_tx
        .send(LlmTaskMessage::Submit {
            task_id: task_id.clone(),
            request,
            assets,
        })
        .await
        .map_err(|_| AppError::ChannelClosed)?;

    Ok(task_id)
}

/// 取消 LLM 任务
#[tauri::command]
#[specta::specta]
pub async fn cancel_llm_task(
    task_id: String,
    state: State<'_, AppState>,
) -> Result<(), AppError> {
    state
        .llm_tx
        .send(LlmTaskMessage::Cancel { task_id })
        .await
        .map_err(|_| AppError::ChannelClosed)
}

/// 查询 LLM 引擎状态
#[tauri::command]
#[specta::specta]
pub async fn get_llm_engine_status(
    state: State<'_, AppState>,
) -> Result<LlmEngineStatus, AppError> {
    let status = state.llm_engine_status.lock().await.clone();
    Ok(status)
}

/// 查询某文档的 LLM 任务历史
#[tauri::command]
#[specta::specta]
pub async fn list_document_llm_tasks(
    document_id: String,
    state: State<'_, AppState>,
) -> Result<Vec<LlmTaskRow>, AppError> {
    let pool = &state.db.pool;

    let rows = sqlx::query(
        r#"SELECT id, document_id, task_type, status,
                  result_text, error_msg, created_at, completed_at
           FROM llm_tasks
           WHERE document_id = ?
           ORDER BY created_at DESC
           LIMIT 20"#,
    )
    .bind(&document_id)
    .fetch_all(pool)
    .await
    .map_err(|e| AppError::Storage(e.to_string()))?;

    let tasks = rows
        .into_iter()
        .map(|r| {
            use sqlx::Row;
            LlmTaskRow {
                id: r.get("id"),
                document_id: r.get("document_id"),
                task_type: r.get("task_type"),
                status: r.get("status"),
                result_text: r.get("result_text"),
                error_msg: r.get("error_msg"),
                created_at: r.get("created_at"),
                completed_at: r.get("completed_at"),
            }
        })
        .collect();

    Ok(tasks)
}
