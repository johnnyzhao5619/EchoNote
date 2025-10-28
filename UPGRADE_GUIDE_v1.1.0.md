# Upgrade Guide: EchoNote v1.1.0

## Overview

EchoNote v1.1.0 introduces a major migration from PyQt6 to PySide6 and updates the license from MIT to Apache 2.0. This guide helps you understand the changes and upgrade process.

## For End Users

### ✅ No Action Required

This is a **transparent migration** for end users:

- All your existing data is preserved
- All features work identically
- No changes to workflows or interfaces
- Settings and configurations remain intact

### Installation

**New Installations:**

```bash
# Download from releases page
# Or install via package manager (when available)
```

**Existing Installations:**

- Simply update to v1.1.0 through your normal update process
- No manual migration steps required

## For Developers

### Prerequisites

- Python 3.10+ (unchanged)
- Remove existing PyQt6 installations to avoid conflicts

### Development Environment Update

1. **Update Dependencies:**

   ```bash
   # Remove old dependencies
   pip uninstall PyQt6 PyQt6-stubs

   # Install new dependencies
   pip install -r requirements-dev.txt
   ```

2. **Verify Installation:**
   ```bash
   python -c "import PySide6; print('PySide6 installed successfully')"
   ```

### Code Migration (for contributors)

**Import Changes:**

```python
# Old (PyQt6)
from PyQt6.QtWidgets import QWidget, QVBoxLayout
from PyQt6.QtCore import pyqtSignal, pyqtSlot
from PyQt6.QtWidgets import QAction

# New (PySide6)
from PySide6.QtWidgets import QWidget, QVBoxLayout
from PySide6.QtCore import Signal, Slot
from PySide6.QtGui import QAction  # Note: moved to QtGui
```

**Signal/Slot Changes:**

```python
# Old (PyQt6)
class MyWidget(QWidget):
    data_changed = pyqtSignal(str)

    @pyqtSlot()
    def handle_click(self):
        pass

# New (PySide6)
class MyWidget(QWidget):
    data_changed = Signal(str)

    @Slot()
    def handle_click(self):
        pass
```

### Testing Your Changes

```bash
# Run migration verification
python scripts/verify_pyside6_migration.py

# Run test suite
pytest tests/

# Check code quality
pre-commit run --all-files
```

## For Distributors/Packagers

### License Changes

**Old License:** MIT  
**New License:** Apache 2.0

**Third-Party Dependencies:**

- PySide6: LGPL v3 (dynamically linked)
- Other dependencies: Various (see THIRD_PARTY_LICENSES.md)

### Packaging Requirements

1. **Include License Files:**

   - `LICENSE` (Apache 2.0)
   - `THIRD_PARTY_LICENSES.md`

2. **PySide6 Compliance:**

   - Include PySide6 plugins: `platforms`, `styles`, `imageformats`
   - Include Qt translations for i18n support
   - Ensure dynamic linking (default behavior)

3. **Build Configuration:**
   ```bash
   # PyInstaller example
   pyinstaller --additional-hooks-dir=hooks \
               --collect-all PySide6 \
               --collect-data PySide6 \
               main.py
   ```

### Platform-Specific Notes

**macOS:**

- Code signing may need updates for PySide6 libraries
- Notarization process remains the same

**Linux:**

- Update package dependencies from PyQt6 to PySide6
- Ensure Qt platform plugins are available

**Windows:**

- Include Visual C++ redistributables if needed
- Update installer scripts for PySide6

## Troubleshooting

### Common Issues

**Import Errors:**

```bash
ImportError: No module named 'PyQt6'
```

**Solution:** Update imports to use PySide6

**Signal/Slot Errors:**

```bash
AttributeError: 'Signal' object has no attribute 'pyqtSignal'
```

**Solution:** Update signal definitions to use PySide6 syntax

**QAction Import Errors:**

```bash
ImportError: cannot import name 'QAction' from 'PySide6.QtWidgets'
```

**Solution:** Import QAction from `PySide6.QtGui` instead

### Getting Help

1. **Check Migration Verification:**

   ```bash
   python scripts/verify_pyside6_migration.py
   ```

2. **Review Documentation:**

   - `docs/PYSIDE6_MIGRATION_GUIDE.md`
   - `docs/DEVELOPER_GUIDE.md`

3. **Report Issues:**
   - GitHub Issues with `migration` tag
   - Include error messages and system info

## Rollback Procedure

If you encounter critical issues:

1. **Backup Current State:**

   ```bash
   git stash  # Save any local changes
   ```

2. **Rollback to Previous Version:**

   ```bash
   git checkout pre-pyside6-migration
   pip install PyQt6>=6.6.0
   pip uninstall PySide6
   ```

3. **Verify Rollback:**
   ```bash
   python main.py  # Test application
   ```

**Estimated Rollback Time:** 30 minutes

## Benefits of Migration

### Technical Benefits

- ✅ Official Qt Company support
- ✅ Better long-term maintenance
- ✅ Improved license compatibility
- ✅ Enhanced development ecosystem

### Business Benefits

- ✅ Unrestricted commercial use
- ✅ No licensing fees
- ✅ Enterprise-friendly Apache 2.0 license
- ✅ Clear patent protection

### Community Benefits

- ✅ Wider contributor base
- ✅ Better integration with Qt ecosystem
- ✅ Simplified distribution

## Timeline

- **v1.1.0 Release:** October 26, 2025
- **Migration Period:** 1-2 weeks for community feedback
- **Stabilization:** v1.1.1+ for any migration-related fixes
- **Future:** v1.2.0+ will leverage PySide6-specific features

---

For detailed technical information, see:

- [Release Notes](RELEASE_NOTES_v1.1.0.md)
- [Migration Guide](docs/PYSIDE6_MIGRATION_GUIDE.md)
- [Changelog](docs/CHANGELOG.md)
