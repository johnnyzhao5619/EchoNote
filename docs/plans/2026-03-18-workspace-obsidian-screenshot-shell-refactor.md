# Workspace Obsidian Screenshot Shell Refactor Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 以硬切换方式完成工作台截图对应区域的重构：把当前工作台壳层升级为更接近 Obsidian 的桌面文档导航与页签体验，补齐真实可用的结构/事件双模式、页签堆栈菜单、统一 SVG 图标体系，并清理当前重复与陈旧实现。

**Architecture:** 继续以 `/Users/weijiazhao/Dev/EchoNote/core/workspace/manager.py` 为唯一 workspace 资产与结构语义入口，不新增第二套文档、事件、任务或页签数据流。本次改造只重构 `/Users/weijiazhao/Dev/EchoNote/ui/workspace/*` 壳层、`/Users/weijiazhao/Dev/EchoNote/ui/common/svg_icons.py` 图标注册、以及对应 theme/i18n/test/docs 契约；所有截图相关能力必须走一套共享 action/icon/selection 语义，禁止在 `library_panel.py`、`widget.py`、`detached_document_window.py` 里重复拼装同类逻辑。

**Tech Stack:** Python 3.12, PySide6, SQLite, QSS, i18n JSON, `/Users/weijiazhao/Dev/EchoNote/core/workspace/manager.py`, `/Users/weijiazhao/Dev/EchoNote/ui/workspace/*`, `/Users/weijiazhao/Dev/EchoNote/ui/common/svg_icons.py`, `/Users/weijiazhao/Dev/EchoNote/resources/themes/*`, `/Users/weijiazhao/Dev/EchoNote/resources/translations/*`, `/Users/weijiazhao/Dev/EchoNote/tests/ui/test_workspace_widget.py`, `/Users/weijiazhao/Dev/EchoNote/tests/unit/test_i18n_outline_contract.py`, `/Users/weijiazhao/Dev/EchoNote/tests/unit/test_theme_outline_contract.py`.

---

**Assumption:** 后续执行发生在独立 worktree / 分支；当前变更只新增计划文档并修正文档导航，不直接修改业务代码。

**Scope Note:** 本计划是 `2026-03-15-workspace-redbox-closure-plan.md` 之后的截图壳层跟进，只覆盖 structure/event 暴露、stacked-tabs menu、SVG icon 统一与 editor chrome 层级收紧，不重复定义 red-box 计划里其他布局项。

## 1. 审查结论

### 1.1 截图中的 Obsidian 功能与布局本质

1. 截图的核心不是“长得像浏览器标签页”，而是桌面文档工具的三层信息架构：
   - 窄侧边工具轨负责应用级入口。
   - 左侧导航树负责定位文档集合。
   - 顶部文档页签负责多文档并行与上下文切换。
2. 截图顶部页签区最重要的不是 tab 本身，而是三个配套能力：
   - 当前文档与多文档并行打开。
   - 溢出/堆叠菜单统一管理已打开页签。
   - 右侧少量高频动作通过 icon-only 控件承载，不挤占正文宽度。
3. 截图右上菜单里的“堆叠标签页 / 收藏当前 N 个标签页 / 全部关闭”说明页签区并非单一 close 按钮，而是一个带批量操作的页签管理壳层。
4. 截图里所有动作图标都属于同一视觉语言，意味着图标应当是“系统级语义资产”，而不是分散在不同控件里各自硬编码。

### 1.2 当前 EchoNote 相关实现的真实现状

1. 数据与结构语义已经具备较好的基础：
   - `/Users/weijiazhao/Dev/EchoNote/core/workspace/manager.py` 已经落地 `inbox / event / batch_task` 文件夹语义。
   - `/Users/weijiazhao/Dev/EchoNote/core/workspace/vault_layout.py` 已经把 Vault 路径和系统文件夹对齐。
   - `source_event_id` / `source_task_id` 已经与结构归属解耦。
