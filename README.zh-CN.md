# EchoNote

智能语音转录、日历编排与时间线洞察的桌面应用。

## 项目概览
- **框架**：PyQt6 桌面应用，主入口位于 `main.py`
- **业务模块**：批量/实时转录、日历同步、时间线与自动任务
- **核心原则**：本地优先、安全存储、资源自我诊断

### 核心特性
1. **批量转录**：`core/transcription` + `engines/speech`，支持音视频队列、模型懒加载、任务恢复。
2. **实时录制**：`core/realtime` 与 `engines/audio`，集成增益调节、语音活动检测与可选翻译。
3. **日历中心**：`core/calendar` 管理本地事件，配合 `engines/calendar_sync` 对接 Google/Outlook。
4. **时间线自动化**：`core/timeline` 提供事件视图、录音附件、自动转录提醒。
5. **安全与配置**：`config/app_config.py`、`data/security` 负责配置验证、数据库加密与密钥管理。
6. **资源保护**：`utils/resource_monitor`、`utils/ffmpeg_checker` 对外部依赖和系统资源进行预警。

### 系统结构
```
EchoNote/
├── main.py                # 启动逻辑与依赖注入
├── core/                  # 业务管理器 (calendar, realtime, timeline, transcription)
├── engines/               # 可插拔引擎 (audio, speech, translation, calendar_sync)
├── data/                  # 数据库、存储与安全管理
├── ui/                    # Qt 组件 (对话框、导航、主题)
├── utils/                 # 通用工具 (日志、国际化、监控)
└── tests/                 # 单元 / 集成 / 端到端测试
```

## 环境准备
- Python 3.10 及以上版本
- 可选依赖：PyAudio（实时录制）、FFmpeg（视频转录）、CUDA（GPU 加速）
- 首次运行会在 `~/.echonote` 下写入配置、日志与加密后的数据库

## 快速开始
```bash
python -m venv .venv
source .venv/bin/activate   # Windows 使用 .venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

配置项通过 `config/default_config.json` 提供默认值，用户修改会持久化到 `~/.echonote/app_config.json`。

## 测试与质量
- `pytest tests/unit`：核心逻辑与工具单元测试
- `pytest tests/integration`：数据库、引擎与管理器集成测试（需要本地依赖）
- `pytest tests/e2e_performance_test.py`：性能回归基线（可选）

运行测试前请确保安装开发依赖 `pip install -r requirements-dev.txt`，并在必要时准备音频输入或日历凭据。

## 文档
- 使用手册：`docs/USER_GUIDE.zh-CN.md`
- 快速入门：`docs/QUICK_START.zh-CN.md`
- 项目说明：`docs/PROJECT_OVERVIEW.zh-CN.md`
- 开发者参考：`docs/DEVELOPER_GUIDE.md`, `docs/API_REFERENCE.md`

更多文档导航请参见 `docs/README.md`。

## 许可证
项目遵循 [MIT License](LICENSE)。
