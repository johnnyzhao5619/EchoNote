# EchoNote v3.0.0 — Tauri + Rust 全量重写设计规格

**日期**：2026-03-20
**版本**：v3.0.0（全新发布，不兼容旧版数据）
**状态**：待实施

---

## 1. 背景与目标

### 1.1 驱动因素

| 优先级 | 问题 | 现状 |
|--------|------|------|
| P0 | UI 现代化 | PySide6 + QSS 有质感天花板，无法对标 Obsidian/AnythingLLM |
| P0 | 本地 LLM 集成质量 | GGUF 通过 `subprocess` 调用，无流式输出、延迟高、无法嵌入推理上下文 |

### 1.2 非目标（v3.0.0 范围外）

- 数据迁移：v3.0.0 为全新版本，不迁移旧版 Python 应用数据
- Google Calendar OAuth 同步：改为本地时间轴（只读展示，无需 OAuth）
- 减小打包体积（非驱动因素）
- 加快启动速度（非驱动因素）

### 1.3 技术选型摘要

| 模块 | 选型 | 理由 |
|------|------|------|
| 应用框架 | Tauri 2.x | 成熟跨平台桌面框架，系统 WebView，原生 Rust 后端 |
| 前端 | React 18 + TypeScript + Tailwind CSS + shadcn/ui | AnythingLLM 同栈，生态最成熟 |
| 前端状态 | Zustand | 轻量无样板，适合桌面本地状态模型 |
| 前端路由 | TanStack Router | 类型安全，比 react-router v6 更适合 Tauri 单页结构 |
| IPC | tauri-specta v2 | 从 Rust 自动生成 TypeScript 类型，消除 any |
| 音频采集 | cpal | Rust 最成熟的跨平台低层音频库 |
| 采样率转换 | rubato | 专为高质量音频重采样设计，支持任意比例 |
| 语音转写 | whisper-rs（whisper.cpp） | CoreML/Metal/CUDA 硬件加速支持 |
| 本地 LLM | llama-cpp-2（llama.cpp） | 流式 token 回调，Metal/CUDA 加速，API 清晰 |
| 数据库 | sqlx + SQLite（WAL 模式） | async 原生，编译期 SQL 验证 |
| HTTP 下载 | reqwest | async 流式下载，进度回调 |
| 配置序列化 | serde + TOML | Rust 生态标准 |
| 国际化 | 运行时加载 JSON | 与现有 en_US/zh_CN/fr_FR 翻译文件格式一致 |

---

## 2. 总体架构

### 2.1 三层架构

```
┌─────────────────────────────────────────────────────────┐
│  UI Layer                                               │
│  React 18 + TypeScript + Tailwind + shadcn/ui           │
│  路由(TanStack) / 状态(Zustand) / 主题(CSS Variables)   │
└─────────────────────────┬───────────────────────────────┘
                          │ tauri-specta（类型安全 IPC Commands）
                          │ Tauri Events（流式推送 / 进度通知）
┌─────────────────────────▼───────────────────────────────┐
│  Rust Backend (tokio async runtime)                     │
│  commands/ → audio/ → transcription/ → llm/            │
│  workspace/ → timeline/ → storage/ → i18n/ → models/   │
└──────────────┬──────────────────────┬───────────────────┘
               │                      │
        ┌──────▼──────┐       ┌───────▼──────┐
        │ whisper.cpp │       │  llama.cpp   │
        │ (whisper-rs)│       │ (llama-cpp-2)│
        │ CoreML/Metal│       │ Metal/CUDA   │
        │ /CUDA       │       │ /CPU         │
        └─────────────┘       └──────────────┘
```

### 2.2 数据流全貌

```
麦克风
  │
  ▼  cpal (audio/capture.rs)  — 采集设备原始 PCM
立体声转单声道 + rubato 重采样 (audio/resampler.rs)
  │  44100Hz/48000Hz → 16000Hz f32
  ▼
环形缓冲区 (audio/buffer.rs)
  │  按 chunk_size（512ms = 8192 samples）切片
  ▼
VAD 静音检测 (audio/vad.rs)  — 过滤静音帧
  │
  ▼  tokio::mpsc::Sender<AudioChunk>
TranscriptionWorker（长驻后台 tokio task）
  │  whisper-rs 推理（非阻塞）
  ├──► emit("transcription:segment", SegmentPayload) → React 实时字幕
  └──► sqlx 持久化 segments
         │
         ▼ 转写完成
     LlmWorker（长驻后台 tokio task）
         │  llama-cpp-2 推理（流式 token 回调）
         ├──► emit("llm:token", TokenPayload)  → React 逐字显示
         └──► emit("llm:done", task_id)
              sqlx 持久化 llm_tasks 结果
```

