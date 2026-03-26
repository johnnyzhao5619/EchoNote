# EchoNote v3.0.0 — AGENTS Guide

> **v3 分支**：Python v2 代码已全部移除，此分支为 Tauri 2.x + Rust 全量重写起点。
> **参考**：v2 Python 代码保留在 `main` 分支，可随时 `git show main:<path>` 查阅旧实现逻辑。

---

## 全局工程原则（必须遵守）

过程中保证不要遗漏任何部分，避免 mock 数据、避免冗余代码、避免同一逻辑在多个部分多次实现、避免硬编码，保证代码结构清晰且保证代码易维护性，清理陈旧和冗余的代码。

始终融入的原则：
1. **系统性思维**：看到具体问题时，思考整个系统。
2. **第一性原理**：从功能本质出发，而不是现有代码。
3. **DRY 原则**：发现重复代码必须指出。
4. **长远考虑**：评估技术债务和维护成本。

绝对禁止：
1. 在没有完整审查现有代码之前修改任何代码。
2. 急于给出解决方案。
3. 跳过搜索和理解步骤。
4. 不分析就推荐方案。
5. 随意假设——假设时必须说明理由。

使用**中文**回复。

---

## 项目背景

**EchoNote v3.0.0** 是对 v2（Python + PySide6）的完全重写，驱动因素：

| 问题 | v2 现状 | v3 解法 |
|------|---------|---------|
| UI 现代化 | PySide6 + QSS 有质感天花板 | Tauri + React + Tailwind + shadcn/ui |
| LLM 集成质量 | subprocess 调用 GGUF，无流式输出 | llama-cpp-2 直接绑定，token 流式推送 |

**硬切换**：不做数据迁移，不考虑向后兼容，以 v3.0.0 全新发布。

---

## 技术栈

| 层 | 技术 |
|----|------|
| 应用框架 | Tauri 2.x |
| 前端 | React 18 + TypeScript + Tailwind CSS v3 + shadcn/ui |
| 前端状态 | Zustand |
| 前端路由 | TanStack Router |
| IPC | tauri-specta v2（Rust → TypeScript 自动类型生成）|
| 音频采集 | cpal 0.15 |
| 采样率转换 | rubato 0.15（任意 Hz → 16000Hz）|
| 语音转写 | whisper-rs 0.11（whisper.cpp，CoreML/Metal/CUDA）|
| 本地 LLM | llama-cpp-2（llama.cpp，Metal/CUDA/CPU）|
| 数据库 | sqlx 0.8 + SQLite（WAL 模式，FTS5）|
| HTTP 下载 | reqwest 0.12（流式，SHA256 校验）|
| 错误处理 | thiserror 1 |
| 异步运行时 | tokio 1（full features）|

---

## 分支策略

```
main     ← Python v2 代码（只读参考，打了 v2-archive 参考点）
  └── v3 ← 当前开发分支（本分支），Tauri + Rust 全新实现
             ↓ v3.0.0 完成后
             → 替换 main，发布 Release
```

**查阅 v2 实现参考**（不修改）：
```bash
git show main:core/workspace/manager.py
git show main:engines/audio/capture.py
git show main:resources/translations/zh_CN.json
```

---

## 项目目录结构（目标态）

