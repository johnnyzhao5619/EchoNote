# EchoNote 前端 UI/UX 优化与重构计划

## 目标与约束
- 目标：将桌面端 UI 壳层优化为更接近 Docker Desktop 的信息架构与视觉语言，同时保持业务功能稳定可用。
- 约束：
  - 不引入 mock 数据。
  - 不重复实现同一逻辑。
  - 避免硬编码，优先常量与配置。
  - 不做向后兼容适配与迁移层。
  - 专注可维护的功能实现，避免过度工程化。

## 全量审查结论（摘要）
- 桌面端主入口为 `ui/`，官网在 `echonote-landing/`，本次 Docker 风格优化应聚焦 `ui/`。
- 主要问题：
  - 导航配置在多处重复定义（`main_window` 与 `sidebar`）。
  - 主窗口缺少统一壳层（顶栏/状态栏），全局入口不集中。
  - 主题文件历史样式层叠过多，局部存在同语义重复定义。
  - 运行状态统计逻辑分散，维护时易产生行为偏差。

## 设计原则映射
- 系统性思维：先统一壳层与导航，再处理页面内细节。
- 第一性原理：从“可导航、可感知状态、可快速定位功能”这三个核心能力出发，不被旧样式结构限制。
- DRY：抽取统一导航配置、统一状态计算逻辑、统一壳层常量。
- 长远考虑：减少 QSS 重复定义与入口分叉，降低后续主题和交互演进成本。

## 分阶段计划

### Phase 1（已完成）
- 统一导航配置源
  - 新增 `ui/navigation.py`，集中页面、文案、图标、快捷键。
- 主壳层重构
  - 主窗口改为顶栏 + 内容区 + 状态栏结构。
  - 新增全局搜索入口（Ctrl+K）与底部实时状态。
- 交互一致性
  - 页面切换统一同步侧栏高亮，避免入口差异。

### Phase 2（已完成）
- 主题技术债清理
  - 在主题文件中移除与新壳层重复的旧 `#sidebar`/`#page_title` 定义。
  - 保留并增强壳层覆盖规则，补齐 `:pressed` 交互反馈。
- 逻辑去重
  - 合并 MainWindow 里运行任务判断与计数重复逻辑，统一数据来源。

### Phase 3（进行中）
- 页面级结构统一
  - 已完成：抽取通用页面标题构建函数，统一 `batch/timeline/settings` 标题创建流程。
  - 已完成：抽取通用页面根布局构建函数，统一 `batch/timeline/settings/realtime/calendar` 根布局。
  - 已完成：抽取通用行容器构建函数，并统一 `realtime/calendar` 头部与工具栏容器创建方式。
  - 已完成：`batch` 工具栏按钮构建逻辑抽取为统一方法，移除重复创建代码。
  - 已完成：`timeline` 筛选项定义改为单一配置源，初始化与翻译更新复用同一逻辑。
  - 已完成：`settings` 未保存更改确认流程抽取为单一方法，取消按钮与离开校验复用。
- 搜索能力增强（轻量）
  - 已完成：全局搜索支持“设置页子分类”直达（如外观/语言/实时）。
- 主题分层
  - 按壳层 / 通用控件 / 业务页面拆分主题片段（可保持最终编译产物为单文件）。

### Phase 4（进行中）
- 代码清理
  - 移除确认无使用路径的旧样式/旧对象名定义。
  - 进行中：收敛残余硬编码布局数值到 `ui/constants.py`。
  - 已完成：模型管理页关键尺寸常量（卡片间距、按钮宽度、对话框最小尺寸）统一收敛到 `ui/constants.py`。
  - 已完成：实时录音可视化区域最大高度常量化，移除页面内裸值。
  - 已完成：错误弹窗详情区高度、OAuth 说明区高度、事件描述区高度统一常量化。
  - 已完成：实时录音文本工具栏标题/词数区间距常量化。
  - 已完成：引入通用 `ZERO_MARGINS` / `ZERO_SPACING` 与日历网格间距常量，替换多处页面内裸值。
  - 已完成：清理 `ui/base_widgets.py` 中全仓未引用的辅助方法/类（陈旧标签辅助与布局拼接样板）。
  - 已完成：模型管理样式从“按钮文案匹配”切换为语义 `role` 匹配，移除多语言文案硬编码依赖。
  - 已完成：`model_config_dialog` 字段标签样式从文本匹配切换为语义 `role`，避免文本耦合。
  - 已完成：侧栏壳层样式选择器从泛化 `#sidebar QPushButton` 收敛到 `role="sidebar-nav-button"`，降低误作用面。
  - 已完成：清理 `ui/` 内所有 `margins=(0,0,0,0)` 调用点，统一改用 `ZERO_MARGINS` 常量。
  - 已完成：移除无引用 `QLabel#subtitle_label` 主题选择器，并将事件卡标题样式从 `#title_label` 切换到语义 `role="event-title"`。
