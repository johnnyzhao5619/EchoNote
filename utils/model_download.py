"""模型下载线程工具。"""

from __future__ import annotations

import asyncio
import logging
from typing import Callable, Optional


def run_model_download(
    model_manager,
    model_name: str,
    *,
    logger: logging.Logger,
    on_success: Optional[Callable[[], None]] = None,
    on_error: Optional[Callable[[Exception], None]] = None,
    error_message: Optional[str] = None,
) -> bool:
    """使用独立事件循环执行模型下载任务。"""

    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        loop.run_until_complete(model_manager.download_model(model_name))
        if on_success:
            on_success()
        return True
    except Exception as exc:  # noqa: BLE001 - 需要捕获所有异常以记录日志
        try:
            loop.stop()
        except RuntimeError:
            pass

        if on_error:
            on_error(exc)

        log_message = error_message or f"Failed to download model {model_name}"
        logger.exception(log_message)
        return False
    finally:
        loop.close()
