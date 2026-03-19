# Workspace Tree Context Menu And Markdown Vault Hard-Switch Implementation Plan

> **归档说明（2026-03-18）**：本文已归档并停止作为执行入口。后续工作台树、右键菜单、拖拽语义和 Markdown Vault 落盘统一以 `/Users/weijiazhao/Dev/EchoNote/docs/plans/archive/2026-03-18-workspace-tree-context-dnd-markdown-vault-superseded.md` 的后继实现与实际代码为准。

**Goal:** 用硬切换方式把工作台树升级为带右键快捷菜单、受约束复制/移动拖拽、以及 Obsidian 风格 Markdown Vault 存储的单一文档工作区。

**Architecture:** 文本文档以本地 Markdown 文件作为唯一事实源，数据库只保留索引、关系、来源关联和主资产指针，不再把 `workspace_assets.text_content` 当成长期主存。工作台树、右键菜单和拖拽规则统一收口到 `/Users/weijiazhao/Dev/EchoNote/core/workspace/manager.py` + `/Users/weijiazhao/Dev/EchoNote/ui/workspace/library_panel.py` 的单一策略层，禁止在时间线、日历、批量任务等外围界面重复实现一套文件移动规则。

**Tech Stack:** Python 3.12, PySide6, SQLite, 本地文件系统, QSS, i18n JSON, `/Users/weijiazhao/Dev/EchoNote/core/workspace/*`, `/Users/weijiazhao/Dev/EchoNote/data/storage/file_manager.py`, `/Users/weijiazhao/Dev/EchoNote/ui/workspace/*`, `/Users/weijiazhao/Dev/EchoNote/ui/settings/*`, `/Users/weijiazhao/Dev/EchoNote/tests/unit/*`, `/Users/weijiazhao/Dev/EchoNote/tests/ui/*`.

---

**Assumption:** 后续执行在独立分支中进行；当前变更只新增计划与文档导航，不直接修改业务代码。

## 1. 审查结论

### 1.1 当前实现与需求的偏差

1. `/Users/weijiazhao/Dev/EchoNote/ui/workspace/library_panel.py` 当前没有右键菜单入口，树上快捷操作全部依赖顶部 icon 按钮，无法满足参考图里“就地打开 / 新建 / 移动 / 重命名 / 删除 / 复制路径”这类上下文操作心智。
2. 当前“复制还是移动”提示只发生在 `WorkspaceLibraryPanel._on_tree_drop_requested()` 的树内 item 拖放分支，而且触发条件依赖“源条目当前所在 folder_kind 是 `event` / `batch_task`”。这意味着它只覆盖工作台树内部移动，不覆盖用户理解中的“事件区/批量任务区作为来源域”的完整约束。
3. `/Users/weijiazhao/Dev/EchoNote/core/workspace/manager.py` 的 `_folder_accepts_direct_items()` 当前允许 `event` 和 `batch_task` 作为直接落点，因此从域模型上仍然允许普通条目被移动回系统目录，这和“文本只能从事件/批量任务流向工作台条目，其他部分不能移动/复制至事件/批量任务”相冲突。
4. 时间线、日历、批量任务面板目前没有任何工作台拖拽协议；它们只支持“查看时路由到工作台”。如果产品预期是“从这些面板直接拖到工作台树”，当前实现完全不满足。
5. `/Users/weijiazhao/Dev/EchoNote/core/workspace/manager.py`、`/Users/weijiazhao/Dev/EchoNote/core/workspace/import_service.py` 和 `/Users/weijiazhao/Dev/EchoNote/ui/workspace/editor_panel.py` 仍然同时依赖 `workspace_assets.text_content` 与磁盘 `file_path`，形成“双写双读”冗余。
6. 当前文本资产落盘路径是 `Workspace/<item_id>/<subfolder>/...`，并不和工作台树目录结构对齐；重命名条目、移动条目、重命名文件夹都不会同步更改磁盘路径，因此并不是 Obsidian 式 Vault。

### 1.2 产品与交互上的硬决策

