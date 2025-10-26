# SPDX-License-Identifier: Apache-2.0
"""
Integration tests for PySide6 migration verification.
"""

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer


def test_pyside6_qt_integration(qapp):
    """Test basic PySide6 Qt integration works."""
    # Test QTimer creation and basic functionality
    timer = QTimer()
    assert timer is not None
    assert hasattr(timer, "timeout")
    assert hasattr(timer, "start")
    assert hasattr(timer, "stop")


def test_pyside6_application_instance(qapp):
    """Test QApplication instance is properly created."""
    app = QApplication.instance()
    assert app is not None
    assert isinstance(app, QApplication)
