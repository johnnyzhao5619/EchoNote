# Workspace Polish And Obsidian Alignment Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 用硬切换方式完成统一工作台的第二阶段整顿：把批量任务收敛为独立工具窗口、把完整录音界面重构为可长期维护的分区控制台、并把笔记工作台升级为更接近 Obsidian 的桌面文档体验。

**Architecture:** 现有 `workspace` / `recording_dock` / `workspace_items` 基础可以继续复用，但 UI 结构仍停留在“技术骨架已到位、产品界面未收口”的状态。本方案不再新增第二套数据流，而是在现有单一资产层上，重新梳理壳层工具入口、工作台局部工具层、文档舞台与检查器的职责边界，直接删除与新体验冲突的旧布局和重复控件。

**Tech Stack:** Python 3.10+, PySide6, QSS, SQLite, `core/workspace/*`, `core/realtime/recorder.py`, `ui/main_window.py`, `ui/common/realtime_recording_dock.py`, `ui/workspace/*`, `resources/themes/*`, `resources/translations/*`, `tests/ui/*`, `tests/unit/*`.

---

**Assumption:** 假定后续实现会在独立 worktree/分支中进行；当前会话只更新规划与相关文档，不直接改业务代码。

## 1. 审查结论

### 1.1 当前代码与界面的真实问题

1. `ui/main_window.py` 仍通过 `_attach_task_drawer()` 把 `WorkspaceTaskPanel` 直接挂到壳层录音底座上方，批量任务仍然是“全局功能被塞进底部辅助层”，与“独立工具窗口/工具面板”的目标冲突。
2. `ui/common/realtime_recording_dock.py` 还保留 `task_drawer_host` 和 `set_task_drawer_widget()`，说明录音底座同时承担“录音控制 + 任务承载”两种职责，信息优先级被混写。
3. `ui/workspace/recording_session_panel.py` 当前是纯 `QVBoxLayout` 线性堆叠：输入源、增益、复选框、开始/停止、marker、预览全部顺序平铺，没有分区、没有层级、没有自适应收纳，截图中的“元器件堆叠”正是这个实现方式直接造成的。
4. `ui/workspace/editor_panel.py` 虽然已经复用了统一编辑器，但工作台主心智仍然偏“技术资产切换”而不是“笔记编辑”：`asset_selector` 仍是 `QComboBox`，AI 按钮仍塞在主工具栏，标题区也只是单个 `QLabel`。
5. `ui/workspace/inspector_panel.py` 当前只承载 `WorkspaceRecordingPanel`，右侧检查器没有形成 Obsidian 式的上下文区，导致音频、属性、AI 操作、来源信息没有真正分层。
6. `ui/workspace/item_list.py` 仍基于 `QListWidget` 拼接多行字符串展示元信息，缺少真正的文档卡片、密度控制、筛选语义和更明确的状态层级。
7. `ui/workspace/detached_document_window.py` 只是把现有编辑器单独包一层窗口，尚未具备与主工作台一致的标题、上下文与检查器体验。
8. `docs/README.md` 当前仍写着“workspace 页拥有 in-page batch task queue”，这与代码里的壳层任务挂载现状已经不一致，文档开始落后于真实实现。

### 1.2 从产品本质出发的判断

1. 批量任务不是“文档内容”，而是跨页面、长生命周期、可随时回看的后台工具，因此不应该继续占用工作台主体，也不应该绑在录音底座上。
2. 录音界面不是“设置表单”，而是“会话控制台”；核心是让用户快速确认采集目标、处理中策略、实时结果和会话标记，而不是按配置项阅读一列控件。
3. 工作台的主对象应当是 note/document，而不是 transcript/translation/summary 等 asset role；这些角色属于文档内部上下文，不应支配主导航。
4. Obsidian 可借鉴的是桌面文档产品的结构能力：工具入口独立、文件树明确、标签页稳定、检查器可折叠、上下文操作不过度打断正文编辑；不需要照搬插件体系、图谱或双链。

### 1.3 外部参考如何转成 EchoNote 的落地原则

