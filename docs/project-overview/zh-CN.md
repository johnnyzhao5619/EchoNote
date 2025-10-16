# EchoNote 项目说明

> 如需最新内容，可参阅英文版 [`README.md`](README.md)。

## 1. 设计目标
- 提供离线优先的语音转录和日程管理体验。
- 通过模块化架构支持快速替换引擎（语音、翻译、日历）。
- 在桌面环境保证数据安全、可维护性与稳定性能。

## 2. 架构概览
```
┌───────────┐      ┌──────────┐      ┌───────────┐
│   UI 层   │ ───▶ │  Core 层 │ ───▶ │ Engines 层 │
└───────────┘      └──────────┘      └───────────┘
        │                 │                   │
        ▼                 ▼                   ▼
   utils/ 工具       data/ 数据层        外部服务 (音频、日历)
```
- **UI 层** (`ui/`)：PyQt6 组件、对话框、通知与国际化文本。
- **Core 层** (`core/`)：业务管理器，负责调度数据库、引擎和 UI 事件。
- **Engines 层** (`engines/`)：音频捕获、语音识别、翻译、日历同步的具体实现。
- **数据层** (`data/`)：SQLite 数据库、模型下载目录、密钥存储与文件系统访问。
- **工具层** (`utils/`)：日志、异常处理、资源监控、启动优化、国际化支持。

## 3. 关键模块
| 模块 | 位置 | 作用 |
| ---- | ---- | ---- |
| 配置管理 | `config/app_config.py` | 加载默认配置、验证必填项、保存用户偏好 |
| 数据库连接 | `data/database/connection.py` | 提供加密 SQLite 访问、版本管理、schema 初始化 |
| 语音模型管理 | `core/models/manager.py` | 管理模型下载、校验、后台验证任务 |
| 转录管理 | `core/transcription/manager.py` | 维护任务队列、调度语音引擎、处理输出 |
| 实时录制 | `core/realtime/recorder.py` | 协调音频捕获、语音引擎与翻译引擎 |
| 日历同步 | `core/calendar/manager.py` & `engines/calendar_sync/*` | 本地事件 CRUD 与外部同步适配器 |
| 时间线调度 | `core/timeline/auto_task_scheduler.py` | 根据日历事件安排自动录制/转录 |

## 4. 数据与安全
- **数据库**：`~/.echonote/data.db`，默认开启 AES 加密，密钥由 `data/security` 负责。
- **文件存储**：录音、转录输出默认位于 `~/Documents/EchoNote/`。
- **Secrets**：OAuth 凭据采用安全存储器，避免明文保存。
- **日志**：所有模块统一写入 `~/.echonote/logs/echonote.log`，便于排查。

## 5. 依赖管理
- 主依赖在 `requirements.txt`，开发依赖在 `requirements-dev.txt`。
- `utils/ffmpeg_checker` 和 `utils/resource_monitor` 负责运行期检测。
- 模型下载目录与缓存可在配置中自定义。

## 6. 测试策略
- **单元测试**：覆盖配置、数据库模型、工具函数。
- **集成测试**：验证转录流水线、日历同步、自动任务。
- **性能基线**：`tests/e2e_performance_test.py` 评估转录吞吐。

## 7. 维护建议
- 遵循 `docs/CODE_STANDARDS.md` 中的命名与结构约定。
- 引入新引擎时保持接口一致，确保 `core` 层无需大幅修改。
- 优先清理冗余日志与未使用资源，保持应用启动性能。
- 定期轮换密钥并验证数据库 schema 版本。

## 8. 未来演进方向
- 增加更多翻译引擎的可插拔适配。
- 扩展跨平台打包脚本，提供正式发行版本。
- 构建可视化分析仪表盘，展示使用统计与模型表现。

该文档会随着核心模块演进而更新，欢迎贡献。
