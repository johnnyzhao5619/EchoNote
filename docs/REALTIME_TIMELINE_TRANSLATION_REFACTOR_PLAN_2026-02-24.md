# EchoNote 实施计划（时间线/实时转写/翻译一体化）

日期：2026-02-24

## 0. 实施状态快照（落盘基线）

### 0.1 已完成（已合入当前工作区）

1. 删除策略重构：事件删除支持“仅删事件/删事件+附件/导出后删除”。
2. 二次转写覆盖：录音结束后可触发二次转写并覆盖实时稿（`replace_realtime=True`）。
3. 重译覆盖：二次转写后若存在旧翻译，自动按新转写重译并覆盖。
4. 时间线“预约”语义修正：筛选逻辑已改为“尚未发生（start_time >= now）”。
5. 统一查看器初版：转写/转译/对比三模式组件已接入时间线与批量查看器。
6. 时间线翻译入口：事件卡支持“翻译转写”，并走统一 `TranscriptionManager.translate_transcript_file` 保存链路。

### 0.2 未完成（本轮必须补齐）

1. 浮窗模式（需求2）：
   - 实时页缺少浮窗开关配置项；
   - 运行态缺少浮窗组件与主窗隐藏/恢复协同；
   - 主题 role、outline、契约测试尚未补齐。
2. 全页面翻译入口（需求3）：
   - 日历中心编辑事件场景未提供“翻译转写”入口；
   - 部分页面仍存在翻译配置读取散点 fallback。
3. 翻译配置统一（需求4）：
   - `settings`、`realtime`、`timeline`、`batch` 尚未统一到单一读取接口。
4. i18n 文案完整性：
   - 统一查看器与新翻译流程相关 key 未完全补齐（中英双语）。

### 0.3 本轮执行顺序（锁定）

1. P0：配置与接口统一（先收敛默认值与读取入口）。
2. P1：浮窗模式端到端落地（UI + 配置 + 主题契约）。
3. P2：补齐 Calendar/Batch/Timeline 翻译入口一致性（统一保存链路）。
4. P3：补齐 i18n 与回归测试，清理重复逻辑。

### 0.4 本轮落地结果（已完成）

1. 浮窗模式已落地（设置项 + 运行态浮窗 + 主窗隐藏恢复 + 主题契约同步）。
2. Calendar Hub 已补齐“查看转写/转译 + 翻译转写”入口，并复用统一查看器与统一翻译保存链路。
3. 翻译偏好读取已统一到 `SettingsManager.get_realtime_translation_preferences()`，页面侧散点 fallback 已收敛。
4. 二次转写覆盖链路补强：无 `text` 字段结果也会从 `segments` 提取文本，保证覆盖与重译不丢失。
5. i18n 与主题契约已补齐，并通过回归测试。

## 1. 目标与范围

本计划覆盖以下 8 项需求，并要求一次性打通 UI、业务层、数据落盘与回归测试：

1. 时间线/日历中心删除逻辑重构：支持仅删除事件，不删除录音/文本。
2. 实时转写与实时翻译新增浮动窗模式：主窗可隐藏，浮窗显示运行状态。
3. 各页面提供翻译入口并打通统一保存逻辑。
4. 统一翻译配置逻辑：settings 页面与实时页一致，默认值来源唯一。
5. 合并“查看转写/查看转译”界面，支持转写/转译/对比三模式并可复用。
6. 智能时间线筛选“预约”语义修正为“尚未发生的事件/任务”。
7. 二次转写完成后，如原先已有翻译，自动基于新转写重译并覆盖旧译文。
8. 实时录音结束后提供“重转写并覆盖实时稿”选项，提升质量。

## 2. 当前阻断与先后顺序

### 2.1 P0 阻断（必须先修）

1. `RealtimeRecordWidget` 调用了不存在的 `settings_manager.update_setting`。
2. `TranscriptionManager` 中处理任务时提前移除了 `event_id`，导致翻译回存失败。
3. 翻译附件保存时传入 `EventAttachment` 不存在字段 `file_name`。
4. 翻译默认值来源不一致（`default_config`/`SettingsManager`/`AutoTaskScheduler` fallback 分裂）。

### 2.2 实施顺序

1. P0：先修阻断并统一配置源。
2. P1：删除策略 + 二次转写覆盖与重译 + 时间线预约筛选语义。
3. P2：统一查看器 + 全页面翻译入口 + 浮窗模式 + 主题样式补齐。
4. P3：清理重复代码、补齐回归测试、执行主题契约测试。

## 3. 设计原则（执行约束）

1. 系统性：UI 入口、业务编排、附件落盘必须同一套规则。
2. 第一性：以“数据正确写入并可追溯”为核心，不以现有界面形态为前提。
3. DRY：翻译执行与附件保存建立统一服务，避免 timeline/batch/calendar/realtime 多处复制。
4. 长期维护：减少散点 fallback、统一配置读取路径、减少跨页面耦合。

## 4. 关键改造方案

### 4.1 删除策略重构（需求 1）

- 改造 `ui/calendar_event_actions.py`：
  - 删除动作改为三选一：
    - 仅删除事件（保留附件文件与附件记录）
    - 删除事件及附件（删除附件记录，按选项删除物理文件）
    - 导出后删除事件及附件
  - 文案明确“事件记录”和“录音/转写/翻译附件”是不同层级。
- 改造 `core/calendar/manager.py`：
  - `delete_event(event_id, delete_artifacts=True, delete_artifact_files=True)`。
  - 仅删除事件时不触碰附件记录和文件。

### 4.2 翻译链路统一（需求 3/4/7）

