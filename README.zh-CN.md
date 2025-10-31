# EchoNote

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-Apache%202.0-2563EB.svg" alt="Apache 2.0 License badge"></a>
  <img src="https://img.shields.io/badge/Python-3.10%2B-4B5563.svg" alt="Python 3.10+ badge">
  <img src="https://img.shields.io/badge/Desktop-Local%20First-0EA5E9.svg" alt="Desktop local-first badge">
</p>

<p align="center">
  <strong>隐私优先的智能语音转录和日历管理桌面应用程序</strong>
</p>

<p align="center">
  <a href="README.md">English</a> •
  <a href="README.zh-CN.md">中文</a> •
  <a href="README.fr.md">Français</a>
</p>

> 📢 v1.2.0 维护版本发布，项目清理和文档重组完成。完整变更可查阅 [CHANGELOG](docs/CHANGELOG.md#v111---2025-10-31)。

## 🚀 快速开始

### 安装与设置

```bash
# 1. 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 2. 安装依赖
pip install -r requirements.txt

# 3. 启动应用
python main.py
```

### 首次启动设置

1. **存储配置**：选择录音和转录文件的保存路径
2. **模型下载**：下载 Faster-Whisper 模型
   - `tiny`: 最快，准确度较低（~75MB）
   - `base`: 速度和准确度平衡（~142MB）- **推荐大多数用户使用**
   - `small`: 较慢，准确度高（~462MB）
   - `medium/large`: 最慢，准确度最高（1.5-3GB）
3. **FFmpeg 检查**：验证 FFmpeg 安装以支持媒体格式
4. **可选**：配置日历同步（Google/Outlook OAuth）

## 🎯 核心功能

### 🎙️ 语音转录

- **批量转录**：处理音频/视频文件，支持多种格式
- **实时录制**：实时语音转录，支持语音活动检测
- **多格式导出**：TXT、SRT、Markdown 等格式
- **模型管理**：本地 Faster-Whisper 模型，支持 GPU 加速

### 📅 日历管理

- **多平台同步**：Google 日历、Outlook 日历集成
- **本地事件**：创建和管理本地日历事件
- **OAuth 安全**：安全的第三方账户连接
- **自动同步**：后台定期同步日历数据

### ⏰ 时间线智能

- **事件关联**：自动关联录音与日历事件
- **自动任务**：基于日历事件的自动录制
- **历史查询**：强大的事件和录音搜索功能
- **提醒系统**：智能提醒和通知

### 🔒 隐私与安全

- **本地优先**：所有数据存储在本地
- **加密存储**：SQLite 数据库应用级加密
- **安全令牌**：OAuth 令牌安全管理
- **无云依赖**：可完全离线使用

## 📋 系统要求

- **Python**：3.10 或更新版本
- **操作系统**：macOS、Linux、Windows
- **可选依赖**：
  - PyAudio（麦克风捕获）
  - FFmpeg（媒体格式支持）
  - CUDA GPU（Faster-Whisper 加速）

## 🏗️ 项目架构

```
EchoNote/
├── main.py                # 应用程序入口点
├── config/                # 配置管理和版本控制
│   ├── __version__.py     # 版本定义（单一数据源）
│   ├── app_config.py      # 配置管理器
│   └── default_config.json # 默认配置
├── core/                  # 核心业务逻辑
│   ├── transcription/     # 转录管理
│   ├── realtime/          # 实时录制
│   ├── calendar/          # 日历管理
│   ├── timeline/          # 时间线智能
│   ├── settings/          # 设置管理
│   └── models/            # 模型管理
├── engines/               # 外部服务集成
│   ├── speech/            # 语音识别引擎
│   ├── audio/             # 音频捕获
│   ├── translation/       # 翻译服务
│   └── calendar_sync/     # 日历同步
├── data/                  # 数据层
│   ├── database/          # 数据库模型
│   ├── security/          # 安全和加密
│   └── storage/           # 文件管理
├── ui/                    # PySide6 用户界面
│   ├── main_window.py     # 主窗口
│   ├── sidebar.py         # 侧边栏
│   ├── batch_transcribe/  # 批量转录界面
│   ├── realtime_record/   # 实时录制界面
│   ├── calendar_hub/      # 日历中心界面
│   ├── timeline/          # 时间线界面
│   ├── settings/          # 设置界面
│   └── common/            # 通用组件
├── utils/                 # 工具和实用程序
│   ├── logger.py          # 日志系统
│   ├── i18n.py            # 国际化
│   ├── error_handler.py   # 错误处理
│   └── qt_async.py        # Qt 异步桥接
├── scripts/               # 脚本工具
│   ├── sync_version.py    # 版本同步
│   └── bump_version.py    # 版本更新
└── tests/                 # 测试套件
    ├── unit/              # 单元测试
    ├── integration/       # 集成测试
    └── fixtures/          # 测试数据
```

## 📚 文档资源

| 用户群体     | 资源         | 位置                                                       |
| ------------ | ------------ | ---------------------------------------------------------- |
| **新用户**   | 快速入门指南 | [`docs/quick-start/README.md`](docs/quick-start/README.md) |
| **终端用户** | 用户手册     | [`docs/user-guide/README.md`](docs/user-guide/README.md)   |
| **开发者**   | 开发者指南   | [`docs/DEVELOPER_GUIDE.md`](docs/DEVELOPER_GUIDE.md)       |
| **开发者**   | API 参考     | [`docs/API_REFERENCE.md`](docs/API_REFERENCE.md)           |
| **贡献者**   | 编码标准     | [`docs/CODE_STANDARDS.md`](docs/CODE_STANDARDS.md)         |
| **贡献者**   | 贡献指南     | [`docs/CONTRIBUTING.md`](docs/CONTRIBUTING.md)             |
| **维护者**   | 版本管理     | [`docs/VERSION_MANAGEMENT.md`](docs/VERSION_MANAGEMENT.md) |
| **所有人**   | 项目状态     | [`docs/PROJECT_STATUS.md`](docs/PROJECT_STATUS.md)         |

## 🧪 开发与测试

### 开发环境设置

```bash
# 安装开发依赖
pip install -r requirements-dev.txt

# 安装预提交钩子
pre-commit install
```

### 运行测试

```bash
# 单元测试
pytest tests/unit

# 集成测试
pytest tests/integration

# 性能测试
pytest tests/e2e_performance_test.py

# 测试覆盖率
pytest --cov=core --cov=engines --cov=data --cov=ui --cov=utils --cov-report=term-missing
```

### 代码质量检查

```bash
# 版本一致性检查
python scripts/sync_version.py

# 代码格式化
black .
isort .

# 代码检查
flake8
mypy

# 安全检查
bandit -c pyproject.toml

# 运行所有预提交检查
pre-commit run --all-files
```

### 版本管理

```bash
# 检查当前版本
python -c "from config import get_version; print(get_version())"

# 更新版本（预览）
python scripts/bump_version.py patch --dry-run

# 更新版本（实际）
python scripts/bump_version.py patch
```

## 🔧 配置说明

### 配置文件位置

- **默认配置**：`config/default_config.json`
- **用户配置**：`~/.echonote/app_config.json`
- **用户数据**：`~/.echonote/`

### 主要配置项

```json
{
  "transcription": {
    "default_engine": "faster-whisper",
    "default_output_format": "txt",
    "max_concurrent_tasks": 2
  },
  "realtime": {
    "auto_save": true,
    "vad_threshold": 0.5
  },
  "calendar": {
    "sync_interval_minutes": 15
  },
  "ui": {
    "theme": "light",
    "language": "zh_CN"
  }
}
```

## 🌍 国际化支持

EchoNote 支持多语言界面：

- **中文（简体）**：`zh_CN`
- **英文**：`en_US`
- **法文**：`fr_FR`

语言文件位于 `resources/translations/` 目录。

## 🚨 故障排除

### 常见问题

1. **模型下载失败**

   - 检查网络连接
   - 确保有足够的磁盘空间
   - 查看日志文件：`~/.echonote/logs/`

2. **音频捕获问题**

   - 安装 PyAudio：`pip install PyAudio`
   - 检查麦克风权限
   - 验证音频设备

3. **FFmpeg 相关问题**

   - 安装 FFmpeg：访问 https://ffmpeg.org/
   - 确保 FFmpeg 在系统 PATH 中
   - 验证安装：`ffmpeg -version`

4. **日历同步问题**
   - 检查 OAuth 配置
   - 验证网络连接
   - 查看同步日志

### 日志和调试

```bash
# 启用调试日志
ECHO_NOTE_LOG_LEVEL=DEBUG python main.py

# 日志文件位置
~/.echonote/logs/app.log
```

## 📄 许可证

本项目基于 [Apache 2.0 许可证](LICENSE) 发布。

### 第三方许可证

- **PySide6** (LGPL v3)：UI 框架，通过动态链接使用，与 Apache 2.0 完全兼容
- **Faster-Whisper** (MIT)：语音识别引擎
- **其他依赖**：详见 [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md)

## 🤝 贡献

我们欢迎贡献！请查看我们的 [贡献指南](docs/CONTRIBUTING.md) 了解：

- 代码标准和风格指南
- 开发工作流程
- 测试要求
- 文档指南

## 📞 支持

- **文档**：[`docs/`](docs/) 目录
- **问题报告**：[GitHub Issues](https://github.com/your-org/echonote/issues)
- **讨论**：[GitHub Discussions](https://github.com/your-org/echonote/discussions)

## 📊 项目状态

- **版本**：v1.2.0（最新维护版本）
- **测试覆盖率**：607 个测试，100% 通过率
- **代码质量**：优秀（符合 PEP 8，完整类型注解）
- **文档**：完整且重新组织
- **许可证**：Apache 2.0（完全合规）

---

<p align="center">
  由 EchoNote 团队用 ❤️ 制作
</p>
