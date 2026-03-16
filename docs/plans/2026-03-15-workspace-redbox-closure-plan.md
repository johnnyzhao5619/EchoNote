# Workspace Red-Box Closure Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 用硬切换方式一次性收口工作台截图红框 1-4 的问题：重构左侧导航信息架构、明确结构视图与事件视图职责、建立“事件文件夹 / 批量任务文件夹 + 来源关联”双轨语义，并把右侧录音预览升级为可发布的侧栏播放器。

**Architecture:** 保持 `core/workspace/` 作为唯一资产层，不新增第二套文档、事件、任务或播放器数据流。本次改造直接删除当前分散的 `WorkspaceToolbar` / `WorkspaceToolRail` 式入口，把工作台重构为 “Navigator + Results + Editor + Inspector” 四区结构；事件归档和批量任务归档都通过 workspace folder 系统语义承载，来源关联继续由 `source_event_id`、`source_task_id` 和原始资产路径承载，结构归属与来源关联明确解耦。录音预览复用 `/Users/weijiazhao/Dev/EchoNote/ui/common/audio_player.py` 的 transport 能力，只扩展 inspector 呈现层，禁止再造一套播放逻辑。

**Tech Stack:** Python 3.12, PySide6, SQLite, QSS, i18n JSON, `/Users/weijiazhao/Dev/EchoNote/core/workspace/*`, `/Users/weijiazhao/Dev/EchoNote/data/database/*`, `/Users/weijiazhao/Dev/EchoNote/ui/workspace/*`, `/Users/weijiazhao/Dev/EchoNote/ui/common/audio_player.py`, `/Users/weijiazhao/Dev/EchoNote/tests/unit/*`, `/Users/weijiazhao/Dev/EchoNote/tests/ui/*`.

---

**Assumption:** 后续执行在独立 worktree / 分支中完成；当前变更只新增实施计划与文档导航，不直接修改业务代码。

## 1. 审查结论

### 1.1 红框问题与真实根因

1. 红框 1 不是单纯间距问题，而是 `/Users/weijiazhao/Dev/EchoNote/ui/workspace/widget.py` 同时挂了 `/Users/weijiazhao/Dev/EchoNote/ui/workspace/toolbar.py`、`/Users/weijiazhao/Dev/EchoNote/ui/workspace/tool_rail.py`、`/Users/weijiazhao/Dev/EchoNote/ui/workspace/library_panel.py` 三套左侧入口，导致“创建动作 / 视图切换 / 导航树”分属不同容器，视觉和职责都不闭环。
2. 红框 2 当前本质上是 folder tree，但它只在 `structure` 模式下显示文件夹控制，在 `event` 模式下只是被动隐藏控件，既不是 Obsidian 式的文件导航器，也不是事件导航器，目的不清晰，设计不合理。
3. 红框 3 当前由 `/Users/weijiazhao/Dev/EchoNote/ui/workspace/item_list.py` 用 `QListWidget + setItemWidget()` 临时拼装，`event` 视图只是排序规则变化，不是真正的事件分组列表；再加上当前行高和卡片容器没有稳定约束，最终出现内容显示不全和堆叠。
4. 红框 4 当前的 `/Users/weijiazhao/Dev/EchoNote/ui/workspace/recording_panel.py` 只是把 `AudioPlayer` 藏在占位文案后面，右侧检查器也只做了最小堆叠，所以用户看到的是“空白容器 + 元数据标签”，不是播放器。
5. 事件文档当前只有 `/Users/weijiazhao/Dev/EchoNote/data/database/models.py` 中的 `WorkspaceItem.source_event_id` 这一条关联事实，没有“事件文件夹”结构语义，所以无法满足“默认归到事件文件夹，但移动后仍保持事件关联”的需求。
6. 批量任务产物当前虽然有 `WorkspaceItem.source_task_id`，但没有“批量任务”系统文件夹语义，也没有把“结构归属”与“原任务/原文件关联”明确拆开，因此无法稳定满足“默认归到批量任务文件夹，但用户移动后仍保持关联”的需求。

### 1.2 当前实现中最重要的复用机会

1. `/Users/weijiazhao/Dev/EchoNote/ui/common/audio_player.py` 已经具备播放/暂停、10 秒快进快退、拖动进度、音量/静音、时间显示和文本面板联动能力，右侧录音预览不应该重写播放器，只应该重做 inspector 呈现。
2. `/Users/weijiazhao/Dev/EchoNote/core/workspace/manager.py` 已经统一承载导入、录音发布、事件资产发布和 item/asset 读写，事件归档逻辑必须也收口在这里，不能分散到 `timeline`、`calendar`、`task_panel` 各自拼接。
3. 当前的左侧入口存在 DRY 债务：创建动作在 toolbar，视图切换在 tool rail，文件夹上下文在 library panel，导致一个简单的“切换工作台上下文”被拆成三块实现。
4. 当前批量任务的来源关联也不够产品化：`source_task_id` 已存在，但没有被提升为用户可理解的结构规则和 inspector 信息，结果是数据层有来源、界面层没有语义。

