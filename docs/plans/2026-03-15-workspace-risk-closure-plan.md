# Workspace Risk Closure And Polish Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在现有硬切换后的工作台基础上，完成剩余风险收口，把“结构已切换但体验仍半成品”的部分收敛为单一路径、稳定契约和可维护实现。

**Architecture:** 继续沿用现有单一 workspace 资产层、单实例任务窗口和壳层录音底座，不再新增第二套数据流或兼容层。本次重点不是扩展功能，而是消除重复入口、清理陈旧路径、补齐主题/i18n/测试契约，并把文档舞台、检查器、任务工具和录音控制台收口到一致的产品语义。所有改动均采用硬切换，直接删除旧路径和无效契约。

**Tech Stack:** Python 3.10+, PySide6, QSS, SQLite, `core/workspace/manager.py`, `core/realtime/recorder.py`, `ui/main_window.py`, `ui/common/realtime_recording_dock.py`, `ui/workspace/*`, `resources/themes/*`, `resources/translations/*`, `tests/ui/*`, `tests/unit/*`.

---

**Assumption:** 假定后续执行发生在独立 worktree/分支中；当前文档仅基于 2026-03-15 当前代码状态、已完成的 workspace polish 改动和截图表现来制定收口计划，不直接实施业务代码修改。

## 1. 审查基线

已审查以下当前实现与契约：

- `docs/plans/2026-03-15-workspace-polish-and-obsidian-alignment.md`
- `ui/main_window.py`
- `ui/common/realtime_recording_dock.py`
- `ui/workspace/widget.py`
- `ui/workspace/task_window.py`
- `ui/workspace/task_panel.py`
- `ui/workspace/tool_rail.py`
- `ui/workspace/library_panel.py`
- `ui/workspace/item_list.py`
- `ui/workspace/editor_panel.py`
- `ui/workspace/inspector_panel.py`
- `ui/workspace/recording_panel.py`
- `ui/workspace/recording_session_panel.py`
- `ui/workspace/detached_document_window.py`
- `ui/constants.py`
- `core/workspace/manager.py`
- `resources/themes/light.qss`
- `resources/themes/dark.qss`
- `resources/themes/theme_outline.json`
- `resources/translations/i18n_outline.json`
- `resources/translations/zh_CN.json`
- `resources/translations/en_US.json`
- `resources/translations/fr_FR.json`
- `tests/unit/test_main_window_shell.py`
- `tests/unit/test_theme_outline_contract.py`
- `tests/unit/test_i18n_outline_contract.py`
- `tests/ui/test_workspace_widget.py`
- `tests/ui/test_batch_task_item_roles.py`

## 2. 当前状态与预期状态差距

### 2.1 应用壳层与全局任务入口

**当前状态**

- `ui/main_window.py` 已切到独立 `WorkspaceTaskWindow`，但 `shell_auxiliary_host` / `set_shell_auxiliary_widget()` 整条旧壳层辅助路径仍留在主窗口中，已经没有有效调用。
- 顶部 `task_window_button` 只是静态按钮文本，没有运行中/待处理任务可见性，也没有窗口状态反馈。
- 任务窗口关闭后只隐藏，不记忆几何信息；再次打开仍是默认大小和位置。

**预期状态**

- 壳层只保留仍然活跃的结构，不存在“旧抽屉已经移除、旧壳层宿主仍在”的死代码。
- 全局任务入口应当让用户不进入窗口就知道任务积压情况。
- 工具窗口是长期存在的壳层工具，尺寸和位置应可恢复。

**优化方向**

- 直接删除 `shell_auxiliary_host` 旧路径。
- 给任务入口增加 backlog 可见性和窗口活跃状态反馈。
- 用现有 `QSettings` 记忆任务窗口 geometry，不设计迁移。

### 2.2 任务工具窗口内容层

**当前状态**

- `ui/workspace/task_panel.py` 已有创建区和筛选区，但仍偏“功能容器”而不是“可管理队列”。
- 当前筛选只有 `all/pending/completed`，没有把 running / failed / paused 明确区分。
- `task_count_label` 只显示当前筛选结果数，不区分总量与积压量。
- 顶部和分区没有专属 role，主题只能落到通用按钮和容器上。

