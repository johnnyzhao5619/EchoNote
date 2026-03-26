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

1. **命令函数只发消息，不执行推理**
   ```rust
   // ✅ 正确
   #[tauri::command]
   pub async fn start_realtime(state: State<'_, AppState>) -> Result<(), AppError> {
       state.transcription_tx.send(TranscriptionCommand::Start).await?;
       Ok(())  // 立即返回，不等推理结果
   }
   // ❌ 错误：在 command 函数里直接调用 whisper/llama
   ```

2. **三个长驻后台 Worker，应用启动时由 `lib.rs` spawn**
   - `TranscriptionWorker::run()` — 音频块 → whisper-rs → emit `transcription:segment`
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
   - `transcription:segment`、`transcription:status`
   - `llm:token`、`llm:done`、`llm:error`
   - `models:required`、`models:progress`、`models:downloaded`、`models:error`
   - `audio:level`、`batch:progress`、`batch:done`、`batch:error`
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

**可并行执行**：M4 + M5、M7 + M8 + M10、M9 最后补全

---

## 执行提示词（逐里程碑）

### 通用前置说明（每次都附在里程碑提示词之前）

```
你是 EchoNote v3.0.0 的实施工程师。

项目仓库：/Users/weijiazhao/Dev/EchoNote（当前在 v3 分支）
规格文档：docs/archive/superpowers/specs/2026-03-20-echonote-v3-tauri-rewrite-design.md
实施计划：docs/archive/superpowers/plans/（M1-M11 共 11 份）
架构上下文：AGENTS.md（本文件）

执行原则：
1. 执行前必须完整阅读对应里程碑的计划文件
2. 严格按计划中的步骤顺序执行，不跳步
3. 每个 Step 必须先运行测试确认 FAIL，再写实现，再确认 PASS（TDD）
4. 每完成一个 Task 立即 commit（使用计划中指定的 commit message）
5. 遇到计划未覆蓋的情况，停下来说明，不自行假设
6. 不修改计划文件本身
7. v2 Python 代码在 main 分支，可用 git show main:<path> 查阅旧实现逻辑，但不复制
```

---

### M1 — 项目骨架 + 主题系统 + 应用布局

```
请使用 superpowers:executing-plans 技能执行以下计划：

计划文件：docs/archive/superpowers/plans/2026-03-20-m1-scaffold-theme-layout.md

目标：在项目根目录 /Users/weijiazhao/Dev/EchoNote 内初始化 Tauri 2.x + React 18
项目骨架，建立三层主题系统（CSS Variables），应用壳层布局（ActivityBar /
SecondPanel / TopBar / StatusBar）和 TanStack Router 路由结构。

M1 完成标准：
- npm run tauri dev 可以启动应用，显示完整布局骨架
- 主题切换（Tokyo Night / Storm / Light）即时生效
- 5 个路由页面可导航（内容为空占位符即可）
- cargo test 全绿，npm run typecheck 零错误
```

---

### M2 — 数据库层 + 设置系统

```
请使用 superpowers:executing-plans 技能执行以下计划：

计划文件：docs/archive/superpowers/plans/2026-03-20-m2-database-settings.md

前置条件：M1 已完成，npm run tauri dev 可正常启动。

目标：建立 sqlx + SQLite（WAL 模式）数据库层，执行 0001_initial.sql 和
0002_llm_tasks.sql migration，实现 AppConfig 设置系统（Rust 后端 + React 设置页面）。

M2 完成标准：
- 应用启动后 {APP_DATA}/echonote.db 自动创建，包含所有设计表
- /settings 页面可读写应用配置（语言、主题等）
- cargo test 全绿，包含数据库集成测试
```

---

### M3 — 模型下载管理器

```
请使用 superpowers:executing-plans 技能执行以下计划：

计划文件：docs/archive/superpowers/plans/2026-03-20-m3-model-manager.md

前置条件：M1、M2 已完成。

目标：实现模型注册表（resources/models.toml）、reqwest 流式下载器
（含 SHA256 校验和 5 秒滑动窗口速度计算）、首次启动模型引导弹窗、
/settings/models 设置子页面。

M3 完成标准：
- 首次启动时若无模型，显示引导弹窗
- 下载过程实时显示速度（KB/s）和 ETA
- 下载完成后 SHA256 自动校验
- 可取消下载、删除模型、设为当前活跃模型
- cargo test 全绿（含 wiremock 下载测试）
```

---

### M4 — 音频管线 + 实时转写

