# EchoNote

本地优先的桌面助手，整合批量/实时转录、日历智能编排与可检索的时间线。

## 项目速览
- **框架**：PyQt6 桌面应用，入口位于 `main.py`
- **核心领域**：批量/实时转录、日历同步、自动任务、设置管理
- **运行原则**：隐私优先、加密持久化、主动的资源诊断

## 核心特性
1. **批量转录** —— `core/transcription` 调度 Faster-Whisper 引擎、支持任务重试与多格式导出。
2. **实时录制** —— `core/realtime` 与 `engines/audio` 提供音频捕获、增益控制、语音活动检测与可选翻译。
3. **日历中心** —— `core/calendar` 管理本地事件，`engines/calendar_sync` 负责 Google/Outlook 账户对接。
4. **时间线自动化** —— `core/timeline` 关联事件与录音，维护自动任务规则并提供历史检索。
5. **安全存储** —— `data/database`、`data/security`、`data/storage` 提供加密 SQLite、令牌保管与文件生命周期管理。
6. **系统健康** —— `utils/` 集中处理日志、诊断、资源监控与 FFmpeg 检测。

## 目录结构
```
EchoNote/
├── main.py                # 应用启动与依赖装配
├── config/                # 默认配置与运行时管理器
├── core/                  # 功能管理器（calendar、realtime、timeline、transcription、settings）
├── engines/               # 可插拔引擎（音频捕获、语音、翻译、日历同步）
├── data/                  # 数据库 schema/模型、加密存储、文件管理
├── ui/                    # Qt 组件、对话框与导航框架
├── utils/                 # 日志、国际化、诊断、资源监控
└── tests/                 # 单元与集成测试
```

## 环境要求
- Python 3.10 及以上
- 可选依赖：PyAudio（麦克风采集）、FFmpeg（媒体格式）、CUDA GPU（加速）
- 首次启动会在 `~/.echonote` 下写入加密数据库、日志与配置

## 运行项目
```bash
python -m venv .venv
source .venv/bin/activate   # Windows 使用 .venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

### 配置说明
- 默认配置位于 `config/default_config.json`，用户修改会保存到 `~/.echonote/app_config.json`。
- 录音与转录文件默认存放在 `~/Documents/EchoNote/`。
- 启用 Google 或 Outlook 同步前，请先在设置界面填入 OAuth 凭据。

## 质量与测试
- `pytest tests/unit` —— 核心逻辑与工具单元测试
- `pytest tests/integration` —— 数据库、引擎与调度器集成测试（需本地依赖）
- 其他端到端与性能场景位于 `tests/`

如需运行更多测试，请先执行 `pip install -r requirements-dev.txt` 安装开发依赖。

## 文档
- 使用手册：`docs/user-guide/zh-CN.md`
- 快速入门：`docs/quick-start/zh-CN.md`
- 项目说明：`docs/project-overview/zh-CN.md`
- 开发者参考：`docs/DEVELOPER_GUIDE.md`、`docs/API_REFERENCE.md`

## 许可证
项目遵循 [MIT License](LICENSE)。
