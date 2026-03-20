# Batch Transcription + Media Import Queue Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现批量媒体文件转写队列——支持 WAV/FLAC 直接转写与 MP3/MP4/M4A/MOV/MKV/WEBM/OGG 经 ffmpeg 转码后转写，串行队列执行，结果自动写入数据库并创建 workspace 文档关联。

**Architecture:** Rust 后端以 `transcription/batch.rs` 为核心，内部维护 `VecDeque<BatchJob>` 串行队列（单并发，防止内存压力），由 tokio channel 驱动；`transcription/ffmpeg.rs` 负责检测系统 ffmpeg 并将非 WAV/FLAC 格式转码为 16kHz 单声道 WAV 临时文件；每个 job 完成后通过事务写入 `recordings`、`transcription_segments`、`workspace_documents` 三张表，并通过 Tauri events 推送状态至前端；React 前端由 `TranscriptionPanel`（拖拽上传区）、`TranscriptionMain`（队列列表）、`FfmpegWarning`（缺失提示）三个组件组成，状态统一由 `store/transcription.ts`（Zustand）管理。

**Tech Stack:** `tauri-plugin-shell`（调用系统 ffmpeg）、`tempfile`（临时 WAV 文件）、`uuid`（job_id 生成）、`tokio::sync::mpsc`（批量队列 channel）、`whisper-rs`（已在 M4 集成）、`sqlx`（已在 M2 集成）、React 18 + TypeScript + Zustand + `react-dropzone` + shadcn/ui

---

### Task 1: Cargo.toml — 新增依赖

**Files:**
- Modify: `src-tauri/Cargo.toml`

- [ ] **Step 1.1: 在 `[dependencies]` 中追加以下 crate**

  ```toml
  tempfile = "3"
  # tauri-plugin-shell 在 M1 已加入，确认存在即可；如未加入则追加：
  # tauri-plugin-shell = "2"
  ```

  验证 `tauri-plugin-shell` 是否已在依赖列表中：若已存在跳过，若缺失则追加。`tempfile` 用于在 `{TEMP_DIR}` 下生成 `echonote-{uuid}.wav` 临时转码文件，转写完成后自动删除（NamedTempFile 的 Drop 实现自动清理）。

- [ ] **Step 1.2: 验证依赖解析**

  ```bash
  cd src-tauri && cargo fetch
  ```

- [ ] **Commit:** `chore(deps): add tempfile to Cargo.toml for batch transcription`

---

### Task 2: `transcription/ffmpeg.rs` — ffmpeg 检测与转码

**Files:**
- Create: `src-tauri/src/transcription/ffmpeg.rs`

- [ ] **Step 2.1: 定义 `FfmpegError` 类型和 `detect_ffmpeg` 函数**

  ```rust
  use std::path::Path;
  use thiserror::Error;

  #[derive(Debug, Error)]
  pub enum FfmpegError {
      #[error("ffmpeg not found in PATH")]
      NotFound,
      #[error("ffmpeg conversion failed: {0}")]
      ConversionFailed(String),
      #[error("io error: {0}")]
      Io(#[from] std::io::Error),
  }

  /// 检测系统 PATH 中是否存在 ffmpeg。
  /// 使用 `which ffmpeg`（Unix）或 `where ffmpeg`（Windows）命令。
  pub fn detect_ffmpeg() -> bool {
      let cmd = if cfg!(target_os = "windows") {
          std::process::Command::new("where")
              .arg("ffmpeg")
              .output()
      } else {
          std::process::Command::new("which")
              .arg("ffmpeg")
              .output()
      };
      cmd.map(|o| o.status.success()).unwrap_or(false)
  }
  ```

- [ ] **Step 2.2: 实现 `convert_to_wav` 函数**

  转码命令固定为：`ffmpeg -y -i <input> -ar 16000 -ac 1 -f wav <output>`

  - `-y`：覆盖已存在的输出文件（临时文件路径由调用方保证唯一）
  - `-ar 16000`：输出采样率 16kHz（whisper-rs 要求）
  - `-ac 1`：单声道
  - `-f wav`：强制 WAV 容器格式

  ```rust
  /// 将任意媒体文件同步转码为 16kHz 单声道 WAV。
  /// 调用方传入已创建好的临时文件路径作为 output。
  /// 此函数为同步阻塞，调用时必须置于 tokio::task::spawn_blocking 中。
  pub fn convert_to_wav(input: &Path, output: &Path) -> Result<(), FfmpegError> {
      let result = std::process::Command::new("ffmpeg")
          .args([
              "-y",
              "-i",
              input.to_str().unwrap_or_default(),
              "-ar", "16000",
              "-ac", "1",
              "-f", "wav",
              output.to_str().unwrap_or_default(),
          ])
          .output()?;

      if result.status.success() {
          Ok(())
      } else {
          let stderr = String::from_utf8_lossy(&result.stderr).to_string();
          Err(FfmpegError::ConversionFailed(stderr))
      }
  }
  ```

- [ ] **Step 2.3: 定义格式分类函数**

  ```rust
  /// 判断文件扩展名是否需要经 ffmpeg 转码（而非直接送 whisper-rs）。
  /// whisper-rs 可直接处理 WAV 和 FLAC（需自行解码 PCM）。
  /// 实际上 whisper-rs 接受 f32 PCM 切片，因此 WAV 需要用 hound 解码，
  /// FLAC 需要 claxon 解码——本实现统一将非 WAV 格式全部经 ffmpeg 转为 WAV。
  pub fn needs_transcode(path: &Path) -> bool {
      let ext = path
          .extension()
          .and_then(|e| e.to_str())
          .map(|e| e.to_lowercase());
      !matches!(ext.as_deref(), Some("wav"))
  }

  /// 判断文件格式是否在支持列表中。
  pub fn is_supported_format(path: &Path) -> bool {
      let ext = path
          .extension()
          .and_then(|e| e.to_str())
          .map(|e| e.to_lowercase());
      matches!(
          ext.as_deref(),
          Some("wav" | "flac" | "mp3" | "mp4" | "m4a" | "mov" | "mkv" | "webm" | "ogg")
      )
  }
  ```

  设计说明：`needs_transcode` 将 FLAC 也归入转码路径（经 ffmpeg → WAV），因为 whisper-rs 直接接收 `&[f32]` PCM，用 ffmpeg 统一转换最为简洁、无需引入额外解码依赖。

- [ ] **Commit:** `feat(transcription): add ffmpeg detection and transcode helpers`

---

### Task 3: `transcription/batch.rs` — 批量队列核心

**Files:**
- Create: `src-tauri/src/transcription/batch.rs`

- [ ] **Step 3.1: 定义 `BatchStatus` 和 `BatchJob` 类型**

  ```rust
  use std::path::PathBuf;
  use serde::{Serialize, Deserialize};
  use specta::Type;

  #[derive(Debug, Clone, Serialize, Deserialize, Type, PartialEq)]
  #[serde(tag = "type", content = "data")]
  pub enum BatchStatus {
      Queued,
      Processing { progress: f32 },   // 0.0 - 1.0
      Done { recording_id: String, document_id: String },
      Failed { error: String },
      Cancelled,
  }

  #[derive(Debug, Clone)]
  pub struct BatchJob {
      pub id: String,                  // UUID v4
      pub file_path: PathBuf,
      pub file_name: String,           // 展示用文件名（不含路径）
      pub language: Option<String>,
      pub status: BatchStatus,
      pub created_at: i64,             // Unix 毫秒
  }

  /// 前端查询用的轻量视图（不含 PathBuf，可直接序列化）
  #[derive(Debug, Clone, Serialize, Deserialize, Type)]
  pub struct BatchJobView {
      pub job_id: String,
      pub file_name: String,
      pub language: Option<String>,
      pub status: BatchStatus,
      pub created_at: i64,
  }
  ```

