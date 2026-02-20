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
"""模型下载器实现。"""

import logging
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from threading import Event, Lock
from typing import Dict, List, Optional, Tuple

import requests
from PySide6.QtCore import QObject, Signal

from .registry import ModelInfo

logger = logging.getLogger(__name__)


class DownloadCancelled(Exception):
    """表示下载过程被主动取消。"""


@dataclass
class _RemoteFile:
    path: str
    size: int


class ModelDownloader(QObject):
    """负责从 Hugging Face 下载模型文件。"""

    download_progress = Signal(str, int, float)
    download_completed = Signal(str)
    download_cancelled = Signal(str)
    download_failed = Signal(str, str)

    def __init__(self, models_dir: Path, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._models_dir = Path(models_dir)
        self._models_dir.mkdir(parents=True, exist_ok=True)
        self._active_flags: Dict[str, Event] = {}
        self._lock = Lock()

    def is_downloading(self, model_name: str) -> bool:
        """当前是否正在下载指定模型。"""

        with self._lock:
            return model_name in self._active_flags

    def has_active_downloads(self) -> bool:
        """当前是否存在任意模型下载任务。"""
        with self._lock:
            return bool(self._active_flags)

    async def download(self, model: ModelInfo) -> Path:
        """下载指定模型，返回本地路径。"""

        import asyncio

        with self._lock:
            if model.name in self._active_flags:
                raise RuntimeError(f"Model '{model.name}' is already downloading")
            cancel_event = Event()
            self._active_flags[model.name] = cancel_event

        try:
            self.download_progress.emit(model.name, 0, 0.0)
            target_path = await asyncio.to_thread(
                self._download_sync,
                model,
                cancel_event,
            )
            self.download_completed.emit(model.name)
            return target_path
        except DownloadCancelled:
            message = "Download cancelled by user"
            logger.info(f"{model.name}: {message}")
            self.download_cancelled.emit(model.name)
            raise
        except Exception as exc:  # pragma: no cover - 记录异常信息
            logger.error(f"Download failed for {model.name}: {exc}", exc_info=True)
            self.download_failed.emit(model.name, str(exc))
            raise
        finally:
            with self._lock:
                self._active_flags.pop(model.name, None)

    def cancel(self, model_name: str) -> None:
        """请求取消正在进行的下载。"""

        with self._lock:
            flag = self._active_flags.get(model_name)
        if flag:
            flag.set()

    # --- 内部实现 ---------------------------------------------------------

    def _download_sync(self, model: ModelInfo, cancel_event: Event) -> Path:
        files = self._fetch_remote_manifest(model)
        if not files:
            raise RuntimeError("No downloadable files found")

        # 计算总字节数，如果获取失败（即 total_bytes=0），使用模型元数据中的预计大小兜底
        total_bytes = sum(f.size for f in files)
        if total_bytes == 0:
            logger.info(
                f"Total bytes from manifest is 0, falling back to metadata size: {model.size_mb} MB"
            )
            total_bytes = model.size_mb * 1024 * 1024

        total_bytes = max(total_bytes, 1)  # 最终安全网
        downloaded_bytes = 0
        start_ts = time.monotonic()

        destination = self._models_dir / model.name
        tmp_destination = destination.with_suffix(".downloading")

        if tmp_destination.exists():
            shutil.rmtree(tmp_destination, ignore_errors=True)
        tmp_destination.mkdir(parents=True, exist_ok=True)

        try:
            for remote_file in files:
                self._download_single_file(
                    model,
                    remote_file,
                    tmp_destination,
                    cancel_event,
                    total_bytes,
                    downloaded_bytes,
                    start_ts,
                )
                downloaded_bytes += remote_file.size

            if cancel_event.is_set():
                raise DownloadCancelled()

            if destination.exists():
                shutil.rmtree(destination, ignore_errors=True)
            tmp_destination.rename(destination)

            final_size = self._calculate_size(destination)
            elapsed = max(time.monotonic() - start_ts, 0.001)
            final_speed = final_size / (1024 * 1024 * elapsed)
            self.download_progress.emit(model.name, 100, final_speed)
            return destination
        except DownloadCancelled:
            shutil.rmtree(tmp_destination, ignore_errors=True)
            raise
        except Exception:
            shutil.rmtree(tmp_destination, ignore_errors=True)
            raise

    def _fetch_remote_manifest(self, model: ModelInfo) -> Tuple[_RemoteFile, ...]:
        """从 Hugging Face API 获取文件清单。"""

        api_url = (
            f"https://huggingface.co/api/models/{model.repo_id}"
            f"?revision={model.revision}"
        )
        logger.info(f"Fetching manifest for {model.repo_id}@{model.revision}")
        response = requests.get(api_url, timeout=30)
        response.raise_for_status()
        payload = response.json()

        siblings = payload.get("siblings", [])
        files_list: List[_RemoteFile] = []

        for sibling in siblings:
            path = sibling.get("rfilename")
            if not path:
                continue

            size = sibling.get("size")
            # 处理 size 为 null 或 0 的情况
            if size is None or size == 0:
                logger.debug(f"Missing size for {path} in API, trying HEAD request...")
                try:
                    resolve_url = (
                        f"https://huggingface.co/{model.repo_id}/resolve/{model.revision}/{path}"
                    )
                    head_resp = requests.head(resolve_url, timeout=10, allow_redirects=True)
                    if head_resp.status_code == 200:
                        size = int(head_resp.headers.get("Content-Length", 0))
                except Exception as e:
                    logger.warning(f"Failed to get size for {path} via HEAD: {e}")

            files_list.append(_RemoteFile(path=path, size=int(size or 0)))

        files = tuple(files_list)

        # 若 manifest 中未提供大小信息，尝试读取 top-level 的 safetensors index
        if not files:
            logger.warning(f"Manifest for {model.repo_id} does not contain files")

        return files

    def _download_single_file(
        self,
        model: ModelInfo,
        remote_file: _RemoteFile,
        destination: Path,
        cancel_event: Event,
        total_bytes: int,
        downloaded_bytes: int,
        start_ts: float,
    ) -> None:
        """下载单个文件并持续更新进度。"""

        url = (
            f"https://huggingface.co/{model.repo_id}/resolve/{model.revision}/"
            f"{remote_file.path}"
        )
        target = destination / remote_file.path
        target.parent.mkdir(parents=True, exist_ok=True)

        logger.info(f"Downloading {remote_file.path} ({remote_file.size} bytes)")

        with requests.get(url, stream=True, timeout=60) as response:
            response.raise_for_status()

            with open(target, "wb") as fh:
                chunk_size = 4 * 1024 * 1024
                bytes_in_file = 0

                for chunk in response.iter_content(chunk_size=chunk_size):
                    if cancel_event.is_set():
                        raise DownloadCancelled()

                    if not chunk:
                        continue

                    fh.write(chunk)
                    bytes_in_file += len(chunk)
                    downloaded_total = downloaded_bytes + bytes_in_file

                    elapsed = max(time.monotonic() - start_ts, 0.001)
                    speed = downloaded_total / (1024 * 1024 * elapsed)
                    progress = int(downloaded_total * 100 / total_bytes)

                    self.download_progress.emit(
                        model.name,
                        min(progress, 100),
                        speed,
                    )

        # 若 manifest 未提供文件尺寸，则在完成后补齐实际大小
        if remote_file.size == 0:
            try:
                remote_file.size = target.stat().st_size
            except OSError:
                remote_file.size = 0

    def _calculate_size(self, path: Path) -> int:
        total = 0
        try:
            for item in path.rglob("*"):
                if item.is_file():
                    total += item.stat().st_size
        except OSError:
            logger.warning(f"Failed to calculate size for {path}")
        return total