1. Obsidian 官方帮助文档把 `File explorer`、`Workspaces`、`Backlinks`、`Properties` 都放在分层面板体系中，证明“导航、正文、上下文”三层解耦是成熟桌面笔记产品的通用组织方式。
2. Apple HIG 的 `Sidebars` 建议在层级较深时使用“sidebar + content list + detail view” 的 split view；EchoNote 当前正缺中间的内容列表语义和右侧上下文面板的职责清晰度。
3. Microsoft `NavigationView` / navigation basics 强调主导航与工具性面板分离，长生命周期工具应可独立打开而不打断主内容流，这与批量任务独立窗口的方向一致。

## 2. 产品目标与非目标

### 2.1 产品目标

1. 批量转写/转译任务收敛为壳层级独立工具窗口，可通过窗口按钮打开，默认单实例、非模态、跨页面可见。
2. 完整录音界面升级为“分区控制台”而不是线性表单，至少清晰拆分为会话摘要、采集控制、处理策略、输出策略、实时预览/marker 五个层级。
3. 工作台笔记体验升级为“局部工具轨 + 资源浏览器 + 文档标签舞台 + 右侧检查器”的桌面式布局，明显减少当前大面积空白和控件堆叠。
4. 编辑主路径以 note/document 为中心，正文区优先，AI 与音频等上下文能力下沉到检查器或次级区，不再抢占主工具栏。
5. 所有优化继续复用统一资产层，不新增第二套任务结果或编辑数据模型。

### 2.2 非目标

1. 不做向前兼容，不保留 task drawer 与 task window 并存的双轨方案。
2. 不实现 Obsidian 插件、双链、图谱、Canvas 等超范围能力。
3. 不重写文本编辑器内核；首期继续基于现有 `TextEditorPanel` / `QTextEdit`，重点重构信息架构和界面分层。
4. 不把时间线、日历、工作台重新合并成一个超重页面。

## 3. 方案决策

### 3.1 批量任务：从底部抽屉改为独立工具窗口

1. 默认方案：新增壳层级 `WorkspaceTaskWindow`，通过主窗口上的工具按钮打开，按钮显示运行中/待处理任务数 badge。
2. 窗口形式：单实例、非模态、可记忆尺寸与位置；关闭窗口不影响任务运行，只影响可视界面。
3. 窗口内容：顶部为任务创建与筛选区，中部为队列列表，底部为上下文操作；查看结果仍统一跳转到工作台对应文档标签。
4. 硬切换要求：删除 `RealtimeRecordingDock.task_drawer_host` 与 `MainWindow._attach_task_drawer()` 这一整条挂载路径，避免录音底座继续背负任务界面职责。

### 3.2 录音：从设置表单改为会话控制台

1. 保留壳层精简录音底座，承担高频开始/停止与基础状态展示。
2. 展开后的完整录音界面改为分区卡片：
   - 会话摘要：状态、时长、输入源、目标语言、保存策略摘要
   - 采集控制：输入设备、增益、音频级别、浮窗
   - 处理策略：转写、翻译、目标语言、模型/默认策略提示
   - 输出策略：保存录音、保存转写、创建日历事件
   - 实时结果：转写预览、翻译预览、marker 列表与新增 marker
3. 控件密度与分组必须由统一常量和主题 role 驱动，不能再把 spacing、标题样式、分隔线散落在多个控件里硬编码。
4. 全部会话选项仍直接复用 `SettingsManager` 默认值与 `RealtimeRecorder` 状态机，避免复制设置读写。

### 3.3 工作台：向 Obsidian 借鉴“桌面文档工作区”而不是“网页应用面板”

1. 保留应用全局侧边导航，不复制第二套全局导航。
2. 在工作台内部新增局部工具轨，承担高频动作与局部视图切换，例如：新建笔记、导入、聚焦结构视图/事件视图、打开任务窗口、折叠检查器。
3. 左侧浏览区拆成两层：
   - Explorer：文件夹树 / 事件入口 / 筛选
   - 内容列表：文档卡片或紧凑列表，展示标题、来源、更新时间、音频/文本状态