2. 当前截图区域真正的问题不在数据层，而在壳层交互未收口：
   - `/Users/weijiazhao/Dev/EchoNote/ui/workspace/library_panel.py` 的 `current_view_mode()` 目前硬编码返回 `"structure"`，事件视图数据通路存在但 UI 入口没落地。
   - `/Users/weijiazhao/Dev/EchoNote/ui/workspace/widget.py` 的页签右侧动作仍是 `ToolButtonTextOnly`，与截图中的 icon-only chrome 明显不一致。
   - `/Users/weijiazhao/Dev/EchoNote/ui/workspace/widget.py` 的页签关闭按钮仍直接 `setText("x")`，不是 SVG 图标。
   - `/Users/weijiazhao/Dev/EchoNote/ui/workspace/library_panel.py` 仍通过 `_tree_icon_svg()` 内嵌 SVG 字符串自绘树节点图标，没有复用 `/Users/weijiazhao/Dev/EchoNote/ui/common/svg_icons.py`。
   - 当前没有“堆叠标签页 / 已打开页签菜单 / 关闭其他标签页 / 全部关闭”这类页签管理能力。
3. 文档与代码存在偏差：
   - `/Users/weijiazhao/Dev/EchoNote/docs/README.md` 当前写着 workspace 已具备 structure/event mode switch，但代码里该开关并未真正暴露。
4. 存在明显 DRY 债务：
   - header action 图标、tree 图标、tab close 图标分散在多个模块。
   - 主工作台与独立文档窗口的顶部动作语义接近，但未抽象为同一套 icon/action 规范。

### 1.3 第一性原理判断

1. EchoNote 不需要照搬 Obsidian 的插件、双链、Canvas，但必须借鉴它对“导航上下文”和“多文档切换”的处理方式。
2. 当前最有价值的重构目标不是继续调 spacing，而是把截图所代表的壳层交互闭环做完整：
   - 真正可切换的结构/事件导航。
   - 可管理的文档页签。
   - 一套统一 SVG 图标系统。
   - 文档导航、页签管理、正文编辑之间清晰分层。
3. 任何新能力都不能建立第二套状态源。页签打开状态、当前文档、事件筛选、图标语义都必须以现有 workspace 结构为基础统一实现。

## 2. 需求定义

### 2.1 产品需求

1. 工作台必须提供真实可用的 `structure` / `event` 双模式导航，而不是只有结构树。
2. 文档页签区必须支持：
   - 多文档并行打开。
   - 当前文档高亮。
   - 单个标签关闭。
   - 页签堆栈菜单。
   - 关闭当前 / 关闭其他 / 全部关闭。
3. 工作台顶部壳层动作必须统一为 SVG icon-only 交互，不再使用文字按钮模拟工具栏。
4. 左侧导航头部必须只承载高频动作和当前上下文，不引入装饰性或无后端支撑的入口。
5. 事件视图必须以事件为导航单位，而不是另一种排序结果。
6. 所有截图范围内图标必须来自统一 SVG 注册中心，禁止 icon font、emoji、纯文本 glyph、模块内联 SVG 重复实现。

### 2.2 UI / 交互需求

1. 左侧导航头：
   - 保留导入文档、新建笔记、新建文件夹、重命名、删除这组高频结构动作。
   - 新增 structure/event segmented switch 或等价 icon toggle。
   - 行为必须随当前 mode 和 selection 更新 enable/disable 状态。
2. 左侧树：
   - `structure` 模式展示现有单树结构。
   - `event` 模式展示事件分组节点，节点下挂对应工作台条目。
   - 未关联事件条目必须有稳定分组入口。
3. 页签区：
   - 所有右侧动作改为 icon-only。
   - 活动态、hover、overflow 状态必须在 light/dark 双主题下一致。
   - 页签菜单必须显示当前已打开文档列表，并标识当前文档。
