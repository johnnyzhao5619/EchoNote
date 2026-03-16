# Workspace Visual Density And Layout Polish Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 收口当前工作台与壳层录音区域的视觉密度、布局层级和交互语义，使红框标注区域从“结构已存在但表现松散”提升到可发布的稳定产品状态。

**Architecture:** 保持现有单一工作台结构不变，不再新增第二套导航、录音或检查器路径。本轮只做硬切换精修：复用现有 `WorkspaceWidget`、`WorkspaceToolRail`、`WorkspaceItemList`、`WorkspaceInspectorPanel`、`RealtimeRecordingDock` 与 `WorkspaceRecordingSessionPanel`，通过调整布局、角色语义、主题契约和文案结构消除空白、重复与视觉失衡。所有优化以现有数据流和 manager API 为唯一事实源，不引入 mock 适配层，不做迁移设计。

**Tech Stack:** Python 3.12, PySide6, QSS, i18n JSON contracts, `ui/main_window.py`, `ui/common/realtime_recording_dock.py`, `ui/workspace/*`, `resources/themes/*`, `resources/translations/*`, `tests/ui/*`, `tests/unit/*`.

---

**Assumption:** 假定后续执行发生在当前仓库的独立工作分支或安全上下文中；当前计划只基于 2026-03-15 已审查代码与用户提供截图制定，不直接实施代码修改。

## 审查结论摘要

已审查并确认与红框区域直接相关的当前实现：

- `/Users/weijiazhao/Dev/EchoNote/ui/main_window.py`
- `/Users/weijiazhao/Dev/EchoNote/ui/workspace/widget.py`
- `/Users/weijiazhao/Dev/EchoNote/ui/workspace/toolbar.py`
- `/Users/weijiazhao/Dev/EchoNote/ui/workspace/tool_rail.py`
- `/Users/weijiazhao/Dev/EchoNote/ui/workspace/library_panel.py`
- `/Users/weijiazhao/Dev/EchoNote/ui/workspace/item_list.py`
- `/Users/weijiazhao/Dev/EchoNote/ui/workspace/inspector_panel.py`
- `/Users/weijiazhao/Dev/EchoNote/ui/common/realtime_recording_dock.py`
- `/Users/weijiazhao/Dev/EchoNote/ui/workspace/recording_session_panel.py`
- `/Users/weijiazhao/Dev/EchoNote/ui/constants.py`
- `/Users/weijiazhao/Dev/EchoNote/resources/themes/light.qss`
- `/Users/weijiazhao/Dev/EchoNote/resources/themes/dark.qss`
- `/Users/weijiazhao/Dev/EchoNote/resources/themes/theme_outline.json`
- `/Users/weijiazhao/Dev/EchoNote/resources/translations/i18n_outline.json`
- `/Users/weijiazhao/Dev/EchoNote/resources/translations/zh_CN.json`
- `/Users/weijiazhao/Dev/EchoNote/resources/translations/en_US.json`
- `/Users/weijiazhao/Dev/EchoNote/resources/translations/fr_FR.json`
- `/Users/weijiazhao/Dev/EchoNote/tests/ui/test_workspace_widget.py`
- `/Users/weijiazhao/Dev/EchoNote/tests/unit/test_main_window_shell.py`
- `/Users/weijiazhao/Dev/EchoNote/tests/unit/test_theme_outline_contract.py`
- `/Users/weijiazhao/Dev/EchoNote/tests/unit/test_i18n_outline_contract.py`
- `/Users/weijiazhao/Dev/EchoNote/AGENTS.md`

## 当前差距与优化目标

### 1. 顶部任务入口与搜索区

**当前状态**
- 顶部搜索框、快捷键提示、任务入口按钮三者只是水平并排，缺少统一容器和视觉对齐。
- `task_window_button` 仍像普通按钮，和“全局工具入口”语义不匹配。
- 顶部区域没有把 backlog badge、按钮状态和整体宽度约束收成一个可复用组。

**预期状态**
- 搜索输入、快捷键 hint、任务入口应成为一个右对齐的紧凑工具组。
- 任务入口按钮与 badge 形成稳定密度，不因文本变化破坏顶栏节奏。
- 顶栏控件高度、内边距、最小宽度都由常量统一管理。

### 2. 左侧工具轨与工作台 explorer

**当前状态**
- `WorkspaceToolRail` 仍是垂直堆叠按钮，信息密度低，占宽不小。
- `WorkspaceLibraryPanel` 的 folder action 与 explorer header 还是“普通按钮排布”，层级弱。
- explorer 列表项结构存在，但行高、标题/元信息/标签间距和选中态仍偏粗糙，导致大面积空白与内容发散。