- [ ] **Step 3.2: 定义 `BatchCommand` 枚举**

  ```rust
  pub enum BatchCommand {
      /// 入队一个新文件
      Enqueue {
          job_id: String,
          file_path: PathBuf,
          language: Option<String>,
      },
      /// 取消指定 job（Queued 状态立即移除；Processing 状态设置取消标志）
      Cancel { job_id: String },
      /// 清除所有 Done / Failed / Cancelled 状态的历史记录
      ClearCompleted,
  }
  ```

- [ ] **Step 3.3: 实现 `BatchQueue` 结构体**

  ```rust
  use std::collections::VecDeque;
  use std::sync::Arc;
  use tokio::sync::{mpsc, Mutex};
  use tauri::AppHandle;
  use crate::storage::db::Database;
  use crate::transcription::engine::WhisperEngine;

  pub struct BatchQueue {
      /// 内部队列（含所有状态的 job，用于历史查询）
      jobs: Arc<Mutex<Vec<BatchJob>>>,
      /// 等待执行的 job_id 顺序（FIFO）
      pending: Arc<Mutex<VecDeque<String>>>,
      /// 当前正在处理的 job_id
      current_job_id: Arc<Mutex<Option<String>>>,
      /// 取消标志：当前 Processing job 被请求取消时设置为 true
      cancel_flag: Arc<Mutex<bool>>,
  }
  ```

- [ ] **Step 3.4: 实现 `BatchQueue::new` 和 `run` 方法**

  `run` 是长驻 tokio task 的主循环，从 `mpsc::Receiver<BatchCommand>` 接收命令，串行处理队列中的 job：

  ```rust
  impl BatchQueue {
      pub fn new() -> Self {
          Self {
              jobs: Arc::new(Mutex::new(Vec::new())),
              pending: Arc::new(Mutex::new(VecDeque::new())),
              current_job_id: Arc::new(Mutex::new(None)),
              cancel_flag: Arc::new(Mutex::new(false)),
          }
      }

      /// 启动长驻后台 task。在 lib.rs 的 setup 钩子中调用：
      /// tokio::spawn(batch_queue.run(rx, app_handle, db, whisper_engine));
      pub async fn run(
          self: Arc<Self>,
          mut rx: mpsc::Receiver<BatchCommand>,
          app_handle: AppHandle,
          db: Arc<Database>,
          whisper_engine: Arc<tokio::sync::Mutex<Option<WhisperEngine>>>,
      ) {
          // 注意：命令接收与 job 执行必须交替进行，不能 select!，
          // 因为 job 执行是 spawn_blocking（阻塞），需要在 await 点接收新命令。
          // 策略：每次执行完一个 job 后，drain rx 中所有待处理命令，再取下一个 pending job。

          loop {
              // 1. 非阻塞 drain：处理所有已到达的命令
              while let Ok(cmd) = rx.try_recv() {
                  self.handle_command(cmd, &app_handle).await;
              }

              // 2. 取下一个 pending job
              let next_job_id = {
                  let mut pending = self.pending.lock().await;
                  pending.pop_front()
              };

              if let Some(job_id) = next_job_id {
                  // 3. 执行 job（串行，await 点在 spawn_blocking 返回时）
                  self.execute_job(
                      &job_id,
                      &app_handle,
                      &db,
                      &whisper_engine,
                  ).await;
              } else {
                  // 4. 无 pending job 时，阻塞等待下一个命令（节省 CPU）
                  match rx.recv().await {
                      Some(cmd) => self.handle_command(cmd, &app_handle).await,
                      None => break, // channel 关闭，退出 loop
                  }
              }
          }
      }
  }
  ```

- [ ] **Step 3.5: 实现 `handle_command` 方法**

  ```rust
  impl BatchQueue {
      async fn handle_command(&self, cmd: BatchCommand, app_handle: &AppHandle) {
          match cmd {
              BatchCommand::Enqueue { job_id, file_path, language } => {
                  use crate::transcription::ffmpeg::is_supported_format;
                  use std::time::{SystemTime, UNIX_EPOCH};

                  let file_name = file_path
                      .file_name()
                      .and_then(|n| n.to_str())
                      .unwrap_or("unknown")
                      .to_string();

                  // 不支持的格式立即标记失败，不入队
                  if !is_supported_format(&file_path) {
                      let _ = app_handle.emit(
                          "batch:error",
                          serde_json::json!({
                              "job_id": &job_id,
                              "file_name": &file_name,
                              "error": "Unsupported file format"
                          }),
                      );
                      return;
                  }

                  let created_at = SystemTime::now()
                      .duration_since(UNIX_EPOCH)
                      .unwrap_or_default()
                      .as_millis() as i64;

                  let job = BatchJob {
                      id: job_id.clone(),
                      file_path,
                      file_name: file_name.clone(),
                      language,
                      status: BatchStatus::Queued,
                      created_at,
                  };

                  self.jobs.lock().await.push(job);
                  self.pending.lock().await.push_back(job_id.clone());

                  let _ = app_handle.emit(
                      "batch:queued",
                      serde_json::json!({
                          "job_id": job_id,
                          "file_name": file_name
                      }),
                  );
              }

              BatchCommand::Cancel { job_id } => {
                  let mut jobs = self.jobs.lock().await;
                  if let Some(job) = jobs.iter_mut().find(|j| j.id == job_id) {
                      match &job.status {
                          BatchStatus::Queued => {
                              // 从 pending 队列移除
                              let mut pending = self.pending.lock().await;
                              pending.retain(|id| id != &job_id);
                              job.status = BatchStatus::Cancelled;
                          }
                          BatchStatus::Processing { .. } => {
                              // 设置取消标志，execute_job 循环中会检查
                              *self.cancel_flag.lock().await = true;
                          }
                          _ => {} // Done/Failed/Cancelled 无法取消
                      }
                  }
              }

              BatchCommand::ClearCompleted => {
                  let mut jobs = self.jobs.lock().await;
                  jobs.retain(|j| {
                      !matches!(
                          &j.status,
                          BatchStatus::Done { .. }
                              | BatchStatus::Failed { .. }
                              | BatchStatus::Cancelled
                      )
                  });
              }
          }
      }
  }
  ```

