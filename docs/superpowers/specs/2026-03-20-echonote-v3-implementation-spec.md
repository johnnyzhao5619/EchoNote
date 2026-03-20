# EchoNote v3.0.0 — 功能实现规格（开发者实施参考）

**日期**：2026-03-20
**配套文档**：`2026-03-20-echonote-v3-tauri-rewrite-design.md`（总体架构）
**读者**：负责具体实现的 Rust / React 开发者
**约定**：本文档列出每个功能的 Rust 类型定义、命令签名、事件 Payload、数据库操作、React 组件职责，开发者可按此直接实现，无需猜测。

---

## 约定说明

### 错误处理

所有 Tauri commands 返回 `Result<T, AppError>`。`AppError` 统一定义在 `src-tauri/src/error.rs`：

```rust
#[derive(Debug, thiserror::Error, serde::Serialize, specta::Type)]
#[serde(tag = "kind", content = "message")]
pub enum AppError {
    #[error("audio error: {0}")]      Audio(String),
    #[error("transcription error: {0}")] Transcription(String),
    #[error("llm error: {0}")]        Llm(String),
    #[error("storage error: {0}")]    Storage(String),
    #[error("io error: {0}")]         Io(String),
    #[error("model error: {0}")]      Model(String),
    #[error("workspace error: {0}")] Workspace(String),
    #[error("not found: {0}")]        NotFound(String),
    #[error("validation: {0}")]       Validation(String),
    #[error("channel closed")]        ChannelClosed,
}
```

前端统一从 `bindings.ts` 引入 `AppError` 类型，不写 `any`。

### ID 约定

所有实体 ID 为 UUID v4 字符串，由 Rust 生成（`uuid` crate），前端不生成 ID。

### 时间戳约定

所有时间戳为 **Unix 毫秒整数**（`i64`），存储在 SQLite `INTEGER` 列。前端负责格式化展示（用 `date-fns` 或 `Intl`）。

---

## 功能一：实时录音 + 采样率重采样 + 流式转写

### 1.1 Rust 类型定义

```rust
// commands/audio.rs

#[derive(Serialize, Deserialize, Clone, Type)]
pub struct AudioDevice {
    pub id: String,       // cpal DeviceId 序列化后的字符串
    pub name: String,
    pub is_default: bool,
    pub sample_rate: u32, // 设备原生采样率，仅供展示
    pub channels: u16,
}

// commands/transcription.rs

#[derive(Serialize, Deserialize, Clone, Type)]
pub struct SegmentPayload {
    pub id: u32,
    pub recording_session_id: String, // 当次录音会话 UUID
    pub start_ms: u32,
    pub end_ms: u32,
    pub text: String,
    pub language: String,
    pub is_partial: bool,  // true = whisper 正在处理，可能被覆盖
}

#[derive(Serialize, Deserialize, Clone, Type)]
pub struct AudioLevelPayload {
    pub rms: f32,          // 0.0-1.0，UI 音频电平表
}

#[derive(Serialize, Deserialize, Clone, Type)]
pub enum RecordingStatus {
    Idle,
    Recording { session_id: String, started_at: i64 },
    Paused  { session_id: String },
    Stopped { session_id: String, recording_id: String },
}

#[derive(Serialize, Deserialize, Clone, Type)]
pub struct RealtimeConfig {
    pub device_id: Option<String>,        // None = 系统默认设备
    pub language: Option<String>,         // None = 自动检测
    pub vad_threshold: f32,               // 0.0-1.0，默认 0.02（RMS 能量阈值）
    pub chunk_duration_ms: u32,           // 默认 500ms
}
```

### 1.2 Tauri Commands

```rust
// 列出可用输入设备（前端下拉选择器数据源）
list_audio_devices() -> Result<Vec<AudioDevice>, AppError>

// 开始实时录音（非阻塞，通过 channel 通知 TranscriptionWorker）
// 返回本次会话的 session_id，后续 events 用此 id 关联
start_realtime(config: RealtimeConfig) -> Result<String, AppError>

// 暂停/继续（不停止 cpal stream，仅停止向 whisper 送数据）
pause_realtime(session_id: String) -> Result<(), AppError>
resume_realtime(session_id: String) -> Result<(), AppError>

// 停止录音，保存音频文件，返回 recording_id（持久化后的 DB 主键）
stop_realtime(session_id: String) -> Result<String, AppError>

// 查询当前录音状态（页面初始化时对齐状态）
get_recording_status() -> Result<RecordingStatus, AppError>
```

### 1.3 Tauri Events（Rust → 前端）

| 事件名 | Payload 类型 | 触发时机 |
|--------|-------------|---------|
| `audio:level` | `AudioLevelPayload` | 每 100ms，AudioCapture 推送 |
| `transcription:segment` | `SegmentPayload` | 每个 whisper segment 推理完成 |
| `transcription:status` | `RecordingStatus` | 状态变更（开始/暂停/停止） |

### 1.4 音频管线实现细节

**audio/capture.rs**
- 调用 `cpal::default_host().input_devices()` 枚举设备
- 用 `device.default_input_config()` 获取原生格式（采样率、声道数、样本格式）
- 开流时 callback 是 `move |data: &[f32], _| { sender.send(data.to_vec()) }`
- **样本格式**：cpal 支持 i16/u16/f32，必须统一转 f32 后再送重采样

