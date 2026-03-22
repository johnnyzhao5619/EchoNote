// src-tauri/src/llm/worker.rs
//
// 长驻 tokio task，接收 LlmTaskMessage，通过 spawn_blocking 执行同步推理。
// 任务取消：通过 DashMap<task_id, Arc<AtomicBool>> 管理；token_cb 每次检查 AtomicBool。

use std::collections::HashMap;
use std::sync::{
    atomic::{AtomicBool, Ordering},
    Arc,
};

use dashmap::DashMap;
use sqlx::SqlitePool;
use tauri::{AppHandle, Emitter};
use tokio::sync::mpsc;

use crate::{
    llm::{
        engine::LlmEngine,
        streaming::make_token_bridge,
        tasks::{build_prompt, get_best_text, parse_meeting_brief, PromptTemplates},
        LlmErrorPayload, LlmTaskResult, LlmTaskType, LlmTaskRequest,
    },
};

// ── 消息类型 ──────────────────────────────────────────────────────────────

#[derive(Debug)]
pub enum LlmTaskMessage {
    Submit {
        task_id: String,
        request: LlmTaskRequest,
        assets: Vec<(String, String)>,
    },
    Cancel {
        task_id: String,
    },
}

// ── Worker ────────────────────────────────────────────────────────────────

pub struct LlmWorker;

impl LlmWorker {
    pub async fn run(
        mut rx: mpsc::Receiver<LlmTaskMessage>,
        app: AppHandle,
        engine_state: Arc<tokio::sync::Mutex<Option<Arc<LlmEngine>>>>,
        templates: Arc<PromptTemplates>,
        active_cancels: Arc<DashMap<String, Arc<AtomicBool>>>,
        pool: SqlitePool,
    ) {
        while let Some(msg) = rx.recv().await {
            match msg {
                LlmTaskMessage::Cancel { task_id } => {
                    if let Some(flag) = active_cancels.get(&task_id) {
                        flag.store(true, Ordering::Relaxed);
                    }
                    let _ = sqlx::query(
                        "UPDATE llm_tasks SET status = 'cancelled' WHERE id = ?",
                    )
                    .bind(&task_id)
                    .execute(&pool)
                    .await;
                }

                LlmTaskMessage::Submit { task_id, request, assets } => {
                    Self::handle_submit(
                        task_id,
                        request,
                        assets,
                        app.clone(),
                        Arc::clone(&engine_state),
                        Arc::clone(&templates),
                        Arc::clone(&active_cancels),
                        pool.clone(),
                    )
                    .await;
                }
            }
        }
    }

