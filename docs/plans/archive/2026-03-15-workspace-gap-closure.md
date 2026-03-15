# Workspace Gap Closure Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 把当前 `workspace` 从“资产浏览器 + 批量任务补丁位”推进到原始需求里的 Notes 式统一工作台，完整承载批量转写、实时录音、文本编辑、录音回放与文稿管理。

**Architecture:** 当前缺口的根因不是单个按钮缺失，而是工作台的信息架构仍偏“资产详情页”，没有把“采集入口、任务编排、文本库、录音操作、事件解绑后保留资产”组织成一个完整的内容生命周期闭环。后续实现应继续以 `workspace_items + workspace_assets` 为唯一事实源，把批量任务、实时录音产物、文档导入、工作台集合筛选和跨页跳转都收敛到 `ui/workspace/` 下，而不是回退到旧页面双轨并存。

**Tech Stack:** Python 3.10+, PySide6, SQLite, QSS, `core/workspace/*`, `core/transcription/manager.py`, `core/realtime/recorder.py`, `ui/workspace/*`, `ui/batch_transcribe/*`, `ui/common/audio_player.py`.

---

## 当前差距结论

1. 工作台已经接回批量任务队列，但仍缺少“工作台级创建入口”：新建笔记、导入文档、发起实时录音三类入口没有统一到同一页面顶部。
2. 实时录音仍停留在浮窗/后台服务视角，工作台里没有明确的录音控制区，因此“类似 Notes 的统一文本/录音工作区”体验还不完整。
3. 工作台左侧仍主要是线性条目列表，缺少集合/筛选（全部、录音、文档、待处理、最近编辑），不利于长期管理。
4. 时间线 / 日历 / 工作台之间仍偏“弹窗查看”，缺少“定位到工作台条目并聚焦正确资产”的单一路径。
5. 删除事件时虽然已支持保留 workspace 资产，但工作台本身还没有显式展示“已脱离事件但保留的条目”的来源状态与整理入口。

### Task 1: 收敛工作台信息架构与顶部入口

**Files:**
- Modify: `ui/workspace/widget.py`
- Create: `ui/workspace/toolbar.py`
- Modify: `ui/workspace/item_list.py`
- Modify: `ui/main_window.py`
- Test: `tests/ui/test_workspace_widget.py`

**Step 1: Write the failing test**

```python
def test_workspace_widget_exposes_unified_create_toolbar(qapp, mock_i18n, workspace_manager):
    widget = WorkspaceWidget(workspace_manager, mock_i18n, transcription_manager=Mock())

    assert widget.toolbar is not None
    assert widget.toolbar.import_document_button.isVisible()
    assert widget.toolbar.new_note_button.isVisible()
    assert widget.toolbar.start_recording_button.isVisible()
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/ui/test_workspace_widget.py::test_workspace_widget_exposes_unified_create_toolbar -v`
Expected: FAIL because the workspace toolbar and create-entry actions do not exist yet.

**Step 3: Write minimal implementation**

```python
class WorkspaceToolbar(BaseWidget):
    ...
```

实现要求：
- 顶部统一提供 `导入文档` / `新建笔记` / `开始录音` 三个入口。
- `导入文档` 直接落到 `WorkspaceManager.import_document()`。
- `新建笔记` 直接创建 `workspace_item + document_text asset`，不再走临时文件逻辑。
- `开始录音` 只负责把用户带到工作台内的录音控制区，不新增旧页面入口。

**Step 4: Run test to verify it passes**

Run: `pytest tests/ui/test_workspace_widget.py -k "toolbar or workspace_widget" -v`
Expected: PASS

**Step 5: Commit**

```bash
git add ui/workspace/widget.py ui/workspace/toolbar.py ui/workspace/item_list.py ui/main_window.py tests/ui/test_workspace_widget.py
git commit -m "feat: add unified workspace toolbar"
```

### Task 2: 把实时录音主控并入工作台

**Files:**
- Modify: `ui/workspace/widget.py`
- Create: `ui/workspace/recording_control_panel.py`
- Modify: `core/realtime/recorder.py`
- Modify: `main.py`
- Test: `tests/ui/test_workspace_widget.py`
- Test: `tests/unit/core/test_realtime_recorder.py`

**Step 1: Write the failing test**

```python
def test_workspace_widget_embeds_realtime_recording_controls(qapp, mock_i18n, workspace_manager):
    widget = WorkspaceWidget(
        workspace_manager,
        mock_i18n,
        transcription_manager=Mock(),
        realtime_recorder=Mock(),
    )

    assert widget.recording_control_panel.record_button.isVisible()
    assert widget.recording_control_panel.stop_button.isVisible()
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/ui/test_workspace_widget.py::test_workspace_widget_embeds_realtime_recording_controls -v`
Expected: FAIL because the workspace has playback only and no recording controls.

**Step 3: Write minimal implementation**

```python
class WorkspaceRecordingControlPanel(BaseWidget):
    ...
```

实现要求：
- 录音控制区必须直接复用现有 `core/realtime/recorder.py`，不要复制第二套录音状态机。
- 录音完成后继续发布到 `workspace_items/workspace_assets`，并在当前工作台自动刷新选中最新条目。
- 浮窗保留为辅助视图，不再承担“唯一主入口”职责。

**Step 4: Run test to verify it passes**

Run: `pytest tests/ui/test_workspace_widget.py tests/unit/core/test_realtime_recorder.py -k workspace -v`
Expected: PASS

**Step 5: Commit**