1. 工作台树需要引入右键菜单，但菜单动作必须复用已有能力，不能把“重命名 / 删除 / 新建”分别在 header、context menu、未来快捷键里各写一遍。
2. 系统目录是“系统生成内容的默认承载位置”，不是用户日常整理目录；因此用户手动移动只能流向 `user` / `inbox`，不能流回 `event` / `batch_task`。
3. 如果后续决定支持“从时间线卡片 / 任务卡片拖入工作台树”，也必须复用同一个 workspace payload 协议和同一套 copy/move 判定，不能让每个来源组件自己弹窗。
4. Markdown Vault 必须支持用户可选根目录；树形目录、磁盘文件夹、磁盘 `.md` 文件命名应保持一致。既然本次明确允许硬切换，就不做旧路径迁移和兼容分支，初始化代码直接切新结构。

## 2. 完整需求拆解

### 2.1 工作台树右键菜单

1. 右键空白区与右键节点必须区分菜单内容：
   - 空白区：新建笔记、新建文件夹、导入文档、在系统文件管理器中打开当前 Vault。
   - 用户文件夹：在新标签页打开、在新窗口中打开、新建笔记、新建文件夹、重命名、删除、复制路径。
   - 系统文件夹（工作台条目 / 事件 / 批量任务 / 事件子文件夹）：允许打开、新建“流出类”动作，不允许重命名系统根；事件子文件夹允许“在文件夹中显示”和“复制路径”，不允许用户把内容拖回去。
   - 文档条目：在新标签页打开、在新窗口中打开、在系统文件管理器中显示、复制路径、重命名、删除。
2. 菜单动作顺序应遵循桌面文档产品通用规则：打开类、创建类、组织类、路径/系统类、破坏性动作。
3. 菜单文案、role、禁用态都必须进入 i18n / theme 契约，不允许继续在代码里用 `default=` 字符串兜底。

### 2.2 复制 / 移动拖拽规则

1. 只有文本条目可以从 `event` / `batch_task` 来源域流向 `user` / `inbox`。
2. 任何普通内容都不能通过拖拽进入 `event` / `batch_task` 系统目录。
3. 从系统来源域流向用户域时，必须弹出明确的二选一确认：
   - 复制：保留原来源条目不变，在目标目录生成一个去关联的新副本。
   - 移动：更新现有条目归属到目标目录，但保留 `source_event_id` / `source_task_id` 作为来源事实。
4. 从用户域到用户域的拖拽不弹窗，默认移动。
5. 如果后续启用外部来源组件拖拽，只有显式声明 `workspace-item/text` payload 的来源组件能投到工作台树，其他组件一律 `ignore`。

### 2.3 Markdown Vault 与目录对齐

1. 笔记正文、转写、翻译、摘要、会议整理等文本统一以 `.md` 文件落盘。
2. 磁盘结构要与工作台树对齐，例如：
   - `工作台条目/Plan.md`
   - `工作台条目/Projects/Spec.md`
   - `事件/Design Review/Transcript.md`
   - `批量任务/meeting-2026-03-18/Transcript.md`
3. 文档标题与文件名保持一致，重命名条目时同时重命名文件。
4. 移动条目 / 移动文件夹时同步移动对应文件 / 目录。
5. 数据库存储保留必要索引，但不再依赖 `text_content` 作为主读路径；读取文本时优先从磁盘读取。
6. 导入的非 Markdown 原文件继续作为 `source_document` 保存，但工作编辑面永远面向对应的 `.md` 文本副本。

## 3. 实施顺序总览

1. 先建立 Vault 根路径与目录布局服务，避免后续路径规则散落在 `manager.py`、`import_service.py`、`editor_panel.py`。
2. 再把文本资产硬切到 Markdown 文件为主存，并让树/文件系统对齐。
3. 然后收紧 folder 允许规则和拖拽策略，确保“只出不进”的系统目录语义成立。
4. 最后加入右键菜单、i18n/theme 契约与回归测试，完成交互收口。

### Task 1: 建立 Workspace Vault 根路径配置与统一路径布局服务

**Files:**
- Create: `/Users/weijiazhao/Dev/EchoNote/core/workspace/vault_layout.py`
- Create: `/Users/weijiazhao/Dev/EchoNote/ui/settings/workspace_page.py`
- Modify: `/Users/weijiazhao/Dev/EchoNote/config/default_config.json`
- Modify: `/Users/weijiazhao/Dev/EchoNote/core/settings/manager.py`
- Modify: `/Users/weijiazhao/Dev/EchoNote/data/storage/file_manager.py`
- Modify: `/Users/weijiazhao/Dev/EchoNote/ui/settings/widget.py`
- Test: `/Users/weijiazhao/Dev/EchoNote/tests/ui/test_settings_widget.py`
- Test: `/Users/weijiazhao/Dev/EchoNote/tests/ui/test_workspace_settings_page.py`

