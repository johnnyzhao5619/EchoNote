import logging
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import importlib.util
import pytest

if "PyQt6" not in sys.modules:
    qt_module = ModuleType("PyQt6")
    qt_widgets = ModuleType("PyQt6.QtWidgets")
    qt_core = ModuleType("PyQt6.QtCore")

    class _Signal:
        def __init__(self, *_, **__):
            pass

        def connect(self, *_, **__):
            pass

        def emit(self, *_, **__):
            pass

    def _pyqt_signal(*_, **__):
        return _Signal()

    class _StubWidget:
        def __init__(self, *_, **__):
            pass

        def setObjectName(self, *_, **__):
            pass

        def setStyleSheet(self, *_, **__):
            pass

        def setContentsMargins(self, *_, **__):
            pass

        def setSpacing(self, *_, **__):
            pass

        def addWidget(self, *_, **__):
            pass

        def addStretch(self, *_, **__):
            pass

        def addSpacing(self, *_, **__):
            pass

        def setFixedWidth(self, *_, **__):
            pass

        def setFixedSize(self, *_, **__):
            pass

        def clicked(self, *_, **__):
            return _Signal()

        def setCheckable(self, *_, **__):
            pass

        def setChecked(self, *_, **__):
            pass

        def setText(self, *_, **__):
            pass

        def setToolTip(self, *_, **__):
            pass

        def layout(self):
            return None

    class _MessageBox:
        class StandardButton:
            Yes = 1
            No = 0

        @staticmethod
        def information(*_, **__):
            return None

        @staticmethod
        def critical(*_, **__):
            return None

        @staticmethod
        def question(*_, **__):
            return _MessageBox.StandardButton.No

    qt_widgets.QWidget = _StubWidget
    qt_widgets.QVBoxLayout = _StubWidget
    qt_widgets.QHBoxLayout = _StubWidget
    qt_widgets.QPushButton = _StubWidget
    qt_widgets.QLabel = _StubWidget
    qt_widgets.QStackedWidget = _StubWidget
    qt_widgets.QButtonGroup = _StubWidget
    qt_widgets.QFrame = _StubWidget
    qt_widgets.QDialog = _StubWidget
    qt_widgets.QMessageBox = _MessageBox

    qt_core.pyqtSignal = _pyqt_signal

    qt_module.QtWidgets = qt_widgets
    qt_module.QtCore = qt_core

    sys.modules["PyQt6"] = qt_module
    sys.modules["PyQt6.QtWidgets"] = qt_widgets
    sys.modules["PyQt6.QtCore"] = qt_core

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

WIDGET_PATH = PROJECT_ROOT / "ui" / "calendar_hub" / "widget.py"
spec = importlib.util.spec_from_file_location("ui.calendar_hub.widget", WIDGET_PATH)
widget_module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(widget_module)  # type: ignore[arg-type]

CalendarHubWidget = widget_module.CalendarHubWidget
I18nManager = widget_module.I18nQtManager  # type: ignore[attr-defined]


@pytest.fixture
def httpx_stub(monkeypatch):
    module = ModuleType("httpx")

    class DummyHTTPError(Exception):
        pass

    module.HTTPError = DummyHTTPError
    monkeypatch.setitem(sys.modules, "httpx", module)
    return module


@pytest.fixture
def adapter():
    return SimpleNamespace(access_token="token-123")


def _bind_method(instance, method_name):
    method = getattr(CalendarHubWidget, method_name)
    return method.__get__(instance, CalendarHubWidget)


def test_get_user_email_handles_unauthorized(monkeypatch, caplog, adapter, httpx_stub):
    class DummyResponse:
        status_code = 401

        @staticmethod
        def json():
            return {}

    class DummyClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, *args, **kwargs):
            return DummyResponse()

    httpx_stub.Client = DummyClient
    caplog.set_level(logging.WARNING, logger="echonote.ui.calendar_hub")

    result = CalendarHubWidget._get_user_email(object(), "google", adapter)

    assert result is None
    assert any(
        "request failed with status 401" in record.message
        for record in caplog.records
    )


def test_get_user_email_handles_network_error(monkeypatch, caplog, adapter, httpx_stub):
    class DummyClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, *args, **kwargs):
            raise httpx_stub.HTTPError("network down")

    httpx_stub.Client = DummyClient
    caplog.set_level(logging.WARNING, logger="echonote.ui.calendar_hub")

    result = CalendarHubWidget._get_user_email(object(), "google", adapter)

    assert result is None
    assert any(
        "HTTP error fetching google user email" in record.message
        for record in caplog.records
    )


def test_format_account_label_without_email_uses_provider_translation():
    dummy = SimpleNamespace()
    dummy.i18n = I18nManager(default_language="en_US")
    dummy._get_provider_display_name = _bind_method(
        dummy, "_get_provider_display_name"
    )

    label = CalendarHubWidget._format_account_label(dummy, "google", None)

    assert label == "Google account"