```
echonote/
├── src-tauri/                      # Rust 后端
│   ├── Cargo.toml
│   ├── tauri.conf.json
│   ├── build.rs                    # 编译标志（CoreML/Metal/CUDA）
│   └── src/
│       ├── main.rs                 # Tauri 启动入口
│       ├── lib.rs                  # 模块注册 + AppState 初始化
│       ├── state.rs                # AppState（Arc 共享状态）
│       ├── error.rs                # 统一错误类型（thiserror）
│       ├── audio/                  # 音频采集 + 重采样 + VAD
│       ├── transcription/          # whisper-rs 推理 + 批量队列
│       ├── llm/                    # llama-cpp-2 推理 + AI 任务
│       ├── workspace/              # 文档库 CRUD + 解析 + 导出
│       ├── timeline/               # 本地时间轴（无 OAuth）
│       ├── storage/                # sqlx 连接池 + migrations
│       ├── models/                 # 模型注册 + reqwest 下载器
│       ├── config/                 # serde 配置结构体
│       ├── i18n/                   # 运行时 JSON 翻译加载
│       └── commands/               # Tauri IPC 命令（每模块一文件）
│
├── src/                            # React 前端
│   ├── components/
│   │   ├── ui/                     # shadcn/ui 基础组件
│   │   ├── layout/                 # Shell / ActivityBar / SecondPanel / TopBar / StatusBar
│   │   ├── recording/
│   │   ├── transcription/
│   │   ├── workspace/
│   │   ├── timeline/
│   │   └── settings/
│   ├── store/                      # Zustand stores（每模块一文件）
│   ├── hooks/                      # 自定义 React hooks
│   ├── lib/
│   │   ├── bindings.ts             # tauri-specta 自动生成（不手写）
│   │   └── utils.ts
│   └── styles/
│       ├── globals.css             # Tailwind base + CSS 变量
│       └── themes/                 # 主题 CSS 文件（Tokyo Night 等）
│
├── resources/
│   ├── translations/               # i18n JSON（en_US / zh_CN / fr_FR）
│   ├── themes/                     # 主题 JSON token 文件
│   ├── prompts/tasks.toml          # LLM 任务提示模板
│   ├── models.toml                 # 模型注册表（URL + SHA256）
│   └── icons/                      # 应用图标
│
├── docs/
│   └── superpowers/
│       ├── specs/                  # 设计规格文档
│       └── plans/                  # M1-M11 实施计划
│
├── .github/workflows/
│   ├── ci.yml                      # PR 质量门禁（三平台矩阵）
│   ├── release.yml                 # tag 触发自动发布
│   └── models-checksum.yml         # 手动触发 SHA256 计算
│
└── echonote-landing/               # 官网落地页（独立 Vue 项目）
```

---

## 架构核心不变量（违反即为 Bug）

### Rust 后端

1. **命令函数不执行任何 whisper/llama 推理**
   ```rust
   // ✅ 正确
   #[tauri::command]
   pub async fn start_realtime(state: State<'_, AppState>) -> Result<(), AppError> {
       state.transcription_tx.send(TranscriptionCommand::Start).await?;
       Ok(())  // 立即返回，不等推理结果
   }
   // ❌ 错误：在 command 函数里直接调用 whisper/llama
   ```
   - 命令层可以启动/停止采集线程、读取轮询状态、写数据库
   - 命令层**不允许**直接执行 whisper/llama 推理，也不允许等待模型流式结果

2. **三个长驻后台 Worker，应用启动时由 `lib.rs` spawn**
   - `TranscriptionWorker::run()` — 音频块 → whisper-rs → 写入实时缓存，并可 best-effort emit `transcription:segment`
   - `LlmWorker::run()` — LlmTask → llama-cpp-2（spawn_blocking）→ emit `llm:token`
   - `ModelManager::run()` — DownloadRequest → reqwest → emit `models:progress`

3. **采样率转换必须发生在数据进入 Whisper 之前**
   - cpal 原始 PCM → 立体声转单声道 → rubato（任意 Hz → 16000Hz）→ Whisper
   - 采样率在运行时从 cpal 设备读取，**不硬编码**

4. **模型不打包进安装包**
   - 存储路径：`{APP_DATA}/models/whisper/` 和 `{APP_DATA}/models/llm/`
   - 启动时检测，缺失则 emit `models:required`，前端显示下载引导

5. **数据库类型名**：`pub struct Database` in `storage/db.rs`，AppState 中为 `pub db: Arc<Database>`

6. **migration 编号顺序**：
   - `0001_initial.sql` — 所有基础表（含 workspace_text_assets）
   - `0002_llm_tasks.sql` — llm_tasks 表
   - `0003_workspace_assets.sql` — FTS5 自动维护 trigger（仅 trigger，不重建表）
   - `0004_llm_tasks_patch.sql` — 条件性补丁（若字段缺失）

### 前端

7. **所有 IPC 调用必须通过 `src/lib/bindings.ts`**
   - `bindings.ts` 由 tauri-specta 自动生成，不手写
   - 禁止在组件中直接写 `invoke('command_name', ...)` 字符串

8. **主题系统三层**：Primitive 色值 → Semantic token（CSS 变量）→ Tailwind 类
   - 所有颜色通过 `var(--color-*)` CSS 变量消费，不写死十六进制

