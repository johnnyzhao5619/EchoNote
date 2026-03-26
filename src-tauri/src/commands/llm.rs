// src-tauri/src/commands/llm.rs

use std::sync::Arc;

use tauri::{AppHandle, Emitter, State};
use uuid::Uuid;

use crate::{
    error::AppError,
    llm::{
        LlmEngineStatus, LlmErrorKind, LlmErrorPayload, LlmTaskControl, LlmTaskRequest, LlmTaskRow,
        worker::{LlmTaskMessage, LlmWorker},
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

    let control = Arc::new(LlmTaskControl::new());
    state
        .llm_task_controls
        .insert(task_id.clone(), Arc::clone(&control));

    // Send to LlmWorker channel
    let send_result = state
        .llm_tx
        .send(LlmTaskMessage::Submit {
            task_id: task_id.clone(),
            request,
            assets,
        })
        .await;

    if send_result.is_err() {
        state.llm_task_controls.remove(&task_id);
        let _ = sqlx::query(
            "UPDATE llm_tasks SET status = 'failed', error_msg = 'llm worker unavailable', completed_at = ? WHERE id = ?",
        )
        .bind(chrono::Utc::now().timestamp_millis())
        .bind(&task_id)
        .execute(&state.db.pool)
        .await;
        return Err(AppError::ChannelClosed);
    }

    Ok(task_id)
}

/// 取消 LLM 任务
#[tauri::command]
#[specta::specta]
pub async fn cancel_llm_task(
    task_id: String,
    app: AppHandle,
    state: State<'_, AppState>,
) -> Result<(), AppError> {
    if let Some(control_ref) = state.llm_task_controls.get(&task_id) {
        let control = Arc::clone(control_ref.value());
        drop(control_ref);

        control.cancel();

        if !control.generation_started() {
            LlmWorker::emit_cancelled_terminal(&task_id, &control, &app, &state.db.pool).await;
            state.llm_task_controls.remove(&task_id);
        }

        return Ok(());
    }

    let now_ms = chrono::Utc::now().timestamp_millis();
    let result = sqlx::query(
        "UPDATE llm_tasks SET status = 'cancelled', error_msg = 'cancelled', completed_at = ? WHERE id = ? AND status IN ('pending', 'running')",
    )
    .bind(now_ms)
    .bind(&task_id)
    .execute(&state.db.pool)
    .await
    .map_err(|e| AppError::Storage(e.to_string()))?;

    if result.rows_affected() > 0 {
        app.emit(
            "llm:error",
            LlmErrorPayload {
                task_id,
                kind: LlmErrorKind::Cancelled,
                error: "cancelled".to_string(),
            },
        )
        .map_err(|e| AppError::Llm(format!("emit llm:error: {e}")))?;
    }

    Ok(())
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