**预期状态**
- 工具轨应更像“模式切换 rail”，而不是窄版按钮列表。
- explorer 顶部要区分“当前模式/集合上下文”和“结构操作”。
- item row 应在固定密度下呈现标题、来源、时间、状态标签，默认一屏容纳更多条目。

### 3. 右侧检查器

**当前状态**
- `WorkspaceInspectorPanel` 已分区，但 AI 按钮区、播放区和元数据区仍是最小堆叠，空白明显。
- metadata 仍直接显示原始 ISO 时间串与源字符串，缺少用户态格式。
- inspector 没有 section title、副文案和更明确的内容边界。

**预期状态**
- inspector 应是清晰的三段卡片：AI 操作、录音预览、属性信息。
- 元数据应转成用户可读格式，避免裸技术值。
- 当没有音频或没有可操作内容时，要有稳定空态，而不是大片空容器。

### 4. 底部录音底座与完整控制台

**当前状态**
- compact dock 和 full panel 都有开始/停止按钮，形成视觉重复。
- compact 区显示 `default`、缺少统一会话摘要语义；full panel 五个 section 仍是简单纵向表单堆叠。
- expanded 状态缺少“概览优先、设置次级”的布局节奏，导致红框内内容拥挤但信息不聚焦。

**预期状态**
- compact dock 负责全局 transport 和会话摘要；full panel 负责详细设置和实时结果，不重复承担同一主入口语义。
- 会话摘要应先展示状态、时长、输入源、目标语言，再决定是否进入详细设置。
- full panel 要压缩表单高度，利用双列或 summary strip 减少纵向膨胀。

### 5. 契约与回归

**当前状态**
- 当前主题有基础 role，但没有覆盖本轮要新增的工具组、inspector section title、explorer row badge 等细粒度语义。
- i18n 大纲还没有针对“检查器 section title / 录音摘要标签 / explorer 元信息格式”收口。
- 组合式 Qt 回归存在结束阶段挂起迹象，执行计划需要避免把大批量 UI 用例绑成单条命令。

**预期状态**
- 所有新增 role 和 key 都先入 outline，再补主题和 locale。
- 测试应拆成稳定的 focused 批次，避免回归命令本身变成不稳定因素。

## 实施顺序

1. 先收口顶栏和工具轨密度，解决最显眼的“入口像半成品”的问题。
2. 再做 explorer 与 inspector 的结构精修，收掉左中右三栏的视觉失衡。
3. 最后处理录音底座的重复语义与 full panel 布局，完成底部区域精修。
4. 每一轮都同步主题、i18n、测试和文档，不把契约债留到最后。

### Task 1: 顶栏全局工具组收口

**Files:**
- Modify: `/Users/weijiazhao/Dev/EchoNote/ui/main_window.py`
- Modify: `/Users/weijiazhao/Dev/EchoNote/ui/constants.py`
- Modify: `/Users/weijiazhao/Dev/EchoNote/resources/themes/light.qss`
- Modify: `/Users/weijiazhao/Dev/EchoNote/resources/themes/dark.qss`
- Modify: `/Users/weijiazhao/Dev/EchoNote/resources/themes/theme_outline.json`
- Test: `/Users/weijiazhao/Dev/EchoNote/tests/unit/test_main_window_shell.py`
- Test: `/Users/weijiazhao/Dev/EchoNote/tests/unit/test_theme_outline_contract.py`

**Step 1: Write the failing test**

```python
def test_main_window_top_bar_groups_search_hint_and_task_entry(qtbot, tmp_path):
    window = build_main_window_with_workspace(tmp_path)[0]

    assert window.top_bar_right_tools is not None
    assert window.top_bar_right_tools.property("role") == "app-topbar-tools"
    assert window.task_window_button.minimumHeight() == APP_TOP_BAR_CONTROL_HEIGHT
    assert window.task_window_badge.parent() is window.task_window_button
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_main_window_shell.py::test_main_window_top_bar_groups_search_hint_and_task_entry -v`

Expected: FAIL，因为当前没有 `top_bar_right_tools` 语义容器，也没有把任务入口做成统一工具组。

**Step 3: Write minimal implementation**

```python
self.top_bar_right_tools = QWidget(top_bar)
self.top_bar_right_tools.setProperty("role", ROLE_APP_TOPBAR_TOOLS)
```