4. 中央舞台保留多标签文档，但升级为“标签条 + 文档头部 + 正文编辑区”三层结构：
   - 标签条负责多开与独立窗口
   - 文档头部负责标题、保存状态、核心元信息
   - 正文区只放编辑主任务
5. 右侧检查器改为可折叠的上下文卡片区，承载音频回放、来源信息、属性、AI 生成动作和后续可能的关联信息。
6. 资产切换改为标签/chips，不再用 `QComboBox` 主导用户心智；`asset_role` 仍在底层存在，但不暴露为技术化主控件。

## 4. 关键假设与建议

1. 假设：批量任务窗口比“嵌入式抽屉”更符合当前产品阶段。
   - 理由：任务是跨页面后台能力，独立窗口能减少对工作台纵向空间的侵占，也更接近 Obsidian 的工具视图心智。
2. 假设：工作台内的“局部工具轨”应控制在 4-6 个高频动作内，不做第二套复杂导航。
   - 理由：EchoNote 已经有应用主导航，再复制 Obsidian 的整套 Ribbon 会产生双重侧边栏和操作噪音。
3. 假设：右侧检查器首期只承载音频、属性、AI 操作、来源信息四类卡片。
   - 理由：这四类已经覆盖当前最核心的上下文需求，再扩展会把改造目标拖成“全量知识管理系统”。
4. 建议：先把布局和职责重构完成，再细修样式。
   - 理由：如果继续在旧布局上补 QSS，只会把结构问题固化。

## 5. 实施顺序总览

1. 先把批量任务从底座上剥离，建立壳层级独立工具窗口。
2. 再重构完整录音控制台，把线性表单拆成明确分区。
3. 然后升级工作台内部布局，让文档舞台、浏览区、检查器各归其位。
4. 最后统一清理主题/i18n/文档/测试，确保硬切换后没有陈旧说明和重复路径。

### Task 1: 建立壳层级批量任务工具窗口并移除底座任务抽屉

**Files:**
- Create: `ui/workspace/task_window.py`
- Modify: `ui/main_window.py`
- Modify: `ui/common/realtime_recording_dock.py`
- Modify: `ui/workspace/task_panel.py`
- Test: `tests/unit/test_main_window_shell.py`
- Test: `tests/ui/test_workspace_widget.py`

**Step 1: Write the failing test**

```python
def test_main_window_opens_singleton_workspace_task_window(tmp_path):
    window = build_main_window_with_workspace(tmp_path)

    window.task_window_button.click()

    assert window.task_window is not None
    assert window.task_window.isVisible()
    assert not hasattr(window.recording_dock, "task_drawer_host")
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_main_window_shell.py tests/ui/test_workspace_widget.py -k "task_window or singleton_workspace_task_window" -v`
Expected: FAIL，因为当前主窗口没有独立任务窗口入口，录音底座仍保留任务抽屉宿主。

**Step 3: Write minimal implementation**

```python
class WorkspaceTaskWindow(QWidget):
    ...
```

实现要求：
- 在 `ui/main_window.py` 增加壳层工具按钮和单实例 `WorkspaceTaskWindow`。
- `WorkspaceTaskPanel` 继续复用，但只能挂载在独立窗口，不再塞进 `RealtimeRecordingDock`。
- 直接移除 `task_drawer_host` / `set_task_drawer_widget()` 相关逻辑，避免新旧并存。

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_main_window_shell.py tests/ui/test_workspace_widget.py -k "task_window or singleton_workspace_task_window" -v`
Expected: PASS

**Step 5: Commit**

```bash
git add ui/workspace/task_window.py ui/main_window.py ui/common/realtime_recording_dock.py ui/workspace/task_panel.py tests/unit/test_main_window_shell.py tests/ui/test_workspace_widget.py
git commit -m "feat: move workspace tasks into utility window"
```

### Task 2: 重构任务窗口内容层，收敛创建入口、筛选与结果跳转

**Files:**
- Modify: `ui/workspace/task_panel.py`
- Modify: `ui/batch_transcribe/task_item.py`
- Modify: `ui/main_window.py`
- Test: `tests/ui/test_workspace_widget.py`
- Test: `tests/ui/test_batch_task_item_roles.py`

**Step 1: Write the failing test**

```python
def test_workspace_task_window_groups_creation_actions_and_routes_view_to_workspace(
    qapp, mock_i18n, workspace_manager, transcription_manager
):
    main_window, _ = build_main_window_with_workspace(
        qapp,
        mock_i18n,
        workspace_manager,
        transcription_manager=transcription_manager,
    )

    main_window.task_window_button.click()
    task_window = main_window.task_window

    assert task_window.panel.task_filter_tabs.count() >= 2
    assert task_window.panel.import_file_button.isVisible()
    assert task_window.panel.import_folder_button.isVisible()
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/ui/test_workspace_widget.py tests/ui/test_batch_task_item_roles.py -k "task_window_groups_creation_actions" -v`
Expected: FAIL，因为当前任务面板没有独立窗口上下文，也没有新的分区结构。

**Step 3: Write minimal implementation**

```python
class WorkspaceTaskPanel(BaseWidget):
    def _build_header(self) -> None:
        ...