```bash
git add ui/workspace/widget.py ui/workspace/recording_control_panel.py core/realtime/recorder.py main.py tests/ui/test_workspace_widget.py tests/unit/core/test_realtime_recorder.py
git commit -m "feat: embed realtime controls in workspace"
```

### Task 3: 给工作台补集合筛选与条目元信息

**Files:**
- Modify: `ui/workspace/item_list.py`
- Modify: `core/workspace/manager.py`
- Modify: `data/database/models.py`
- Test: `tests/unit/core/test_workspace_manager.py`
- Test: `tests/ui/test_workspace_widget.py`

**Step 1: Write the failing test**

```python
def test_workspace_manager_lists_filtered_collections(tmp_path):
    manager = build_workspace_manager(tmp_path)
    create_workspace_recording(manager, title="Call")
    create_workspace_document(manager, title="Agenda")

    recordings = manager.list_items(collection="recordings")
    assert [item.title for item in recordings] == ["Call"]
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/core/test_workspace_manager.py::test_workspace_manager_lists_filtered_collections -v`
Expected: FAIL because `list_items()` only supports raw `item_type` and the UI has no collection abstraction.

**Step 3: Write minimal implementation**

```python
def list_items(self, *, collection: Optional[str] = None, item_type: Optional[str] = None):
    ...
```

实现要求：
- 至少支持 `all / recordings / documents / orphaned / recent` 五个集合。
- `orphaned` 表达“原来关联事件，但事件删除后保留在 workspace 的条目”。
- 左侧列表需要展示来源、更新时间、是否存在录音/文本等轻量元信息，不要只剩标题。

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/core/test_workspace_manager.py tests/ui/test_workspace_widget.py -k "collection or orphaned or recent" -v`
Expected: PASS

**Step 5: Commit**

```bash
git add ui/workspace/item_list.py core/workspace/manager.py data/database/models.py tests/unit/core/test_workspace_manager.py tests/ui/test_workspace_widget.py
git commit -m "feat: add workspace collections and metadata list"
```

### Task 4: 统一时间线/日历到工作台的打开路径

**Files:**
- Modify: `ui/timeline/widget.py`
- Modify: `ui/calendar_hub/widget.py`
- Modify: `ui/main_window.py`
- Modify: `ui/workspace/widget.py`
- Test: `tests/ui/test_timeline_widget_delete.py`
- Test: `tests/ui/test_calendar_hub_widget.py`
- Test: `tests/unit/test_main_window_search.py`

**Step 1: Write the failing test**

```python
def test_timeline_open_transcript_routes_to_workspace_item(qapp, mock_i18n):
    main_window = build_main_window_with_workspace()
    event_id = seed_event_with_workspace_assets(main_window)

    main_window.pages["timeline"]._on_view_transcript(event_id=event_id)

    assert main_window.current_page_name == "workspace"
    assert main_window.pages["workspace"].current_item_id() is not None
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/ui/test_calendar_hub_widget.py tests/ui/test_timeline_widget_delete.py tests/unit/test_main_window_search.py -k workspace -v`
Expected: FAIL because timeline/calendar still prefer modal viewers over routing to workspace focus.

**Step 3: Write minimal implementation**

```python
def open_workspace_item(self, *, item_id: str, asset_role: Optional[str] = None) -> None:
    ...
```

实现要求：
- 时间线 / 日历点击“查看转写/查看翻译/查看录音”时，优先把主窗口切到 `workspace` 并选中对应条目/资产。
- 只有在工作台无法定位条目时，才退回共享查看器。
- 删除事件后若用户选择保留资产，工作台必须能直接定位到已脱离事件的条目。

**Step 4: Run test to verify it passes**

Run: `pytest tests/ui/test_calendar_hub_widget.py tests/ui/test_timeline_widget_delete.py tests/unit/test_main_window_search.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add ui/timeline/widget.py ui/calendar_hub/widget.py ui/main_window.py ui/workspace/widget.py tests/ui/test_timeline_widget_delete.py tests/ui/test_calendar_hub_widget.py tests/unit/test_main_window_search.py
git commit -m "feat: route event artifacts into workspace"
```

### Task 5: 文档、i18n 与清理收口

**Files:**
- Modify: `AGENTS.md`
- Modify: `docs/README.md`
- Modify: `CHANGELOG.md`
- Modify: `resources/translations/i18n_outline.json`
- Modify: `resources/translations/zh_CN.json`
- Modify: `resources/translations/en_US.json`
- Modify: `resources/translations/fr_FR.json`
- Test: `tests/unit/test_i18n_outline_contract.py`

**Step 1: Write the failing test**

```python
def test_all_locales_have_identical_nested_key_paths():
    ...
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_i18n_outline_contract.py -v`
Expected: FAIL after adding new workspace / delete-flow copy until all locales and outline are synchronized.

**Step 3: Write minimal implementation**

```json
{
  "workspace": {
    "task_queue_title": "...",
    "library_title": "..."
  }
}
```

实现要求：
- `AGENTS.md` 和 `docs/README.md` 必须反映“工作台拥有任务队列 + 资产库 + 录音控制”的职责变化。
- `CHANGELOG.md` 记录删除语义与工作台职责收敛带来的维护性变化。
- 删除所有已失效的“Batch Tasks 页面”文案指向，统一改为工作台任务列表或工作台条目。

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_i18n_outline_contract.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add AGENTS.md docs/README.md CHANGELOG.md resources/translations/i18n_outline.json resources/translations/zh_CN.json resources/translations/en_US.json resources/translations/fr_FR.json
git commit -m "docs: align workspace gap closure docs"
```
