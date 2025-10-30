# EchoNote Troubleshooting Guide

本文档提供常见问题的诊断和解决方案。

## 目录

1. [模型加载问题](#模型加载问题)
2. [实时录音问题](#实时录音问题)
3. [UI 相关问题](#ui-相关问题)
4. [FFmpeg 相关问题](#ffmpeg-相关问题)
5. [数据库问题](#数据库问题)

---

## 模型加载问题

### 问题：提示"Model 'xxx' is not downloaded"但模型已下载

**症状**：

- 在设置页面看到模型显示为"已下载"
- 但在使用转录功能时提示模型未下载
- 日志中显示 `ValueError: Model 'xxx' is not downloaded`

**可能原因**：

1. 配置文件中的模型名称与实际下载的模型不匹配
2. 模型文件不完整或损坏
3. 模型目录权限问题

**诊断步骤**：

1. 检查配置文件中的模型设置：

```bash
cat ~/.echonote/app_config.json | grep -A 10 "faster_whisper"
```

2. 检查实际下载的模型：

```bash
ls -la ~/.echonote/models/
```

3. 验证模型文件完整性：

```bash
# 检查模型目录中是否包含必需文件
ls -la ~/.echonote/models/[model_name]/
# 应该包含: config.json, model.bin, tokenizer.json
```

**解决方案**：

**方案 1：使用已下载的模型**

1. 打开设置 > 转录
2. 在"默认模型"下拉菜单中选择一个已下载的模型
3. 点击"保存"

**方案 2：重新下载模型**

1. 打开设置 > 模型管理
2. 找到需要的模型，点击"删除"（如果已部分下载）
3. 点击"下载"重新下载完整模型
4. 等待下载完成后，返回设置 > 转录
5. 选择刚下载的模型并保存

**方案 3：手动修复配置**
编辑 `~/.echonote/app_config.json`：

```json
{
  "transcription": {
    "faster_whisper": {
      "model_size": "tiny", // 改为已下载的模型名称
      "default_model": "tiny" // 确保与 model_size 一致
    }
  }
}
```

### 问题：模型下载失败

**症状**：

- 下载进度卡住不动
- 下载失败并显示网络错误
- 下载完成但模型不可用

**可能原因**：

1. 网络连接问题
2. Hugging Face 服务不可用
3. 磁盘空间不足
4. 防火墙或代理设置

**解决方案**：

1. 检查网络连接：

```bash
# 测试 Hugging Face 连接
curl -I https://huggingface.co
```

2. 检查磁盘空间：

```bash
df -h ~/.echonote/models
```

3. 配置代理（如需要）：

```bash
export HTTP_PROXY=http://your-proxy:port
export HTTPS_PROXY=http://your-proxy:port
```

4. 使用镜像站点（中国用户）：

```bash
export HF_ENDPOINT=https://hf-mirror.com
```

---

## 实时录音问题

### 问题：无法开始录音

**症状**：

- 点击录音按钮后提示错误
- 错误信息："Speech recognition model is not available"

**解决方案**：

1. 确保至少下载了一个模型（参见[模型加载问题](#模型加载问题)）

2. 检查麦克风权限：

   - **macOS**: 系统偏好设置 > 安全性与隐私 > 隐私 > 麦克风
   - **Windows**: 设置 > 隐私 > 麦克风
   - **Linux**: 检查 PulseAudio/ALSA 配置

3. 检查音频设备：

```bash
# 列出可用的音频设备
python -c "import pyaudio; p = pyaudio.PyAudio(); [print(f'{i}: {p.get_device_info_by_index(i)[\"name\"]}') for i in range(p.get_device_count())]"
```

### 问题：录音有声音但没有转录文本

**症状**：

- 录音正常进行
- 音频波形显示正常
- 但转录区域没有文本输出

**可能原因**：

1. 音频音量太低
2. VAD（语音活动检测）阈值设置过高
3. 模型加载失败

**解决方案**：

1. 调整麦克风增益：

   - 打开设置 > 实时录音
   - 调整"麦克风增益"滑块
   - 建议值：1.0 - 1.5

2. 调整 VAD 阈值：

   - 打开设置 > 实时录音
   - 降低"VAD 阈值"（建议 0.3 - 0.5）

3. 检查日志：

```bash
tail -f ~/.echonote/logs/echonote.log | grep -i "transcription\|error"
```

---

## UI 相关问题

### 问题：界面显示异常或崩溃

**症状**：

- 窗口无法打开
- 按钮或控件显示错误
- 应用崩溃并显示 Qt 相关错误

**解决方案**：

1. 清除 UI 缓存：

```bash
rm -rf ~/.echonote/.cache
rm -rf ~/.echonote/settings.ini
```

2. 重置窗口状态：

```bash
# 删除窗口状态配置
rm ~/.echonote/window_state.json
```

3. 检查 PySide6 安装：

```bash
python -c "from PySide6 import QtWidgets; print('PySide6 OK')"
```

### 问题：主题切换不生效

**症状**：

- 切换主题后界面没有变化
- 部分控件主题不一致

**解决方案**：

1. 重启应用
2. 检查主题文件：

```bash
ls -la resources/themes/
# 应该包含: light.qss, dark.qss
```

3. 手动设置主题：
   编辑 `~/.echonote/app_config.json`：

```json
{
  "ui": {
    "theme": "light" // 或 "dark"
  }
}
```

---

## FFmpeg 相关问题

### 问题：无法转录视频文件

**症状**：

- 音频文件可以正常转录
- 视频文件导入失败或转录失败
- 错误信息提示 FFmpeg 相关问题

**解决方案**：

1. 检查 FFmpeg 安装：

```bash
ffmpeg -version
ffprobe -version
```

2. 安装 FFmpeg：

**macOS**:

```bash
brew install ffmpeg
```

**Ubuntu/Debian**:

```bash
sudo apt update
sudo apt install ffmpeg
```

**Windows**:

- 从 https://ffmpeg.org/download.html 下载
- 解压到 `C:\ffmpeg`
- 添加 `C:\ffmpeg\bin` 到系统 PATH

3. 验证安装：

```bash
# 重启 EchoNote 后检查日志
grep -i ffmpeg ~/.echonote/logs/echonote.log
```

---

## 数据库问题

### 问题：数据库损坏或无法访问

**症状**：

- 应用启动失败
- 错误信息提示数据库相关问题
- 历史记录丢失

**解决方案**：

**警告：以下操作可能导致数据丢失，请先备份！**

1. 备份数据库：

```bash
cp ~/.echonote/data.db ~/.echonote/data.db.backup
```

2. 检查数据库完整性：

```bash
sqlite3 ~/.echonote/data.db "PRAGMA integrity_check;"
```

3. 如果数据库损坏，尝试修复：

```bash
sqlite3 ~/.echonote/data.db ".recover" | sqlite3 ~/.echonote/data_recovered.db
mv ~/.echonote/data.db ~/.echonote/data.db.corrupted
mv ~/.echonote/data_recovered.db ~/.echonote/data.db
```

4. 如果无法修复，重置数据库：

```bash
rm ~/.echonote/data.db
# 重启应用将创建新数据库
```

---

## 日志和诊断

### 查看日志

日志文件位置：`~/.echonote/logs/echonote.log`

查看最新日志：

```bash
tail -f ~/.echonote/logs/echonote.log
```

查看错误日志：

```bash
grep -i error ~/.echonote/logs/echonote.log
```

查看特定功能的日志：

```bash
# 转录相关
grep -i transcription ~/.echonote/logs/echonote.log

# 模型相关
grep -i model ~/.echonote/logs/echonote.log

# 录音相关
grep -i recording ~/.echonote/logs/echonote.log
```

### 启用调试模式

设置环境变量：

```bash
export ECHO_NOTE_LOG_LEVEL=DEBUG
python main.py
```

### 收集诊断信息

运行诊断脚本：

```bash
python scripts/diagnose.py > diagnosis.txt
```

诊断信息包括：

- 系统信息
- Python 版本和依赖
- 配置文件内容
- 模型状态
- 数据库状态
- 最近的错误日志

---

## 获取帮助

如果以上方法都无法解决问题：

1. **查看文档**：

   - [开发者指南](DEVELOPER_GUIDE.md)
   - [API 参考](API_REFERENCE.md)

2. **搜索已知问题**：

   - GitHub Issues: https://github.com/johnnyzhao5619/echonote/issues

3. **提交问题报告**：

   - 包含完整的错误信息
   - 附上诊断信息（`diagnosis.txt`）
   - 说明复现步骤
   - 注明操作系统和 Python 版本

4. **社区支持**：
   - GitHub Discussions
   - 项目 Wiki

---

## 常见错误代码

| 错误代码             | 含义          | 解决方案             |
| -------------------- | ------------- | -------------------- |
| `MODEL_NOT_FOUND`    | 模型未下载    | 下载所需模型         |
| `AUDIO_DEVICE_ERROR` | 音频设备问题  | 检查麦克风权限和设备 |
| `DATABASE_ERROR`     | 数据库错误    | 检查数据库完整性     |
| `NETWORK_ERROR`      | 网络连接问题  | 检查网络和代理设置   |
| `FFMPEG_NOT_FOUND`   | FFmpeg 未安装 | 安装 FFmpeg          |
| `PERMISSION_DENIED`  | 权限不足      | 检查文件和目录权限   |

---

## 性能优化建议

### 转录性能

1. **使用 GPU 加速**（如果可用）：

   - 设置 > 模型管理 > 设备：选择 "CUDA"
   - 确保安装了 CUDA 驱动

2. **选择合适的模型**：

   - `tiny`: 最快，准确度较低
   - `base`: 平衡速度和准确度
   - `small`: 较慢，准确度高
   - `medium/large`: 最慢，准确度最高

3. **调整并发任务数**：
   - 设置 > 转录 > 最大并发任务数
   - 建议值：CPU 核心数的 50-75%

### 内存优化

1. **关闭不需要的功能**：

   - 禁用自动翻译（如不需要）
   - 减少时间线显示范围

2. **定期清理**：

```bash
# 清理旧的录音文件
find ~/Documents/EchoNote/Recordings -mtime +30 -delete

# 清理缓存
rm -rf ~/.echonote/.cache/*
```

---

最后更新：2025-10-30
