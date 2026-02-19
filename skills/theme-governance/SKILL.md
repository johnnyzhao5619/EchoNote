---
name: theme-governance
description: 统一和治理 EchoNote 的主题样式系统。用于 light/dark 漂移、控件尺寸不一致、样式重复定义、以及新增主题时的标准化落地。
---

# Theme Governance Skill

## 何时使用
- 用户要求统一 `light/dark` 视觉风格、按钮/输入框尺寸、间距和圆角。
- 发现同一语义样式在多个 QSS 段重复定义。
- 新增页面 `role` 后需要确保所有主题都覆盖。
- 计划新增第三主题（例如 high-contrast）并需要完整操作清单。

## 强约束
- 先审查后修改：先定位重复选择器、代码侧尺寸硬编码、缺失 role 覆盖。
- 单一事实来源：样式以语义 `role/variant/state` 为主，不依赖临时 `objectName` 补丁。
- DRY：同一 selector 只保留一个权威块；删除被后置覆盖的旧块。
- 先通过合同测试再收尾：`theme_outline` 与 `theme_contract` 必须通过。

## 标准流程
1. 审查当前状态
   - 扫描代码尺寸硬编码：`rg -n "setFixed|setMinimum|setMaximum|setStyleSheet\\(" ui`
   - 扫描主题重复选择器（建议脚本统计）。
   - 查验 outline 合同文件：`/Users/weijiazhao/Dev/EchoNote/resources/themes/theme_outline.json`
2. 收敛语义入口
   - 先补 `role`（Python 代码），再补 QSS selector。
   - 删除旧对象名规则或重复块，只保留语义规则。
3. 收敛尺寸策略
   - 布局尺寸优先放在 `ui/constants.py`。
   - 页面局部禁止临时 `setFixedWidth/Height` 修样式，优先交给语义 QSS。
4. 同步所有主题
   - 每次改动必须同时更新 `light.qss` 与 `dark.qss`。
   - 如果新增主题，同步更新 `ThemeManager.THEMES/PALETTES`。
5. 回归验证
   - 必跑：`pytest tests/unit/test_theme_outline_contract.py -q`
   - 再跑受影响 UI 测试（按页面选择）。

## 新增主题检查清单
- 在 `theme_outline.json` 的 `themes` 增加主题名。
- 新主题 QSS 覆盖所有 outline section。
- `ThemeManager.PALETTES` 新主题 token 键集合与现有主题完全一致。
- UI 中所有 `role` 在新主题均有 selector。
- 合同测试通过后再交付。

## 完成标准
- `light/dark` 不存在重复 selector 块。
- 所有新增 `role` 在所有主题均覆盖。
- 没有新增样式硬编码或逻辑重复实现。
- 相关测试全部通过。
