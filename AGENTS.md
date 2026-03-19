# EchoNote AGENTS Guide

## 全局工程原则（必须遵守）

过程中保证不要遗漏任何部分，避免mock数据、避免冗余代码、避免同一逻辑在多个部分多次实现、避免硬编码，保证代码结构清晰且保证代码易维护性，清理陈旧和冗余的代码。专注于功能实现，避免过度工程化。不需要考虑向后兼容，也不需要迁移，如有相关代码，可以移除冗余。使用中文回复。

始终应融入的原则包括:
1. 系统性思维：看到具体问题时，思考整个系统。
2. 第一性原理：从功能本质出发，而不是现有代码。
3. DRY原则：发现重复代码必须指出。
4. 长远考虑：评估技术债务和维护成本。

同时绝对禁止:
1. 在没有完整审查现有代码之前修改任何代码。
2. 急于给出解决方案。
3. 跳过搜索和理解步骤。
4. 不分析就推荐方案。
5. 避免随意假设。

## 项目代码结构速查（用于快速定位）

- `main.py`：应用启动入口，初始化管理器与主窗口。
- `config/`：配置与版本信息。
  - `config/__version__.py`：版本单一事实源（SSOT）。
  - `config/default_config.json`：默认配置；模型统一存储根目录由 `models.root_dir` 管理，运行时固定拆分到 `speech/`、`translation/`、`text_ai/` 子目录。
- `core/`：核心业务编排与管理器。
  - `core/workspace/`：统一资产层与 workspace 服务（导入、Vault 路径布局、资产读写、摘要、会议整理）。
  - `core/models/`：模型注册、下载、状态聚合与 Text AI 模型治理。
  - `core/realtime/`：实时录音/转写集成（录音器、路由、归档等）。
  - `core/settings/`：设置读写与偏好聚合。
  - `core/timeline/`：时间线事件与任务调度。
  - `core/calendar/`：日历同步与任务逻辑。
- `engines/`：引擎层实现。
  - `engines/audio/`：音频采集与VAD。
  - `engines/speech/`：语音识别引擎。
  - `engines/translation/`：翻译引擎。
  - `engines/text_ai/`：本地文本 AI 能力（extractive、ONNX 摘要、GGUF 会议整理 runtime）。
- `ui/`：桌面端界面层（PySide6）。
- `ui/workspace/`：统一 workspace 工作台（顶部创建入口、Obsidian 风格单树导航、结构/事件双模式目录、文件夹管理、壳层级批量任务工具窗口、卡片/标签式文本编辑、独立窗口、录音回放与 AI 操作；录音会话完成后的文档、翻译与回放都统一回到 workspace，`recording_session_panel.py` 只承载轻量录音选项弹出层）。
  - `ui/realtime_record/`：实时录音浮动窗与音频可视化组件（主录音入口已硬切到应用壳层底座与 `ui/common/realtime_recording_dock.py`）。
  - `ui/timeline/`：时间线页面与事件卡片（`widget.py`、`event_card.py`、`transcript_viewer.py`）。
  - `ui/settings/`：设置页面（含 `translation_page.py`、`workspace_page.py` 与 `workspace_ai_page.py` 独立默认设置页）。
  - `ui/common/`：通用组件（含音频播放器 `audio_player.py`、启动器 `audio_player_launcher.py`、应用壳层录音底座 `realtime_recording_dock.py`）。
  - `ui/constants.py`：UI尺寸、角色常量与密度基线。
- `resources/`：主题与国际化资源。
  - `resources/themes/light.qss`、`resources/themes/dark.qss`：主题样式。
  - `resources/themes/theme_outline.json`：主题契约轮廓。
  - `resources/translations/`：多语言文案。
- `tests/`：测试体系。
  - `tests/ui/`：UI行为回归。
  - `tests/unit/`：单元测试（含主题契约测试）。
  - `tests/integration/`：集成测试。
- `scripts/`：构建、发布、版本同步与工具脚本。
- `docs/`：设计说明、开发规范与专题方案文档。
  - `docs/plans/`：多阶段功能实施计划与执行拆解文档。
- `echonote-landing/`：官网/落地页前端（独立包版本）。

## 常用定位建议