4. 文档舞台：
   - 页签名称只承载文档标题，不拼技术性 role 文案。
   - 资产 role 信息下沉到 editor 内部的 asset tabs / context meta。
5. 独立窗口：
   - 继续保留，但动作语言和图标系统与主工作台一致。

### 2.3 技术需求

1. `ui/common/svg_icons.py` 成为唯一 workspace shell 图标注册入口。
2. 所有 workspace shell action 通过统一命名 icon token 调用，禁止模块内部再写一套 SVG 模板。
3. i18n 只负责 tooltip / accessible name / menu 文案，不负责承载伪图标字符。
4. 新增 role / i18n key 时必须同步更新：
   - `/Users/weijiazhao/Dev/EchoNote/resources/themes/theme_outline.json`
   - `/Users/weijiazhao/Dev/EchoNote/resources/translations/i18n_outline.json`
   - `/Users/weijiazhao/Dev/EchoNote/resources/translations/zh_CN.json`
   - `/Users/weijiazhao/Dev/EchoNote/resources/translations/en_US.json`
   - `/Users/weijiazhao/Dev/EchoNote/resources/translations/fr_FR.json`

### 2.4 非目标

1. 不实现 bookmark/starred/stash/pin 的持久化模型。
2. 不实现页签会话持久化与 workspace profile。
3. 不新增第二个搜索入口来复制主壳层 `Ctrl+K` 全局搜索。
4. 不做兼容旧 UI 的迁移层；直接硬切换。

## 3. 假设与建议

1. 假设：截图右上“收藏当前 N 个标签页”对应的是页签集合/堆栈类能力，而不是简单 bookmark。
   - 建议：首期只实现“已打开页签菜单 + 批量关闭”，不实现持久化收藏。
   - 理由：当前仓库没有“收藏页签”数据模型，强上只会引入半成品状态。
2. 假设：工作台不应新增第二个局部搜索 icon 来模仿截图。
   - 建议：首期不复制搜索 icon；若后续确定需要局部搜索，应实现真正的 tree/item filter，而不是装饰按钮。
   - 理由：应用壳层已经有全局搜索，重复入口会制造双重心智。
3. 假设：事件视图入口必须落实到当前 UI，而不是继续停留在数据层 helper。
   - 建议：直接移除当前库中与“未来会支持 event mode”相关但未落地的死角状态和未使用导入。
   - 理由：当前 `current_view_mode()` 硬编码为 `structure`，继续保留半成品只会误导文档与后续开发。

## 4. 优化方向

### 4.1 产品方向

1. 从“功能存在”升级为“功能有明确壳层位置”。
2. 从“能打开多个文档”升级为“能管理多个文档上下文”。
3. 从“事件数据已关联”升级为“事件视图对用户可见可操作”。

### 4.2 UI 方向

1. 用少量高辨识度 SVG icon 替代文本按钮。
2. 让页签、导航头、树节点使用同一套图标语言。
3. 降低工具控件对正文宽度的侵占，恢复桌面文档工作区的重心。

### 4.3 技术方向

1. 删除 `library_panel.py` 内联 SVG。
2. 删除页签关闭按钮的文本 glyph。
3. 把 workspace shell action/icon 命名统一收敛，避免后续新增按钮时继续分叉。
4. 修正文档与代码现实不一致的问题，避免计划与真实实现错位。

## 5. 实施顺序总览

1. 先统一图标体系，清掉最明显的重复实现和文本 glyph 债务。
2. 再把结构/事件双模式真正落地到导航头和树。
3. 然后补齐文档页签堆栈菜单与批量管理能力。
4. 最后收 editor chrome、契约、文档与回归批次。

### Task 1: 建立统一的 Workspace Shell SVG 图标注册并移除局部重复实现

