// src-tauri/src/llm/worker.rs
//
// 长驻 tokio task，接收 submit 消息并为每个任务启动独立 async task。
// 真正的模型推理仍由单 permit Semaphore 串行化，取消语义不再依赖 FIFO channel。

use std::collections::HashMap;
use std::sync::{
    atomic::{AtomicBool, Ordering},
    Arc,
};

use dashmap::DashMap;
use sqlx::{sqlite::SqliteQueryResult, SqlitePool};
use tauri::{AppHandle, Emitter};
use tokio::sync::{mpsc, OwnedSemaphorePermit, Semaphore};

use crate::llm::{
    contracts::{finalize_task_output, structured_prompt_spec},
    build_prompt,
    engine::{GenerationProfile, LlmEngine},
    get_best_text,
    LlmErrorKind,
    LlmErrorPayload,
    LlmTaskResult,
    LlmTaskType,
    LlmTaskRequest,
    PromptTemplates,
};

#[derive(Debug)]
pub enum LlmTaskMessage {
    Submit {
        task_id: String,
        request: LlmTaskRequest,
        assets: Vec<(String, String)>,
    },
}

#[derive(Debug, Default)]
pub struct LlmTaskControl {
    cancelled: AtomicBool,
    generation_started: AtomicBool,
    terminal_emitted: AtomicBool,
}

impl LlmTaskControl {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn cancel(&self) {
        self.cancelled.store(true, Ordering::Relaxed);
    }

    pub fn is_cancelled(&self) -> bool {
        self.cancelled.load(Ordering::Relaxed)
    }

    pub fn mark_generation_started(&self) {
        self.generation_started.store(true, Ordering::Relaxed);
    }

    pub fn generation_started(&self) -> bool {
        self.generation_started.load(Ordering::Relaxed)
    }

    pub fn try_mark_terminal(&self) -> bool {
        self.terminal_emitted
            .compare_exchange(false, true, Ordering::Relaxed, Ordering::Relaxed)
            .is_ok()
    }
}

#[derive(Clone)]
struct SubmitContext {
    app: AppHandle,
    engine_state: Arc<tokio::sync::Mutex<Option<Arc<LlmEngine>>>>,
    templates: Arc<PromptTemplates>,
    task_controls: Arc<DashMap<String, Arc<LlmTaskControl>>>,
    generation_permit: Arc<Semaphore>,
    pool: SqlitePool,
}

pub struct LlmWorker;

impl LlmWorker {
    async fn acquire_generation_permit(
        control: &LlmTaskControl,
        generation_permit: Arc<Semaphore>,
    ) -> Result<Option<OwnedSemaphorePermit>, tokio::sync::AcquireError> {
        let permit = generation_permit.acquire_owned().await?;
        if control.is_cancelled() {
            drop(permit);
            return Ok(None);
        }
        Ok(Some(permit))
    }

    async fn persist_cancelled_status(
        pool: &SqlitePool,
        task_id: &str,
    ) -> Option<SqliteQueryResult> {
        let now_ms = chrono::Utc::now().timestamp_millis();
        sqlx::query(
            "UPDATE llm_tasks SET status = 'cancelled', error_msg = 'cancelled', completed_at = ? WHERE id = ? AND status NOT IN ('done', 'failed', 'cancelled')",
        )
        .bind(now_ms)
        .bind(task_id)
        .execute(pool)
        .await
        .ok()
    }

    pub async fn run(
        mut rx: mpsc::Receiver<LlmTaskMessage>,
        app: AppHandle,
        engine_state: Arc<tokio::sync::Mutex<Option<Arc<LlmEngine>>>>,
        templates: Arc<PromptTemplates>,
        task_controls: Arc<DashMap<String, Arc<LlmTaskControl>>>,
        generation_permit: Arc<Semaphore>,
        pool: SqlitePool,
    ) {
        while let Some(msg) = rx.recv().await {
            let ctx = SubmitContext {
                app: app.clone(),
                engine_state: Arc::clone(&engine_state),
                templates: Arc::clone(&templates),
                task_controls: Arc::clone(&task_controls),
                generation_permit: Arc::clone(&generation_permit),
                pool: pool.clone(),
            };

            match msg {
                LlmTaskMessage::Submit {
                    task_id,
                    request,
                    assets,
                } => {
                    tokio::spawn(async move {
                        Self::handle_submit(task_id, request, assets, ctx).await;
                    });
                }
            }
        }
    }

