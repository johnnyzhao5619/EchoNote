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
  - `config/default_config.json`：默认配置。
- `core/`：核心业务编排与管理器。
  - `core/realtime/`：实时录音/转写集成（录音器、路由、归档等）。
  - `core/settings/`：设置读写与偏好聚合。
  - `core/timeline/`：时间线事件与任务调度。
  - `core/calendar/`：日历同步与任务逻辑。
- `engines/`：引擎层实现。
  - `engines/audio/`：音频采集与VAD。
  - `engines/speech/`：语音识别引擎。
  - `engines/translation/`：翻译引擎。
- `ui/`：桌面端界面层（PySide6）。
  - `ui/realtime_record/`：实时录音页面与浮动窗。
  - `ui/timeline/`：时间线与音频播放器（`audio_player.py`）。
  - `ui/settings/`：设置页面（含 `translation_page.py` 独立翻译默认设置页）。
  - `ui/common/`：通用组件。
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
- `echonote-landing/`：官网/落地页前端（独立包版本）。

## 常用定位建议

- 查“实时录音/浮动窗”：优先看 `ui/realtime_record/` + `core/realtime/` + `resources/themes/*qss`。
- 查“时间线音频播放”：优先看 `ui/timeline/audio_player.py` + 相关 `ui/common/` 组件。
- 查“主题覆盖缺失”：先对照 `ui/constants.py` 的 role，再查双主题与 `theme_outline.json`。
- 查“版本发布遗漏”：先看 `config/__version__.py`，再按发布清单同步其他文件。

## 功能关键词到文件路径（快速索引）

- 录音设备刷新：`ui/realtime_record/widget.py`、`engines/audio/capture.py`、`tests/ui/test_realtime_record_widget.py`
- 浮动窗布局：`ui/realtime_record/floating_overlay.py`、`ui/constants.py`、`resources/themes/light.qss`、`resources/themes/dark.qss`
- 主题契约与角色覆盖：`resources/themes/theme_outline.json`、`tests/unit/test_theme_outline_contract.py`、`ui/constants.py`
- 实时录音偏好设置：`core/settings/manager.py`、`ui/settings/realtime_page.py`、`config/default_config.json`
- 翻译默认设置：`ui/settings/translation_page.py`、`core/settings/manager.py`、`config/default_config.json`
- 时间线音频播放器：`ui/timeline/audio_player.py`、`ui/timeline/transcript_viewer.py`、`tests/ui/test_timeline_audio_player.py`
- 翻译引擎接入：`utils/app_initializer.py`、`engines/translation/`、`core/realtime/recorder.py`
- 版本号与发布：`config/__version__.py`、`CHANGELOG.md`、`scripts/build_config.py`、`pyproject.toml`

## 结构变更同步更新要求（强制）

当项目目录结构、模块职责、关键入口、或功能归属发生变化时，必须在同一变更中同步更新以下文件，禁止只改代码不改文档：

1. `AGENTS.md`：更新“项目代码结构速查”“功能关键词到文件路径”。
2. `skills/release-process/SKILL.md`：更新 `Quick Location Map` 与发布版本清单中的路径。
3. `docs/README.md`：若涉及对外可见模块/文档导航变化，更新对应入口说明。
4. `CHANGELOG.md`：记录结构调整带来的维护性或流程变化（如适用）。

同时要求：
- 若新增/删除主题 role 或选择器族，必须同步更新 `resources/themes/theme_outline.json` 并通过契约测试。
- 若新增/删除关键测试路径，必须同步更新对应测试索引与回归命令说明。

- 若新增/删除/重命名 i18n key，必须先更新 `resources/translations/i18n_outline.json`，并保证 `zh_CN/en_US/fr_FR` 结构一致。
- 多语言更新必须遵循“大纲驱动”流程：先定 section/key，再在所有 locale 同步补齐，再执行 i18n 契约测试。

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