**audio/resampler.rs**
```rust
pub struct AudioResampler {
    inner: rubato::FftFixedIn<f32>,
    in_rate: u32,
    out_rate: u32,  // 固定 16000
    channels: usize,
    chunk_size: usize, // rubato 要求固定输入块大小
}

impl AudioResampler {
    pub fn new(in_rate: u32, channels: usize) -> Result<Self, rubato::ResampleError>

    // 输入：interleaved 多声道 f32
    // 输出：16000Hz 单声道 f32（whisper-rs 要求的格式）
    pub fn process(&mut self, input: &[f32]) -> Result<Vec<f32>, rubato::ResampleError>
}
```
- 多声道 → 单声道：平均所有声道（`interleaved[ch::channels].iter().sum() / channels`）
- rubato `FftFixedIn` 需要恰好 `chunk_size` 个输入样本；用内部缓冲积攒到 chunk_size 后再调用 `process_into_buffer`

**audio/vad.rs**
- 计算输入块的 RMS：`(samples.iter().map(|s| s*s).sum::<f32>() / len as f32).sqrt()`
- 连续 N 块（默认 N=6，即 ~3s）RMS < threshold → 静音，不送 whisper
- 静音状态转为有声时，把缓存的前导静音帧一起送出（保留上下文）

**transcription/pipeline.rs**
- `tokio::spawn` 一个 loop，接收 `AudioChunk` via `mpsc::Receiver`
- 维护内部音频累积缓冲区，积攒到 30 秒或检测到长静音再整块送 whisper
- whisper-rs 推理是同步阻塞调用，必须用 `tokio::task::spawn_blocking` 包裹

**transcription/engine.rs**
```rust
pub struct WhisperEngine {
    ctx: Arc<Mutex<WhisperContext>>,
}

impl WhisperEngine {
    pub fn new(model_path: &Path) -> Result<Self, AppError>

    // 同步阻塞，必须在 spawn_blocking 内调用
    pub fn transcribe(
        &self,
        audio: &[f32],  // 16000Hz 单声道
        language: Option<&str>,
    ) -> Result<Vec<RawSegment>, AppError>
}

pub struct RawSegment {
    pub start_ms: u32,
    pub end_ms: u32,
    pub text: String,
    pub language: String,
}
```

### 1.5 数据库操作

录音停止时（`stop_realtime`）执行：
```sql
-- 插入录音主记录
INSERT INTO recordings (id, title, file_path, duration_ms, language, created_at, updated_at)
VALUES (?, ?, ?, ?, ?, ?, ?);

-- 批量插入 segments（一次 transaction）
INSERT INTO transcription_segments
  (recording_id, start_ms, end_ms, text, language, confidence)
VALUES (?, ?, ?, ?, ?, ?);
```

### 1.6 React 组件职责

**RecordingPanel（SecondPanel）**
- 设备下拉（`list_audio_devices`，页面加载时调用一次）
- 语言选择（auto / zh / en / fr / ja 等，对应 whisper language 参数）
- VAD 灵敏度滑块（0.0-1.0，写入 `useSettingsStore`）
- 录音模式选择：仅录音 / 转写 / 转写+翻译

**RecordingMain（MainContent）**
- 顶部：录音控制按钮（开始/暂停/停止），录音时长计时器
- 中部：实时音频电平仪（监听 `audio:level` 事件，用 `<canvas>` 画波形条）
- 下部：实时字幕流（监听 `transcription:segment`，新 segment 追加渲染）

**useRecordingStore（Zustand）**
```typescript
interface RecordingStore {
  status: 'idle' | 'recording' | 'paused'
  sessionId: string | null
  startedAt: number | null
  audioLevel: number           // 0-1，来自 audio:level 事件
  segments: SegmentPayload[]   // 当前会话的所有 segments

  // Actions
  start: (config: RealtimeConfig) => Promise<void>
  pause: () => Promise<void>
  resume: () => Promise<void>
  stop: () => Promise<string>  // 返回 recording_id

  // 内部：监听 Tauri events（在 store 初始化时 setup）
  _setupEventListeners: () => () => void  // 返回 cleanup fn
}
```

---

## 功能二：批量文件转写

### 2.1 Rust 类型定义

```rust
#[derive(Serialize, Deserialize, Clone, Type)]
pub enum JobStatus {
    Queued,
    Processing { progress_pct: u8 },
    Done { recording_id: String },
    Failed { error: String },
    Cancelled,
}

#[derive(Serialize, Deserialize, Clone, Type)]
pub struct TranscriptionJob {
    pub job_id: String,
    pub file_path: String,
    pub file_name: String,
    pub language: Option<String>,
    pub status: JobStatus,
    pub created_at: i64,
}

#[derive(Serialize, Deserialize, Clone, Type)]
pub struct JobProgressPayload {
    pub job_id: String,
    pub status: JobStatus,
    pub current_segment: Option<SegmentPayload>,
}
```

### 2.2 Tauri Commands

```rust
// 提交一个文件转写任务（支持 mp3/mp4/m4a/wav/ogg/flac/webm/mkv）
// 返回 job_id
submit_transcription_job(
    file_path: String,
    language: Option<String>,
) -> Result<String, AppError>

// 批量提交（用户拖入多文件）
submit_transcription_jobs(
    requests: Vec<JobRequest>,  // { file_path, language }
) -> Result<Vec<String>, AppError>  // 返回 job_id 列表

// 查询所有任务（含历史）
list_transcription_jobs() -> Result<Vec<TranscriptionJob>, AppError>

// 取消排队中/处理中的任务
cancel_transcription_job(job_id: String) -> Result<(), AppError>

// 清除已完成/失败的历史任务
clear_finished_jobs() -> Result<(), AppError>
```

