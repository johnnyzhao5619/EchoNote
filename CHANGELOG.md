# Changelog

All notable changes to EchoNote will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.2.0] - 2025-01-31

### Added

- **Base Manager Class**: Introduced `BaseManager` to standardize manager initialization patterns
- **Validation Utilities**: Created `utils/validation.py` with common validation functions to reduce code duplication
- **UI Layout Constants**: Added centralized constants to eliminate hardcoded values in settings pages
- **Type Annotations**: Comprehensive type annotations for better code maintainability and IDE support
- **Error Handling**: Improved error handling and logging consistency across all managers

### Changed

- **Version Management**: Updated to version 1.2.0 across all configuration files
- **Code Structure**: Refactored realtime settings page to use constants instead of magic numbers
- **Import Organization**: Improved import organization and removed unused imports following Python best practices
- **Code Quality**: Enhanced code structure following open source best practices

### Fixed

- **Type Imports**: Fixed missing type imports in calendar manager (`OAuthManager`, `I18nManager`)
- **Unused Imports**: Removed unused PySide6 widget imports in realtime settings page
- **Import Standards**: Corrected import organization to follow project standards
- **Runtime Errors**: Fixed potential runtime errors from undefined imports and missing dependencies

### Technical Improvements

- **Constants Management**: Eliminated hardcoded UI dimensions and replaced with named constants
- **Configuration**: Standardized gain slider configuration using centralized constants
- **Maintainability**: Improved code maintainability through better separation of concerns
- **Validation Patterns**: Enhanced validation patterns for consistent error handling
- **Code Duplication**: Reduced code duplication across manager classes with base class pattern

### Code Quality

- **Formatting**: Applied consistent formatting using Black and isort
- **Type Safety**: Improved type safety with proper type annotations
- **Documentation**: Enhanced documentation and code comments
- **Best Practices**: Followed Python best practices for import organization
- **Compatibility**: Maintained full backward compatibility with existing functionality

## [1.1.1] - 2025-10-31

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
- **Project Status**: New unified project status document (`docs/PROJECT_STATUS.md`)
- **CI/CD Documentation**: Added comprehensive CI/CD guide (`docs/CI_CD_GUIDE.md`)
- **Performance Tests**: Added comprehensive performance test suite
- **UI Tests**: Added UI component test coverage
- **Core Tests**: Enhanced core module test coverage

### Changed

- **Project Maintenance**: Comprehensive project cleanup and documentation reorganization
- **Documentation**: Restructured documentation following open-source best practices
- **Scripts**: Reduced script count from 43 to 8 core scripts (81% reduction)
- **File Structure**: Removed 60 temporary/redundant files (88% reduction overall)
- **Documentation Index**: Enhanced `docs/README.md` with better navigation and audience-specific sections
- **README Structure**: Reorganized main README.md following multilingual best practices
- **Splash Screen**: Enhanced version display logic with consistent formatting
- **Configuration System**: Version now automatically injected from code, not config files
- **Main Application**: Improved version loading for startup splash screen

### Removed

- **Temporary Scripts**: Removed 35 one-time analysis and fix scripts
- **Report Files**: Cleaned up 21 temporary report files
- **Cache Directories**: Removed build and analysis cache directories
- **Redundant Documentation**: Consolidated project status information
- **Temporary Files**: Removed temporary progress tracking files and outdated project status reports

### Fixed

- **Version Consistency**: Eliminated version number discrepancies across project files
- **Startup Display**: Splash screen now always shows current application version
- **Documentation Maintenance**: Reduced content duplication and improved maintainability
- **Documentation Links**: Updated all documentation cross-references
- **Project Structure**: Cleaned up project root directory

### Technical Notes

- **Zero Functionality Impact**: All application features remain identical
- **Test Coverage**: 607 tests, 100% pass rate maintained
- **Code Quality**: No regressions, all quality checks pass
- **Performance**: No impact on application performance
- **Maintenance**: Significantly improved project maintainability

## [1.1.0] - 2025-10-26

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

## [1.0.0] - 2025-10-23

### Changed

- 调整 `TimelineManager.get_timeline_events` 的分页策略：历史事件继续遵循 `page/page_size`，但第一页始终返回完整的未来事件列表，并新增 `future_total_count` 字段，便于前端与调度器依赖未来事件数据时保持兼容
- 优化时间线搜索结果的自动任务加载逻辑，通过批量查询减少数据库往返次数
- 数据库连接初始化时改为对 SQLCipher 密钥使用参数绑定，并在必要时回退到安全的引用方案，避免字符串拼接导致的注入风险
- 修复转录任务在用户取消后仍继续生成结果文件并标记完成的问题：任务队列现在向任务处理函数传递 `cancel_event`，管理器会在检测到取消时立刻终止处理、保持数据库状态为 `cancelled`，同时不会产生新的导出文件或成功通知
- 实时录制模块在创建日历事件与错误提示时接入国际化资源，根据当前语言返回标题、描述与警告信息，并同步更新中英法本地化文本
- 实时录制在停止时会等待翻译协程完整退出：若后台翻译超时，将发送显式终止信号并清理队列，确保导出的翻译文件与累积内容一致
- 时间线音频播放器新增媒体状态管理：在加载本地文件时执行严格路径校验，并在媒体不可播放或出错时自动禁用播放控件、反馈本地化错误提示，避免用户触发无效操作

### Fixed

- 修复短录音在停止后因未满足最小时长而缺失转录与翻译的问题，停止录制时会自动补偿处理缓冲区中的剩余音频
- 修正转录任务队列在任务被取消时错误地终止 worker 的问题：现在取消请求只会结束当前任务，worker 会继续处理后续排队项

---

## Release Notes

### Version 1.2.0 Focus Areas

This release focuses on code quality improvements, maintainability enhancements, and preparation for future development. Key improvements include:

1. **Code Structure**: Introduction of base classes and utilities to reduce duplication
2. **Constants Management**: Centralized configuration values to eliminate magic numbers
3. **Type Safety**: Enhanced type annotations for better IDE support and error prevention
4. **Import Organization**: Cleaned up imports following Python best practices
5. **Validation**: Standardized validation patterns across the application

### Compatibility

This release maintains full backward compatibility with existing configurations and data. No user action is required for the upgrade.

### Development Guidelines

For developers contributing to EchoNote:

- Use the new `BaseManager` class for future manager implementations
- Utilize validation utilities from `utils/validation.py` for consistent error handling
- Follow the established constants pattern for UI dimensions and configuration values
- Ensure proper type annotations for all new code
- Follow the import organization standards established in this release

### Migration Notes

- All existing configurations and user data remain compatible
- No breaking changes to public APIs
- Enhanced error messages provide better debugging information
- Improved type safety helps catch errors during development