**Files:**
- Modify: `/Users/weijiazhao/Dev/EchoNote/ui/common/svg_icons.py`
- Modify: `/Users/weijiazhao/Dev/EchoNote/ui/workspace/library_panel.py`
- Modify: `/Users/weijiazhao/Dev/EchoNote/ui/workspace/widget.py`
- Modify: `/Users/weijiazhao/Dev/EchoNote/ui/workspace/detached_document_window.py`
- Test: `/Users/weijiazhao/Dev/EchoNote/tests/ui/test_workspace_widget.py`

**Step 1: Write the failing test**

```python
def test_workspace_shell_uses_svg_icons_instead_of_text_glyphs(
    qapp, mock_i18n, workspace_manager
):
    widget = WorkspaceWidget(workspace_manager, mock_i18n)

    close_button = widget.document_tabs.tabBar().tabButton(
        0,
        widget.document_tabs.tabBar().ButtonPosition.RightSide,
    )

    assert not widget.library_panel.import_document_button.icon().isNull()
    assert not widget.open_in_window_button.icon().isNull()
    assert not widget.inspector_toggle_button.icon().isNull()
    assert close_button is not None
    assert not close_button.icon().isNull()
    assert close_button.text() == ""
    assert widget.open_in_window_button.text() == ""
    assert widget.inspector_toggle_button.text() == ""
```

**Step 2: Run test to verify it fails**

Run: `pytest /Users/weijiazhao/Dev/EchoNote/tests/ui/test_workspace_widget.py::test_workspace_shell_uses_svg_icons_instead_of_text_glyphs -v`

Expected: FAIL，因为当前 `workspace-tab-close` 仍使用 `"x"` 文本，tab action 仍是 text-only，tree 图标也未统一走共享 SVG 注册。

**Step 3: Write minimal implementation**

```python
_SVG_TEMPLATES.update(
    {
        "workspace_tab_close": "...",
        "workspace_open_window": "...",
        "workspace_inspector": "...",
        "workspace_tabs_menu": "...",
        "workspace_structure_mode": "...",
        "workspace_event_mode": "...",
        "workspace_folder": "...",
        "workspace_folder_inbox": "...",
        "workspace_folder_event_root": "...",
        "workspace_folder_batch_root": "...",
        "workspace_folder_event": "...",
        "workspace_item": "...",
    }
)
```

实现要求：
- `/Users/weijiazhao/Dev/EchoNote/ui/common/svg_icons.py` 成为唯一 workspace shell 图标来源。
- 删除 `/Users/weijiazhao/Dev/EchoNote/ui/workspace/library_panel.py::_tree_icon_svg()` 这类模块内联 SVG 构造。
- `QToolButton[role="workspace-tab-close"]` 改为真正 SVG icon，不允许文本 `"x"` 兜底。
- `widget.py` 与 `detached_document_window.py` 的 tab action 统一改为 icon-only，但必须保留 tooltip 和 accessible name。

**Step 4: Run test to verify it passes**

Run: `pytest /Users/weijiazhao/Dev/EchoNote/tests/ui/test_workspace_widget.py -k "svg_icons or document_tabs_expose_semantic_roles or navigator_header_actions" -v`

Expected: PASS

**Step 5: Commit**

```bash
git add /Users/weijiazhao/Dev/EchoNote/ui/common/svg_icons.py /Users/weijiazhao/Dev/EchoNote/ui/workspace/library_panel.py /Users/weijiazhao/Dev/EchoNote/ui/workspace/widget.py /Users/weijiazhao/Dev/EchoNote/ui/workspace/detached_document_window.py /Users/weijiazhao/Dev/EchoNote/tests/ui/test_workspace_widget.py
git commit -m "feat: unify workspace shell svg icons"
```

### Task 2: 把 Structure / Event 双模式真正落地到导航头和树