- 在 `core/transcription` 引入统一翻译保存服务：
  - 统一翻译执行、文本落盘、`event_attachments` 关联、覆盖策略。
  - 对同一事件同类型附件（`translation`）执行 upsert 逻辑，避免重复垃圾数据。
- `TranscriptionManager`：
  - 保留 `event_id` 到翻译阶段。
  - 二次转写 `replace_realtime=True` 时覆盖实时稿文件。
  - 若事件已存在翻译附件或当前任务启用翻译，二次转写完成后基于新转写重译并覆盖。
- `main.py` 初始化时将 `translation_engine` 注入 `TranscriptionManager`，并与运行时重载保持一致。

### 4.3 实时录音“结束后重转写”交互（需求 8）

- `ui/realtime_record/widget.py`：
  - 去掉“录音前勾选二次转写”的默认流程。
  - 录音结束后弹出操作确认（重转写并覆盖 / 保持当前结果）。
  - 确认后下发 `replace_realtime=True` 的二次转写任务并保留 `event_id`。

### 4.4 时间线筛选语义（需求 6）

- `ui/timeline/widget.py`：
  - 筛选项文案由“预约”改为“待发生”语义。
  - 传递新的语义过滤标识，不再映射 `EventType.APPOINTMENT`。
- `core/timeline/manager.py`：
  - 新增语义过滤分支：`future_pending` => `event.start_time >= now`。
  - 保留 `event_type` 过滤兼容历史类型。

### 4.5 统一查看器（需求 5）

- 新增可复用组件（放 `ui/common`）：
  - 单界面支持三模式：转写 / 转译 / 对比。
  - 统一搜索、复制、导出交互。
- 替换入口：
  - `ui/timeline/widget.py`
  - `ui/batch_transcribe/widget.py`
  - 后续其他页面复用同组件。

### 4.6 全页面翻译入口（需求 3）

- 入口统一接入翻译服务，避免页面内直接写文件或直接写 `EventAttachment`。
- 接入页：
  - 时间线过去事件卡
  - 日历中心事件详情（可编辑场景）
  - 批量转写完成任务

### 4.7 浮动窗模式（需求 2）

- 新增 `ui/realtime_record/floating_overlay.py`：
  - 置顶、小窗、可拖拽、简要状态（录音状态/时长/最近转写片段）。
  - 提供“显示主窗口”动作。
- 实时页增加开关并保存到统一配置键：
  - `realtime.floating_window_enabled`
  - `realtime.hide_main_window_when_floating`
- 主题：
  - 使用语义 role 增加浮窗样式，light/dark 同步。
  - 同步 `theme_outline` 契约覆盖。

## 5. 文件级改造清单（首批）

1. `core/transcription/manager.py`
2. `core/calendar/manager.py`
3. `ui/calendar_event_actions.py`
4. `ui/realtime_record/widget.py`
5. `ui/timeline/widget.py`
6. `core/timeline/manager.py`
7. `ui/batch_transcribe/widget.py`
8. `ui/calendar_hub/widget.py`
9. `core/settings/manager.py`
10. `config/default_config.json`
11. `main.py`
12. `resources/translations/zh_CN.json`
13. `resources/translations/en_US.json`
14. `resources/themes/light.qss`
15. `resources/themes/dark.qss`
16. `resources/themes/theme_outline.json`

## 6. 验收标准

1. 删除事件时可明确选择是否保留录音/转写/翻译文件与关联。
2. 二次转写后实时稿被覆盖，且已有翻译会被基于新稿重译覆盖。
3. 各页面翻译入口均写入同一套保存逻辑，无重复实现。
4. 浮窗模式可独立展示运行状态，主窗可隐藏且可恢复。
5. 时间线“预约/待发生”筛选结果仅包含未发生事件/任务。
6. 转写/转译/对比在同一查看器中可切换。
7. 设置页与实时页翻译默认值一致，不存在分裂 fallback。

## 7. 回归测试清单

1. `tests/ui/test_calendar_event_actions.py`
2. `tests/unit/core/test_calendar_manager.py`
3. `tests/unit/core/test_transcription_manager.py`
4. `tests/ui/test_timeline_widget_filters.py`
5. `tests/unit/core/test_timeline_manager.py`
6. `tests/ui/test_realtime_record_widget.py`
7. `tests/ui/test_calendar_hub_widget.py`
8. `tests/ui/test_batch_transcribe_widget.py`
9. `tests/unit/test_theme_outline_contract.py`

## 7.1 本轮新增回归矩阵（避免遗漏）

1. 浮窗模式
   - 开关开启后可显示浮窗，状态/简要文本可更新。
   - 开启“浮窗时隐藏主窗口”后，主窗可隐藏并可从浮窗恢复。
   - 停止录音/关闭浮窗后，资源清理与窗口状态可恢复。
2. 翻译入口
   - 时间线、批量查看器、日历中心均可触发翻译并写入统一保存链路。
   - 同一事件重复翻译不产生脏附件（translation upsert）。
3. 配置一致性
   - `settings.realtime` 与运行时读取一致，默认值来源唯一。
   - `translation_source_lang/translation_target_lang` 在各页面表现一致。
4. 二次转写质量保障
   - 二次转写覆盖旧实时转写文本。
   - 若存在旧翻译，基于新转写再次翻译并覆盖。

## 8. 假设与处理

1. 假设：事件删除“仅删除事件”需要保留附件记录，避免失去后续追溯与二次处理能力。
  - 理由：用户明确要求“仅删除事件，不删除录音/文本”；从第一性看，音频与文本是独立资产。
2. 假设：实时浮窗首版优先文本与状态展示，不内置复杂编辑操作。
  - 理由：避免过度工程化，先完成“可隐藏主窗且可继续监控”的核心价值。