```
请使用 superpowers:executing-plans 技能执行以下计划：

计划文件：docs/archive/superpowers/plans/2026-03-20-m4-audio-transcription.md

前置条件：M1、M2、M3 已完成，whisper 模型已下载至 APP_DATA/models/。

目标：实现完整实时音频录制管线：
cpal 麦克风采集 → rubato 重采样（任意 Hz → 16000Hz 单声道）→
VAD 静音过滤 → whisper-rs 推理（spawn_blocking）→ Tauri Event 流式字幕。
录音结束后自动保存 WAV、写入 recordings 表、创建 workspace_documents 记录。

M4 完成标准：
- 录音页面可以开始/暂停/停止录音
- 录音时底部 StatusBar 显示音频电平
- 转写文字实时出现在页面上（segment by segment）
- 录音结束后文件自动出现在 Workspace
- cargo test 包含重采样比例测试和 VAD 测试
```

---

### M5 — LLM 推理引擎 + AI 任务

```
请使用 superpowers:executing-plans 技能执行以下计划：

计划文件：docs/archive/superpowers/plans/2026-03-20-m5-llm-engine.md

前置条件：M1、M2、M3 已完成，LLM 模型已下载。M4 可同步进行。

目标：实现 llama-cpp-2 本地 LLM 推理引擎，支持流式 token 推送
（unbounded channel → Tauri Event），DashMap 管理多任务取消；
从 resources/prompts/tasks.toml 加载提示模板；
实现摘要、会议纪要（结构化解析）、翻译、问答四种任务；
前端 AiTaskBar 组件和 StreamingText 逐字渲染。

M5 完成标准：
- Workspace 文档页面的 AI 任务栏可触发摘要生成
- 文字逐字流式出现，可点击「取消」中断
- 会议纪要生成后自动拆分为 4 个 asset（总结/决策/行动项/下一步）
- cargo test 包含 parse_meeting_brief 的中英文和 fallback 测试
```

---

### M6 — Workspace 文档库

```
请使用 superpowers:executing-plans 技能执行以下计划：

计划文件：docs/archive/superpowers/plans/2026-03-20-m6-workspace.md

前置条件：M1、M2 已完成。M5 建议先完成（AI 任务栏依赖 LLM）。

目标：实现文件夹树 CRUD（含递归删除）、文档 CRUD、FTS5 全文搜索
（含 highlight snippet）、多格式导出（MD/TXT/SRT/VTT）、
PDF/DOCX/TXT/MD 文件导入解析；0003_workspace_assets.sql migration
补充 FTS5 自动维护 trigger（不重建表，表已在 M2 的 0001 中创建）。

M6 完成标准：
- 可创建/重命名/删除文件夹（含子文件夹递归删除确认）
- 搜索框输入后 300ms 显示带高亮的搜索结果
- 文档导出为 SRT 格式时时间戳格式正确（HH:MM:SS,mmm）
- PDF 文件可导入并在文档视图显示文本内容
- cargo test 包含递归删除、FTS5 搜索、SRT 时间戳测试
```

---

### M7 — 批量转写 + 文件导入

```
请使用 superpowers:executing-plans 技能执行以下计划：

计划文件：docs/archive/superpowers/plans/2026-03-20-m7-batch-transcription.md

前置条件：M1、M2、M4 已完成。

目标：实现批量媒体文件转写队列（VecDeque 串行执行），支持
WAV/FLAC 直接转写和 MP3/MP4/M4A/MOV/MKV/WEBM/OGG 经 ffmpeg 转码，
临时文件用 NamedTempFile 自动清理；前端支持拖拽上传，
ffmpeg 缺失时显示平台对应安装指引。

M7 完成标准：
- 可拖拽 MP4 文件到转写页，显示队列进度条
- 转写完成后自动跳转链接到 Workspace 对应文档
- 系统无 ffmpeg 时显示安装提示（macOS/Windows/Linux 对应命令）
- cargo test 包含格式检测（8 个 case）和 ffmpeg 检测测试
```

---

### M8 — 本地时间轴

```
请使用 superpowers:executing-plans 技能执行以下计划：

计划文件：docs/archive/superpowers/plans/2026-03-20-m8-timeline.md

前置条件：M1、M2 已完成。M6 建议完成（事件可关联文档）。

目标：实现本地时间轴（无 OAuth），CRUD 时间线事件，tags 以 JSON
字符串存储并在 Rust 侧透明序列化；三视图（月/周/日）；
事件可关联录音和 Workspace 文档；date-fns 处理本地时间显示。

M8 完成标准：
- 月视图正确显示当前月所有事件，有事件的日期高亮
- 周视图事件块高度正比于时长（最小 30px）
- 点击空白处弹出新建事件表单，可添加 tag chip
- cargo test 包含边界值查询和 tags JSON 序列化测试
```

