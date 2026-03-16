# Realtime Recording Workflow Correction Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

## 1. 背景与目标

本计划用于纠正 2026-03-16 当天已落地但方向错误的录音工作流重构。当前实现把录音 dock 扩展成了 `配置 / 实时结果 / 录制结果` 三阶段底部面板，虽然完成了实时会话状态统一、悬浮窗接线、时间轴资产落盘和二次处理复用，但在产品信息架构上仍然存在根本问题：

- `实时结果` 与 `录制结果` 被做成了底部工作区，导致主界面底部再次出现大型内容容器，和工作台正文区竞争空间。
- `录制结果` 实际上是录制完成后生成的文档资产，应该统一进入工作台，而不是在 dock 中再复制一份结果呈现。
- 悬浮窗已经接入会话状态，但仍被降级成辅助部件，没有承担“实时实施结果展示”的主职责。
- 底部 dock 同时负责传输控制、配置、实时内容浏览、结果浏览、后处理入口，违反单一职责并形成重复导航。

本轮硬切目标：

- 将 `ui/common/realtime_recording_dock.py` 收敛为“紧凑横向录音控制台”，只承载会话控制、状态摘要、少量上下文入口。
- 将“实时转录 / 实时转译”统一转移到 `ui/realtime_record/floating_overlay.py` 承担，并提供 SVG 图标开关。
- 将“录制结果”彻底从 dock 中移除；录音结束后统一发布为工作台文档，并在工作台中查看、回放、二次处理。
- 保留并复用已经完成的共享会话状态、时间轴 JSON 落盘、播放器跟随高亮、二次处理编排，避免推倒重写。

## 2. 外部最佳实践依据

本次纠偏遵循以下官方设计原则：

