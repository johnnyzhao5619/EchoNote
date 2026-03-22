// src-tauri/src/llm/mod.rs

pub mod engine;
pub mod streaming;
pub mod tasks;
pub mod worker;

pub use engine::LlmEngine;
pub use tasks::{PromptTemplates, LlmTaskType, LlmTaskRequest, build_prompt, get_best_text};
pub use worker::{LlmWorker, LlmTaskMessage};

use serde::{Deserialize, Serialize};
use specta::Type;

// ── 共享 Payload 类型（被 commands/llm.rs 和 worker.rs 引用）─────────────

#[derive(Debug, Clone, Serialize, Deserialize, Type)]
pub struct TokenPayload {
    pub task_id: String,
    pub token: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, Type)]
pub struct LlmTaskResult {
    pub task_id: String,
    pub document_id: String,
    pub task_type: LlmTaskType,
    pub result_text: String,
    pub asset_role: String,
    pub asset_id: String,
    pub completed_at: i64,
}

#[derive(Debug, Clone, Serialize, Deserialize, Type)]
#[serde(rename_all = "snake_case", tag = "status")]
pub enum LlmEngineStatus {
    NotLoaded,
    Loading { model_id: String },
    Ready { model_id: String, loaded_at: i64 },
    Error { message: String },
}

#[derive(Debug, Clone, Serialize, Deserialize, Type)]
pub struct LlmTaskRow {
    pub id: String,
    pub document_id: String,
    pub task_type: String,
    pub status: String,            // 'pending'|'running'|'done'|'failed'|'cancelled'
    pub result_text: Option<String>,
    pub error_msg: Option<String>,
    pub created_at: i64,
    pub completed_at: Option<i64>,
}

#[derive(Debug, Clone, Serialize, Deserialize, Type)]
pub struct LlmErrorPayload {
    pub task_id: String,
    pub error: String,
}
