# Workspace Experience Rearchitecture Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 用硬切换方式把当前“批量任务堆叠 + 简化录音控件 + 资产下拉编辑”重构为真正可长期使用的统一工作台：提供应用壳层级常驻录音底座、支持结构视图/事件视图切换的文档库、以及接近 Obsidian / Notes 的卡片式多文档编辑体验。

**Architecture:** 当前问题的本质不是单个控件缺失，而是工作台仍然在复用“旧页面碎片”的拼装结果，没有围绕“采集 -> 入库 -> 组织 -> 编辑 -> 整理 -> 回看”这条内容生命周期组织信息架构。本方案继续以 `workspace_items + workspace_assets` 为唯一事实源，并新增 `workspace_folders` 作为用户自定义文件结构层；录音入口上移到 `ui/main_window.py` 壳层底部，以“精简底座 + 常规展开面板”的双形态常驻界面，工作台本身则收敛为“库导航 + 卡片编辑区 + 检查器 + 任务抽屉”的主内容空间。

**Tech Stack:** Python 3.10+, PySide6, SQLite, QSS, `core/workspace/*`, `data/database/*`, `core/realtime/recorder.py`, `core/settings/manager.py`, `ui/main_window.py`, `ui/common/*`, `ui/workspace/*`, `ui/settings/*`, `tests/ui/*`, `tests/unit/*`.

---

**Assumption:** 假定后续实现会在独立 worktree/分支中进行；当前会话仅修订计划与文档，不直接改业务代码。

## 1. 审查结论

### 1.1 当前实现的真实问题

1. `ui/workspace/widget.py` 已经把 `task_panel + item_list + editor_panel + recording_control_panel + recording_panel` 塞进一个页面，但这只是物理合并，不是信息架构重构。
2. 录音入口仍是“页面局部控件”，不是像音乐播放应用那样的应用壳层级常驻底座，用户无法在任何时刻快速发起录音。
3. 工作台内的录音主控只有开始/停止，没有承接旧实时录音页已有的能力基线：输入源、增益、转写/翻译策略、marker、运行态预览、浮窗联动、错误提示、会话级参数确认。
4. `ui/settings/realtime_page.py` 保留完整设置，但当前工作流没有“精简默认启动”与“展开调整”的双形态闭环。
5. 内容库仍是扁平列表，缺少用户自定义文件结构、创建/删除/移动文件夹、结构化整理能力。
6. 系统虽然有事件来源字段，但没有“结构视图 / 事件视图”双视图切换，无法同时满足长期整理和回看录音/日历来源两类心智模型。
7. `ui/workspace/editor_panel.py` 虽然复用了 `TextEditorPanel`，但仍然是“资产下拉框 + 文本框 + 两个 AI 按钮”的技术型界面，不是面向笔记编辑的桌面体验。
8. 当前文档只能单实例聚焦，缺少卡片式多开、标签切换和独立窗口查看，无法支撑多文档并行整理。
9. `ui/batch_transcribe/transcript_viewer.py` 与 `ui/workspace/editor_panel.py` 仍共存，属于文本编辑逻辑双轨，违反 DRY。
10. `ui/realtime_record/README.md` 仍描述已退出主导航的完整实时录音页，文档已经落后于当前产品结构。

### 1.2 对应的产品判断

1. 工作台应该只有一个“主舞台”：内容库与文档编辑。
2. 录音是一级能力，但应以应用壳层底座常驻，而不是占用工作台主舞台。
3. 文档组织必须同时支持“用户主动整理”与“按事件回看”两种视图，且二者可相互切换。
4. 文本编辑应以“文档卡片/标签页”为中心，而不是以“某个 asset role 下拉切换”为中心。
5. 硬切换要求删除重复 viewer、重复入口和失效文档，而不是继续保留旧路径作为后门。

## 2. 产品目标与非目标

### 2.1 产品目标

1. 用户在任意主页面都能看到常驻录音底座，并可一键按默认设置启动录音。
2. 录音底座同时提供精简面板和常规面板：
   - 精简面板只承担开始/停止、基础状态、时长和当前目标信息。
   - 常规面板提供完整录音参数、实时预览、marker 和设置联动。
