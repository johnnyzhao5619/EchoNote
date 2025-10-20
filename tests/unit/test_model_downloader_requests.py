"""ModelDownloader 网络异常处理测试。"""

from __future__ import annotations

from typing import List, Tuple

import pytest

requests = pytest.importorskip(
    "requests", reason="ModelDownloader requires requests for HTTP downloads"
)

from core.models.downloader import ModelDownloader
from core.models.registry import ModelInfo


@pytest.mark.asyncio
async def test_model_downloader_emits_failure_on_network_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
    qtbot,
) -> None:
    """当网络不可用时应抛出异常并发出失败信号。"""

    downloader = ModelDownloader(tmp_path)
    model = ModelInfo(
        name="unit-test-model",
        full_name="Unit Test Model",
        description="用于测试的模型。",
        size_mb=1,
        speed="fast",
        accuracy="high",
        languages=("en",),
        repo_id="dummy/repo",
    )

    emitted: List[Tuple[str, str]] = []
    downloader.download_failed.connect(emitted.append)

    def _offline_get(*args, **kwargs):
        raise requests.exceptions.ConnectionError("network unreachable")

    monkeypatch.setattr("core.models.downloader.requests.get", _offline_get)

    with pytest.raises(requests.exceptions.ConnectionError):
        await downloader.download(model)

    assert emitted, "下载失败信号应当被触发"
    name, message = emitted[0]
    assert name == model.name
    assert "network" in message.lower()
    assert not downloader.is_downloading(model.name)


@pytest.mark.asyncio
async def test_model_downloader_imports_requests_module(tmp_path, qtbot) -> None:
    """确认 requests 可用，防止依赖缺失导致下载器失效。"""

    downloader = ModelDownloader(tmp_path)
    assert downloader  # 避免未使用变量的静态检查告警

    # 直接访问 requests 异常类型确保依赖可用
    assert requests.exceptions.RequestException is not None