## 2. 产品目标与边界

### 2.1 目标

1. 左侧上半区硬切换为单一 navigator shell，统一承载创建动作、结构/事件模式切换、导航树和上下文摘要，消除重叠与布局割裂。
2. 重新定义红框 2 的职责为 Navigator，而不是“半成品文件夹树”：
   - `structure` 模式：像 Obsidian 文件浏览器一样承载工作台结构导航。
   - `event` 模式：承载按事件分组的导航入口，而不是简单换一种排序。
3. 事件产生的文档默认进入“事件”系统根目录下对应事件文件夹，但 `folder_id` 与 `source_event_id` 必须是两条独立事实；移动文档到别的文件夹后，事件关系依然成立。
4. 批量任务对应的转写/翻译文档默认进入“批量任务”系统根目录下，但 `folder_id` 与 `source_task_id`、原始文件资产关联必须是独立事实；移动文档到别的文件夹后，任务关联和原文件关联依然成立。
5. 红框 3 改为稳定的结果列表，支持完整标题、来源、更新时间、音频/文本状态、事件/任务关联标识，不再出现内容裁切和堆叠。
6. 红框 4 改为侧栏播放器卡片，视觉参考 VLC / Apple Music 的 transport 心智，至少支持播放、暂停、快退、快进、拖动进度、静音/音量调节，并保持空态、元数据和 AI 操作分层。

### 2.2 非目标

1. 不实现 Obsidian 的插件系统、双链、图谱、Canvas。
2. 不保留旧的 `WorkspaceToolbar` / `WorkspaceToolRail` 并行方案。
3. 不设计任何向前兼容或迁移逻辑；数据库和初始化代码允许直接硬切换。
4. 不新造第二套播放器或第二套事件资产模型。
5. 不为“原文件关联”额外引入第三套弱引用临时表；优先复用 `source_task_id` 与现有资产事实，只有在实现阶段确认必须表达 item-to-item 关系时，才升级为显式字段。

## 3. 关键架构决策

### 3.1 左侧信息架构

1. 直接移除 `/Users/weijiazhao/Dev/EchoNote/ui/workspace/toolbar.py` 在工作台主体中的独立横条，把导入文档 / 新建笔记动作内聚进 `WorkspaceLibraryPanel` 顶部 header action cluster。
2. 直接移除 `/Users/weijiazhao/Dev/EchoNote/ui/workspace/tool_rail.py` 的独立竖条，把结构视图 / 事件视图切换收成 header 内的 segmented control，避免三套左侧控件同时占位。
3. `/Users/weijiazhao/Dev/EchoNote/ui/workspace/widget.py` 的主布局固定为三列：
   - 左列：Navigator + Results
   - 中列：Tab editor stage
   - 右列：Inspector

### 3.2 红框 2 的新职责定义

1. 红框 2 未来只承担“导航上下文”：
   - 在 `structure` 模式展示用户文件夹树和系统“事件”根目录。
   - 在 `event` 模式展示事件导航树，例如“今天 / 即将到来 / 历史”或按月份分组的事件节点。
2. Navigator 不直接展示正文内容；正文内容始终下沉到红框 3 的 results list 和中间 editor stage。
3. 这与 Obsidian 的借鉴点一致：左侧面板负责定位文档，上下文操作不与正文编辑混写。

### 3.3 事件文件夹与事件关联解耦

1. 在 `/Users/weijiazhao/Dev/EchoNote/data/database/schema.sql` 和 `/Users/weijiazhao/Dev/EchoNote/data/database/models.py` 中给 `workspace_folders` 增加系统语义字段：
   - `folder_kind`，至少区分 `user`、`system_root`、`event`、`batch_task`
   - `source_event_id`，仅 event folder 使用
2. 在 `/Users/weijiazhao/Dev/EchoNote/core/workspace/manager.py` 建立单一入口：
   - `ensure_event_root_folder()`
   - `ensure_event_folder(event_id)`
   - `resolve_default_folder_for_event(event_id)`
   - `ensure_batch_task_root_folder()`
   - `resolve_default_folder_for_batch_task(task_id)`
