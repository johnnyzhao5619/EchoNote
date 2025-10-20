import pytest

PyQt6 = pytest.importorskip("PyQt6")
from PyQt6.QtWidgets import QApplication

from ui.common.splash_screen import SplashScreen


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


def test_splash_screen_formats_version_with_prefix(qapp):
    splash = SplashScreen(version="1.2.3")
    try:
        assert splash.version == "v1.2.3"
    finally:
        splash.deleteLater()
        qapp.processEvents()


def test_splash_screen_keeps_existing_prefix(qapp):
    splash = SplashScreen(version="v2.0.0")
    try:
        assert splash.version == "v2.0.0"
    finally:
        splash.deleteLater()
        qapp.processEvents()