```

实现要求：
- 任务窗口顶部明确分成“创建动作”和“队列筛选”两层。
- 查看任务结果仍统一复用 `MainWindow.open_workspace_item()`，不引入第二套查看器。
- 如果 `view_clicked` 目标已发布到工作台，则直接聚焦对应文档；未发布时再触发发布逻辑。

**Step 4: Run test to verify it passes**

Run: `pytest tests/ui/test_workspace_widget.py tests/ui/test_batch_task_item_roles.py -k "task_window_groups_creation_actions" -v`
Expected: PASS

**Step 5: Commit**

```bash
git add ui/workspace/task_panel.py ui/batch_transcribe/task_item.py ui/main_window.py tests/ui/test_workspace_widget.py tests/ui/test_batch_task_item_roles.py
git commit -m "feat: polish workspace task utility surface"
```

### Task 3: 把完整录音面板重构为分区控制台

**Files:**
- Modify: `ui/workspace/recording_session_panel.py`
- Modify: `ui/common/realtime_recording_dock.py`
- Modify: `ui/realtime_record/floating_overlay.py`
- Modify: `ui/constants.py`
- Modify: `resources/themes/light.qss`
- Modify: `resources/themes/dark.qss`
- Modify: `resources/themes/theme_outline.json`
- Test: `tests/unit/test_theme_outline_contract.py`
- Test: `tests/unit/test_main_window_shell.py`
- Test: `tests/ui/test_workspace_widget.py`

**Step 1: Write the failing test**

```python
def test_recording_dock_full_panel_exposes_grouped_console_sections():
    dock = build_recording_dock()

    dock.set_expanded(True)

    assert dock.full_panel.session_summary_section is not None
    assert dock.full_panel.capture_section is not None
    assert dock.full_panel.processing_section is not None
    assert dock.full_panel.output_section is not None
    assert dock.full_panel.live_results_section is not None
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_main_window_shell.py tests/ui/test_workspace_widget.py tests/unit/test_theme_outline_contract.py -k "grouped_console_sections or recording_dock_full_panel" -v`
Expected: FAIL，因为当前完整录音面板还是线性堆叠，没有分区语义，也没有对应主题契约。

**Step 3: Write minimal implementation**

```python
class WorkspaceRecordingSessionPanel(BaseWidget):
    def _build_section(self, title: str) -> QWidget:
        ...
```

实现要求：
- 用稳定的 section/card 结构替代纯线性堆叠。
- 预览区与 marker 区独立成块，不再夹在开始/停止按钮之间。
- 新增 role/selector 必须同步补齐双主题和 `theme_outline.json`。

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_main_window_shell.py tests/ui/test_workspace_widget.py tests/unit/test_theme_outline_contract.py -k "grouped_console_sections or recording_dock_full_panel" -v`
Expected: PASS

**Step 5: Commit**

