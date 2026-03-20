# Local LLM Inference Engine Implementation Plan (M5)

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现本地 LLM 推理引擎与 AI 任务系统，支持流式 token 推送、会议纪要结构化解析、任务取消，并在前端提供逐字渲染的 AI 操作区 UI。

**Architecture:** Rust 后端以 `llm/engine.rs`（llama-cpp-2 同步封装）为核心，通过 `llm/streaming.rs` 将同步 token 回调桥接为 tokio unbounded channel，再 emit Tauri 事件；`llm/worker.rs` 是长驻 tokio loop，以 `spawn_blocking` 运行推理，用 `DashMap<String, Arc<AtomicBool>>` 管理活跃任务取消；`llm/tasks.rs` 在启动时加载 `resources/prompts/tasks.toml` 模板，提供 `build_prompt`、`parse_meeting_brief`、`get_best_text` 三个纯函数；前端 Zustand store `useLlmStore` 聚合 token 流，`AiTaskBar` 组件提供三个操作按钮，`StreamingText` 组件逐字追加渲染。

**Tech Stack:** `llama-cpp-2 0.1`（Metal/CUDA/CPU）、`regex 1`、`dashmap 6`、`std::sync::atomic::AtomicBool`、`tokio::sync::mpsc::unbounded_channel`、`serde`/`toml`、React 18 + TypeScript + Zustand + shadcn/ui

---

### Task 1: Prompt 模板文件

**Files:**
- Create: `resources/prompts/tasks.toml`

- [ ] **Step 1.1: 创建 `resources/prompts/tasks.toml`**

  按规格写入 summary、meeting_brief、translation、qa 四个任务的 system/user 模板，变量占位符使用 `{text}`、`{target_language}`、`{question}`、`{context}`。`max_tokens` 字段控制每个任务的最大生成长度。

  ```toml
  # resources/prompts/tasks.toml
  # LLM 任务 Prompt 模板
  # 变量占位符：{text} {target_language} {question} {context}
  # 修改模板后无需重新编译，应用重启即可生效。

  [summary]
  system     = "You are a helpful assistant that summarizes meeting transcripts concisely."
  user       = "Write a concise summary of the following text. Focus on key decisions and outcomes.\n\n{text}"
  max_tokens = 512

  [meeting_brief]
  system = "You are a meeting assistant. Extract structured information from transcripts."
  user   = """Create a structured meeting brief with these sections:
  ## Summary
  ## Decisions
  ## Action Items
  ## Next Steps

  Transcript:
  {text}"""
  max_tokens = 1024

  [translation]
  system     = "You are a professional translator."
  user       = "Translate the following text to {target_language}. Output only the translation.\n\n{text}"
  max_tokens = 2048

  [qa]
  system     = "You are a helpful assistant. Answer questions based on the provided document."
  user       = "Document:\n{context}\n\nQuestion: {question}"
  max_tokens = 512
  ```

- [ ] **Step 1.2: Commit**

  ```
  feat(resources): add LLM prompt templates for summary/brief/translation/qa
  ```

---

### Task 2: Rust 类型定义与错误扩展

**Files:**
- Modify: `src-tauri/src/error.rs`（确认 `Llm` variant 已存在）
- Create: `src-tauri/src/llm/mod.rs`

- [ ] **Step 2.1: 确认 `error.rs` 中 `Llm` variant**

  打开 `src-tauri/src/error.rs`，确认以下 variant 已存在（M1 骨架阶段应已定义）：

  ```rust
  #[error("llm error: {0}")]
  Llm(String),
  ```

  若缺失则补充。同时确认 `Storage`、`NotFound`、`Io` variant 均已存在（后续 Task 依赖）。

- [ ] **Step 2.2: 创建 `src-tauri/src/llm/mod.rs`**

  声明子模块并 re-export 核心类型，供 `commands/llm.rs` 引用：

  ```rust
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
  ```

- [ ] **Step 2.3: 在 `src-tauri/src/lib.rs` 中注册 `llm` 模块**

  找到 `lib.rs` 的模块声明区域，添加：

  ```rust
  pub mod llm;
  ```

- [ ] **Step 2.4: Commit**

  ```
  feat(llm): scaffold llm module with shared payload types
  ```

---

### Task 3: LLM 推理引擎封装（`llm/engine.rs`）

**Files:**
- Create: `src-tauri/src/llm/engine.rs`
- Modify: `src-tauri/Cargo.toml`

- [ ] **Step 3.1: 在 `Cargo.toml` 中添加 llama-cpp-2 依赖**

  在 `[dependencies]` 区块添加（CPU-only 先跑通，Metal 作为可选 feature）：

  ```toml
  llama-cpp-2 = { version = "0.1", features = [] }
  # Metal 加速在 macOS 上可选开启：features = ["metal"]
  # CUDA  加速用 feature flag 控制：见 [features] cuda = ["llama-cpp-2/cuda"]
  ```

  同时确认以下依赖已存在（M1/M2 应已添加）：

  ```toml
  tokio       = { version = "1", features = ["full"] }
  serde       = { version = "1", features = ["derive"] }
  thiserror   = "1"
  ```