---

### M9 — 国际化 i18n

```
请使用 superpowers:executing-plans 技能执行以下计划：

计划文件：docs/archive/superpowers/plans/2026-03-20-m9-i18n.md

前置条件：M1 已完成。建议在 M6-M8 完成后执行（确保所有 UI 字符串已确定）。

参考：v2 翻译文件在 resources/translations/（保留在此分支作为参考，
结构不同但词条可复用）。

目标：实现三语言（zh_CN/en_US/fr_FR）完整翻译系统，
8 个命名空间 JSON 文件按需懒加载；Rust 侧 I18nRegistry
支持点分路径查找、插值替换和 locale fallback；
前端轻量 useI18n hook（无第三方库）；语言切换即时生效。

M9 完成标准：
- 设置页语言切换后，整个应用所有文字即时切换语言
- 语言设置重启后保持
- StatusBar 显示当前语言，点击可循环切换三语言
- cargo test 包含 fallback 和插值测试；前端测试包含点分路径解析
```

---

### M10 — 主题自定义编辑器

```
请使用 superpowers:executing-plans 技能执行以下计划：

计划文件：docs/archive/superpowers/plans/2026-03-20-m10-theme-editor.md

前置条件：M1（基础主题系统）、M2（app_settings 存储）已完成。

参考：resources/themes/theme_outline.json 包含 v2 的主题 token 契约，
可作为 v3 22 个 semantic token 设计的参考。

目标：在 M1 三内置主题基础上新增用户自定义主题闭环：
从现有主题克隆创建、token 编辑器实时预览（修改即写入 CSS 变量）、
JSON 导入导出、22 个 semantic token schema 校验；
ThemeSelector / ThemeEditor / ThemePreview 三组件。

M10 完成标准：
- 可从 Tokyo Night 克隆并修改任意颜色，应用 UI 实时预览
- 导出 JSON 后可在另一设备导入并生效
- 导入格式错误（缺少 token、颜色非法）时显示具体错误提示
- cargo test 包含 schema 校验（缺 token/颜色非法/名称过长）
```

---

### M11 — 跨平台 CI/CD

```
请使用 superpowers:executing-plans 技能执行以下计划：

计划文件：docs/archive/superpowers/plans/2026-03-20-m11-cicd.md

前置条件：M1-M10 全部完成，代码可在三平台构建。

目标：建立 GitHub Actions 三流水线：
ci.yml（PR 质量门禁，三平台矩阵）、release.yml（tag 触发自动发布，
macOS Universal Binary + Windows MSI + Linux AppImage/deb）、
models-checksum.yml（手动触发 SHA256 计算）；
版本号单一来源（tauri.conf.json），check-version.sh 强制校验。

M11 完成标准：
- 推送 PR 后 ci.yml 在三平台均通过
- 推送 v3.0.0 tag 后 release.yml 产出三平台安装包
- GitHub Release 页面有完整的发布说明（从 CHANGELOG.md 读取）
- 版本号不一致时 CI 构建失败并有明确错误信息
```

---

## 资源文件说明（已保留在 v3 分支）

| 路径 | 用途 | 状态 |
|------|------|------|
| `resources/translations/` | v2 翻译文件，供 M9 复用词条 | 只读参考，M9 会重构 |
| `resources/themes/theme_outline.json` | v2 主题 token 契约，供 M10 参考 | 只读参考 |
| `resources/icons/` | 应用图标（现有 .icns / .ico / .png）| M11 直接使用 |
| `echonote-landing/` | 官网落地页（独立 Vue 项目）| 独立维护，不受 v3 影响 |
| `docs/archive/superpowers/specs/` | v3 架构规格文档 | 权威来源 |
| `docs/archive/superpowers/plans/` | M1-M11 实施计划 | 执行依据 |

---

## 结构变更同步要求（强制）

当项目目录结构、模块职责、IPC 命令签名、Tauri Event 名称发生变化时，
必须在同一变更中同步更新：

1. **`AGENTS.md`**：更新"目录结构""架构核心不变量""Tauri Event 命名约定"。
2. **`docs/archive/superpowers/specs/`**：若影响架构设计，更新规格文档。
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