- 验证闭环
  - 已完成：新增主壳层搜索测试（含设置子页直达）。
  - 已完成：补齐状态栏显示与快捷键切换的行为测试。
  - 已完成：补齐时间线筛选项翻译更新与选中态保持测试。
  - 已完成：新增模型管理页语义 `role` 样式钩子测试（下载/删除按钮、配置表单标签）。
  - 已完成：新增日历对话框布局常量测试与错误弹窗详情高度常量测试。
  - 已完成：新增时间线事件卡标题语义 `role` 钩子测试，防止回退到旧对象名样式耦合。

### Phase 5（本轮完成）
- 统一 light/dark 设计语言（Docker Desktop 风格对齐）
  - 在 `resources/themes/light.qss` 与 `resources/themes/dark.qss` 末尾新增统一“设计系统覆盖层”，统一按钮、输入框、列表、表格、分组、标签页、滚动条、状态标签等基础元件样式。
  - 使用语义属性优先（`variant` / `role` / `state`），减少对象名样式耦合，确保跨页面一致性。
- 语义化与去硬编码
  - `ui/base_widgets.py` 中按钮创建逻辑统一补充 `variant` 属性（default/primary/secondary），形成单一入口。
  - `ui/base_widgets.py` 布局默认边距统一改为 `ZERO_MARGINS`，消除重复裸值。
  - `ui/batch_transcribe/search_widget.py` 大文档阈值改为复用 `ui/constants.py` 常量，移除重复常量定义。
- 主题色板一致性
  - `ui/common/theme.py` 的 light/dark 调色板已与壳层 QSS 同步，避免主题管理器与样式文件颜色语义分叉。

### 下一阶段（建议）
- 继续将历史对象名选择器迁移到语义属性选择器（优先 `timeline` / `batch` / `calendar` 的动作按钮）。
- 逐步清理被覆盖且无调用路径的旧 QSS 规则，降低主题维护成本并缩短样式回归定位时间。

### Phase 6（本轮继续完成）
- 语义样式钩子扩展
  - `batch` 工具栏按钮新增统一语义角色：`role="toolbar-secondary-action"`。
  - `calendar` 视图切换按钮新增统一语义角色：`role="calendar-view-toggle"`。
  - `timeline` 事件卡动作按钮新增语义角色：`timeline-recording-action` / `timeline-transcript-action` / `timeline-translation-action`。
  - `timeline` 转录查看器动作按钮新增语义角色：`timeline-copy-action` / `timeline-export-action`。
- 主题覆盖层增强
  - 在 light/dark 统一覆盖层中补齐上述语义角色样式，并保留对象名兜底选择器，确保渐进式去耦合。
- 测试补强
  - 增加语义角色回归测试，防止后续重构回退到对象名强耦合。

### Phase 7（本轮继续完成）
- 冗余样式清理
  - 移除 light/dark 中已被统一覆盖层接管的旧对象名规则块（`view_button`、`import_*`、`timeline_*` 动作按钮），减少重复定义。
  - 对已迁移按钮移除无必要 `objectName` 绑定，转为仅依赖语义 `role`，降低样式耦合面。
- 回归保护
  - 新增 `calendar_hub` 视图切换按钮语义角色测试，防止后续回退到对象名样式路径。

### Phase 8（本轮继续完成）
- 语义化去耦合扩展
  - `batch` 搜索条动作按钮（上一条/下一条/关闭）改为语义 `role`（`search-nav-action` / `search-close-action`），移除按钮 `objectName` 依赖。
  - `batch` 转录查看器工具栏改为语义 `role`（编辑/导出/复制/搜索 + 工具栏容器），编辑态统一通过 `state` 属性表达（`active/default`）。
  - `batch` 任务项动作按钮改为语义 `role`（start/pause/cancel/delete/view/export/retry），移除按钮 `objectName` 绑定。
- 主题规则收敛
  - light/dark 中上述区域的选择器从 `#objectName` 全量切换为 `role/state` 语义选择器，避免同语义跨页面重复实现。
- 回归测试补强
  - 新增 `search_widget` 语义角色测试。
  - 新增 `task_item` 语义角色测试。
  - 新增 `batch transcript viewer dialog` 工具栏语义角色与编辑态 `state` 测试。

