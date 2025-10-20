import sys

import pytest

PyQt6 = pytest.importorskip("PyQt6")  # noqa: F401 - imported for availability check
from PyQt6.QtWidgets import QApplication

from ui.common.splash_screen import SplashScreen


@pytest.fixture(scope="module")
def qt_app():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


def test_splash_screen_normalizes_version_prefix(qt_app):
    splash = SplashScreen(version="1.2.3")
    assert splash.version == "v1.2.3"
    splash.close()


def test_splash_screen_set_version_updates_display(qt_app):
    splash = SplashScreen(version="v0.9.0")
    splash.set_version("2.0.0")
    assert splash.version == "v2.0.0"
    splash.close()