    async fn handle_submit(
        task_id: String,
        request: LlmTaskRequest,
        assets: Vec<(String, String)>,
        app: AppHandle,
        engine_state: Arc<tokio::sync::Mutex<Option<Arc<LlmEngine>>>>,
        templates: Arc<PromptTemplates>,
        active_cancels: Arc<DashMap<String, Arc<AtomicBool>>>,
        pool: SqlitePool,
    ) {
        let now_ms = chrono::Utc::now().timestamp_millis();

        // ① 更新 DB 状态为 running
        let _ = sqlx::query(
            "UPDATE llm_tasks SET status = 'running' WHERE id = ?",
        )
        .bind(&task_id)
        .execute(&pool)
        .await;

        // ② 短暂加锁，clone Arc<LlmEngine>，立即释放锁
        let engine_arc: Option<Arc<LlmEngine>> = {
            let guard = engine_state.lock().await;
            guard.as_ref().map(|e| Arc::clone(e))
        };

        let Some(engine) = engine_arc else {
            let _ = app.emit("llm:error", LlmErrorPayload {
                task_id: task_id.clone(),
                error: "LLM engine not loaded".to_string(),
            });
            let _ = sqlx::query(
                "UPDATE llm_tasks SET status = 'failed', error_msg = 'engine not loaded' WHERE id = ?",
            )
            .bind(&task_id)
            .execute(&pool)
            .await;
            return;
        };

        // ③ 取最佳文本
        let text = get_best_text(
            &assets,
            request.text_role_hint.as_deref(),
        )
        .unwrap_or("")
        .to_string();

        // ④ 构建 prompt 变量表
        let mut vars: HashMap<&str, &str> = HashMap::new();
        vars.insert("text", &text);

        let mut target_lang_owned = String::new();
        let mut question_owned = String::new();
        match &request.task_type {
            LlmTaskType::Translation { target_language } => {
                target_lang_owned = target_language.clone();
                vars.insert("target_language", &target_lang_owned);
            }
            LlmTaskType::Qa { question } => {
                question_owned = question.clone();
                vars.insert("context", &text);
                vars.insert("question", &question_owned);
            }
            _ => {}
        }

        let Ok((system, user, max_tokens)) =
            build_prompt(&templates, &request.task_type, &vars)
        else {
            let _ = app.emit("llm:error", LlmErrorPayload {
                task_id: task_id.clone(),
                error: "failed to build prompt".to_string(),
            });
            return;
        };

        // ⑤ 创建 AtomicBool 取消标志，注册到 DashMap
        let cancelled = Arc::new(AtomicBool::new(false));
        active_cancels.insert(task_id.clone(), Arc::clone(&cancelled));

        // ⑥ 创建 token 桥接
        let (token_sender, _bridge_handle) =
            make_token_bridge(app.clone(), task_id.clone());

        // ⑦ spawn_blocking 运行同步推理
        let cancelled_clone = Arc::clone(&cancelled);
        let result = tokio::task::spawn_blocking(move || {
            engine.generate(
                &system,
                &user,
                max_tokens,
                |token| {
                    if cancelled_clone.load(Ordering::Relaxed) {
                        return false;
                    }
                    token_sender.send(token)
                },
            )
        })
        .await;

        // ⑧ 清理取消标志
        active_cancels.remove(&task_id);

        // ⑨ 处理结果
        match result {
            Err(join_err) => {
                let msg = format!("spawn_blocking panic: {join_err}");
                let _ = app.emit("llm:error", LlmErrorPayload {
                    task_id: task_id.clone(),
                    error: msg.clone(),
                });
                let _ = sqlx::query(
                    "UPDATE llm_tasks SET status = 'failed', error_msg = ?, completed_at = ? WHERE id = ?",
                )
                .bind(&msg)
                .bind(now_ms)
                .bind(&task_id)
                .execute(&pool)
                .await;
            }

            Ok(Err(app_err)) => {
                let msg = app_err.to_string();
                let _ = app.emit("llm:error", LlmErrorPayload {
                    task_id: task_id.clone(),
                    error: msg.clone(),
                });
                let _ = sqlx::query(
                    "UPDATE llm_tasks SET status = 'failed', error_msg = ?, completed_at = ? WHERE id = ?",
                )
                .bind(&msg)
                .bind(now_ms)
                .bind(&task_id)
                .execute(&pool)
                .await;
            }

            Ok(Ok(result_text)) => {
                if cancelled.load(Ordering::Relaxed) {
                    let _ = sqlx::query(
                        "UPDATE llm_tasks SET status = 'cancelled', completed_at = ? WHERE id = ?",
                    )
                    .bind(now_ms)
                    .bind(&task_id)
                    .execute(&pool)
                    .await;
                    return;
                }

                let asset_role = Self::derive_asset_role(&request.task_type);
                let document_id = request.document_id.clone();

                let assets_to_write = if matches!(request.task_type, LlmTaskType::MeetingBrief) {
                    let sections = parse_meeting_brief(&result_text);
                    sections.to_assets()
                } else {
                    vec![(asset_role.clone(), result_text.clone())]
                };

                let mut first_asset_id = String::new();
                for (role, content) in &assets_to_write {
                    let asset_id = uuid::Uuid::new_v4().to_string();
                    if first_asset_id.is_empty() {
                        first_asset_id = asset_id.clone();
                    }
                    let _ = sqlx::query(
                        r#"INSERT INTO workspace_text_assets (id, document_id, role, content, created_at, updated_at)
                           VALUES (?, ?, ?, ?, ?, ?)
                           ON CONFLICT(document_id, role) DO UPDATE SET content = excluded.content, updated_at = excluded.updated_at"#,
                    )
                    .bind(&asset_id)
                    .bind(&document_id)
                    .bind(role)
                    .bind(content)
                    .bind(now_ms)
                    .bind(now_ms)
                    .execute(&pool)
                    .await;
                }

                let _ = sqlx::query(
                    "UPDATE llm_tasks SET status = 'done', result_text = ?, completed_at = ? WHERE id = ?",
                )
                .bind(&result_text)
                .bind(now_ms)
                .bind(&task_id)
                .execute(&pool)
                .await;

                let _ = app.emit("llm:done", LlmTaskResult {
                    task_id: task_id.clone(),
                    document_id,
                    task_type: request.task_type,
                    result_text,
                    asset_role,
                    asset_id: first_asset_id,
                    completed_at: now_ms,
                });
            }
        }
    }

    fn derive_asset_role(task_type: &LlmTaskType) -> String {
        match task_type {
            LlmTaskType::Summary => "summary",
            LlmTaskType::MeetingBrief => "meeting_brief",
            LlmTaskType::Translation { .. } => "translation",
            LlmTaskType::Qa { .. } => "qa_answer",
        }
        .to_string()
    }
}