**Step 1: Write the failing test**

```python
def test_workspace_settings_page_persists_markdown_vault_root(qapp, mock_i18n, settings_manager):
    page = WorkspaceSettingsPage(settings_manager, mock_i18n)
    page.load_settings()

    page.vault_root_edit.setText("/tmp/echonote-vault")
    page.save_settings()

    assert settings_manager.get_setting("workspace.storage_root") == "/tmp/echonote-vault"
```

**Step 2: Run test to verify it fails**

Run: `pytest /Users/weijiazhao/Dev/EchoNote/tests/ui/test_workspace_settings_page.py::test_workspace_settings_page_persists_markdown_vault_root -v`

Expected: FAIL，因为当前没有 `workspace.storage_root` 配置，也没有工作台设置页。

**Step 3: Write minimal implementation**

```python
class WorkspaceVaultLayout:
    def __init__(self, vault_root: str):
        self.vault_root = Path(vault_root).expanduser()
```

实现要求：
- 在默认配置中新增 `workspace.storage_root`，默认值直接指向新的 Markdown Vault 根目录，例如 `~/Documents/EchoNote/WorkspaceVault`。
- `FileManager` 不再把 `workspace_dir` 当作唯一工作台文本根目录来源，而是暴露可注入的 vault root。
- 新建 `WorkspaceVaultLayout` 统一生成：
  - 系统根目录路径
  - 文件夹目录路径
  - 条目 Markdown 文件路径
  - 非文本附件路径
- 新增设置页，允许用户选择 Vault 根目录；不做迁移逻辑，只在新路径下工作。

**Step 4: Run test to verify it passes**

Run: `pytest /Users/weijiazhao/Dev/EchoNote/tests/ui/test_workspace_settings_page.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add /Users/weijiazhao/Dev/EchoNote/config/default_config.json /Users/weijiazhao/Dev/EchoNote/core/settings/manager.py /Users/weijiazhao/Dev/EchoNote/data/storage/file_manager.py /Users/weijiazhao/Dev/EchoNote/core/workspace/vault_layout.py /Users/weijiazhao/Dev/EchoNote/ui/settings/widget.py /Users/weijiazhao/Dev/EchoNote/ui/settings/workspace_page.py /Users/weijiazhao/Dev/EchoNote/tests/ui/test_settings_widget.py /Users/weijiazhao/Dev/EchoNote/tests/ui/test_workspace_settings_page.py
git commit -m "feat: add workspace vault root settings"
```

### Task 2: 将工作台文本资产硬切换为 Markdown 文件事实源

**Files:**
- Modify: `/Users/weijiazhao/Dev/EchoNote/core/workspace/manager.py`
- Modify: `/Users/weijiazhao/Dev/EchoNote/core/workspace/import_service.py`
- Modify: `/Users/weijiazhao/Dev/EchoNote/ui/workspace/editor_panel.py`
- Modify: `/Users/weijiazhao/Dev/EchoNote/data/database/models.py`
- Test: `/Users/weijiazhao/Dev/EchoNote/tests/unit/core/test_workspace_manager.py`
- Test: `/Users/weijiazhao/Dev/EchoNote/tests/ui/test_workspace_widget.py`

**Step 1: Write the failing test**

```python
def test_workspace_note_is_stored_as_markdown_file_in_vault(tmp_path):
    manager = build_workspace_manager(tmp_path)
    note_id = manager.create_note(title="Plan", text_content="hello")

    asset = manager.get_primary_text_asset(note_id)

    assert asset is not None
    assert asset.file_path.endswith("Plan.md")
    assert Path(asset.file_path).read_text(encoding="utf-8") == "hello"
    assert asset.content_type == "text/markdown"
```

**Step 2: Run test to verify it fails**

Run: `pytest /Users/weijiazhao/Dev/EchoNote/tests/unit/core/test_workspace_manager.py::test_workspace_note_is_stored_as_markdown_file_in_vault -v`

Expected: FAIL，因为当前默认保存路径是 `Workspace/<item_id>/notes/note.md`，文件名和树标题不对齐。

**Step 3: Write minimal implementation**

```python
def read_asset_text(self, asset):
    return Path(asset.file_path).read_text(encoding="utf-8")
```

