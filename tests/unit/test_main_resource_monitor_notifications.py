import logging
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tests.unit.test_transcription_manager_failure import _ensure_numpy_stub  # type: ignore

_ensure_numpy_stub()

from main import _create_resource_monitor_handlers


class StubTranscriptionManager:
    def __init__(self):
        self._running = True
        self._paused = False
        self.pause_calls = 0
        self.resume_calls = 0

    def pause_processing(self):
        self.pause_calls += 1
        self._paused = True

    def resume_processing(self):
        self.resume_calls += 1
        self._paused = False

    def is_paused(self):
        return self._paused


class StubI18n:
    def __init__(self):
        self.calls = []

    def t(self, key, **kwargs):
        self.calls.append((key, kwargs))
        if not kwargs:
            return key
        formatted = ",".join(f"{k}={v}" for k, v in sorted(kwargs.items()))
        return f"{key}[{formatted}]"


class StubNotificationManager:
    def __init__(self):
        self.warning_messages = []
        self.info_messages = []

    def send_warning(self, title, message):
        self.warning_messages.append((title, message))

    def send_info(self, title, message):
        self.info_messages.append((title, message))


@pytest.fixture()
def stub_notification_manager(monkeypatch):
    manager = StubNotificationManager()
    monkeypatch.setattr(
        "ui.common.notification.get_notification_manager",
        lambda: manager,
    )
    return manager


def test_resource_monitor_handlers_send_notifications(stub_notification_manager):
    transcription_manager = StubTranscriptionManager()
    i18n = StubI18n()
    logger = logging.getLogger("test_resource_monitor")

    on_low_memory, on_resources_recovered = _create_resource_monitor_handlers(
        transcription_manager=transcription_manager,
        i18n=i18n,
        logger=logger,
    )

    on_low_memory(256.3)

    assert transcription_manager.pause_calls == 1
    assert transcription_manager.is_paused() is True
    assert stub_notification_manager.warning_messages == [
        (
            "notification.low_memory.title",
            "notification.low_memory.message[memory=256MB]",
        )
    ]

    on_resources_recovered()

    assert transcription_manager.resume_calls == 1
    assert transcription_manager.is_paused() is False
    assert stub_notification_manager.info_messages == [
        (
            "notification.resources_recovered.title",
            "notification.resources_recovered.message",
        )
    ]