---

## 3. 项目目录结构

```
echonote/
├── src-tauri/
│   ├── Cargo.toml
│   ├── tauri.conf.json
│   ├── build.rs                        # whisper.cpp/llama.cpp 编译标志
│   └── src/
│       ├── main.rs                     # Tauri 启动入口
│       ├── lib.rs                      # 模块注册 + AppState 初始化
│       ├── state.rs                    # AppState（Arc 共享状态）
│       ├── error.rs                    # 统一错误类型（thiserror）
│       │
│       ├── audio/
│       │   ├── mod.rs
│       │   ├── capture.rs              # cpal 音频流采集
│       │   ├── resampler.rs            # rubato 重采样（任意Hz → 16000Hz）
│       │   ├── buffer.rs               # 环形缓冲区
│       │   └── vad.rs                  # 静音检测（能量阈值）
│       │
│       ├── transcription/
│       │   ├── mod.rs
│       │   ├── engine.rs               # whisper-rs 封装
│       │   ├── pipeline.rs             # 实时流水线（tokio channel 驱动）
│       │   └── batch.rs                # 批量文件转写
│       │
│       ├── llm/
│       │   ├── mod.rs
│       │   ├── engine.rs               # llama-cpp-2 封装
│       │   ├── streaming.rs            # token 流 → Tauri event 桥接
│       │   └── tasks.rs                # 摘要 / 翻译 / 问答任务定义
│       │
│       ├── workspace/
│       │   ├── mod.rs
│       │   ├── manager.rs
│       │   ├── document.rs
│       │   └── parser.rs               # PDF/DOCX 文本提取
│       │
│       ├── timeline/
│       │   ├── mod.rs
│       │   └── manager.rs              # 本地时间轴（无 OAuth）
│       │
│       ├── storage/
│       │   ├── mod.rs
│       │   ├── db.rs                   # sqlx 连接池 + WAL 模式
│       │   └── migrations/
│       │       ├── 0001_initial.sql
│       │       └── 0002_llm_tasks.sql
│       │
│       ├── models/
│       │   ├── mod.rs
│       │   ├── registry.rs             # 已下载模型注册与校验
│       │   └── downloader.rs           # reqwest 流式下载 + SHA256 校验
│       │
│       ├── config/
│       │   ├── mod.rs
│       │   └── schema.rs               # serde 配置结构体
│       │
│       ├── i18n/
│       │   └── mod.rs                  # 运行时加载 JSON 翻译文件
│       │
│       └── commands/                   # Tauri IPC 入口（tauri-specta）
│           ├── mod.rs
│           ├── audio.rs
│           ├── transcription.rs
│           ├── llm.rs
│           ├── workspace.rs
│           ├── timeline.rs
│           ├── models.rs
│           ├── settings.rs
│           └── theme.rs
│
├── src/                                # React 前端
│   ├── main.tsx
│   ├── App.tsx
│   ├── router.tsx                      # TanStack Router 路由定义
│   ├── components/
│   │   ├── ui/                         # shadcn/ui 基础组件（CLI 生成）
│   │   ├── layout/
│   │   │   ├── Shell.tsx               # 顶层布局容器
│   │   │   ├── ActivityBar.tsx         # 左侧图标导航栏
│   │   │   ├── SecondPanel.tsx         # 可调宽二级面板
│   │   │   ├── TopBar.tsx              # 面包屑 + 页面操作
│   │   │   └── StatusBar.tsx           # 底部状态栏
│   │   ├── recording/                  # 实时录音界面
│   │   ├── transcription/              # 转写结果视图
│   │   ├── workspace/                  # 文档库界面
│   │   ├── timeline/                   # 时间轴界面
│   │   └── settings/                   # 设置面板
│   ├── hooks/                          # 自定义 React hooks
│   ├── store/
│   │   ├── recording.ts                # 录音状态
│   │   ├── transcription.ts            # 转写结果
│   │   ├── llm.ts                      # LLM 流式任务
│   │   ├── workspace.ts                # 文档库
│   │   ├── timeline.ts                 # 时间轴
│   │   ├── settings.ts                 # 应用设置
│   │   └── theme.ts                    # 主题状态
│   ├── lib/
│   │   ├── bindings.ts                 # tauri-specta 自动生成（不手写）
│   │   └── utils.ts
│   └── styles/
│       ├── globals.css                 # Tailwind base + CSS 变量定义
│       └── themes/
│           ├── tokyo-night.css
│           ├── tokyo-night-storm.css
│           └── tokyo-night-light.css
│
├── resources/
│   ├── translations/
│   │   ├── en_US.json
│   │   ├── zh_CN.json
│   │   └── fr_FR.json
│   ├── themes/                         # 用户可导入的主题 JSON token 文件
│   │   ├── tokyo-night.json
│   │   ├── tokyo-night-storm.json
│   │   └── tokyo-night-light.json
│   └── models.toml                     # 模型注册表（URL + SHA256，配置驱动）
│
├── .github/workflows/
│   └── release.yml                     # macOS + Windows + Linux 矩阵构建
│
└── package.json
```