实现要求：
- `create_note()`、`save_text_asset()`、`update_text_asset()`、`import_document()`、`publish_transcription_task()`、`publish_recording_session()` 统一通过 `WorkspaceVaultLayout` 生成 Markdown 路径。
- `read_asset_text()` 优先读文件；`text_content` 仅作为可选缓存字段，后续可删则删，不允许再作为主逻辑短路。
- `import_document()` 对 `.txt/.docx/.pdf/...` 导入时始终生成一个 Markdown 副本作为 `document_text`。
- `WorkspaceEditorPanel` 保存时只经 `workspace_manager.update_text_asset()`，不自行回写裸文件路径分支。

**Step 4: Run test to verify it passes**

Run: `pytest /Users/weijiazhao/Dev/EchoNote/tests/unit/core/test_workspace_manager.py -k "markdown_file_in_vault or import_document" -v`

Expected: PASS

**Step 5: Commit**

```bash
git add /Users/weijiazhao/Dev/EchoNote/core/workspace/manager.py /Users/weijiazhao/Dev/EchoNote/core/workspace/import_service.py /Users/weijiazhao/Dev/EchoNote/ui/workspace/editor_panel.py /Users/weijiazhao/Dev/EchoNote/data/database/models.py /Users/weijiazhao/Dev/EchoNote/tests/unit/core/test_workspace_manager.py /Users/weijiazhao/Dev/EchoNote/tests/ui/test_workspace_widget.py
git commit -m "feat: hard switch workspace text assets to markdown files"
```

### Task 3: 让树结构、文件系统与来源语义严格对齐

**Files:**
- Modify: `/Users/weijiazhao/Dev/EchoNote/core/workspace/manager.py`
- Modify: `/Users/weijiazhao/Dev/EchoNote/core/workspace/import_service.py`
- Modify: `/Users/weijiazhao/Dev/EchoNote/data/storage/file_manager.py`
- Test: `/Users/weijiazhao/Dev/EchoNote/tests/unit/core/test_workspace_manager.py`

**Step 1: Write the failing test**

```python
def test_rename_and_move_item_sync_markdown_file_path(tmp_path):
    manager = build_workspace_manager(tmp_path)
    folder_id = manager.create_folder("Projects")
    note_id = manager.create_note(title="Plan", text_content="hello")

    manager.move_item_to_folder(note_id, folder_id)
    manager.rename_item(note_id, "Spec")

    asset = manager.get_primary_text_asset(note_id)
    assert asset is not None
    assert asset.file_path.endswith("Projects/Spec.md")
    assert Path(asset.file_path).read_text(encoding="utf-8") == "hello"
```

**Step 2: Run test to verify it fails**

Run: `pytest /Users/weijiazhao/Dev/EchoNote/tests/unit/core/test_workspace_manager.py::test_rename_and_move_item_sync_markdown_file_path -v`

Expected: FAIL，因为当前 rename/move 只改数据库，不改磁盘路径。

**Step 3: Write minimal implementation**

```python
def move_item_to_folder(self, item_id: str, folder_id: str | None) -> WorkspaceItem:
    self._relocate_item_markdown_assets(item, target_folder)
```

实现要求：
- `rename_folder()`、`move_folder()`、`rename_item()`、`move_item_to_folder()` 同步变更磁盘目录 / 文件名。
- 为避免“系统目录可回流”歧义，把用户手动移动 API 收紧为只允许 `user` / `inbox` 目标目录。
- 系统默认分配（事件/批量任务发布）改走单独内部 helper，例如 `_assign_item_to_system_folder()`；不要继续复用用户移动 API。
- 删除已经不再需要的 item-id 中间目录层级和相关陈旧 helper。

**Step 4: Run test to verify it passes**

Run: `pytest /Users/weijiazhao/Dev/EchoNote/tests/unit/core/test_workspace_manager.py -k "sync_markdown_file_path or keep_link_after_move or invalid_move_target" -v`

Expected: PASS

**Step 5: Commit**

```bash
git add /Users/weijiazhao/Dev/EchoNote/core/workspace/manager.py /Users/weijiazhao/Dev/EchoNote/core/workspace/import_service.py /Users/weijiazhao/Dev/EchoNote/data/storage/file_manager.py /Users/weijiazhao/Dev/EchoNote/tests/unit/core/test_workspace_manager.py
git commit -m "feat: align workspace tree moves with vault filesystem"
```

