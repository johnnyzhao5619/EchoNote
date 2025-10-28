# EchoNote v1.1.0 Release Notes

**Release Date:** October 26, 2025  
**Migration:** PySide6 + Apache 2.0 License

## 🎉 主要变更

### UI 框架迁移: PyQt6 → PySide6

成功从 PyQt6 迁移到 PySide6，解决许可证兼容性问题，支持无限制商业分发。

**核心优势:**

- ✅ **许可证兼容**: PySide6 (LGPL v3) 与 Apache 2.0 完全兼容
- ✅ **商业自由**: 无商业使用限制
- ✅ **官方支持**: Qt 公司官方维护
- ✅ **零功能影响**: 所有功能保持一致

### 许可证更新: MIT → Apache 2.0

更新为 Apache 2.0 许可证，提供更好的专利保护和企业兼容性。

## 🔧 技术变更

### 依赖更新

```diff
- PyQt6>=6.6.0
+ PySide6>=6.6.0
```

### 代码变更

```diff
- from PyQt6.QtCore import pyqtSignal, pyqtSlot
+ from PySide6.QtCore import Signal, Slot

- from PyQt6.QtWidgets import QAction
+ from PySide6.QtGui import QAction
```

## 📊 性能影响

迁移性能测试显示影响最小:

| 指标     | PyQt6 基准 | PySide6 结果 | 变化   |
| -------- | ---------- | ------------ | ------ |
| 启动时间 | 3.2s       | 3.1s         | -3% ✅ |
| 内存使用 | 285MB      | 292MB        | +2% ✅ |

## 🔄 升级指南

### 最终用户

**无需任何操作** - 透明迁移:

- 所有现有数据和配置保持不变
- 所有功能工作方式完全一致

### 开发者

**贡献者更新环境:**

```bash
pip uninstall PyQt6 PyQt6-stubs
pip install -r requirements-dev.txt
```

**基于 EchoNote 开发:**

- 更新依赖使用 PySide6
- 检查许可证兼容性 (Apache 2.0 + LGPL v3)

## 📋 许可证合规

### Apache 2.0 要求

分发时需要:

- ✅ 包含 LICENSE 文件
- ✅ 保留源文件版权声明

### PySide6 (LGPL v3) 合规

通过动态链接符合 LGPL v3:

- ✅ 动态链接 PySide6 (非静态链接)
- ✅ 用户可独立替换 PySide6 库

## 🐛 已知问题

### 兼容性说明

- **Python**: 需要 Python 3.10+ (无变化)
- **平台**: macOS, Linux, Windows (无变化)

## 🔄 回滚信息

如发现关键问题，可执行回滚:

```bash
git checkout pre-pyside6-migration
pip install PyQt6>=6.6.0
pip uninstall PySide6
```

## 📞 支持

### 问题报告

- **GitHub Issues**: 创建 issue 并标记`migration`和`pyside6`
- **许可证问题**: 标记`license`和`compliance`

---

**完整变更日志**: [v1.0.0...v1.1.0](docs/CHANGELOG.md#v110---2025-10-26)
