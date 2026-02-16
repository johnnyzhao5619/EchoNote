# SPDX-License-Identifier: Apache-2.0
#
# Copyright (c) 2024-2025 EchoNote Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Model download thread utilities."""

import asyncio
import logging
from typing import Callable, Optional

from core.models.downloader import DownloadCancelled


def run_model_download(
    model_manager,
    model_name: str,
    *,
    logger: logging.Logger,
    on_success: Optional[Callable[[], None]] = None,
    on_error: Optional[Callable[[Exception], None]] = None,
    error_message: Optional[str] = None,
) -> bool:
    """Execute model download task using independent event loop."""

    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        loop.run_until_complete(model_manager.download_model(model_name))
        if on_success:
            on_success()
        return True
    except DownloadCancelled:
        logger.info("Model download cancelled: %s", model_name)
        return False
    except Exception as exc:  # noqa: BLE001 - need to catch all exceptions for logging
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