3. `WorkspaceItem.folder_id` 表示当前结构归属；`WorkspaceItem.source_event_id` / `WorkspaceItem.source_task_id` 表示来源关联。移动 item 时只更新 `folder_id`，除非用户明确执行“解除来源关联”，否则不能清空 `source_event_id` 或 `source_task_id`。
4. 批量任务“原文件关联”默认基于现有事实承载：
   - 转写任务优先使用 `source_task_id + audio asset.file_path`
   - 翻译任务优先使用 `source_task_id + text asset.file_path`
   - inspector 和结果列表要把这层关联显式展示为“来源任务 / 原文件”
5. 所有事件来源和批量任务来源创建路径必须走同一 helper，包括：
   - `publish_transcription_task(...)`
   - `publish_recording_session(...)`
   - `publish_event_text_asset(...)`
   - `create_note(..., event_id=...)`（新增签名）

### 3.4 右侧播放器的实现原则

1. `/Users/weijiazhao/Dev/EchoNote/ui/common/audio_player.py` 继续是唯一 transport 逻辑所有者。
2. `/Users/weijiazhao/Dev/EchoNote/ui/workspace/recording_panel.py` 只负责 inspector 场景的数据绑定和空态，不复制播放按钮、seek、volume 逻辑。
3. 若现有 `AudioPlayer` 的 dialog 样式不适合 inspector，优先通过以下方式扩展：
   - 新增 `presentation="dialog" | "inspector"` 参数
   - 新增专用 role / size token
   - 默认在 inspector 模式折叠 transcript panel
4. 右侧 inspector 的信息层级固定为：
   - AI 操作
   - 录音预览播放器
   - 条目信息 / 事件关联

## 4. 实施顺序总览

1. 先打通事件文件夹和批量任务文件夹领域模型，避免 UI 先做完后再返工数据层。
2. 再重构左侧 navigator shell，解决红框 1 和 2 的根因。
3. 然后替换结果列表实现，解决红框 3 的堆叠和事件视图语义问题。
4. 最后收右侧播放器和 inspector，解决红框 4，并同步 theme / i18n / docs / tests。

### Task 1: 建立事件文件夹 / 批量任务文件夹领域模型并删除旧的临时 schema 兜底

**Files:**
- Modify: `/Users/weijiazhao/Dev/EchoNote/data/database/schema.sql`
- Modify: `/Users/weijiazhao/Dev/EchoNote/data/database/connection.py`
- Modify: `/Users/weijiazhao/Dev/EchoNote/data/database/models.py`
- Modify: `/Users/weijiazhao/Dev/EchoNote/core/workspace/manager.py`
- Test: `/Users/weijiazhao/Dev/EchoNote/tests/unit/core/test_workspace_manager.py`

**Step 1: Write the failing test**

```python
def test_event_linked_items_default_into_event_folder_but_keep_link_after_move(tmp_path):
    manager = build_workspace_manager(tmp_path)
    event = CalendarEvent(
        title="Design Review",
        start_time="2026-03-15T09:00:00+00:00",
        end_time="2026-03-15T10:00:00+00:00",
    )
    event.save(manager.db)

    item_id = manager.create_note(title="Review Notes", event_id=event.id)
    item = manager.get_item(item_id)
    event_folder = manager.get_folder(item.folder_id)

    assert event_folder is not None
    assert event_folder.folder_kind == "event"
    assert event_folder.source_event_id == event.id

    archive_folder_id = manager.create_folder("Archive")
    manager.move_item_to_folder(item_id, archive_folder_id)
    moved = manager.get_item(item_id)

    assert moved.folder_id == archive_folder_id
    assert moved.source_event_id == event.id


def test_batch_task_items_default_into_batch_folder_but_keep_task_link_after_move(tmp_path):
    manager = build_workspace_manager(tmp_path)
    task = SimpleNamespace(
        id="task-1",
        file_path=str(tmp_path / "meeting.wav"),
        file_name="meeting.wav",
        status="completed",
    )
    Path(task.file_path).write_bytes(b"RIFF")
    transcript_path = tmp_path / "meeting.md"
    transcript_path.write_text("hello", encoding="utf-8")

    item_id = manager.publish_transcription_task(task, transcript_path=str(transcript_path))
    item = manager.get_item(item_id)
    batch_folder = manager.get_folder(item.folder_id)

    assert batch_folder is not None
    assert batch_folder.folder_kind == "batch_task"
    assert item.source_task_id == "task-1"

    archive_folder_id = manager.create_folder("Archive")
    manager.move_item_to_folder(item_id, archive_folder_id)
    moved = manager.get_item(item_id)

    assert moved.folder_id == archive_folder_id
    assert moved.source_task_id == "task-1"
```

**Step 2: Run test to verify it fails**