实现要求：
- 给右上角搜索区 + hint + task entry 建立唯一容器。
- 不新增第二套任务入口。
- 顶栏相关最小宽度和间距全部进入 `ui/constants.py`。

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_main_window_shell.py::test_main_window_top_bar_groups_search_hint_and_task_entry tests/unit/test_theme_outline_contract.py -k "topbar_tools or task_entry_badge" -v`

Expected: PASS

**Step 5: Commit**

```bash
git add ui/main_window.py ui/constants.py resources/themes/light.qss resources/themes/dark.qss resources/themes/theme_outline.json tests/unit/test_main_window_shell.py tests/unit/test_theme_outline_contract.py
git commit -m "feat: tighten top bar utility group"
```

### Task 2: 工具轨与 explorer header 的信息层级重构

**Files:**
- Modify: `/Users/weijiazhao/Dev/EchoNote/ui/workspace/tool_rail.py`
- Modify: `/Users/weijiazhao/Dev/EchoNote/ui/workspace/library_panel.py`
- Modify: `/Users/weijiazhao/Dev/EchoNote/ui/workspace/widget.py`
- Modify: `/Users/weijiazhao/Dev/EchoNote/ui/constants.py`
- Modify: `/Users/weijiazhao/Dev/EchoNote/resources/themes/light.qss`
- Modify: `/Users/weijiazhao/Dev/EchoNote/resources/themes/dark.qss`
- Modify: `/Users/weijiazhao/Dev/EchoNote/resources/themes/theme_outline.json`
- Test: `/Users/weijiazhao/Dev/EchoNote/tests/ui/test_workspace_widget.py`
- Test: `/Users/weijiazhao/Dev/EchoNote/tests/unit/test_theme_outline_contract.py`

**Step 1: Write the failing test**

```python
def test_workspace_tool_rail_and_explorer_header_expose_compact_mode_shell(qapp, mock_i18n, workspace_manager):
    widget = WorkspaceWidget(workspace_manager, mock_i18n)

    assert widget.tool_rail.mode_button_group is not None
    assert widget.library_panel.context_label is not None
    assert widget.content_splitter.sizes()[1] > widget.content_splitter.sizes()[2]
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/ui/test_workspace_widget.py::test_workspace_tool_rail_and_explorer_header_expose_compact_mode_shell -v`

Expected: FAIL，因为当前工具轨仍是简单按钮堆叠，explorer header 只有标题，没有上下文 label。

**Step 3: Write minimal implementation**

```python
self.context_label = QLabel(self.explorer_header)
self.context_label.setProperty("role", ROLE_WORKSPACE_CONTEXT_LABEL)
```

实现要求：
- 工具轨保留唯一视图切换职责，但收成更紧凑的模式按钮组。
- explorer header 增加当前视图/当前文件夹上下文，不新增新的过滤状态源。
- `content_splitter` 默认尺寸继续保持文档优先。

**Step 4: Run test to verify it passes**

Run: `pytest tests/ui/test_workspace_widget.py -k "tool_rail_and_explorer_header_expose_compact_mode_shell or document_first_splitter" -v`

Expected: PASS

**Step 5: Commit**

```bash
git add ui/workspace/tool_rail.py ui/workspace/library_panel.py ui/workspace/widget.py ui/constants.py resources/themes/light.qss resources/themes/dark.qss resources/themes/theme_outline.json tests/ui/test_workspace_widget.py tests/unit/test_theme_outline_contract.py
git commit -m "feat: refine workspace rail and explorer header"
```

### Task 3: Explorer 列表行密度与状态标签精修

**Files:**
- Modify: `/Users/weijiazhao/Dev/EchoNote/ui/workspace/item_list.py`
- Modify: `/Users/weijiazhao/Dev/EchoNote/ui/constants.py`
- Modify: `/Users/weijiazhao/Dev/EchoNote/resources/themes/light.qss`
- Modify: `/Users/weijiazhao/Dev/EchoNote/resources/themes/dark.qss`
- Modify: `/Users/weijiazhao/Dev/EchoNote/resources/themes/theme_outline.json`
- Modify: `/Users/weijiazhao/Dev/EchoNote/resources/translations/i18n_outline.json`
- Modify: `/Users/weijiazhao/Dev/EchoNote/resources/translations/zh_CN.json`
- Modify: `/Users/weijiazhao/Dev/EchoNote/resources/translations/en_US.json`
- Modify: `/Users/weijiazhao/Dev/EchoNote/resources/translations/fr_FR.json`
- Test: `/Users/weijiazhao/Dev/EchoNote/tests/ui/test_workspace_widget.py`
- Test: `/Users/weijiazhao/Dev/EchoNote/tests/unit/test_i18n_outline_contract.py`
- Test: `/Users/weijiazhao/Dev/EchoNote/tests/unit/test_theme_outline_contract.py`

**Step 1: Write the failing test**

```python
def test_workspace_item_row_uses_dense_title_meta_and_badge_roles(qapp, mock_i18n, workspace_manager):
    widget = WorkspaceWidget(workspace_manager, mock_i18n)
    row = widget.item_list.list_widget.itemWidget(widget.item_list.list_widget.item(0))

    assert row.title_label.property("role") == "workspace-item-title"
    assert row.meta_label.property("role") == "workspace-item-meta"
    assert row.badges_widget.property("role") == "workspace-item-badges"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/ui/test_workspace_widget.py::test_workspace_item_row_uses_dense_title_meta_and_badge_roles -v`

Expected: FAIL，因为当前列表行还没有细粒度 role，也没有 badge 容器暴露。

**Step 3: Write minimal implementation**

```python
self.title_label.setProperty("role", ROLE_WORKSPACE_ITEM_TITLE)
self.meta_label.setProperty("role", ROLE_WORKSPACE_ITEM_META)
self.badges_widget.setProperty("role", ROLE_WORKSPACE_ITEM_BADGES)
```

实现要求：
- 保持 `WorkspaceManager.get_item_list_metadata()` 作为唯一元数据来源。
- 不再拼接过长原始字符串；元信息格式统一由一个 helper 负责。
- badge 风格统一，不在多个地方各自创建不同标签样式。

**Step 4: Run test to verify it passes**

Run: `pytest tests/ui/test_workspace_widget.py -k "item_row_uses_dense_title_meta_and_badge_roles or renders_structured_row_widgets" -v`

Expected: PASS

**Step 5: Commit**

```bash
git add ui/workspace/item_list.py ui/constants.py resources/themes/light.qss resources/themes/dark.qss resources/themes/theme_outline.json resources/translations/i18n_outline.json resources/translations/zh_CN.json resources/translations/en_US.json resources/translations/fr_FR.json tests/ui/test_workspace_widget.py tests/unit/test_i18n_outline_contract.py tests/unit/test_theme_outline_contract.py
git commit -m "feat: polish workspace explorer rows"
```

### Task 4: 检查器卡片化与元数据用户态格式化

**Files:**
- Modify: `/Users/weijiazhao/Dev/EchoNote/ui/workspace/inspector_panel.py`
- Modify: `/Users/weijiazhao/Dev/EchoNote/ui/workspace/recording_panel.py`
- Modify: `/Users/weijiazhao/Dev/EchoNote/ui/workspace/detached_document_window.py`
- Modify: `/Users/weijiazhao/Dev/EchoNote/ui/constants.py`
- Modify: `/Users/weijiazhao/Dev/EchoNote/resources/themes/light.qss`
- Modify: `/Users/weijiazhao/Dev/EchoNote/resources/themes/dark.qss`
- Modify: `/Users/weijiazhao/Dev/EchoNote/resources/themes/theme_outline.json`
- Modify: `/Users/weijiazhao/Dev/EchoNote/resources/translations/i18n_outline.json`
- Modify: `/Users/weijiazhao/Dev/EchoNote/resources/translations/zh_CN.json`
- Modify: `/Users/weijiazhao/Dev/EchoNote/resources/translations/en_US.json`
- Modify: `/Users/weijiazhao/Dev/EchoNote/resources/translations/fr_FR.json`
- Test: `/Users/weijiazhao/Dev/EchoNote/tests/ui/test_workspace_widget.py`
- Test: `/Users/weijiazhao/Dev/EchoNote/tests/unit/test_i18n_outline_contract.py`
- Test: `/Users/weijiazhao/Dev/EchoNote/tests/unit/test_theme_outline_contract.py`

**Step 1: Write the failing test**

```python
def test_workspace_inspector_exposes_section_titles_and_user_facing_metadata(qapp, mock_i18n, workspace_manager):
    widget = WorkspaceWidget(workspace_manager, mock_i18n)
    item = workspace_manager.list_items()[0]
    widget.open_item(item.id)

    assert widget.inspector_panel.ai_section_title.text()
    assert widget.inspector_panel.media_section_title.text()
    assert widget.inspector_panel.metadata_section_title.text()
    assert "T" not in widget.inspector_panel.updated_value_label.text()
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/ui/test_workspace_widget.py::test_workspace_inspector_exposes_section_titles_and_user_facing_metadata -v`

Expected: FAIL，因为当前没有 section title，更新时间仍可能直接显示 ISO 原串。

**Step 3: Write minimal implementation**

```python
def _format_updated_at(self, value: str) -> str:
    return value.replace("T", " ")[:16] if value else "-"
