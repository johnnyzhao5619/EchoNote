# EchoNote 快速入门 / Quick Start Guide

## 中文版

### 5 分钟快速上手

#### 1. 首次启动（2 分钟）

1. **启动应用**

   - 双击应用图标启动 EchoNote

2. **完成向导**

   - 选择语言：中文（简体）
   - 选择主题：浅色或深色
   - 下载模型：点击「立即下载」下载 base 模型（约 145 MB）

3. **等待初始化**
   - 应用会自动完成初始化设置
   - 首次启动可能需要 5-10 秒

#### 2. 第一次转录（3 分钟）

1. **导入音频文件**

   ```
   批量转录 → 导入文件 → 选择音频文件
   ```

2. **开始转录**

   - 文件会自动添加到队列
   - 等待转录完成（进度条会显示）

3. **查看结果**
   - 点击「查看」按钮
   - 可以复制文本或导出为文件

### 常用操作速查

#### 批量转录音频

```
1. 点击「批量转录」
2. 点击「导入文件」或「导入文件夹」
3. 选择模型（推荐 base）
4. 等待转录完成
5. 点击「查看」或「导出」
```

#### 实时录制会议

```
1. 点击「实时录制」
2. 选择麦克风
3. 选择模型（推荐 tiny 或 base）
4. 点击「开始录制」
5. 说话（转录文本会实时显示）
6. 点击「停止录制」
7. 导出转录文本
```

#### 连接 Google 日历

```
1. 点击「设置」
2. 选择「日历」
3. 点击「添加 Google 账户」
4. 在浏览器中登录并授权
5. 返回应用，事件会自动同步
```

#### 下载新模型

```
1. 点击「设置」
2. 选择「模型管理」
3. 在「可下载模型」中选择模型
4. 点击「下载」
5. 等待下载完成
```

### 推荐设置

#### 日常使用

- **模型**: base
- **并发任务**: 2
- **设备**: 自动
- **主题**: 跟随系统

#### 高质量转录

- **模型**: medium 或 large
- **并发任务**: 1
- **设备**: CUDA（如果有 GPU）
- **计算类型**: float16

#### 快速转录

- **模型**: tiny
- **并发任务**: 3-5
- **设备**: 自动
- **计算类型**: int8

### 常见问题快速解决

#### 问题：转录失败

**快速检查**：

1. 文件格式是否支持？
2. 模型是否已下载？
3. 磁盘空间是否充足？

**解决方案**：

```
设置 → 模型管理 → 验证模型
```

#### 问题：转录速度慢

**快速解决**：

```
设置 → 转录设置 → 选择更小的模型（tiny 或 base）
```

#### 问题：无法录音

**快速检查**：

1. 麦克风是否连接？
2. 是否授予麦克风权限？
3. 音频输入源是否正确？

**解决方案**：

```
实时录制 → 音频输入 → 选择正确的设备
```

#### 问题：日历不同步

**快速解决**：

```
设置 → 日历 → 移除账户 → 重新添加
```

### 快捷键

| 功能     | 快捷键       |
| -------- | ------------ |
| 批量转录 | Ctrl+1 (⌘+1) |
| 实时录制 | Ctrl+2 (⌘+2) |
| 日历中心 | Ctrl+3 (⌘+3) |
| 时间线   | Ctrl+4 (⌘+4) |
| 设置     | Ctrl+, (⌘+,) |

### 数据位置

```
数据库：~/.echonote/data.db
录音：~/Documents/EchoNote/Recordings/
转录：~/Documents/EchoNote/Transcripts/
日志：~/.echonote/logs/echonote.log
```

---

## English Version

### 5-Minute Quick Start

#### 1. First Launch (2 minutes)

1. **Launch Application**

   - Double-click the application icon to start EchoNote

2. **Complete Wizard**

   - Choose language: English
   - Choose theme: Light or Dark
   - Download model: Click "Download Now" to download base model (~145 MB)

3. **Wait for Initialization**
   - App will automatically complete initial setup
   - First launch may take 5-10 seconds

#### 2. First Transcription (3 minutes)

1. **Import Audio File**

   ```
   Batch Transcribe → Import File → Select audio file
   ```

2. **Start Transcription**

   - File will be automatically added to queue
   - Wait for transcription to complete (progress bar will show)

3. **View Results**
   - Click "View" button
   - Can copy text or export to file

### Common Operations Quick Reference

#### Batch Transcribe Audio

```
1. Click "Batch Transcribe"
2. Click "Import File" or "Import Folder"
3. Select model (recommend base)
4. Wait for transcription to complete
5. Click "View" or "Export"
```

#### Real-time Record Meeting

```
1. Click "Real-time Record"
2. Select microphone
3. Select model (recommend tiny or base)
4. Click "Start Recording"
5. Speak (transcription text displays in real-time)
6. Click "Stop Recording"
7. Export transcription text
```

#### Connect Google Calendar

```
1. Click "Settings"
2. Select "Calendar"
3. Click "Add Google Account"
4. Log in and authorize in browser
5. Return to app, events will sync automatically
```

#### Download New Model

```
1. Click "Settings"
2. Select "Model Management"
3. Select model in "Available Models"
4. Click "Download"
5. Wait for download to complete
```

### Recommended Settings

#### Daily Use

- **Model**: base
- **Concurrent Tasks**: 2
- **Device**: Auto
- **Theme**: Follow System

#### High Quality Transcription

- **Model**: medium or large
- **Concurrent Tasks**: 1
- **Device**: CUDA (if GPU available)
- **Compute Type**: float16

#### Fast Transcription

- **Model**: tiny
- **Concurrent Tasks**: 3-5
- **Device**: Auto
- **Compute Type**: int8

### Quick Problem Solving

#### Problem: Transcription Failed

**Quick Check**:

1. Is file format supported?
2. Is model downloaded?
3. Is disk space sufficient?

**Solution**:

```
Settings → Model Management → Verify model
```

#### Problem: Slow Transcription

**Quick Fix**:

```
Settings → Transcription Settings → Select smaller model (tiny or base)
```

#### Problem: Cannot Record

**Quick Check**:

1. Is microphone connected?
2. Is microphone permission granted?
3. Is audio input source correct?

**Solution**:

```
Real-time Record → Audio Input → Select correct device
```

#### Problem: Calendar Not Syncing

**Quick Fix**:

```
Settings → Calendar → Remove account → Re-add
```

### Keyboard Shortcuts

| Function         | Shortcut     |
| ---------------- | ------------ |
| Batch Transcribe | Ctrl+1 (⌘+1) |
| Real-time Record | Ctrl+2 (⌘+2) |
| Calendar Hub     | Ctrl+3 (⌘+3) |
| Timeline         | Ctrl+4 (⌘+4) |
| Settings         | Ctrl+, (⌘+,) |

### Data Locations

```
Database: ~/.echonote/data.db
Recordings: ~/Documents/EchoNote/Recordings/
Transcripts: ~/Documents/EchoNote/Transcripts/
Logs: ~/.echonote/logs/echonote.log
```

---

**For detailed information, please refer to the [User Guide](USER_GUIDE.md)**