**预期状态**

- 工具窗口首页应先回答三个问题：现在有多少任务、哪些需要关注、我要如何继续创建/查看结果。
- 任务窗口应优先突出 active backlog，而不是只提供一个“列表容器”。
- 工具窗口 copy 和状态语义应稳定进入 i18n 契约。

**优化方向**

- 把筛选改为 `all/running/pending/completed/failed` 或等价语义的唯一一套状态分组。
- 计数展示拆为 “总量 / 活跃 / 失败” 摘要，而不是复用过滤后的局部数量。
- 给 header、summary、filter bar 增加专属 role，并同步主题契约和 i18n。

### 2.3 工作台壳层布局与局部导航

**当前状态**

- `WorkspaceToolRail` 已存在，但 `WorkspaceLibraryPanel` 仍保留 `view_mode_combo`；结构/事件视图切换出现两套入口。
- `WorkspaceToolbar` 仍保留隐藏的 `start_recording_button` 和 `recording_requested` 信号，形成死路径。
- `content_splitter` 当前拉伸系数为 `1:2:2`，正文舞台和右侧检查器默认同宽，截图中右侧空白过大。

**预期状态**

- 同一动作只出现一处主入口，不再允许“工具轨 + explorer header”双重切换。
- 工作台应以文档舞台优先，检查器是上下文，不应该默认与正文等权。
- 不再保留被隐藏但仍然存在的旧交互控件。

**优化方向**

- 硬切删除 `view_mode_combo` 或 `tool_rail` 其中一套；结合当前结构，保留 `tool_rail`、删除 header duplicate 是更小改动。
- 删除 workspace toolbar 中无效录音入口及对应信号。
- 为 `content_splitter` 增加明确初始尺寸和最小宽度常量，改成文档优先比例。

### 2.4 Explorer 与内容列表

**当前状态**

- `ui/workspace/item_list.py` 仍用 `QListWidgetItem` 拼接字符串，元信息通过 `" / "` 文本串表达。
- 事件 ID、folder、source、audio/text/orphaned 都是纯文本，没有主次层级。
- 空列表没有专属 empty state，只是普通列表为空。

**预期状态**

- Explorer 列表应表达“标题 / 次级元信息 / 状态标记”三层结构，而不是字符串堆叠。
- audio/text/orphaned 等状态应是可识别的视觉标志，不是原始英文片段。
- 空态应明确告诉用户当前视图/文件夹下没有内容。

**优化方向**

- 在 `ui/workspace/item_list.py` 内引入自定义 row widget 或 delegate，避免新建重复列表体系。
- 元数据继续从 `WorkspaceManager.get_item_list_metadata()` 单点提供，UI 只负责渲染，不再二次拼字符串。
- 增加列表 empty state role 与契约测试。

### 2.5 文档舞台与资产标签

**当前状态**

- `WorkspaceEditorPanel` 已改用 `asset_tabs`，但仍沿用全局 tab 样式，没有 workspace 自己的 asset-chip 语义。
- `set_item()` 通过 `read_asset_text(asset)` 过滤文本资产，空白 note 的主文本资产可能被直接过滤掉，导致新建空笔记没有可编辑 tab。
- 文档头只有标题和当前资产标签，没有保存状态、来源或主文本上下文摘要。

**预期状态**

- 资产标签应始终稳定存在，只要资产是可编辑文本资产，就算内容为空也必须能打开和编辑。
- 资产切换的视觉语言要明确是“文档内部标签”，而不是系统级浏览器 tab。
- 文档头应能告诉用户当前在编辑什么、内容来源是什么、是否处于可保存状态。

**优化方向**

- 过滤逻辑改为“基于资产 role 和路径可编辑性”而不是“当前文本非空”。
- 引入 `workspace-asset-tab` 或等价 role，而不是继续保留未被使用的 `workspace-asset-selector` 旧契约。
- 补齐文档头的上下文字段和测试，不增加第二套保存逻辑。

### 2.6 检查器与独立文档窗口

**当前状态**

