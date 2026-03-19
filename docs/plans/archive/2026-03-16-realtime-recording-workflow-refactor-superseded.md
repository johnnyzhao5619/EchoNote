# Realtime Recording Workflow Refactor Implementation Plan (Superseded)

> Superseded on 2026-03-16 by `/Users/weijiazhao/Dev/EchoNote/docs/plans/archive/2026-03-16-realtime-recording-workflow-refactor-superseded.md`.

## Superseded Reason

该版本计划把录音 dock 设计成了完整的底部三阶段工作流，核心方向为：

- 在 dock 中承载 `配置 / 实时结果 / 录制结果`
- 让底部区域同时承担实时监视和录制完成后的结果浏览
- 将录音完成后的后续动作继续停留在 dock 内组织

该方向已被判定为错误，原因包括：

- 底部 dock 变成第二个工作区，和主 workspace 竞争空间
- `录制结果` 与工作台文档树重复，破坏单一事实源
- 悬浮窗被降级为辅助视图，没有承担实时结果主展示职责
- UI 生命周期错误替代了业务生命周期，造成重复导航和维护成本上升

## Historical Snapshot

旧方案的实施目标包括：

- 持久化会话转录/翻译 segment，并保存 `.txt + .json`
- 将 dock 改造成 workflow shell
- 让悬浮窗接入同一 recorder 状态
- 在录音结束后提供 dock 内的二次处理与结果入口

其中以下部分已被保留并纳入新方案：

- 共享会话状态
- `.txt + .json` 时间轴资产落盘
- 播放器跟随高亮能力
- 二次处理继续复用 `TranscriptionManager`

以下部分被明确废弃：

- 底部 `配置 / 实时结果 / 录制结果` 三标签结构
- dock 内的“录制结果页”
- 以 dock 作为录音完成结果主界面的信息架构

## Archival Note

该归档仅用于保留本次方向纠偏的历史上下文，不应再作为实施依据。后续开发应以当前归档记录 `/Users/weijiazhao/Dev/EchoNote/docs/plans/archive/2026-03-16-realtime-recording-workflow-refactor-superseded.md` 为准。
