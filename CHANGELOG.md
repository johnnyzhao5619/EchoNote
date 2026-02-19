# Changelog

All notable changes to EchoNote will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.3.5] - 2026-02-19

### Changed

- Released `v1.3.5` with batch transcription stability fixes, i18n coverage updates, calendar/timeline deletion flow improvements, and shell status consistency fixes.
- Updated canonical project and landing version references to `v1.3.5`.
- Updated landing package metadata to `1.3.5` for release consistency.

## [1.3.3] - 2026-02-19

### Changed

- Updated canonical project and landing version references to `v1.3.3`.
- Updated landing package metadata to `1.3.3` for release consistency.
- Extended `.gitignore` to exclude local test media artifacts (`test/*.mp4`).

## [1.3.1] - 2026-02-17

### Fixed

- **Settings Startup Error**: Resolved `SettingsManager` stale API calls (`get_all_settings`) that caused settings panel load failure.
- **Settings Persistence Path**: Updated settings save and rollback flows to use `ConfigManager` APIs (`get_all`, `save`, `replace_all`) after manager refactor.
- **Shutdown Save Hook**: Fixed main window shutdown settings persistence path to avoid calling removed `SettingsManager.save_settings`.

### Changed

- **Model Management Save Flow**: Aligned model settings dialog persistence with the current `config_manager.save()` path.
- **Version and Docs Alignment**: Bumped project and landing references to `v1.3.1` to keep release metadata consistent.

## [1.3.0] - 2026-02-17

### Added

- **Landing Navigation Resilience**: Introduced compact desktop `More` menu behavior for `lg~xl` widths to prevent header overflow in longer locales.
- **Locale Persistence**: Persisted selected landing page language in `localStorage` and synchronized `<html lang>` for accessibility and SEO consistency.
- **Release Documentation**: Added explicit `v1.3.0` highlights and deployment baseline updates in landing documentation.

### Changed

- **Landing Information Architecture**: Finalized single-page structure by removing the legacy `/about` route and template view.
- **Header Breakpoint Strategy**: Unified breakpoint visibility rules across mobile toggle, mobile menu panel, and desktop navigation blocks.
- **Language Switcher UX**: Replaced multi-button language controls with a stable single-select control to avoid wrapping and layout drift.
- **Project Versioning**: Bumped canonical application and landing versions to `1.3.0` across version source files.

### Fixed

- **Narrow-Width Header Bug**: Resolved the issue where clicking the top-right menu button showed only an `X` icon without opening the menu (caused by `md`/`lg` breakpoint mismatch).
- **Long Locale Header Overflow**: Fixed top navigation instability in English/French locales caused by long labels and wrapping controls.

## [1.2.0] - 2025-11-01

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
- **Unified English Documentation**: Streamlined documentation system with comprehensive English-only content
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

- Adjusted `TimelineManager.get_timeline_events` pagination strategy: historical events continue to follow `page/page_size`, but the first page always returns the complete future events list with a new `future_total_count` field for frontend and scheduler compatibility
- Optimized timeline search result auto-task loading logic by using batch queries to reduce database round trips
- Database connection initialization now uses parameter binding for SQLCipher keys with secure fallback to prevent injection risks from string concatenation
- Fixed transcription tasks continuing to generate result files and mark completion after user cancellation: task queue now passes `cancel_event` to processing functions, manager terminates processing immediately upon cancellation detection, maintains database state as `cancelled`, and prevents new export files or success notifications
- Real-time recording module integrated internationalization resources for calendar event creation and error prompts, returning titles, descriptions, and warning messages based on current language with synchronized localization text updates
- Real-time recording now waits for translation coroutines to fully exit when stopping: if background translation times out, explicit termination signals are sent and queues are cleaned to ensure exported translation files match accumulated content
- Timeline audio player added media state management: performs strict path validation when loading local files, automatically disables playback controls and provides localized error feedback when media is unplayable or errors occur, preventing invalid user operations

### Fixed

- Fixed short recordings missing transcription and translation after stopping due to not meeting minimum duration requirements: stopping recording now automatically compensates by processing remaining audio in the buffer
- Fixed transcription task queue incorrectly terminating workers when tasks are cancelled: cancellation requests now only end the current task, workers continue processing subsequent queued items

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