Run: `pytest /Users/weijiazhao/Dev/EchoNote/tests/unit/core/test_workspace_manager.py::test_event_linked_items_default_into_event_folder_but_keep_link_after_move -v`

Expected: FAIL，因为当前 `create_note()` 不支持 `event_id`，`publish_transcription_task()` 也不会默认指向“批量任务”系统文件夹，`workspace_folders` 还没有 `folder_kind` / `source_event_id` 语义。

**Step 3: Write minimal implementation**

```python
class WorkspaceFolder:
    folder_kind: str = "user"
    source_event_id: Optional[str] = None
```

实现要求：
- 在 `schema.sql` 中直接加入 `workspace_folders.folder_kind` 和 `workspace_folders.source_event_id`。
- 将 `/Users/weijiazhao/Dev/EchoNote/data/database/connection.py` 的 workspace 临时补列逻辑升级为新的 schema 版本硬切换，不再为旧 `folder_id` 单列补丁保留特殊路径。
- 在 `WorkspaceManager` 中新增 `ensure_event_root_folder()` / `ensure_event_folder(event_id)` / `ensure_batch_task_root_folder()` / `create_note(..., event_id=None)`。
- `publish_transcription_task()` 在没有显式 folder override 时默认落到“批量任务”系统根目录。
- `move_item_to_folder()` 只能变更 `folder_id`，不得动 `source_event_id` 或 `source_task_id`。

**Step 4: Run test to verify it passes**

Run: `pytest /Users/weijiazhao/Dev/EchoNote/tests/unit/core/test_workspace_manager.py -k "event_folder or batch_folder or keep_link_after_move" -v`

Expected: PASS

**Step 5: Commit**

```bash
git add /Users/weijiazhao/Dev/EchoNote/data/database/schema.sql /Users/weijiazhao/Dev/EchoNote/data/database/connection.py /Users/weijiazhao/Dev/EchoNote/data/database/models.py /Users/weijiazhao/Dev/EchoNote/core/workspace/manager.py /Users/weijiazhao/Dev/EchoNote/tests/unit/core/test_workspace_manager.py
git commit -m "feat: add event folder semantics to workspace"
```

### Task 2: 重构工作台左侧信息架构，移除独立 toolbar 和 tool rail

**Files:**
- Modify: `/Users/weijiazhao/Dev/EchoNote/ui/workspace/widget.py`
- Modify: `/Users/weijiazhao/Dev/EchoNote/ui/workspace/library_panel.py`
- Delete: `/Users/weijiazhao/Dev/EchoNote/ui/workspace/toolbar.py`
- Delete: `/Users/weijiazhao/Dev/EchoNote/ui/workspace/tool_rail.py`
- Modify: `/Users/weijiazhao/Dev/EchoNote/ui/constants.py`
- Test: `/Users/weijiazhao/Dev/EchoNote/tests/ui/test_workspace_widget.py`

**Step 1: Write the failing test**

```python
def test_workspace_uses_single_navigator_shell_without_toolbar_or_tool_rail(
    qapp, mock_i18n, workspace_manager
):
    widget = WorkspaceWidget(workspace_manager, mock_i18n)

    assert widget.library_panel.header_action_bar is not None
    assert widget.library_panel.view_mode_switch is not None
    assert not hasattr(widget, "toolbar")
    assert not hasattr(widget, "tool_rail")
```

**Step 2: Run test to verify it fails**

Run: `pytest /Users/weijiazhao/Dev/EchoNote/tests/ui/test_workspace_widget.py::test_workspace_uses_single_navigator_shell_without_toolbar_or_tool_rail -v`

Expected: FAIL，因为当前 `WorkspaceWidget` 仍然同时创建 `toolbar` 和 `tool_rail`。

**Step 3: Write minimal implementation**

```python
class WorkspaceLibraryPanel(BaseWidget):
    def _build_header_actions(self) -> None:
        ...
```

实现要求：
- 把导入文档 / 新建笔记 / 结构视图 / 事件视图 / inspector toggle 收口到 `WorkspaceLibraryPanel` 头部。
- `WorkspaceWidget` 主布局直接变成三列，不再在 body 左侧额外挂一条 tool rail。
- navigator 头部需要显式暴露系统文件夹入口，包括“事件”和“批量任务”，避免用户只能在结果列表里被动发现系统归档。
- 新的 header action cluster 只保留高频动作，不再复制第二套导航。

**Step 4: Run test to verify it passes**

Run: `pytest /Users/weijiazhao/Dev/EchoNote/tests/ui/test_workspace_widget.py -k "single_navigator_shell or structure_and_event_views" -v`

Expected: PASS

**Step 5: Commit**