- 查“统一工作台/文档资产”：优先看 `core/workspace/`（尤其 `manager.py` + `vault_layout.py`）+ `ui/workspace/` + `data/database/models.py`。
- 查“工作台批量转写/转译任务”：优先看 `ui/workspace/task_window.py` + `ui/workspace/task_panel.py` + `ui/main_window.py` + `core/transcription/manager.py` + `ui/batch_transcribe/task_item.py` + `ui/workspace/editor_panel.py`。
- 查“事件/批量任务拖入工作台树”：优先看 `ui/workspace_drag_payload.py` + `ui/workspace/library_panel.py` + `ui/workspace/task_panel.py` + `ui/batch_transcribe/task_item.py` + `ui/timeline/widget.py` + `ui/timeline/event_card.py` + `core/workspace/manager.py`。
- 查“工作台创建入口/录音主控”：优先看 `ui/workspace/library_panel.py` + `ui/common/realtime_recording_dock.py` + `ui/workspace/recording_session_panel.py` + `core/realtime/recorder.py` + `core/workspace/manager.py`；当前录音工作流已收口为“紧凑横向 dock + 录音选项弹出层 + 悬浮窗实时结果 + workspace 完成结果”。
- 查“实时录音/浮动窗”：优先看 `ui/common/realtime_recording_dock.py` + `ui/realtime_record/floating_overlay.py` + `core/realtime/` + `resources/themes/*qss`；悬浮窗现在是实时转录/转译主展示面，与壳层录音 dock 共用同一 recorder 状态，录音落盘与资产发布再看 `core/workspace/manager.py`。
- 查“工作台单树导航/文件夹管理”：优先看 `ui/workspace/library_panel.py` + `ui/workspace/item_list.py` + `core/workspace/manager.py` + `data/database/models.py`。
- 查“文档标签页/独立窗口”：优先看 `ui/workspace/widget.py` + `ui/workspace/editor_panel.py` + `ui/workspace/detached_document_window.py`。
- 查“时间线音频播放”：优先看 `ui/common/audio_player.py` + `ui/common/audio_player_launcher.py` + `ui/timeline/widget.py`。
- 查“本地摘要/会议整理/Text AI”：优先看 `engines/text_ai/` + `core/workspace/summary_service.py` + `core/workspace/meeting_brief_service.py` + `core/models/manager.py`。
- 查“模型下载失败/模型落盘位置”：优先看 `core/models/downloader.py` + `core/models/manager.py` + `core/models/text_ai_registry.py` + `config/default_config.json`；所有受管模型现在统一落在 `models.root_dir/{speech,translation,text_ai}`。
- 查“工作台任务窗口/录音控制台文案”：优先看 `resources/translations/i18n_outline.json` + `resources/translations/zh_CN.json` + `resources/translations/en_US.json` + `resources/translations/fr_FR.json` + `ui/workspace/task_window.py` + `ui/workspace/recording_session_panel.py`。
- 查“工作台红框问题总计划/布局精修”：优先看 `docs/plans/archive/2026-03-15-workspace-redbox-closure-plan-superseded.md` + `ui/constants.py` + `resources/themes/theme_outline.json` + `tests/unit/test_main_window_shell.py` + `tests/ui/test_workspace_widget.py` + `tests/unit/test_i18n_outline_contract.py` + `tests/unit/test_theme_outline_contract.py`。
  历史原始计划文件名 `docs/plans/2026-03-15-workspace-redbox-closure-plan.md` 已被归档 superseded，当前只作为旧引用名保留。
- 查“主题覆盖缺失”：先对照 `ui/constants.py` 的 role，再查双主题与 `theme_outline.json`。
- 查“版本发布遗漏”：先看 `config/__version__.py`，再按发布清单同步其他文件。
- 查“新功能实施计划”：优先看 `docs/plans/`，再回到对应模块代码与测试。

## 功能关键词到文件路径（快速索引）

