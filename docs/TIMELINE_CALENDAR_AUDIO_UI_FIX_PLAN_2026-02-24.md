# 时间线/查看器/音频播放器/日历中心优化实施计划（2026-02-24）

## 目标与边界
- 目标：修复并优化以下 4 类问题：时间线事件卡片布局、查看模式交互、音频播放时转写/翻译联动与滚动、日历中心查看窗口层级与界面可用性。
- 边界：仅做当前版本前端与交互改进，不做向后兼容迁移；避免 mock、避免硬编码、避免重复实现；优先复用已有 `ui.common.transcript_translation_viewer`。

## 已完成审查范围（改前全量阅读）
- 时间线：`ui/timeline/event_card.py`、`ui/timeline/widget.py`、`ui/base_widgets.py`
- 查看器：`ui/common/transcript_translation_viewer.py`、`ui/timeline/transcript_viewer.py`
- 音频播放：`ui/common/audio_player.py`
- 日历中心：`ui/calendar_hub/widget.py`、`ui/calendar_hub/event_dialog.py`、`ui/calendar_hub/calendar_view.py`
- 主题契约：`resources/themes/theme_outline.json`、`tests/unit/test_theme_outline_contract.py`、`ui/common/theme.py`、`docs/THEME_OUTLINE_GUIDE.md`
- 文案：`resources/translations/zh_CN.json`、`resources/translations/en_US.json`
- 现有测试：`tests/ui/test_timeline_event_card.py`、`tests/ui/test_timeline_widget_filters.py`、`tests/ui/test_calendar_hub_widget.py`、`tests/ui/test_calendar_dialog_layout.py`

## 根因分析（对应问题）
1. 时间线卡片“堆叠感强/样式不统一”
- 过去事件操作区是单排平铺，动作过多时语义分组不清；“查看转写/查看翻译”分散导致操作路径冗长。
- 元信息行（时间/类型/来源）缺少更清晰的分层与稳定对齐结构。

2. 查看模式交互复杂
- 查看器使用“标签 + 下拉框”切换模式，模式切换需要额外认知和点击，不符合高频“快速切换转写/转译/对照”场景。

3. 音频播放页无法展示翻译/对照，且无法随播放滚动；存在播放界面错位/穿插风险
- 播放器仅接收 `transcript_path`，未接入 `translation_path`。
- 播放器未建立“时间轴 -> 文本段落”的高亮/自动滚动链路。
- 转写展开/收起通过手动增减窗口高度，易产生布局重叠和错位。

4. 日历中心中“查看转写/转译”窗口在后方且不可置前
- 事件编辑框使用 `exec()` 模态循环，查看器由 `CalendarHubWidget` 作为父窗口弹出，导致层级落在当前模态对话框之后。
- 日历中心未复用时间线的查看器缓存与激活逻辑，重复打开时也缺少统一前置策略。

## 改进方案（实施顺序）
1. 抽象并统一“文本查看入口”行为
- 在日历中心引入与时间线一致的查看器缓存/激活策略（避免重复弹窗与层级混乱）。
- 为事件编辑对话框触发的查看动作传递 `parent_hint`（当前对话框），保证窗口层级正确。

2. 优化查看器交互为“显式模式切换”
- 将查看模式从下拉切换为三态切换按钮（转写/转译/对照），隐藏不可用模式。
- 保持搜索、复制、导出逻辑不变，减少学习成本并提升切换效率。

3. 重构时间线事件卡片动作区（不改业务能力）
- 过去事件动作统一为“播放/二次转写/查看转写或转译（单入口）/翻译转写/删除”。
- 同时存在转写和翻译时，查看入口默认进入对照模式；仅存在其一时进入对应单模式。
- 保持现有信号链路，不新增重复业务分支。

4. 增强音频播放器文本联动能力
- 接入 `translation_path`，提供转写/转译/对照三种显示模式（按可用性自动启用）。
- 基于时间戳段落（segments）实现当前播放段高亮与自动滚动（歌词式）。
- 去除手工 `resize(+/-固定高度)`，改为布局驱动的稳定展开/收起，消除控件重叠。
- 增加“同一时刻仅一个播放器发声”保护，避免并行播放造成“穿插”体验。

5. 主题与密度收敛（light/dark 对称）
- 仅在语义角色层补齐必要样式，保持 light/dark 结构一致。
- 不引入页面硬编码色值；不增加重复全局选择器。

## DRY 与技术债处理
- 消除“时间线/日历中心”两处查看器前置逻辑分叉，统一为同一套缓存+激活行为。
- 减少“查看转写/查看翻译”双入口重复操作，统一为单入口 + 模式切换。
- 去除音频播放器中手工窗口高度调节这类脆弱逻辑，降低后续维护成本。

## 风险与假设
- 假设 A：转写关联文件可能同时存在 `.txt` 与 `.json`，且 `.json` 包含 `segments`。  
  处理：优先读取可用段落时间轴；缺失时降级为纯文本显示，不阻断播放。
- 假设 B：翻译文件多数为纯文本，可能缺少时间戳。  
  处理：转译/对照模式支持展示；若无时间轴，则仅使用可用时间轴进行滚动高亮降级。

## 验证计划
- 单测：补充/更新时间线卡片、查看器模式切换、日历中心查看窗口层级、播放器文本模式可用性与联动行为。
- 契约：`pytest tests/unit/test_theme_outline_contract.py -q`
- UI：运行受影响 UI 测试集（timeline/calendar/viewer 相关）。

## 交付完成判定
- 4 类问题均可复现验证通过：布局、交互、播放联动、窗口层级。
- 无 mock 数据、无新增冗余分支、无重复实现同类逻辑。
- 主题契约测试通过，light/dark 样式同步。
