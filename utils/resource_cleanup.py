"""资源清理辅助函数。"""

from __future__ import annotations

import asyncio
import inspect
import logging
from typing import Any


def close_lazy_loaded_engine(name: str, loader: Any, logger: logging.Logger) -> None:
    """关闭惰性加载的引擎实例。"""
    if not loader or not getattr(loader, 'is_initialized', lambda: False)():
        return

    try:
        engine = loader.get()
    except Exception:  # noqa: BLE001
        logger.exception("Failed to retrieve %s during cleanup", name)
        return

    if engine is None:
        logger.debug(
            "%s was initialized but returned no instance; skipping cleanup",
            name,
        )
        return

    attempted = False

    for method_name in ('close', 'aclose'):
        method = getattr(engine, method_name, None)
        if not callable(method):
            continue

        try:
            attempted = True
            logger.debug("Closing %s via %s", name, method_name)

            if inspect.iscoroutinefunction(method):
                asyncio.run(method())
            else:
                result = method()
                if inspect.isawaitable(result):
                    asyncio.run(result)

            logger.info("%s resources released", name)
            break
        except Exception:  # noqa: BLE001
            logger.exception("Failed to close %s using %s", name, method_name)
            continue

    if not attempted:
        logger.debug("%s does not provide a close/aclose method", name)