```bash
git add /Users/weijiazhao/Dev/EchoNote/ui/workspace/widget.py /Users/weijiazhao/Dev/EchoNote/ui/workspace/library_panel.py /Users/weijiazhao/Dev/EchoNote/ui/constants.py /Users/weijiazhao/Dev/EchoNote/tests/ui/test_workspace_widget.py
git rm /Users/weijiazhao/Dev/EchoNote/ui/workspace/toolbar.py /Users/weijiazhao/Dev/EchoNote/ui/workspace/tool_rail.py
git commit -m "feat: collapse workspace left controls into navigator shell"
```

### Task 3: 将红框 2 重定义为真正的 Navigator，并让事件视图具备 Obsidian 式分层入口

**Files:**
- Modify: `/Users/weijiazhao/Dev/EchoNote/ui/workspace/library_panel.py`
- Modify: `/Users/weijiazhao/Dev/EchoNote/core/workspace/manager.py`
- Modify: `/Users/weijiazhao/Dev/EchoNote/data/database/models.py`
- Test: `/Users/weijiazhao/Dev/EchoNote/tests/ui/test_workspace_widget.py`
- Test: `/Users/weijiazhao/Dev/EchoNote/tests/unit/core/test_workspace_manager.py`

**Step 1: Write the failing test**

```python
def test_workspace_event_mode_exposes_event_navigation_nodes(
    qapp, mock_i18n, workspace_manager
):
    widget = WorkspaceWidget(workspace_manager, mock_i18n)
    widget.library_panel.set_view_mode("event")

    node_types = widget.library_panel.visible_navigation_node_types()

    assert "event_group" in node_types
    assert "event" in node_types
    assert "folder" not in node_types
```

**Step 2: Run test to verify it fails**

Run: `pytest /Users/weijiazhao/Dev/EchoNote/tests/ui/test_workspace_widget.py::test_workspace_event_mode_exposes_event_navigation_nodes -v`

Expected: FAIL，因为当前 event mode 仍复用 folder tree，只是隐藏结构控件。

**Step 3: Write minimal implementation**

```python
def list_navigation_nodes(self, *, view_mode: str) -> list[dict]:
    ...
```

实现要求：
- `structure` 模式返回文件夹树，包含系统 `事件` 根目录与 event folders。
- `structure` 模式同时包含系统 `批量任务` 根目录。
- `event` 模式返回事件导航树，不显示用户文件夹节点。
- Navigator 节点与 results list 之间通过单一 selection state 绑定，禁止再出现“左边一个模式、下面一个列表、两边互不知道选中谁”的状态分裂。

**Step 4: Run test to verify it passes**

Run: `pytest /Users/weijiazhao/Dev/EchoNote/tests/ui/test_workspace_widget.py /Users/weijiazhao/Dev/EchoNote/tests/unit/core/test_workspace_manager.py -k "event_navigation_nodes or dual_library_views" -v`

Expected: PASS

**Step 5: Commit**

```bash
git add /Users/weijiazhao/Dev/EchoNote/ui/workspace/library_panel.py /Users/weijiazhao/Dev/EchoNote/core/workspace/manager.py /Users/weijiazhao/Dev/EchoNote/data/database/models.py /Users/weijiazhao/Dev/EchoNote/tests/ui/test_workspace_widget.py /Users/weijiazhao/Dev/EchoNote/tests/unit/core/test_workspace_manager.py
git commit -m "feat: rebuild workspace navigator for structure and event modes"
```

### Task 4: 替换结果列表实现，修复红框 3 的堆叠、裁切和事件条目表达

**Files:**
- Modify: `/Users/weijiazhao/Dev/EchoNote/ui/workspace/item_list.py`
- Modify: `/Users/weijiazhao/Dev/EchoNote/ui/workspace/library_panel.py`
- Modify: `/Users/weijiazhao/Dev/EchoNote/ui/workspace/widget.py`
- Modify: `/Users/weijiazhao/Dev/EchoNote/ui/constants.py`
- Modify: `/Users/weijiazhao/Dev/EchoNote/resources/translations/i18n_outline.json`
- Modify: `/Users/weijiazhao/Dev/EchoNote/resources/translations/zh_CN.json`
- Modify: `/Users/weijiazhao/Dev/EchoNote/resources/translations/en_US.json`
- Modify: `/Users/weijiazhao/Dev/EchoNote/resources/translations/fr_FR.json`
- Test: `/Users/weijiazhao/Dev/EchoNote/tests/ui/test_workspace_widget.py`
- Test: `/Users/weijiazhao/Dev/EchoNote/tests/unit/test_i18n_outline_contract.py`

**Step 1: Write the failing test**