- [Apple Human Interface Guidelines](https://developer.apple.com/design/human-interface-guidelines/)：临时上下文内容应尽量使用轻量浮层或补充界面，而不是长期占据主工作区；持续可见的控制区应保持紧凑。
- [Material 3 Tabs](https://m3.material.io/components/tabs/overview)：标签页适合在同一信息密度层级下切换并列内容，不适合把会话控制、实时监视、结果浏览这类不同生命周期的职责混装在一起。
- [Obsidian File Explorer](https://help.obsidian.md/plugins/file-explorer)：内容完成后应统一归入主文档树，而不是在次级控制区维护第二套结果容器。

设计结论：

- dock 应是 transport/status bar，而不是二级工作台。
- live result 应是轻量、可隐藏、可悬浮的上下文视图。
- completed result 应进入单一事实源，也就是 workspace 文档树。

## 3. 现状问题审计

### 3.1 业务问题

1. 录音中和录音后结果被分散在两个地方：
- 录音中：悬浮窗和底部 `实时结果` 标签同时存在。
- 录音后：工作台文档和底部 `录制结果` 标签同时存在。

2. 会话完成后的主动作不清晰：
- 用户真正需要的是“继续查看文档 / 回放跟随 / 二次处理”。
- 当前实现却先把用户引到 dock 结果标签，再由 dock 跳转回工作台。

3. 会话生命周期被错误拆分为 UI 生命周期：
- 业务生命周期：准备 -> 录音中 -> 录音结束 -> 文档发布 -> 后处理。
- 当前 UI 生命周期：准备 tab -> 实时结果 tab -> 录制结果 tab。
- 这导致底部 dock 被迫承载本该属于 workspace 的结果浏览。

### 3.2 交互问题

1. 底部区域再次堆叠：
- 主工作区已经有 workspace 编辑区。
- 底部又出现滚动内容、按钮组、标签页，形成“工作区下面还有一个工作区”。

2. 横向密度差：
- 录音控制按钮、计时、设备/语言信息、本次会话动作没有压缩到一条清晰的横向轨道。
- 大量纵向堆叠来自本不该长期展开的配置和结果内容。

3. 悬浮窗职责不明确：
- 已接实时数据，但不是默认主展示面。
- 缺少清晰开关和状态反馈，用户无法理解何时应该依赖悬浮窗。

### 3.3 技术问题

1. 信息架构重复，增加维护成本：
- `WorkspaceRecordingSessionPanel` 与工作台文档区共同承担结果浏览。
- dock 和 overlay 都在消费实时结果，却没有明确主次。

2. 二次处理入口可能出现重复实现趋势：
- 如果继续保留 dock 的结果页，后续极易在 dock 内再长出更多“结果操作”，复制 workspace/editor 的逻辑。

3. 样式与布局问题不是 QSS 单点问题：
- 根因是职责放错位置，不是单纯按钮过高或间距过大。

## 4. 重构后的产品要求

### 4.1 会话级能力边界

录音会话必须只有一个共享状态源，继续复用 `RealtimeRecorder` 的会话结果与 `SessionArchiver` 的产物。

录音会话的三个核心输出：

- 实时输出：转录和转译增量结果，只在悬浮窗中主展示。
- 完成输出：工作台文档资产，包括转录文档、转译文档、音频及时间轴 JSON。
- 后处理输出：摘要、会议整理、二次高质量转写等，继续复用现有 workspace / transcription 流程。

### 4.2 UI 职责拆分

#### A. 底部 dock

只负责：

- 开始录音 / 停止录音
- 录音计时
- 当前输入设备、识别语言、翻译状态的紧凑摘要
- 悬浮窗显示开关
- 少量即时动作，例如“展开设置”“打开最新文档”

不再负责：

- 实时转录正文浏览
- 实时转译正文浏览
- 录制结果详情浏览
- 会话完成后的长内容展示

#### B. 悬浮窗

成为实时结果主展示面，负责：

- 实时转录增量
- 实时转译增量
- 录音状态与时长
- 回主窗口 / 置顶 / 显示或隐藏翻译等轻量动作

要求：

- 默认由 dock 的 SVG 图标开关控制
- 录音中可独立显示，不打断主界面编辑
- 录音结束后自动切回摘要态或关闭态，不继续承担结果浏览

#### C. 工作台

成为录制完成结果的唯一展示面，负责：

- 自动出现新生成的录音文档和翻译文档
- 回放时通过现有 `AudioPlayer` + 时间轴 JSON 提供歌词式跟随显示
- 继续提供摘要、会议整理、导出、二次处理等文档后续操作

### 4.3 录音结束后的行为

录音停止后：

1. `RealtimeRecorder` 收敛本次会话结果。
2. `SessionArchiver` 落盘音频、文本、时间轴 JSON。
3. `WorkspaceManager` 发布转录文档；若开启翻译，再发布翻译文档。
4. 主窗口可根据当前上下文自动聚焦最新生成的工作台文档，或至少提供“打开最新文档”快捷入口。
5. dock 回到紧凑完成态，不展开结果页。
6. 悬浮窗停止滚动实时内容，仅保留短暂完成反馈后收起或静默。

### 4.4 二次处理能力

继续复用旧版本已有能力，不新增第二套实现：

- 二次高质量转写
- 转译补跑
- 摘要/会议整理

这些能力的主入口应留在工作台文档操作区；dock 最多保留一个“对最新会话执行二次处理”的快捷动作，但实际调用必须仍然走 `TranscriptionManager` 和既有 dialog/queue。

## 5. 业务流程重构

### 5.1 录音前

用户在 dock 上完成最低限度配置：

- 输入设备
- 识别语言
- 是否启用翻译
- 是否开启悬浮窗

详细设置不应展开成大型底部内容区，应改成：

- 紧凑下拉 / popover / 小面板

### 5.2 录音中

dock 仅保留 transport 和状态摘要。

悬浮窗承担：

- 实时字幕
- 实时转译
- 状态提示

主窗口 workspace 可继续编辑或浏览其他文档，不被底部录音结果区挤压。

### 5.3 录音结束

系统将录音会话发布为工作台资产，不在 dock 保留“结果页”。

如果用户当前就在工作台：

- 可自动选中最新录音文档

如果用户当前不在工作台：

- 保留非打断式提示和“打开最新文档”入口

### 5.4 回放和后处理

用户在工作台中：

- 打开录音文档
- 使用右侧录音预览或共享播放器回放
- 通过时间轴 JSON 高亮当前句段
- 根据需要执行二次高质量转写、转译补跑、摘要、会议整理

## 6. 技术改造方向

### 6.1 保留的部分

以下能力已经方向正确，不应重复实现：

- `core/realtime/recorder.py` 中的会话统一状态
- `core/realtime/archiver.py` 中的 `.txt + .json` 落盘
- `ui/common/audio_player.py` 的时间轴跟随能力
- `TranscriptionManager` 及其二次处理链路

### 6.2 需要硬切删除或降级的部分

需要从架构上移除或降级：

- `WorkspaceRecordingSessionPanel` 中承载大型 `实时结果 / 录制结果` 内容区的职责
- dock 中把完整结果再次显示一遍的逻辑
- 会话完成后依赖底部结果页驱动用户后续操作的交互路径

### 6.3 建议的新组件职责

- `ui/common/realtime_recording_dock.py`
  - 保留为紧凑控制条
  - 新增 SVG 图标级开关与 tooltip
  - 承担最小会话状态摘要

- `ui/realtime_record/floating_overlay.py`
  - 成为实时结果主展示面
  - 承担转录/转译内容分页或双栏切换
  - 保持 always-on-top 和 pin 能力

- `ui/workspace/recording_session_panel.py`
  - 不再作为三阶段大面板
  - 若保留，应降级为轻量配置表单或临时弹出内容
  - 如其职责完全可被 dock 内嵌控件替代，可直接删除

- `ui/main_window.py`
  - 负责录音结束后聚焦最新工作台文档
  - 负责 overlay 与 dock 的生命周期编排

## 7. 实施任务拆解

### Task 1: 重写录音工作流计划基线并锁定业务契约

**Files**
- Modify: `/Users/weijiazhao/Dev/EchoNote/docs/plans/2026-03-16-realtime-recording-workflow-refactor.md`
- Modify: `/Users/weijiazhao/Dev/EchoNote/docs/README.md`

**目标**

将错误的“底部三阶段 tab 工作流”从主计划中移除，明确新的单一事实源和职责拆分。

**验收**

- 主计划不再把 `录制结果` 视为 dock 内容
- 文档入口清楚标明悬浮窗与 workspace 的职责

### Task 2: 将 dock 收敛为紧凑横向控制条

**Files**
- Modify: `/Users/weijiazhao/Dev/EchoNote/ui/common/realtime_recording_dock.py`
- Modify: `/Users/weijiazhao/Dev/EchoNote/ui/constants.py`
- Modify: `/Users/weijiazhao/Dev/EchoNote/resources/themes/theme_outline.json`
- Modify: `/Users/weijiazhao/Dev/EchoNote/resources/themes/light.qss`
- Modify: `/Users/weijiazhao/Dev/EchoNote/resources/themes/dark.qss`
- Test: `/Users/weijiazhao/Dev/EchoNote/tests/unit/test_main_window_shell.py`

**具体改造**

- 移除大型底部展开内容区
- 移除 `配置 / 实时结果 / 录制结果` tab
- 以横向 transport + 摘要 chips + icon actions 重建布局
- 为悬浮窗开关提供 SVG icon + tooltip

**关键测试**

- dock 在窄宽度下不再产生二级工作区堆叠
- 录音状态和关键摘要仍然可见

### Task 3: 让悬浮窗成为实时结果主界面

**Files**
- Modify: `/Users/weijiazhao/Dev/EchoNote/ui/realtime_record/floating_overlay.py`
- Modify: `/Users/weijiazhao/Dev/EchoNote/ui/common/realtime_recording_dock.py`
- Modify: `/Users/weijiazhao/Dev/EchoNote/ui/main_window.py`
- Test: `/Users/weijiazhao/Dev/EchoNote/tests/unit/test_main_window_shell.py`

**具体改造**

- 悬浮窗直接绑定实时转录/转译流
- 增加显隐开关和完成态行为
- 录音中主展示实时文本，录音后自动退出正文浏览角色

**关键测试**

- 录音开始后，开启浮窗时可看到实时结果
- 停止录音后，浮窗不会继续承担“结果页”职责

### Task 4: 把录制完成结果完全收口到工作台

**Files**
- Modify: `/Users/weijiazhao/Dev/EchoNote/ui/main_window.py`
- Modify: `/Users/weijiazhao/Dev/EchoNote/core/workspace/manager.py`
- Modify: `/Users/weijiazhao/Dev/EchoNote/ui/workspace/widget.py`
- Modify: `/Users/weijiazhao/Dev/EchoNote/ui/workspace/editor_panel.py`
- Test: `/Users/weijiazhao/Dev/EchoNote/tests/ui/test_workspace_widget.py`

**具体改造**

- 录音完成后自动生成并发布工作台文档
- 主窗口提供聚焦最新文档的路径
- 不再在 dock 中重复显示完成结果

**关键测试**

- 开启翻译时会生成转录文档和转译文档
- 最新录音文档能在工作台中直接打开

### Task 5: 保持回放跟随与二次处理链路一致

**Files**
- Modify: `/Users/weijiazhao/Dev/EchoNote/ui/common/audio_player.py`
- Modify: `/Users/weijiazhao/Dev/EchoNote/ui/workspace/recording_panel.py`
- Modify: `/Users/weijiazhao/Dev/EchoNote/ui/main_window.py`
- Test: `/Users/weijiazhao/Dev/EchoNote/tests/ui/test_timeline_audio_player.py`
- Test: `/Users/weijiazhao/Dev/EchoNote/tests/ui/test_workspace_widget.py`

**具体改造**

- 保持 `.txt + .json` 的跟随播放链路
- 后处理入口继续走 `TranscriptionManager`
- 删除任何新长出的 recording-only duplicate path

**关键测试**

- 回放时仍能跟随句段高亮
- 二次处理入口与旧版逻辑一致

### Task 6: 收口 theme / i18n / docs / regression

**Files**
- Modify: `/Users/weijiazhao/Dev/EchoNote/resources/translations/i18n_outline.json`
- Modify: `/Users/weijiazhao/Dev/EchoNote/resources/translations/zh_CN.json`
- Modify: `/Users/weijiazhao/Dev/EchoNote/resources/translations/en_US.json`
- Modify: `/Users/weijiazhao/Dev/EchoNote/resources/translations/fr_FR.json`
- Modify: `/Users/weijiazhao/Dev/EchoNote/ui/realtime_record/README.md`
- Modify: `/Users/weijiazhao/Dev/EchoNote/AGENTS.md`
- Modify: `/Users/weijiazhao/Dev/EchoNote/CHANGELOG.md`
- Test: `/Users/weijiazhao/Dev/EchoNote/tests/unit/test_i18n_outline_contract.py`
- Test: `/Users/weijiazhao/Dev/EchoNote/tests/unit/test_theme_outline_contract.py`

**回归批次**

- `pytest tests/unit/test_main_window_shell.py -v`
- `pytest tests/ui/test_workspace_widget.py -v`
- `pytest tests/unit/core/test_realtime_recorder.py -v`
- `pytest tests/ui/test_timeline_audio_player.py -v`
- `pytest tests/unit/test_i18n_outline_contract.py -v`
- `pytest tests/unit/test_theme_outline_contract.py -v`

## 8. 风险与约束

### 风险 1: 继续在旧 dock 上做小修小补

结果会是：

- 底部堆叠继续存在
- 悬浮窗和 dock 结果区继续重复
- 后续每增加一个动作都更难维护

结论：必须硬切，不再继续补丁式修饰当前三标签结构。

### 风险 2: 误删已完成的正确能力

需要保住：

- 实时会话统一状态
- 时间轴 JSON 资产
- workspace 文档发布
- 二次处理复用链路

结论：本次不是重做录音引擎，而是纠正 UI 架构和职责分配。

## 9. 实施顺序建议

1. 先删 dock 中的三标签与结果内容区，再重建紧凑横向骨架。
2. 其次增强悬浮窗，使其真正可承担实时结果展示。
3. 然后把录音完成后的默认入口切回工作台。
4. 最后收口回放跟随、二次处理、theme/i18n/docs/tests。

## 10. 完成定义

满足以下条件才算完成：

- 底部只剩紧凑录音控制台，不再出现大型内容堆叠区。
- 实时转录 / 转译只在悬浮窗中作为主视图展示。
- 录音完成结果只进入工作台，不在 dock 再复制一份。
- 回放跟随和二次处理继续可用。
- 没有新增重复逻辑，没有保留无主责任的旧 UI 残骸。