    async fn handle_submit(
        task_id: String,
        request: LlmTaskRequest,
        assets: Vec<(String, String)>,
        ctx: SubmitContext,
    ) {
        let control = ctx
            .task_controls
            .get(&task_id)
            .map(|entry| Arc::clone(entry.value()))
            .unwrap_or_else(|| {
                let control = Arc::new(LlmTaskControl::new());
                ctx.task_controls.insert(task_id.clone(), Arc::clone(&control));
                control
            });

        if control.is_cancelled() {
            Self::emit_cancelled_terminal(&task_id, &control, &ctx.app, &ctx.pool).await;
            ctx.task_controls.remove(&task_id);
            return;
        }

        let _permit = match Self::acquire_generation_permit(&control, Arc::clone(&ctx.generation_permit)).await {
            Ok(Some(permit)) => permit,
            Ok(None) => {
                Self::emit_cancelled_terminal(&task_id, &control, &ctx.app, &ctx.pool).await;
                ctx.task_controls.remove(&task_id);
                return;
            }
            Err(_) => {
                Self::emit_failed_terminal(
                    &task_id,
                    "generation permit closed".to_string(),
                    &control,
                    &ctx,
                )
                .await;
                ctx.task_controls.remove(&task_id);
                return;
            }
        };

        if control.is_cancelled() {
            Self::emit_cancelled_terminal(&task_id, &control, &ctx.app, &ctx.pool).await;
            ctx.task_controls.remove(&task_id);
            return;
        }

        control.mark_generation_started();

        let now_ms = chrono::Utc::now().timestamp_millis();
        let _ = sqlx::query("UPDATE llm_tasks SET status = 'running' WHERE id = ?")
            .bind(&task_id)
            .execute(&ctx.pool)
            .await;

        let engine = {
            let guard = ctx.engine_state.lock().await;
            guard.as_ref().map(Arc::clone)
        };

        let Some(engine) = engine else {
            Self::emit_failed_terminal(
                &task_id,
                "LLM engine not loaded".to_string(),
                &control,
                &ctx,
            )
            .await;
            ctx.task_controls.remove(&task_id);
            return;
        };

        let source_text = get_best_text(&assets, request.text_role_hint.as_deref())
            .unwrap_or("")
            .to_string();

        let max_tokens = match request.task_type {
            LlmTaskType::Summary => ctx.templates.summary.max_tokens,
            LlmTaskType::MeetingBrief => ctx.templates.meeting_brief.max_tokens,
            LlmTaskType::Translation { .. } => ctx.templates.translation.max_tokens,
            LlmTaskType::Qa { .. } => ctx.templates.qa.max_tokens,
        };

        let profile = GenerationProfile::new(engine.ctx_params.ctx_size, max_tokens, None);

        let text = match engine.fit_text_to_context(&source_text, profile.max_input_tokens) {
            Ok(text) => text,
            Err(err) => {
                Self::emit_failed_terminal(&task_id, err.to_string(), &control, &ctx).await;
                ctx.task_controls.remove(&task_id);
                return;
            }
        };

        let prompt_result = match &request.task_type {
            LlmTaskType::Translation { target_language } => {
                let target_language_owned = target_language.clone();
                let mut vars: HashMap<&str, &str> = HashMap::new();
                vars.insert("text", &text);
                vars.insert("target_language", &target_language_owned);
                build_prompt(&ctx.templates, &request.task_type, &vars)
            }
            LlmTaskType::Qa { question } => {
                let question_owned = question.clone();
                let mut vars: HashMap<&str, &str> = HashMap::new();
                vars.insert("text", &text);
                vars.insert("context", &text);
                vars.insert("question", &question_owned);
                build_prompt(&ctx.templates, &request.task_type, &vars)
            }
            _ => {
                let mut vars: HashMap<&str, &str> = HashMap::new();
                vars.insert("text", &text);
                build_prompt(&ctx.templates, &request.task_type, &vars)
            }
        };

        let (system_prompt, base_user_prompt, max_tokens) = match prompt_result {
            Ok(value) => value,
            Err(err) => {
                Self::emit_failed_terminal(&task_id, err.to_string(), &control, &ctx).await;
                ctx.task_controls.remove(&task_id);
                return;
            }
        };

        let prompt_spec = match structured_prompt_spec(&request.task_type, &base_user_prompt) {
            Ok(spec) => spec,
            Err(err) => {
                Self::emit_failed_terminal(&task_id, err.to_string(), &control, &ctx).await;
                ctx.task_controls.remove(&task_id);
                return;
            }
        };
        let profile = GenerationProfile::new(
            engine.ctx_params.ctx_size,
            max_tokens,
            prompt_spec.grammar.clone(),
        );
        let user_prompt = prompt_spec.user_prompt;

        let (token_sender, _bridge_handle) =
            crate::llm::streaming::make_token_bridge(ctx.app.clone(), task_id.clone());
        let cancelled_control = Arc::clone(&control);

        let generation = tokio::task::spawn_blocking(move || {
            engine.generate(
                &system_prompt,
                &user_prompt,
                &profile,
                |token| {
                    if cancelled_control.is_cancelled() {
                        return false;
                    }
                    token_sender.send(token)
                },
            )
        })
        .await;

        if control.is_cancelled() {
            Self::emit_cancelled_terminal(&task_id, &control, &ctx.app, &ctx.pool).await;
            ctx.task_controls.remove(&task_id);
            return;
        }

        let raw_result = match generation {
            Ok(Ok(result)) => result,
            Ok(Err(err)) => {
                Self::emit_failed_terminal(&task_id, err.to_string(), &control, &ctx).await;
                ctx.task_controls.remove(&task_id);
                return;
            }
            Err(join_err) => {
                Self::emit_failed_terminal(
                    &task_id,
                    format!("spawn_blocking panic: {join_err}"),
                    &control,
                    &ctx,
                )
                .await;
                ctx.task_controls.remove(&task_id);
                return;
            }
        };

        let finalized = match finalize_task_output(&request.task_type, &raw_result) {
            Ok(output) => output,
            Err(err) => {
                Self::emit_failed_terminal(&task_id, err.to_string(), &control, &ctx).await;
                ctx.task_controls.remove(&task_id);
                return;
            }
        };

        if control.is_cancelled() {
            Self::emit_cancelled_terminal(&task_id, &control, &ctx.app, &ctx.pool).await;
            ctx.task_controls.remove(&task_id);
            return;
        }

        let mut first_asset_id = String::new();
        for (role, content) in &finalized.assets_to_write {
            let asset_id = uuid::Uuid::new_v4().to_string();
            if first_asset_id.is_empty() {
                first_asset_id = asset_id.clone();
            }
            if let Err(err) = sqlx::query(
                r#"INSERT INTO workspace_text_assets (id, document_id, role, content, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(document_id, role) DO UPDATE SET content = excluded.content, updated_at = excluded.updated_at"#,
            )
            .bind(&asset_id)
            .bind(&request.document_id)
            .bind(role)
            .bind(content)
            .bind(now_ms)
            .bind(now_ms)
            .execute(&ctx.pool)
            .await
            {
                Self::emit_failed_terminal(&task_id, err.to_string(), &control, &ctx).await;
                ctx.task_controls.remove(&task_id);
                return;
            }
        }

        if !control.try_mark_terminal() {
            ctx.task_controls.remove(&task_id);
            return;
        }

        let _ = sqlx::query(
            "UPDATE llm_tasks SET status = 'done', result_text = ?, completed_at = ? WHERE id = ?",
        )
        .bind(&finalized.result_text)
        .bind(now_ms)
        .bind(&task_id)
        .execute(&ctx.pool)
        .await;

        let _ = ctx.app.emit(
            "llm:done",
            LlmTaskResult {
                task_id: task_id.clone(),
                document_id: request.document_id,
                task_type: request.task_type,
                result_text: finalized.result_text,
                asset_role: finalized.asset_role,
                asset_id: first_asset_id,
                completed_at: now_ms,
            },
        );

        ctx.task_controls.remove(&task_id);
    }