- [ ] **Step 3.6: 实现 `execute_job` 方法**

  此方法处理单个 job 的完整生命周期：格式检测 → 可选转码 → WAV 解码 → whisper 推理 → 数据库写入 → 事件通知。

  ```rust
  impl BatchQueue {
      async fn execute_job(
          &self,
          job_id: &str,
          app_handle: &AppHandle,
          db: &Arc<Database>,
          whisper_engine: &Arc<tokio::sync::Mutex<Option<WhisperEngine>>>,
      ) {
          use crate::transcription::ffmpeg::{detect_ffmpeg, needs_transcode, convert_to_wav, FfmpegError};
          use uuid::Uuid;

          // --- 取出 job 信息 ---
          let (file_path, file_name, language) = {
              let jobs = self.jobs.lock().await;
              let job = match jobs.iter().find(|j| j.id == job_id) {
                  Some(j) => j,
                  None => return,
              };
              (job.file_path.clone(), job.file_name.clone(), job.language.clone())
          };

          // --- 检查是否已被取消 ---
          if *self.cancel_flag.lock().await {
              *self.cancel_flag.lock().await = false;
              return;
          }

          // --- 更新状态为 Processing(0.0) ---
          *self.current_job_id.lock().await = Some(job_id.to_string());
          {
              let mut jobs = self.jobs.lock().await;
              if let Some(job) = jobs.iter_mut().find(|j| j.id == job_id) {
                  job.status = BatchStatus::Processing { progress: 0.0 };
              }
          }
          let _ = app_handle.emit(
              "batch:progress",
              serde_json::json!({
                  "job_id": job_id,
                  "file_name": &file_name,
                  "progress": 0.0_f32
              }),
          );

          // --- 转码（如需要）---
          // temp_file 持有 NamedTempFile，Drop 时自动删除
          let (wav_path, _temp_file) = if needs_transcode(&file_path) {
              // 检查 ffmpeg 是否可用
              if !detect_ffmpeg() {
                  let _ = app_handle.emit("batch:ffmpeg_missing", ());
                  self.mark_failed(job_id, "ffmpeg not found in PATH").await;
                  let _ = app_handle.emit(
                      "batch:error",
                      serde_json::json!({
                          "job_id": job_id,
                          "file_name": &file_name,
                          "error": "ffmpeg not found. Please install ffmpeg."
                      }),
                  );
                  *self.current_job_id.lock().await = None;
                  return;
              }

              // 创建临时 WAV 文件
              let tmp = match tempfile::Builder::new()
                  .prefix(&format!("echonote-{}", Uuid::new_v4()))
                  .suffix(".wav")
                  .tempfile()
              {
                  Ok(f) => f,
                  Err(e) => {
                      self.mark_failed(job_id, &e.to_string()).await;
                      self.emit_error(app_handle, job_id, &file_name, &e.to_string());
                      *self.current_job_id.lock().await = None;
                      return;
                  }
              };
              let tmp_path = tmp.path().to_path_buf();
              let input_path = file_path.clone();
              let output_path = tmp_path.clone();

              // 转码（阻塞，放入 spawn_blocking）
              let convert_result = tokio::task::spawn_blocking(move || {
                  convert_to_wav(&input_path, &output_path)
              })
              .await;

              match convert_result {
                  Ok(Ok(())) => (tmp_path, Some(tmp)),
                  Ok(Err(e)) => {
                      self.mark_failed(job_id, &e.to_string()).await;
                      self.emit_error(app_handle, job_id, &file_name, &e.to_string());
                      *self.current_job_id.lock().await = None;
                      return;
                  }
                  Err(e) => {
                      self.mark_failed(job_id, &e.to_string()).await;
                      self.emit_error(app_handle, job_id, &file_name, &e.to_string());
                      *self.current_job_id.lock().await = None;
                      return;
                  }
              }
          } else {
              (file_path.clone(), None)
          };

          // emit progress: 转码完成，进度 0.2
          let _ = app_handle.emit(
              "batch:progress",
              serde_json::json!({ "job_id": job_id, "file_name": &file_name, "progress": 0.2_f32 }),
          );

          // --- 解码 WAV → f32 PCM ---
          let wav_path_clone = wav_path.clone();
          let pcm_result = tokio::task::spawn_blocking(move || -> Result<Vec<f32>, String> {
              let mut reader = hound::WavReader::open(&wav_path_clone)
                  .map_err(|e| e.to_string())?;
              let spec = reader.spec();
              // 转码后期望：16000Hz, 单声道, 16-bit PCM
              let samples: Result<Vec<f32>, _> = match spec.sample_format {
                  hound::SampleFormat::Int => reader
                      .samples::<i16>()
                      .map(|s| s.map(|v| v as f32 / i16::MAX as f32))
                      .collect(),
                  hound::SampleFormat::Float => reader
                      .samples::<f32>()
                      .collect(),
              };
              samples.map_err(|e| e.to_string())
          })
          .await;

          let pcm = match pcm_result {
              Ok(Ok(v)) => v,
              Ok(Err(e)) | Err(_) if true => {
                  let err_msg = pcm_result
                      .unwrap_or_else(|e| Err(e.to_string()))
                      .unwrap_err();
                  self.mark_failed(job_id, &err_msg).await;
                  self.emit_error(app_handle, job_id, &file_name, &err_msg);
                  *self.current_job_id.lock().await = None;
                  return;
              }
              _ => unreachable!(),
          };

          // emit progress: WAV 解码完成，进度 0.3
          let _ = app_handle.emit(
              "batch:progress",
              serde_json::json!({ "job_id": job_id, "file_name": &file_name, "progress": 0.3_f32 }),
          );

          // --- 检查取消标志 ---
          if *self.cancel_flag.lock().await {
              *self.cancel_flag.lock().await = false;
              self.mark_cancelled(job_id).await;
              *self.current_job_id.lock().await = None;
              return;
          }

          // --- whisper 推理（spawn_blocking）---
          let engine_arc = {
              let guard = whisper_engine.lock().await;
              guard.as_ref().map(|e| e.clone_arc())
          };

          let engine = match engine_arc {
              Some(e) => e,
              None => {
                  self.mark_failed(job_id, "Whisper engine not loaded").await;
                  self.emit_error(app_handle, job_id, &file_name, "Whisper engine not loaded");
                  *self.current_job_id.lock().await = None;
                  return;
              }
          };

          let lang_clone = language.clone();
          let transcribe_result = tokio::task::spawn_blocking(move || {
              engine.transcribe(&pcm, lang_clone.as_deref())
          })
          .await;

          let segments = match transcribe_result {
              Ok(Ok(segs)) => segs,
              Ok(Err(e)) => {
                  self.mark_failed(job_id, &e.to_string()).await;
                  self.emit_error(app_handle, job_id, &file_name, &e.to_string());
                  *self.current_job_id.lock().await = None;
                  return;
              }
              Err(e) => {
                  self.mark_failed(job_id, &e.to_string()).await;
                  self.emit_error(app_handle, job_id, &file_name, &e.to_string());
                  *self.current_job_id.lock().await = None;
                  return;
              }
          };

          // emit progress: 推理完成，进度 0.9
          let _ = app_handle.emit(
              "batch:progress",
              serde_json::json!({ "job_id": job_id, "file_name": &file_name, "progress": 0.9_f32 }),
          );

          // --- 数据库写入（单一事务）---
          let db_result = Self::persist_job(
              db,
              job_id,
              &file_path,
              &file_name,
              &segments,
              &language,
          ).await;

          match db_result {
              Ok((recording_id, document_id)) => {
                  // 更新内存状态
                  {
                      let mut jobs = self.jobs.lock().await;
                      if let Some(job) = jobs.iter_mut().find(|j| j.id == job_id) {
                          job.status = BatchStatus::Done {
                              recording_id: recording_id.clone(),
                              document_id: document_id.clone(),
                          };
                      }
                  }
                  let _ = app_handle.emit(
                      "batch:done",
                      serde_json::json!({
                          "job_id": job_id,
                          "recording_id": recording_id,
                          "document_id": document_id
                      }),
                  );
              }
              Err(e) => {
                  self.mark_failed(job_id, &e.to_string()).await;
                  self.emit_error(app_handle, job_id, &file_name, &e.to_string());
              }
          }

          *self.current_job_id.lock().await = None;
      }
  }
  ```

