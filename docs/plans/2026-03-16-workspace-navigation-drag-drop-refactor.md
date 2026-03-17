# 工作台导航与拖拽交互改进计划

**日期**: 2026-03-16
**目标**: 移除冗余的视图切换控件，彻底固化单树导航界面，修复项间拖放逻辑，增加具有约束性的跨层拖放提醒机制。

## 1. 痛点分析与需求背景

目前用户在使用工作台主窗体时遭遇到了以下四个体验与功能障碍：

1. **界面元素冗余：** 树形结构上方保留了“结构”与“事件”的切换按钮（Segmented Control）。当“结构”树已经将事件纳入统一层级时，保留独立的事件切换变得既多余又引起困惑。
2. **树形内交互缺陷：** 用户希望在单树内调整条目父级时由于无法命中项而引发放置失败（drop 被拒绝），这种反常识的设定导致拖放重分组功能“不能正常工作”。
3. **关键操作无防呆机制：** 当内容从系统受保护层（事件或批量任务目录下）拖往随意的用户工作台文件夹时，应用由于未提供“复制”亦或“剪切”的预期确认，常常导致用户无意中弄乱原有关联。
4. **安全与限制缺失：** 用户自定义产生的“纯文本条目”不能由于错误的拖入，而非法注入进高度依赖来源数据的“事件 / 批量任务”内发生耦合混乱。

## 2. 核心设计原则与改进方向

遵循第一性原理和 DRY 原则，本次改进方向被界定为“做减法”和“堵漏洞”。本次工作不引入前向兼容代码，抛弃过时的 UI，采取硬切换策略。重点方向如下：

- **移除顶层视图切换开关**：完全消除 `view_mode_switch` 所造成的代码债务。强绑定工作台处于唯一的、清晰的 `structure` Navigator 视角中。
- **重建项级吸附判断 (`item-to-item drop`)**：在 `WorkspaceNavigationTree` 与 `_on_tree_drop_requested` 中，若拖曳内容作用于 `item` 结点上方，树将自动反查该目标条目所隶属的父级 `folder`，将其转译为一个向该文件夹汇集的移动操作，从而彻底解决内拖拽异常。
- **引入双轨询问与拦截体系**：在 `library_panel` 添加拖拽询问逻辑。通过 `source_kind` 以及 `target_kind` 判断源和目标的 `folder_kind`：
  - [拦截] 绝不允许向具有 `event`、`batch_task`、`system_root` 属性的文件夹投放任意类型物件。
  - [弹窗] 当物品明确由 `event` 或 `batch_task` 被拖入了 `inbox` 或 `user`，弹出强制拦截选项框（复制 / 获取副本 抑或 移动 / 剪切离域）。
- **底座追加全量拷贝能效**：为 `WorkspaceManager` 新增 `copy_item_to_folder` 功能。此方法不仅要在 DB 层生成一模一样的新 `WorkspaceItem` 和 `WorkspaceAsset` 对应元数据，还会实际调用 `FileManager` 的 `copy_file` 方法产生安全且独立的文件副本分片。
- **废弃对应的契约测试与翻译表**：与 UI 模式选择器挂钩的 Role 和 Json 数据必须严格清理并通过契约验证。

## 3. 实施清单 (Implementation Checklist)

### 3.1. 域模型与 `WorkspaceManager` 扩军
- [ ] 检查并确保 `FileManager` 存在 `copy_file`，实现对源副本的安全拷贝。
- [ ] 新增 `WorkspaceManager.copy_item_to_folder(item_id, target_folder_id)`：
  1. 获取原对象，分配全新 `uuid`、带 `[副本]` 标识的全新可解析 Title。
  2. 利用安全目录 `get_workspace_path`，为挂载点下的每个 Asset 拷贝文件副本。
  3. 通过 `save()` 保存这些信息并维护回主条目。
  
### 3.2. 视觉清理与模式锁死
- [ ] 从 `ui/workspace/library_panel.py` 去除 `ROLE_WORKSPACE_MODE_BUTTON_GROUP` 强关联的所有初始化代码与部件变量 (`self.structure_view_button`, `self.event_view_button`)。
- [ ] 删除 `self._build_event_tree()` 方法，简化 `set_view_mode` 方法或彻底砍掉其判断，让主窗恒定走 `_build_structure_tree()` 实现渲染。
- [ ] 删除 `constants.py` 中对应的常量。并在 `resources/themes/(light|dark).qss` 和 `theme_outline.json` 中一并剔除遗留定义。
- [ ] 在中、英、法字串库内移除 `workspace.structure_view_short` 等弃用词条。

### 3.3. 树形组件规则松绑与拖放弹窗
- [ ] 在 `WorkspaceNavigationTree` 下对 `dropEvent` 放宽验证，去掉 `source_kind == "item" and target_kind != "folder"` 时即刻引发的 `event.ignore()` 行动。
- [ ] 修改 `_resolve_item_drop_target_folder_id` 使其能够解析被命中的“兄弟项”，自动返回兄弟项所属的 `folder_id`。
- [ ] 修改 `_on_tree_drop_requested` 中条目移动部分代码。在调用 `move_item_to_folder` 前增加判断与弹窗逻辑——询问用户对于特殊的“只读导出项”应当采取哪种动作。同时严打那些目标 `folder_kind` 为非 `user` 类的行动。

## 4. 影响评估与保障
通过 UI、样式表及多语言资源四层契约进行防御。改动涉及到了最高级别的界面框架重修，执行完毕后严格利用 `pytest` 集成套组中的 `test_theme_outline_contract.py` 和 `test_workspace_widget.py` 对改动成果进行无情验证。此工程不携带任何历史包袱代码，且无向下兼顾需求。