3. 文档库支持文件夹树管理，可创建、删除、重命名、移动文件夹与文档。
4. 文档库同时保留事件视图，可按录音/日历事件聚合查看内容，两视图之间可即时切换。
5. 编辑区支持卡片式多开、标签切换，并允许将单个文档独立窗口显示。
6. 任何转写/翻译/录音结果都必须落入统一内容库，并可再次编辑、整理和定位。

### 2.2 非目标

1. 不做向前兼容层，不保留旧页面双轨入口。
2. 不做数据迁移设计；初始化代码直接以新结构为准即可。
3. 不引入富文本/WYSIWYG 编辑器；首期坚持纯文本/Markdown 优先，避免过度工程化。
4. 不实现 Obsidian 式双链、图谱、插件系统等超范围能力。

## 3. 交互与信息架构决策

### 3.1 新的整体结构

1. 应用壳层底部：常驻录音底座
   - 参考音乐应用 mini player。
   - 所有主页面可见，不局限于工作台页。
   - 默认展示精简面板，支持展开为常规面板。
2. 左侧：双视图库导航
   - 顶部视图切换：`结构视图` / `事件视图`。
   - 结构视图显示文件夹树、文档列表、上下文菜单。
   - 事件视图按录音/日历事件、日期或来源分组查看。
3. 中央：卡片式编辑舞台
   - 顶部是打开文档标签条。
   - 当前文档显示标题、保存状态、正文编辑区与资产标签。
   - 支持关闭标签、切换标签、在新窗口打开当前文档。
4. 右侧：检查器
   - 展示来源信息、音频播放器、AI 操作、关联资产、文档属性。
   - 默认可折叠，无内容时不占大面积空白。
5. 底部辅助层：任务抽屉
   - 批量转写/转译队列改为抽屉。
   - 抽屉位于常驻录音底座之上，不与主编辑区争夺常驻空间。

### 3.2 参考最佳实践的落地边界

1. 参考 Notes：库导航、列表、文档主体层级清晰，文件夹组织与事件来源并存。
2. 参考 Obsidian：文件树、标签页、多开文档、独立窗口这些桌面能力可直接提升多文档整理效率。
3. 不照搬网页聊天工作区布局；EchoNote 的主对象仍然是“文档/会议资产”，不是“聊天线程”。

## 4. 文档组织与编辑体验要求

### 4.1 文档组织要求

1. 新增用户可管理的文件夹层级，至少支持：
   - 创建文件夹
   - 删除空文件夹
   - 重命名文件夹
   - 移动文档到文件夹
   - 拖拽或命令式移动文档/文件夹
2. 结构视图与事件视图共存：
   - 结构视图用于长期整理。
   - 事件视图用于回看录音/日历来源。
   - 任一文档在两种视图中都能定位到同一 `workspace_item`。
3. 事件视图不复制第二套数据结构，只是对统一资产层的另一种查询与分组方式。

### 4.2 编辑体验要求

1. 编辑对象首先是 document/note，而不是 asset role。
2. 标题与正文分离，标题直接持久化到 `workspace_items.title`。
3. 资产切换改为稳定顺序的 tabs/chips，不再使用技术味很重的下拉框。
4. 打开文档以卡片/标签页形式管理，支持：
   - 同时打开多个文档
   - 关闭当前文档
   - 保持最近打开顺序
   - 将当前文档在新窗口中打开
5. 保存状态明确：
   - 显示“已保存 / 保存中 / 保存失败”。
   - 支持自动保存（短 debounce）与显式保存按钮并存，但只保留一套保存逻辑。
6. 搜索、复制、导出、切换资产都围绕同一个编辑器实现，不再复制 viewer。
7. 对大文本保持只读切换、滚动位置和选中位置稳定，避免频繁重建 `QTextEdit` 状态。
8. AI 生成按钮移入检查器或次级区，主工具栏只保留高频编辑动作。

## 5. 录音底座与会话能力要求

1. 录音入口上移到应用壳层，形成全局常驻录音底座。
2. 精简面板必须始终可见，至少包括：
   - 开始/停止
   - 当前状态
   - 时长
   - 当前输入/目标摘要
   - 展开常规面板按钮
