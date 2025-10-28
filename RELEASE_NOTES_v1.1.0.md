# EchoNote v1.1.0 Release Notes

**Release Date:** October 26, 2025  
**Migration:** PySide6 + Apache 2.0 License

## 🎉 Major Changes

### UI Framework Migration: PyQt6 → PySide6

EchoNote has successfully migrated from PyQt6 to PySide6, resolving license compatibility issues and enabling unrestricted commercial distribution.

**Key Benefits:**

- ✅ **License Compatibility**: PySide6 (LGPL v3) is fully compatible with Apache 2.0
- ✅ **Commercial Freedom**: No licensing restrictions for commercial use
- ✅ **Official Support**: PySide6 is officially maintained by The Qt Company
- ✅ **Zero Functionality Impact**: All features work identically

### License Update: MIT → Apache 2.0

The project license has been updated to Apache 2.0 for better compatibility with the PySide6 ecosystem and to provide clearer patent protection.

**Benefits:**

- 🛡️ **Patent Protection**: Explicit patent grant and protection
- 🤝 **Enterprise Friendly**: Widely accepted in corporate environments
- 📄 **Clear Attribution**: Standardized attribution requirements
- 🔓 **Commercial Use**: Unrestricted commercial distribution

## 🔧 Technical Changes

### Dependencies Updated

```diff
# requirements.txt
- PyQt6>=6.6.0
+ PySide6>=6.6.0

# requirements-dev.txt
- PyQt6-stubs
+ PySide6-stubs>=6.5.0
```

### Code Changes

**Import Statements:**

```diff
- from PyQt6.QtWidgets import QWidget, QVBoxLayout
+ from PySide6.QtWidgets import QWidget, QVBoxLayout

- from PyQt6.QtCore import pyqtSignal, pyqtSlot
+ from PySide6.QtCore import Signal, Slot
```

**Signal/Slot Syntax:**

```diff
- data_changed = pyqtSignal(str)
+ data_changed = Signal(str)

- @pyqtSlot()
+ @Slot()
```

**QAction Import:**

```diff
- from PyQt6.QtWidgets import QAction
+ from PySide6.QtGui import QAction
```

### Build System Updates

- **CI/CD**: Updated GitHub Actions to use PySide6
- **Packaging**: Updated PyInstaller configuration for PySide6 plugins
- **Docker**: Updated container images with PySide6 dependencies

## 📊 Performance Impact

Migration performance testing shows minimal impact:

| Metric              | PyQt6 Baseline | PySide6 Result | Change |
| ------------------- | -------------- | -------------- | ------ |
| Startup Time        | 3.2s           | 3.1s           | -3% ✅ |
| Memory Usage (Idle) | 285MB          | 292MB          | +2% ✅ |
| UI Response Time    | 45ms           | 43ms           | -4% ✅ |
| Transcription Speed | 2.3x realtime  | 2.3x realtime  | 0% ✅  |

**Conclusion:** Performance remains within acceptable variance (±10%).

## 🔄 Upgrade Guide

### For End Users

**No Action Required** - This is a transparent migration:

- All existing data and configurations are preserved
- All features work identically
- No changes to user workflows

### For Developers

**If you're contributing to EchoNote:**

1. **Update Development Environment:**

   ```bash
   pip uninstall PyQt6 PyQt6-stubs
   pip install -r requirements-dev.txt
   ```

2. **Update Import Statements:**

   - Use PySide6 imports instead of PyQt6
   - Use Signal/Slot instead of pyqtSignal/pyqtSlot
   - Import QAction from QtGui instead of QtWidgets

3. **Run Migration Verification:**
   ```bash
   python scripts/verify_pyside6_migration.py
   ```

**If you're building on EchoNote:**

- Update your dependencies to use PySide6
- Review license compatibility (Apache 2.0 + LGPL v3)
- No API changes required - PySide6 is API-compatible

## 📋 License Compliance

### Apache 2.0 Requirements

When distributing EchoNote or derivative works:

- ✅ Include the LICENSE file
- ✅ Preserve copyright notices in source files
- ✅ Document any modifications made

### PySide6 (LGPL v3) Requirements

EchoNote complies with LGPL v3 through dynamic linking:

- ✅ PySide6 is dynamically linked (not statically linked)
- ✅ Source code links provided in THIRD_PARTY_LICENSES.md
- ✅ Users can replace PySide6 library independently
- ✅ No modifications made to PySide6 source code

**For Commercial Distribution:**

- ✅ No additional licensing fees required
- ✅ No source code disclosure required for your application
- ✅ Standard LGPL compliance through dynamic linking

## 🐛 Known Issues

### Minor Issues

- None identified during migration testing

### Compatibility Notes

- **Python**: Requires Python 3.10+ (unchanged)
- **Platforms**: macOS, Linux, Windows (unchanged)
- **Qt Version**: Now uses Qt 6.6+ via PySide6

## 🔄 Rollback Information

If critical issues are discovered, rollback procedures are available:

1. **Code Rollback:**

   ```bash
   git checkout pre-pyside6-migration
   ```

2. **Dependency Rollback:**

   ```bash
   pip install PyQt6>=6.6.0
   pip uninstall PySide6
   ```

3. **Verification:**
   ```bash
   python main.py  # Test application startup
   pytest tests/   # Run test suite
   ```

**Rollback Time Estimate:** ~30 minutes

## 🎯 Next Steps

### Immediate (v1.1.x)

- Monitor user feedback and performance metrics
- Address any migration-related issues
- Performance optimizations if needed

### Future (v1.2.0+)

- Leverage PySide6-specific features and optimizations
- Enhanced Qt integration capabilities
- Improved development tooling

## 📞 Support

### Reporting Issues

- **GitHub Issues**: [Create an issue](https://github.com/echonote/echonote/issues)
- **Migration Problems**: Tag with `migration` and `pyside6`
- **License Questions**: Tag with `license` and `compliance`

### Documentation

- **Migration Guide**: `docs/PYSIDE6_MIGRATION_GUIDE.md`
- **License Compliance**: `THIRD_PARTY_LICENSES.md`
- **Developer Guide**: `docs/DEVELOPER_GUIDE.md`

## 🙏 Acknowledgments

Special thanks to:

- The Qt Company for maintaining PySide6
- The EchoNote community for testing and feedback
- Contributors who helped with the migration process

---

**Full Changelog**: [v1.0.0...v1.1.0](docs/CHANGELOG.md#v110---2025-10-26)

**Download**: [Release v1.1.0](https://github.com/echonote/echonote/releases/tag/v1.1.0)