- `WorkspaceInspectorPanel` 目前只有两个大按钮和一个 `WorkspaceRecordingPanel`，没有 source / properties / context 分区。
- AI 按钮直接调用 `WorkspaceEditorPanel._generate_summary()` / `_generate_meeting_brief()`，存在通过受保护方法跨组件耦合的问题。
- `DetachedDocumentWindow` 只有标题 + editor，没有 inspector 上下文，和主工作台体验不一致。

**预期状态**

- 右侧检查器应是上下文卡片栈：AI 操作、录音回放、来源/属性，职责清晰。
- Inspector 与 editor 之间应通过公开命令或委托交互，不直接依赖私有方法。
- 独立窗口要么与主舞台保持核心能力一致，要么显式裁剪为完整但简化的单文档模式；当前两者都不是。

**优化方向**

- 为 inspector 增加分区容器和 item metadata 展示。
- 把 AI 生成动作提升为 editor 公共 API 或独立回调。
- 为 detached window 引入 inspector，或在主计划中明确其简化边界并同步测试；当前更建议直接补齐 inspector，避免双套体验。

### 2.7 录音底座与完整录音控制台

**当前状态**

- `WorkspaceRecordingSessionPanel` 已有五分区，但内部仍是单列控件堆叠，缺少 summary 行、字段说明和可滚动边界。
- `gain_spin` 没有应用 `ROLE_REALTIME_FIELD_CONTROL`，控件语义不一致。
- 默认输入源、目标语言、marker 计数等仍显示原始 `"default"`、`"en"`、数字等技术值，文案颗粒度不足。
- 展开后的完整控制台没有高度约束；窗口高度不足时会粗暴挤压工作台主体。

**预期状态**

- 完整控制台应先可扫读，再可操作；字段要能被普通用户理解，而不是暴露内部枚举值。
- 所有表单控件共享同一套 role 和密度基线。
- 扩展态应该是受控的控制台区域，必要时滚动，不应无限挤压主工作区。

**优化方向**

- 为会话摘要和实时结果区补齐标题、辅助说明、用户态标签。
- 统一字段 role，并把默认值显示改成 i18n 可翻译 copy。
- 给 full panel 增加滚动容器或最大高度约束。

### 2.8 主题、i18n、测试与陈旧契约

**当前状态**

- `ROLE_WORKSPACE_ASSET_SELECTOR` 与 `QComboBox[role="workspace-asset-selector"]` 仍残留在常量、QSS、`theme_outline.json` 和测试中，但当前 UI 已不再使用该控件。
- 任务窗口 badge、empty note asset tab、duplicate view control removal、detached inspector parity、recording console field copy 等都没有测试覆盖。
- 文档已更新到“任务窗口/工具轨”新结构，但下一轮结构收口仍需要同步更新索引和 changelog。

**预期状态**

- 所有 role、selector、i18n key、文档索引都与当前真实控件一一对应。
- 契约测试覆盖真实风险点，而不是只验证容器存在。
- 不保留已经废弃的 role 或隐藏控件。

**优化方向**

- 硬切删除 `workspace-asset-selector` 旧契约。
- 用更细粒度 UI 回归和契约测试覆盖本轮收口点。
- 在相同变更中同步更新 `AGENTS.md`、`docs/README.md`、`skills/release-process/SKILL.md`、`CHANGELOG.md`。

## 3. 实施顺序总览

1. 先清理壳层死路径，并把任务入口补齐为真正的壳层工具入口。
2. 再收口工作台壳层布局，去掉重复入口，把文档舞台比例调回正文优先。
3. 然后修正 explorer 列表、文档舞台和 inspector 的核心产品语义。
4. 最后完成录音控制台 copy/密度/滚动约束，并统一清理主题、i18n、测试和文档契约。

### Task 1: 删除陈旧壳层辅助宿主并补齐任务窗口几何记忆

**Files:**
- Modify: `ui/main_window.py`
- Modify: `ui/workspace/task_window.py`
- Test: `tests/unit/test_main_window_shell.py`

**Step 1: Write the failing test**