3. 常规面板至少包括：
   - 输入源
   - 增益
   - 是否转写
   - 是否翻译
   - 翻译目标语言
   - 保存录音
   - 保存转写
   - 创建日历事件
   - 实时转写预览
   - 实时翻译预览
   - marker 列表与新增 marker
   - 打开/关闭浮窗
4. 精简面板应默认直接用设置默认值启动，不要求用户每次先进入常规面板。
5. 常规面板必须直接消费 `SettingsManager.get_realtime_preferences()` 与共享翻译默认值，不复制设置逻辑。
6. “更多设置”从常规面板直接跳到 `settings -> realtime`。
7. 录音结束后自动定位到生成的 `workspace_item`，并能在结构视图和事件视图中找到。

## 6. 技术与清理决策

1. 新增 `workspace_folders` 持久化层，承载文件夹树结构；`workspace_items` 持有可选 `folder_id`。
2. 事件视图继续依赖 `workspace_items.source_event_id` 与来源元数据，不新增第二套长期内容表。
3. 常驻录音底座放在 `ui/main_window.py` 壳层，而不是 `ui/workspace/widget.py` 局部区域。
4. 常规录音面板与精简底座必须共享同一录音状态机，继续复用 `RealtimeRecorder`。
5. 删除或停用重复文本查看路径，统一收口到 workspace 编辑器体系。
6. 批量任务查看动作不再弹 `TranscriptViewerDialog`，而是路由到工作台文档卡片。
7. 旧实时录音整页文档要改成“浮窗与可复用组件说明”，不能继续描述主页面入口。
8. 所有 asset label、集合类型、视图模式、会话状态常量应集中定义，禁止散落硬编码。

## 7. 关键假设与建议

1. 假设：首期文本编辑继续基于 `QTextEdit`，不引入 Markdown AST 编辑器。
   - 理由：当前已有复用基础，重构重点是结构与交互，不是重写编辑器内核。
2. 假设：多窗口能力首期只要求“当前文档独立窗口显示”，不做任意拖拽标签跨窗口全量工作区同步。
   - 理由：满足核心桌面体验即可，避免把问题升级为复杂窗口管理系统。
3. 假设：事件视图是查询视图，不改变文档的真实归属文件夹。
   - 理由：否则“按结构整理”和“按事件回看”会互相污染。
4. 建议：任务抽屉与录音底座分层实现，底座常驻，任务抽屉按需展开。
   - 理由：二者都是辅助工作流，但录音入口的触达优先级高于任务队列。

## 8. 实施顺序总览

1. 先重构应用壳层与工作台壳层，建立常驻录音底座和新工作台主布局。
2. 再补齐文件夹树与结构视图/事件视图双视图。
3. 再升级编辑器为卡片式多开，并补独立窗口。
4. 然后补齐录音底座的精简/常规双形态与设置联动。
5. 最后清理重复 viewer、陈旧文档、i18n、主题角色与回归测试。

### Task 1: 重构应用壳层与工作台壳层，建立常驻录音底座骨架

**Files:**
- Create: `ui/common/realtime_recording_dock.py`
- Create: `ui/workspace/library_panel.py`
- Create: `ui/workspace/inspector_panel.py`
- Modify: `ui/main_window.py`
- Modify: `ui/workspace/widget.py`
- Modify: `ui/constants.py`
- Test: `tests/ui/test_workspace_widget.py`
- Test: `tests/unit/test_main_window_shell.py`

**Step 1: Write the failing test**

```python
def test_main_window_exposes_persistent_recording_dock_and_workspace_shell(
    qapp, mock_i18n
):
    main_window = build_main_window_with_workspace()

    assert main_window.recording_dock is not None
    assert main_window.recording_dock.isVisible()
    assert main_window.pages["workspace"].library_panel is not None
    assert main_window.pages["workspace"].inspector_panel is not None
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_main_window_shell.py tests/ui/test_workspace_widget.py -k "recording_dock or workspace_shell" -v`
Expected: FAIL，因为当前录音入口仍在 workspace 局部，且工作台仍是旧拼装布局。

**Step 3: Write minimal implementation**

```python
class RealtimeRecordingDock(QWidget):
    ...
```