### 2.3 Tauri Events

| 事件名 | Payload | 触发时机 |
|--------|---------|---------|
| `transcription:job_progress` | `JobProgressPayload` | 每个 segment 推理完成时 |
| `transcription:job_done` | `{ job_id: String, recording_id: String }` | 任务成功完成 |
| `transcription:job_error` | `{ job_id: String, error: String }` | 任务失败 |

### 2.4 实现细节

**transcription/batch.rs**
- 维护一个 `VecDeque<BatchJob>` 队列，单次只并发 1 个任务（推理资源互斥）
- 音频解码：用 `ffmpeg-next` crate 或调用系统 `ffmpeg` 命令行将非 WAV 格式转换为 16kHz WAV，再送 whisper-rs
- 若系统未安装 ffmpeg：对 mp3/mp4 等格式提示"需要 ffmpeg 支持"，仅 WAV 格式直接处理
- 任务完成后自动创建 `recordings` + `transcription_segments` 数据库记录，并在 workspace inbox 文件夹创建对应的 `workspace_documents` 记录

**TranscriptionPanel（SecondPanel）**
- 文件拖放区域（`tauri-plugin-dialog` 选择文件 / 拖拽）
- 任务列表（进度条 + 状态 + 文件名）
- 清除历史按钮

**TranscriptionMain（MainContent）**
- 选中任务的完整转写文本展示
- 导出按钮（TXT / SRT / VTT 格式）

---

## 功能三：本地 LLM 推理（摘要、会议纪要、翻译）

### 3.1 任务类型与 Prompt 模板

Prompt 模板存储在 `resources/prompts/` 目录（TOML 格式），**不硬编码在 Rust 代码中**：

```toml
# resources/prompts/tasks.toml

[summary]
system = "You are a helpful assistant that summarizes meeting transcripts concisely."
user   = "Write a concise summary of the following text. Focus on key decisions and outcomes.\n\n{text}"
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
system = "You are a professional translator."
user   = "Translate the following text to {target_language}. Output only the translation.\n\n{text}"
max_tokens = 2048

[qa]
system = "You are a helpful assistant. Answer questions based on the provided document."
user   = "Document:\n{context}\n\nQuestion: {question}"
max_tokens = 512
```

### 3.2 Rust 类型定义

```rust
#[derive(Serialize, Deserialize, Clone, Type)]
#[serde(rename_all = "snake_case")]
pub enum LlmTaskType {
    Summary,
    MeetingBrief,
    Translation { target_language: String },
    Qa { question: String },
}

#[derive(Serialize, Deserialize, Clone, Type)]
pub struct LlmTaskRequest {
    pub document_id: String,
    pub task_type: LlmTaskType,
    pub text_role_hint: Option<String>, // 优先使用哪个 asset role 的文本
                                        // None = 按优先级取：transcript > document_text
}

#[derive(Serialize, Deserialize, Clone, Type)]
pub struct TokenPayload {
    pub task_id: String,
    pub token: String,
}

#[derive(Serialize, Deserialize, Clone, Type)]
pub struct LlmTaskResult {
    pub task_id: String,
    pub document_id: String,
    pub task_type: LlmTaskType,
    pub result_text: String,
    pub asset_role: String,  // 结果保存到哪个 asset role
    pub asset_id: String,
    pub completed_at: i64,
}

#[derive(Serialize, Deserialize, Clone, Type)]
pub enum LlmEngineStatus {
    NotLoaded,
    Loading { model_id: String },
    Ready { model_id: String, loaded_at: i64 },
    Error { message: String },
}
```

### 3.3 Tauri Commands

```rust
// 提交 LLM 任务，立即返回 task_id（非阻塞）
submit_llm_task(request: LlmTaskRequest) -> Result<String, AppError>

// 取消进行中的任务
cancel_llm_task(task_id: String) -> Result<(), AppError>

// 查询 LLM 引擎状态（设置页展示）
get_llm_engine_status() -> Result<LlmEngineStatus, AppError>

// 查询某文档的所有 LLM 任务历史
list_document_llm_tasks(document_id: String) -> Result<Vec<LlmTaskRow>, AppError>
```

### 3.4 Tauri Events

| 事件名 | Payload | 触发时机 |
|--------|---------|---------|
| `llm:token` | `TokenPayload` | 每个推理 token |
| `llm:done` | `LlmTaskResult` | 任务完成（含最终结果和 asset_id） |
| `llm:error` | `{ task_id: String, error: String }` | 任务失败 |
| `llm:status` | `LlmEngineStatus` | 引擎状态变更（加载/就绪/错误） |

### 3.5 实现细节

**llm/engine.rs**
```rust
pub struct LlmEngine {
    model: Arc<llama_cpp_2::LlamaModel>,
    ctx_params: ContextParams,
}

impl LlmEngine {
    pub fn new(model_path: &Path, ctx_size: u32) -> Result<Self, AppError>

    // 同步阻塞，必须在 spawn_blocking 内调用
    // token_cb 每生成一个 token 就调用一次，返回 false 停止生成
    pub fn generate(
        &self,
        system_prompt: &str,
        user_prompt: &str,
        max_tokens: u32,
        token_cb: impl Fn(String) -> bool,
    ) -> Result<String, AppError>
}
```