### Task 4: 为工作台树引入可复用的右键菜单动作层

**Files:**
- Create: `/Users/weijiazhao/Dev/EchoNote/ui/workspace/tree_context_menu.py`
- Modify: `/Users/weijiazhao/Dev/EchoNote/ui/workspace/library_panel.py`
- Modify: `/Users/weijiazhao/Dev/EchoNote/ui/workspace/widget.py`
- Modify: `/Users/weijiazhao/Dev/EchoNote/resources/translations/i18n_outline.json`
- Modify: `/Users/weijiazhao/Dev/EchoNote/resources/translations/zh_CN.json`
- Modify: `/Users/weijiazhao/Dev/EchoNote/resources/translations/en_US.json`
- Modify: `/Users/weijiazhao/Dev/EchoNote/resources/translations/fr_FR.json`
- Modify: `/Users/weijiazhao/Dev/EchoNote/ui/constants.py`
- Modify: `/Users/weijiazhao/Dev/EchoNote/resources/themes/theme_outline.json`
- Test: `/Users/weijiazhao/Dev/EchoNote/tests/ui/test_workspace_widget.py`
- Test: `/Users/weijiazhao/Dev/EchoNote/tests/unit/test_i18n_outline_contract.py`
- Test: `/Users/weijiazhao/Dev/EchoNote/tests/unit/test_theme_outline_contract.py`

**Step 1: Write the failing test**

```python
def test_workspace_tree_context_menu_exposes_item_actions(qapp, mock_i18n, workspace_manager):
    note_id = workspace_manager.create_note(title="Plan")
    widget = WorkspaceWidget(workspace_manager, mock_i18n)
    node = widget.library_panel.find_item_node(note_id)

    actions = widget.library_panel.build_context_menu_actions(node)

    assert "workspace.open_in_new_tab" in actions
    assert "workspace.open_in_new_window" in actions
    assert "common.rename" in actions
    assert "common.delete" in actions
```

**Step 2: Run test to verify it fails**

Run: `pytest /Users/weijiazhao/Dev/EchoNote/tests/ui/test_workspace_widget.py::test_workspace_tree_context_menu_exposes_item_actions -v`

Expected: FAIL，因为当前树没有 context menu。

**Step 3: Write minimal implementation**

```python
class WorkspaceTreeContextMenu:
    def build_for_node(self, node):
        return QMenu()
```

实现要求：
- `library_panel.py` 只负责选中节点、委托 action 执行，不直接在一个方法里硬编码整套菜单。
- `tree_context_menu.py` 负责按 selection kind/folder kind 组装菜单，避免 header actions 与 context menu 各写一份判定。
- 新增 “在新标签页打开 / 在新窗口中打开 / 在系统文件管理器中显示 / 复制路径 / 新建笔记 / 新建文件夹 / 重命名 / 删除” 对应的 i18n key。
- 若新增 role 或状态 selector，必须同步更新 `theme_outline.json`。

**Step 4: Run test to verify it passes**

Run: `pytest /Users/weijiazhao/Dev/EchoNote/tests/ui/test_workspace_widget.py -k "context_menu" -v`

Expected: PASS

**Step 5: Commit**

```bash
git add /Users/weijiazhao/Dev/EchoNote/ui/workspace/tree_context_menu.py /Users/weijiazhao/Dev/EchoNote/ui/workspace/library_panel.py /Users/weijiazhao/Dev/EchoNote/ui/workspace/widget.py /Users/weijiazhao/Dev/EchoNote/resources/translations/i18n_outline.json /Users/weijiazhao/Dev/EchoNote/resources/translations/zh_CN.json /Users/weijiazhao/Dev/EchoNote/resources/translations/en_US.json /Users/weijiazhao/Dev/EchoNote/resources/translations/fr_FR.json /Users/weijiazhao/Dev/EchoNote/ui/constants.py /Users/weijiazhao/Dev/EchoNote/resources/themes/theme_outline.json /Users/weijiazhao/Dev/EchoNote/tests/ui/test_workspace_widget.py /Users/weijiazhao/Dev/EchoNote/tests/unit/test_i18n_outline_contract.py /Users/weijiazhao/Dev/EchoNote/tests/unit/test_theme_outline_contract.py
git commit -m "feat: add workspace tree context menu"
```