实现要求：
- 在 `ui/main_window.py` 壳层底部加入常驻录音底座。
- 工作台页只保留内容编辑相关区域，不再常驻一整列录音空白区。
- 任务抽屉设计预留在底座之上，不与底座混写。

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_main_window_shell.py tests/ui/test_workspace_widget.py -k "recording_dock or workspace_shell" -v`
Expected: PASS

**Step 5: Commit**

```bash
git add ui/common/realtime_recording_dock.py ui/workspace/library_panel.py ui/workspace/inspector_panel.py ui/main_window.py ui/workspace/widget.py ui/constants.py tests/unit/test_main_window_shell.py tests/ui/test_workspace_widget.py
git commit -m "feat: add persistent recording dock shell"
```

### Task 2: 新增文件夹树持久化，并支持结构视图 / 事件视图双视图

**Files:**
- Modify: `data/database/schema.sql`
- Modify: `data/database/models.py`
- Modify: `core/workspace/manager.py`
- Modify: `ui/workspace/library_panel.py`
- Modify: `ui/workspace/item_list.py`
- Test: `tests/unit/data/test_database_models.py`
- Test: `tests/unit/core/test_workspace_manager.py`
- Test: `tests/ui/test_workspace_widget.py`

**Step 1: Write the failing test**

```python
def test_workspace_manager_supports_folders_and_dual_library_views(tmp_path):
    manager = build_workspace_manager(tmp_path)
    folder_id = manager.create_folder("Projects")
    note_id = manager.create_note(title="Plan")
    manager.move_item_to_folder(note_id, folder_id)

    structure_items = manager.list_items(view_mode="structure", folder_id=folder_id)
    event_items = manager.list_items(view_mode="event")

    assert [item.id for item in structure_items] == [note_id]
    assert event_items is not None
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/data/test_database_models.py tests/unit/core/test_workspace_manager.py -k "folder or dual_library_views" -v`
Expected: FAIL，因为当前没有文件夹持久化层，也没有视图模式参数。

**Step 3: Write minimal implementation**

```python
class WorkspaceFolder:
    ...

def list_items(self, *, view_mode: str = "structure", folder_id: str | None = None, ...):
    ...
```

实现要求：
- 新增 `workspace_folders` 表与对应模型。
- 支持创建、删除、重命名文件夹，以及把文档移动到文件夹。
- 结构视图与事件视图共享同一套 item/asset 数据，不复制第二套持久化结构。

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/data/test_database_models.py tests/unit/core/test_workspace_manager.py tests/ui/test_workspace_widget.py -k "folder or dual_library_views or structure_view or event_view" -v`
Expected: PASS

**Step 5: Commit**

```bash
git add data/database/schema.sql data/database/models.py core/workspace/manager.py ui/workspace/library_panel.py ui/workspace/item_list.py tests/unit/data/test_database_models.py tests/unit/core/test_workspace_manager.py tests/ui/test_workspace_widget.py
git commit -m "feat: add workspace folders and dual library views"
```

### Task 3: 把编辑器升级为卡片式多开，并支持独立窗口显示

**Files:**
- Create: `ui/workspace/detached_document_window.py`
- Modify: `ui/workspace/editor_panel.py`
- Modify: `ui/workspace/widget.py`
- Modify: `core/workspace/manager.py`
- Test: `tests/ui/test_workspace_widget.py`

**Step 1: Write the failing test**

```python
def test_workspace_supports_document_tabs_and_detached_window(
    qapp, mock_i18n, workspace_manager
):
    widget = WorkspaceWidget(workspace_manager, mock_i18n)
    first_id, second_id = [item.id for item in workspace_manager.list_items()[:2]]

    widget.open_item(first_id)
    widget.open_item(second_id)

    assert widget.document_tabs.count() == 2
    assert widget.open_current_item_in_window_action is not None
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/ui/test_workspace_widget.py::test_workspace_supports_document_tabs_and_detached_window -v`
Expected: FAIL，因为当前工作台没有标签页和独立窗口能力。

**Step 3: Write minimal implementation**

```python
class DetachedDocumentWindow(QWidget):
    ...
```

实现要求：
- 工作台顶部提供轻量标签条，用于多文档并行切换。
- 当前文档可在独立窗口中打开，但仍复用同一套编辑器与保存逻辑。
- 标签页能力服务于编辑效率，不引入复杂的 IDE 式窗口管理。