**llm/tasks.rs**
- 从 `resources/prompts/tasks.toml` 加载模板（应用启动时一次性读取，存入 `AppState`）
- 根据 `LlmTaskType` 填充模板变量（`{text}`, `{target_language}`, `{question}`）
- 文本来源优先级：`transcript` > `document_text`（按 `TEXT_ASSET_ROLE_PRIORITY` 排序）
- 生成完成后：更新 `llm_tasks.status = 'done'`，并在 `workspace_text_assets` 插入结果

**LLM Worker 取消机制**
```rust
// 使用 AtomicBool 控制取消
let cancelled = Arc::new(AtomicBool::new(false));

engine.generate(system, user, max_tokens, |token| {
    if cancelled.load(Ordering::Relaxed) {
        return false; // 停止生成
    }
    app_handle.emit("llm:token", TokenPayload { task_id, token }).ok();
    true
})?;
```

### 3.6 会议纪要特殊处理

`MeetingBrief` 任务生成完成后，需要将结果解析成四个 asset：
- `summary`
- `decisions`
- `action_items`
- `next_steps`

Rust 端用正则提取各 `## Section` 内容，写入 4 条 `workspace_text_assets` 记录。

解析逻辑（`llm/tasks.rs::parse_meeting_brief`）：
```rust
fn parse_meeting_brief(text: &str) -> MeetingBriefSections {
    let re = Regex::new(r"##\s*([\w\s]+)\n([\s\S]*?)(?=##|\z)").unwrap();
    // 提取 Summary / Decisions / Action Items / Next Steps
    // 对未识别到的 section 保留 None，前端展示占位文字
}
```

---

## 功能四：Workspace 文档库

### 4.1 数据模型（补充 Schema）

在 `0001_initial.sql` 基础上增加：

```sql
-- workspace_text_assets：文档的各类文本资产（转写稿、摘要、翻译等）
CREATE TABLE workspace_text_assets (
    id           TEXT PRIMARY KEY,
    document_id  TEXT NOT NULL REFERENCES workspace_documents(id) ON DELETE CASCADE,
    role         TEXT NOT NULL,   -- 见下方 Asset Role 说明
    content      TEXT NOT NULL,
    file_path    TEXT,            -- 对应磁盘上的 .md 文件路径
    created_at   INTEGER NOT NULL,
    updated_at   INTEGER NOT NULL
);
CREATE INDEX idx_assets_document ON workspace_text_assets(document_id, role);
```

**Asset Role 优先级**（用于"取最佳可读文本"逻辑）：

| role | 优先级 | 说明 |
|------|--------|------|
| `document_text` | 0（最高） | 手动编辑的笔记内容 |
| `transcript` | 1 | 语音转写稿 |
| `meeting_brief` | 2 | 完整会议纪要 |
| `summary` | 3 | AI 摘要 |
| `translation` | 4 | 翻译版本 |
| `decisions` | 5 | 决议提取 |
| `action_items` | 6 | 行动项提取 |
| `next_steps` | 7 | 下一步提取 |

### 4.2 系统文件夹（固定，不可重命名删除）

| folder_kind | 名称 | 说明 |
|------------|------|------|
| `inbox` | Inbox | 所有新录音和导入的默认目录 |
| `system_root` | Events | 与时间轴事件关联的文档 |
| `batch_task` | Batch Tasks | 批量转写任务产生的文档 |

用户创建的文件夹 `folder_kind = 'user'`，可嵌套。

### 4.3 Vault 文件系统布局

```
{APP_DATA}/vault/
├── workspace-items/     ← inbox folder
│   ├── 会议记录.md       ← 文档主文件（document_text asset）
│   └── 会议记录/         ← 同名目录，存放该文档的其他 assets
│       ├── Transcript.md
│       ├── Summary.md
│       ├── Translation.md
│       └── Meeting Brief.md
├── events/              ← system_root folder
│   └── 2026-03-20 周例会/
│       ├── Transcript.md
│       └── Meeting Brief.md
└── batch-tasks/         ← batch_task folder
    └── 项目录音转写/
        ├── Transcript.md
        └── Summary.md
```

所有文本 asset 都同步写入磁盘文件（与数据库双写），实现 Obsidian 风格的"本地文件优先"。

### 4.4 Rust 类型定义

```rust
#[derive(Serialize, Deserialize, Clone, Type)]
pub struct FolderNode {
    pub id: String,
    pub name: String,
    pub parent_id: Option<String>,
    pub folder_kind: String,     // 'user' | 'inbox' | 'system_root' | 'event' | 'batch_task'
    pub is_system: bool,         // system folders 不可重命名/删除
    pub children: Vec<FolderNode>,
    pub document_count: u32,
}

#[derive(Serialize, Deserialize, Clone, Type)]
pub struct DocumentSummary {
    pub id: String,
    pub title: String,
    pub folder_id: Option<String>,
    pub source_type: String,     // 'recording' | 'import' | 'note' | 'batch_task'
    pub has_transcript: bool,
    pub has_summary: bool,
    pub has_meeting_brief: bool,
    pub recording_id: Option<String>,
    pub updated_at: i64,
    pub created_at: i64,
}

#[derive(Serialize, Deserialize, Clone, Type)]
pub struct DocumentDetail {
    pub id: String,
    pub title: String,
    pub folder_id: Option<String>,
    pub source_type: String,
    pub recording_id: Option<String>,
    pub assets: Vec<TextAsset>,  // 所有 roles，前端按优先级选择显示哪个
    pub created_at: i64,
    pub updated_at: i64,
}

#[derive(Serialize, Deserialize, Clone, Type)]
pub struct TextAsset {
    pub id: String,
    pub role: String,
    pub content: String,
    pub updated_at: i64,
}

#[derive(Serialize, Deserialize, Clone, Type)]
pub struct SearchResult {
    pub document_id: String,
    pub title: String,
    pub snippet: String,   // FTS5 highlight() 结果
    pub rank: f64,
    pub folder_id: Option<String>,
    pub updated_at: i64,
}
```