---

## 4. 音频管线与推理调度

### 4.1 采样率匹配（关键）

whisper-rs 强制要求 **16000Hz 单声道 f32**。cpal 采集的设备格式由 OS 决定（通常 44100Hz 或 48000Hz，立体声）。转换层必须在数据进入 Whisper 之前完成。

**转换链**：

```
cpal 原始 PCM（interleaved, 任意Hz, 任意ch）
  → 立体声转单声道（左右声道平均）
  → rubato::FftFixedIn<f32>（任意Hz → 16000Hz）
  → Vec<f32>（16000Hz, 单声道）
```

`AudioResampler` 在采集启动时从 cpal 设备配置读取实际采样率，运行时构建 rubato 实例，**不硬编码任何采样率假设**。

### 4.2 后台推理调度（防止 GUI 阻塞）

**原则**：Tauri command 函数只发消息，立即返回；所有推理在独立 tokio task 中运行。

**架构**：

```
lib.rs 应用启动
  ├── tokio::spawn → TranscriptionWorker::run()  [长驻]
  │     loop { recv AudioChunk → whisper 推理 → emit event }
  ├── tokio::spawn → LlmWorker::run()            [长驻]
  │     loop { recv LlmTask → llama 推理(流式) → emit token events }
  └── tokio::spawn → ModelManager::run()         [长驻]
        loop { recv DownloadRequest → reqwest 下载 → emit progress }

AppState（Arc，注入所有 commands）
  ├── transcription_tx: mpsc::Sender<TranscriptionCommand>
  ├── llm_tx:           mpsc::Sender<LlmTask>
  └── model_tx:         mpsc::Sender<DownloadRequest>
```

Tauri command 正确模式：
```rust
#[tauri::command]
#[specta::specta]
pub async fn start_realtime(state: tauri::State<'_, AppState>) -> Result<(), AppError> {
    // 仅发消息，不等待推理结果
    state.transcription_tx.send(TranscriptionCommand::Start).await
        .map_err(AppError::channel)
}
```

### 4.3 模型管理

- **不打包进安装包**：模型存储在 `{APP_DATA}/models/`
- **启动检测**：若模型缺失，emit `models:required` 事件，前端展示下载引导
- **下载**：reqwest 流式下载，每 chunk emit `models:progress`（含 downloaded/total/percent）
- **校验**：下载完成后 SHA256 验证，失败则删除重试
- **配置驱动**：所有模型 URL 和 SHA256 存于 `resources/models.toml`，不硬编码

---

## 5. IPC 层设计（tauri-specta）

所有 Rust 命令标注 `#[specta::specta]`，构建时自动生成 `src/lib/bindings.ts`。前端代码**只从 `bindings.ts` 引入**，禁止手写 `invoke` 字符串。

**事件清单**：

| 事件名 | Payload | 触发方 | 消费方 |
|--------|---------|--------|--------|
| `transcription:segment` | `SegmentPayload` | TranscriptionWorker | 录音页实时字幕 |
| `transcription:done` | `RecordingId` | TranscriptionWorker | 录音页完成状态 |
| `llm:token` | `TokenPayload { task_id, token }` | LlmWorker | 流式文本显示 |
| `llm:done` | `TaskId` | LlmWorker | 任务完成标记 |
| `models:required` | `MissingModels[]` | ModelManager | 下载引导弹窗 |
| `models:progress` | `DownloadProgress` | ModelManager | 进度条 |
| `models:downloaded` | `ModelId` | ModelManager | 下载完成通知 |
| `audio:level` | `f32` (0.0-1.0) | AudioCapture | StatusBar 音频电平 |