**Step 4: Run test to verify it passes**

Run: `pytest tests/ui/test_workspace_widget.py -k "document_tabs or detached_window" -v`
Expected: PASS

**Step 5: Commit**

```bash
git add ui/workspace/detached_document_window.py ui/workspace/editor_panel.py ui/workspace/widget.py core/workspace/manager.py tests/ui/test_workspace_widget.py
git commit -m "feat: add workspace document tabs and detached window"
```

### Task 4: 构建常驻录音底座的精简 / 常规双形态

**Files:**
- Modify: `ui/common/realtime_recording_dock.py`
- Create: `ui/workspace/recording_session_panel.py`
- Modify: `core/realtime/recorder.py`
- Modify: `core/settings/manager.py`
- Test: `tests/ui/test_workspace_widget.py`
- Test: `tests/unit/core/test_realtime_recorder.py`
- Test: `tests/unit/test_main_window_shell.py`

**Step 1: Write the failing test**

```python
def test_recording_dock_supports_compact_and_full_modes(
    qapp, mock_i18n, mock_realtime_recorder
):
    dock = RealtimeRecordingDock(mock_realtime_recorder, mock_i18n)

    assert dock.compact_panel.start_button.isVisible()
    assert dock.compact_panel.stop_button.isVisible()
    assert dock.expand_button.isVisible()

    dock.expand_button.click()

    assert dock.full_panel.input_source_combo is not None
    assert dock.full_panel.marker_button.isVisible()
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_main_window_shell.py tests/ui/test_workspace_widget.py tests/unit/core/test_realtime_recorder.py -k "compact_and_full_modes or recording_dock" -v`
Expected: FAIL，因为当前没有常驻底座，更没有精简/常规双形态。

**Step 3: Write minimal implementation**

```python
class RealtimeRecordingDock(QWidget):
    def set_expanded(self, expanded: bool) -> None:
        ...
```

实现要求：
- 精简面板始终可见，支持直接按默认设置启动录音。
- 常规面板展开后提供完整录音参数和实时预览。
- 精简面板与常规面板共享同一个 `RealtimeRecorder` 实例与状态。

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_main_window_shell.py tests/ui/test_workspace_widget.py tests/unit/core/test_realtime_recorder.py -k "recording_dock or compact_and_full_modes" -v`
Expected: PASS

**Step 5: Commit**

```bash
git add ui/common/realtime_recording_dock.py ui/workspace/recording_session_panel.py core/realtime/recorder.py core/settings/manager.py tests/unit/test_main_window_shell.py tests/ui/test_workspace_widget.py tests/unit/core/test_realtime_recorder.py
git commit -m "feat: add compact and full recording dock modes"
```

### Task 5: 收敛录音默认值、常规面板设置与工作台定位逻辑

**Files:**
- Modify: `ui/settings/realtime_page.py`
- Modify: `ui/common/realtime_recording_dock.py`
- Modify: `ui/workspace/recording_session_panel.py`
- Modify: `ui/main_window.py`
- Test: `tests/ui/test_realtime_settings_page.py`
- Test: `tests/ui/test_workspace_widget.py`

**Step 1: Write the failing test**

```python
def test_recording_dock_compact_mode_uses_defaults_and_full_mode_routes_to_settings(
    qapp, mock_i18n, workspace_manager
):
    main_window = build_main_window_with_workspace()

    main_window.recording_dock.compact_panel.start_button.click()
    main_window.recording_dock.full_panel.more_settings_button.click()

    assert main_window.current_page_name == "settings"
    assert main_window.pages["settings"].current_page_id() == "realtime"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/ui/test_realtime_settings_page.py tests/ui/test_workspace_widget.py -k "compact_mode_uses_defaults or more_settings" -v`
Expected: FAIL，因为当前没有“默认值直启 + 常规面板跳转设置页”的闭环。

**Step 3: Write minimal implementation**

```python
def build_realtime_session_options(self, *, quick_start: bool = False) -> dict:
    ...