```python
def test_main_window_task_window_persists_geometry_and_drops_shell_auxiliary_host(tmp_path):
    main_window = build_main_window_with_workspace(tmp_path, transcription_manager=_build_transcription_manager())

    main_window.task_window_button.click()
    task_window = main_window.task_window
    task_window.resize(840, 610)
    task_window.move(120, 160)
    task_window.close()
    main_window.close()

    reopened = build_main_window_with_workspace(tmp_path, transcription_manager=_build_transcription_manager())
    reopened.task_window_button.click()

    assert not hasattr(reopened, "shell_auxiliary_host")
    assert reopened.task_window.size().width() == 840
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_main_window_shell.py::test_main_window_task_window_persists_geometry_and_drops_shell_auxiliary_host -v`
Expected: FAIL，因为当前主窗口仍保留 `shell_auxiliary_host`，任务窗口也没有 geometry 持久化。

**Step 3: Write minimal implementation**

```python
class WorkspaceTaskWindow(BaseWidget):
    def save_window_state(self) -> None:
        ...

    def restore_window_state(self) -> None:
        ...
```

实现要求：

- 直接删除 `MainWindow` 里的 `shell_auxiliary_host`、`shell_auxiliary_layout`、`_shell_auxiliary_widget` 和 `set_shell_auxiliary_widget()`。
- 复用主窗口现有 `QSettings` 方案，为任务窗口新增 geometry 读写。
- 关闭任务窗口时仍只隐藏，但必须先保存几何信息。

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_main_window_shell.py::test_main_window_task_window_persists_geometry_and_drops_shell_auxiliary_host -v`
Expected: PASS

**Step 5: Commit**

```bash
git add ui/main_window.py ui/workspace/task_window.py tests/unit/test_main_window_shell.py
git commit -m "refactor: remove stale shell auxiliary host"
```

### Task 2: 给壳层任务入口补齐 backlog 反馈和任务窗口摘要

**Files:**
- Modify: `ui/main_window.py`
- Modify: `ui/workspace/task_panel.py`
- Modify: `ui/constants.py`
- Modify: `resources/themes/light.qss`
- Modify: `resources/themes/dark.qss`
- Modify: `resources/themes/theme_outline.json`
- Modify: `resources/translations/i18n_outline.json`
- Modify: `resources/translations/zh_CN.json`
- Modify: `resources/translations/en_US.json`
- Modify: `resources/translations/fr_FR.json`
- Test: `tests/unit/test_main_window_shell.py`
- Test: `tests/ui/test_workspace_widget.py`
- Test: `tests/unit/test_i18n_outline_contract.py`
- Test: `tests/unit/test_theme_outline_contract.py`

**Step 1: Write the failing test**

```python
def test_main_window_task_entry_exposes_backlog_badge(tmp_path):
    manager = _build_transcription_manager()
    manager.get_active_task_count.return_value = 3
    main_window = build_main_window_with_workspace(tmp_path, transcription_manager=manager)

    MainWindow._update_shell_status(main_window)

    assert main_window.task_window_badge.text() == "3"
    assert main_window.task_window_badge.isVisible()
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_main_window_shell.py::test_main_window_task_entry_exposes_backlog_badge -v`
Expected: FAIL，因为当前顶部只有 `task_window_button`，没有 badge 容器。

**Step 3: Write minimal implementation**

```python
class MainWindow(QMainWindow):
    def _refresh_task_entry_state(self) -> None:
        active_count = self._get_active_transcription_task_count()
        ...
```

实现要求：

- 顶部任务入口改成“按钮 + badge”唯一结构。
- 任务窗口顶部补一个总览摘要区，明确 total / active / failed 或等价语义。
- 同步新增 role、QSS 选择器和 i18n key，不允许直接硬编码中文/英文状态文本。

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_main_window_shell.py tests/ui/test_workspace_widget.py tests/unit/test_i18n_outline_contract.py tests/unit/test_theme_outline_contract.py -k "task_entry_exposes_backlog_badge or task_window_summary" -v`
Expected: PASS

**Step 5: Commit**

```bash
git add ui/main_window.py ui/workspace/task_panel.py ui/constants.py resources/themes/light.qss resources/themes/dark.qss resources/themes/theme_outline.json resources/translations/i18n_outline.json resources/translations/zh_CN.json resources/translations/en_US.json resources/translations/fr_FR.json tests/unit/test_main_window_shell.py tests/ui/test_workspace_widget.py tests/unit/test_i18n_outline_contract.py tests/unit/test_theme_outline_contract.py
git commit -m "feat: surface workspace task backlog state"
```

