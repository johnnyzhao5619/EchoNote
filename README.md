# EchoNote

**智能语音转录与日历管理应用 / Intelligent Voice Transcription and Calendar Management Application**

[![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)](https://github.com/yourusername/echonote)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey.svg)](https://github.com/yourusername/echonote)

---

## 简介 / Introduction

EchoNote 是一款跨平台桌面应用，专注于智能语音转录、翻译和日历管理。应用采用本地优先（local-first）理念，确保您的数据安全和离线可用性。

EchoNote is a cross-platform desktop application focused on intelligent voice transcription, translation, and calendar management. The application follows a local-first philosophy, ensuring your data security and offline availability.

### 核心功能 / Core Features

- 📝 **批量转录** / Batch Transcription

  - 支持多种音频/视频格式
  - 队列管理和并发处理
  - 多种输出格式（TXT, SRT, MD）

- 🎙️ **实时录制** / Real-time Recording

  - 实时语音转录
  - 可选翻译功能
  - 自动保存录音和转录

- 📅 **日历中心** / Calendar Hub

  - 统一管理本地和外部日历
  - 支持 Google Calendar 和 Outlook
  - 自动同步和事件管理

- ⏱️ **智能时间线** / Intelligent Timeline

  - 时间轴视图展示过去和未来事件
  - 自动任务调度
  - 录音和转录文件关联

- 🌍 **多语言支持** / Multi-language Support

  - 界面语言：中文、English、Français
  - 转录支持 99+ 种语言

- 🎨 **主题支持** / Theme Support
  - 浅色/深色主题
  - 跟随系统设置

---

## 快速开始 / Quick Start

### 安装 / Installation

#### Windows

```bash
# 下载并运行安装程序
EchoNote-Setup-1.0.0.exe
```

#### macOS

```bash
# 下载并打开 DMG 文件
open EchoNote-1.0.0.dmg
# 拖动到 Applications 文件夹
```

#### Linux

```bash
# 从源码运行
git clone https://github.com/yourusername/echonote.git
cd echonote
pip install -r requirements.txt
python main.py
```

### 首次运行 / First Run

1. 启动应用
2. 完成首次运行向导（选择语言、主题）
3. 下载语音识别模型（推荐 base 模型）
4. 开始使用！

详细说明请参考 [快速入门指南](docs/QUICK_START.md)。

For detailed instructions, see [Quick Start Guide](docs/QUICK_START.md).

---

## 文档 / Documentation

### 用户文档 / User Documentation

- 📘 **[用户指南 / User Guide](docs/USER_GUIDE.md)** - 完整的功能说明和使用教程
- ⚡ **[快速入门 / Quick Start](docs/QUICK_START.md)** - 5 分钟快速上手
- 📑 **[文档索引 / Documentation Index](docs/README.md)** - 所有文档导航

### 开发者文档 / Developer Documentation

- 👨‍💻 **[开发者指南 / Developer Guide](docs/DEVELOPER_GUIDE.md)** - 完整的开发者文档
- 📚 **[API 参考 / API Reference](docs/API_REFERENCE.md)** - 详细的 API 文档
- 🤝 **[贡献指南 / Contributing Guide](docs/CONTRIBUTING.md)** - 如何为项目做贡献
- 📏 **[代码规范 / Code Standards](docs/CODE_STANDARDS.md)** - 代码风格和最佳实践

### 技术文档 / Technical Documentation

- 📋 **[需求文档 / Requirements](.kiro/specs/echonote-core/requirements.md)** - 详细功能需求
- 🏗️ **[设计文档 / Design](.kiro/specs/echonote-core/design.md)** - 系统架构设计
- ✅ **[任务清单 / Tasks](.kiro/specs/echonote-core/tasks.md)** - 实现任务列表

### 其他文档 / Other Documentation

- 🚀 **[性能优化 / Performance](docs/PERFORMANCE_OPTIMIZATION_USER_GUIDE.md)** - 性能优化指南
- ❓ **[性能 FAQ / Performance FAQ](docs/PERFORMANCE_FAQ.md)** - 性能相关常见问题
- 📝 **[更新日志 / Changelog](CHANGELOG.md)** - 版本更新记录

---

## 系统要求 / System Requirements

### 最低要求 / Minimum Requirements

- **操作系统 / OS**: Windows 10/11, macOS 10.15+, Linux
- **内存 / RAM**: 4 GB
- **磁盘空间 / Disk**: 2 GB (不含模型 / excluding models)
- **处理器 / CPU**: Intel Core i3 或同等性能 / or equivalent

### 推荐配置 / Recommended Configuration

- **内存 / RAM**: 8 GB 或更多 / or more
- **磁盘空间 / Disk**: 10 GB (含多个模型 / including multiple models)
- **处理器 / CPU**: Intel Core i5 或更好 / or better
- **显卡 / GPU**: NVIDIA GPU (支持 CUDA / CUDA support) 用于加速 / for acceleration

---

## 技术栈 / Technology Stack

### 前端 / Frontend

- **框架 / Framework**: PyQt6
- **设计 / Design**: Microsoft Teams / Slack 风格

### 后端 / Backend

- **语言 / Language**: Python 3.8+
- **架构 / Architecture**: 模块化、可插拔设计

### 语音识别 / Speech Recognition

- **默认引擎 / Default**: faster-whisper (本地 / local)
- **可选 / Optional**: OpenAI, Google, Azure (云服务 / cloud services)

### 数据存储 / Data Storage

- **数据库 / Database**: SQLite (加密 / encrypted)
- **文件系统 / File System**: 本地存储 / Local storage

---

## 开发 / Development

### 环境设置 / Environment Setup

```bash
# 克隆仓库 / Clone repository
git clone https://github.com/yourusername/echonote.git
cd echonote

# 创建虚拟环境 / Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/macOS
# or
venv\Scripts\activate  # Windows

# 安装依赖 / Install dependencies
pip install -r requirements.txt

# 运行应用 / Run application
python main.py
```

### 项目结构 / Project Structure

```
echonote/
├── main.py                 # 应用入口 / Application entry
├── ui/                     # UI 组件 / UI components
├── core/                   # 业务逻辑 / Business logic
├── engines/                # 语音识别引擎 / Speech engines
├── data/                   # 数据层 / Data layer
├── utils/                  # 工具函数 / Utilities
├── resources/              # 资源文件 / Resources
├── docs/                   # 文档 / Documentation
└── tests/                  # 测试 / Tests
```

---

## 贡献 / Contributing

欢迎贡献！请查看 [贡献指南](CONTRIBUTING.md)（待创建）。

Contributions are welcome! Please see [Contributing Guide](CONTRIBUTING.md) (to be created).

### 开发流程 / Development Workflow

1. Fork 项目 / Fork the project
2. 创建特性分支 / Create feature branch (`git checkout -b feature/AmazingFeature`)
3. 提交更改 / Commit changes (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 / Push to branch (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request / Open Pull Request

---

## 许可证 / License

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件。

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 致谢 / Acknowledgments

- [OpenAI Whisper](https://github.com/openai/whisper) - 语音识别模型
- [faster-whisper](https://github.com/SYSTRAN/faster-whisper) - 优化的 Whisper 实现
- [PyQt6](https://www.riverbankcomputing.com/software/pyqt/) - GUI 框架
- 所有贡献者和用户 / All contributors and users

---

## 联系方式 / Contact

- **项目主页 / Project Home**: [GitHub](https://github.com/yourusername/echonote)
- **问题反馈 / Issues**: [GitHub Issues](https://github.com/yourusername/echonote/issues)
- **讨论 / Discussions**: [GitHub Discussions](https://github.com/yourusername/echonote/discussions)

---

## 状态 / Status

- ✅ 核心功能已完成 / Core features completed
- ✅ 用户文档已完成 / User documentation completed
- 🚧 打包分发进行中 / Packaging in progress
- 📅 预计发布 / Expected release: TBD

---

**Made with ❤️ by the EchoNote Team**