```python
def test_workspace_results_rows_use_stable_delegate_metrics_and_event_badges(
    qapp, mock_i18n, workspace_manager
):
    widget = WorkspaceWidget(workspace_manager, mock_i18n)
    widget.library_panel.set_view_mode("event")

    assert widget.item_list.uses_delegate_layout is True
    assert widget.item_list.row_min_height > 0
    assert widget.item_list.supports_event_link_badge is True
```

**Step 2: Run test to verify it fails**

Run: `pytest /Users/weijiazhao/Dev/EchoNote/tests/ui/test_workspace_widget.py::test_workspace_results_rows_use_stable_delegate_metrics_and_event_badges -v`

Expected: FAIL，因为当前仍是 `QListWidget + setItemWidget()`。

**Step 3: Write minimal implementation**

```python
class WorkspaceItemListModel(QAbstractListModel):
    ...
```

实现要求：
- 将 `WorkspaceItemList` 改为 `QListView + model/delegate`，用统一行高 token 和绘制规则保证不会堆叠。
- 结构视图和事件视图共用一套 row renderer，但元信息来源不同：
  - 结构视图：文件夹 / 来源 / 更新时间
  - 事件视图：事件标题 / 来源 / 更新时间 / 关联状态
- 当 item 仍绑定 `source_event_id` 但已移动到用户文件夹时，row 上必须有显式关联标识，避免“看起来已脱离事件”。
- 当 item 绑定 `source_task_id` 时，row 上必须展示“批量任务”或“原任务”关联标识；如果用户已把文档移出“批量任务”文件夹，也不能丢失该标识。

**Step 4: Run test to verify it passes**

Run: `pytest /Users/weijiazhao/Dev/EchoNote/tests/ui/test_workspace_widget.py /Users/weijiazhao/Dev/EchoNote/tests/unit/test_i18n_outline_contract.py -k "delegate_metrics or event_badges" -v`

Expected: PASS

**Step 5: Commit**

```bash
git add /Users/weijiazhao/Dev/EchoNote/ui/workspace/item_list.py /Users/weijiazhao/Dev/EchoNote/ui/workspace/library_panel.py /Users/weijiazhao/Dev/EchoNote/ui/workspace/widget.py /Users/weijiazhao/Dev/EchoNote/ui/constants.py /Users/weijiazhao/Dev/EchoNote/resources/translations/i18n_outline.json /Users/weijiazhao/Dev/EchoNote/resources/translations/zh_CN.json /Users/weijiazhao/Dev/EchoNote/resources/translations/en_US.json /Users/weijiazhao/Dev/EchoNote/resources/translations/fr_FR.json /Users/weijiazhao/Dev/EchoNote/tests/ui/test_workspace_widget.py /Users/weijiazhao/Dev/EchoNote/tests/unit/test_i18n_outline_contract.py
git commit -m "feat: replace workspace results list with stable delegate rendering"
```

### Task 5: 重做 editor/inspector 上下文，让移动文件夹不破坏事件关系显示

**Files:**
- Modify: `/Users/weijiazhao/Dev/EchoNote/ui/workspace/editor_panel.py`
- Modify: `/Users/weijiazhao/Dev/EchoNote/ui/workspace/inspector_panel.py`
- Modify: `/Users/weijiazhao/Dev/EchoNote/ui/workspace/library_panel.py`
- Modify: `/Users/weijiazhao/Dev/EchoNote/ui/main_window.py`
- Test: `/Users/weijiazhao/Dev/EchoNote/tests/ui/test_workspace_widget.py`

**Step 1: Write the failing test**

```python
def test_workspace_editor_and_inspector_show_folder_and_event_context_independently(
    qapp, mock_i18n, workspace_manager
):
    widget = WorkspaceWidget(workspace_manager, mock_i18n)
    item_id = workspace_manager.create_note(title="Event Doc")
    item = workspace_manager.get_item(item_id)
    item.source_event_id = "evt-1"
    item.folder_id = workspace_manager.create_folder("Archive")
    item.save(workspace_manager.db)

    widget.open_item(item_id, view_mode="structure")

    assert "Archive" in widget.editor_panel.document_context_label.text()
    assert "evt-1" in widget.inspector_panel.event_value_label.text()
```

**Step 2: Run test to verify it fails**

Run: `pytest /Users/weijiazhao/Dev/EchoNote/tests/ui/test_workspace_widget.py::test_workspace_editor_and_inspector_show_folder_and_event_context_independently -v`

Expected: FAIL，因为当前 editor 只显示 asset label，inspector 也没有单独的事件关联字段。

**Step 3: Write minimal implementation**

```python
self.event_value_label = QLabel(self.metadata_section)
```