```

实现要求：
- 保持 inspector 仍通过 editor 公共 API 调用 AI 动作，不回退到私有方法。
- detached window 同步复用同一套 inspector 结构，不允许主/独立窗口出现两套属性卡片实现。
- 如果当前条目没有音频，媒体区必须显示稳定空态文案。

**Step 4: Run test to verify it passes**

Run: `pytest tests/ui/test_workspace_widget.py -k "inspector_exposes_section_titles_and_user_facing_metadata or detached_document_window_matches_workspace_context_stack" -v`

Expected: PASS

**Step 5: Commit**

```bash
git add ui/workspace/inspector_panel.py ui/workspace/recording_panel.py ui/workspace/detached_document_window.py ui/constants.py resources/themes/light.qss resources/themes/dark.qss resources/themes/theme_outline.json resources/translations/i18n_outline.json resources/translations/zh_CN.json resources/translations/en_US.json resources/translations/fr_FR.json tests/ui/test_workspace_widget.py tests/unit/test_i18n_outline_contract.py tests/unit/test_theme_outline_contract.py
git commit -m "feat: refine workspace inspector cards"
```

### Task 5: 底部录音 dock 的 compact/full 语义去重

**Files:**
- Modify: `/Users/weijiazhao/Dev/EchoNote/ui/common/realtime_recording_dock.py`
- Modify: `/Users/weijiazhao/Dev/EchoNote/ui/workspace/recording_session_panel.py`
- Modify: `/Users/weijiazhao/Dev/EchoNote/ui/constants.py`
- Modify: `/Users/weijiazhao/Dev/EchoNote/resources/themes/light.qss`
- Modify: `/Users/weijiazhao/Dev/EchoNote/resources/themes/dark.qss`
- Modify: `/Users/weijiazhao/Dev/EchoNote/resources/themes/theme_outline.json`
- Modify: `/Users/weijiazhao/Dev/EchoNote/resources/translations/i18n_outline.json`
- Modify: `/Users/weijiazhao/Dev/EchoNote/resources/translations/zh_CN.json`
- Modify: `/Users/weijiazhao/Dev/EchoNote/resources/translations/en_US.json`
- Modify: `/Users/weijiazhao/Dev/EchoNote/resources/translations/fr_FR.json`
- Test: `/Users/weijiazhao/Dev/EchoNote/tests/unit/test_main_window_shell.py`
- Test: `/Users/weijiazhao/Dev/EchoNote/tests/unit/test_i18n_outline_contract.py`
- Test: `/Users/weijiazhao/Dev/EchoNote/tests/unit/test_theme_outline_contract.py`

**Step 1: Write the failing test**

```python
def test_recording_dock_uses_single_transport_summary_and_dense_full_panel():
    dock = RealtimeRecordingDock(realtime_recorder, _build_i18n())

    assert dock.compact_panel.summary_group is not None
    assert dock.full_panel.session_summary_section is not None
    assert dock.full_panel.capture_form_layout.columnCount() == 2
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_main_window_shell.py::test_recording_dock_uses_single_transport_summary_and_dense_full_panel -v`

Expected: FAIL，因为当前 compact/full 两侧都直接暴露开始/停止，full panel 也还是单列堆叠。

**Step 3: Write minimal implementation**

```python
self.compact_panel.summary_group = QWidget(self.compact_panel)
self.capture_form_layout = QGridLayout()
```

实现要求：
- compact dock 保留唯一主 transport。
- full panel 中的开始/停止只保留一种明确语义；若保留按钮，必须解释为“应用当前设置并开始”，不能和 compact 完全重复。
- capture / processing / output 区优先使用密集表单布局，不新增重复控件。
- 默认输入源、目标语言、会话状态全部走 i18n 文案 helper。

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_main_window_shell.py -k "recording_dock_uses_single_transport_summary_and_dense_full_panel or localized_summary_labels" -v`