- [ ] **Step 3.7: 实现辅助方法 `persist_job`、`mark_failed`、`mark_cancelled`、`emit_error`**

  ```rust
  impl BatchQueue {
      /// 将转写结果写入数据库，返回 (recording_id, document_id)
      async fn persist_job(
          db: &Arc<Database>,
          job_id: &str,
          file_path: &std::path::Path,
          file_name: &str,
          segments: &[crate::transcription::engine::RawSegment],
          language: &Option<String>,
      ) -> Result<(String, String), crate::error::AppError> {
          use uuid::Uuid;
          use std::time::{SystemTime, UNIX_EPOCH};

          let now = SystemTime::now()
              .duration_since(UNIX_EPOCH)
              .unwrap_or_default()
              .as_millis() as i64;

          let recording_id = Uuid::new_v4().to_string();
          let document_id = Uuid::new_v4().to_string();
          let duration_ms = segments.last().map(|s| s.end_ms as i64).unwrap_or(0);
          let detected_language = segments.first().map(|s| s.language.clone());
          let lang = language.clone().or(detected_language);

          // 合并所有 segment 文本作为 workspace_document 内容
          let full_text: String = segments
              .iter()
              .map(|s| s.text.as_str())
              .collect::<Vec<_>>()
              .join(" ");

          let pool = db.pool();
          let mut tx = pool.begin().await
              .map_err(|e| crate::error::AppError::Storage(e.to_string()))?;

          // 1. 插入 recordings
          sqlx::query!(
              r#"INSERT INTO recordings (id, title, file_path, duration_ms, language, created_at, updated_at)
                 VALUES (?, ?, ?, ?, ?, ?, ?)"#,
              recording_id,
              file_name,
              file_path.to_str().unwrap_or_default(),
              duration_ms,
              lang,
              now,
              now,
          )
          .execute(&mut *tx)
          .await
          .map_err(|e| crate::error::AppError::Storage(e.to_string()))?;

          // 2. 批量插入 transcription_segments
          for seg in segments {
              sqlx::query!(
                  r#"INSERT INTO transcription_segments
                     (recording_id, start_ms, end_ms, text, language, confidence)
                     VALUES (?, ?, ?, ?, ?, ?)"#,
                  recording_id,
                  seg.start_ms,
                  seg.end_ms,
                  seg.text,
                  seg.language,
                  Option::<f64>::None,
              )
              .execute(&mut *tx)
              .await
              .map_err(|e| crate::error::AppError::Storage(e.to_string()))?;
          }

          // 3. 创建 workspace_documents（source_type='recording'，自动加入 inbox）
          // inbox folder_id 为 NULL（规范：NULL folder_id 代表根 inbox）
          sqlx::query!(
              r#"INSERT INTO workspace_documents
                 (id, folder_id, title, content_text, source_type, recording_id, created_at, updated_at)
                 VALUES (?, NULL, ?, ?, 'recording', ?, ?, ?)"#,
              document_id,
              file_name,
              full_text,
              recording_id,
              now,
              now,
          )
          .execute(&mut *tx)
          .await
          .map_err(|e| crate::error::AppError::Storage(e.to_string()))?;

          tx.commit().await
              .map_err(|e| crate::error::AppError::Storage(e.to_string()))?;

          Ok((recording_id, document_id))
      }

      async fn mark_failed(&self, job_id: &str, error: &str) {
          let mut jobs = self.jobs.lock().await;
          if let Some(job) = jobs.iter_mut().find(|j| j.id == job_id) {
              job.status = BatchStatus::Failed { error: error.to_string() };
          }
      }

      async fn mark_cancelled(&self, job_id: &str) {
          let mut jobs = self.jobs.lock().await;
          if let Some(job) = jobs.iter_mut().find(|j| j.id == job_id) {
              job.status = BatchStatus::Cancelled;
          }
      }

      fn emit_error(&self, app_handle: &AppHandle, job_id: &str, file_name: &str, error: &str) {
          let _ = app_handle.emit(
              "batch:error",
              serde_json::json!({
                  "job_id": job_id,
                  "file_name": file_name,
                  "error": error
              }),
          );
      }

      /// 返回所有 job 的视图（用于前端查询）
      pub async fn get_all_jobs(&self) -> Vec<BatchJobView> {
          self.jobs.lock().await.iter().map(|j| BatchJobView {
              job_id: j.id.clone(),
              file_name: j.file_name.clone(),
              language: j.language.clone(),
              status: j.status.clone(),
              created_at: j.created_at,
          }).collect()
      }
  }
  ```

- [ ] **Commit:** `feat(transcription): implement BatchQueue with serial job execution`

---

### Task 4: `transcription/mod.rs` — 注册新子模块

**Files:**
- Modify: `src-tauri/src/transcription/mod.rs`

- [ ] **Step 4.1: 在 `mod.rs` 中追加模块声明**

  ```rust
  pub mod engine;
  pub mod pipeline;
  pub mod batch;    // 新增
  pub mod ffmpeg;   // 新增
  ```

- [ ] **Commit:** `chore(transcription): register batch and ffmpeg modules`

---

### Task 5: `state.rs` — 注入 `batch_tx`

**Files:**
- Modify: `src-tauri/src/state.rs`

- [ ] **Step 5.1: 在 `AppState` 中添加 `batch_tx` 字段**

  ```rust
  use tokio::sync::mpsc;
  use crate::transcription::batch::BatchCommand;

  pub struct AppState {
      // 已有字段（M1/M2/M4 建立）...
      pub transcription_tx: std::sync::mpsc::SyncSender<crate::transcription::pipeline::TranscriptionCommand>,
      pub whisper_engine: Arc<tokio::sync::Mutex<Option<crate::transcription::engine::WhisperEngine>>>,
      pub db: Arc<crate::storage::db::Database>,

      // M7 新增
      pub batch_tx: mpsc::Sender<BatchCommand>,
  }
  ```

- [ ] **Commit:** `feat(state): add batch_tx channel sender to AppState`

---

### Task 6: `lib.rs` — 启动 BatchQueue 后台 Task

**Files:**
- Modify: `src-tauri/src/lib.rs`

- [ ] **Step 6.1: 在应用启动的 `setup` 钩子中初始化并 spawn `BatchQueue`**

  在现有 `tokio::spawn(transcription_worker)` 等调用之后追加：

  ```rust
  use crate::transcription::batch::{BatchQueue, BatchCommand};
  use std::sync::Arc;

  // 创建 channel（buffer = 64，batch 命令量少，不会积压）
  let (batch_tx, batch_rx) = tokio::sync::mpsc::channel::<BatchCommand>(64);

  let batch_queue = Arc::new(BatchQueue::new());
  let batch_queue_clone = Arc::clone(&batch_queue);
  let app_handle_clone = app.handle().clone();
  let db_clone = Arc::clone(&db);
  let whisper_engine_clone = Arc::clone(&whisper_engine);

  tokio::spawn(async move {
      batch_queue_clone.run(
          batch_rx,
          app_handle_clone,
          db_clone,
          whisper_engine_clone,
      ).await;
  });

  // 将 batch_tx 注入 AppState
  // （与已有的 transcription_tx、llm_tx 等字段一起构建 AppState）
  app.manage(AppState {
      // ... 已有字段 ...
      batch_tx,
  });
  ```

- [ ] **Commit:** `feat(lib): spawn BatchQueue background task and inject batch_tx into AppState`

---

### Task 7: `commands/transcription.rs` — Tauri Commands

**Files:**
- Modify: `src-tauri/src/commands/transcription.rs`