### Task 5: 收紧复制/移动拖拽语义并审查所有来源组件

**Files:**
- Modify: `/Users/weijiazhao/Dev/EchoNote/ui/workspace/library_panel.py`
- Modify: `/Users/weijiazhao/Dev/EchoNote/core/workspace/manager.py`
- Modify: `/Users/weijiazhao/Dev/EchoNote/ui/batch_transcribe/task_item.py`
- Modify: `/Users/weijiazhao/Dev/EchoNote/ui/workspace/task_panel.py`
- Modify: `/Users/weijiazhao/Dev/EchoNote/ui/timeline/widget.py`
- Modify: `/Users/weijiazhao/Dev/EchoNote/ui/calendar_hub/widget.py`
- Test: `/Users/weijiazhao/Dev/EchoNote/tests/ui/test_workspace_widget.py`
- Test: `/Users/weijiazhao/Dev/EchoNote/tests/unit/core/test_workspace_manager.py`

**Step 1: Write the failing test**

```python
def test_workspace_drag_from_event_folder_to_user_folder_requires_copy_or_move(
    qapp, mock_i18n, workspace_manager
):
    event = CalendarEvent(
        title="Design Review",
        start_time="2026-03-18T09:00:00+00:00",
        end_time="2026-03-18T10:00:00+00:00",
    )
    event.save(workspace_manager.db)
    target_folder_id = workspace_manager.create_folder("Archive")
    note_id = workspace_manager.create_note(title="Notes", event_id=event.id)
    widget = WorkspaceWidget(workspace_manager, mock_i18n)

    with patch.object(widget.library_panel, "_prompt_drag_conflict_resolution", return_value="copy"):
        widget.library_panel._on_tree_drop_requested("item", note_id, "folder", target_folder_id)

    copied_items = [item for item in workspace_manager.list_items() if item.title.startswith("Notes")]
    assert len(copied_items) == 2
```

**Step 2: Run test to verify it fails**

Run: `pytest /Users/weijiazhao/Dev/EchoNote/tests/ui/test_workspace_widget.py::test_workspace_drag_from_event_folder_to_user_folder_requires_copy_or_move -v`

Expected: FAIL，因为当前提示逻辑没有抽成稳定可测试的策略层，且 manager 仍允许回流到系统目录。

**Step 3: Write minimal implementation**

```python
def _classify_drag_operation(self, source_item, target_folder):
    return "prompt-copy-or-move"
```

实现要求：
- 把拖拽规则抽成单一 helper，例如 `_classify_item_drop()`，返回：
  - `move`
  - `prompt-copy-or-move`
  - `reject`
- `copy_item_to_folder()` 继续保留，但复制副本时必须清空系统来源目录归属，只保留必要来源元数据策略；不要复制出还挂在原系统目录的路径。
- `move_item_to_folder()` 对系统目录目标一律抛 `invalid_move_target`。
- 明确审查 `/Users/weijiazhao/Dev/EchoNote/ui/batch_transcribe/task_item.py`、`/Users/weijiazhao/Dev/EchoNote/ui/workspace/task_panel.py`、`/Users/weijiazhao/Dev/EchoNote/ui/timeline/widget.py`、`/Users/weijiazhao/Dev/EchoNote/ui/calendar_hub/widget.py`：
  - 如果没有 workspace drag payload，就保持不可拖。
  - 如果未来启用拖拽，只能发出统一 payload，不能自行处理复制/移动弹窗。

**Step 4: Run test to verify it passes**

Run: `pytest /Users/weijiazhao/Dev/EchoNote/tests/ui/test_workspace_widget.py -k "drag_from_event_folder or duplicate_item_name or drop_onto_item_target" -v`

Expected: PASS

**Step 5: Commit**

```bash
git add /Users/weijiazhao/Dev/EchoNote/ui/workspace/library_panel.py /Users/weijiazhao/Dev/EchoNote/core/workspace/manager.py /Users/weijiazhao/Dev/EchoNote/ui/batch_transcribe/task_item.py /Users/weijiazhao/Dev/EchoNote/ui/workspace/task_panel.py /Users/weijiazhao/Dev/EchoNote/ui/timeline/widget.py /Users/weijiazhao/Dev/EchoNote/ui/calendar_hub/widget.py /Users/weijiazhao/Dev/EchoNote/tests/ui/test_workspace_widget.py /Users/weijiazhao/Dev/EchoNote/tests/unit/core/test_workspace_manager.py
git commit -m "feat: constrain workspace drag and drop semantics"
```