### Task 3: 删除工作台重复视图入口并重设正文优先布局

**Files:**
- Modify: `ui/workspace/widget.py`
- Modify: `ui/workspace/library_panel.py`
- Modify: `ui/workspace/tool_rail.py`
- Modify: `ui/workspace/toolbar.py`
- Modify: `ui/constants.py`
- Modify: `resources/themes/light.qss`
- Modify: `resources/themes/dark.qss`
- Modify: `resources/themes/theme_outline.json`
- Test: `tests/ui/test_workspace_widget.py`
- Test: `tests/unit/test_theme_outline_contract.py`

**Step 1: Write the failing test**

```python
def test_workspace_shell_uses_single_view_mode_entry_and_document_first_splitter(qapp, mock_i18n, workspace_manager):
    widget = WorkspaceWidget(workspace_manager, mock_i18n)
    widget.show()
    qapp.processEvents()

    assert not hasattr(widget.library_panel, "view_mode_combo")
    assert widget.content_splitter.sizes()[1] > widget.content_splitter.sizes()[2]
    assert not hasattr(widget.toolbar, "start_recording_button")
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/ui/test_workspace_widget.py::test_workspace_shell_uses_single_view_mode_entry_and_document_first_splitter -v`
Expected: FAIL，因为当前仍有 `view_mode_combo`、隐藏录音按钮和对正文不友好的 splitter 比例。

**Step 3: Write minimal implementation**

```python
class WorkspaceLibraryPanel(BaseWidget):
    def _init_ui(self) -> None:
        self.title_label = QLabel(...)
        # no view_mode_combo
```

实现要求：

- 保留 `tool_rail` 作为结构/事件视图唯一切换入口，删除 explorer header 中重复的 `view_mode_combo`。
- 删除 `WorkspaceToolbar` 中未使用的录音按钮和 `recording_requested` 信号。
- 给 `content_splitter` 设置明确的初始 sizes / minimum widths，让 document stage 默认宽于 inspector。

**Step 4: Run test to verify it passes**

Run: `pytest tests/ui/test_workspace_widget.py tests/unit/test_theme_outline_contract.py -k "single_view_mode_entry_and_document_first_splitter" -v`
Expected: PASS

**Step 5: Commit**

```bash
git add ui/workspace/widget.py ui/workspace/library_panel.py ui/workspace/tool_rail.py ui/workspace/toolbar.py ui/constants.py resources/themes/light.qss resources/themes/dark.qss resources/themes/theme_outline.json tests/ui/test_workspace_widget.py tests/unit/test_theme_outline_contract.py
git commit -m "refactor: dedupe workspace local navigation"
```

### Task 4: 把 Explorer 列表从字符串拼接升级为结构化条目

**Files:**
- Modify: `ui/workspace/item_list.py`
- Modify: `ui/constants.py`
- Modify: `resources/themes/light.qss`
- Modify: `resources/themes/dark.qss`
- Modify: `resources/themes/theme_outline.json`
- Modify: `resources/translations/i18n_outline.json`
- Modify: `resources/translations/zh_CN.json`
- Modify: `resources/translations/en_US.json`
- Modify: `resources/translations/fr_FR.json`
- Test: `tests/ui/test_workspace_widget.py`
- Test: `tests/unit/test_i18n_outline_contract.py`
- Test: `tests/unit/test_theme_outline_contract.py`

**Step 1: Write the failing test**

```python
def test_workspace_item_list_renders_structured_row_widgets(qapp, mock_i18n, workspace_manager):
    note_id = workspace_manager.create_note(title="Plan")
    widget = WorkspaceWidget(workspace_manager, mock_i18n)
    widget.show()
    qapp.processEvents()

    row_widget = widget.item_list.list_widget.itemWidget(widget.item_list.list_widget.item(0))

    assert row_widget.title_label.text() == "Plan"
    assert row_widget.meta_label.text()
    assert row_widget.status_badges_layout.count() >= 1
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/ui/test_workspace_widget.py::test_workspace_item_list_renders_structured_row_widgets -v`
Expected: FAIL，因为当前列表只塞了 `QListWidgetItem` 文本，没有 item widget。