- 统一工作台入口：`ui/workspace/widget.py`、`ui/main_window.py`、`ui/navigation.py`
- 工作台顶部入口与录音主控：`ui/workspace/library_panel.py`、`ui/common/realtime_recording_dock.py`、`ui/workspace/recording_session_panel.py`、`core/realtime/recorder.py`、`core/workspace/manager.py`
- 工作台批量任务区：`ui/workspace/task_window.py`、`ui/workspace/task_panel.py`、`ui/main_window.py`、`core/transcription/manager.py`、`ui/batch_transcribe/task_item.py`、`ui/workspace/editor_panel.py`
- 工作台外部拖拽协议：`ui/workspace_drag_payload.py`、`ui/workspace/library_panel.py`、`ui/workspace/task_panel.py`、`ui/batch_transcribe/task_item.py`、`ui/timeline/widget.py`、`ui/timeline/event_card.py`、`core/workspace/manager.py`
- 工作台单树导航：`ui/workspace/library_panel.py`、`ui/workspace/item_list.py`、`core/workspace/manager.py`、`data/database/models.py`
- 工作台文档标签页与独立窗口：`ui/workspace/widget.py`、`ui/workspace/editor_panel.py`、`ui/workspace/detached_document_window.py`
- 工作台集合筛选与条目元信息：`ui/workspace/item_list.py`、`core/workspace/manager.py`、`data/database/models.py`
- 统一工作台资产层：`core/workspace/manager.py`、`core/workspace/import_service.py`、`data/database/models.py`
- Markdown Vault 路径布局：`core/workspace/vault_layout.py`、`core/workspace/manager.py`、`core/workspace/import_service.py`、`ui/settings/workspace_page.py`
- 文档导入与解析：`core/workspace/document_parser.py`、`core/workspace/import_service.py`、`tests/unit/core/test_workspace_manager.py`
- 本地摘要与会议整理：`core/workspace/summary_service.py`、`core/workspace/meeting_brief_service.py`、`engines/text_ai/`
- Text AI 模型管理：`core/models/manager.py`、`core/models/text_ai_registry.py`、`ui/settings/model_management_page.py`、`ui/settings/workspace_ai_page.py`
- 统一模型存储根目录：`config/default_config.json`、`config/app_config.py`、`core/models/manager.py`、`core/models/downloader.py`
- 设置页提供商选择骨架：`ui/settings/components/provider_selector.py`、`ui/settings/components/section_card.py`、`ui/settings/transcription_page.py`、`ui/settings/translation_page.py`、`ui/settings/workspace_ai_page.py`
- 设置页导航与模型管理页签：`ui/settings/widget.py`、`ui/settings/model_management_page.py`、`resources/themes/theme_outline.json`、`resources/themes/light.qss`、`resources/themes/dark.qss`
- 录音设备刷新：`ui/settings/realtime_page.py`、`engines/audio/capture.py`、`core/realtime/recorder.py`
- 壳层录音底座与浮动窗布局：`ui/common/realtime_recording_dock.py`、`ui/workspace/recording_session_panel.py`、`ui/realtime_record/floating_overlay.py`、`ui/constants.py`、`resources/themes/light.qss`、`resources/themes/dark.qss`；dock 只负责 transport/status 与少量图标动作，实时结果走悬浮窗，播放跟随文本依赖 `core/realtime/archiver.py` 写出的同名 `.txt + .json` 资产对
- 主题契约与角色覆盖：`resources/themes/theme_outline.json`、`tests/unit/test_theme_outline_contract.py`、`ui/constants.py`
- 实时录音偏好设置：`core/settings/manager.py`、`ui/settings/realtime_page.py`、`config/default_config.json`
- 翻译默认设置：`ui/settings/translation_page.py`、`core/settings/manager.py`、`config/default_config.json`
- Workspace Vault 默认设置：`ui/settings/workspace_page.py`、`core/settings/manager.py`、`config/default_config.json`
- Workspace AI 默认设置：`ui/settings/workspace_ai_page.py`、`core/settings/manager.py`、`config/default_config.json`
- 时间线音频播放器：`ui/common/audio_player.py`、`ui/common/audio_player_launcher.py`、`ui/timeline/transcript_viewer.py`、`tests/ui/test_timeline_audio_player.py`
- 事件删除与 workspace 清理提示：`ui/calendar_event_actions.py`、`core/calendar/manager.py`、`core/workspace/manager.py`、`tests/ui/test_calendar_event_actions.py`
- 时间线/日历跳转工作台：`ui/timeline/widget.py`、`ui/calendar_hub/widget.py`、`ui/main_window.py`、`ui/workspace/widget.py`
- 翻译引擎接入：`utils/app_initializer.py`、`engines/translation/`、`core/realtime/recorder.py`
- Text AI 引擎接入：`utils/app_initializer.py`、`engines/text_ai/`、`core/workspace/summary_service.py`
- 版本号与发布：`config/__version__.py`、`CHANGELOG.md`、`scripts/build_config.py`、`pyproject.toml`
- 统一工作台规划：`docs/plans/archive/2026-03-15-workspace-redbox-closure-plan-superseded.md`、`docs/plans/archive/2026-03-15-workspace-polish-and-obsidian-alignment.md`、`docs/plans/archive/2026-03-15-workspace-experience-rearchitecture.md`、`docs/plans/archive/2026-03-15-unified-workspace-and-local-ai.md`、`ui/main_window.py`、`ui/navigation.py`、`core/transcription/manager.py`
- 工作台视觉精修计划：`docs/plans/archive/2026-03-15-workspace-redbox-closure-plan-superseded.md`、`ui/main_window.py`、`ui/common/realtime_recording_dock.py`、`ui/workspace/library_panel.py`、`ui/workspace/item_list.py`、`ui/workspace/inspector_panel.py`、`ui/workspace/recording_session_panel.py`、`resources/themes/theme_outline.json`、`resources/translations/i18n_outline.json`
  历史原始文件名 `docs/plans/2026-03-15-workspace-redbox-closure-plan.md` 已 superseded 到 archive 路径。