```bash
git add ui/workspace/recording_session_panel.py ui/common/realtime_recording_dock.py ui/realtime_record/floating_overlay.py ui/constants.py resources/themes/light.qss resources/themes/dark.qss resources/themes/theme_outline.json tests/unit/test_theme_outline_contract.py tests/unit/test_main_window_shell.py tests/ui/test_workspace_widget.py
git commit -m "feat: redesign recording session console"
```

### Task 4: 重构工作台浏览区与局部工具轨，建立更接近 Obsidian 的桌面笔记壳层

**Files:**
- Create: `ui/workspace/tool_rail.py`
- Modify: `ui/workspace/widget.py`
- Modify: `ui/workspace/library_panel.py`
- Modify: `ui/workspace/item_list.py`
- Modify: `ui/workspace/toolbar.py`
- Modify: `ui/constants.py`
- Modify: `resources/themes/light.qss`
- Modify: `resources/themes/dark.qss`
- Modify: `resources/themes/theme_outline.json`
- Test: `tests/ui/test_workspace_widget.py`
- Test: `tests/unit/test_theme_outline_contract.py`

**Step 1: Write the failing test**

```python
def test_workspace_shell_exposes_tool_rail_explorer_and_document_stage(
    qapp, mock_i18n, workspace_manager
):
    widget = WorkspaceWidget(workspace_manager, mock_i18n)

    assert widget.tool_rail is not None
    assert widget.library_panel.explorer_header is not None
    assert widget.library_panel.item_list is not None
    assert widget.document_tabs is not None
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/ui/test_workspace_widget.py tests/unit/test_theme_outline_contract.py -k "tool_rail_explorer_and_document_stage" -v`
Expected: FAIL，因为当前工作台还没有局部工具轨，浏览区也没有新的 explorer/header 分层。

**Step 3: Write minimal implementation**

```python
class WorkspaceToolRail(QWidget):
    ...
```

实现要求：
- 工作台内部新增局部工具轨，但不复制应用全局导航。
- 浏览区拆成 explorer 层和内容列表层，支持更清晰的结构视图/事件视图切换。
- `WorkspaceToolbar` 只保留极少数高频动作，避免与工具轨重复实现。

**Step 4: Run test to verify it passes**

Run: `pytest tests/ui/test_workspace_widget.py tests/unit/test_theme_outline_contract.py -k "tool_rail_explorer_and_document_stage" -v`
Expected: PASS

**Step 5: Commit**

```bash
git add ui/workspace/tool_rail.py ui/workspace/widget.py ui/workspace/library_panel.py ui/workspace/item_list.py ui/workspace/toolbar.py ui/constants.py resources/themes/light.qss resources/themes/dark.qss resources/themes/theme_outline.json tests/ui/test_workspace_widget.py tests/unit/test_theme_outline_contract.py
git commit -m "feat: restructure workspace shell around note explorer"
```

### Task 5: 重构文档头部、资产切换与检查器，回到 note-first 编辑体验

**Files:**
- Modify: `ui/workspace/editor_panel.py`
- Modify: `ui/workspace/inspector_panel.py`
- Modify: `ui/workspace/recording_panel.py`
- Modify: `ui/workspace/detached_document_window.py`
- Modify: `ui/workspace/widget.py`
- Test: `tests/ui/test_workspace_widget.py`

**Step 1: Write the failing test**

```python
def test_workspace_editor_uses_asset_tabs_and_inspector_hosts_ai_actions(
    qapp, mock_i18n, workspace_manager
):
    widget = WorkspaceWidget(workspace_manager, mock_i18n)
    item = workspace_manager.list_items()[0]

    widget.open_item(item.id)

    assert widget.editor_panel.asset_tab_bar is not None
    assert widget.inspector_panel.ai_actions_section is not None
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/ui/test_workspace_widget.py -k "asset_tabs_and_inspector_hosts_ai_actions" -v`
Expected: FAIL，因为当前编辑器仍使用 `asset_selector`，AI 动作仍留在主工具栏，检查器也没有 AI section。

**Step 3: Write minimal implementation**

```python
class WorkspaceEditorPanel(TextEditorPanel):
    def _build_document_header(self) -> None:
        ...
```

