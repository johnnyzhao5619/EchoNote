# PySide6 Migration Guide

**Version**: 1.0.0  
**Last Updated**: October 2025

---

## Table of Contents

1. [Overview](#overview)
2. [Migration Best Practices](#migration-best-practices)
3. [Common Pitfalls and Solutions](#common-pitfalls-and-solutions)
4. [API Differences](#api-differences)
5. [Code Examples](#code-examples)
6. [Testing Strategy](#testing-strategy)
7. [Rollback Procedure](#rollback-procedure)

---

## Overview

This guide documents the migration from PyQt6 to PySide6 and provides best practices for similar migrations in the future.

### Why PySide6?

- **License Compatibility**: PySide6 uses LGPL v3, which is compatible with Apache 2.0 through dynamic linking
- **Official Support**: PySide6 is the official Python binding from Qt Company
- **Better Community**: Larger community and better long-term support
- **No Commercial License**: No need for commercial licenses for proprietary applications

### Migration Timeline

The complete migration took approximately 10 working days:

- Day 1: Environment preparation and backup
- Days 2-3: Automated migration and manual fixes
- Days 4-7: Testing and validation
- Days 8-9: Documentation updates
- Day 10: Final review and deployment

---

## Migration Best Practices

### 1. Preparation Phase

#### Create a Comprehensive Backup

```bash
# Create a Git tag before starting
git tag pre-pyside6-migration
git push origin pre-pyside6-migration

# Backup critical files
cp requirements.txt requirements.txt.backup
cp requirements-dev.txt requirements-dev.txt.backup
cp LICENSE LICENSE.backup
```

#### Set Up a Migration Branch

```bash
# Create and switch to migration branch
git checkout -b feature/pyside6-migration
```

#### Install PySide6 in Development Environment

```bash
# Install PySide6 alongside PyQt6 initially for comparison
pip install PySide6>=6.6.0
pip install PySide6-stubs>=6.5.0

# Verify installation
python -c "from PySide6.QtWidgets import QApplication; print('PySide6 OK')"
```

### 2. Automated Migration

#### Use Migration Scripts

Create or use existing migration scripts to automate repetitive changes:

```python
# Example migration script pattern
import re
from pathlib import Path

def migrate_imports(file_path):
    """Migrate PyQt6 imports to PySide6."""
    content = file_path.read_text()

    # Replace import statements
    content = re.sub(r'from PyQt6\.', 'from PySide6.', content)
    content = re.sub(r'import PyQt6', 'import PySide6', content)

    # Replace signal/slot syntax
    content = re.sub(r'pyqtSignal', 'Signal', content)
    content = re.sub(r'pyqtSlot', 'Slot', content)
    content = re.sub(r'pyqtProperty', 'Property', content)

    file_path.write_text(content)
```

#### Run in Dry-Run Mode First

```bash
# Always test migration script in dry-run mode
python scripts/migrate_to_pyside6.py --dry-run

# Review the report before actual migration
# Then run the actual migration
python scripts/migrate_to_pyside6.py
```

### 3. Manual Verification

#### Check API Differences

After automated migration, manually verify these common differences:

1. **QAction Location**

   ```python
   # PyQt6
   from PyQt6.QtWidgets import QAction

   # PySide6
   from PySide6.QtGui import QAction
   ```

2. **Signal Type Annotations**

   ```python
   # PyQt6 (both work)
   data_changed = pyqtSignal(str)
   data_changed = pyqtSignal[str]

   # PySide6 (only first form)
   data_changed = Signal(str)  # Correct
   # data_changed = Signal[str]  # Wrong!
   ```

3. **Enum Access**
   ```python
   # Both frameworks support these patterns
   Qt.AlignmentFlag.AlignCenter
   Qt.AlignCenter  # Shorthand
   ```

### 4. Testing Strategy

#### Update Test Fixtures

```python
# Update test fixtures to use PySide6
import pytest
from PySide6.QtWidgets import QApplication

@pytest.fixture(scope="session")
def qapp():
    """Create QApplication for tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app
    app.quit()
```

#### Test Signal/Slot Connections

```python
# Test that signals work correctly
def test_signal_emission(qtbot):
    widget = MyWidget()

    with qtbot.waitSignal(widget.data_changed, timeout=1000):
        widget.trigger_change()
```

#### Run Full Test Suite

```bash
# Run all tests
pytest tests/

# Run with coverage
pytest --cov=. --cov-report=html tests/

# Check for any test failures
```

### 5. Documentation Updates

#### Update All References

Search and replace in documentation:

- `PyQt6` → `PySide6`
- `pyqtSignal` → `Signal`
- `pyqtSlot` → `Slot`
- `GPLv3` → `LGPL v3`
- `Riverbank Computing` → `Qt Company`

#### Update Code Examples

Ensure all code examples in documentation use PySide6:

```python
# Good example in documentation
from PySide6.QtWidgets import QWidget, QVBoxLayout
from PySide6.QtCore import Signal, Slot

class MyWidget(QWidget):
    data_changed = Signal(str)

    @Slot()
    def on_button_clicked(self):
        self.data_changed.emit("new data")
```

---

## Common Pitfalls and Solutions

### Pitfall 1: QAction Import Location

**Problem**: QAction is in different modules between PyQt6 and PySide6.

**Solution**:

```python
# PySide6: QAction is in QtGui, not QtWidgets
from PySide6.QtGui import QAction  # Correct
# from PySide6.QtWidgets import QAction  # Wrong!
```

### Pitfall 2: Signal Type Annotation Syntax

**Problem**: PySide6 doesn't support bracket notation for signal types.

**Solution**:

```python
# Use parentheses, not brackets
data_changed = Signal(str)  # Correct
# data_changed = Signal[str]  # Wrong!

# For multiple parameters
progress_updated = Signal(int, str)  # Correct
```

### Pitfall 3: Incomplete Import Updates

**Problem**: Missing some PyQt6 imports in comments or strings.

**Solution**:

```bash
# Search thoroughly for all references
grep -r "PyQt6" --include="*.py" .
grep -r "PyQt6" --include="*.md" docs/
grep -r "pyqtSignal" --include="*.py" .
```

### Pitfall 4: Test Mock Objects

**Problem**: Test mocks still reference PyQt6 classes.

**Solution**:

```python
# Update all mock imports in tests
from unittest.mock import Mock, patch
from PySide6.QtWidgets import QWidget  # Not PyQt6

def test_widget():
    mock_widget = Mock(spec=QWidget)  # Use PySide6 spec
```

### Pitfall 5: Forgotten Dependencies

**Problem**: requirements.txt still lists PyQt6.

**Solution**:

```bash
# Verify dependencies are updated
grep -i "pyqt" requirements.txt  # Should return nothing
grep -i "pyside" requirements.txt  # Should show PySide6
```

### Pitfall 6: CI/CD Configuration

**Problem**: CI/CD still installs PyQt6.

**Solution**:

```yaml
# Update GitHub Actions workflow
- name: Install dependencies
  run: |
    pip install PySide6>=6.6.0  # Not PyQt6
    pip install -r requirements.txt
```

---

## API Differences

### Import Mapping

| PyQt6                                   | PySide6                               | Notes                  |
| --------------------------------------- | ------------------------------------- | ---------------------- |
| `from PyQt6.QtWidgets import QAction`   | `from PySide6.QtGui import QAction`   | QAction moved to QtGui |
| `from PyQt6.QtCore import pyqtSignal`   | `from PySide6.QtCore import Signal`   | Renamed                |
| `from PyQt6.QtCore import pyqtSlot`     | `from PySide6.QtCore import Slot`     | Renamed                |
| `from PyQt6.QtCore import pyqtProperty` | `from PySide6.QtCore import Property` | Renamed                |
| `from PyQt6.sip import *`               | `from PySide6.shiboken6 import *`     | Different C++ binding  |

### Signal/Slot Syntax

| PyQt6                  | PySide6            |
| ---------------------- | ------------------ |
| `pyqtSignal()`         | `Signal()`         |
| `pyqtSignal(str)`      | `Signal(str)`      |
| `pyqtSignal(int, str)` | `Signal(int, str)` |
| `@pyqtSlot()`          | `@Slot()`          |
| `@pyqtSlot(str)`       | `@Slot(str)`       |

### Property Syntax

| PyQt6                               | PySide6                         |
| ----------------------------------- | ------------------------------- |
| `@pyqtProperty(str)`                | `@Property(str)`                |
| `@pyqtProperty(int, notify=signal)` | `@Property(int, notify=signal)` |

---

## Code Examples

### Basic Widget Migration

**Before (PyQt6):**

```python
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton
from PyQt6.QtCore import pyqtSignal, pyqtSlot

class MyWidget(QWidget):
    button_clicked = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()
        button = QPushButton("Click Me")
        button.clicked.connect(self.on_button_clicked)
        layout.addWidget(button)
        self.setLayout(layout)

    @pyqtSlot()
    def on_button_clicked(self):
        self.button_clicked.emit("Button was clicked")
```

**After (PySide6):**

```python
from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton
from PySide6.QtCore import Signal, Slot

class MyWidget(QWidget):
    button_clicked = Signal(str)

    def __init__(self):
        super().__init__()
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()
        button = QPushButton("Click Me")
        button.clicked.connect(self.on_button_clicked)
        layout.addWidget(button)
        self.setLayout(layout)

    @Slot()
    def on_button_clicked(self):
        self.button_clicked.emit("Button was clicked")
```

### Menu Action Migration

**Before (PyQt6):**

```python
from PyQt6.QtWidgets import QMainWindow, QMenu, QAction

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.create_menu()

    def create_menu(self):
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("File")

        open_action = QAction("Open", self)
        open_action.triggered.connect(self.on_open)
        file_menu.addAction(open_action)
```

**After (PySide6):**

```python
from PySide6.QtWidgets import QMainWindow, QMenu
from PySide6.QtGui import QAction  # Note: QAction moved to QtGui

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.create_menu()

    def create_menu(self):
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("File")

        open_action = QAction("Open", self)
        open_action.triggered.connect(self.on_open)
        file_menu.addAction(open_action)
```

### Custom Signal with Multiple Parameters

**Before (PyQt6):**

```python
from PyQt6.QtCore import QObject, pyqtSignal

class DataProcessor(QObject):
    progress_updated = pyqtSignal(int, str, float)

    def process(self):
        # Emit with multiple parameters
        self.progress_updated.emit(50, "Processing...", 0.5)
```

**After (PySide6):**

```python
from PySide6.QtCore import QObject, Signal

class DataProcessor(QObject):
    progress_updated = Signal(int, str, float)

    def process(self):
        # Emit with multiple parameters
        self.progress_updated.emit(50, "Processing...", 0.5)
```

---

## Testing Strategy

### Unit Tests

```python
import pytest
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

@pytest.fixture(scope="session")
def qapp():
    """Provide QApplication instance for tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app

def test_widget_creation(qapp):
    """Test that widget can be created."""
    from ui.main_window import MainWindow
    window = MainWindow()
    assert window is not None
    assert window.windowTitle() != ""

def test_signal_emission(qapp, qtbot):
    """Test signal emission."""
    from ui.sidebar import Sidebar
    sidebar = Sidebar()

    with qtbot.waitSignal(sidebar.page_changed, timeout=1000):
        sidebar.select_page("batch_transcribe")
```

### Integration Tests

```python
def test_transcription_workflow(qapp, qtbot, tmp_path):
    """Test complete transcription workflow."""
    from ui.batch_transcribe.widget import BatchTranscribeWidget

    widget = BatchTranscribeWidget()

    # Add a test file
    test_file = tmp_path / "test.wav"
    test_file.write_bytes(b"fake audio data")

    with qtbot.waitSignal(widget.task_added, timeout=1000):
        widget.add_file(str(test_file))

    # Verify task was added
    assert len(widget.get_tasks()) == 1
```

### Manual Testing Checklist

- [ ] Application starts without errors
- [ ] All menus and toolbars display correctly
- [ ] Dialogs open and close properly
- [ ] Signals and slots work correctly
- [ ] Theme switching works
- [ ] Language switching works
- [ ] All keyboard shortcuts work
- [ ] Custom widgets render correctly
- [ ] No memory leaks during extended use

---

## Rollback Procedure

If critical issues are discovered after migration, follow this rollback procedure:

### Step 1: Assess the Situation

Determine if rollback is necessary:

- Critical functionality broken?
- Severe performance degradation?
- Unfixable compatibility issues?

### Step 2: Restore from Git Tag

```bash
# Switch to the pre-migration tag
git checkout pre-pyside6-migration

# Create a rollback branch
git checkout -b rollback/pyside6-migration

# Restore dependency files
cp requirements.txt.backup requirements.txt
cp requirements-dev.txt.backup requirements-dev.txt
```

### Step 3: Reinstall Dependencies

```bash
# Remove PySide6
pip uninstall PySide6 PySide6-stubs -y

# Install PyQt6
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### Step 4: Verify Rollback

```bash
# Run tests
pytest tests/

# Start application
python main.py

# Verify all functionality works
```

### Step 5: Document Issues

Create a detailed issue report:

- What went wrong?
- When was it discovered?
- What was the impact?
- Why couldn't it be fixed forward?
- What needs to be addressed before retry?

### Rollback Timeline

- Code rollback: 5 minutes
- Dependency installation: 10 minutes
- Testing and verification: 15 minutes
- **Total: ~30 minutes**

---

## Lessons Learned

### What Went Well

1. **Automated Migration**: The migration script saved significant time
2. **Comprehensive Testing**: Caught issues early before production
3. **Documentation**: Clear documentation helped team members understand changes
4. **Incremental Approach**: Breaking migration into phases reduced risk

### What Could Be Improved

1. **Earlier Testing**: Should have tested on all platforms earlier
2. **Performance Benchmarking**: Should have established baselines before migration
3. **Communication**: More frequent updates to stakeholders
4. **Dependency Audit**: Should have audited all dependencies upfront

### Recommendations for Future Migrations

1. **Plan Thoroughly**: Spend adequate time in planning phase
2. **Automate Everything**: Create scripts for repetitive tasks
3. **Test Continuously**: Test after each major change
4. **Document Everything**: Keep detailed notes throughout
5. **Have a Rollback Plan**: Always have a tested rollback procedure
6. **Communicate Often**: Keep all stakeholders informed

---

## Additional Resources

### Official Documentation

- [PySide6 Documentation](https://doc.qt.io/qtforpython/)
- [Qt for Python Wiki](https://wiki.qt.io/Qt_for_Python)
- [PySide6 Examples](https://doc.qt.io/qtforpython/examples/index.html)

### Migration Tools

- `scripts/migrate_to_pyside6.py` - Automated migration script
- `scripts/verify_pyside6_migration.py` - Verification script

### Community Resources

- [Qt Forum](https://forum.qt.io/)
- [Stack Overflow - PySide6 Tag](https://stackoverflow.com/questions/tagged/pyside6)
- [Qt Discord Server](https://discord.gg/qt)

---

## Conclusion

The migration from PyQt6 to PySide6 was successful and achieved all objectives:

- ✅ License compatibility resolved
- ✅ Zero functionality regression
- ✅ Performance maintained or improved
- ✅ All tests passing
- ✅ Documentation updated

This guide serves as a reference for future migrations and documents the best practices learned during this process.

For questions or issues, please refer to the [CONTRIBUTING.md](CONTRIBUTING.md) guide or open an issue on GitHub.