### 4.5 Tauri Commands

```rust
// 文件夹 CRUD
get_folder_tree() -> Result<Vec<FolderNode>, AppError>
create_folder(name: String, parent_id: Option<String>) -> Result<FolderNode, AppError>
rename_folder(id: String, name: String) -> Result<(), AppError>
delete_folder(id: String) -> Result<(), AppError>  // 级联删除子文件夹和文档
move_folder(id: String, new_parent_id: Option<String>) -> Result<(), AppError>

// 文档 CRUD
list_documents(folder_id: Option<String>) -> Result<Vec<DocumentSummary>, AppError>
get_document(id: String) -> Result<DocumentDetail, AppError>
create_note(title: String, folder_id: Option<String>, content: String) -> Result<DocumentSummary, AppError>
update_document_title(id: String, title: String) -> Result<(), AppError>
update_document_content(id: String, role: String, content: String) -> Result<(), AppError>
delete_document(id: String) -> Result<(), AppError>
move_document(id: String, folder_id: Option<String>) -> Result<(), AppError>
duplicate_document(id: String) -> Result<DocumentSummary, AppError>

// 导入
import_file(file_path: String, folder_id: Option<String>) -> Result<DocumentSummary, AppError>

// 全文搜索
search_documents(query: String) -> Result<Vec<SearchResult>, AppError>

// 导出
export_document_as_markdown(id: String, target_path: String) -> Result<(), AppError>
export_document_as_txt(id: String, target_path: String) -> Result<(), AppError>
```

### 4.6 校验规则（Workspace Validation）

- 文件夹名不能为空，不能包含 `/` `\` `:` `*` `?` `"` `<` `>` `|`
- 同一父文件夹下不能有同名子文件夹
- 系统文件夹（`is_system: true`）不可重命名、删除、移动
- 文档标题最长 255 字符
- 移动目标不能是当前文件夹的子孙（防止循环）

错误通过 `AppError::Validation(code)` 返回稳定错误码（不是自由文本），前端用 i18n key 显示对应提示：
- `"workspace.duplicate_name"` - 名称冲突
- `"workspace.invalid_name"` - 非法字符
- `"workspace.invalid_move_target"` - 循环移动

### 4.7 React 组件职责

**WorkspacePanel（SecondPanel）**
- 视图切换：Structure 视图（文件夹树）/ Event 视图（按时间轴事件分组）
- 文件夹树（递归渲染 `FolderNode`，支持折叠/展开）
- 右键菜单：新建子文件夹 / 重命名 / 删除 / 打开本地文件夹
- 拖拽：文档/文件夹拖拽移动（拖到目标文件夹释放）
- 底部：搜索框（输入时调用 `search_documents`，结果替换文件夹树）

**WorkspaceMain（MainContent）**
- 标签式多文档编辑器（最多同时打开 N 个 tab）
- 文档内容区：根据 asset roles 展示多个面板（Transcript / Summary / Meeting Brief 等）
- Inspector 侧栏（可折叠）：文档元数据、关联录音、关联时间轴事件
- AI 操作按钮：生成摘要 / 生成会议纪要 / 翻译（触发 `submit_llm_task`）
- LLM 结果流式展示：监听 `llm:token` 事件，逐字追加

**useWorkspaceStore（Zustand）**
```typescript
interface WorkspaceStore {
  folderTree: FolderNode[]
  openTabs: DocumentDetail[]           // 当前打开的文档 tabs
  activeTabId: string | null
  searchQuery: string
  searchResults: SearchResult[]

  loadFolderTree: () => Promise<void>
  openDocument: (id: string) => Promise<void>
  closeTab: (id: string) => void
  setActiveTab: (id: string) => void
  updateTabContent: (id: string, role: string, content: string) => Promise<void>
  createNote: (title: string, folderId?: string) => Promise<void>
  importFile: () => Promise<void>      // 调用 dialog plugin 选择文件
  search: (query: string) => Promise<void>
}
```

---

## 功能五：本地时间轴

### 5.1 定位说明

v3.0.0 时间轴为**纯本地**日程管理，无需 Google OAuth。用户手动创建事件，可关联录音/文档。

### 5.2 Rust 类型定义

```rust
#[derive(Serialize, Deserialize, Clone, Type)]
pub struct TimelineEvent {
    pub id: String,
    pub title: String,
    pub start_at: i64,              // Unix ms
    pub end_at: i64,                // Unix ms
    pub description: Option<String>,
    pub tags: Vec<String>,
    pub recording_id: Option<String>,  // 关联的录音
    pub document_id: Option<String>,   // 关联的 workspace 文档
    pub created_at: i64,
}

#[derive(Serialize, Deserialize, Clone, Type)]
pub struct CreateEventRequest {
    pub title: String,
    pub start_at: i64,
    pub end_at: i64,
    pub description: Option<String>,
    pub tags: Vec<String>,
}
```