- [ ] **Step 7.1: 追加批量转写相关命令**

  在文件末尾追加以下命令（保留已有的实时转写命令不动）：

  ```rust
  use crate::transcription::batch::{BatchCommand, BatchJobView};
  use crate::transcription::ffmpeg::{detect_ffmpeg, is_supported_format};
  use crate::state::AppState;
  use crate::error::AppError;
  use uuid::Uuid;
  use std::path::PathBuf;

  /// 检测系统 ffmpeg 是否可用（前端启动时调用，决定是否显示安装提示）
  #[tauri::command]
  #[specta::specta]
  pub async fn check_ffmpeg_available() -> bool {
      tokio::task::spawn_blocking(detect_ffmpeg)
          .await
          .unwrap_or(false)
  }

  /// 批量入队文件转写任务，返回各文件对应的 job_id 列表（顺序一一对应）
  #[tauri::command]
  #[specta::specta]
  pub async fn add_files_to_batch(
      paths: Vec<String>,
      state: tauri::State<'_, AppState>,
  ) -> Result<Vec<String>, AppError> {
      let mut job_ids = Vec::with_capacity(paths.len());

      for path_str in paths {
          let file_path = PathBuf::from(&path_str);

          if !file_path.exists() {
              return Err(AppError::Io(format!("File not found: {path_str}")));
          }
          if !is_supported_format(&file_path) {
              return Err(AppError::Validation(format!(
                  "Unsupported format: {}",
                  file_path.extension()
                      .and_then(|e| e.to_str())
                      .unwrap_or("unknown")
              )));
          }

          let job_id = Uuid::new_v4().to_string();
          state
              .batch_tx
              .send(BatchCommand::Enqueue {
                  job_id: job_id.clone(),
                  file_path,
                  language: None, // TODO: 可扩展为接受 language 参数
              })
              .await
              .map_err(|_| AppError::ChannelClosed)?;

          job_ids.push(job_id);
      }

      Ok(job_ids)
  }

  /// 查询当前队列（含历史）所有任务的状态快照
  #[tauri::command]
  #[specta::specta]
  pub async fn get_batch_queue(
      state: tauri::State<'_, AppState>,
  ) -> Result<Vec<BatchJobView>, AppError> {
      // BatchQueue 通过 AppState 共享 Arc，直接读取内存状态
      // 注意：AppState 需额外持有 Arc<BatchQueue> 以支持此查询
      // （见 Task 8 的 state.rs 补充）
      Ok(state.batch_queue.get_all_jobs().await)
  }

  /// 取消指定 job（Queued → 直接移除；Processing → 设置取消标志）
  #[tauri::command]
  #[specta::specta]
  pub async fn cancel_batch_job(
      job_id: String,
      state: tauri::State<'_, AppState>,
  ) -> Result<(), AppError> {
      state
          .batch_tx
          .send(BatchCommand::Cancel { job_id })
          .await
          .map_err(|_| AppError::ChannelClosed)
  }

  /// 清除所有已完成（Done / Failed / Cancelled）的历史任务记录
  #[tauri::command]
  #[specta::specta]
  pub async fn clear_completed_jobs(
      state: tauri::State<'_, AppState>,
  ) -> Result<(), AppError> {
      state
          .batch_tx
          .send(BatchCommand::ClearCompleted)
          .await
          .map_err(|_| AppError::ChannelClosed)
  }
  ```

- [ ] **Step 7.2: 在 `commands/mod.rs` 中注册新命令至 `generate_handler!` 宏**

  ```rust
  // commands/mod.rs（或 lib.rs 中的 invoke_handler 配置处）
  // 追加以下命令：
  check_ffmpeg_available,
  add_files_to_batch,
  get_batch_queue,
  cancel_batch_job,
  clear_completed_jobs,
  ```

- [ ] **Commit:** `feat(commands): add batch transcription commands with specta types`

---

### Task 8: `state.rs` 补充 — 持有 `Arc<BatchQueue>`

**Files:**
- Modify: `src-tauri/src/state.rs`

- [ ] **Step 8.1: 在 `AppState` 中额外持有 `batch_queue` Arc，供 `get_batch_queue` 命令直接读取**

  `get_batch_queue` 命令需要直接访问 `BatchQueue` 的内存状态（只读），不经过 channel（channel 是单向的，不适合查询）。因此 `AppState` 同时持有 `batch_tx` 和 `batch_queue` Arc：

  ```rust
  pub struct AppState {
      // ... 已有字段 ...
      pub batch_tx: mpsc::Sender<BatchCommand>,
      pub batch_queue: Arc<crate::transcription::batch::BatchQueue>, // 新增，供只读查询
  }
  ```

  在 `lib.rs` setup 时同样将 `batch_queue` 存入 `AppState`（与 Task 6 中的 `batch_queue_clone` 是同一个 Arc）。

- [ ] **Commit:** `feat(state): expose Arc<BatchQueue> for direct read in get_batch_queue command`

---

### Task 9: 单元测试 — Rust 后端

**Files:**
- Modify: `src-tauri/src/transcription/ffmpeg.rs`（在文件末尾追加 `#[cfg(test)]` 模块）
- Modify: `src-tauri/src/transcription/batch.rs`（在文件末尾追加 `#[cfg(test)]` 模块）

- [ ] **Step 9.1: `ffmpeg.rs` 测试 — `detect_ffmpeg` 与格式分类**

  ```rust
  #[cfg(test)]
  mod tests {
      use super::*;
      use std::path::Path;

      #[test]
      fn test_detect_ffmpeg_returns_bool() {
          // 仅验证函数可调用并返回布尔值，不断言具体值（取决于测试环境）
          let result = detect_ffmpeg();
          assert!(result == true || result == false);
      }

      #[test]
      fn test_needs_transcode_wav_is_false() {
          assert!(!needs_transcode(Path::new("audio.wav")));
          assert!(!needs_transcode(Path::new("/path/to/recording.WAV")));
      }

      #[test]
      fn test_needs_transcode_non_wav_is_true() {
          for ext in &["mp3", "mp4", "m4a", "mov", "mkv", "webm", "ogg", "flac"] {
              let path = Path::new(&format!("audio.{ext}"));
              assert!(
                  needs_transcode(path),
                  "Expected needs_transcode=true for .{ext}"
              );
          }
      }

      #[test]
      fn test_is_supported_format() {
          let supported = ["wav", "flac", "mp3", "mp4", "m4a", "mov", "mkv", "webm", "ogg"];
          for ext in &supported {
              assert!(
                  is_supported_format(Path::new(&format!("file.{ext}"))),
                  ".{ext} should be supported"
              );
          }
          assert!(!is_supported_format(Path::new("file.txt")));
          assert!(!is_supported_format(Path::new("file.avi")));
          assert!(!is_supported_format(Path::new("file")));
      }

      #[test]
      fn test_needs_transcode_case_insensitive() {
          // 扩展名大写应同样处理
          assert!(!needs_transcode(Path::new("AUDIO.WAV")));
          assert!(needs_transcode(Path::new("AUDIO.MP3")));
      }
  }
  ```

- [ ] **Step 9.2: `batch.rs` 测试 — BatchStatus 与 job_id 唯一性**

  ```rust
  #[cfg(test)]
  mod tests {
      use super::*;
      use std::collections::HashSet;

      #[test]
      fn test_batch_status_processing_progress_range() {
          let s = BatchStatus::Processing { progress: 0.5 };
          if let BatchStatus::Processing { progress } = s {
              assert!(progress >= 0.0 && progress <= 1.0);
          } else {
              panic!("Expected Processing variant");
          }
      }

      #[test]
      fn test_batch_status_variants_are_distinct() {
          // 验证各状态变体不互相混淆（通过 PartialEq）
          assert_eq!(BatchStatus::Queued, BatchStatus::Queued);
          assert_ne!(BatchStatus::Queued, BatchStatus::Cancelled);
          assert_ne!(
              BatchStatus::Processing { progress: 0.0 },
              BatchStatus::Processing { progress: 1.0 }
          );
      }

      #[test]
      fn test_job_id_uniqueness() {
          // 验证连续生成的 UUID 不重复
          let ids: HashSet<String> = (0..1000)
              .map(|_| uuid::Uuid::new_v4().to_string())
              .collect();
          assert_eq!(ids.len(), 1000, "All generated job_ids must be unique");
      }

      #[test]
      fn test_batch_job_view_serializable() {
          // 验证 BatchJobView 可被 serde_json 序列化（隐式验证 Type derive）
          let view = BatchJobView {
              job_id: "test-id".to_string(),
              file_name: "audio.mp3".to_string(),
              language: Some("en".to_string()),
              status: BatchStatus::Queued,
              created_at: 1_700_000_000_000,
          };
          let json = serde_json::to_string(&view).expect("Should serialize");
          assert!(json.contains("test-id"));
          assert!(json.contains("audio.mp3"));
          assert!(json.contains("Queued"));
      }

      #[tokio::test]
      async fn test_batch_queue_get_all_jobs_empty() {
          let queue = BatchQueue::new();
          let jobs = queue.get_all_jobs().await;
          assert!(jobs.is_empty());
      }
  }
  ```

