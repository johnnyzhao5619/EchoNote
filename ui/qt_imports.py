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
Centralized PySide6 imports for UI components.

This module provides commonly used PySide6 classes to reduce import duplication
and ensure consistent import patterns across the UI layer.
"""

# Core Qt classes
from PySide6.QtCore import (
    QDate,
    QDateTime,
    QRect,
    QSize,
    Qt,
    QThread,
    QTime,
    QTimer,
    QUrl,
    Signal,
    Slot,
)

# GUI classes
from PySide6.QtGui import (
    QAction,
    QClipboard,
    QColor,
    QFont,
    QFontMetrics,
    QIcon,
    QPainter,
    QPen,
    QPixmap,
    QTextCharFormat,
    QTextCursor,
    QTextDocument,
)

# Multimedia classes
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer

# Widget classes
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplashScreen,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

# Common widget combinations for specific use cases
__all__ = [
    # Core
    "QDate",
    "QDateTime",
    "QRect",
    "QSize",
    "QThread",
    "QTime",
    "QTimer",
    "QUrl",
    "Qt",
    "Signal",
    "Slot",
    # GUI
    "QAction",
    "QClipboard",
    "QColor",
    "QFont",
    "QFontMetrics",
    "QIcon",
    "QPainter",
    "QPen",
    "QPixmap",
    "QTextCharFormat",
    "QTextCursor",
    "QTextDocument",
    # Widgets
    "QApplication",
    "QButtonGroup",
    "QCheckBox",
    "QComboBox",
    "QDialog",
    "QFileDialog",
    "QFrame",
    "QGridLayout",
    "QGroupBox",
    "QHBoxLayout",
    "QLabel",
    "QListWidget",
    "QListWidgetItem",
    "QMenu",
    "QMessageBox",
    "QProgressBar",
    "QPushButton",
    "QSplashScreen",
    "QStackedWidget",
    "QTextEdit",
    "QVBoxLayout",
    "QWidget",
    # Multimedia
    "QAudioOutput",
    "QMediaPlayer",
]