### Phase 9（本轮继续完成）
- 配色与按钮系统优化（light/dark 同步）
  - 统一覆盖层中的按钮体系升级为更清晰主次层级：默认/primary/secondary/danger 的亮暗配色与交互状态（hover/pressed/focus/disabled）整体重整。
  - 提升按钮可读性和点击反馈：统一圆角、内边距、最小尺寸与焦点边框，减少视觉抖动与状态歧义。
- 页面动作语义强化
  - 设置页底部动作按钮语义化：`save` 归一为 `primary`，`cancel/reset` 归一为 `secondary`，并补充稳定 `role` 钩子（`settings-save-action` / `settings-cancel-action` / `settings-reset-action`）。
  - 统一补齐 `batch viewer/search/task` 动作按钮在覆盖层中的语义样式规则，避免散落在历史样式段中。
- 冗余清理（DRY）
  - 删除 light/dark 历史区块中与统一覆盖层重复的 `search` 与 `task-item` 按钮规则，只保留一套语义化来源，降低后续维护成本和回归定位成本。

### Phase 10（本轮继续完成）
- 顶栏搜索区尺寸校准
  - 收敛顶栏高度、边距与搜索宽度上限，避免搜索输入区在壳层中占比异常。
  - 为 `top_bar_search` 与快捷键提示块设置统一控件高度，修复视觉基线不一致问题。
- 控件密度优化（按钮/下拉/输入框）
  - 下调全局按钮最小高度、最小宽度与内边距，减少页面“发胖”感。
  - 下调输入框与下拉框最小高度与聚焦态内边距，提升信息密度。
  - 优化下拉列表项高度与内边距，修复模型/语言选择菜单体积偏大问题。
- 系统性收敛
  - 将壳层尺寸约束归一到 `ui/constants.py`，避免页面内散落硬编码，便于后续整体调优。

### Phase 11（本轮继续完成）
- 页面级微调（基于最新截图）
  - 进一步压缩顶栏与侧栏密度：缩小品牌字号、侧栏按钮高度/内边距、壳层内容边距，使导航与内容区比例更平衡。
  - 继续收窄顶栏搜索尺寸（宽度上限 + 控件高度），减少头部右侧视觉拥挤。
- 交互控件细粒度密度优化
  - 为日历工具条新增语义角色（`calendar-nav-action` / `calendar-utility-action` / `calendar-primary-action`），分别控制前后翻页、同步/加账号、主动作按钮尺寸。
  - 为时间线检索区新增语义角色（`timeline-search-input` / `timeline-search-action` / `timeline-filter-control`），单独压缩搜索与筛选控件高度。
  - 设置页导航列表进一步紧凑化（容器内边距与 item 内边距收敛）。
- 回归保护
  - 补充/更新语义角色断言测试，确保后续重构不回退到大体积默认样式路径。

### Phase 12（本轮继续完成）
- 三页联动微调（Calendar / Timeline / Settings）
  - 日历页：进一步收紧导航与工具按钮宽度层级，降低顶部两行工具区占比。
  - 时间线页：搜索/筛选控件再次压缩高度，并为检索区维持单独语义角色样式。
  - 设置页：左侧导航宽度继续收窄，减少横向浪费。
- 事件卡信息层级优化
  - 时间线事件卡内部间距下调（header/details/actions），并新增 `event-meta` 语义样式钩子，统一“时间/详情”字体层级。
  - 日历网格头部、日期数字和“more events”文字体积下调，降低视觉噪音，突出事件主体信息。

### Phase 13（本轮继续完成）
- 顶栏与壳层比例进一步校准
  - 顶栏搜索输入与快捷提示块高度统一下调（28px），并继续收窄搜索宽度上限，修复头部右侧体积偏大问题。
  - 收敛壳层间距常量（顶栏间距/边距、侧栏宽度与按钮高度），使导航和内容区比例更接近 Docker Desktop 的紧凑节奏。
- 控件体积二次收口（light/dark 同步）
  - 全局按钮、输入框、下拉框、日期控件、下拉列表项统一再压一档（高度/内边距/最小宽度），避免页面“松散”和控件过胖。
  - 日历与时间线的语义动作控件（`calendar-*`、`timeline-*`）分别按操作优先级重设尺寸层级，确保主次动作一眼可辨且占位合理。
- 冗余样式清理（DRY）
  - 删除 `settings-nav` 在旧样式段中的重复定义，仅保留统一覆盖层作为唯一生效来源，降低后续样式回归定位成本。