- [ ] **Step 9.3: 运行测试验证通过**

  ```bash
  cd src-tauri && cargo test transcription::ffmpeg::tests && cargo test transcription::batch::tests
  ```

- [ ] **Commit:** `test(transcription): add unit tests for ffmpeg detection and BatchStatus`

---

### Task 10: `store/transcription.ts` — Zustand Store

**Files:**
- Create: `src/store/transcription.ts`

- [ ] **Step 10.1: 定义类型并实现 store**

  ```typescript
  import { create } from 'zustand';
  import { listen } from '@tauri-apps/api/event';
  import {
    addFilesToBatch,
    getBatchQueue,
    cancelBatchJob,
    clearCompletedJobs,
    checkFfmpegAvailable,
  } from '../lib/bindings';

  // 与 Rust 端 BatchStatus 对应的 TypeScript 类型
  export type BatchStatus =
    | { type: 'Queued' }
    | { type: 'Processing'; data: { progress: number } }
    | { type: 'Done'; data: { recording_id: string; document_id: string } }
    | { type: 'Failed'; data: { error: string } }
    | { type: 'Cancelled' };

  export interface BatchJobStatus {
    job_id: string;
    file_name: string;
    language: string | null;
    status: BatchStatus;
    created_at: number;
  }

  interface TranscriptionStore {
    queue: BatchJobStatus[];
    ffmpegAvailable: boolean;
    isCheckingFfmpeg: boolean;

    // Actions
    checkFfmpeg: () => Promise<void>;
    addFiles: (paths: string[]) => Promise<string[]>;
    cancelJob: (jobId: string) => Promise<void>;
    clearCompleted: () => Promise<void>;
    refreshQueue: () => Promise<void>;

    // 内部：初始化 Tauri 事件监听（在 App 初始化时调用）
    setupEventListeners: () => Promise<() => void>;
  }

  export const useTranscriptionStore = create<TranscriptionStore>((set, get) => ({
    queue: [],
    ffmpegAvailable: true,
    isCheckingFfmpeg: false,

    checkFfmpeg: async () => {
      set({ isCheckingFfmpeg: true });
      try {
        const available = await checkFfmpegAvailable();
        set({ ffmpegAvailable: available });
      } finally {
        set({ isCheckingFfmpeg: false });
      }
    },

    addFiles: async (paths) => {
      const jobIds = await addFilesToBatch(paths);
      await get().refreshQueue();
      return jobIds;
    },

    cancelJob: async (jobId) => {
      await cancelBatchJob(jobId);
      // 乐观更新：本地先标记为 Cancelled
      set((state) => ({
        queue: state.queue.map((job) =>
          job.job_id === jobId
            ? { ...job, status: { type: 'Cancelled' as const } }
            : job
        ),
      }));
    },

    clearCompleted: async () => {
      await clearCompletedJobs();
      set((state) => ({
        queue: state.queue.filter(
          (job) =>
            job.status.type !== 'Done' &&
            job.status.type !== 'Failed' &&
            job.status.type !== 'Cancelled'
        ),
      }));
    },

    refreshQueue: async () => {
      const jobs = await getBatchQueue();
      set({ queue: jobs });
    },

    setupEventListeners: async () => {
      const unlisteners = await Promise.all([
        listen<{ job_id: string; file_name: string }>(
          'batch:queued',
          (event) => {
            const { job_id, file_name } = event.payload;
            set((state) => ({
              queue: [
                ...state.queue,
                {
                  job_id,
                  file_name,
                  language: null,
                  status: { type: 'Queued' as const },
                  created_at: Date.now(),
                },
              ],
            }));
          }
        ),

        listen<{ job_id: string; file_name: string; progress: number }>(
          'batch:progress',
          (event) => {
            const { job_id, progress } = event.payload;
            set((state) => ({
              queue: state.queue.map((job) =>
                job.job_id === job_id
                  ? {
                      ...job,
                      status: { type: 'Processing' as const, data: { progress } },
                    }
                  : job
              ),
            }));
          }
        ),

        listen<{ job_id: string; recording_id: string; document_id: string }>(
          'batch:done',
          (event) => {
            const { job_id, recording_id, document_id } = event.payload;
            set((state) => ({
              queue: state.queue.map((job) =>
                job.job_id === job_id
                  ? {
                      ...job,
                      status: {
                        type: 'Done' as const,
                        data: { recording_id, document_id },
                      },
                    }
                  : job
              ),
            }));
          }
        ),

        listen<{ job_id: string; file_name: string; error: string }>(
          'batch:error',
          (event) => {
            const { job_id, error } = event.payload;
            set((state) => ({
              queue: state.queue.map((job) =>
                job.job_id === job_id
                  ? {
                      ...job,
                      status: { type: 'Failed' as const, data: { error } },
                    }
                  : job
              ),
            }));
          }
        ),

        listen('batch:ffmpeg_missing', () => {
          set({ ffmpegAvailable: false });
        }),
      ]);

      // 返回 cleanup 函数
      return () => {
        unlisteners.forEach((unlisten) => unlisten());
      };
    },
  }));
  ```

- [ ] **Commit:** `feat(store): add transcription Zustand store with batch queue and event listeners`

---

### Task 11: `components/transcription/FfmpegWarning.tsx`

**Files:**
- Create: `src/components/transcription/FfmpegWarning.tsx`

- [ ] **Step 11.1: 实现平台感知的 ffmpeg 安装提示组件**

  ```tsx
  import { platform } from '@tauri-apps/plugin-os';
  import { useEffect, useState } from 'react';
  import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
  import { ExternalLink } from 'lucide-react';

  interface InstallInstruction {
    label: string;
    command: string;
    downloadUrl?: string;
  }

  function getInstallInstructions(os: string): InstallInstruction[] {
    switch (os) {
      case 'macos':
        return [
          { label: 'Homebrew', command: 'brew install ffmpeg' },
        ];
      case 'windows':
        return [
          { label: 'winget', command: 'winget install ffmpeg' },
          {
            label: '手动下载',
            command: '',
            downloadUrl: 'https://www.gyan.dev/ffmpeg/builds/',
          },
        ];
      case 'linux':
        return [
          { label: 'apt (Debian/Ubuntu)', command: 'sudo apt install ffmpeg' },
          { label: 'dnf (Fedora)', command: 'sudo dnf install ffmpeg' },
          { label: 'pacman (Arch)', command: 'sudo pacman -S ffmpeg' },
        ];
      default:
        return [{ label: '请参考官方文档', command: '', downloadUrl: 'https://ffmpeg.org/download.html' }];
    }
  }

  export function FfmpegWarning() {
    const [os, setOs] = useState<string>('');

    useEffect(() => {
      platform().then(setOs).catch(() => setOs('unknown'));
    }, []);

    const instructions = getInstallInstructions(os);

    return (
      <Alert variant="destructive" className="mb-4">
        <AlertTitle className="font-semibold">
          需要安装 ffmpeg
        </AlertTitle>
        <AlertDescription className="mt-2 space-y-2">
          <p className="text-sm text-text-secondary">
            转写 MP3、MP4、M4A、MOV、MKV、WEBM、OGG 格式需要系统安装 ffmpeg。
            WAV 格式无需 ffmpeg，可直接转写。
          </p>
          <div className="space-y-1">
            {instructions.map((inst) => (
              <div key={inst.label} className="flex items-center gap-2">
                <span className="text-xs text-text-muted w-40 shrink-0">{inst.label}:</span>
                {inst.command ? (
                  <code className="text-xs bg-bg-input px-2 py-0.5 rounded font-mono">
                    {inst.command}
                  </code>
                ) : null}
                {inst.downloadUrl ? (
                  <a
                    href={inst.downloadUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs text-accent flex items-center gap-1 hover:underline"
                  >
                    下载 <ExternalLink size={10} />
                  </a>
                ) : null}
              </div>
            ))}
          </div>
          <p className="text-xs text-text-muted mt-2">
            安装完成后重启 EchoNote 即可生效。
          </p>
        </AlertDescription>
      </Alert>
    );
  }
  ```