实现要求：
- 用标签/chips 取代 `asset_selector` 作为主切换控件。
- 把 AI 生成动作从编辑主工具栏移到检查器卡片区。
- 文档头部明确展示标题、保存状态和来源摘要。
- 独立窗口沿用同一套文档头部与资产切换，不再只是裸编辑器。

**Step 4: Run test to verify it passes**

Run: `pytest tests/ui/test_workspace_widget.py -k "asset_tabs_and_inspector_hosts_ai_actions" -v`
Expected: PASS

**Step 5: Commit**

```bash
git add ui/workspace/editor_panel.py ui/workspace/inspector_panel.py ui/workspace/recording_panel.py ui/workspace/detached_document_window.py ui/workspace/widget.py tests/ui/test_workspace_widget.py
git commit -m "feat: align workspace editor with note-first workflow"
```

### Task 6: 清理陈旧文档、i18n、测试索引与结构说明

**Files:**
- Modify: `AGENTS.md`
- Modify: `docs/README.md`
- Modify: `ui/realtime_record/README.md`
- Modify: `resources/translations/i18n_outline.json`
- Modify: `resources/translations/zh_CN.json`
- Modify: `resources/translations/en_US.json`
- Modify: `resources/translations/fr_FR.json`
- Modify: `CHANGELOG.md`
- Test: `tests/unit/test_i18n_outline_contract.py`
- Test: `tests/unit/test_theme_outline_contract.py`

**Step 1: Write the failing test**

```python
def test_i18n_outline_covers_workspace_task_window_and_recording_console_copy():
    keys = load_i18n_outline_keys()

    assert "workspace.task_window_title" in keys
    assert "workspace.recording_console.section_capture" in keys
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_i18n_outline_contract.py tests/unit/test_theme_outline_contract.py -k "task_window_title or recording_console" -v`
Expected: FAIL，因为新的工具窗口与录音控制台文案、主题角色、结构说明尚未同步。

**Step 3: Write minimal implementation**

```json
{
  "workspace": {
    "task_window_title": "...",
    "recording_console": {
      "section_capture": "..."
    }
  }
}
```

实现要求：
- 按大纲驱动补齐所有 locale，不允许只更新单语种。
- `AGENTS.md` 与 `docs/README.md` 必须同步反映任务窗口和新的工作台职责边界。
- `CHANGELOG.md` 记录这次结构与体验收敛带来的维护性变化。

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_i18n_outline_contract.py tests/unit/test_theme_outline_contract.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add AGENTS.md docs/README.md ui/realtime_record/README.md resources/translations/i18n_outline.json resources/translations/zh_CN.json resources/translations/en_US.json resources/translations/fr_FR.json CHANGELOG.md tests/unit/test_i18n_outline_contract.py tests/unit/test_theme_outline_contract.py
git commit -m "docs: sync workspace polish architecture"
```

## 6. 验证清单

1. `pytest tests/unit/test_main_window_shell.py tests/ui/test_workspace_widget.py -v`
2. `pytest tests/ui/test_batch_task_item_roles.py -v`
3. `pytest tests/unit/test_theme_outline_contract.py tests/unit/test_i18n_outline_contract.py -v`
4. 手动验证：
   - 壳层任务按钮打开单实例工具窗口
   - 工作台主舞台不再被批量任务占据
   - 录音完整面板不再出现纵向堆砌
   - 文档主编辑区、检查器、资产切换和独立窗口体验保持一致

## 7. 外部参考

1. Obsidian Help, File explorer: `https://help.obsidian.md/plugins/file-explorer`
2. Obsidian Help, Workspaces: `https://help.obsidian.md/user-interface/workspaces`
3. Obsidian Help, Backlinks: `https://help.obsidian.md/plugins/backlinks`
4. Obsidian Help, Properties view: `https://help.obsidian.md/plugins/properties-view`
5. Apple Human Interface Guidelines, Sidebars: `https://developer.apple.com/design/human-interface-guidelines/sidebars`
6. Microsoft Learn, NavigationView: `https://learn.microsoft.com/en-us/windows/apps/develop/ui/controls/navigationview`
