import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

NOTIFICATION_MODULE_PATH = PROJECT_ROOT / "ui" / "common" / "notification.py"
spec = importlib.util.spec_from_file_location(
    "test_notification_module", NOTIFICATION_MODULE_PATH
)
notification_module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(notification_module)

NotificationManager = notification_module.NotificationManager


@pytest.mark.parametrize(
    "notification_type, expected_urgency",
    [
        ("info", "normal"),
        ("error", "critical"),
    ],
)
def test_linux_notification_arguments(monkeypatch, notification_type, expected_urgency):
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(subprocess, "run", fake_run)

    manager = NotificationManager.__new__(NotificationManager)
    manager.system = "Linux"
    manager.linux_available = True

    manager._send_linux_notification("Title", "Message", notification_type, 3)

    assert captured["command"][0] == "notify-send"
    assert captured["command"][1] == f"--urgency={expected_urgency}"
    assert captured["command"][2] == "--expire-time=3000"
    assert captured["command"][3:] == ["Title", "Message"]
    assert captured["kwargs"] == {"capture_output": True, "timeout": 5, "check": True}