- [ ] **Step 3.2: 实现 `src-tauri/src/llm/engine.rs`**

  ```rust
  // src-tauri/src/llm/engine.rs
  //
  // llama-cpp-2 同步封装。
  // 注意：generate() 是阻塞调用，调用方必须通过 tokio::task::spawn_blocking 包裹。

  use std::path::Path;
  use std::sync::Arc;

  use llama_cpp_2::{
      context::params::LlamaContextParams,
      llama_backend::LlamaBackend,
      llama_batch::LlamaBatch,
      model::{params::LlamaModelParams, AddBos, LlamaModel, Special},
      token::data_array::LlamaTokenDataArray,
  };

  use crate::error::AppError;

  // llama-cpp-2 的 LlamaBackend 需全局初始化一次
  static LLAMA_BACKEND: std::sync::OnceLock<LlamaBackend> = std::sync::OnceLock::new();

  fn get_backend() -> Result<&'static LlamaBackend, AppError> {
      LLAMA_BACKEND.get_or_try_init(|| {
          LlamaBackend::init().map_err(|e| AppError::Llm(format!("backend init: {e}")))
      })
  }

  pub struct ContextParams {
      pub ctx_size: u32,
      pub n_threads: i32,
  }

  impl Default for ContextParams {
      fn default() -> Self {
          Self {
              ctx_size: 4096,
              n_threads: num_cpus::get() as i32 / 2,
          }
      }
  }

  pub struct LlmEngine {
      /// Arc 允许 worker 克隆后在 spawn_blocking 中使用，无需持有外层锁
      pub inner_model: Arc<LlamaModel>,
      pub ctx_params: ContextParams,
  }

  impl LlmEngine {
      /// 同步构造——只在启动时或用户切换模型时调用一次，可在 spawn_blocking 中执行
      pub fn new(model_path: &Path, ctx_params: ContextParams) -> Result<Self, AppError> {
          let _backend = get_backend()?;

          let model_params = LlamaModelParams::default();
          let model = LlamaModel::load_from_file(model_path, model_params)
              .map_err(|e| AppError::Llm(format!("load model: {e}")))?;

          Ok(Self {
              inner_model: Arc::new(model),
              ctx_params,
          })
      }

      /// 同步阻塞推理。
      ///
      /// # Arguments
      /// * `system_prompt` - 系统提示词
      /// * `user_prompt`   - 用户提示词（已填充变量）
      /// * `max_tokens`    - 最大生成 token 数
      /// * `token_cb`      - 每生成一个 token 调用一次；返回 `false` 中止生成
      ///
      /// # Returns
      /// 完整生成文本（所有 token 拼接）
      pub fn generate(
          &self,
          system_prompt: &str,
          user_prompt: &str,
          max_tokens: u32,
          token_cb: impl Fn(String) -> bool,
      ) -> Result<String, AppError> {
          let backend = get_backend()?;

          let ctx_params = LlamaContextParams::default()
              .with_n_ctx(std::num::NonZeroU32::new(self.ctx_params.ctx_size))
              .with_n_threads(self.ctx_params.n_threads);

          let mut ctx = self
              .inner_model
              .new_context(backend, ctx_params)
              .map_err(|e| AppError::Llm(format!("create context: {e}")))?;

          // 构建 ChatML 格式 prompt
          let full_prompt = format!(
              "<|im_start|>system\n{system_prompt}<|im_end|>\n\
               <|im_start|>user\n{user_prompt}<|im_end|>\n\
               <|im_start|>assistant\n"
          );

          // Tokenize
          let tokens = self
              .inner_model
              .str_to_token(&full_prompt, AddBos::Always)
              .map_err(|e| AppError::Llm(format!("tokenize: {e}")))?;

          let n_prompt = tokens.len();
          let mut batch = LlamaBatch::new(n_prompt.max(512), 1);

          for (i, &tok) in tokens.iter().enumerate() {
              batch
                  .add(tok, i as i32, &[0], i == n_prompt - 1)
                  .map_err(|e| AppError::Llm(format!("batch add: {e}")))?;
          }

          ctx.decode(&mut batch)
              .map_err(|e| AppError::Llm(format!("prefill decode: {e}")))?;

          let mut result = String::new();
          let mut n_cur = n_prompt as i32;

          loop {
              if n_cur >= n_prompt as i32 + max_tokens as i32 {
                  break;
              }

              let candidates = ctx
                  .candidates_ith(batch.n_tokens() - 1)
                  .map_err(|e| AppError::Llm(format!("candidates: {e}")))?;

              let mut arr = LlamaTokenDataArray::from_iter(candidates, false);
              ctx.sample_temp(None, 0.7);
              ctx.sample_top_p(None, 0.9, 1);
              let new_token = ctx.sample_token_greedy(&mut arr);

              if self
                  .inner_model
                  .is_eog_token(new_token)
              {
                  break;
              }

              let piece = self
                  .inner_model
                  .token_to_str(new_token, Special::Tokenize)
                  .map_err(|e| AppError::Llm(format!("token to str: {e}")))?;

              result.push_str(&piece);

              if !token_cb(piece) {
                  break; // 调用方请求取消
              }

              batch.clear();
              batch
                  .add(new_token, n_cur, &[0], true)
                  .map_err(|e| AppError::Llm(format!("batch add loop: {e}")))?;

              ctx.decode(&mut batch)
                  .map_err(|e| AppError::Llm(format!("decode loop: {e}")))?;

              n_cur += 1;
          }

          Ok(result)
      }
  }

  // ── 集成测试（需要真实模型文件，默认 ignore）────────────────────────────

  #[cfg(test)]
  mod tests {
      use super::*;
      use std::path::PathBuf;

      /// 需要 LLM 模型文件才能运行，跳过 CI。
      /// 运行方式：cargo test -- --ignored test_generate_smoke
      #[test]
      #[ignore]
      fn test_generate_smoke() {
          // 从环境变量读取模型路径，避免硬编码
          let model_path = std::env::var("ECHONOTE_LLM_MODEL_PATH")
              .unwrap_or_else(|_| panic!(
                  "Set ECHONOTE_LLM_MODEL_PATH to a .gguf file to run this test"
              ));
          let path = PathBuf::from(model_path);
          let engine = LlmEngine::new(&path, ContextParams::default())
              .expect("engine init");

          let mut tokens = Vec::new();
          let result = engine
              .generate(
                  "You are a helpful assistant.",
                  "Say hello in one word.",
                  16,
                  |tok| { tokens.push(tok); true },
              )
              .expect("generate");

          assert!(!result.is_empty(), "generated text should not be empty");
          assert!(!tokens.is_empty(), "should have received tokens via callback");
      }
  }
  ```

  > **注意**：`num_cpus` crate 需在 `Cargo.toml` 中添加 `num_cpus = "1"`。`ContextParams::default()` 中 `n_threads` 取物理核数的一半，避免与转写引擎抢资源。

- [ ] **Step 3.3: 在 `Cargo.toml` 添加 `num_cpus`**

  ```toml
  num_cpus = "1"
  ```

- [ ] **Step 3.4: Commit**

  ```
  feat(llm/engine): implement LlmEngine wrapping llama-cpp-2
  ```

---

### Task 4: Token 流桥接（`llm/streaming.rs`）

**Files:**
- Create: `src-tauri/src/llm/streaming.rs`

- [ ] **Step 4.1: 实现 `src-tauri/src/llm/streaming.rs`**

  该模块提供一个工厂函数 `make_token_bridge`，返回「同步发送端」和「async 转发 task 的 JoinHandle」。调用方在 `spawn_blocking` 闭包中持有发送端，async 侧持有 JoinHandle 确保转发 goroutine 在 done 之前不被丢弃。

  ```rust
  // src-tauri/src/llm/streaming.rs
  //
  // 同步 token callback → tokio unbounded channel → Tauri event 桥接。
  //
  // 设计原则：
  //   - 发送端（TokenSender）可安全地在 spawn_blocking 闭包中（非 tokio 线程）调用
  //   - unbounded channel 保证 send 不阻塞，不会因 emit 延迟而拖慢推理循环
  //   - 转发 task 在 channel 关闭（发送端 drop）时自动退出

  use tauri::{AppHandle, Emitter};
  use tokio::sync::mpsc::{self, UnboundedReceiver, UnboundedSender};
  use tokio::task::JoinHandle;

  use crate::llm::TokenPayload;

  /// 同步发送端——在 spawn_blocking 中使用
  #[derive(Clone)]
  pub struct TokenSender(UnboundedSender<String>);

  impl TokenSender {
      /// 发送一个 token。若接收侧已关闭（任务被取消），返回 false 通知推理循环停止。
      pub fn send(&self, token: String) -> bool {
          self.0.send(token).is_ok()
      }
  }

  /// 创建 token 桥接：
  ///
  /// 返回 `(TokenSender, JoinHandle)`:
  /// - `TokenSender` 传入 spawn_blocking 闭包，在 token_cb 中调用 `sender.send(token)`
  /// - `JoinHandle` 由 worker 持有，转发 task 在 channel 关闭时自动结束
  pub fn make_token_bridge(
      app: AppHandle,
      task_id: String,
  ) -> (TokenSender, JoinHandle<()>) {
      let (tx, mut rx): (UnboundedSender<String>, UnboundedReceiver<String>) =
          mpsc::unbounded_channel();

      let handle = tokio::spawn(async move {
          while let Some(token) = rx.recv().await {
              let payload = TokenPayload {
                  task_id: task_id.clone(),
                  token,
              };
              // emit 失败（窗口已关闭）时静默忽略，不 panic
              app.emit("llm:token", payload).ok();
          }
      });

      (TokenSender(tx), handle)
  }

  #[cfg(test)]
  mod tests {
      use super::*;

      #[test]
      fn token_sender_send_returns_false_after_drop() {
          let (tx, rx) = tokio::sync::mpsc::unbounded_channel::<String>();
          let sender = TokenSender(tx);
          // rx 立即 drop，模拟接收侧关闭
          drop(rx);
          assert!(!sender.send("hello".to_string()));
      }
  }
  ```

- [ ] **Step 4.2: Commit**

  ```
  feat(llm/streaming): implement sync-to-async token bridge
  ```

---

### Task 5: Prompt 模板与任务工具函数（`llm/tasks.rs`）

**Files:**
- Create: `src-tauri/src/llm/tasks.rs`
- Modify: `src-tauri/Cargo.toml`（添加 `regex`、`toml`）

- [ ] **Step 5.1: 在 `Cargo.toml` 中添加依赖**

  ```toml
  regex = "1"
  toml  = "0.8"
  ```

  `toml` crate 用于解析 `tasks.toml`；`regex` 用于 `parse_meeting_brief`。