## 结构变更同步更新要求（强制）

当项目目录结构、模块职责、关键入口、或功能归属发生变化时，必须在同一变更中同步更新以下文件，禁止只改代码不改文档：

1. `AGENTS.md`：更新“项目代码结构速查”“功能关键词到文件路径”。
2. `skills/release-process/SKILL.md`：更新 `Quick Location Map` 与发布版本清单中的路径。
3. `docs/README.md`：若涉及对外可见模块/文档导航变化，更新对应入口说明。
4. `CHANGELOG.md`：记录结构调整带来的维护性或流程变化（如适用）。

同时要求：
- 若新增/删除主题 role 或选择器族，必须同步更新 `resources/themes/theme_outline.json` 并通过契约测试。
- 若新增/删除关键测试路径，必须同步更新对应测试索引与回归命令说明。
- 工作台视觉精修相关回归命令必须拆成稳定批次，至少分别运行：
  - `pytest tests/unit/test_main_window_shell.py -v`
  - `pytest tests/ui/test_workspace_widget.py -v`
  - `pytest tests/unit/test_i18n_outline_contract.py -v`
  - `pytest tests/unit/test_theme_outline_contract.py -v`

- 若新增/删除/重命名 i18n key，必须先更新 `resources/translations/i18n_outline.json`，并保证 `zh_CN/en_US/fr_FR` 结构一致。
- 多语言更新必须遵循“大纲驱动”流程：先定 section/key，再在所有 locale 同步补齐，再执行 i18n 契约测试。
- 工作台视觉精修完成时，必须明确确认 theme/i18n/tests/docs 已同变更收口，禁止只改 QSS 或只改单一测试。

## Release Workflow (Required)

When performing a release, follow this exact sequence and do not skip version sync points.

1. Determine target version (semantic versioning) and release date.
2. Update canonical version source first:
- `config/__version__.py`
3. Synchronize all project-facing version references:
- `pyproject.toml`
- `config/default_config.json`
- `scripts/build_config.py`
- `README.md`
- `docs/README.md`
- `echonote-landing/src/config/project.ts`
- `echonote-landing/package.json`
- `echonote-landing/package-lock.json` (root project version fields)
4. Update `CHANGELOG.md` with a new version section at the top, including:
- version number
- absolute date
- concise change summary
5. Validate:
- ensure no missed version by searching old version string globally
- run focused tests for touched modules
- run theme contract test if UI/theme selectors changed
6. Commit:
- commit message format: `release: vX.Y.Z`
7. Tag:
- annotated tag required: `vX.Y.Z`
8. Push:
- push branch
- push tag
9. Final verification:
- `git show --no-patch --decorate <commit>` includes `tag: vX.Y.Z`
- working tree is clean (or only intentionally retained files)

## Hard Rules

- Never release with partially updated version references.
- Never create lightweight tags for official releases.
- Never skip changelog updates.
- Never push tags before commit is on remote branch.

## Optional Automation

Use `skills/release-process/SKILL.md` for an executable checklist version of this process.