9. **Tauri Event 命名约定**：`{domain}:{action}`
   - 录音域当前以前端轮询命令为主：`get_audio_level`、`get_realtime_segments`、`get_recording_status`
   - `transcription:segment`、`transcription:status`、`audio:level` 仅作为兼容/调试用的 best-effort 事件，不作为录音页正确性的唯一依据
   - `llm:token`、`llm:done`、`llm:error`
   - `models:required`、`models:progress`、`models:downloaded`、`models:error`
   - `batch:progress`、`batch:done`、`batch:error`
   - `locale:changed`、`theme:changed`

---

## 关键设计决策速查

| 问题 | 决策 | 原因 |
|------|------|------|
| LLM 流式输出 | unbounded_channel + spawn_blocking | llama-cpp-2 同步 API，需桥接 tokio |
| 任务取消 | `DashMap<String, Arc<AtomicBool>>` | 多任务并发取消，无锁竞争 |
| 批量转写 | `VecDeque` 串行执行 | 避免多模型并发占用内存 |
| 会议纪要解析 | Unicode `.+?` 正则（非 `\w`） | 支持中英文 section 标题 |
| ffmpeg 转码 | tauri-plugin-shell 调用系统 ffmpeg | 避免 GPL 绑定，用户自行安装 |
| 主题存储 | `app_settings` KV 表（JSON） | 统一持久化入口，无额外文件 |
| i18n 加载 | 前端按命名空间懒加载 | 避免首屏加载全部翻译 |
| Calendar | 仅本地时间轴，无 OAuth | v3.0.0 范围外，降低复杂度 |

---

## 里程碑概览与依赖关系

```
M1 项目骨架+主题+布局
  └── M2 数据库+设置
        └── M3 模型下载管理器
              ├── M4 音频管线+实时转写 ──→ M7 批量转写+导入
              ├── M5 LLM 引擎+AI 任务  ─┐
              └── M6 Workspace 文档库  ←┘→ M8 本地时间轴
                                          M9 国际化 i18n
                                          M10 主题自定义编辑器
M11 跨平台 CI/CD（所有功能完成后）
```

---

## 结构变更同步要求（强制）

当项目目录结构、模块职责、IPC 命令签名、Tauri Event 名称发生变化时，
必须在同一变更中同步更新：

1. **`AGENTS.md`**：更新"目录结构""架构核心不变量""Tauri Event 命名约定"。
2. **`docs/superpowers/specs/`**：若影响架构设计，更新规格文档。
3. **`src/lib/bindings.ts`**：tauri-specta 重新生成（`cargo test` 会触发）。
4. **`CHANGELOG.md`**：记录破坏性变更。

---

## Release Workflow（v3.0.0）

1. 确认所有 M1-M11 完成，`cargo test` + `npm run typecheck` + `npm run lint` 全绿。
2. 更新 `src-tauri/tauri.conf.json` 中的 `version` 字段（单一来源）。
3. 同步 `src-tauri/Cargo.toml` 中的 `version`（与 tauri.conf.json 保持一致）。
4. 更新 `CHANGELOG.md`，添加 v3.0.0 版本节。
5. 运行 `models-checksum.yml` 工作流，填入 `resources/models.toml` 的 SHA256。
6. Commit：`release: v3.0.0`
7. Tag：`git tag -a v3.0.0 -m "EchoNote v3.0.0 — Tauri+Rust complete rewrite"`
8. Push：`git push origin v3 && git push origin v3.0.0`
9. 等待 `release.yml` 完成，确认三平台安装包产出。
10. 将 v3 分支内容替换 main：
    ```bash
    git checkout main
    git reset --hard v3
    git push origin main --force-with-lease
    ```

---

## Hard Rules

- 不在 Tauri command 函数内执行任何推理（whisper/llama），只发 channel 消息。
- 不把模型文件打包进安装包。
- 不手写 `bindings.ts`，始终由 tauri-specta 生成。
- 不跳过 TDD：先写失败测试，再写实现，再确认通过。
- 不直接在主 tokio 线程调用同步推理 API，必须 `spawn_blocking`。
- 不使用 `unwrap()` 或 `expect()` 处理用户输入路径，统一走 `AppError`。