**Files:**
- Modify: `/Users/weijiazhao/Dev/EchoNote/ui/workspace/library_panel.py`
- Modify: `/Users/weijiazhao/Dev/EchoNote/ui/workspace/widget.py`
- Modify: `/Users/weijiazhao/Dev/EchoNote/core/workspace/manager.py`
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
def test_workspace_library_panel_can_switch_between_structure_and_event_modes(
    qapp, mock_i18n, workspace_manager
):
    event = CalendarEvent(
        title="Design Review",
        start_time="2026-03-18T09:00:00+00:00",
        end_time="2026-03-18T10:00:00+00:00",
    )
    event.save(workspace_manager.db)
    event_note_id = workspace_manager.create_note(title="Review Notes", event_id=event.id)

    widget = WorkspaceWidget(workspace_manager, mock_i18n)
    widget.library_panel.event_view_button.click()
    qapp.processEvents()

    assert widget.library_panel.current_view_mode() == "event"
    assert widget.library_panel.find_event_node(event.id) is not None

    widget.library_panel.select_event(event.id)
    qapp.processEvents()

    assert widget.current_item_id() == event_note_id
    assert not widget.library_panel.new_folder_button.isEnabled()
```

**Step 2: Run test to verify it fails**

Run: `pytest /Users/weijiazhao/Dev/EchoNote/tests/ui/test_workspace_widget.py::test_workspace_library_panel_can_switch_between_structure_and_event_modes -v`

Expected: FAIL，因为当前 `current_view_mode()` 被硬编码为 `structure`，事件视图切换按钮和事件节点查找都不存在。

**Step 3: Write minimal implementation**

```python
class WorkspaceLibraryPanel(BaseWidget):
    def set_view_mode(self, mode: str) -> None:
        self._view_mode = mode
        self.refresh_navigation()
        self.view_mode_changed.emit(mode)
```

实现要求：
- 为 `library_panel.py` 增加真实的 `self._view_mode` 状态，删除“只有 structure mode 的伪接口”。
- 头部新增 structure/event 模式切换控件，使用 SVG icon + tooltip，不用第二套文本按钮。
- `refresh_navigation()` 根据 mode 分支到 `_build_structure_tree()` / `_build_event_tree()`。
- `event` 模式必须复用 `/Users/weijiazhao/Dev/EchoNote/core/workspace/manager.py::get_event_navigation_entries()`，不要再自己拼 SQL。
- `event` 模式下 folder 管理动作禁用或隐藏，只保留与当前选择兼容的操作。
- 清理 `library_panel.py` 中与旧半成品 view mode 相关的死代码和未使用导入。

**Step 4: Run test to verify it passes**

Run:
- `pytest /Users/weijiazhao/Dev/EchoNote/tests/ui/test_workspace_widget.py -k "structure_and_event_modes or event_mode" -v`
- `pytest /Users/weijiazhao/Dev/EchoNote/tests/unit/test_i18n_outline_contract.py -v`
- `pytest /Users/weijiazhao/Dev/EchoNote/tests/unit/test_theme_outline_contract.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add /Users/weijiazhao/Dev/EchoNote/ui/workspace/library_panel.py /Users/weijiazhao/Dev/EchoNote/ui/workspace/widget.py /Users/weijiazhao/Dev/EchoNote/core/workspace/manager.py /Users/weijiazhao/Dev/EchoNote/ui/constants.py /Users/weijiazhao/Dev/EchoNote/resources/themes/light.qss /Users/weijiazhao/Dev/EchoNote/resources/themes/dark.qss /Users/weijiazhao/Dev/EchoNote/resources/themes/theme_outline.json /Users/weijiazhao/Dev/EchoNote/resources/translations/i18n_outline.json /Users/weijiazhao/Dev/EchoNote/resources/translations/zh_CN.json /Users/weijiazhao/Dev/EchoNote/resources/translations/en_US.json /Users/weijiazhao/Dev/EchoNote/resources/translations/fr_FR.json /Users/weijiazhao/Dev/EchoNote/tests/ui/test_workspace_widget.py /Users/weijiazhao/Dev/EchoNote/tests/unit/test_i18n_outline_contract.py /Users/weijiazhao/Dev/EchoNote/tests/unit/test_theme_outline_contract.py
git commit -m "feat: add real workspace event navigation mode"
```

### Task 3: 重构文档页签壳层并补齐“堆叠标签页”菜单

**Files:**
- Modify: `/Users/weijiazhao/Dev/EchoNote/ui/workspace/widget.py`
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
def test_workspace_tab_strip_exposes_stacked_tabs_menu_and_batch_close_actions(
    qapp, mock_i18n, workspace_manager
):
    first_id = workspace_manager.list_items()[0].id
    second_id = workspace_manager.create_note(title="Plan")
    third_id = workspace_manager.create_note(title="Spec")

    widget = WorkspaceWidget(workspace_manager, mock_i18n)
    widget.open_item(first_id)
    widget.open_item(second_id)
    widget.open_item(third_id)

    menu = widget._build_tab_stack_menu()
    action_texts = [action.text() for action in menu.actions() if action.text()]

    assert widget.tab_stack_button is not None
    assert "Plan" in action_texts
    assert "Spec" in action_texts
    assert mock_i18n.t("workspace.close_other_tabs") in action_texts
    assert mock_i18n.t("workspace.close_all_tabs") in action_texts
```