### Task 6: 收口文档、契约与稳定回归批次

**Files:**
- Modify: `/Users/weijiazhao/Dev/EchoNote/docs/README.md`
- Modify: `/Users/weijiazhao/Dev/EchoNote/docs/plans/archive/2026-03-16-workspace-navigation-drag-drop-refactor-superseded.md`
- Modify: `/Users/weijiazhao/Dev/EchoNote/CHANGELOG.md`
- Test: `/Users/weijiazhao/Dev/EchoNote/tests/unit/test_i18n_outline_contract.py`
- Test: `/Users/weijiazhao/Dev/EchoNote/tests/unit/test_theme_outline_contract.py`
- Test: `/Users/weijiazhao/Dev/EchoNote/tests/unit/test_main_window_shell.py`
- Test: `/Users/weijiazhao/Dev/EchoNote/tests/ui/test_workspace_widget.py`

**Step 1: Write the failing test**

```python
def test_visual_polish_contracts_are_documented_in_project_guides():
    docs_readme_text = (PROJECT_ROOT / "docs" / "README.md").read_text(encoding="utf-8")
    assert "2026-03-18-workspace-tree-context-dnd-markdown-vault-superseded.md" in docs_readme_text
```

**Step 2: Run test to verify it fails**

Run: `pytest /Users/weijiazhao/Dev/EchoNote/tests/unit/test_i18n_outline_contract.py::test_visual_polish_contracts_are_documented_in_project_guides -v`

Expected: FAIL，因为文档导航尚未指向新计划。

**Step 3: Write minimal implementation**

```python
assert "2026-03-18-workspace-tree-context-dnd-markdown-vault-superseded.md" in docs_readme_text
```

实现要求：
- 在 `docs/README.md` 的 Active Plans 中新增本计划入口，并明确它是树交互与 Markdown Vault 的主 handoff。
- 给 `archive/2026-03-16-workspace-navigation-drag-drop-refactor-superseded.md` 加注释，说明其范围过窄，后续以新计划为准。
- 若执行阶段新增/删除 i18n key、theme role、测试路径，必须同步更新 outline 和说明文档。

**Step 4: Run test to verify it passes**

Run:
- `pytest /Users/weijiazhao/Dev/EchoNote/tests/unit/test_i18n_outline_contract.py -v`
- `pytest /Users/weijiazhao/Dev/EchoNote/tests/unit/test_theme_outline_contract.py -v`
- `pytest /Users/weijiazhao/Dev/EchoNote/tests/unit/test_main_window_shell.py -v`
- `pytest /Users/weijiazhao/Dev/EchoNote/tests/ui/test_workspace_widget.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add /Users/weijiazhao/Dev/EchoNote/docs/README.md /Users/weijiazhao/Dev/EchoNote/docs/plans/archive/2026-03-16-workspace-navigation-drag-drop-refactor-superseded.md /Users/weijiazhao/Dev/EchoNote/CHANGELOG.md /Users/weijiazhao/Dev/EchoNote/tests/unit/test_i18n_outline_contract.py
git commit -m "docs: align workspace tree and markdown vault plan"
```

## 4. 执行期检查清单

1. 不允许在任何新代码里继续硬编码 `default="..."` 的 i18n 兜底字符串。
2. 不允许继续把条目文本长期保存在 `workspace_assets.text_content` 并绕过磁盘文件。
3. 不允许再把用户移动 API 用作系统默认归档 API。
4. 不允许新增第二套右键菜单判定或第二套拖拽判定。
5. 若新增工作台设置页，必须同步更新设置导航文案、i18n outline、对应 UI 测试。

## 5. 验收标准

1. 用户能在树节点上通过右键完成 90% 高频操作，不需要把鼠标移到顶部 icon bar。
2. 从事件/批量任务来源域拖到用户目录时，必定出现复制/移动选择；拖回系统目录时必定被拒绝。
3. 新建、导入、转写、翻译、总结生成的文本都以 `.md` 落在 Vault 中，并与树目录对齐。
4. 重命名/移动条目和文件夹后，磁盘结构与树结构保持一致。
5. theme / i18n / docs / tests 在同一变更中收口，稳定批次全部通过。