**Step 3: Write minimal implementation**

```python
class WorkspaceItemRowWidget(QWidget):
    ...
```

实现要求：

- 继续复用 `WorkspaceManager.get_item_list_metadata()` 作为唯一元数据来源。
- UI 只负责把标题、meta、状态标记拆成结构化行，不新增第二套 metadata 计算。
- 为空列表增加显式 empty state，并用新的 role/selector 收口主题。

**Step 4: Run test to verify it passes**

Run: `pytest tests/ui/test_workspace_widget.py tests/unit/test_i18n_outline_contract.py tests/unit/test_theme_outline_contract.py -k "structured_row_widgets or workspace_item_list_empty_state" -v`
Expected: PASS

**Step 5: Commit**

```bash
git add ui/workspace/item_list.py ui/constants.py resources/themes/light.qss resources/themes/dark.qss resources/themes/theme_outline.json resources/translations/i18n_outline.json resources/translations/zh_CN.json resources/translations/en_US.json resources/translations/fr_FR.json tests/ui/test_workspace_widget.py tests/unit/test_i18n_outline_contract.py tests/unit/test_theme_outline_contract.py
git commit -m "feat: render structured workspace explorer rows"
```

### Task 5: 修正文档舞台资产标签语义并保证空白笔记可编辑

**Files:**
- Modify: `ui/workspace/editor_panel.py`
- Modify: `ui/constants.py`
- Modify: `resources/themes/light.qss`
- Modify: `resources/themes/dark.qss`
- Modify: `resources/themes/theme_outline.json`
- Test: `tests/ui/test_workspace_widget.py`
- Test: `tests/unit/test_theme_outline_contract.py`

**Step 1: Write the failing test**

```python
def test_workspace_editor_keeps_blank_note_asset_tab_editable(qapp, mock_i18n, workspace_manager):
    note_id = workspace_manager.create_note(title="Blank Note", text_content="")
    widget = WorkspaceWidget(workspace_manager, mock_i18n)

    widget.open_item(note_id)

    assert widget.editor_panel.asset_tabs.count() == 1
    assert widget.editor_panel.edit_button.isEnabled()
    assert widget.editor_panel.text_edit.toPlainText() == ""
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/ui/test_workspace_widget.py::test_workspace_editor_keeps_blank_note_asset_tab_editable -v`
Expected: FAIL，因为当前 `set_item()` 会把空文本资产过滤掉。

**Step 3: Write minimal implementation**

```python
class WorkspaceEditorPanel(TextEditorPanel):
    def _is_editable_text_asset(self, asset) -> bool:
        ...
```

实现要求：

- 空内容的 `document_text` / `transcript` / `translation` 等文本资产也必须进入 `asset_tabs`。
- 删除未使用的 `workspace-asset-selector` 旧 role 依赖，改成新的 workspace asset tab role。
- 文档头补齐当前资产语义与保存状态提示，但不新增第二套保存模型。

**Step 4: Run test to verify it passes**

Run: `pytest tests/ui/test_workspace_widget.py tests/unit/test_theme_outline_contract.py -k "blank_note_asset_tab_editable or workspace_asset_tabs" -v`
Expected: PASS

**Step 5: Commit**

```bash
git add ui/workspace/editor_panel.py ui/constants.py resources/themes/light.qss resources/themes/dark.qss resources/themes/theme_outline.json tests/ui/test_workspace_widget.py tests/unit/test_theme_outline_contract.py
git commit -m "fix: keep workspace blank notes editable"
```

### Task 6: 把检查器升级为上下文卡片并让独立文档窗口与主舞台对齐

**Files:**
- Modify: `ui/workspace/inspector_panel.py`
- Modify: `ui/workspace/recording_panel.py`
- Modify: `ui/workspace/editor_panel.py`
- Modify: `ui/workspace/detached_document_window.py`
- Modify: `ui/constants.py`
- Modify: `resources/themes/light.qss`
- Modify: `resources/themes/dark.qss`
- Modify: `resources/themes/theme_outline.json`
- Modify: `resources/translations/i18n_outline.json`
- Modify: `resources/translations/zh_CN.json`
- Modify: `resources/translations/en_US.json`
- Modify: `resources/translations/fr_FR.json`
- Test: `tests/ui/test_workspace_widget.py`
- Test: `tests/unit/test_i18n_outline_contract.py`
- Test: `tests/unit/test_theme_outline_contract.py`