- 实时录音动作语义统一
  - 为录音页头部按钮补齐语义角色（`realtime-marker-action` / `realtime-record-action`），并补充对应回归测试，避免继续依赖对象名特例样式。

### Phase 14（本轮继续完成）
- 主题一致性“可执行大纲”落地
  - 新增 `resources/themes/theme_outline.json`，按 Shell / Base Controls / 页面语义角色分区定义主题必备选择器清单。
  - 新增 `tests/unit/test_theme_outline_contract.py`，自动校验：
    - 每个主题文件都覆盖 outline 清单；
    - UI 代码里声明的 `role` 在每个主题中都有样式选择器；
    - `light/dark` 的 role 集合完全一致，防止单主题漏配；
    - `ThemeManager` 的主题声明与 palette 键集合保持一致。
- 已发现并修复的不一致根因样例
  - 修复 `dark.qss` 缺失 `current-time` / `current-time-line` 语义样式的问题。
  - 音频播放器转录区域样式从单一 `objectName` 扩展为 `role` 语义选择器，避免样式入口分叉。
- 后续新增主题指导
  - 新增 `docs/THEME_OUTLINE_GUIDE.md`，明确新增主题的标准流程与反模式约束。

### Phase 15（本轮继续完成）
- 密度基线去重（DRY）
  - 清理 light/dark 顶部历史区块中的重复全局按钮与文本输入基线规则，统一收敛到末尾覆盖层作为单一生效入口。
- 尺寸合同化（避免再次漂移）
  - 在 `tests/unit/test_theme_outline_contract.py` 新增密度合同检查：
    - 核心全局 `QPushButton` 基线只允许单定义；
    - 禁止回退到旧的重复输入基线块；
    - 核心控件尺寸（顶栏搜索高度、实时录音时长标签高度、标记按钮宽度）与常量保持一致。
- 常量与样式对齐
  - `CONTROL_BUTTON_MIN_HEIGHT` 与统一 QSS 按钮高度对齐，减少“同功能控件大小不一致”。

### Phase 16（本轮继续完成）
- 语义规则进一步去重（batch/model/timeline）
  - 删除 `batch-viewer-toolbar` 中段历史块里与统一覆盖层重复的按钮样式定义（active/copy/export 等），保留单一语义来源。
  - 清理 `model-delete`、`time-display`、`clear_markers_button` 的重复定义入口，避免同语义在不同段落多次实现。
  - 任务状态颜色规则中，移除与统一覆盖层重复的 processing/completed/failed 旧定义，保留单一后置语义映射。
- 回归防线增强
  - 在 `tests/unit/test_theme_outline_contract.py` 增加“重复语义块去重”断言，防止后续将同一语义样式再次散落到多个区块。

### Phase 17（本轮继续完成）
- 日历事件弹窗运行时稳定性修复
  - 修复 `EventDialog` 保存流程对 `QDateTime.toPyDateTime()` 的硬依赖，改为统一兼容转换函数（`toPython` / `toPyDateTime` / 手动回退）。
  - 替换表单校验与提交数据收集中的日期时间转换调用，避免 Qt 绑定差异导致运行时崩溃。
- 回归测试补齐
  - 新增事件弹窗时间转换与时间区间校验测试，确保“保存”路径不再触发 `AttributeError`。

### Phase 18（本轮继续完成）
- 根因收敛：消除样式“多入口覆盖”
  - 移除 light/dark 中遗留的早期 `QCheckBox/QRadioButton` 与 `task-item` 重复定义，统一保留末尾语义覆盖层单入口。
  - `settings` 底部动作按钮规则重构为单入口（save/reset/cancel），避免同一选择器在多个区块重复声明。
  - 音频播放器进度条与音量条补齐专用 `add-page / pressed / border` 子规则，避免继承全局 `QSlider` 历史样式导致视觉异常。
- 紧凑化与去硬编码
  - 批量转写搜索条移除按钮固定宽度硬编码（`setFixedWidth`），改为语义 role 的主题规则统一控制尺寸。
  - 同步压缩 `search-nav-action / search-close-action` 的按钮密度（高度、内边距、字号），提升工具条紧凑度与一致性。
- 回归防线
  - `test_theme_outline_contract` 增加“全量选择器重复块为 0”校验，确保后续不会再次出现样式散落和重复定义。

## 验收标准
- 结构：导航、快捷键、搜索入口由统一配置驱动。
- 视觉：主壳层风格统一，亮暗主题一致可用。
- 质量：相关 UI 测试通过，无 mock 数据依赖。
- 维护：主题与壳层逻辑重复定义显著减少。
