# SPDX-License-Identifier: Apache-2.0
#
# Copyright (c) 2024-2025 EchoNote Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
Centralized PySide6 imports for the UI layer.

This module provides a single location for all PySide6 imports used throughout
the UI layer, making it easier to manage dependencies and ensure consistent
import patterns across the UI layer.
"""

# Core Qt classes
from PySide6.QtCore import (
    QDate,
    QDateTime,
    QEvent,
    QLocale,
    QObject,
    QPoint,
    QRect,
    QSettings,
    QSize,
    Qt,
    QThread,
    QTime,
    QTimer,
    Signal,
    Slot,
)

# GUI classes
from PySide6.QtGui import (
    QAction,
    QBrush,
    QClipboard,
    QCloseEvent,
    QColor,
    QFocusEvent,
    QFont,
    QHideEvent,
    QIcon,
    QKeyEvent,
    QKeySequence,
    QMouseEvent,
    QMoveEvent,
    QPainter,
    QPaintEvent,
    QPalette,
    QPen,
    QPixmap,
    QResizeEvent,
    QShortcut,
    QShowEvent,
    QTextCursor,
)

# Widget classes
from PySide6.QtWidgets import (  # Layout classes; Container widgets; Input widgets; Display widgets; Item widgets; Item views; Menu and toolbar; Spacers
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSlider,
    QSplitter,
    QStackedWidget,
    QTableWidget,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

# Re-export commonly used items for convenience
__all__ = [
    # Core
    "QApplication",
    "QWidget",
    "QMainWindow",
    "QDialog",
    "QObject",
    "Qt",
    "Signal",
    "Slot",
    "QLocale",
    "QTimer",
    "QThread",
    # Layouts
    "QVBoxLayout",
    "QHBoxLayout",
    "QGridLayout",
    "QFormLayout",
    # Common widgets
    "QLabel",
    "QPushButton",
    "QLineEdit",
    "QTextEdit",
    "QComboBox",
    "QCheckBox",
    "QRadioButton",
    "QSlider",
    "QProgressBar",
    "QListWidget",
    "QTreeWidget",
    "QTableWidget",
    # Containers
    "QFrame",
    "QGroupBox",
    "QScrollArea",
    "QSplitter",
    "QStackedWidget",
    "QTabWidget",
    # Dialogs
    "QMessageBox",
    "QFileDialog",
    "QInputDialog",
    # Events
    "QCloseEvent",
    "QKeyEvent",
    "QMouseEvent",
    "QPaintEvent",
    # Graphics and styling
    "QPixmap",
    "QIcon",
    "QColor",
    "QFont",
    "QPainter",
    "QBrush",
    "QPen",
    # Utility
    "QSettings",
    "QSize",
    "QPoint",
    "QRect",
    "QKeySequence",
]
