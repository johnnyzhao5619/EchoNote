import sys
from types import ModuleType, SimpleNamespace

import pytest


def _ensure_pyqt_stub():
    if "PyQt6" in sys.modules:
        return

    pyqt6_module = ModuleType("PyQt6")
    qtcore_module = ModuleType("PyQt6.QtCore")
    qtwidgets_module = ModuleType("PyQt6.QtWidgets")

    class _Signal:
        def __init__(self):
            self._callbacks = []

        def connect(self, callback):
            self._callbacks.append(callback)

        def emit(self, *args, **kwargs):
            for callback in list(self._callbacks):
                callback(*args, **kwargs)

    class _SignalDescriptor:
        def __set_name__(self, owner, name):
            self._storage_name = f"__qt_signal_{name}"

        def __get__(self, instance, owner):
            if instance is None:
                return self
            signal = getattr(instance, self._storage_name, None)
            if signal is None:
                signal = _Signal()
                setattr(instance, self._storage_name, signal)
            return signal

        def __set__(self, instance, value):  # noqa: D401
            raise AttributeError("Signal attributes are read-only")

    def _pyqt_signal(*args, **kwargs):  # noqa: D401, ARG002
        return _SignalDescriptor()

    class _QObject:
        def __init__(self, *args, **kwargs):  # noqa: D401, ARG002
            pass

    class _QTimer:
        def __init__(self, *args, **kwargs):  # noqa: D401, ARG002
            self._active = False
            self._interval = 0
            self.timeout = _Signal()

        def start(self, interval):  # noqa: D401
            self._interval = interval
            self._active = True

        def stop(self):  # noqa: D401
            self._active = False

        def isActive(self):  # noqa: D401
            return self._active

    class _QApplication:
        _instance = None

        def __init__(self, *args, **kwargs):  # noqa: D401, ARG002
            type(self)._instance = self

        @classmethod
        def instance(cls):  # noqa: D401
            return cls._instance

        def processEvents(self):  # noqa: D401
            return None

    qtcore_module.QObject = _QObject  # type: ignore[attr-defined]
    qtcore_module.QTimer = _QTimer  # type: ignore[attr-defined]
    qtcore_module.pyqtSignal = _pyqt_signal  # type: ignore[attr-defined]
    qtwidgets_module.QApplication = _QApplication  # type: ignore[attr-defined]

    pyqt6_module.QtCore = qtcore_module  # type: ignore[attr-defined]
    pyqt6_module.QtWidgets = qtwidgets_module  # type: ignore[attr-defined]

    sys.modules["PyQt6"] = pyqt6_module
    sys.modules["PyQt6.QtCore"] = qtcore_module
    sys.modules["PyQt6.QtWidgets"] = qtwidgets_module


def _ensure_psutil_stub():
    if "psutil" in sys.modules:
        return

    psutil_module = ModuleType("psutil")

    class _VirtualMemory:
        available = 1024 * 1024 * 1024
        total = 4 * 1024 * 1024 * 1024
        percent = 0.0

    def _virtual_memory():
        return _VirtualMemory()

    def _cpu_percent(interval=None):  # noqa: ARG001
        return 0.0

    psutil_module.virtual_memory = _virtual_memory  # type: ignore[attr-defined]
    psutil_module.cpu_percent = _cpu_percent  # type: ignore[attr-defined]
    psutil_module.cpu_count = lambda *args, **kwargs: 1  # type: ignore[attr-defined, E731]

    sys.modules["psutil"] = psutil_module


_ensure_pyqt_stub()
_ensure_psutil_stub()

from utils import resource_monitor as resource_monitor_module


class StubConfig:
    def __init__(self, low_memory_mb=256, high_cpu_percent=70):
        self._values = {
            "resource_monitor.low_memory_mb": low_memory_mb,
            "resource_monitor.high_cpu_percent": high_cpu_percent,
        }

    def get(self, key, default=None):
        return self._values.get(key, default)


@pytest.fixture()
def qt_app():
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_resource_monitor_thresholds_from_config(monkeypatch, qt_app):
    monkeypatch.setattr(
        resource_monitor_module.psutil,
        "virtual_memory",
        lambda: SimpleNamespace(
            available=1024 * 1024 * 1024,
            total=4 * 1024 * 1024 * 1024,
            percent=50.0,
        ),
    )
    monkeypatch.setattr(
        resource_monitor_module.psutil,
        "cpu_percent",
        lambda interval=None: 10.0,
    )

    monitor = resource_monitor_module.ResourceMonitor(
        config_manager=StubConfig(low_memory_mb=384, high_cpu_percent=65)
    )

    assert monitor.low_memory_threshold_mb == pytest.approx(384.0)
    assert monitor.high_cpu_threshold_percent == pytest.approx(65.0)


def test_resource_monitor_low_memory_warning(monkeypatch, qt_app):
    monkeypatch.setattr(
        resource_monitor_module.psutil,
        "virtual_memory",
        lambda: SimpleNamespace(
            available=200 * 1024 * 1024,
            total=8 * 1024 * 1024 * 1024,
            percent=80.0,
        ),
    )
    monkeypatch.setattr(
        resource_monitor_module.psutil,
        "cpu_percent",
        lambda interval=None: 30.0,
    )

    monitor = resource_monitor_module.ResourceMonitor(
        config_manager=StubConfig(low_memory_mb=256, high_cpu_percent=90)
    )

    captured = []
    monitor.low_memory_warning.connect(lambda value: captured.append(value))

    monitor._check_resources()
    qt_app.processEvents()

    assert monitor.low_memory_threshold_mb == pytest.approx(256.0)
    assert captured == [pytest.approx(200.0)]


def test_resource_monitor_high_cpu_warning(monkeypatch, qt_app):
    monkeypatch.setattr(
        resource_monitor_module.psutil,
        "virtual_memory",
        lambda: SimpleNamespace(
            available=1024 * 1024 * 1024,
            total=16 * 1024 * 1024 * 1024,
            percent=40.0,
        ),
    )
    monkeypatch.setattr(
        resource_monitor_module.psutil,
        "cpu_percent",
        lambda interval=None: 82.0,
    )

    monitor = resource_monitor_module.ResourceMonitor(
        config_manager=StubConfig(low_memory_mb=256, high_cpu_percent=75)
    )

    captured = []
    monitor.high_cpu_warning.connect(lambda value: captured.append(value))

    monitor._check_resources()
    qt_app.processEvents()

    assert monitor.high_cpu_threshold_percent == pytest.approx(75.0)
    assert captured == [pytest.approx(82.0)]