**Step 1: Write the failing test**

```python
def test_detached_document_window_matches_workspace_context_stack(qapp, mock_i18n, workspace_manager):
    note_id = workspace_manager.create_note(title="Plan")
    window = DetachedDocumentWindow(workspace_manager, mock_i18n, note_id)
    window.show()
    qapp.processEvents()

    assert window.inspector_panel is not None
    assert window.inspector_panel.recording_panel is not None
    assert hasattr(window.editor_panel, "generate_summary")
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/ui/test_workspace_widget.py::test_detached_document_window_matches_workspace_context_stack -v`
Expected: FAIL，因为当前 detached window 没有 inspector，editor 也只暴露私有 AI 方法。

**Step 3: Write minimal implementation**

```python
class WorkspaceEditorPanel(TextEditorPanel):
    def generate_summary(self) -> None:
        self._generate_summary()
```

实现要求：

- Inspector 改成至少三段：AI actions、recording/media、item metadata/source。
- Inspector 与 editor 通过公开方法或显式回调协作，不再直接调用私有方法。
- `DetachedDocumentWindow` 引入与主舞台一致的 inspector stack，避免双套体验。

**Step 4: Run test to verify it passes**

Run: `pytest tests/ui/test_workspace_widget.py tests/unit/test_i18n_outline_contract.py tests/unit/test_theme_outline_contract.py -k "detached_document_window_matches_workspace_context_stack or workspace_inspector_metadata" -v`
Expected: PASS

**Step 5: Commit**

```bash
git add ui/workspace/inspector_panel.py ui/workspace/recording_panel.py ui/workspace/editor_panel.py ui/workspace/detached_document_window.py ui/constants.py resources/themes/light.qss resources/themes/dark.qss resources/themes/theme_outline.json resources/translations/i18n_outline.json resources/translations/zh_CN.json resources/translations/en_US.json resources/translations/fr_FR.json tests/ui/test_workspace_widget.py tests/unit/test_i18n_outline_contract.py tests/unit/test_theme_outline_contract.py
git commit -m "feat: align workspace inspector and detached window"
```

### Task 7: 收口录音控制台字段语义、滚动边界与分区密度

**Files:**
- Modify: `ui/common/realtime_recording_dock.py`
- Modify: `ui/workspace/recording_session_panel.py`
- Modify: `ui/constants.py`
- Modify: `resources/themes/light.qss`
- Modify: `resources/themes/dark.qss`
- Modify: `resources/themes/theme_outline.json`
- Modify: `resources/translations/i18n_outline.json`
- Modify: `resources/translations/zh_CN.json`
- Modify: `resources/translations/en_US.json`
- Modify: `resources/translations/fr_FR.json`
- Test: `tests/unit/test_main_window_shell.py`
- Test: `tests/ui/test_workspace_widget.py`
- Test: `tests/unit/test_i18n_outline_contract.py`
- Test: `tests/unit/test_theme_outline_contract.py`

**Step 1: Write the failing test**

```python
def test_recording_dock_full_panel_uses_scroll_container_and_localized_summary_labels():
    dock = build_recording_dock()

    dock.set_expanded(True)

    assert dock.full_panel_scroll_area is not None
    assert dock.full_panel.gain_spin.property("role") == "realtime-field-control"
    assert "default" not in dock.full_panel.summary_input_label.text().lower()
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_main_window_shell.py::test_recording_dock_full_panel_uses_scroll_container_and_localized_summary_labels -v`
Expected: FAIL，因为当前没有 scroll container，`gain_spin` 未设置 role，summary 仍可能显示原始技术值。

**Step 3: Write minimal implementation**

```python
class RealtimeRecordingDock(BaseWidget):
    def _init_ui(self) -> None:
        self.full_panel_scroll_area = QScrollArea(...)
```

实现要求：