### 5.3 Tauri Commands

```rust
list_events(start_at: i64, end_at: i64) -> Result<Vec<TimelineEvent>, AppError>
get_event(id: String) -> Result<TimelineEvent, AppError>
create_event(req: CreateEventRequest) -> Result<TimelineEvent, AppError>
update_event(id: String, req: CreateEventRequest) -> Result<(), AppError>
delete_event(id: String) -> Result<(), AppError>

// 将录音/文档关联到事件（关联后自动将文档移入 events/ 系统文件夹）
link_recording_to_event(event_id: String, recording_id: String) -> Result<(), AppError>
link_document_to_event(event_id: String, document_id: String) -> Result<(), AppError>
unlink_from_event(event_id: String) -> Result<(), AppError>
```

### 5.4 React 组件职责

**TimelinePanel（SecondPanel）**
- 月历视图（点击日期 → 过滤该日事件）
- 事件列表（按时间排序）
- 新建事件按钮（打开弹窗表单）

**TimelineMain（MainContent）**
- 日周月视图切换
- 事件卡片（点击 → 弹出详情：标题/时间/描述/标签/关联录音链接）
- 关联录音时可跳转到 Workspace 查看转写稿

---

## 功能六：模型下载管理器

### 6.1 模型配置文件（配置驱动）

```toml
# resources/models.toml

[whisper]
default_variant = "base"

[whisper.variants.tiny]
url       = "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-tiny.bin"
sha256    = "be07e048e1e599ad46341c8d2a135645097a538221678b7acdd1b1919c6e1b21"
size_bytes = 75161336
description = "最小模型，速度最快，精度较低"

[whisper.variants.base]
url       = "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.bin"
sha256    = "60ed5bc3dd14eea856493d334349b405782ddcaf0028d4b5df4088345fba2efe"
size_bytes = 142068640
description = "推荐入门模型，速度与精度平衡"

[whisper.variants.small]
url       = "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.bin"
sha256    = "1be3a9b2063867b937e64e2ec7483364a79917e157fa98c5d94b5c1fffea987b"
size_bytes = 466013312
description = "精度更高，需要约 1GB RAM"

[whisper.variants.medium]
url       = "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-medium.bin"
sha256    = "fd9727b6e1217c2f614f9b698455c4ffd82463b4"
size_bytes = 1528006144
description = "高精度，需要约 3GB RAM"

[llm]
default_variant = "qwen2.5-3b-q4"

[llm.variants.qwen2.5-3b-q4]
url       = "https://huggingface.co/Qwen/Qwen2.5-3B-Instruct-GGUF/resolve/main/qwen2.5-3b-instruct-q4_k_m.gguf"
sha256    = "..."
size_bytes = 1890000000
description = "轻量模型，适合低配设备，需要约 2GB RAM"

[llm.variants.qwen2.5-7b-q4]
url       = "https://huggingface.co/Qwen/Qwen2.5-7B-Instruct-GGUF/resolve/main/qwen2.5-7b-instruct-q4_k_m.gguf"
sha256    = "..."
size_bytes = 4370000000
description = "推荐模型，效果好，需要约 5GB RAM"
```

### 6.2 Rust 类型定义

```rust
#[derive(Serialize, Deserialize, Clone, Type)]
pub struct ModelVariant {
    pub variant_id: String,    // e.g. "whisper/base" | "llm/qwen2.5-7b-q4"
    pub model_type: String,    // "whisper" | "llm"
    pub name: String,
    pub description: String,
    pub size_bytes: u64,
    pub size_display: String,  // "142 MB"（格式化后）
    pub is_downloaded: bool,
    pub is_active: bool,       // 当前加载的模型
}

#[derive(Serialize, Deserialize, Clone, Type)]
pub struct DownloadProgressPayload {
    pub variant_id: String,
    pub downloaded_bytes: u64,
    pub total_bytes: Option<u64>,
    pub speed_bps: u64,          // bytes/sec，UI 展示下载速度
    pub eta_secs: Option<u64>,   // 预计剩余时间
}
```

### 6.3 Tauri Commands

```rust
// 列出所有可用模型变体及下载状态
list_model_variants() -> Result<Vec<ModelVariant>, AppError>

// 开始下载（非阻塞）
download_model(variant_id: String) -> Result<(), AppError>

// 取消下载
cancel_download(variant_id: String) -> Result<(), AppError>

// 删除已下载的模型文件
delete_model(variant_id: String) -> Result<(), AppError>

// 切换激活模型（需要重新加载 engine）
set_active_model(variant_id: String) -> Result<(), AppError>
```

### 6.4 Tauri Events

| 事件名 | Payload | 触发时机 |
|--------|---------|---------|
| `models:required` | `{ missing: Vec<String> }` | 启动时检测到模型缺失 |
| `models:progress` | `DownloadProgressPayload` | 每个 chunk 下载完成 |
| `models:downloaded` | `{ variant_id: String }` | 下载并校验成功 |
| `models:error` | `{ variant_id: String, error: String }` | 下载失败 |

### 6.5 实现细节

**models/downloader.rs**