    pub async fn emit_cancelled_terminal(
        task_id: &str,
        control: &LlmTaskControl,
        app: &AppHandle,
        pool: &SqlitePool,
    ) -> Option<SqliteQueryResult> {
        if !control.try_mark_terminal() {
            return None;
        }

        let result = Self::persist_cancelled_status(pool, task_id).await;

        let _ = app.emit(
            "llm:error",
            LlmErrorPayload {
                task_id: task_id.to_string(),
                kind: LlmErrorKind::Cancelled,
                error: "cancelled".to_string(),
            },
        );

        result
    }

    async fn emit_failed_terminal(
        task_id: &str,
        error: String,
        control: &LlmTaskControl,
        ctx: &SubmitContext,
    ) {
        if !control.try_mark_terminal() {
            return;
        }

        let now_ms = chrono::Utc::now().timestamp_millis();
        let _ = sqlx::query(
            "UPDATE llm_tasks SET status = 'failed', error_msg = ?, completed_at = ? WHERE id = ?",
        )
        .bind(&error)
        .bind(now_ms)
        .bind(task_id)
        .execute(&ctx.pool)
        .await;

        let _ = ctx.app.emit(
            "llm:error",
            LlmErrorPayload {
                task_id: task_id.to_string(),
                kind: LlmErrorKind::Failed,
                error,
            },
        );
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::Duration;

    #[test]
    fn task_control_marks_terminal_once() {
        let control = LlmTaskControl::new();
        assert!(control.try_mark_terminal());
        assert!(!control.try_mark_terminal());
    }

    #[test]
    fn task_control_cancel_before_start_is_visible() {
        let control = LlmTaskControl::new();
        control.cancel();
        assert!(control.is_cancelled());
        assert!(!control.generation_started());
    }

    async fn insert_pending_task(pool: &SqlitePool, task_id: &str, request: &LlmTaskRequest) {
        let now_ms = chrono::Utc::now().timestamp_millis();
        sqlx::query(
            r#"INSERT INTO workspace_documents (id, title, source_type, created_at, updated_at)
               VALUES (?, ?, 'manual', ?, ?)
               ON CONFLICT(id) DO NOTHING"#,
        )
        .bind(&request.document_id)
        .bind("Test Document")
        .bind(now_ms)
        .bind(now_ms)
        .execute(pool)
        .await
        .unwrap();

        let task_type_str = serde_json::to_string(&request.task_type).unwrap();
        sqlx::query(
            r#"INSERT INTO llm_tasks (id, document_id, task_type, status, created_at)
               VALUES (?, ?, ?, 'pending', ?)"#,
        )
        .bind(task_id)
        .bind(&request.document_id)
        .bind(task_type_str)
        .bind(now_ms)
        .execute(pool)
        .await
        .unwrap();
    }

    #[tokio::test]
    async fn acquire_generation_permit_returns_none_when_task_is_cancelled_while_waiting() {
        let control = Arc::new(LlmTaskControl::new());
        let permit = Arc::new(Semaphore::new(1));
        let held_permit = Arc::clone(&permit).acquire_owned().await.unwrap();

        let waiting = tokio::spawn({
            let control = Arc::clone(&control);
            let permit = Arc::clone(&permit);
            async move { LlmWorker::acquire_generation_permit(&control, permit).await.unwrap() }
        });

        tokio::time::sleep(Duration::from_millis(25)).await;
        control.cancel();
        drop(held_permit);

        let acquired = waiting.await.unwrap();
        assert!(acquired.is_none());
        assert!(!control.generation_started());
    }

    #[tokio::test]
    async fn persist_cancelled_status_marks_pending_task_as_cancelled() {
        let db = crate::storage::db::Database::open("sqlite::memory:")
            .await
            .unwrap();
        let request = LlmTaskRequest {
            document_id: "doc-1".to_string(),
            task_type: LlmTaskType::Summary,
            text_role_hint: None,
        };
        let task_id = "task-persist-cancelled";

        insert_pending_task(&db.pool, task_id, &request).await;

        let result = LlmWorker::persist_cancelled_status(&db.pool, task_id).await;
        assert!(result.is_some());

        let row: (String, Option<String>) = sqlx::query_as(
            "SELECT status, error_msg FROM llm_tasks WHERE id = ?",
        )
        .bind(task_id)
        .fetch_one(&db.pool)
        .await
        .unwrap();
        assert_eq!(row.0, "cancelled");
        assert_eq!(row.1.as_deref(), Some("cancelled"));
    }

    #[tokio::test]
    async fn persist_cancelled_status_does_not_overwrite_done_task() {
        let db = crate::storage::db::Database::open("sqlite::memory:")
            .await
            .unwrap();
        let request = LlmTaskRequest {
            document_id: "doc-2".to_string(),
            task_type: LlmTaskType::Summary,
            text_role_hint: None,
        };
        let task_id = "task-done";

        insert_pending_task(&db.pool, task_id, &request).await;
        sqlx::query(
            "UPDATE llm_tasks SET status = 'done', result_text = 'done', completed_at = ? WHERE id = ?",
        )
        .bind(chrono::Utc::now().timestamp_millis())
        .bind(task_id)
        .execute(&db.pool)
        .await
        .unwrap();

        let result = LlmWorker::persist_cancelled_status(&db.pool, task_id).await;
        let rows_affected = result.map(|value| value.rows_affected()).unwrap_or(0);
        assert_eq!(rows_affected, 0);

        let row: (String, Option<String>) = sqlx::query_as(
            "SELECT status, error_msg FROM llm_tasks WHERE id = ?",
        )
            .bind(task_id)
            .fetch_one(&db.pool)
            .await
            .unwrap();
        assert_eq!(row.0, "done");
        assert_eq!(row.1, None);
    }
}
