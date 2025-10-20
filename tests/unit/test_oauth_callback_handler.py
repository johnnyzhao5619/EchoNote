import importlib.util
import sys
import threading
import types
from http.client import HTTPConnection
from http.server import HTTPServer
from pathlib import Path


if "PyQt6" not in sys.modules:
    qt_module = types.ModuleType("PyQt6")
    qt_core = types.ModuleType("PyQt6.QtCore")
    qt_widgets = types.ModuleType("PyQt6.QtWidgets")

    class _Qt:  # pragma: no cover - test stub
        class AlignmentFlag:  # pragma: no cover - test stub
            AlignCenter = 0

    class _Signal:  # pragma: no cover - test stub
        def __init__(self, *_, **__):
            self._slots = []

        def connect(self, slot):
            self._slots.append(slot)

        def emit(self, *args, **kwargs):
            for slot in list(self._slots):
                slot(*args, **kwargs)

    def _pyqt_signal(*_, **__):  # pragma: no cover - test stub
        return _Signal()

    class _QTimer:  # pragma: no cover - test stub
        @staticmethod
        def singleShot(*args, **kwargs):
            if len(args) >= 2 and callable(args[1]):
                args[1]()

    class _QThread:  # pragma: no cover - test stub
        pass

    qt_core.Qt = _Qt
    qt_core.pyqtSignal = _pyqt_signal
    qt_core.QTimer = _QTimer
    qt_core.QThread = _QThread

    class _Widget:  # pragma: no cover - test stub
        def __init__(self, *_, **__):
            pass

        def setAlignment(self, *_, **__):
            pass

        def setStyleSheet(self, *_, **__):
            pass

        def setText(self, *_, **__):
            pass

        def setHtml(self, *_, **__):
            pass

        def setVisible(self, *_, **__):
            pass

        def setRange(self, *_, **__):
            pass

        def setReadOnly(self, *_, **__):
            pass

        def setMaximumHeight(self, *_, **__):
            pass

        def clicked(self, *_, **__):
            return self

        def connect(self, *_, **__):
            pass

        def setObjectName(self, *_, **__):
            pass

        def addWidget(self, *_, **__):
            pass

        def addLayout(self, *_, **__):
            pass

        def addStretch(self, *_, **__):
            pass

    class _QDialog(_Widget):  # pragma: no cover - test stub
        def setWindowTitle(self, *_, **__):
            pass

        def setMinimumWidth(self, *_, **__):
            pass

        def setModal(self, *_, **__):
            pass

        def reject(self):
            pass

        def accept(self):
            pass

        def closeEvent(self, *_):
            pass

    class _QHBoxLayout(_Widget):  # pragma: no cover - test stub
        pass

    class _QVBoxLayout(_QHBoxLayout):  # pragma: no cover - test stub
        pass

    class _QLabel(_Widget):  # pragma: no cover - test stub
        pass

    class _QPushButton(_Widget):  # pragma: no cover - test stub
        def setEnabled(self, *_, **__):
            pass

    class _QProgressBar(_Widget):  # pragma: no cover - test stub
        pass

    class _QTextEdit(_Widget):  # pragma: no cover - test stub
        pass

    class _QMessageBox:  # pragma: no cover - test stub
        @staticmethod
        def critical(*_, **__):
            pass

    qt_widgets.QDialog = _QDialog
    qt_widgets.QHBoxLayout = _QHBoxLayout
    qt_widgets.QVBoxLayout = _QVBoxLayout
    qt_widgets.QLabel = _QLabel
    qt_widgets.QPushButton = _QPushButton
    qt_widgets.QProgressBar = _QProgressBar
    qt_widgets.QTextEdit = _QTextEdit
    qt_widgets.QMessageBox = _QMessageBox

    qt_module.QtCore = qt_core
    qt_module.QtWidgets = qt_widgets

    sys.modules["PyQt6"] = qt_module
    sys.modules["PyQt6.QtCore"] = qt_core
    sys.modules["PyQt6.QtWidgets"] = qt_widgets


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


OAUTH_DIALOG_PATH = PROJECT_ROOT / "ui" / "calendar_hub" / "oauth_dialog.py"
spec = importlib.util.spec_from_file_location("ui.calendar_hub.oauth_dialog", OAUTH_DIALOG_PATH)
oauth_dialog = importlib.util.module_from_spec(spec)
assert spec and spec.loader  # safety for type checkers
spec.loader.exec_module(oauth_dialog)


OAuthCallbackHandler = oauth_dialog.OAuthCallbackHandler


def test_oauth_callback_handler_error_response():
    received = {}

    def _callback(code, error):
        received["code"] = code
        received["error"] = error

    server = HTTPServer(("localhost", 0), OAuthCallbackHandler)
    OAuthCallbackHandler.callback_received = staticmethod(_callback)

    server_thread = threading.Thread(target=server.handle_request, daemon=True)
    server_thread.start()

    host, port = server.server_address
    conn = HTTPConnection(host, port)

    try:
        conn.request("GET", "/?error=access_denied")
        response = conn.getresponse()
        body = response.read().decode("utf-8")
    finally:
        conn.close()
        server.server_close()
        server_thread.join(timeout=1)
        OAuthCallbackHandler.callback_received = None

    assert response.status == 400
    assert "Authorization Failed" in body
    assert "access_denied" in body
    assert received == {"code": None, "error": "access_denied"}
