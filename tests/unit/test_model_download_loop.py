"""run_model_download 事件循环资源管理测试。"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from utils.model_download import run_model_download


class _FakeLoop:
    def __init__(self, *, raise_on_run: bool = False):
        self.raise_on_run = raise_on_run
        self.closed = False
        self.stopped = False
        self.run_args = None

    def run_until_complete(self, coro):
        self.run_args = coro
        if self.raise_on_run:
            raise RuntimeError("boom")
        return "ok"

    def stop(self):
        self.stopped = True

    def close(self):
        self.closed = True


class _RecorderLogger:
    def __init__(self, loop: _FakeLoop):
        self.loop = loop
        self.messages = []

    def exception(self, message: str):
        # 记录日志前应当先停止循环
        assert self.loop.stopped is True
        self.messages.append(message)


class _DummyManager:
    def download_model(self, model_name: str):
        return f"download:{model_name}"


def test_run_model_download_stops_and_closes_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    """异常时应在记录日志前停止并关闭事件循环。"""

    loop = _FakeLoop(raise_on_run=True)
    monkeypatch.setattr(
        "utils.model_download.asyncio.new_event_loop",
        lambda: loop,
    )
    monkeypatch.setattr(
        "utils.model_download.asyncio.set_event_loop",
        lambda _loop: None,
    )

    logger = _RecorderLogger(loop)
    errors = []

    def _on_error(exc: Exception) -> None:
        errors.append(str(exc))

    success = run_model_download(
        _DummyManager(),
        "unit-test",
        logger=logger,
        on_error=_on_error,
        error_message="thread download failed",
    )

    assert success is False
    assert errors == ["boom"], "应将异常传递给 on_error 回调"
    assert loop.closed is True, "异常后必须关闭事件循环"
    assert loop.stopped is True, "记录日志前必须停止事件循环"
    assert logger.messages == ["thread download failed"]


def test_run_model_download_success_closes_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    """成功完成时也必须关闭事件循环并执行成功回调。"""

    loop = _FakeLoop(raise_on_run=False)
    monkeypatch.setattr(
        "utils.model_download.asyncio.new_event_loop",
        lambda: loop,
    )
    monkeypatch.setattr(
        "utils.model_download.asyncio.set_event_loop",
        lambda _loop: None,
    )

    success_called: list[bool] = []

    def _on_success() -> None:
        success_called.append(True)

    success = run_model_download(
        _DummyManager(),
        "unit-test",
        logger=_RecorderLogger(loop),
        on_success=_on_success,
        error_message="thread download failed",
    )

    assert success is True
    assert success_called == [True]
    assert loop.closed is True, "成功后同样需要关闭事件循环"
    assert loop.stopped is False, "成功路径不应调用 stop"