实现要求：
- `WorkspaceEditorPanel` 头部同时展示标题、文件夹归属和当前 asset，而不是只剩 asset label。
- `WorkspaceInspectorPanel` 元信息区新增“关联事件”“来源任务”“原文件”字段，并在存在 `source_event_id` / `source_task_id` 时展示可理解文本而不是裸 ID。
- `MainWindow.open_workspace_item()` 在 `view_mode="event"` 时仍应优先按事件上下文打开 item，但不能强制把 item 移回事件文件夹。

**Step 4: Run test to verify it passes**

Run: `pytest /Users/weijiazhao/Dev/EchoNote/tests/ui/test_workspace_widget.py -k "folder_and_event_context_independently or open_workspace_item" -v`

Expected: PASS

**Step 5: Commit**

```bash
git add /Users/weijiazhao/Dev/EchoNote/ui/workspace/editor_panel.py /Users/weijiazhao/Dev/EchoNote/ui/workspace/inspector_panel.py /Users/weijiazhao/Dev/EchoNote/ui/workspace/library_panel.py /Users/weijiazhao/Dev/EchoNote/ui/main_window.py /Users/weijiazhao/Dev/EchoNote/tests/ui/test_workspace_widget.py
git commit -m "feat: surface folder and event context across workspace stage"
```

### Task 6: 将红框 4 升级为 inspector transport player，复用 AudioPlayer 核心能力

**Files:**
- Modify: `/Users/weijiazhao/Dev/EchoNote/ui/common/audio_player.py`
- Modify: `/Users/weijiazhao/Dev/EchoNote/ui/workspace/recording_panel.py`
- Modify: `/Users/weijiazhao/Dev/EchoNote/ui/workspace/inspector_panel.py`
- Modify: `/Users/weijiazhao/Dev/EchoNote/ui/constants.py`
- Modify: `/Users/weijiazhao/Dev/EchoNote/resources/themes/light.qss`
- Modify: `/Users/weijiazhao/Dev/EchoNote/resources/themes/dark.qss`
- Modify: `/Users/weijiazhao/Dev/EchoNote/resources/themes/theme_outline.json`
- Test: `/Users/weijiazhao/Dev/EchoNote/tests/ui/test_timeline_audio_player.py`
- Test: `/Users/weijiazhao/Dev/EchoNote/tests/ui/test_workspace_widget.py`
- Test: `/Users/weijiazhao/Dev/EchoNote/tests/unit/test_theme_outline_contract.py`

**Step 1: Write the failing test**

```python
def test_workspace_recording_panel_uses_inspector_audio_player_presentation(
    qapp, mock_i18n, workspace_manager
):
    panel = WorkspaceRecordingPanel(workspace_manager, mock_i18n)

    assert panel.audio_player.presentation == "inspector"
    assert panel.audio_player.play_button is not None
    assert panel.audio_player.rewind_button is not None
    assert panel.audio_player.forward_button is not None
    assert panel.audio_player.volume_slider.isVisible()
```

**Step 2: Run test to verify it fails**

Run: `pytest /Users/weijiazhao/Dev/EchoNote/tests/ui/test_timeline_audio_player.py /Users/weijiazhao/Dev/EchoNote/tests/ui/test_workspace_widget.py -k "inspector_audio_player_presentation" -v`

Expected: FAIL，因为当前 `AudioPlayer` 没有 inspector 呈现模式，`WorkspaceRecordingPanel` 也没有播放器卡片语义。

**Step 3: Write minimal implementation**

```python
player = AudioPlayer("", self.i18n, self, auto_load=False, presentation="inspector")
```

实现要求：
- `AudioPlayer` 新增 inspector 呈现模式，保留现有播放逻辑，但调整头部、按钮密度、字幕面板默认状态和 role。
- `WorkspaceRecordingPanel` 明确三种状态：空态、可播放态、错误态。
- `WorkspaceInspectorPanel` 的 media section 要形成播放器卡片而不是空白容器，风格参考 VLC / Apple Music 的 transport 组织：进度条、主控制、音量、标题/来源一体化。

**Step 4: Run test to verify it passes**

Run: `pytest /Users/weijiazhao/Dev/EchoNote/tests/ui/test_timeline_audio_player.py /Users/weijiazhao/Dev/EchoNote/tests/ui/test_workspace_widget.py /Users/weijiazhao/Dev/EchoNote/tests/unit/test_theme_outline_contract.py -k "inspector_audio_player or recording_panel" -v`

Expected: PASS

**Step 5: Commit**