- 使用 `reqwest::Client` 流式下载，每 chunk（128KB）emit 一次 progress
- 下载到 `{variant_id}.tmp` 临时文件，完成后 SHA256 校验，通过后 rename 为最终文件名
- 校验失败：删除临时文件，emit error 事件，前端提示重试
- 下载速度计算：记录最近 5 秒的下载量，计算 ETA
- 支持断点续传：检查临时文件大小，用 `Range: bytes=N-` 请求头续传

**启动时检测流程**（`models/registry.rs::check_startup`）：
1. 读取用户配置中的激活模型 ID
2. 检查对应文件是否存在
3. 若存在：验证文件大小（快速检查，不每次 SHA256）
4. 若缺失：emit `models:required` 事件，前端弹出下载引导

**ModelsPanel（SettingsPanel 子页面）**
- 分 Whisper / LLM 两组
- 每个变体：名称 + 描述 + 大小 + 状态（已下载/下载中/未下载）
- 下载中：进度条 + 速度 + ETA + 取消按钮
- 已下载：删除按钮 + "设为当前"按钮（高亮当前激活）

---

## 功能七：主题系统（VSCode 风格）

### 7.1 内置主题来源

直接从 `docs/themes/` 目录中的三个 VSCode 主题 JSON 提取 `colors` 字段，映射到语义 token：

```
VSCode token → EchoNote 语义 token
───────────────────────────────────────────────────────
editor.background           → bg.primary
sideBar.background          → bg.sidebar
panel.background            → bg.secondary
input.background            → bg.input
list.hoverBackground        → bg.hover
editor.selectionBackground  → bg.selection
foreground                  → text.primary
descriptionForeground       → text.secondary
disabledForeground          → text.muted
button.background           → accent.primary
button.hoverBackground      → accent.hover
focusBorder                 → border.focus
sash.hoverBorder            → border.default
errorForeground             → status.error  （Tokyo Night: #f7768e）
inputValidation.warningBorder → status.warning （#e0af68）
gitDecoration.addedResourceForeground → status.success（#9ece6a）
editorInfo.foreground       → status.info    （#2ac3de）
```

**映射转换脚本**（构建时执行，不在运行时做）：`scripts/convert-themes.ts` 读取 `docs/themes/*.json` 输出 `resources/themes/*.json`（语义 token 格式）。

### 7.2 主题命令

```rust
// 获取所有主题（内置 + 用户自定义）
list_themes() -> Result<Vec<ThemeManifest>, AppError>

// 读取主题 token（前端应用到 CSS 变量）
get_theme(theme_id: String) -> Result<ThemeTokens, AppError>

// 保存用户自定义主题
save_custom_theme(theme: ThemeDefinition) -> Result<String, AppError>

// 删除用户自定义主题（内置主题不可删除）
delete_custom_theme(theme_id: String) -> Result<(), AppError>

// 设置当前激活主题（持久化到 app_settings）
set_active_theme(theme_id: String) -> Result<(), AppError>
```

### 7.3 用户自定义主题存储路径

```
{APP_DATA}/themes/{theme_id}.json
```

内置主题只读，存储在应用资源目录（`resources/themes/`），不可删除。

### 7.4 主题编辑器 UI（SettingsMain 子页面）

- 左侧：主题列表（分"内置"/"自定义"两组）
- 右侧：token 编辑区（每个语义 token 一行，颜色选择器）
- 实时预览：编辑时立即应用到当前页面（不保存），点击"保存"才持久化
- 操作：克隆现有主题 / 导入 JSON / 导出 JSON / 删除

---

## 功能八：国际化（i18n）

### 8.1 架构决策

- 翻译文件格式与现有 `resources/translations/` 完全一致（JSON，嵌套结构）
- **不使用 fluent-rs**：保持与现有翻译文件兼容，用简单 JSON 路径查找 + 插值
- Rust 侧只负责提供翻译数据（command），实际渲染在前端完成
- Rust 端错误消息使用 stable error code，不翻译（前端根据 code 查 i18n）

### 8.2 Tauri Commands

```rust
// 返回指定 locale 的完整翻译 JSON（前端缓存）
get_translations(locale: String) -> Result<serde_json::Value, AppError>

// 获取系统推荐 locale（macOS/Windows 系统语言）
get_system_locale() -> Result<String, AppError>

// 持久化用户选择的 locale
set_app_locale(locale: String) -> Result<(), AppError>
```

### 8.3 前端 i18n Hook

```typescript
// hooks/useT.ts
// 单一 hook，全局使用
export function useT() {
  const translations = useSettingsStore(s => s.translations)
  return (key: string, vars?: Record<string, string>): string => {
    const value = getNestedValue(translations, key) ?? key
    if (!vars) return value
    return Object.entries(vars).reduce(
      (s, [k, v]) => s.replace(`{${k}}`, v),
      value
    )
  }
}
```

前端所有用户可见字符串通过 `useT()` 获取，**不硬编码任何显示文本**。

### 8.4 i18n Key 结构沿用

沿用现有 `i18n_outline.json` 中的 sections 结构，key 路径格式为 `section.key`（例：`workspace.new_folder`）。v3.0.0 移除以下 sections（不再需要）：
- `calendar_hub`（OAuth 日历已移除）
- `calendar`（同上）
- `loopback`（系统音频回环，v3.0.0 范围外）
- `wizard`（首次引导改为 React 组件实现）

新增 sections：
- `models`（模型管理页）
- `theme`（主题设置页）

---

## 功能九：设置系统

### 9.1 设置存储