---

## 6. 前端架构

### 6.1 UI 布局（对标 Obsidian/AnythingLLM）

```
┌──┬───────────────────────────────────────────────────────┐
│  │  TopBar：面包屑 + 当前页操作按钮 + 录音状态指示灯     │
│  ├──────────────┬────────────────────────────────────────┤
│A │  SecondPanel │                                        │
│c │  （随页面变  │           MainContent                  │
│t │   化的上下   │           各功能页主体内容              │
│i │   文面板）   │                                        │
│v │              │                                        │
│i │  录音页：    │                                        │
│t │    设备/参数 │                                        │
│y │  转写页：    │                                        │
│B │    文件列表  │                                        │
│a │  Workspace:  │                                        │
│r │    文档树    │                                        │
│  │  Timeline:   │                                        │
│  │    日程列表  │                                        │
│  ├──────────────┴────────────────────────────────────────┤
│  │  StatusBar：模型状态 / 音频电平 / 语言 / 版本         │
└──┴───────────────────────────────────────────────────────┘
```

SecondPanel 宽度可拖拽，可完全折叠。各页面通过路由插槽分别提供 panel 和 main 内容，不使用条件渲染大杂烩。

### 6.2 路由结构

```
/                   → redirect to /recording
/recording          → RecordingPanel + RecordingMain
/transcription      → TranscriptionPanel + TranscriptionMain
/workspace          → WorkspacePanel + WorkspaceMain
/workspace/:docId   → WorkspacePanel + DocumentMain
/timeline           → TimelinePanel + TimelineMain
/settings           → SettingsPanel + SettingsMain
/settings/models    → ModelsPanel + ModelsMain
/settings/theme     → ThemePanel + ThemeMain
```

### 6.3 Zustand Store 分层

每个 store 单一职责，跨 store 依赖通过 hook 组合，不在 store 内互相引用：

```typescript
// 各 store 的职责边界
useRecordingStore   // status, deviceId, audioLevel, segments, start/stop
useTranscriptionStore // files, results, progress
useLlmStore         // tasks: Map<taskId, { status, tokens[] }>, submitTask
useWorkspaceStore   // folders, documents, currentDoc, search
useTimelineStore    // events, dateRange, selectedEvent
useSettingsStore    // all app settings, persist via Tauri store plugin
useThemeStore       // current, themes[], setTheme, import/exportTheme
```

---

## 7. 主题系统（VSCode 风格）

### 7.1 三层 Token 架构

```
原语层（Primitive）    语义层（Semantic）        Tailwind / CSS 消费
──────────────────     ──────────────────        ──────────────────
#1a1b26          ────► --color-bg-primary   ────► bg-bg-primary
#c0caf5          ────► --color-text-primary ────► text-text-primary
#7aa2f7          ────► --color-accent       ────► text-accent
```

### 7.2 主题 JSON 格式（用户可自定义）

```json
{
  "name": "Tokyo Night",
  "type": "dark",
  "semanticTokens": {
    "bg.primary":     "#1a1b26",
    "bg.secondary":   "#16161e",
    "bg.sidebar":     "#13131a",
    "bg.input":       "#14141b",
    "bg.hover":       "#202330",
    "bg.selection":   "#3d59a144",
    "text.primary":   "#c0caf5",
    "text.secondary": "#787c99",
    "text.muted":     "#515670",
    "text.disabled":  "#545c7e",
    "accent.primary": "#7aa2f7",
    "accent.hover":   "#3d59a1",
    "accent.muted":   "#3d59a144",
    "border.default": "#29355a",
    "border.focus":   "#545c7e33",
    "status.error":   "#f7768e",
    "status.warning": "#e0af68",
    "status.success": "#9ece6a",
    "status.info":    "#2ac3de"
  }
}
```

**内置主题**：Tokyo Night / Tokyo Night Storm / Tokyo Night Light（直接从 `docs/themes/` 转换）

**用户自定义流程**（对标 VSCode）：
1. 设置 → 主题 → 新建主题（从现有主题克隆）
2. 可视化 token 编辑器（颜色选择器）实时预览
3. 导出为 JSON 文件（可分享）
4. 从文件导入，JSON schema 校验后生效

