# SPDX-License-Identifier: Apache-2.0
"""
Pytest configuration for EchoNote PySide6 migration tests.
"""

import sys
import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="session")
def qapp():
    """Create QApplication instance for PySide6 testing."""
    if not QApplication.instance():
        app = QApplication(sys.argv)
    else:
        app = QApplication.instance()
    yield app
