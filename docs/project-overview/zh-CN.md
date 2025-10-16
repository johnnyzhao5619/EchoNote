# EchoNote 项目说明

> 如需最新内容，可参阅英文版 [`README.md`](README.md)。

## 1. 设计目标
- 提供离线优先的语音转录和日程管理体验。
- 通过可插拔引擎支持语音、翻译、日历提供商的独立演进。
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
- **数据层** (`data/`)：SQLite schema、模型、加密、存储工具及密钥管理。
- **工具层** (`utils/`)：日志、异常处理、资源监控、启动优化与国际化支持。

## 3. 关键模块
| 模块 | 位置 | 作用 |
| ---- | ---- | ---- |
| 配置管理 | `config/app_config.py` | 加载默认配置、验证必填项、保存用户偏好 |
| 数据库连接 | `data/database/connection.py` | 线程安全的 SQLite 访问、schema 初始化、可选 SQLCipher 密钥 |
| 数据模型 | `data/database/models.py` | 任务、日历事件、附件、自动任务配置、同步状态的 CRUD 工具 |
| 加密与令牌 | `data/security/` | AES-GCM 工具、OAuth 凭据保险箱、密钥管理 |
| 转录管理 | `core/transcription/manager.py` | 任务队列调度、引擎协同、格式转换 |
| 任务队列 | `core/transcription/task_queue.py` | 支持重试/退避与暂停/恢复的异步工作池 |
| 实时录制 | `core/realtime/recorder.py` | 音频捕获、流式转录、翻译派发、文件落地 |
| 日历管理 | `core/calendar/manager.py` | 本地 CRUD、同步计划、颜色策略、账户状态追踪 |
| 时间线管理 | `core/timeline/manager.py` | 时间线查询、分页、关联事件附件 |
| 自动任务调度 | `core/timeline/auto_task_scheduler.py` | 基于日历规则准备并触发会议录音/转录 |

## 4. 数据与安全
- **数据库**：`~/.echonote/data.db`，若系统支持 SQLCipher 则自动开启加密，密钥由 `data/security` 管理。
- **文件存储**：录音与转录默认保存在 `~/Documents/EchoNote/`，可在设置中自定义。
- **敏感信息**：OAuth 凭据通过安全存储管理，避免明文暴露。
- **日志**：所有模块统一写入 `~/.echonote/logs/echonote.log`，便于诊断。

## 5. 依赖管理
- 运行依赖位于 `requirements.txt`，开发依赖位于 `requirements-dev.txt`。
- `utils/ffmpeg_checker` 与 `utils/resource_monitor` 在运行期检测依赖与资源状态。
- 模型缓存路径可通过配置管理器自定义。

## 6. 测试策略
- **单元测试**：覆盖配置、数据库模型与工具模块。
- **集成测试**：验证转录流水线、日历同步、调度器流程。
- **性能基线**：`tests/e2e_performance_test.py` 评估转录吞吐。

## 7. 维护建议
- 遵循 `docs/CODE_STANDARDS.md` 中的命名与结构约定。
- 引入新引擎时保持既有接口，避免核心层大幅调整。
- 优先清理冗余资源与噪声日志，确保启动性能与可读性。
- 定期轮换密钥并确认数据库 schema 版本。

## 8. 未来演进方向
- 增加更多翻译引擎的可插拔适配。
- 扩展跨平台打包脚本，提供正式发行版本。
- 构建可视化分析仪表盘，展示使用统计与模型表现。

该文档会随着核心模块演进而更新，欢迎贡献。