**Step 2: Run test to verify it fails**

Run: `pytest /Users/weijiazhao/Dev/EchoNote/tests/ui/test_workspace_widget.py::test_workspace_tab_strip_exposes_stacked_tabs_menu_and_batch_close_actions -v`

Expected: FAIL，因为当前没有 `tab_stack_button`，也没有页签堆叠菜单和批量关闭能力。

**Step 3: Write minimal implementation**

```python
def _build_tab_stack_menu(self) -> QMenu:
    menu = QMenu(self)
    ...
    return menu
```

实现要求：
- `widget.py` 页签右侧角标动作统一为：
  - inspector toggle
  - open in new window
  - stacked tabs menu
- stacked tabs menu 至少支持：
  - 列出所有已打开标签页
  - 当前标签页打勾
  - 关闭当前
  - 关闭其他
  - 全部关闭
- 不实现“收藏当前 N 个标签页”的持久化版本；若产品后续确认需要，再单独设计状态模型。
- 独立文档窗口继续保留 inspector toggle，但不复制 stacked tabs menu。
- 页签 close、corner actions、menu labels 全部走 i18n + SVG；不得出现 icon font 或文本图形字符。

**Step 4: Run test to verify it passes**

Run:
- `pytest /Users/weijiazhao/Dev/EchoNote/tests/ui/test_workspace_widget.py -k "stacked_tabs or document_tabs or toggle_inspector_panel" -v`
- `pytest /Users/weijiazhao/Dev/EchoNote/tests/unit/test_i18n_outline_contract.py -v`
- `pytest /Users/weijiazhao/Dev/EchoNote/tests/unit/test_theme_outline_contract.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add /Users/weijiazhao/Dev/EchoNote/ui/workspace/widget.py /Users/weijiazhao/Dev/EchoNote/ui/workspace/detached_document_window.py /Users/weijiazhao/Dev/EchoNote/ui/constants.py /Users/weijiazhao/Dev/EchoNote/resources/themes/light.qss /Users/weijiazhao/Dev/EchoNote/resources/themes/dark.qss /Users/weijiazhao/Dev/EchoNote/resources/themes/theme_outline.json /Users/weijiazhao/Dev/EchoNote/resources/translations/i18n_outline.json /Users/weijiazhao/Dev/EchoNote/resources/translations/zh_CN.json /Users/weijiazhao/Dev/EchoNote/resources/translations/en_US.json /Users/weijiazhao/Dev/EchoNote/resources/translations/fr_FR.json /Users/weijiazhao/Dev/EchoNote/tests/ui/test_workspace_widget.py /Users/weijiazhao/Dev/EchoNote/tests/unit/test_i18n_outline_contract.py /Users/weijiazhao/Dev/EchoNote/tests/unit/test_theme_outline_contract.py
git commit -m "feat: add workspace stacked tabs menu"
```