- 展开态完整控制台使用受控滚动容器或最大高度，避免挤压正文区。
- 给所有字段控件统一 role，`QDoubleSpinBox` 也纳入 `ROLE_REALTIME_FIELD_CONTROL`。
- 默认输入源、目标语言、marker 数等展示值改成用户态文案，并进入 i18n 大纲。

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_main_window_shell.py tests/ui/test_workspace_widget.py tests/unit/test_i18n_outline_contract.py tests/unit/test_theme_outline_contract.py -k "scroll_container_and_localized_summary_labels or recording_console_copy" -v`
Expected: PASS

**Step 5: Commit**

```bash
git add ui/common/realtime_recording_dock.py ui/workspace/recording_session_panel.py ui/constants.py resources/themes/light.qss resources/themes/dark.qss resources/themes/theme_outline.json resources/translations/i18n_outline.json resources/translations/zh_CN.json resources/translations/en_US.json resources/translations/fr_FR.json tests/unit/test_main_window_shell.py tests/ui/test_workspace_widget.py tests/unit/test_i18n_outline_contract.py tests/unit/test_theme_outline_contract.py
git commit -m "feat: polish realtime recording console semantics"
```

### Task 8: 删除陈旧主题契约并同步文档索引

**Files:**
- Modify: `ui/constants.py`
- Modify: `resources/themes/light.qss`
- Modify: `resources/themes/dark.qss`
- Modify: `resources/themes/theme_outline.json`
- Modify: `tests/unit/test_theme_outline_contract.py`
- Modify: `AGENTS.md`
- Modify: `docs/README.md`
- Modify: `skills/release-process/SKILL.md`
- Modify: `CHANGELOG.md`

**Step 1: Write the failing test**

```python
def test_theme_outline_no_longer_references_workspace_asset_selector():
    outline = _load_theme_outline()
    selectors = {
        selector
        for section in outline.get("sections", [])
        for selector in section.get("selectors", [])
    }
    assert 'QComboBox[role="workspace-asset-selector"]' not in selectors
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_theme_outline_contract.py::test_theme_outline_no_longer_references_workspace_asset_selector -v`
Expected: FAIL，因为当前旧 selector 仍在 outline/QSS/常量中。

**Step 3: Write minimal implementation**

```python
ROLE_WORKSPACE_ASSET_SELECTOR = None
```

实现要求：

- 直接删除 `ROLE_WORKSPACE_ASSET_SELECTOR` 常量和对应 QSS/outline/test 引用，不保留兼容层。
- 把本轮最终结构同步写回 `AGENTS.md`、`docs/README.md`、`skills/release-process/SKILL.md`、`CHANGELOG.md`。
- 文档描述必须与最终代码真实结构一致，不能继续写“可选方案”或“双轨存在”。

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_theme_outline_contract.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add ui/constants.py resources/themes/light.qss resources/themes/dark.qss resources/themes/theme_outline.json tests/unit/test_theme_outline_contract.py AGENTS.md docs/README.md skills/release-process/SKILL.md CHANGELOG.md
git commit -m "chore: remove stale workspace theme contracts"
```

## 4. 最终验证

执行完全部任务后，至少运行以下回归：

- `pytest tests/unit/test_main_window_shell.py -v`
- `pytest tests/ui/test_workspace_widget.py -v`
- `pytest tests/ui/test_batch_task_item_roles.py -v`
- `pytest tests/unit/test_theme_outline_contract.py -v`
- `pytest tests/unit/test_i18n_outline_contract.py -v`

预期结果：

- 全部通过。
- `rg -n "workspace-asset-selector|shell_auxiliary_host|recording_requested" ui resources tests` 无残留或只剩测试断言中的“not in”语义。
- `git diff --check` 无格式错误。

## 5. 风险提示

- `WorkspaceEditorPanel` 空白资产可编辑性是当前真实行为风险，优先级高于纯视觉 polish。
- 删除 duplicate view control 后，需要同步确认测试和 i18n 不再引用 explorer header 的旧视图切换文案。
- Detached window 如果补 inspector，要注意与主窗口共享同一个 `WorkspaceManager`，不能引入第二套 item 缓存。
- Recording console copy 收口时，必须只用 i18n key，不要把 `"default"`、语言码或 source 状态直接拼进 UI。