### 7.3 Tailwind 配置接入

```typescript
// tailwind.config.ts
theme: {
  extend: {
    colors: {
      bg:     { primary: 'var(--color-bg-primary)', secondary: '...', sidebar: '...', input: '...', hover: '...', selection: '...' },
      text:   { primary: 'var(--color-text-primary)', secondary: '...', muted: '...', disabled: '...' },
      accent: { DEFAULT: 'var(--color-accent-primary)', hover: '...', muted: '...' },
      border: { DEFAULT: 'var(--color-border-default)', focus: '...' },
      status: { error: '...', warning: '...', success: '...', info: '...' },
    }
  }
}
```

---

## 8. 数据库设计

### 8.1 核心 Schema

```sql
-- 0001_initial.sql

CREATE TABLE recordings (
    id          TEXT PRIMARY KEY,          -- UUID
    title       TEXT NOT NULL,
    file_path   TEXT NOT NULL,
    duration_ms INTEGER NOT NULL DEFAULT 0,
    language    TEXT,
    created_at  INTEGER NOT NULL,
    updated_at  INTEGER NOT NULL
);

CREATE TABLE transcription_segments (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    recording_id TEXT NOT NULL REFERENCES recordings(id) ON DELETE CASCADE,
    start_ms     INTEGER NOT NULL,
    end_ms       INTEGER NOT NULL,
    text         TEXT NOT NULL,
    language     TEXT,
    confidence   REAL
);
CREATE INDEX idx_segments_recording ON transcription_segments(recording_id);

CREATE TABLE workspace_folders (
    id         TEXT PRIMARY KEY,
    parent_id  TEXT REFERENCES workspace_folders(id) ON DELETE CASCADE,
    name       TEXT NOT NULL,
    created_at INTEGER NOT NULL
);

CREATE TABLE workspace_documents (
    id           TEXT PRIMARY KEY,
    folder_id    TEXT REFERENCES workspace_folders(id) ON DELETE SET NULL,
    title        TEXT NOT NULL,
    file_path    TEXT,
    content_text TEXT,
    source_type  TEXT NOT NULL,            -- 'recording' | 'import' | 'manual'
    recording_id TEXT REFERENCES recordings(id) ON DELETE SET NULL,
    created_at   INTEGER NOT NULL,
    updated_at   INTEGER NOT NULL
);

-- 全文搜索
CREATE VIRTUAL TABLE workspace_fts USING fts5(
    title, content_text,
    content=workspace_documents,
    content_rowid=rowid
);

CREATE TABLE timeline_events (
    id           TEXT PRIMARY KEY,
    title        TEXT NOT NULL,
    start_at     INTEGER NOT NULL,
    end_at       INTEGER NOT NULL,
    description  TEXT,
    tags         TEXT,                     -- JSON array
    recording_id TEXT REFERENCES recordings(id) ON DELETE SET NULL,
    created_at   INTEGER NOT NULL
);

CREATE TABLE model_registry (
    model_id      TEXT PRIMARY KEY,        -- 'whisper/medium' | 'llm/qwen2.5-7b-q4'
    file_path     TEXT NOT NULL,
    sha256        TEXT NOT NULL,
    size_bytes    INTEGER NOT NULL,
    downloaded_at INTEGER NOT NULL
);

CREATE TABLE app_settings (
    key        TEXT PRIMARY KEY,
    value      TEXT NOT NULL,              -- JSON 序列化
    updated_at INTEGER NOT NULL
);
```

```sql
-- 0002_llm_tasks.sql

CREATE TABLE llm_tasks (
    id           TEXT PRIMARY KEY,
    document_id  TEXT REFERENCES workspace_documents(id) ON DELETE CASCADE,
    task_type    TEXT NOT NULL,            -- 'summary' | 'translation' | 'brief'
    status       TEXT NOT NULL DEFAULT 'pending',
    result_text  TEXT,
    error_msg    TEXT,
    created_at   INTEGER NOT NULL,
    completed_at INTEGER
);
```

---

## 9. 跨平台构建

### 9.1 目标产物

| 平台 | 产物 | 硬件加速 |
|------|------|---------|
| macOS (Universal) | `.dmg` + `.app` | CoreML（Whisper）+ Metal（LLM）|
| Windows x64 | `.msi` + `.exe` | CPU（默认），CUDA（feature flag）|
| Linux x64 | `.AppImage` + `.deb` | CPU（默认），CUDA（feature flag）|