Expected: PASS

**Step 5: Commit**

```bash
git add ui/common/realtime_recording_dock.py ui/workspace/recording_session_panel.py ui/constants.py resources/themes/light.qss resources/themes/dark.qss resources/themes/theme_outline.json resources/translations/i18n_outline.json resources/translations/zh_CN.json resources/translations/en_US.json resources/translations/fr_FR.json tests/unit/test_main_window_shell.py tests/unit/test_i18n_outline_contract.py tests/unit/test_theme_outline_contract.py
git commit -m "feat: streamline recording dock density"
```

### Task 6: 文档、契约和稳定回归收口

**Files:**
- Modify: `/Users/weijiazhao/Dev/EchoNote/AGENTS.md`
- Modify: `/Users/weijiazhao/Dev/EchoNote/docs/README.md`
- Modify: `/Users/weijiazhao/Dev/EchoNote/skills/release-process/SKILL.md`
- Modify: `/Users/weijiazhao/Dev/EchoNote/CHANGELOG.md`
- Test: `/Users/weijiazhao/Dev/EchoNote/tests/unit/test_main_window_shell.py`
- Test: `/Users/weijiazhao/Dev/EchoNote/tests/ui/test_workspace_widget.py`
- Test: `/Users/weijiazhao/Dev/EchoNote/tests/unit/test_i18n_outline_contract.py`
- Test: `/Users/weijiazhao/Dev/EchoNote/tests/unit/test_theme_outline_contract.py`

