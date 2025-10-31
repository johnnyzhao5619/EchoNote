# Changelog

## Unreleased

### Added

- **Version Management System**: Centralized version management with single source of truth

  - `config/__version__.py` - Canonical version definition
  - `scripts/sync_version.py` - Automated version synchronization across all files
  - `scripts/bump_version.py` - Semantic version bumping with validation
  - `docs/VERSION_MANAGEMENT.md` - Comprehensive version management guide

- **Multilingual Documentation**: Comprehensive language-specific documentation system
  - `README.zh-CN.md` - Complete Chinese documentation with local context
  - `README.fr.md` - Complete French documentation with cultural adaptations
  - `docs/MULTILINGUAL_DOCUMENTATION.md` - Best practices guide for multilingual docs
  - Language-specific setup instructions, troubleshooting, and examples

### Changed

- **README Structure**: Reorganized main README.md following multilingual best practices

  - Simplified main README with focus on English content
  - Clear references to language-specific documentation
  - Improved navigation and user experience

- **Splash Screen**: Enhanced version display logic with consistent formatting
- **Configuration System**: Version now automatically injected from code, not config files
- **Main Application**: Improved version loading for startup splash screen

### Fixed

- **Version Consistency**: Eliminated version number discrepancies across project files
- **Startup Display**: Splash screen now always shows current application version
- **Documentation Maintenance**: Reduced content duplication and improved maintainability

## v1.1.1 - 2025-10-31

### Changed

- **Project Maintenance**: Comprehensive project cleanup and documentation reorganization
- **Documentation**: Restructured documentation following open-source best practices
- **Scripts**: Reduced script count from 43 to 8 core scripts (81% reduction)
- **File Structure**: Removed 60 temporary/redundant files (88% reduction overall)
- **Documentation Index**: Enhanced docs/README.md with better navigation and audience-specific sections

### Added

- **Project Status**: New unified project status document (docs/PROJECT_STATUS.md)
- **CI/CD Documentation**: Added comprehensive CI/CD guide (docs/CI_CD_GUIDE.md)
- **Performance Tests**: Added comprehensive performance test suite
- **UI Tests**: Added UI component test coverage
- **Core Tests**: Enhanced core module test coverage

### Removed

- **Temporary Scripts**: Removed 35 one-time analysis and fix scripts
- **Report Files**: Cleaned up 21 temporary report files
- **Cache Directories**: Removed build and analysis cache directories
- **Redundant Documentation**: Consolidated project status information

### Fixed

- **Documentation Links**: Updated all documentation cross-references
- **Project Structure**: Cleaned up project root directory
- **Git Ignore**: Enhanced .gitignore to prevent future temporary file accumulation

### Technical Notes

- **Zero Functionality Impact**: All application features remain identical
- **Test Coverage**: 607 tests, 100% pass rate maintained
- **Code Quality**: No regressions, all quality checks pass
- **Performance**: No impact on application performance
- **Maintenance**: Significantly improved project maintainability

### Changed

- Cleaned up redundant and outdated documentation files (14 files removed)
- Moved PROJECT_COMPLETION_REPORT.md to docs/ directory for better organization
- Simplified README.md model management instructions

### Removed

- Removed temporary progress tracking files (PROGRESS.txt, TASKS.md)
- Removed outdated project status reports (PROJECT_STATUS.md, REVIEW_COMPLETION_SUMMARY.md)
- Removed temporary bug fix documentation (BUGFIX_VIEWER_REOPEN.md, BUGFIX_WINDOW_STATE.md)
- Removed redundant release notes (RELEASE_NOTES_v1.1.0.md, already in CHANGELOG)
- Removed completed project review documents (PROJECT_REVIEW_2025.md, IMPROVEMENT_PLAN_2025.md)
- Removed temporary UI implementation summaries (4 files from ui/settings/ and ui/calendar_hub/)

## v1.1.0 - 2025-10-26

### Changed

- **BREAKING**: Migrated UI framework from PyQt6 to PySide6 for better license compatibility
- **BREAKING**: Updated project license from MIT to Apache 2.0
- Updated all Qt imports from `PyQt6.*` to `PySide6.*`
- Updated signal/slot syntax from `pyqtSignal`/`pyqtSlot` to `Signal`/`Slot`
- Updated QAction imports from `QtWidgets` to `QtGui` module
- Updated dependencies: `PyQt6>=6.6.0` → `PySide6>=6.6.0`
- Updated development dependencies: `PyQt6-stubs` → `PySide6-stubs>=6.5.0`
- Added Apache 2.0 license headers to all Python source files
- Updated all documentation to reflect PySide6 usage and Apache 2.0 licensing
- Updated build and packaging scripts to use PySide6 libraries and plugins

### Added

- Added PySide6 best practices to development guidelines
- Added license compliance documentation for LGPL v3 requirements
- Added migration verification script (`scripts/verify_pyside6_migration.py`)
- Added rollback procedures for migration safety

### Fixed

- Resolved license compatibility issues between PyQt6 (GPLv3) and MIT licensing
- Fixed signal type annotation syntax for PySide6 compatibility
- Updated enum access patterns where needed for PySide6
- Corrected import paths for Qt components that moved between modules

### Technical Notes

- **Zero Functionality Impact**: All application features remain identical after migration
- **Performance**: Startup time and memory usage remain within 10% of previous baseline
- **Compatibility**: Maintains support for macOS, Linux, and Windows platforms
- **License Compliance**: PySide6 (LGPL v3) is fully compatible with Apache 2.0 through dynamic linking
- **Commercial Use**: Now allows unrestricted commercial distribution without additional licensing

## v1.0.0 - 2025-10-23

### Changed

- 调整 `TimelineManager.get_timeline_events` 的分页策略：历史事件继续遵循 `page/page_size`，但第一页始终返回完整的未来事件列表，并新增 `future_total_count` 字段，便于前端与调度器依赖未来事件数据时保持兼容。
- 优化时间线搜索结果的自动任务加载逻辑，通过批量查询减少数据库往返次数。
- 数据库连接初始化时改为对 SQLCipher 密钥使用参数绑定，并在必要时回退到安全的引用方案，避免字符串拼接导致的注入风险。
- 修复转录任务在用户取消后仍继续生成结果文件并标记完成的问题：任务队列现在向任务处理函数传递 `cancel_event`，管理器会在检测到取消时立刻终止处理、保持数据库状态为 `cancelled`，同时不会产生新的导出文件或成功通知。
- 实时录制模块在创建日历事件与错误提示时接入国际化资源，根据当前语言返回标题、描述与警告信息，并同步更新中英法本地化文本。
- 实时录制在停止时会等待翻译协程完整退出：若后台翻译超时，将发送显式终止信号并清理队列，确保导出的翻译文件与累积内容一致。
- 时间线音频播放器新增媒体状态管理：在加载本地文件时执行严格路径校验，并在媒体不可播放或出错时自动禁用播放控件、反馈本地化错误提示，避免用户触发无效操作。

### Fixed

- 修复短录音在停止后因未满足最小时长而缺失转录与翻译的问题，停止录制时会自动补偿处理缓冲区中的剩余音频。
- 修正转录任务队列在任务被取消时错误地终止 worker 的问题：现在取消请求只会结束当前任务，worker 会继续处理后续排队项。