```

实现要求：
- 精简面板直接使用默认配置，不重复要求用户确认。
- 常规面板通过共享的偏好解析函数生成会话启动参数。
- 录音结束后自动定位到对应 `workspace_item`，并优先在当前工作台打开。

**Step 4: Run test to verify it passes**

Run: `pytest tests/ui/test_realtime_settings_page.py tests/ui/test_workspace_widget.py -k "quick_start or more_settings or workspace_item" -v`
Expected: PASS

**Step 5: Commit**

```bash
git add ui/settings/realtime_page.py ui/common/realtime_recording_dock.py ui/workspace/recording_session_panel.py ui/main_window.py tests/ui/test_realtime_settings_page.py tests/ui/test_workspace_widget.py
git commit -m "feat: unify recording dock defaults and settings routing"
```

### Task 6: 将批量任务区改为抽屉，并删除重复文本查看器路径

**Files:**
- Modify: `ui/workspace/task_panel.py`
- Modify: `ui/workspace/widget.py`
- Delete: `ui/batch_transcribe/transcript_viewer.py`
- Modify: `ui/batch_transcribe/task_item.py`
- Modify: `ui/main_window.py`
- Test: `tests/ui/test_workspace_widget.py`
- Test: `tests/unit/test_main_window_search.py`

**Step 1: Write the failing test**

```python
def test_workspace_task_view_action_routes_to_open_document_card(
    qapp, mock_i18n, workspace_manager, transcription_manager
):
    main_window = build_main_window_with_workspace(transcription_manager=transcription_manager)
    workspace = main_window.pages["workspace"]

    workspace.task_panel.task_items[0].view_clicked.emit("task-1")

    assert main_window.current_page_name == "workspace"
    assert workspace.document_tabs.count() >= 1
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/ui/test_workspace_widget.py tests/unit/test_main_window_search.py -k "task_view_action_routes_to_open_document_card" -v`
Expected: FAIL，因为当前批量任务仍依赖旧 `TranscriptViewerDialog` 路径。

**Step 3: Write minimal implementation**

```python
class WorkspaceTaskPanel(BaseWidget):
    def _on_view_task_requested(self, task_id: str) -> None:
        ...
```

实现要求：
- 任务列表默认收进录音底座之上的抽屉。
- 查看任务直接定位到 workspace 文档卡片，不再弹独立 viewer。
- 删除 `ui/batch_transcribe/transcript_viewer.py` 后，所有引用同步清理，避免残留死代码。

**Step 4: Run test to verify it passes**

Run: `pytest tests/ui/test_workspace_widget.py tests/unit/test_main_window_search.py -k "task_view or document_card or task_drawer" -v`
Expected: PASS

**Step 5: Commit**

```bash
git add ui/workspace/task_panel.py ui/workspace/widget.py ui/batch_transcribe/task_item.py ui/main_window.py tests/ui/test_workspace_widget.py tests/unit/test_main_window_search.py
git rm ui/batch_transcribe/transcript_viewer.py
git commit -m "refactor: route batch tasks into workspace document cards"
```

### Task 7: 扩大所有查看入口到工作台，并让结构视图 / 事件视图都可定位资产

**Files:**
- Modify: `ui/timeline/widget.py`
- Modify: `ui/calendar_hub/widget.py`
- Modify: `ui/workspace/library_panel.py`
- Modify: `ui/workspace/widget.py`
- Modify: `ui/workspace/inspector_panel.py`
- Test: `tests/ui/test_timeline_widget_delete.py`
- Test: `tests/ui/test_calendar_hub_widget.py`
- Test: `tests/ui/test_timeline_audio_player.py`

**Step 1: Write the failing test**

```python
def test_event_entry_routes_to_workspace_event_view_and_focuses_asset(
    qapp, mock_i18n
):
    main_window = build_main_window_with_workspace()
    event_id = seed_event_with_workspace_assets(main_window)

    main_window.pages["timeline"]._on_view_transcript(event_id=event_id)

    assert main_window.current_page_name == "workspace"
    assert main_window.pages["workspace"].library_panel.current_view_mode() == "event"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/ui/test_timeline_widget_delete.py tests/ui/test_calendar_hub_widget.py tests/ui/test_timeline_audio_player.py -k "event_view and workspace" -v`
Expected: FAIL，因为当前工作台还没有事件视图，也不能按视图模式精准定位。

**Step 3: Write minimal implementation**

```python
def open_item(self, item_id: str, asset_role: str | None = None, view_mode: str | None = None) -> bool:
    ...