**Step 1: Write the failing test**

```python
def test_theme_outline_and_i18n_outline_cover_workspace_visual_polish_contracts():
    assert "workspace-item-title" in _load_outline_roles()
    assert "workspace.inspector_ai_section" in workspace_keys
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_theme_outline_contract.py tests/unit/test_i18n_outline_contract.py -k "visual_polish_contracts" -v`

Expected: FAIL，直到所有新增 role / i18n key 都同步进入 outline。

**Step 3: Write minimal implementation**

```python
# 只补齐真实新增的 role、key、索引和回归命令，不新增说明性废话。
```

实现要求：
- `AGENTS.md`、`docs/README.md`、`skills/release-process/SKILL.md`、`CHANGELOG.md` 同步更新。
- 回归命令拆成稳定批次，不把所有 Qt UI 用例绑成一个可能挂起的单进程命令。
- 明确记录“主题/文案/测试/文档必须同变更收口”的执行结果。

**Step 4: Run test to verify it passes**

Run:
- `pytest tests/unit/test_main_window_shell.py -v`
- `pytest tests/ui/test_workspace_widget.py -v`
- `pytest tests/unit/test_i18n_outline_contract.py -v`
- `pytest tests/unit/test_theme_outline_contract.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add AGENTS.md docs/README.md skills/release-process/SKILL.md CHANGELOG.md tests/unit/test_main_window_shell.py tests/ui/test_workspace_widget.py tests/unit/test_i18n_outline_contract.py tests/unit/test_theme_outline_contract.py
git commit -m "docs: sync workspace visual polish contracts"
```

## 执行注意事项

- 不要在 `ui/main_window.py`、`ui/workspace/widget.py`、`ui/common/realtime_recording_dock.py` 中重复创建第二套状态源；一切状态继续来自现有 manager / recorder / workspace item。
- 不要为了视觉精修引入新的 mock 数据、演示文案或脱离业务的占位逻辑。
- 不要在 explorer、inspector、recording panel 各自实现不同的时间/来源格式化逻辑；共性格式必须收为单 helper。
- 不要把本轮视觉精修做成“仅改 QSS”；凡是影响语义层级、标题、空态、字段 copy，都必须同步更新 i18n 和测试。
- 如果执行时发现某个红框区域的真实代码与本计划不符，只允许做最小必要校正，不得扩展成新的重构议题。

## 建议回归顺序

1. `pytest tests/unit/test_main_window_shell.py -v`
2. `pytest tests/ui/test_workspace_widget.py -v`
3. `pytest tests/unit/test_i18n_outline_contract.py -v`
4. `pytest tests/unit/test_theme_outline_contract.py -v`

避免使用单条超大组合命令作为唯一回归依据；Qt UI 用例如需组合运行，先分批确认通过，再做补充组合验证。

Plan complete and saved to docs/plans/2026-03-15-workspace-visual-density-and-layout-polish-plan.md. Two execution options:

1. Subagent-Driven (this session) - I dispatch a fresh subagent per task, review between tasks, fast iteration

2. Parallel Session (separate) - Open a new session with executing-plans, batch execution with checkpoints

Which approach?