### Task 4: 收紧 Editor Chrome 信息层级，避免页签与文档上下文重复

**Files:**
- Modify: `/Users/weijiazhao/Dev/EchoNote/ui/workspace/editor_panel.py`
- Modify: `/Users/weijiazhao/Dev/EchoNote/ui/workspace/widget.py`
- Modify: `/Users/weijiazhao/Dev/EchoNote/ui/workspace/inspector_panel.py`
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
def test_workspace_editor_chrome_uses_compact_title_and_asset_context(
    qapp, mock_i18n, workspace_manager
):
    item_id = workspace_manager.list_items()[0].id
    workspace_manager.save_text_asset(item_id, "translation", "translated")
    widget = WorkspaceWidget(workspace_manager, mock_i18n)
    widget.open_item(item_id)

    tab_text = widget.document_tabs.tabText(widget.document_tabs.currentIndex())

    assert tab_text == "Sprint Sync"
    assert widget.editor_panel.document_title_label.text() == "Sprint Sync"
    assert widget.editor_panel.asset_tabs.count() >= 2
    assert ":" not in widget.editor_panel.asset_tabs.tabText(0)
```

**Step 2: Run test to verify it fails**

Run: `pytest /Users/weijiazhao/Dev/EchoNote/tests/ui/test_workspace_widget.py::test_workspace_editor_chrome_uses_compact_title_and_asset_context -v`

Expected: FAIL，因为当前 asset tabs 采用 `Role: FileName` 复合标签，信息层级混在一起。

**Step 3: Write minimal implementation**

```python
def _label_for_asset(self, asset) -> str:
    return WORKSPACE_ASSET_LABELS.get(asset.asset_role, asset.asset_role)
```

实现要求：
- 页签名只显示文档标题。
- `editor_panel.py` 的 asset tabs 只显示资产语义名，例如 `Transcript / Translation / Summary`，不要在 tab 上再拼文件名。
- 文件名、来源任务、事件、更新时间等上下文信息下沉到 `document_context_label` 或 inspector，不与顶层页签重复。
- 继续复用现有 metadata helper，不允许再造第二套元数据拼接逻辑。

**Step 4: Run test to verify it passes**

Run:
- `pytest /Users/weijiazhao/Dev/EchoNote/tests/ui/test_workspace_widget.py -k "editor_chrome or inspector or current_asset_role" -v`
- `pytest /Users/weijiazhao/Dev/EchoNote/tests/unit/test_i18n_outline_contract.py -v`
- `pytest /Users/weijiazhao/Dev/EchoNote/tests/unit/test_theme_outline_contract.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add /Users/weijiazhao/Dev/EchoNote/ui/workspace/editor_panel.py /Users/weijiazhao/Dev/EchoNote/ui/workspace/widget.py /Users/weijiazhao/Dev/EchoNote/ui/workspace/inspector_panel.py /Users/weijiazhao/Dev/EchoNote/ui/constants.py /Users/weijiazhao/Dev/EchoNote/resources/themes/light.qss /Users/weijiazhao/Dev/EchoNote/resources/themes/dark.qss /Users/weijiazhao/Dev/EchoNote/resources/themes/theme_outline.json /Users/weijiazhao/Dev/EchoNote/resources/translations/i18n_outline.json /Users/weijiazhao/Dev/EchoNote/resources/translations/zh_CN.json /Users/weijiazhao/Dev/EchoNote/resources/translations/en_US.json /Users/weijiazhao/Dev/EchoNote/resources/translations/fr_FR.json /Users/weijiazhao/Dev/EchoNote/tests/ui/test_workspace_widget.py /Users/weijiazhao/Dev/EchoNote/tests/unit/test_i18n_outline_contract.py /Users/weijiazhao/Dev/EchoNote/tests/unit/test_theme_outline_contract.py
git commit -m "feat: tighten workspace editor chrome hierarchy"
```

### Task 5: 同步收口文档、契约与稳定回归批次

**Files:**
- Modify: `/Users/weijiazhao/Dev/EchoNote/docs/README.md`
- Modify: `/Users/weijiazhao/Dev/EchoNote/docs/plans/2026-03-18-workspace-obsidian-screenshot-shell-refactor.md`
- Test: `/Users/weijiazhao/Dev/EchoNote/tests/unit/test_main_window_shell.py`
- Test: `/Users/weijiazhao/Dev/EchoNote/tests/ui/test_workspace_widget.py`
- Test: `/Users/weijiazhao/Dev/EchoNote/tests/unit/test_i18n_outline_contract.py`
- Test: `/Users/weijiazhao/Dev/EchoNote/tests/unit/test_theme_outline_contract.py`

**Step 1: Write the failing test**

```python
def test_workspace_docs_point_to_current_screenshot_shell_plan():
    readme = Path("/Users/weijiazhao/Dev/EchoNote/docs/README.md").read_text(encoding="utf-8")
    assert "2026-03-18-workspace-obsidian-screenshot-shell-refactor.md" in readme