- [ ] **Step 5.2: 实现 `src-tauri/src/llm/tasks.rs`**

  ```rust
  // src-tauri/src/llm/tasks.rs
  //
  // 职责：
  //   1. PromptTemplates：从 tasks.toml 加载（启动时一次），线程安全（只读）
  //   2. build_prompt：填充模板变量，返回 (system, user, max_tokens)
  //   3. parse_meeting_brief：Unicode 安全正则，提取四个 section；全部失败时 fallback 全文
  //   4. get_best_text：按 asset role 优先级取文档最佳可读文本

  use std::collections::HashMap;
  use std::path::Path;
  use std::sync::OnceLock;

  use regex::Regex;
  use serde::Deserialize;

  use crate::error::AppError;
  use crate::llm::LlmTaskType;

  // ── tasks.toml 反序列化结构 ───────────────────────────────────────────────

  #[derive(Debug, Deserialize, Clone)]
  pub struct TaskTemplate {
      pub system: String,
      pub user: String,
      pub max_tokens: u32,
  }

  #[derive(Debug, Deserialize, Clone)]
  pub struct PromptTemplates {
      pub summary: TaskTemplate,
      pub meeting_brief: TaskTemplate,
      pub translation: TaskTemplate,
      pub qa: TaskTemplate,
  }

  impl PromptTemplates {
      /// 从磁盘加载 tasks.toml。
      /// 通常在应用启动时调用一次，结果存入 `AppState`。
      pub fn load(toml_path: &Path) -> Result<Self, AppError> {
          let raw = std::fs::read_to_string(toml_path)
              .map_err(|e| AppError::Io(format!("read tasks.toml: {e}")))?;
          toml::from_str(&raw)
              .map_err(|e| AppError::Llm(format!("parse tasks.toml: {e}")))
      }
  }

  // ── 变量替换 ──────────────────────────────────────────────────────────────

  /// 填充模板变量，返回 `(system_prompt, user_prompt, max_tokens)`。
  ///
  /// 支持的变量：
  /// - `{text}`            : 文档正文（summary / meeting_brief / translation）
  /// - `{target_language}` : 目标语言（translation）
  /// - `{context}`         : 文档上下文（qa）
  /// - `{question}`        : 用户问题（qa）
  pub fn build_prompt(
      templates: &PromptTemplates,
      task_type: &LlmTaskType,
      vars: &HashMap<&str, &str>,
  ) -> Result<(String, String, u32), AppError> {
      let template = match task_type {
          LlmTaskType::Summary => &templates.summary,
          LlmTaskType::MeetingBrief => &templates.meeting_brief,
          LlmTaskType::Translation { .. } => &templates.translation,
          LlmTaskType::Qa { .. } => &templates.qa,
      };

      let fill = |s: &str| -> String {
          let mut out = s.to_string();
          for (k, v) in vars {
              out = out.replace(&format!("{{{k}}}"), v);
          }
          out
      };

      Ok((
          fill(&template.system),
          fill(&template.user),
          template.max_tokens,
      ))
  }

  // ── 会议纪要结构体 ────────────────────────────────────────────────────────

  #[derive(Debug, Default, Clone)]
  pub struct MeetingBriefSections {
      pub summary: Option<String>,
      pub decisions: Option<String>,
      pub action_items: Option<String>,
      pub next_steps: Option<String>,
      /// 全部 section 解析失败时的 fallback：保存完整文本
      pub full_text_fallback: Option<String>,
  }

  impl MeetingBriefSections {
      /// 返回 (asset_role, content) 对列表，供写入 workspace_text_assets 使用。
      /// 若 fallback 触发，则返回单条 ("meeting_brief", full_text)。
      pub fn to_assets(&self) -> Vec<(String, String)> {
          if let Some(ref full) = self.full_text_fallback {
              return vec![("meeting_brief".to_string(), full.clone())];
          }
          let mut assets = Vec::new();
          if let Some(ref s) = self.summary {
              assets.push(("summary".to_string(), s.clone()));
          }
          if let Some(ref d) = self.decisions {
              assets.push(("decisions".to_string(), d.clone()));
          }
          if let Some(ref a) = self.action_items {
              assets.push(("action_items".to_string(), a.clone()));
          }
          if let Some(ref n) = self.next_steps {
              assets.push(("next_steps".to_string(), n.clone()));
          }
          assets
      }
  }

  // ── 全局编译好的正则（lazy，避免重复编译）───────────────────────────────

  fn meeting_brief_regex() -> &'static Regex {
      static RE: OnceLock<Regex> = OnceLock::new();
      RE.get_or_init(|| {
          // (?m) 多行模式：^ 匹配每行开头，$ 匹配每行末尾
          // .+?  非贪婪匹配，支持 Unicode（含中文），不使用 \w 避免只匹配 ASCII
          // [\s\S]*? 跨行匹配 section 内容
          // (?=^##|\z) 前瞻：下一个 ## 标题或文本结束
          Regex::new(r"(?m)^##\s*(.+?)\s*$\n([\s\S]*?)(?=^##|\z)").unwrap()
      })
  }

  /// Unicode 安全的会议纪要解析器。
  ///
  /// 支持英文和中文 section 标题，例如：
  /// - `## Summary` / `## 总结` / `## 摘要`
  /// - `## Decisions` / `## 决策` / `## 决定`
  /// - `## Action Items` / `## 行动项` / `## 任务`
  /// - `## Next Steps` / `## 下一步` / `## 后续`
  ///
  /// 全部 section 均匹配失败时，`full_text_fallback` 置为完整文本，确保数据不丢失。
  pub fn parse_meeting_brief(text: &str) -> MeetingBriefSections {
      let re = meeting_brief_regex();
      let mut sections = MeetingBriefSections::default();

      for cap in re.captures_iter(text) {
          let title = cap[1].trim().to_lowercase();
          let content = cap[2].trim().to_string();
          if content.is_empty() {
              continue;
          }

          if title.contains("summary")
              || title.contains("摘要")
              || title.contains("总结")
              || title.contains("概述")
          {
              sections.summary = Some(content);
          } else if title.contains("decision")
              || title.contains("决策")
              || title.contains("决定")
          {
              sections.decisions = Some(content);
          } else if title.contains("action")
              || title.contains("行动")
              || title.contains("任务")
          {
              sections.action_items = Some(content);
          } else if title.contains("next")
              || title.contains("下一步")
              || title.contains("后续")
          {
              sections.next_steps = Some(content);
          }
      }

      // Fallback：若所有 section 均为 None，保存完整文本
      if sections.summary.is_none()
          && sections.decisions.is_none()
          && sections.action_items.is_none()
          && sections.next_steps.is_none()
      {
          sections.full_text_fallback = Some(text.to_string());
      }

      sections
  }

  // ── Asset Role 优先级 ─────────────────────────────────────────────────────

  /// Asset role 优先级表（数字越小优先级越高）。
  const ROLE_PRIORITY: &[&str] = &[
      "document_text", // 0
      "transcript",    // 1
      "meeting_brief", // 2
      "summary",       // 3
      "translation",   // 4
      "decisions",     // 5
      "action_items",  // 6
      "next_steps",    // 7
  ];

  fn role_rank(role: &str) -> usize {
      ROLE_PRIORITY
          .iter()
          .position(|&r| r == role)
          .unwrap_or(usize::MAX)
  }

  /// 按 Asset Role 优先级从 `(role, content)` 列表中取最佳可读文本。
  ///
  /// 若 `role_hint` 不为 None 且列表中存在对应 role，直接返回该 role 的内容；
  /// 否则按优先级取最高的。列表为空时返回 `None`。
  pub fn get_best_text<'a>(
      assets: &'a [(String, String)],
      role_hint: Option<&str>,
  ) -> Option<&'a str> {
      if let Some(hint) = role_hint {
          if let Some((_, content)) = assets.iter().find(|(r, _)| r == hint) {
              return Some(content.as_str());
          }
      }

      assets
          .iter()
          .min_by_key(|(role, _)| role_rank(role))
          .map(|(_, content)| content.as_str())
  }

  // ── 单元测试 ──────────────────────────────────────────────────────────────

  #[cfg(test)]
  mod tests {
      use super::*;

      // ── parse_meeting_brief ──────────────────────────────────────────────

      #[test]
      fn test_parse_meeting_brief_english_headers() {
          let text = "## Summary\nWe discussed Q1 targets.\n\
                      ## Decisions\nAdopt new CI pipeline.\n\
                      ## Action Items\nAlice: update docs.\n\
                      ## Next Steps\nSchedule follow-up for April.";

          let sections = parse_meeting_brief(text);

          assert!(sections.full_text_fallback.is_none(), "no fallback expected");
          assert_eq!(
              sections.summary.as_deref(),
              Some("We discussed Q1 targets.")
          );
          assert_eq!(
              sections.decisions.as_deref(),
              Some("Adopt new CI pipeline.")
          );
          assert_eq!(
              sections.action_items.as_deref(),
              Some("Alice: update docs.")
          );
          assert_eq!(
              sections.next_steps.as_deref(),
              Some("Schedule follow-up for April.")
          );
      }

      #[test]
      fn test_parse_meeting_brief_chinese_headers() {
          let text = "## 总结\n本次会议讨论了 Q1 目标。\n\
                      ## 决策\n采用新的 CI 流程。\n\
                      ## 任务\n张三：更新文档。\n\
                      ## 下一步\n四月份安排跟进。";

          let sections = parse_meeting_brief(text);

          assert!(sections.full_text_fallback.is_none(), "no fallback expected");
          assert_eq!(
              sections.summary.as_deref(),
              Some("本次会议讨论了 Q1 目标。")
          );
          assert_eq!(
              sections.decisions.as_deref(),
              Some("采用新的 CI 流程。")
          );
          assert_eq!(
              sections.action_items.as_deref(),
              Some("张三：更新文档。")
          );
          assert_eq!(
              sections.next_steps.as_deref(),
              Some("四月份安排跟进。")
          );
      }

      #[test]
      fn test_parse_meeting_brief_fallback_when_no_sections() {
          let text = "This is a plain paragraph with no section headers at all.";

          let sections = parse_meeting_brief(text);

          assert!(sections.summary.is_none());
          assert!(sections.decisions.is_none());
          assert!(sections.action_items.is_none());
          assert!(sections.next_steps.is_none());
          assert_eq!(
              sections.full_text_fallback.as_deref(),
              Some(text),
              "fallback should contain the original text"
          );
      }

      // ── build_prompt ─────────────────────────────────────────────────────

      #[test]
      fn test_build_prompt_summary_variable_substitution() {
          // 构造最小 PromptTemplates（不加载文件）
          let templates = PromptTemplates {
              summary: TaskTemplate {
                  system: "You are a summarizer.".into(),
                  user: "Summarize: {text}".into(),
                  max_tokens: 256,
              },
              meeting_brief: TaskTemplate {
                  system: "".into(),
                  user: "{text}".into(),
                  max_tokens: 1024,
              },
              translation: TaskTemplate {
                  system: "".into(),
                  user: "Translate to {target_language}:\n{text}".into(),
                  max_tokens: 2048,
              },
              qa: TaskTemplate {
                  system: "".into(),
                  user: "Context: {context}\nQ: {question}".into(),
                  max_tokens: 512,
              },
          };

          let vars: HashMap<&str, &str> =
              [("text", "Hello world")].into_iter().collect();

          let (system, user, max_tokens) =
              build_prompt(&templates, &LlmTaskType::Summary, &vars).unwrap();

          assert_eq!(system, "You are a summarizer.");
          assert_eq!(user, "Summarize: Hello world");
          assert_eq!(max_tokens, 256);
          // 确认占位符已被完全替换
          assert!(!user.contains('{'), "no unresolved placeholders in user prompt");
      }

      #[test]
      fn test_build_prompt_translation_substitutes_language_and_text() {
          let templates = PromptTemplates {
              summary: TaskTemplate { system: "".into(), user: "{text}".into(), max_tokens: 1 },
              meeting_brief: TaskTemplate { system: "".into(), user: "{text}".into(), max_tokens: 1 },
              translation: TaskTemplate {
                  system: "Translator".into(),
                  user: "Translate to {target_language}:\n{text}".into(),
                  max_tokens: 512,
              },
              qa: TaskTemplate { system: "".into(), user: "{context}{question}".into(), max_tokens: 1 },
          };

          let vars: HashMap<&str, &str> = [
              ("target_language", "Chinese"),
              ("text", "Good morning"),
          ]
          .into_iter()
          .collect();

          let task = LlmTaskType::Translation { target_language: "Chinese".into() };
          let (_, user, _) = build_prompt(&templates, &task, &vars).unwrap();

          assert_eq!(user, "Translate to Chinese:\nGood morning");
      }

      // ── get_best_text ────────────────────────────────────────────────────

      #[test]
      fn test_get_best_text_returns_highest_priority_role() {
          let assets = vec![
              ("summary".to_string(), "summary content".to_string()),
              ("transcript".to_string(), "transcript content".to_string()),
          ];
          // transcript (priority 1) > summary (priority 3)
          assert_eq!(
              get_best_text(&assets, None),
              Some("transcript content")
          );
      }

      #[test]
      fn test_get_best_text_respects_role_hint() {
          let assets = vec![
              ("transcript".to_string(), "transcript content".to_string()),
              ("summary".to_string(), "summary content".to_string()),
          ];
          // hint 要求 summary，即使 transcript 优先级更高
          assert_eq!(
              get_best_text(&assets, Some("summary")),
              Some("summary content")
          );
      }

      #[test]
      fn test_get_best_text_empty_returns_none() {
          let assets: Vec<(String, String)> = vec![];
          assert_eq!(get_best_text(&assets, None), None);
      }
  }
  ```

- [ ] **Step 5.3: Commit**

  ```
  feat(llm/tasks): implement PromptTemplates, build_prompt, parse_meeting_brief, get_best_text with unit tests
  ```

---

### Task 6: LLM Worker（`llm/worker.rs`）

**Files:**
- Create: `src-tauri/src/llm/worker.rs`
- Modify: `src-tauri/Cargo.toml`（添加 `dashmap`）

- [ ] **Step 6.1: 在 `Cargo.toml` 中添加 `dashmap`**

  ```toml
  dashmap = "6"
  ```

- [ ] **Step 6.2: 实现 `src-tauri/src/llm/worker.rs`**

  ```rust
  // src-tauri/src/llm/worker.rs
  //
  // 长驻 tokio task，接收 LlmTaskMessage，通过 spawn_blocking 执行同步推理。
  // 任务取消：通过 DashMap<task_id, Arc<AtomicBool>> 管理；token_cb 每次检查 AtomicBool。

  use std::collections::HashMap;
  use std::sync::{
      atomic::{AtomicBool, Ordering},
      Arc, Mutex,
  };

  use dashmap::DashMap;
  use sqlx::SqlitePool;
  use tauri::{AppHandle, Emitter};
  use tokio::sync::mpsc;

  use crate::{
      error::AppError,
      llm::{
          engine::LlmEngine,
          streaming::make_token_bridge,
          tasks::{build_prompt, get_best_text, parse_meeting_brief, PromptTemplates},
          LlmEngineStatus, LlmErrorPayload, LlmTaskResult, LlmTaskType, LlmTaskRequest,
          TokenPayload,
      },
  };

  // ── 消息类型 ──────────────────────────────────────────────────────────────

  #[derive(Debug)]
  pub enum LlmTaskMessage {
      Submit {
          task_id: String,
          request: LlmTaskRequest,
          /// (role, content) 列表，由 worker 在推理前从数据库查好并传入（避免 worker 持有 pool Arc 复杂度）
          assets: Vec<(String, String)>,
      },
      Cancel {
          task_id: String,
      },
  }

  // ── Worker ────────────────────────────────────────────────────────────────

  pub struct LlmWorker;

  impl LlmWorker {
      /// 启动长驻 loop。
      ///
      /// 调用方（`lib.rs`）：
      /// ```rust
      /// let (llm_tx, llm_rx) = tokio::sync::mpsc::channel(64);
      /// tokio::spawn(LlmWorker::run(llm_rx, app_handle.clone(), engine_state.clone(), ...));
      /// ```
      pub async fn run(
          mut rx: mpsc::Receiver<LlmTaskMessage>,
          app: AppHandle,
          /// 外层 Mutex<Option<LlmEngine>>——短暂加锁后 clone Arc<LlamaModel>，立即释放
          engine_state: Arc<tokio::sync::Mutex<Option<LlmEngine>>>,
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
                      // 更新数据库状态为 cancelled
                      let _ = sqlx::query!(
                          "UPDATE llm_tasks SET status = 'cancelled' WHERE id = ?",
                          task_id
                      )
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
          engine_state: Arc<tokio::sync::Mutex<Option<LlmEngine>>>,
          templates: Arc<PromptTemplates>,
          active_cancels: Arc<DashMap<String, Arc<AtomicBool>>>,
          pool: SqlitePool,
      ) {
          // ① 更新 DB 状态为 running
          let now_ms = chrono::Utc::now().timestamp_millis();
          let _ = sqlx::query!(
              "UPDATE llm_tasks SET status = 'running' WHERE id = ?",
              task_id
          )
          .execute(&pool)
          .await;

          // ② 短暂加锁，clone Arc<LlamaModel>，立即释放锁
          let engine_arc: Option<Arc<LlmEngine>> = {
              let guard = engine_state.lock().await;
              guard.as_ref().map(|e| {
                  // LlmEngine 不是 Clone，包裹一层 Arc 在 AppState 层
                  // 此处假设 AppState 存的是 Arc<LlmEngine>
                  // 实际见 state.rs Task 8 的设计
                  Arc::clone(
                      // SAFETY: 由 AppState 的 Arc<Mutex<Option<Arc<LlmEngine>>>> 保证
                      // 此处类型参见 Task 8
                      unsafe { &*(e as *const LlmEngine as *const Arc<LlmEngine>) }
                  )
              })
          };

          // 注意：上方 unsafe 仅为占位说明，Task 8 会将 AppState 改为
          // `llm_engine: Arc<Mutex<Option<Arc<LlmEngine>>>>`，消除 unsafe。
          // 实际代码见 Task 8 后的修正版本。

          let Some(engine) = engine_arc else {
              let _ = app.emit("llm:error", LlmErrorPayload {
                  task_id: task_id.clone(),
                  error: "LLM engine not loaded".to_string(),
              });
              let _ = sqlx::query!(
                  "UPDATE llm_tasks SET status = 'failed', error_msg = 'engine not loaded' WHERE id = ?",
                  task_id
              ).execute(&pool).await;
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

          let (target_lang_owned, question_owned);
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

          // ⑥ 创建 token 桥接（同步 callback → async emit）
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
                          return false; // 取消信号
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
                  let _ = sqlx::query!(
                      "UPDATE llm_tasks SET status = 'failed', error_msg = ?, completed_at = ? WHERE id = ?",
                      msg, now_ms, task_id
                  ).execute(&pool).await;
              }

              Ok(Err(app_err)) => {
                  let msg = app_err.to_string();
                  let _ = app.emit("llm:error", LlmErrorPayload {
                      task_id: task_id.clone(),
                      error: msg.clone(),
                  });
                  let _ = sqlx::query!(
                      "UPDATE llm_tasks SET status = 'failed', error_msg = ?, completed_at = ? WHERE id = ?",
                      msg, now_ms, task_id
                  ).execute(&pool).await;
              }

              Ok(Ok(result_text)) => {
                  // 检查是否因取消而停止
                  if cancelled.load(Ordering::Relaxed) {
                      let _ = sqlx::query!(
                          "UPDATE llm_tasks SET status = 'cancelled', completed_at = ? WHERE id = ?",
                          now_ms, task_id
                      ).execute(&pool).await;
                      return;
                  }

                  // ⑩ 写入数据库 + 拆分 MeetingBrief asset
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
                      let _ = sqlx::query!(
                          r#"INSERT INTO workspace_text_assets (id, document_id, role, content, created_at, updated_at)
                             VALUES (?, ?, ?, ?, ?, ?)
                             ON CONFLICT(document_id, role) DO UPDATE SET content = excluded.content, updated_at = excluded.updated_at"#,
                          asset_id, document_id, role, content, now_ms, now_ms
                      ).execute(&pool).await;
                  }

                  let _ = sqlx::query!(
                      "UPDATE llm_tasks SET status = 'done', result_text = ?, completed_at = ? WHERE id = ?",
                      result_text, now_ms, task_id
                  ).execute(&pool).await;

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
  ```

  > **注意**：上方代码中 `engine_state` 类型在 Task 8 完成后需同步修正为 `Arc<tokio::sync::Mutex<Option<Arc<LlmEngine>>>>`，届时删除 `unsafe` 块，直接 `Arc::clone(e)` 即可。

- [ ] **Step 6.3: 在 `Cargo.toml` 添加 `chrono`（若 M2 未添加）**

  ```toml
  chrono = { version = "0.4", features = ["serde"] }
  ```

- [ ] **Step 6.4: Commit**

  ```
  feat(llm/worker): implement LlmWorker with spawn_blocking, DashMap cancel, meeting brief split
  ```

---

### Task 7: Tauri Commands（`commands/llm.rs`）

**Files:**
- Create: `src-tauri/src/commands/llm.rs`
- Modify: `src-tauri/src/commands/mod.rs`
- Modify: `src-tauri/src/lib.rs`（注册 commands）

- [ ] **Step 7.1: 实现 `src-tauri/src/commands/llm.rs`**

  ```rust
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

  /// 提交 LLM 任务，立即返回 task_id（非阻塞）。
  /// Worker 通过 channel 收到后开始排队执行。
  #[tauri::command]
  #[specta::specta]
  pub async fn submit_llm_task(
      request: LlmTaskRequest,
      state: State<'_, AppState>,
  ) -> Result<String, AppError> {
      let task_id = Uuid::new_v4().to_string();
      let now_ms = chrono::Utc::now().timestamp_millis();

      // 写入 llm_tasks 表（status = 'pending'）
      let task_type_str = serde_json::to_string(&request.task_type)
          .map_err(|e| AppError::Llm(format!("serialize task_type: {e}")))?;

      sqlx::query!(
          r#"INSERT INTO llm_tasks (id, document_id, task_type, status, created_at)
             VALUES (?, ?, ?, 'pending', ?)"#,
          task_id,
          request.document_id,
          task_type_str,
          now_ms,
      )
      .execute(&state.pool)
      .await
      .map_err(|e| AppError::Storage(e.to_string()))?;

      // 查询该文档的 assets，供 worker 直接使用（避免 worker 持有 pool 引用）
      let asset_rows = sqlx::query!(
          "SELECT role, content FROM workspace_text_assets WHERE document_id = ? ORDER BY rowid",
          request.document_id
      )
      .fetch_all(&state.pool)
      .await
      .map_err(|e| AppError::Storage(e.to_string()))?;

      let assets: Vec<(String, String)> = asset_rows
          .into_iter()
          .map(|r| (r.role, r.content))
          .collect();

      // 发送到 LlmWorker channel（非阻塞，channel 有界 64）
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

  /// 取消进行中或排队中的 LLM 任务。
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

  /// 查询 LLM 引擎当前状态（设置页展示）。
  #[tauri::command]
  #[specta::specta]
  pub async fn get_llm_engine_status(
      state: State<'_, AppState>,
  ) -> Result<LlmEngineStatus, AppError> {
      let status = state.llm_engine_status.lock().await.clone();
      Ok(status)
  }

  /// 查询某文档的所有 LLM 任务历史（最新 20 条）。
  #[tauri::command]
  #[specta::specta]
  pub async fn list_document_llm_tasks(
      document_id: String,
      state: State<'_, AppState>,
  ) -> Result<Vec<LlmTaskRow>, AppError> {
      let rows = sqlx::query_as!(
          LlmTaskRow,
          r#"SELECT id, document_id, task_type, status,
                    result_text, error_msg, created_at, completed_at
             FROM llm_tasks
             WHERE document_id = ?
             ORDER BY created_at DESC
             LIMIT 20"#,
          document_id
      )
      .fetch_all(&state.pool)
      .await
      .map_err(|e| AppError::Storage(e.to_string()))?;

      Ok(rows)
  }
  ```

- [ ] **Step 7.2: 在 `commands/mod.rs` 中声明 `llm` 子模块并 re-export**

  ```rust
  pub mod llm;
  pub use llm::{
      cancel_llm_task, get_llm_engine_status, list_document_llm_tasks, submit_llm_task,
  };
  ```

- [ ] **Step 7.3: 在 `lib.rs` 的 `tauri::Builder` 中注册四个命令**

  在现有 `.invoke_handler(tauri::generate_handler![...])` 中追加：

  ```rust
  commands::submit_llm_task,
  commands::cancel_llm_task,
  commands::get_llm_engine_status,
  commands::list_document_llm_tasks,
  ```

  同时在 tauri-specta 的 `collect_commands![]` 宏中追加相同四个函数，确保 TypeScript binding 自动生成。

- [ ] **Step 7.4: Commit**

  ```
  feat(commands/llm): add submit/cancel/status/list LLM task commands
  ```

---

### Task 8: AppState 扩展（`state.rs`）

**Files:**
- Modify: `src-tauri/src/state.rs`

- [ ] **Step 8.1: 在 `state.rs` 中扩展 `AppState`**

  打开 `src-tauri/src/state.rs`，在现有字段后追加以下四个字段（其中 `llm_engine` 包裹 `Arc<LlmEngine>` 使 worker 可安全 clone）：

  ```rust
  use dashmap::DashMap;
  use std::sync::{atomic::AtomicBool, Arc};
  use tokio::sync::{Mutex, mpsc};

  use crate::llm::{
      engine::LlmEngine,
      tasks::PromptTemplates,
      worker::LlmTaskMessage,
      LlmEngineStatus,
  };

  pub struct AppState {
      // ... 现有字段（pool, transcription_tx, model_tx 等）...

      /// LLM Worker 消息发送端。command 层通过此 channel 提交任务。
      pub llm_tx: mpsc::Sender<LlmTaskMessage>,

      /// LLM 引擎实例（Option：模型未加载时为 None）。
      /// 外层 Mutex 保护初始化/切换，clone Arc 后立即释放锁，不跨越 spawn_blocking。
      pub llm_engine: Arc<Mutex<Option<Arc<LlmEngine>>>>,

      /// 活跃任务取消标志表（task_id → AtomicBool）。
      /// Worker 插入，command 层通过 cancel 消息触发 Worker 设置 flag。
      pub active_llm_cancels: Arc<DashMap<String, Arc<AtomicBool>>>,

      /// Prompt 模板（启动时一次性加载，只读，Arc 共享）。
      pub prompt_templates: Arc<PromptTemplates>,

      /// LLM 引擎状态（供 get_llm_engine_status command 查询）。
      pub llm_engine_status: Arc<Mutex<LlmEngineStatus>>,
  }
  ```

- [ ] **Step 8.2: 在 `lib.rs` 的 `setup` 闭包中初始化 LLM 相关状态**

  在 `tauri::Builder::default()` 的 `.setup(|app| { ... })` 中添加：

  ```rust
  // 加载 Prompt 模板
  let prompts_path = app.path()
      .resource_dir()
      .expect("resource dir")
      .join("resources/prompts/tasks.toml");
  let prompt_templates = Arc::new(
      PromptTemplates::load(&prompts_path)
          .expect("failed to load tasks.toml")
  );

  // LLM channel（有界 64，防止无限堆积）
  let (llm_tx, llm_rx) = tokio::sync::mpsc::channel::<LlmTaskMessage>(64);

  let llm_engine: Arc<Mutex<Option<Arc<LlmEngine>>>> =
      Arc::new(Mutex::new(None));
  let active_llm_cancels: Arc<DashMap<String, Arc<AtomicBool>>> =
      Arc::new(DashMap::new());
  let llm_engine_status: Arc<Mutex<LlmEngineStatus>> =
      Arc::new(Mutex::new(LlmEngineStatus::NotLoaded));

  // 启动 LlmWorker 长驻 loop
  let app_handle = app.handle().clone();
  let pool_clone = pool.clone();
  let engine_clone = Arc::clone(&llm_engine);
  let templates_clone = Arc::clone(&prompt_templates);
  let cancels_clone = Arc::clone(&active_llm_cancels);
  tokio::spawn(async move {
      LlmWorker::run(
          llm_rx,
          app_handle,
          engine_clone,
          templates_clone,
          cancels_clone,
          pool_clone,
      )
      .await;
  });

  // 注册 AppState（需在现有 manage() 调用中合并）
  app.manage(AppState {
      // ... 现有字段 ...
      llm_tx,
      llm_engine,
      active_llm_cancels,
      prompt_templates,
      llm_engine_status,
  });
  ```

  同时修正 Task 6 中 `handle_submit` 的 `engine_state` 类型为
  `Arc<tokio::sync::Mutex<Option<Arc<LlmEngine>>>>` 并删除 `unsafe` 块：

  ```rust
  // 修正版 — 删除 unsafe，直接 clone Arc<LlmEngine>
  let engine_arc: Option<Arc<LlmEngine>> = {
      let guard = engine_state.lock().await;
      guard.as_ref().map(|e| Arc::clone(e))
  };
  ```

- [ ] **Step 8.3: 在 `storage/migrations/0002_llm_tasks.sql` 中确认 schema**

  确认 `llm_tasks` 表的 `status` 字段与本计划一致：

  ```sql
  -- status: 'pending' | 'running' | 'done' | 'failed' | 'cancelled'
  CREATE TABLE IF NOT EXISTS llm_tasks (
      id           TEXT PRIMARY KEY,
      document_id  TEXT REFERENCES workspace_documents(id) ON DELETE CASCADE,
      task_type    TEXT NOT NULL,
      status       TEXT NOT NULL DEFAULT 'pending',
      result_text  TEXT,
      error_msg    TEXT,
      created_at   INTEGER NOT NULL,
      completed_at INTEGER
  );
  ```

  若 M2 已建此表但缺少 `error_msg` 或 `completed_at` 字段，创建 `0004_llm_tasks_patch.sql` 补充 `ALTER TABLE` 语句。

- [ ] **Step 8.4: Commit**

  ```
  feat(state): extend AppState with llm_tx, llm_engine, active_llm_cancels, prompt_templates
  ```

---

### Task 9: 数据库迁移补充

**Files:**
- Create（视情况）: `src-tauri/src/storage/migrations/0004_llm_tasks_patch.sql`

- [ ] **Step 9.1: 检查并补充 `workspace_text_assets` 表**

  若 M6（Workspace）尚未执行（即 0003_workspace_assets.sql 未运行），`workspace_text_assets` 已由 M2 的 0001_initial.sql 创建，此 patch 仅补充 llm_tasks 字段完整性：

  ```sql
  -- src-tauri/src/storage/migrations/0004_llm_tasks_patch.sql

  -- workspace_text_assets（若 M4 未创建则在此补充）
  CREATE TABLE IF NOT EXISTS workspace_text_assets (
      id           TEXT PRIMARY KEY,
      document_id  TEXT NOT NULL REFERENCES workspace_documents(id) ON DELETE CASCADE,
      role         TEXT NOT NULL,
      content      TEXT NOT NULL,
      file_path    TEXT,
      created_at   INTEGER NOT NULL,
      updated_at   INTEGER NOT NULL,
      UNIQUE(document_id, role)
  );
  CREATE INDEX IF NOT EXISTS idx_assets_document ON workspace_text_assets(document_id, role);

  -- llm_tasks 表确保完整（含 error_msg、completed_at）
  CREATE TABLE IF NOT EXISTS llm_tasks (
      id           TEXT PRIMARY KEY,
      document_id  TEXT REFERENCES workspace_documents(id) ON DELETE CASCADE,
      task_type    TEXT NOT NULL,
      status       TEXT NOT NULL DEFAULT 'pending',
      result_text  TEXT,
      error_msg    TEXT,
      created_at   INTEGER NOT NULL,
      completed_at INTEGER
  );
  ```

  同时在 `storage/db.rs` 的 `sqlx::migrate!("src/storage/migrations")` 确保新文件被包含（sqlx migrate 自动按文件名排序执行）。

- [ ] **Step 9.2: Commit**

  ```
  feat(storage): add workspace_text_assets and ensure llm_tasks schema completeness
  ```

---

### Task 10: React — `useLlmStore`（Zustand）

**Files:**
- Create: `src/store/llm.ts`

- [ ] **Step 10.1: 实现 `src/store/llm.ts`**

  ```typescript
  // src/store/llm.ts
  // LLM 流式任务状态管理。
  // 各任务独立存储 token 列表，支持逐字追加渲染。

  import { create } from "zustand";

  export type LlmTaskStatus =
    | "pending"
    | "running"
    | "done"
    | "failed"
    | "cancelled";

  export interface LlmTaskState {
    taskId: string;
    documentId: string;
    status: LlmTaskStatus;
    tokens: string[];          // 流式 token 列表（逐个追加）
    resultText: string | null; // done 后的完整文本（来自 llm:done 事件）
    errorMsg: string | null;
  }

  interface LlmStore {
    tasks: Map<string, LlmTaskState>;

    // 内部：收到 submit 返回 taskId 时初始化记录
    initTask: (taskId: string, documentId: string) => void;

    // 内部：token 事件追加
    appendToken: (taskId: string, token: string) => void;

    // 内部：任务完成
    setDone: (taskId: string, resultText: string) => void;

    // 内部：任务失败
    setError: (taskId: string, error: string) => void;

    // 内部：任务取消
    setCancelled: (taskId: string) => void;

    // 按 documentId 取该文档最新的各类型任务
    getDocumentTasks: (documentId: string) => LlmTaskState[];

    // 清除已结束的旧任务（UI 可调用）
    clearFinished: (documentId: string) => void;
  }

  export const useLlmStore = create<LlmStore>((set, get) => ({
    tasks: new Map(),

    initTask: (taskId, documentId) =>
      set((s) => {
        const next = new Map(s.tasks);
        next.set(taskId, {
          taskId,
          documentId,
          status: "pending",
          tokens: [],
          resultText: null,
          errorMsg: null,
        });
        return { tasks: next };
      }),

    appendToken: (taskId, token) =>
      set((s) => {
        const task = s.tasks.get(taskId);
        if (!task) return s;
        const next = new Map(s.tasks);
        next.set(taskId, {
          ...task,
          status: "running",
          tokens: [...task.tokens, token],
        });
        return { tasks: next };
      }),

    setDone: (taskId, resultText) =>
      set((s) => {
        const task = s.tasks.get(taskId);
        if (!task) return s;
        const next = new Map(s.tasks);
        next.set(taskId, { ...task, status: "done", resultText });
        return { tasks: next };
      }),

    setError: (taskId, error) =>
      set((s) => {
        const task = s.tasks.get(taskId);
        if (!task) return s;
        const next = new Map(s.tasks);
        next.set(taskId, { ...task, status: "failed", errorMsg: error });
        return { tasks: next };
      }),

    setCancelled: (taskId) =>
      set((s) => {
        const task = s.tasks.get(taskId);
        if (!task) return s;
        const next = new Map(s.tasks);
        next.set(taskId, { ...task, status: "cancelled" });
        return { tasks: next };
      }),

    getDocumentTasks: (documentId) => {
      const all = Array.from(get().tasks.values());
      return all.filter((t) => t.documentId === documentId);
    },

    clearFinished: (documentId) =>
      set((s) => {
        const next = new Map(s.tasks);
        for (const [id, task] of next) {
          if (
            task.documentId === documentId &&
            (task.status === "done" ||
              task.status === "failed" ||
              task.status === "cancelled")
          ) {
            next.delete(id);
          }
        }
        return { tasks: next };
      }),
  }));
  ```

- [ ] **Step 10.2: Commit**

  ```
  feat(store/llm): implement useLlmStore for streaming task state management
  ```

---

### Task 11: React — `useLlmStream` Hook

**Files:**
- Create: `src/hooks/useLlmStream.ts`

- [ ] **Step 11.1: 实现 `src/hooks/useLlmStream.ts`**

  ```typescript
  // src/hooks/useLlmStream.ts
  // 监听 Tauri 事件 llm:token / llm:done / llm:error，按 task_id 聚合到 useLlmStore。
  // 在应用顶层（App.tsx）调用一次即可；不需要在每个组件中重复调用。

  import { useEffect } from "react";
  import { listen, UnlistenFn } from "@tauri-apps/api/event";
  import { useLlmStore } from "@/store/llm";

  // 来自 bindings.ts（tauri-specta 自动生成，此处展示期望的类型）
  interface TokenPayload {
    task_id: string;
    token: string;
  }
  interface LlmTaskResult {
    task_id: string;
    document_id: string;
    result_text: string;
    asset_role: string;
    asset_id: string;
    completed_at: number;
  }
  interface LlmErrorPayload {
    task_id: string;
    error: string;
  }

  export function useLlmStream() {
    const { appendToken, setDone, setError, setCancelled } = useLlmStore();

    useEffect(() => {
      const cleanups: UnlistenFn[] = [];

      (async () => {
        const unToken = await listen<TokenPayload>("llm:token", (event) => {
          appendToken(event.payload.task_id, event.payload.token);
        });
        cleanups.push(unToken);

        const unDone = await listen<LlmTaskResult>("llm:done", (event) => {
          setDone(event.payload.task_id, event.payload.result_text);
        });
        cleanups.push(unDone);

        const unError = await listen<LlmErrorPayload>("llm:error", (event) => {
          // 区分取消（error msg 约定以 "cancelled" 开头）和真实错误
          if (event.payload.error.toLowerCase().startsWith("cancelled")) {
            setCancelled(event.payload.task_id);
          } else {
            setError(event.payload.task_id, event.payload.error);
          }
        });
        cleanups.push(unError);
      })();

      return () => {
        cleanups.forEach((fn) => fn());
      };
    }, []); // eslint-disable-line react-hooks/exhaustive-deps
  }
  ```

- [ ] **Step 11.2: 在 `src/App.tsx` 中调用 `useLlmStream()`**

  ```tsx
  // src/App.tsx（在顶层组件中注册一次事件监听）
  import { useLlmStream } from "@/hooks/useLlmStream";

  export default function App() {
    useLlmStream(); // 注册全局 LLM 事件监听

    return (/* 现有 JSX */);
  }
  ```

- [ ] **Step 11.3: Commit**

  ```
  feat(hooks): implement useLlmStream to aggregate llm:token/done/error events
  ```

---

### Task 12: React — `StreamingText` 组件

**Files:**
- Create: `src/components/ui/StreamingText.tsx`

- [ ] **Step 12.1: 实现 `src/components/ui/StreamingText.tsx`**

  ```tsx
  // src/components/ui/StreamingText.tsx
  // 逐字追加渲染流式文本。
  // 通过 className prop 保持主题一致性；使用 whitespace-pre-wrap 保留换行。

  import { useEffect, useRef } from "react";
  import { cn } from "@/lib/utils";

  interface StreamingTextProps {
    /** 已接收的 token 列表（来自 useLlmStore）*/
    tokens: string[];
    /** 任务是否已结束（done / failed / cancelled）*/
    isFinished: boolean;
    className?: string;
  }

  export function StreamingText({
    tokens,
    isFinished,
    className,
  }: StreamingTextProps) {
    const endRef = useRef<HTMLDivElement>(null);

    // 每次新 token 到来，自动滚动到底部
    useEffect(() => {
      if (!isFinished) {
        endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
      }
    }, [tokens.length, isFinished]);

    const text = tokens.join("");

    return (
      <div
        className={cn(
          "whitespace-pre-wrap break-words text-text-primary text-sm leading-relaxed",
          className
        )}
      >
        {text}
        {/* 光标动画：推理进行中显示闪烁光标 */}
        {!isFinished && text.length > 0 && (
          <span
            className="inline-block w-0.5 h-4 bg-accent ml-0.5 align-middle animate-pulse"
            aria-hidden="true"
          />
        )}
        <div ref={endRef} />
      </div>
    );
  }
  ```

- [ ] **Step 12.2: Commit**

  ```
  feat(ui): implement StreamingText component with auto-scroll and cursor animation
  ```

---

### Task 13: React — `AiTaskBar` 组件

**Files:**
- Create: `src/components/workspace/AiTaskBar.tsx`

- [ ] **Step 13.1: 实现 `src/components/workspace/AiTaskBar.tsx`**

  ```tsx
  // src/components/workspace/AiTaskBar.tsx
  // AI 操作区：生成摘要、会议纪要、翻译三个按钮，含加载状态和取消按钮。
  // 放置在 DocumentMain 顶部操作栏区域。

  import { useState } from "react";
  import { Button } from "@/components/ui/button";
  import { Loader2, X, FileText, Users, Languages } from "lucide-react";
  import { commands } from "@/lib/bindings"; // tauri-specta 生成
  import { useLlmStore } from "@/store/llm";
  import { StreamingText } from "@/components/ui/StreamingText";

  interface AiTaskBarProps {
    documentId: string;
    /** 目标翻译语言（来自 useSettingsStore），默认 "English" */
    targetLanguage?: string;
  }

  type TaskKind = "summary" | "meeting_brief" | "translation";

  export function AiTaskBar({
    documentId,
    targetLanguage = "English",
  }: AiTaskBarProps) {
    const { tasks, initTask, getDocumentTasks } = useLlmStore();
    const [activeTaskId, setActiveTaskId] = useState<string | null>(null);

    const docTasks = getDocumentTasks(documentId);
    const activeTask = activeTaskId ? tasks.get(activeTaskId) : null;
    const isRunning =
      activeTask?.status === "pending" || activeTask?.status === "running";

    const handleSubmit = async (kind: TaskKind) => {
      if (isRunning) return;

      try {
        const taskType =
          kind === "translation"
            ? { translation: { target_language: targetLanguage } }
            : kind === "meeting_brief"
            ? { meeting_brief: null }
            : { summary: null };

        const taskId = await commands.submitLlmTask({
          document_id: documentId,
          task_type: taskType as any,
          text_role_hint: null,
        });

        initTask(taskId, documentId);
        setActiveTaskId(taskId);
      } catch (err) {
        console.error("[AiTaskBar] submit error:", err);
      }
    };

    const handleCancel = async () => {
      if (!activeTaskId) return;
      try {
        await commands.cancelLlmTask(activeTaskId);
      } catch (err) {
        console.error("[AiTaskBar] cancel error:", err);
      }
    };

    return (
      <div className="flex flex-col gap-3">
        {/* 操作按钮行 */}
        <div className="flex items-center gap-2 flex-wrap">
          <Button
            variant="outline"
            size="sm"
            disabled={isRunning}
            onClick={() => handleSubmit("summary")}
            className="gap-1.5"
          >
            <FileText className="w-3.5 h-3.5" />
            生成摘要
          </Button>

          <Button
            variant="outline"
            size="sm"
            disabled={isRunning}
            onClick={() => handleSubmit("meeting_brief")}
            className="gap-1.5"
          >
            <Users className="w-3.5 h-3.5" />
            会议纪要
          </Button>

          <Button
            variant="outline"
            size="sm"
            disabled={isRunning}
            onClick={() => handleSubmit("translation")}
            className="gap-1.5"
          >
            <Languages className="w-3.5 h-3.5" />
            翻译为 {targetLanguage}
          </Button>

          {/* 取消按钮：仅在任务运行中显示 */}
          {isRunning && (
            <Button
              variant="ghost"
              size="sm"
              onClick={handleCancel}
              className="gap-1.5 text-status-error hover:text-status-error"
            >
              <X className="w-3.5 h-3.5" />
              取消
            </Button>
          )}

          {/* 运行指示器 */}
          {isRunning && (
            <span className="flex items-center gap-1.5 text-xs text-text-muted ml-auto">
              <Loader2 className="w-3 h-3 animate-spin" />
              AI 处理中…
            </span>
          )}
        </div>

        {/* 流式输出区域：有活跃任务且有 token 时显示 */}
        {activeTask && activeTask.tokens.length > 0 && (
          <div className="rounded-md border border-border bg-bg-secondary p-3">
            <StreamingText
              tokens={activeTask.tokens}
              isFinished={
                activeTask.status === "done" ||
                activeTask.status === "failed" ||
                activeTask.status === "cancelled"
              }
            />
            {/* 失败时显示错误信息 */}
            {activeTask.status === "failed" && activeTask.errorMsg && (
              <p className="mt-2 text-xs text-status-error">
                错误：{activeTask.errorMsg}
              </p>
            )}
          </div>
        )}
      </div>
    );
  }
  ```

- [ ] **Step 13.2: Commit**

  ```
  feat(workspace): implement AiTaskBar with streaming display and cancel button
  ```

---

### Task 14: 端到端集成验证

**Files:**
- No new files（手动/自动化验证）

- [ ] **Step 14.1: `cargo test` 运行所有单元测试**

  ```bash
  cd src-tauri
  cargo test llm::tasks
  ```

  预期通过的测试：
  - `llm::tasks::tests::test_parse_meeting_brief_english_headers`
  - `llm::tasks::tests::test_parse_meeting_brief_chinese_headers`
  - `llm::tasks::tests::test_parse_meeting_brief_fallback_when_no_sections`
  - `llm::tasks::tests::test_build_prompt_summary_variable_substitution`
  - `llm::tasks::tests::test_build_prompt_translation_substitutes_language_and_text`
  - `llm::tasks::tests::test_get_best_text_returns_highest_priority_role`
  - `llm::tasks::tests::test_get_best_text_respects_role_hint`
  - `llm::tasks::tests::test_get_best_text_empty_returns_none`
  - `llm::streaming::tests::token_sender_send_returns_false_after_drop`

- [ ] **Step 14.2: `cargo build` 确认编译无 warning**

  ```bash
  cd src-tauri
  cargo build 2>&1 | grep -E "^error"
  ```

  目标：零 `error`，warning 数量不超过 M4 基线。

- [ ] **Step 14.3: 集成测试（需模型文件，CI 跳过）**

  本地验证时设置环境变量后运行：

  ```bash
  ECHONOTE_LLM_MODEL_PATH=/path/to/model.gguf \
    cargo test -- --ignored test_generate_smoke
  ```

- [ ] **Step 14.4: 前端 TypeScript 类型检查**

  ```bash
  pnpm tsc --noEmit
  ```

  确认 `useLlmStore`、`AiTaskBar`、`StreamingText`、`useLlmStream` 无类型错误。

- [ ] **Step 14.5: 手动端到端验证清单**

  - [ ] 打开应用，进入 Workspace，打开一个含 `transcript` asset 的文档
  - [ ] 点击"生成摘要"——底部出现流式文本逐字渲染
  - [ ] 点击"取消"——渲染停止，DB 中 `llm_tasks.status = 'cancelled'`
  - [ ] 再点击"会议纪要"——生成完成后 DB 中写入 `summary`/`decisions`/`action_items`/`next_steps` 四条 asset
  - [ ] 对无 section header 的文本测试 fallback：DB 中写入 `meeting_brief` 单条 asset
  - [ ] 点击"翻译"——翻译结果以 `translation` role 写入 `workspace_text_assets`

- [ ] **Step 14.6: 最终 Commit**

  ```
  feat(m5): complete LLM inference engine milestone — engine/streaming/tasks/worker/commands/UI
  ```

---

## 附录 A：`Cargo.toml` 新增依赖汇总

以下依赖均在各 Task 中单独说明，此处汇总以便一次性 diff review：

```toml
[dependencies]
# M5 新增
llama-cpp-2 = { version = "0.1", features = [] }
regex       = "1"
toml        = "0.8"
dashmap     = "6"
num_cpus    = "1"
# chrono 若 M2 已添加则跳过
chrono      = { version = "0.4", features = ["serde"] }

[features]
default = []
metal   = ["llama-cpp-2/metal"]
cuda    = ["llama-cpp-2/cuda", "whisper-rs/cuda"]
```

---

## 附录 B：事件名与 Payload 类型速查

| 事件名       | Rust Payload 类型   | 方向            | 说明                               |
|--------------|--------------------|-----------------|------------------------------------|
| `llm:token`  | `TokenPayload`     | Rust → 前端     | 每个推理 token，含 task_id         |
| `llm:done`   | `LlmTaskResult`    | Rust → 前端     | 任务完成，含 asset_id 和 role      |
| `llm:error`  | `LlmErrorPayload`  | Rust → 前端     | 任务失败或取消，含 error 字符串    |
| `llm:status` | `LlmEngineStatus`  | Rust → 前端     | 引擎状态变更（加载/就绪/错误）     |

---

## 附录 C：`llm_tasks.status` 状态机

```
pending  ──► running ──► done
   │             │
   └─► cancelled ◄─┘ (via cancel command → AtomicBool)
         │
         └─► failed  (generate() 返回 Err)
```

- `pending`：`submit_llm_task` 写入 DB 后的初始状态
- `running`：Worker `handle_submit` 开始执行时更新
- `done`：`generate()` 成功完成，asset 已写入
- `failed`：`generate()` 返回 `AppError` 或 `spawn_blocking` panic
- `cancelled`：`cancel_llm_task` 触发 AtomicBool，推理循环提前退出