```bash
git add /Users/weijiazhao/Dev/EchoNote/ui/common/audio_player.py /Users/weijiazhao/Dev/EchoNote/ui/workspace/recording_panel.py /Users/weijiazhao/Dev/EchoNote/ui/workspace/inspector_panel.py /Users/weijiazhao/Dev/EchoNote/ui/constants.py /Users/weijiazhao/Dev/EchoNote/resources/themes/light.qss /Users/weijiazhao/Dev/EchoNote/resources/themes/dark.qss /Users/weijiazhao/Dev/EchoNote/resources/themes/theme_outline.json /Users/weijiazhao/Dev/EchoNote/tests/ui/test_timeline_audio_player.py /Users/weijiazhao/Dev/EchoNote/tests/ui/test_workspace_widget.py /Users/weijiazhao/Dev/EchoNote/tests/unit/test_theme_outline_contract.py
git commit -m "feat: redesign workspace inspector recording preview"
```

### Task 7: 同步文档、契约和稳定回归批次，关闭实施尾项

**Files:**
- Modify: `/Users/weijiazhao/Dev/EchoNote/AGENTS.md`
- Modify: `/Users/weijiazhao/Dev/EchoNote/docs/README.md`
- Modify: `/Users/weijiazhao/Dev/EchoNote/CHANGELOG.md`
- Test: `/Users/weijiazhao/Dev/EchoNote/tests/unit/test_main_window_shell.py`
- Test: `/Users/weijiazhao/Dev/EchoNote/tests/ui/test_workspace_widget.py`
- Test: `/Users/weijiazhao/Dev/EchoNote/tests/unit/test_i18n_outline_contract.py`
- Test: `/Users/weijiazhao/Dev/EchoNote/tests/unit/test_theme_outline_contract.py`

**Step 1: Write the failing test**

```python
def test_docs_reference_new_workspace_navigator_and_event_folder_paths():
    docs = Path("/Users/weijiazhao/Dev/EchoNote/docs/README.md").read_text(encoding="utf-8")
    assert "event folder" in docs.lower()
```

**Step 2: Run test to verify it fails**

Run: `pytest /Users/weijiazhao/Dev/EchoNote/tests/unit/test_main_window_shell.py -k "workspace" -v`

Expected: 至少需要人工确认文档仍引用旧的 `toolbar.py` / `tool_rail.py` 路径和旧职责描述。

**Step 3: Write minimal implementation**

```python
# no code sample; this task is docs/contracts/regression only
```

实现要求：
- 若 Task 2-6 改变了工作台入口职责，必须同步更新 `AGENTS.md` 的“项目代码结构速查”“常用定位建议”“功能关键词到文件路径”。
- `docs/README.md` 更新 active plan 和开发者导航，去掉旧的职责描述。
- `CHANGELOG.md` 记录工作台信息架构、事件归档语义和 inspector 播放器重构。
- 必须按稳定批次执行以下回归：
  - `pytest /Users/weijiazhao/Dev/EchoNote/tests/unit/test_main_window_shell.py -v`
  - `pytest /Users/weijiazhao/Dev/EchoNote/tests/ui/test_workspace_widget.py -v`
  - `pytest /Users/weijiazhao/Dev/EchoNote/tests/unit/test_i18n_outline_contract.py -v`
  - `pytest /Users/weijiazhao/Dev/EchoNote/tests/unit/test_theme_outline_contract.py -v`

**Step 4: Run test to verify it passes**

Run: `pytest /Users/weijiazhao/Dev/EchoNote/tests/unit/test_main_window_shell.py -v`

Expected: PASS，并且其余三批回归也全部通过。

**Step 5: Commit**

```bash
git add /Users/weijiazhao/Dev/EchoNote/AGENTS.md /Users/weijiazhao/Dev/EchoNote/docs/README.md /Users/weijiazhao/Dev/EchoNote/CHANGELOG.md
git commit -m "docs: close workspace red-box implementation trail"
```

## 5. 执行注意事项

1. 不要先改 QSS 再补结构；必须先完成事件 folder 领域模型和 navigator shell，样式只跟随结构落地。
2. `folder_id` 与 `source_event_id` / `source_task_id` 的解耦是本次改造的基础约束，任何实现只要把结构归属重新绑死到来源关联，就会再次制造技术债。
3. 右侧播放器禁止复制 `AudioPlayer` 的 seek / volume / play state 逻辑；所有 transport 行为必须继续从 `/Users/weijiazhao/Dev/EchoNote/ui/common/audio_player.py` 发出。
4. 若 Task 2 确认删除 `/Users/weijiazhao/Dev/EchoNote/ui/workspace/toolbar.py` 和 `/Users/weijiazhao/Dev/EchoNote/ui/workspace/tool_rail.py`，实施当次必须同步清理 imports、测试引用、文档索引和主题 role，避免留下空壳模块。