```

实现要求：
- 从时间线/日历/录音结束进入工作台时，优先切到事件视图并定位到对应条目。
- 用户手动整理文档时，仍可切回结构视图继续管理文件夹。
- transcript / translation / summary / meeting_brief / audio 都通过统一工作台定位。

**Step 4: Run test to verify it passes**

Run: `pytest tests/ui/test_timeline_widget_delete.py tests/ui/test_calendar_hub_widget.py tests/ui/test_timeline_audio_player.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add ui/timeline/widget.py ui/calendar_hub/widget.py ui/workspace/library_panel.py ui/workspace/widget.py ui/workspace/inspector_panel.py tests/ui/test_timeline_widget_delete.py tests/ui/test_calendar_hub_widget.py tests/ui/test_timeline_audio_player.py
git commit -m "feat: route artifacts into structure and event workspace views"
```

### Task 8: 文档、i18n、主题契约与陈旧实现清理收口

**Files:**
- Modify: `AGENTS.md`
- Modify: `docs/README.md`
- Modify: `ui/realtime_record/README.md`
- Modify: `resources/translations/i18n_outline.json`
- Modify: `resources/translations/zh_CN.json`
- Modify: `resources/translations/en_US.json`
- Modify: `resources/translations/fr_FR.json`
- Modify: `resources/themes/theme_outline.json`
- Test: `tests/unit/test_i18n_outline_contract.py`
- Test: `tests/unit/test_theme_outline_contract.py`

**Step 1: Write the failing test**

```python
def test_theme_outline_covers_recording_dock_and_document_tab_roles():
    ...

def test_all_locales_have_dual_view_and_detached_window_keys():
    ...
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_i18n_outline_contract.py tests/unit/test_theme_outline_contract.py -v`
Expected: FAIL，因为常驻录音底座、双视图、文档标签和独立窗口新增的 role/key 尚未同步到契约文件与多语言文案。

**Step 3: Write minimal implementation**

```json
{
  "workspace": {
    "structure_view": "...",
    "event_view": "...",
    "open_in_new_window": "..."
  }
}
```

实现要求：
- `AGENTS.md`、`docs/README.md`、`ui/realtime_record/README.md` 同步反映新壳层与工作台结构。
- 主题 role 与 i18n key 全部走契约更新，禁止只改 UI 不补 outline。
- 清理陈旧 README 中对旧实时录音主页面和旧 viewer 路径的描述。

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_i18n_outline_contract.py tests/unit/test_theme_outline_contract.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add AGENTS.md docs/README.md ui/realtime_record/README.md resources/translations/i18n_outline.json resources/translations/zh_CN.json resources/translations/en_US.json resources/translations/fr_FR.json resources/themes/theme_outline.json tests/unit/test_i18n_outline_contract.py tests/unit/test_theme_outline_contract.py
git commit -m "docs: sync workspace rearchitecture shell and dual-view contracts"
```

## 9. 执行验证清单

1. `pytest tests/unit/test_main_window_shell.py -v`
2. `pytest tests/ui/test_workspace_widget.py -v`
3. `pytest tests/ui/test_realtime_settings_page.py -v`
4. `pytest tests/ui/test_calendar_hub_widget.py tests/ui/test_timeline_widget_delete.py tests/ui/test_timeline_audio_player.py -v`
5. `pytest tests/unit/data/test_database_models.py tests/unit/core/test_workspace_manager.py tests/unit/core/test_realtime_recorder.py -v`
6. `pytest tests/unit/test_main_window_search.py -v`
7. `pytest tests/unit/test_i18n_outline_contract.py tests/unit/test_theme_outline_contract.py -v`

## 10. 完成定义

1. 应用壳层底部存在常驻录音底座，且支持精简/常规双形态。
2. 工作台内容库支持文件夹树与事件视图双视图，并能相互切换。
3. 编辑区支持卡片式多开与独立窗口，且仍只有一套保存逻辑。
4. 批量任务、时间线、日历、录音结果都能路由到统一工作台，而不是弹旧 viewer。
5. 陈旧文档与契约文件同步完成，仓库内不存在与新结构冲突的说明。
