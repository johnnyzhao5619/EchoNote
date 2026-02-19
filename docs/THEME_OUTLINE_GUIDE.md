# Theme Outline 指南

## 目标
- 把主题一致性从“人工记忆”改为“可执行约束”。
- 防止 `light/dark` 样式漂移、遗漏和重复定义。
- 为后续新增主题提供统一落地路径。

## 单一事实来源
- 语义颜色令牌：`/Users/weijiazhao/Dev/EchoNote/ui/common/theme.py`
- 主题大纲合同：`/Users/weijiazhao/Dev/EchoNote/resources/themes/theme_outline.json`
- 主题实现文件：`/Users/weijiazhao/Dev/EchoNote/resources/themes/light.qss`、`/Users/weijiazhao/Dev/EchoNote/resources/themes/dark.qss`
- 守护测试：`/Users/weijiazhao/Dev/EchoNote/tests/unit/test_theme_outline_contract.py`
- 可复用技能模板：`/Users/weijiazhao/Dev/EchoNote/skills/theme-governance/SKILL.md`

## Theme Outline 覆盖范围
- Shell：顶栏、侧栏、状态栏、全局搜索。
- Base Controls：按钮、输入、下拉、日期、滚动条、选择控件。
- 页面语义动作：`dialog`、`calendar`、`timeline`、`realtime`、`settings`、`batch`、`audio player`。
- 角色一致性：所有 UI 代码里声明的 `role` 必须在每个主题里有对应选择器。

## 修改主题的标准流程
1. 先改语义角色，不加页面局部硬编码样式。
2. 同步修改所有主题 QSS（当前是 `light/dark`）。
3. 如果是新语义区域，更新 `theme_outline.json` 的对应 section。
4. 如果新增语义颜色，更新 `ThemeManager.PALETTES`（所有主题同键集合）。
5. 运行 `pytest tests/unit/test_theme_outline_contract.py -q`。
6. 再运行受影响页面测试，确认无回归。

## 新增主题（例如 high-contrast）流程
1. 在 `theme_outline.json` 的 `themes` 中增加主题名。
2. 新建对应 QSS 文件（例如 `high-contrast.qss`），按 outline 完整覆盖所有 section。
3. 在 `ThemeManager.THEMES` 与 `ThemeManager.PALETTES` 中增加同名主题。
4. 保证新主题 palette 的 token 键集合与现有主题完全一致。
5. 运行 Theme Contract 测试，修复所有缺失选择器和角色覆盖项。

## 最佳实践
- Role First：优先 `role` / `variant` / `state`，避免依赖文案、业务文案或临时 `objectName`。
- DRY：同一语义样式只保留一个权威定义入口，删除被覆盖的旧规则。
- 尺寸集中管理：布局和尺寸优先放在 `ui/constants.py`，避免散落硬编码。
- 主题只处理外观：组件行为逻辑不放在 QSS 对应代码分支里。
- 小步收敛：每次变更同时做“规则收敛 + 回归测试”，避免技术债累积。

## 反模式（禁止）
- 只改 `light` 不改 `dark`。
- 新增 `role` 但不更新主题覆盖。
- 在页面代码里通过 `setFixed*` 临时修复视觉问题而不回收到语义样式系统。
- 在多个 QSS 区块重复定义同一语义选择器，依赖“后加载覆盖”碰运气。