### 9.2 Cargo 特性与编译标志

```toml
[features]
default = []
cuda = ["llama-cpp-2/cuda", "whisper-rs/cuda"]

[dependencies]
whisper-rs  = { version = "0.11", features = ["coreml"] }
llama-cpp-2 = { version = "0.1",  features = ["metal"] }
cpal        = "0.15"
rubato      = "0.15"
sqlx        = { version = "0.8", features = ["sqlite", "runtime-tokio", "macros"] }
reqwest     = { version = "0.12", features = ["stream", "json"] }
tokio       = { version = "1",    features = ["full"] }
serde       = { version = "1",    features = ["derive"] }
thiserror   = "1"
uuid        = { version = "1",    features = ["v4"] }
tauri       = { version = "2",    features = ["protocol-asset"] }
specta      = "2"
tauri-specta = { version = "2",   features = ["derive"] }
```

### 9.3 GitHub Actions 矩阵

```yaml
strategy:
  matrix:
    include:
      - os: macos-latest
        args: --target universal-apple-darwin
      - os: windows-latest
        args: ''
      - os: ubuntu-22.04
        args: ''
```

macOS 构建自动产出 Universal Binary（Intel + Apple Silicon）。Linux 构建需预装 `libwebkit2gtk-4.1-dev` 等系统依赖（CI 中 apt 安装）。

---

## 10. 功能清单（v3.0.0 范围）

| 功能 | 优先级 | 说明 |
|------|--------|------|
| 实时录音 + VAD + 流式转写 | P0 | 核心功能 |
| 批量文件转写 | P0 | 支持常见音视频格式 |
| 本地 LLM 摘要（流式） | P0 | llama-cpp-2，逐 token 显示 |
| Workspace 文档库 | P1 | 文档管理 + 全文搜索 |
| 本地时间轴 | P1 | 无 OAuth，纯本地事件管理 |
| 翻译（LLM 驱动） | P1 | 替换旧版 ONNX 翻译引擎 |
| 模型下载管理器 | P0 | 首次启动引导，进度条下载 |
| 主题系统（VSCode 风格） | P1 | 3 内置主题 + 用户自定义 |
| 国际化（中/英/法） | P1 | 运行时 JSON 加载 |
| PDF/DOCX 导入 | P2 | Workspace 文档导入 |

---

## 11. 关键风险与缓解措施

| 风险 | 严重度 | 缓解措施 |
|------|--------|---------|
| Rust 学习曲线（FFI/unsafe/所有权） | 高 | 从 commands/ 层入手，推迟接触 whisper-rs/llama-cpp-2 unsafe 代码；优先跑通端到端 demo |
| whisper-rs CoreML 构建配置 | 高 | 单独写构建验证脚本，在 CI 中尽早跑通，不等功能完整 |
| llama-cpp-2 Metal/CUDA 编译标志 | 高 | CPU-only 先跑通推理，硬件加速作为可选 feature，分阶段验证 |
| Linux WebKitGTK 版本差异 | 中 | 锁定 ubuntu-22.04 作为 CI 基准，文档说明最低 GTK 版本要求 |
| cpal 在 Linux ALSA/PulseAudio/PipeWire 的差异 | 中 | 优先适配 PipeWire（现代发行版默认），ALSA 作为 fallback |
| LLM 推理期间内存压力（4B+ 模型） | 中 | 默认推荐 Q4 量化，设置页提示模型内存需求，低内存设备警告 |

---

## 12. 里程碑规划（参考，无硬性时限）

| 里程碑 | 交付内容 |
|--------|---------|
| M1：骨架可运行 | Tauri 项目初始化，前端路由/布局/主题系统跑通，Rust 模块目录建立 |
| M2：音频转写端到端 | 麦克风 → 重采样 → whisper-rs → 实时字幕显示完整跑通 |
| M3：LLM 流式推理 | llama-cpp-2 集成，摘要/翻译流式 token 显示 |
| M4：Workspace + Timeline | 文档库 CRUD，全文搜索，本地时间轴 |
| M5：模型管理 + 主题自定义 | 首次启动引导，下载进度，主题编辑器 |
| M6：跨平台构建验证 | CI 三平台全部产出可安装包，v3.0.0 beta |