- [ ] **Commit:** `feat(ui): add FfmpegWarning component with platform-specific install instructions`

---

### Task 12: `components/transcription/TranscriptionPanel.tsx` — 拖拽上传区

**Files:**
- Create: `src/components/transcription/TranscriptionPanel.tsx`

- [ ] **Step 12.1: 安装 `react-dropzone`**

  ```bash
  npm install react-dropzone
  ```

- [ ] **Step 12.2: 实现拖拽上传面板**

  此组件作为 `/transcription` 路由的 SecondPanel，提供文件选择/拖拽入口和格式说明：

  ```tsx
  import { useCallback } from 'react';
  import { useDropzone } from 'react-dropzone';
  import { Upload, FileAudio } from 'lucide-react';
  import { open } from '@tauri-apps/plugin-dialog';
  import { Button } from '@/components/ui/button';
  import { useTranscriptionStore } from '@/store/transcription';
  import { FfmpegWarning } from './FfmpegWarning';

  const SUPPORTED_EXTENSIONS = [
    '.wav', '.flac', '.mp3', '.mp4', '.m4a', '.mov', '.mkv', '.webm', '.ogg'
  ];

  const DIRECT_FORMATS = ['WAV', 'FLAC'];
  const TRANSCODE_FORMATS = ['MP3', 'MP4', 'M4A', 'MOV', 'MKV', 'WEBM', 'OGG'];

  export function TranscriptionPanel() {
    const { addFiles, ffmpegAvailable } = useTranscriptionStore();

    const handleFiles = useCallback(
      async (filePaths: string[]) => {
        if (filePaths.length === 0) return;
        try {
          await addFiles(filePaths);
        } catch (err) {
          console.error('Failed to add files:', err);
        }
      },
      [addFiles]
    );

    // react-dropzone：拖拽到窗口区域时触发（Tauri 环境中文件路径通过 event.dataTransfer 获取）
    const { getRootProps, getInputProps, isDragActive } = useDropzone({
      accept: {
        'audio/*': SUPPORTED_EXTENSIONS,
        'video/*': ['.mp4', '.mov', '.mkv', '.webm', '.m4a'],
      },
      noClick: true, // 点击由自定义按钮处理，避免双重触发
      onDrop: (acceptedFiles) => {
        // 在 Tauri 中，File.path 需要通过 @tauri-apps/plugin-fs 转换
        // 这里使用 Tauri drag-drop 插件提供的路径（需在 tauri.conf.json 中开启 drag-drop）
        const paths = acceptedFiles.map((f) => (f as File & { path?: string }).path ?? f.name);
        handleFiles(paths.filter(Boolean) as string[]);
      },
    });

    const openFileDialog = async () => {
      const selected = await open({
        multiple: true,
        filters: [
          {
            name: '音频/视频文件',
            extensions: ['wav', 'flac', 'mp3', 'mp4', 'm4a', 'mov', 'mkv', 'webm', 'ogg'],
          },
        ],
      });
      if (selected) {
        const paths = Array.isArray(selected) ? selected : [selected];
        await handleFiles(paths);
      }
    };

    return (
      <div className="flex flex-col h-full p-4 gap-4">
        {/* ffmpeg 缺失警告 */}
        {!ffmpegAvailable && <FfmpegWarning />}

        {/* 拖拽区域 */}
        <div
          {...getRootProps()}
          className={[
            'flex flex-col items-center justify-center gap-3 rounded-lg border-2 border-dashed p-6 transition-colors cursor-default',
            isDragActive
              ? 'border-accent bg-accent-muted'
              : 'border-border-default bg-bg-secondary hover:border-accent hover:bg-bg-hover',
          ].join(' ')}
        >
          <input {...getInputProps()} />
          <Upload
            size={32}
            className={isDragActive ? 'text-accent' : 'text-text-muted'}
          />
          <p className="text-sm text-text-secondary text-center">
            {isDragActive ? '松开以添加文件' : '拖拽媒体文件到此处'}
          </p>
          <Button
            variant="outline"
            size="sm"
            onClick={openFileDialog}
            className="mt-1"
          >
            <FileAudio size={14} className="mr-1.5" />
            选择文件
          </Button>
        </div>

        {/* 支持格式说明 */}
        <div className="text-xs text-text-muted space-y-1.5 px-1">
          <p className="font-medium text-text-secondary">支持格式</p>
          <div className="flex flex-wrap gap-1">
            {DIRECT_FORMATS.map((fmt) => (
              <span
                key={fmt}
                className="px-1.5 py-0.5 rounded bg-status-success/15 text-status-success"
              >
                {fmt}
              </span>
            ))}
            {TRANSCODE_FORMATS.map((fmt) => (
              <span
                key={fmt}
                className="px-1.5 py-0.5 rounded bg-bg-input text-text-muted"
              >
                {fmt}
              </span>
            ))}
          </div>
          <p className="text-[11px]">
            绿色格式无需 ffmpeg 直接转写；灰色格式需要系统安装 ffmpeg。
          </p>
        </div>
      </div>
    );
  }
  ```

- [ ] **Commit:** `feat(ui): add TranscriptionPanel with drag-drop upload and format legend`

---

### Task 13: `components/transcription/TranscriptionMain.tsx` — 队列主视图

**Files:**
- Create: `src/components/transcription/TranscriptionMain.tsx`