所有设置通过 `app_settings` 表的键值对持久化（JSON 序列化值）。

### 9.2 设置 Schema

```rust
// config/schema.rs
#[derive(Serialize, Deserialize, Default, Type)]
pub struct AppConfig {
    pub locale: String,               // 默认 "zh_CN"
    pub active_theme: String,         // 默认 "tokyo-night"
    pub active_whisper_model: String, // 默认 "whisper/base"
    pub active_llm_model: String,     // 默认 "llm/qwen2.5-3b-q4"
    pub llm_context_size: u32,        // 默认 4096
    pub vault_path: String,           // 文档库路径，默认 {APP_DATA}/vault
    pub default_language: Option<String>,   // 默认转写语言
    pub vad_threshold: f32,           // 默认 0.02
    pub audio_chunk_ms: u32,          // 默认 500
    pub auto_llm_on_stop: bool,       // 停止录音后自动触发摘要
    pub default_llm_task: String,     // "summary" | "meeting_brief"
}
```

### 9.3 Tauri Commands

```rust
get_config() -> Result<AppConfig, AppError>
update_config(partial: PartialAppConfig) -> Result<(), AppError>  // 只更新传入的字段
reset_config() -> Result<AppConfig, AppError>
```

---

## 功能十：文件导入（PDF / DOCX / TXT / MD）

### 10.1 支持格式与实现

| 格式 | Rust crate | 提取内容 |
|------|-----------|---------|
| `.txt` | 标准库 | 直接读取 |
| `.md` | 标准库 | 直接读取（保留 markdown） |
| `.pdf` | `pdf-extract` | 提取纯文本 |
| `.docx` | `docx-rs` | 提取段落文本 |

**导入流程**（`workspace/manager.rs::import_file`）：
1. 读取文件 → 提取纯文本
2. 在 `workspace_documents` 创建记录（`source_type = 'import'`）
3. 在 `workspace_text_assets` 创建 `document_text` role 记录（存储提取的文本）
4. 同步写入磁盘文件到 vault 路径（`{folder_path}/{title}.md`）
5. 若文本超过 4000 字：自动触发 `submit_llm_task(Summary)`（`auto_llm_on_stop` 设置控制）

### 10.2 提取文本后处理

- 移除多余空行（超过 2 个连续空行压缩为 1 个）
- 统一换行符（`\r\n` → `\n`）
- 编码检测：非 UTF-8 文件尝试 GBK/Latin-1 转换（使用 `encoding_rs` crate）

---

## 附录 A：AppState 结构

```rust
// state.rs
pub struct AppState {
    pub db: Arc<Db>,
    pub config: Arc<RwLock<AppConfig>>,
    pub translations: Arc<RwLock<serde_json::Value>>,
    pub prompt_templates: Arc<PromptTemplates>,     // 启动时一次性加载
    pub model_config: Arc<ModelConfig>,             // models.toml 内容

    // Worker channels
    pub transcription_tx: mpsc::Sender<TranscriptionCommand>,
    pub llm_tx:           mpsc::Sender<LlmTaskMessage>,
    pub download_tx:      mpsc::Sender<DownloadCommand>,

    // Engine handles（Option，模型未加载时为 None）
    pub whisper_engine: Arc<Mutex<Option<WhisperEngine>>>,
    pub llm_engine:     Arc<Mutex<Option<LlmEngine>>>,
}
```

---

## 附录 B：lib.rs 启动顺序

```rust
// lib.rs
pub fn run() {
    // 1. 初始化数据目录（APP_DATA）
    // 2. 运行 sqlx migrations
    // 3. 加载 AppConfig
    // 4. 加载翻译文件（按 config.locale）
    // 5. 加载 models.toml 和 prompts/tasks.toml
    // 6. 检查模型文件（emit models:required 若缺失）
    // 7. 若模型存在 → 加载 WhisperEngine + LlmEngine
    // 8. 启动后台 workers（tokio::spawn × 3）
    // 9. 注册所有 commands（tauri-specta 导出 bindings.ts）
    // 10. 启动 Tauri 窗口
}
```

步骤 3-8 若任一步骤失败，应记录 warn 日志但不 panic（模型缺失是正常状态，不是错误）。

---

## 附录 C：开发顺序建议

按以下顺序实现，每个里程碑都是可独立运行的可验证状态：

1. **M1 骨架**：Tauri 初始化 + React 路由 + Layout + 主题系统（CSS 变量 + 硬编码 Tokyo Night）
2. **M2 数据库**：sqlx 连接 + migrations + `app_settings` CRUD + 设置页
3. **M3 音频转写**：cpal + rubato + whisper-rs + 实时字幕展示（端到端 smoke test）
4. **M4 模型管理**：models.toml 加载 + 下载器 + 首次启动引导弹窗
5. **M5 LLM**：llama-cpp-2 + 流式 token 显示 + 摘要/会议纪要任务
6. **M6 Workspace**：文件夹树 + 文档 CRUD + FTS 搜索 + 标签编辑器
7. **M7 批量转写 + 导入**：批量转写队列 + PDF/DOCX 导入
8. **M8 时间轴**：本地事件 CRUD + 关联录音
9. **M9 i18n 完整化**：所有 UI 字符串走 `useT()` + 语言切换
10. **M10 主题自定义**：主题编辑器 + 导入导出 + 三内置主题
11. **M11 CI/CD**：GitHub Actions 三平台矩阵构建 + 代码签名