```

**Step 2: Run test to verify it fails**

Run: `pytest /Users/weijiazhao/Dev/EchoNote/tests/unit/test_main_window_shell.py -k "dummy" -v`

Expected: 当前无需真正新增 docs pytest；这里的“失败验证”用人工 review 替代，因为仓库尚无文档链接契约测试。

**Step 3: Write minimal implementation**

```markdown
- Workspace screenshot shell note: ...
- Active plan: plans/2026-03-18-workspace-obsidian-screenshot-shell-refactor.md
```

实现要求：
- `/Users/weijiazhao/Dev/EchoNote/docs/README.md` 必须修正“当前已具备 structure/event switch”的不准确信息。
- 新计划必须进入 `Active Plans` 列表，并明确它聚焦截图对应的 shell chrome，而不是重复旧 red-box 计划。
- 回归说明必须继续拆分为稳定批次，不允许写成一条大而全的 pytest 命令。

**Step 4: Run test to verify it passes**

Run:
- `pytest /Users/weijiazhao/Dev/EchoNote/tests/unit/test_main_window_shell.py -v`
- `pytest /Users/weijiazhao/Dev/EchoNote/tests/ui/test_workspace_widget.py -v`
- `pytest /Users/weijiazhao/Dev/EchoNote/tests/unit/test_i18n_outline_contract.py -v`
- `pytest /Users/weijiazhao/Dev/EchoNote/tests/unit/test_theme_outline_contract.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add /Users/weijiazhao/Dev/EchoNote/docs/README.md /Users/weijiazhao/Dev/EchoNote/docs/plans/2026-03-18-workspace-obsidian-screenshot-shell-refactor.md
git commit -m "docs: align workspace screenshot shell plan"
```

## 6. 执行检查清单

1. 确认工作台所有截图范围内 icon 均来自 `/Users/weijiazhao/Dev/EchoNote/ui/common/svg_icons.py`。
2. 确认 `library_panel.py` 不再内联 SVG 字符串。
3. 确认 `widget.py` / `detached_document_window.py` 不再使用文本 glyph 充当关闭按钮。
4. 确认 `structure` / `event` 模式是真实可切换状态，而不是文档描述。
5. 确认新增 role / i18n key 已同步 light/dark/theme_outline/i18n_outline/三语 locale。
6. 确认回归批次至少执行：
   - `pytest /Users/weijiazhao/Dev/EchoNote/tests/unit/test_main_window_shell.py -v`
   - `pytest /Users/weijiazhao/Dev/EchoNote/tests/ui/test_workspace_widget.py -v`
   - `pytest /Users/weijiazhao/Dev/EchoNote/tests/unit/test_i18n_outline_contract.py -v`
   - `pytest /Users/weijiazhao/Dev/EchoNote/tests/unit/test_theme_outline_contract.py -v`