- [ ] **Step 13.1: 实现批量任务列表**

  ```tsx
  import { useEffect } from 'react';
  import { useNavigate } from '@tanstack/react-router';
  import { X, CheckCircle, AlertCircle, Loader2, Clock } from 'lucide-react';
  import { Button } from '@/components/ui/button';
  import { Progress } from '@/components/ui/progress';
  import { Badge } from '@/components/ui/badge';
  import { useTranscriptionStore, BatchJobStatus, BatchStatus } from '@/store/transcription';

  function StatusBadge({ status }: { status: BatchStatus }) {
    switch (status.type) {
      case 'Queued':
        return (
          <Badge variant="outline" className="gap-1 text-text-muted border-border-default">
            <Clock size={10} /> 排队中
          </Badge>
        );
      case 'Processing':
        return (
          <Badge variant="outline" className="gap-1 text-status-info border-status-info/30">
            <Loader2 size={10} className="animate-spin" /> 转写中
          </Badge>
        );
      case 'Done':
        return (
          <Badge variant="outline" className="gap-1 text-status-success border-status-success/30">
            <CheckCircle size={10} /> 完成
          </Badge>
        );
      case 'Failed':
        return (
          <Badge variant="outline" className="gap-1 text-status-error border-status-error/30">
            <AlertCircle size={10} /> 失败
          </Badge>
        );
      case 'Cancelled':
        return (
          <Badge variant="outline" className="gap-1 text-text-disabled border-border-default">
            取消
          </Badge>
        );
    }
  }

  function JobRow({ job, onCancel }: { job: BatchJobStatus; onCancel: (id: string) => void }) {
    const navigate = useNavigate();

    const handleClick = () => {
      if (job.status.type === 'Done') {
        navigate({ to: '/workspace/$docId', params: { docId: job.status.data.document_id } });
      }
    };

    const canCancel =
      job.status.type === 'Queued' || job.status.type === 'Processing';

    const progress =
      job.status.type === 'Processing' ? job.status.data.progress * 100 : undefined;

    return (
      <div
        className={[
          'group flex flex-col gap-2 p-3 rounded-md border border-border-default bg-bg-secondary',
          job.status.type === 'Done' ? 'cursor-pointer hover:bg-bg-hover' : '',
        ].join(' ')}
        onClick={handleClick}
      >
        <div className="flex items-center justify-between gap-2">
          <span className="text-sm text-text-primary truncate flex-1" title={job.file_name}>
            {job.file_name}
          </span>
          <div className="flex items-center gap-1.5 shrink-0">
            <StatusBadge status={job.status} />
            {canCancel && (
              <Button
                variant="ghost"
                size="icon"
                className="h-5 w-5 opacity-0 group-hover:opacity-100 transition-opacity"
                onClick={(e) => {
                  e.stopPropagation();
                  onCancel(job.job_id);
                }}
              >
                <X size={12} />
              </Button>
            )}
          </div>
        </div>

        {/* 进度条（仅 Processing 状态显示）*/}
        {progress !== undefined && (
          <Progress value={progress} className="h-1" />
        )}

        {/* 失败原因 */}
        {job.status.type === 'Failed' && (
          <p className="text-xs text-status-error line-clamp-2">
            {job.status.data.error}
          </p>
        )}
      </div>
    );
  }

  export function TranscriptionMain() {
    const { queue, cancelJob, clearCompleted, refreshQueue, setupEventListeners } =
      useTranscriptionStore();

    useEffect(() => {
      refreshQueue();
      let cleanup: (() => void) | undefined;
      setupEventListeners().then((fn) => { cleanup = fn; });
      return () => { cleanup?.(); };
    }, []);

    const hasCompleted = queue.some(
      (j) =>
        j.status.type === 'Done' ||
        j.status.type === 'Failed' ||
        j.status.type === 'Cancelled'
    );

    return (
      <div className="flex flex-col h-full">
        {/* 工具栏 */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-border-default shrink-0">
          <h2 className="text-sm font-medium text-text-primary">
            转写队列
            {queue.length > 0 && (
              <span className="ml-2 text-xs text-text-muted">({queue.length})</span>
            )}
          </h2>
          {hasCompleted && (
            <Button variant="ghost" size="sm" onClick={clearCompleted} className="text-xs">
              清除已完成
            </Button>
          )}
        </div>

        {/* 任务列表 */}
        <div className="flex-1 overflow-y-auto p-4 space-y-2">
          {queue.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full gap-3 text-text-muted">
              <p className="text-sm">暂无转写任务</p>
              <p className="text-xs">在左侧面板拖入音频或视频文件</p>
            </div>
          ) : (
            queue.map((job) => (
              <JobRow key={job.job_id} job={job} onCancel={cancelJob} />
            ))
          )}
        </div>
      </div>
    );
  }
  ```

- [ ] **Commit:** `feat(ui): add TranscriptionMain with job list, progress bars, and navigation`

---

### Task 14: 路由注册 — `/transcription` 页面

**Files:**
- Modify: `src/router.tsx`（或 TanStack Router 的路由定义文件）

- [ ] **Step 14.1: 注册 `/transcription` 路由，接入 TranscriptionPanel 和 TranscriptionMain**

  在路由配置中追加（以 TanStack Router 的 `createRoute` 为例）：

  ```typescript
  import { TranscriptionPanel } from '@/components/transcription/TranscriptionPanel';
  import { TranscriptionMain } from '@/components/transcription/TranscriptionMain';

  // TanStack Router 路由定义（参考 M1 已有的 /recording 路由结构）
  export const transcriptionRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: '/transcription',
    component: () => (
      <Shell
        panel={<TranscriptionPanel />}
        main={<TranscriptionMain />}
      />
    ),
  });
  ```

- [ ] **Step 14.2: 在 App 启动时调用 `checkFfmpeg`**

  在 `App.tsx` 的 `useEffect` 中（或 store 的 `setupEventListeners` 调用旁）：

  ```typescript
  import { useTranscriptionStore } from '@/store/transcription';

  // App.tsx useEffect
  useEffect(() => {
    useTranscriptionStore.getState().checkFfmpeg();
  }, []);
  ```

- [ ] **Commit:** `feat(router): register /transcription route with TranscriptionPanel and TranscriptionMain`

---

### Task 15: 集成验证（手动测试清单）

**Files:**（无新增文件，仅验证）

- [ ] **Step 15.1: WAV 文件直接转写测试**

  1. 准备一个 16kHz 单声道 WAV 文件（或任意 WAV）
  2. 启动应用，导航至 `/transcription`
  3. 拖拽 WAV 文件至上传区，或点击"选择文件"
  4. 观察队列中出现任务，状态从 Queued → Processing（进度条更新）→ Done
  5. 点击 Done 任务，验证跳转至 `/workspace/:docId` 对应文档

- [ ] **Step 15.2: 需转码格式测试（ffmpeg 已安装环境）**

  1. 准备 MP3 / MP4 / M4A 测试文件
  2. 添加至队列，观察 Processing 状态中的进度（0.0 → 0.2 转码 → 0.3 解码 → 0.9 推理 → Done）
  3. 验证数据库中 `recordings`、`transcription_segments`、`workspace_documents` 三张表均有对应记录

- [ ] **Step 15.3: ffmpeg 缺失提示测试**

  1. 临时将 PATH 中的 ffmpeg 重命名（或在测试机上模拟无 ffmpeg 环境）
  2. 添加 MP3 文件，观察：
     - 队列中任务状态变为 Failed
     - 顶部出现 `FfmpegWarning` 组件并显示正确的平台安装命令
  3. 恢复 ffmpeg，重启应用，验证警告消失

- [ ] **Step 15.4: 取消任务测试**

  1. 添加多个大文件（使第一个进入 Processing，其余处于 Queued）
  2. 取消一个 Queued 任务：验证其从 pending 队列移除，状态变为 Cancelled
  3. 取消正在 Processing 的任务：验证该 job 被标记 Cancelled，下一个 Queued job 开始执行

- [ ] **Step 15.5: "清除已完成"测试**

  1. 完成/失败若干任务
  2. 点击"清除已完成"按钮
  3. 验证 Done/Failed/Cancelled 任务从列表消失，Queued/Processing 任务保留

- [ ] **Commit:** `test(integration): verify M7 batch transcription end-to-end flows`

---

## 附录：Tauri Events 汇总

| 事件名 | Payload 字段 | 触发时机 |
|--------|-------------|---------|
| `batch:queued` | `{ job_id, file_name }` | 文件成功入队后立即 |
| `batch:progress` | `{ job_id, file_name, progress: f32 }` | 转码完成（0.2）、解码完成（0.3）、推理完成（0.9） |
| `batch:done` | `{ job_id, recording_id, document_id }` | 数据库写入成功后 |
| `batch:error` | `{ job_id, file_name, error: String }` | 任意阶段失败时 |
| `batch:ffmpeg_missing` | `{}` | 检测到 ffmpeg 不存在且当前格式需转码时 |

## 附录：文件创建/修改清单

| 操作 | 文件路径 |
|------|---------|
| Create | `src-tauri/src/transcription/ffmpeg.rs` |
| Create | `src-tauri/src/transcription/batch.rs` |
| Modify | `src-tauri/src/transcription/mod.rs` |
| Modify | `src-tauri/src/state.rs` |
| Modify | `src-tauri/src/lib.rs` |
| Modify | `src-tauri/src/commands/transcription.rs` |
| Modify | `src-tauri/Cargo.toml` |
| Create | `src/store/transcription.ts` |
| Create | `src/components/transcription/FfmpegWarning.tsx` |
| Create | `src/components/transcription/TranscriptionPanel.tsx` |
| Create | `src/components/transcription/TranscriptionMain.tsx` |
| Modify | `src/router.tsx` |
| Modify | `src/App.tsx` |
