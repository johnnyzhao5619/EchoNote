# EchoNote 用户指南 / User Guide

**版本 / Version:** 1.0.0  
**语言 / Languages:** 中文 | [English](#english-version)

---

## 中文版

### 目录

1. [简介](#简介)
2. [快速开始](#快速开始)
3. [功能详解](#功能详解)
   - [批量转录](#批量转录)
   - [实时录制](#实时录制)
   - [日历中心](#日历中心)
   - [时间线](#时间线)
   - [设置](#设置)
4. [常见问题](#常见问题)
5. [故障排查](#故障排查)

---

### 简介

EchoNote 是一款跨平台桌面应用，专注于智能语音转录、翻译和日历管理。应用采用本地优先（local-first）理念，确保您的数据安全和离线可用性。

**核心功能：**

- 📝 批量音频/视频文件转录
- 🎙️ 实时录制与转录
- 📅 统一日历管理（支持 Google Calendar 和 Outlook）
- ⏱️ 智能时间线视图
- 🌍 多语言支持（中文、英文、法语）
- 🎨 浅色/深色主题

---

### 快速开始

#### 首次运行

1. **启动应用**

   - Windows: 双击 `EchoNote.exe`
   - macOS: 打开 `EchoNote.app`

2. **首次运行向导**

   首次启动时，应用会引导您完成初始设置：

   - **选择语言**：选择您的首选界面语言
   - **选择主题**：选择浅色或深色主题
   - **下载模型**：下载语音识别模型（推荐下载 `base` 模型）

3. **FFmpeg 安装（可选）**

   如果您需要处理视频格式（MP4、MKV 等），建议安装 FFmpeg：

   - **macOS**: `brew install ffmpeg`
   - **Windows**: 使用 Chocolatey `choco install ffmpeg` 或从官网下载
   - **Linux**: `sudo apt-get install ffmpeg` (Ubuntu/Debian)

   > 注意：纯音频格式（WAV、MP3、FLAC）无需 FFmpeg 即可处理

---

### 功能详解

#### 批量转录

批量转录功能允许您一次性处理多个音频或视频文件。

##### 使用步骤

1. **导入文件**

   点击左侧边栏的「批量转录」，然后：

   - 点击「导入文件」选择单个或多个文件
   - 点击「导入文件夹」批量导入整个文件夹

   支持的格式：

   - 音频：MP3, WAV, M4A, FLAC, OGG, OPUS
   - 视频：MP4, AVI, MKV, MOV, WEBM（需要 FFmpeg）

2. **选择模型**

   在顶部选择要使用的语音识别模型：

   - `tiny`: 最快，准确度较低
   - `base`: 平衡选择（推荐）
   - `small`: 较准确
   - `medium`: 高准确度
   - `large`: 最准确，速度较慢

3. **开始转录**

   - 文件导入后会自动添加到任务队列
   - 点击任务旁的「开始」按钮开始转录
   - 或等待自动处理（根据并发设置）

4. **查看进度**

   任务列表会显示：

   - 文件名和大小
   - 当前状态（待处理/处理中/已完成/失败）
   - 进度百分比
   - 预估剩余时间

5. **导出结果**

   转录完成后，点击「查看」或「导出」：

   - **TXT**: 纯文本格式
   - **SRT**: 字幕格式（带时间戳）
   - **MD**: Markdown 格式（带时间戳）

##### 任务管理

- **暂停/继续**: 点击任务旁的按钮
- **取消**: 停止正在处理的任务
- **重试**: 重新处理失败的任务
- **删除**: 从队列中移除任务
- **清空队列**: 清除所有任务

##### 提示与技巧

- 在设置中调整并发任务数（1-5），根据您的设备性能选择
- 使用 GPU 加速可显著提高处理速度（需要支持 CUDA 的 NVIDIA 显卡）
- 长音频文件建议使用较大的模型以获得更好的准确度

---

#### 实时录制

实时录制功能允许您捕捉音频并同步进行转录和翻译。

##### 使用步骤

1. **选择音频输入**

   在「音频输入」下拉菜单中选择：

   - 默认麦克风
   - 系统音频（需要虚拟音频设备）
   - 其他音频输入设备

2. **调整增益**

   使用增益滑块调整音频输入音量：

   - 观察音频波形确保音量适中
   - 避免过载（波形不应触顶）

3. **选择模型和语言**

   - **模型**: 选择语音识别模型（推荐 `tiny` 或 `base` 以获得低延迟）
   - **源语言**: 选择说话的语言
   - **目标语言**: 如果启用翻译，选择翻译目标语言

4. **启用翻译（可选）**

   勾选「启用翻译」复选框：

   - 需要在设置中配置 Google Translate API 密钥
   - 翻译文本会实时显示在转录文本下方

5. **开始录制**

   点击「开始录制」按钮：

   - 录制时长会实时显示
   - 转录文本会以流式方式显示（延迟约 2-3 秒）
   - 如果启用翻译，翻译文本也会实时更新

6. **停止录制**

   点击「停止录制」按钮：

   - 录音文件会自动保存到配置的目录
   - 可以导出转录文本和翻译文本
   - 会自动在日历中创建一个事件记录

##### 导出选项

- **导出转录**: 保存转录文本为 TXT 或 MD 格式
- **导出翻译**: 保存翻译文本为独立文件
- **保存录音**: 录音文件已自动保存（WAV 或 MP3 格式）

##### 提示与技巧

- 使用较小的模型（tiny/base）以获得更低的延迟
- 确保麦克风音量适中，避免背景噪音
- 在安静的环境中录制可获得更好的转录质量
- 翻译功能需要网络连接

---

#### 日历中心

日历中心提供统一的日历管理，支持本地事件和外部日历同步。

##### 连接外部日历

1. **添加 Google Calendar**

   - 点击「添加账户」→「添加 Google 账户」
   - 浏览器会打开 Google 授权页面
   - 登录并授权 EchoNote 访问您的日历
   - 授权成功后，事件会自动同步

2. **添加 Outlook Calendar**

   - 点击「添加账户」→「添加 Outlook 账户」
   - 浏览器会打开 Microsoft 授权页面
   - 登录并授权 EchoNote 访问您的日历
   - 授权成功后，事件会自动同步

3. **管理连接**

   - 在设置 > 日历中查看已连接的账户
   - 点击「移除账户」断开连接
   - 断开连接后，外部事件会从本地删除

##### 创建事件

1. **点击「创建事件」按钮**

2. **填写事件信息**

   必填字段：

   - 标题
   - 类型（事件/任务/约会）
   - 开始时间
   - 结束时间

   可选字段：

   - 地点
   - 参会人员（逗号分隔）
   - 描述
   - 提醒时间
   - 重复规则

3. **同步到外部日历（可选）**

   - 勾选「同步到 Google 日历」或「同步到 Outlook 日历」
   - 事件会在本地创建后推送到外部服务

##### 查看事件

- **月视图**: 查看整月的事件
- **周视图**: 查看一周的详细安排
- **日视图**: 查看单日的时间槽

事件颜色编码：

- 🔵 蓝色：本地事件
- 🔴 红色：Google Calendar 事件
- 🟠 橙色：Outlook Calendar 事件

##### 编辑和删除

- **本地事件**: 可以编辑和删除
- **外部事件**: 只读，需要在原始日历中编辑

##### 自动同步

- 应用会每 15 分钟自动同步外部日历（可在设置中调整）
- 点击「立即同步」手动触发同步

---

#### 时间线

时间线提供一个统一的视图，显示过去和未来的事件，以及相关的录音和转录文件。

##### 界面布局

- **当前时间线**: 红色虚线标记当前时间
- **未来事件**: 显示在时间线下方
- **过去事件**: 显示在时间线上方

##### 未来事件功能

每个未来事件卡片包含：

- 事件详情（标题、时间、地点、参会人员）
- **启用实时转录**: 开关按钮
- **启用会议录音**: 开关按钮

**自动任务**：

- 启用后，事件开始时会自动启动录制和转录
- 事件开始前 5 分钟会收到桌面通知
- 录制会在事件结束时自动停止

##### 过去事件功能

每个过去事件卡片包含：

- 事件详情
- **播放录音**: 如果有录音文件
- **查看转录**: 如果有转录文本

**音频播放器**：

- 播放/暂停控制
- 进度条（可拖动跳转）
- 音量控制
- 显示当前时间和总时长

**转录查看器**：

- 显示完整转录文本
- 搜索功能（高亮匹配）
- 复制全部或选中部分
- 导出为 TXT、SRT 或 MD 格式

##### 搜索和过滤

- **搜索框**: 输入关键词搜索事件标题、描述和转录文本
- **类型过滤**: 按事件类型过滤（全部/事件/任务/约会）
- **来源过滤**: 按来源过滤（全部/本地/Google/Outlook）

##### 提示与技巧

- 为重要会议启用自动录制，避免遗漏
- 使用搜索功能快速找到历史会议内容
- 定期导出重要的转录文本作为备份

---

#### 设置

设置页面允许您自定义应用的各个方面。

##### 转录设置

- **默认输出格式**: 选择 TXT、SRT 或 MD
- **并发任务数**: 1-5（根据设备性能调整）
- **保存位置**: 转录文件的默认保存目录
- **语音识别引擎**: 选择 faster-whisper 或云服务
- **模型大小**: 选择 Whisper 模型（tiny/base/small/medium/large）
- **设备**: 选择计算设备（自动/CPU/CUDA）
- **计算类型**: 选择计算精度（int8/float16/float32）

**云服务配置**（可选）：

- OpenAI Whisper API
- Google Speech-to-Text API
- Azure Speech Service

输入 API 密钥后，可以点击「测试连接」验证。

##### 实时录制设置

- **音频输入源**: 选择默认音频输入设备
- **增益级别**: 设置默认增益
- **录音格式**: WAV 或 MP3
- **录音保存位置**: 录音文件的默认保存目录
- **自动保存录音**: 启用后自动保存所有录音
- **翻译引擎**: 配置 Google Translate API 密钥

##### 日历设置

- **已连接账户**: 查看和管理已连接的外部日历
- **添加账户**: 连接 Google 或 Outlook 日历
- **移除账户**: 断开外部日历连接
- **同步间隔**: 调整自动同步频率（默认 15 分钟）

##### 时间线设置

- **视图范围**: 设置显示过去和未来多少天的事件
- **提醒时间**: 设置事件开始前多久发送提醒（默认 5 分钟）
- **启用自动启动录制**: 事件开始时自动启动录制

##### 模型管理

- **已下载模型**: 查看、配置和删除已下载的模型
- **可下载模型**: 浏览和下载新模型
- **模型详情**: 查看模型大小、支持的语言、使用次数等
- **模型配置**: 为每个模型单独配置计算参数

**下载模型**：

1. 在「可下载模型」列表中选择模型
2. 点击「下载」按钮
3. 等待下载完成（进度会实时显示）
4. 下载完成后，模型会出现在「已下载模型」列表中

**删除模型**：

1. 在「已下载模型」列表中选择模型
2. 点击「删除」按钮
3. 确认删除（会显示释放的磁盘空间）

##### 外观设置

- **主题**: 选择浅色、深色或跟随系统
- **主题预览**: 实时预览主题效果
- 主题更改会立即应用到整个应用

##### 语言设置

- **当前语言**: 显示当前界面语言
- **选择语言**: 中文（简体）、English、Français
- 语言更改会立即应用到整个应用

---

### 常见问题

#### 1. 如何下载语音识别模型？

**答**: 前往「设置」→「模型管理」→「可下载模型」，选择一个模型并点击「下载」。推荐首次使用下载 `base` 模型。

#### 2. 为什么转录速度很慢？

**答**: 可能的原因：

- 使用了较大的模型（medium/large）
- 设备性能较低
- 未启用 GPU 加速

**解决方案**：

- 使用较小的模型（tiny/base）
- 在设置中启用 GPU 加速（如果有 NVIDIA 显卡）
- 减少并发任务数

#### 3. 如何启用 GPU 加速？

**答**:

1. 确保您有支持 CUDA 的 NVIDIA 显卡
2. 安装支持 CUDA 的 PyTorch
3. 在「设置」→「转录设置」中，将「设备」设置为「CUDA」
4. 将「计算类型」设置为「float16」以获得最佳性能

#### 4. 翻译功能不可用怎么办？

**答**: 翻译功能需要 Google Translate API 密钥：

1. 前往 Google Cloud Console 创建项目
2. 启用 Cloud Translation API
3. 创建 API 密钥
4. 在「设置」→「实时录制设置」中输入 API 密钥

#### 5. 如何处理视频文件？

**答**: 处理视频文件需要安装 FFmpeg：

- **macOS**: `brew install ffmpeg`
- **Windows**: `choco install ffmpeg` 或从官网下载
- **Linux**: `sudo apt-get install ffmpeg`

安装后重启 EchoNote。

#### 6. 外部日历同步失败怎么办？

**答**: 可能的原因：

- 网络连接问题
- OAuth token 过期
- API 配额限制

**解决方案**：

1. 检查网络连接
2. 在设置中移除账户并重新连接
3. 点击「立即同步」手动触发同步
4. 查看日志文件了解详细错误信息

#### 7. 如何备份我的数据？

**答**: EchoNote 的数据存储在：

- **数据库**: `~/.echonote/data.db`
- **录音文件**: `~/Documents/EchoNote/Recordings/`
- **转录文件**: `~/Documents/EchoNote/Transcripts/`
- **配置文件**: `~/.echonote/secrets.enc`

定期备份这些文件即可。

#### 8. 应用启动很慢怎么办？

**答**: 首次启动时，应用需要加载模型和初始化组件，可能需要 5-10 秒。后续启动会更快。

如果启动持续很慢：

1. 检查是否有大量历史任务
2. 清理不需要的模型
3. 检查磁盘空间是否充足

#### 9. 如何卸载应用？

**答**:

- **Windows**: 通过控制面板卸载
- **macOS**: 将应用拖到废纸篓

如果要删除所有数据，手动删除 `~/.echonote/` 目录。

#### 10. 支持哪些语言的转录？

**答**: Whisper 模型支持 99 种语言，包括：

- 中文（简体/繁体）
- 英语
- 法语
- 西班牙语
- 德语
- 日语
- 韩语
- 等等

完整列表请参考 OpenAI Whisper 文档。

---

### 故障排查

#### 转录失败

**症状**: 任务状态显示「失败」

**可能原因**：

1. 文件格式不支持
2. 文件损坏
3. 模型未下载或损坏
4. 内存不足

**解决步骤**：

1. 检查文件格式是否在支持列表中
2. 尝试用其他播放器打开文件，确认文件完整
3. 在「设置」→「模型管理」中验证模型
4. 关闭其他应用释放内存
5. 查看任务详情中的错误信息
6. 查看日志文件：`~/.echonote/logs/echonote.log`

#### 实时录制无声音

**症状**: 录制时音频波形无变化

**可能原因**：

1. 麦克风未连接或未授权
2. 选择了错误的音频输入源
3. 系统音量设置问题

**解决步骤**：

1. 检查麦克风是否正常工作（在系统设置中测试）
2. 在应用中选择正确的音频输入源
3. 调整增益滑块
4. 检查系统是否授予了麦克风权限
5. 重启应用

#### 日历同步不工作

**症状**: 外部事件未显示

**可能原因**：

1. OAuth token 过期
2. 网络连接问题
3. API 配额限制
4. 同步调度器未启动

**解决步骤**：

1. 在设置中检查账户连接状态
2. 点击「立即同步」手动触发
3. 移除账户并重新连接
4. 检查网络连接
5. 查看日志文件了解详细错误

#### 应用崩溃

**症状**: 应用突然关闭

**可能原因**：

1. 内存不足
2. 模型文件损坏
3. 数据库损坏
4. 软件 bug

**解决步骤**：

1. 重启应用
2. 检查系统资源（内存、磁盘空间）
3. 在「设置」→「模型管理」中验证模型
4. 备份数据库后尝试重置：删除 `~/.echonote/data.db`
5. 查看崩溃日志：`~/.echonote/logs/echonote.log`
6. 如果问题持续，请提交 bug 报告

#### 性能问题

**症状**: 应用响应缓慢

**可能原因**：

1. 设备性能不足
2. 并发任务过多
3. 模型过大
4. 内存不足

**解决步骤**：

1. 减少并发任务数（设置 → 转录设置）
2. 使用较小的模型（tiny/base）
3. 关闭其他应用释放资源
4. 清理历史任务和文件
5. 重启应用

#### 文件权限错误

**症状**: 无法保存文件或读取文件

**可能原因**：

1. 目录权限不足
2. 磁盘空间不足
3. 文件被其他程序占用

**解决步骤**：

1. 检查保存目录的权限
2. 检查磁盘空间
3. 关闭可能占用文件的其他程序
4. 尝试更改保存位置（设置中）
5. 以管理员身份运行应用（Windows）

---

## 获取帮助

如果您遇到本指南未涵盖的问题：

1. **查看日志文件**: `~/.echonote/logs/echonote.log`
2. **检查 GitHub Issues**: 搜索类似问题
3. **提交 Bug 报告**: 包含详细的错误信息和日志
4. **联系支持**: 通过项目主页联系开发团队

---

## 附录

### 支持的文件格式

**音频格式**：

- MP3 (.mp3)
- WAV (.wav)
- M4A (.m4a)
- FLAC (.flac)
- OGG (.ogg)
- OPUS (.opus)

**视频格式**（需要 FFmpeg）：

- MP4 (.mp4)
- AVI (.avi)
- MKV (.mkv)
- MOV (.mov)
- WEBM (.webm)

### 系统要求

**最低要求**：

- **操作系统**: Windows 10/11, macOS 10.15+, Linux
- **内存**: 4 GB RAM
- **磁盘空间**: 2 GB（不含模型）
- **处理器**: Intel Core i3 或同等性能

**推荐配置**：

- **内存**: 8 GB RAM 或更多
- **磁盘空间**: 10 GB（含多个模型）
- **处理器**: Intel Core i5 或更好
- **显卡**: NVIDIA GPU（支持 CUDA）用于加速

### 模型大小和性能

| 模型   | 大小    | 速度 | 准确度 | 推荐用途             |
| ------ | ------- | ---- | ------ | -------------------- |
| tiny   | ~75 MB  | 最快 | 低     | 实时转录、快速预览   |
| base   | ~145 MB | 快   | 中     | 日常使用、平衡选择   |
| small  | ~466 MB | 中   | 高     | 重要内容、较高准确度 |
| medium | ~1.5 GB | 慢   | 很高   | 专业用途、高质量要求 |
| large  | ~2.9 GB | 最慢 | 最高   | 最高质量、不在意速度 |

### 快捷键

| 功能           | Windows/Linux | macOS |
| -------------- | ------------- | ----- |
| 切换到批量转录 | Ctrl+1        | ⌘+1   |
| 切换到实时录制 | Ctrl+2        | ⌘+2   |
| 切换到日历中心 | Ctrl+3        | ⌘+3   |
| 切换到时间线   | Ctrl+4        | ⌘+4   |
| 打开设置       | Ctrl+,        | ⌘+,   |
| 搜索           | Ctrl+F        | ⌘+F   |
| 复制           | Ctrl+C        | ⌘+C   |
| 全选           | Ctrl+A        | ⌘+A   |

---

---

## English Version

### Table of Contents

1. [Introduction](#introduction)
2. [Getting Started](#getting-started)
3. [Features](#features)
   - [Batch Transcription](#batch-transcription)
   - [Real-time Recording](#real-time-recording)
   - [Calendar Hub](#calendar-hub)
   - [Timeline](#timeline)
   - [Settings](#settings)
4. [FAQ](#faq)
5. [Troubleshooting](#troubleshooting)

---

### Introduction

EchoNote is a cross-platform desktop application focused on intelligent voice transcription, translation, and calendar management. The application follows a local-first philosophy, ensuring your data security and offline availability.

**Core Features:**

- 📝 Batch audio/video file transcription
- 🎙️ Real-time recording and transcription
- 📅 Unified calendar management (supports Google Calendar and Outlook)
- ⏱️ Intelligent timeline view
- 🌍 Multi-language support (Chinese, English, French)
- 🎨 Light/Dark themes

---

### Getting Started

#### First Run

1. **Launch the Application**

   - Windows: Double-click `EchoNote.exe`
   - macOS: Open `EchoNote.app`

2. **First Run Wizard**

   On first launch, the app will guide you through initial setup:

   - **Choose Language**: Select your preferred interface language
   - **Choose Theme**: Select light or dark theme
   - **Download Model**: Download a speech recognition model (recommended: `base` model)

3. **FFmpeg Installation (Optional)**

   If you need to process video formats (MP4, MKV, etc.), install FFmpeg:

   - **macOS**: `brew install ffmpeg`
   - **Windows**: Use Chocolatey `choco install ffmpeg` or download from official website
   - **Linux**: `sudo apt-get install ffmpeg` (Ubuntu/Debian)

   > Note: Pure audio formats (WAV, MP3, FLAC) can be processed without FFmpeg

---

### Features

#### Batch Transcription

Batch transcription allows you to process multiple audio or video files at once.

##### Usage Steps

1. **Import Files**

   Click "Batch Transcribe" in the left sidebar, then:

   - Click "Import File" to select single or multiple files
   - Click "Import Folder" to batch import an entire folder

   Supported formats:

   - Audio: MP3, WAV, M4A, FLAC, OGG, OPUS
   - Video: MP4, AVI, MKV, MOV, WEBM (requires FFmpeg)

2. **Select Model**

   Choose the speech recognition model at the top:

   - `tiny`: Fastest, lower accuracy
   - `base`: Balanced choice (recommended)
   - `small`: More accurate
   - `medium`: High accuracy
   - `large`: Most accurate, slower

3. **Start Transcription**

   - Files are automatically added to the task queue after import
   - Click the "Start" button next to a task to begin transcription
   - Or wait for automatic processing (based on concurrency settings)

4. **View Progress**

   The task list displays:

   - File name and size
   - Current status (Pending/Processing/Completed/Failed)
   - Progress percentage
   - Estimated remaining time

5. **Export Results**

   After transcription completes, click "View" or "Export":

   - **TXT**: Plain text format
   - **SRT**: Subtitle format (with timestamps)
   - **MD**: Markdown format (with timestamps)

##### Task Management

- **Pause/Resume**: Click the button next to the task
- **Cancel**: Stop a processing task
- **Retry**: Reprocess a failed task
- **Delete**: Remove task from queue
- **Clear Queue**: Remove all tasks

##### Tips & Tricks

- Adjust concurrent tasks (1-5) in settings based on your device performance
- GPU acceleration can significantly improve processing speed (requires CUDA-capable NVIDIA GPU)
- Use larger models for long audio files to get better accuracy

---

#### Real-time Recording

Real-time recording allows you to capture audio and perform simultaneous transcription and translation.

##### Usage Steps

1. **Select Audio Input**

   Choose from the "Audio Input" dropdown:

   - Default microphone
   - System audio (requires virtual audio device)
   - Other audio input devices

2. **Adjust Gain**

   Use the gain slider to adjust audio input volume:

   - Watch the audio waveform to ensure appropriate volume
   - Avoid clipping (waveform should not hit the top)

3. **Select Model and Language**

   - **Model**: Choose speech recognition model (recommend `tiny` or `base` for low latency)
   - **Source Language**: Select the spoken language
   - **Target Language**: If translation is enabled, select the translation target language

4. **Enable Translation (Optional)**

   Check the "Enable Translation" checkbox:

   - Requires Google Translate API key configured in settings
   - Translation text will display in real-time below transcription text

5. **Start Recording**

   Click the "Start Recording" button:

   - Recording duration displays in real-time
   - Transcription text streams with ~2-3 second delay
   - If translation is enabled, translation text also updates in real-time

6. **Stop Recording**

   Click the "Stop Recording" button:

   - Recording file is automatically saved to configured directory
   - Can export transcription and translation text
   - Automatically creates a calendar event record

##### Export Options

- **Export Transcription**: Save transcription text as TXT or MD format
- **Export Translation**: Save translation text as separate file
- **Save Recording**: Recording file is automatically saved (WAV or MP3 format)

##### Tips & Tricks

- Use smaller models (tiny/base) for lower latency
- Ensure microphone volume is appropriate, avoid background noise
- Record in quiet environment for better transcription quality
- Translation feature requires internet connection

---

#### Calendar Hub

Calendar Hub provides unified calendar management with support for local events and external calendar sync.

##### Connect External Calendars

1. **Add Google Calendar**

   - Click "Add Account" → "Add Google Account"
   - Browser will open Google authorization page
   - Log in and authorize EchoNote to access your calendar
   - After successful authorization, events will sync automatically

2. **Add Outlook Calendar**

   - Click "Add Account" → "Add Outlook Account"
   - Browser will open Microsoft authorization page
   - Log in and authorize EchoNote to access your calendar
   - After successful authorization, events will sync automatically

3. **Manage Connections**

   - View connected accounts in Settings > Calendar
   - Click "Remove Account" to disconnect
   - After disconnecting, external events are removed from local storage

##### Create Events

1. **Click "Create Event" button**

2. **Fill in Event Information**

   Required fields:

   - Title
   - Type (Event/Task/Appointment)
   - Start time
   - End time

   Optional fields:

   - Location
   - Attendees (comma-separated)
   - Description
   - Reminder time
   - Recurrence rule

3. **Sync to External Calendar (Optional)**

   - Check "Sync to Google Calendar" or "Sync to Outlook Calendar"
   - Event will be pushed to external service after local creation

##### View Events

- **Month View**: View events for the entire month
- **Week View**: View detailed weekly schedule
- **Day View**: View daily time slots

Event color coding:

- 🔵 Blue: Local events
- 🔴 Red: Google Calendar events
- 🟠 Orange: Outlook Calendar events

##### Edit and Delete

- **Local Events**: Can be edited and deleted
- **External Events**: Read-only, must be edited in original calendar

##### Auto Sync

- App automatically syncs external calendars every 15 minutes (adjustable in settings)
- Click "Sync Now" to manually trigger sync

---

#### Timeline

Timeline provides a unified view showing past and future events, along with related recordings and transcripts.

##### Interface Layout

- **Current Time Line**: Red dashed line marks current time
- **Future Events**: Displayed below the timeline
- **Past Events**: Displayed above the timeline

##### Future Event Features

Each future event card contains:

- Event details (title, time, location, attendees)
- **Enable Real-time Transcription**: Toggle button
- **Enable Meeting Recording**: Toggle button

**Auto Tasks**:

- When enabled, recording and transcription start automatically when event begins
- Desktop notification sent 5 minutes before event starts
- Recording stops automatically when event ends

##### Past Event Features

Each past event card contains:

- Event details
- **Play Recording**: If recording file exists
- **View Transcript**: If transcript text exists

**Audio Player**:

- Play/pause controls
- Progress bar (draggable to seek)
- Volume control
- Display current time and total duration

**Transcript Viewer**:

- Display complete transcript text
- Search function (highlight matches)
- Copy all or selected portion
- Export as TXT, SRT, or MD format

##### Search and Filter

- **Search Box**: Enter keywords to search event titles, descriptions, and transcript text
- **Type Filter**: Filter by event type (All/Event/Task/Appointment)
- **Source Filter**: Filter by source (All/Local/Google/Outlook)

##### Tips & Tricks

- Enable auto-recording for important meetings to avoid missing content
- Use search function to quickly find historical meeting content
- Regularly export important transcripts as backup

---

#### Settings

Settings page allows you to customize various aspects of the application.

##### Transcription Settings

- **Default Output Format**: Choose TXT, SRT, or MD
- **Concurrent Tasks**: 1-5 (adjust based on device performance)
- **Save Location**: Default save directory for transcript files
- **Speech Recognition Engine**: Choose faster-whisper or cloud services
- **Model Size**: Choose Whisper model (tiny/base/small/medium/large)
- **Device**: Choose compute device (Auto/CPU/CUDA)
- **Compute Type**: Choose compute precision (int8/float16/float32)

**Cloud Service Configuration** (Optional):

- OpenAI Whisper API
- Google Speech-to-Text API
- Azure Speech Service

After entering API key, click "Test Connection" to verify.

##### Real-time Recording Settings

- **Audio Input Source**: Choose default audio input device
- **Gain Level**: Set default gain
- **Recording Format**: WAV or MP3
- **Recording Save Location**: Default save directory for recording files
- **Auto-save Recordings**: Automatically save all recordings when enabled
- **Translation Engine**: Configure Google Translate API key

##### Calendar Settings

- **Connected Accounts**: View and manage connected external calendars
- **Add Account**: Connect Google or Outlook calendar
- **Remove Account**: Disconnect external calendar
- **Sync Interval**: Adjust auto-sync frequency (default 15 minutes)

##### Timeline Settings

- **View Range**: Set how many days of past and future events to display
- **Reminder Time**: Set how long before event start to send reminder (default 5 minutes)
- **Enable Auto-start Recording**: Automatically start recording when event begins

##### Model Management

- **Downloaded Models**: View, configure, and delete downloaded models
- **Available Models**: Browse and download new models
- **Model Details**: View model size, supported languages, usage count, etc.
- **Model Configuration**: Configure compute parameters for each model individually

**Download Model**:

1. Select a model from "Available Models" list
2. Click "Download" button
3. Wait for download to complete (progress displays in real-time)
4. After completion, model appears in "Downloaded Models" list

**Delete Model**:

1. Select a model from "Downloaded Models" list
2. Click "Delete" button
3. Confirm deletion (shows disk space to be freed)

##### Appearance Settings

- **Theme**: Choose Light, Dark, or Follow System
- **Theme Preview**: Preview theme effects in real-time
- Theme changes apply immediately to entire application

##### Language Settings

- **Current Language**: Display current interface language
- **Select Language**: Chinese (Simplified), English, Français
- Language changes apply immediately to entire application

---

### FAQ

#### 1. How do I download speech recognition models?

**Answer**: Go to "Settings" → "Model Management" → "Available Models", select a model and click "Download". Recommended to download `base` model for first-time use.

#### 2. Why is transcription slow?

**Answer**: Possible reasons:

- Using larger model (medium/large)
- Low device performance
- GPU acceleration not enabled

**Solutions**:

- Use smaller model (tiny/base)
- Enable GPU acceleration in settings (if you have NVIDIA GPU)
- Reduce concurrent task count

#### 3. How do I enable GPU acceleration?

**Answer**:

1. Ensure you have CUDA-capable NVIDIA GPU
2. Install PyTorch with CUDA support
3. In "Settings" → "Transcription Settings", set "Device" to "CUDA"
4. Set "Compute Type" to "float16" for best performance

#### 4. Translation feature not available?

**Answer**: Translation feature requires Google Translate API key:

1. Go to Google Cloud Console to create project
2. Enable Cloud Translation API
3. Create API key
4. Enter API key in "Settings" → "Real-time Recording Settings"

#### 5. How do I process video files?

**Answer**: Processing video files requires FFmpeg installation:

- **macOS**: `brew install ffmpeg`
- **Windows**: `choco install ffmpeg` or download from official website
- **Linux**: `sudo apt-get install ffmpeg`

Restart EchoNote after installation.

#### 6. External calendar sync failed?

**Answer**: Possible reasons:

- Network connection issues
- OAuth token expired
- API quota limits

**Solutions**:

1. Check network connection
2. Remove account in settings and reconnect
3. Click "Sync Now" to manually trigger sync
4. Check log file for detailed error information

#### 7. How do I backup my data?

**Answer**: EchoNote data is stored in:

- **Database**: `~/.echonote/data.db`
- **Recording Files**: `~/Documents/EchoNote/Recordings/`
- **Transcript Files**: `~/Documents/EchoNote/Transcripts/`
- **Config Files**: `~/.echonote/secrets.enc`

Regularly backup these files.

#### 8. Application starts slowly?

**Answer**: On first launch, the app needs to load models and initialize components, which may take 5-10 seconds. Subsequent launches will be faster.

If startup is consistently slow:

1. Check if there are many historical tasks
2. Clean up unnecessary models
3. Check if disk space is sufficient

#### 9. How do I uninstall the application?

**Answer**:

- **Windows**: Uninstall through Control Panel
- **macOS**: Drag application to Trash

To delete all data, manually delete `~/.echonote/` directory.

#### 10. Which languages are supported for transcription?

**Answer**: Whisper models support 99 languages, including:

- Chinese (Simplified/Traditional)
- English
- French
- Spanish
- German
- Japanese
- Korean
- And more

See OpenAI Whisper documentation for complete list.

---

### Troubleshooting

#### Transcription Failed

**Symptom**: Task status shows "Failed"

**Possible Causes**:

1. Unsupported file format
2. Corrupted file
3. Model not downloaded or corrupted
4. Insufficient memory

**Resolution Steps**:

1. Check if file format is in supported list
2. Try opening file with other player to confirm file integrity
3. Verify model in "Settings" → "Model Management"
4. Close other applications to free memory
5. Check error message in task details
6. Check log file: `~/.echonote/logs/echonote.log`

#### Real-time Recording No Sound

**Symptom**: Audio waveform shows no activity during recording

**Possible Causes**:

1. Microphone not connected or not authorized
2. Wrong audio input source selected
3. System volume settings issue

**Resolution Steps**:

1. Check if microphone works normally (test in system settings)
2. Select correct audio input source in application
3. Adjust gain slider
4. Check if system has granted microphone permission
5. Restart application

#### Calendar Sync Not Working

**Symptom**: External events not displayed

**Possible Causes**:

1. OAuth token expired
2. Network connection issues
3. API quota limits
4. Sync scheduler not started

**Resolution Steps**:

1. Check account connection status in settings
2. Click "Sync Now" to manually trigger
3. Remove account and reconnect
4. Check network connection
5. Check log file for detailed errors

#### Application Crashes

**Symptom**: Application suddenly closes

**Possible Causes**:

1. Insufficient memory
2. Corrupted model files
3. Corrupted database
4. Software bug

**Resolution Steps**:

1. Restart application
2. Check system resources (memory, disk space)
3. Verify models in "Settings" → "Model Management"
4. Backup database then try reset: delete `~/.echonote/data.db`
5. Check crash log: `~/.echonote/logs/echonote.log`
6. If problem persists, submit bug report

#### Performance Issues

**Symptom**: Application responds slowly

**Possible Causes**:

1. Insufficient device performance
2. Too many concurrent tasks
3. Model too large
4. Insufficient memory

**Resolution Steps**:

1. Reduce concurrent task count (Settings → Transcription Settings)
2. Use smaller model (tiny/base)
3. Close other applications to free resources
4. Clean up historical tasks and files
5. Restart application

#### File Permission Errors

**Symptom**: Cannot save or read files

**Possible Causes**:

1. Insufficient directory permissions
2. Insufficient disk space
3. File occupied by other program

**Resolution Steps**:

1. Check save directory permissions
2. Check disk space
3. Close other programs that might be using the file
4. Try changing save location (in settings)
5. Run application as administrator (Windows)

---

## Getting Help

If you encounter issues not covered in this guide:

1. **Check Log File**: `~/.echonote/logs/echonote.log`
2. **Check GitHub Issues**: Search for similar problems
3. **Submit Bug Report**: Include detailed error information and logs
4. **Contact Support**: Contact development team through project homepage

---

## Appendix

### Supported File Formats

**Audio Formats**:

- MP3 (.mp3)
- WAV (.wav)
- M4A (.m4a)
- FLAC (.flac)
- OGG (.ogg)
- OPUS (.opus)

**Video Formats** (requires FFmpeg):

- MP4 (.mp4)
- AVI (.avi)
- MKV (.mkv)
- MOV (.mov)
- WEBM (.webm)

### System Requirements

**Minimum Requirements**:

- **Operating System**: Windows 10/11, macOS 10.15+, Linux
- **Memory**: 4 GB RAM
- **Disk Space**: 2 GB (excluding models)
- **Processor**: Intel Core i3 or equivalent

**Recommended Configuration**:

- **Memory**: 8 GB RAM or more
- **Disk Space**: 10 GB (including multiple models)
- **Processor**: Intel Core i5 or better
- **Graphics**: NVIDIA GPU (CUDA support) for acceleration

### Model Sizes and Performance

| Model  | Size    | Speed   | Accuracy  | Recommended Use                             |
| ------ | ------- | ------- | --------- | ------------------------------------------- |
| tiny   | ~75 MB  | Fastest | Low       | Real-time transcription, quick preview      |
| base   | ~145 MB | Fast    | Medium    | Daily use, balanced choice                  |
| small  | ~466 MB | Medium  | High      | Important content, higher accuracy          |
| medium | ~1.5 GB | Slow    | Very High | Professional use, high quality requirements |
| large  | ~2.9 GB | Slowest | Highest   | Highest quality, speed not a concern        |

### Keyboard Shortcuts

| Function                   | Windows/Linux | macOS |
| -------------------------- | ------------- | ----- |
| Switch to Batch Transcribe | Ctrl+1        | ⌘+1   |
| Switch to Real-time Record | Ctrl+2        | ⌘+2   |
| Switch to Calendar Hub     | Ctrl+3        | ⌘+3   |
| Switch to Timeline         | Ctrl+4        | ⌘+4   |
| Open Settings              | Ctrl+,        | ⌘+,   |
| Search                     | Ctrl+F        | ⌘+F   |
| Copy                       | Ctrl+C        | ⌘+C   |
| Select All                 | Ctrl+A        | ⌘+A   |

---

**End of User Guide**
