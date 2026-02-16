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
"""模型管理器实现。"""

import logging
import threading
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set

import psutil
from PySide6.QtCore import QCoreApplication, QObject, QTimer, Signal

from config.app_config import ConfigManager, get_app_dir
from core.models.downloader import DownloadCancelled, ModelDownloader
from core.models.registry import ModelInfo, ModelRegistry
from data.database.connection import DatabaseConnection
from data.database.models import ModelUsageStats
from utils.gpu_detector import GPUDetector

logger = logging.getLogger(__name__)


class ModelManager(QObject):
    """管理可用模型及其生命周期。"""

    models_updated = Signal()
    model_validation_failed = Signal(str, str)

    def __init__(
        self,
        config: ConfigManager,
        database: DatabaseConnection,
        registry: Optional[ModelRegistry] = None,
        downloader: Optional[ModelDownloader] = None,
    ) -> None:
        super().__init__()
        self._config = config
        self._database = database
        self._registry = registry or ModelRegistry()
        self._models_dir = Path(
            self._config.get(
                "transcription.faster_whisper.model_dir",
                str(get_app_dir() / "models"),
            )
        ).expanduser()
        self._models_dir.mkdir(parents=True, exist_ok=True)

        self.downloader = downloader or ModelDownloader(self._models_dir, self)
        self.downloader.download_completed.connect(self._on_download_completed)
        self.downloader.download_failed.connect(self._on_download_failed)

        self._lock = threading.RLock()
        self._model_cache: Dict[str, ModelInfo] = {}
        self._model_order: List[str] = []
        self._invalid_models: Set[str] = set()
        self._dirty = True

        self._refresh_cache()

    # ------------------------------------------------------------------
    # 公共接口
    # ------------------------------------------------------------------

    def get_all_models(self) -> List[ModelInfo]:
        """获取所有可用模型的列表。

        Returns:
            所有模型信息的列表副本。
        """
        with self._lock:
            self._ensure_cache()
            return [replace(self._model_cache[name]) for name in self._model_order]

    def get_downloaded_models(self) -> List[ModelInfo]:
        """获取所有已下载模型的列表。

        Returns:
            已下载模型信息的列表。
        """
        return [m for m in self.get_all_models() if m.is_downloaded]

    def get_model(self, name: str) -> Optional[ModelInfo]:
        """根据名称获取模型信息。

        Args:
            name: 模型名称。

        Returns:
            模型信息副本，如果不存在则返回 None。
        """
        with self._lock:
            self._ensure_cache()
            model = self._model_cache.get(name)
            return replace(model) if model else None

    def is_model_downloaded(self, name: str) -> bool:
        """检查模型是否已下载。

        Args:
            name: 模型名称。

        Returns:
            如果模型已下载则返回 True，否则返回 False。
        """
        model = self.get_model(name)
        return bool(model and model.is_downloaded)

    def is_model_in_use(self, name: str) -> bool:
        """检查模型是否正在使用中（下载中或当前已配置为活动模型）。

        Args:
            name: 模型名称。

        Returns:
            如果模型正在下载或当前已配置为活动模型则返回 True，否则返回 False。
        """
        return self.downloader.is_downloading(name) or self._is_configured_active_model(name)

    def has_active_downloads(self) -> bool:
        """检查是否存在任意模型下载任务。"""
        return self.downloader.has_active_downloads()

    async def download_model(self, name: str) -> Path:
        """下载指定的模型。

        Args:
            name: 模型名称。

        Returns:
            下载后的模型路径。

        Raises:
            ValueError: 如果模型名称未知。
            DownloadCancelled: 如果下载被取消。
        """
        model = self.get_model(name)
        if not model:
            raise ValueError(f"Unknown model: {name}")
        if model.is_downloaded:
            logger.info(f"Model {name} already downloaded")
            return Path(model.local_path)

        logger.info(f"Downloading model: {name}")
        try:
            path = await self.downloader.download(model)
            return path
        except DownloadCancelled:
            logger.info(f"Model download cancelled: {name}")
            raise

    def cancel_download(self, name: str) -> None:
        """取消正在进行的模型下载。

        Args:
            name: 模型名称。
        """
        logger.info(f"Cancelling download for model: {name}")
        self.downloader.cancel(name)

    def delete_model(self, name: str) -> bool:
        """删除已下载的模型。

        Args:
            name: 模型名称。

        Returns:
            如果成功删除则返回 True，否则返回 False。

        Raises:
            RuntimeError: 如果模型正在被使用。
        """
        model = self.get_model(name)
        if not model or not model.is_downloaded:
            return False

        if self.is_model_in_use(name):
            raise RuntimeError("Model is in use")

        path = Path(model.local_path)
        try:
            if path.exists():
                logger.info(f"Removing model directory: {path}")
                import shutil

                shutil.rmtree(path)
                if path.exists():
                    raise RuntimeError(f"Model directory still exists after deletion: {path}")
        except Exception as exc:
            logger.error(f"Failed to delete model {name}: {exc}")
            raise

        with self._lock:
            self._invalid_models.discard(name)
        self._mark_dirty()
        self._refresh_cache()
        self.models_updated.emit()
        return True

    def mark_model_used(
        self,
        name: str,
        transcription_duration: float = 0.0,
    ) -> None:
        """标记模型已使用并更新使用统计。

        Args:
            name: 模型名称。
            transcription_duration: 转录持续时间（秒）。
        """
        try:
            ModelUsageStats.increment_usage(
                self._database,
                name,
                transcription_duration,
            )
        except Exception as exc:
            logger.error(f"Failed to update usage stats for {name}: {exc}")
        finally:
            self._mark_dirty()
            self._refresh_cache()
            self.models_updated.emit()

    def start_validation(self, deferred: bool = True) -> None:
        """启动模型验证过程，检查已下载模型的完整性。"""
        logger.info("Starting model validation")
        self._refresh_cache()
        app = QCoreApplication.instance()
        if not deferred or app is None:
            self._validate_models()
        else:
            QTimer.singleShot(0, self._validate_models)

    def recommend_model(self) -> str:
        """根据系统资源和使用历史推荐最佳模型。

        Returns:
            推荐的模型名称。
        """
        models = self.get_all_models()
        downloaded = [m for m in models if m.is_downloaded]
        if downloaded:
            downloaded.sort(
                key=lambda m: (
                    -m.usage_count,
                    self._accuracy_rank(m.accuracy),
                    m.size_mb,
                )
            )
            return downloaded[0].name

        context = self.get_recommendation_context()
        memory_gb = context["memory_gb"]
        has_gpu = context["has_gpu"]

        if has_gpu:
            if memory_gb >= 24 and self._registry.has("large-v3"):
                return "large-v3"
            if memory_gb >= 16 and self._registry.has("medium"):
                return "medium"
            if memory_gb >= 12 and self._registry.has("small"):
                return "small"
            if self._registry.has("base"):
                return "base"
        else:
            if memory_gb >= 16 and self._registry.has("small"):
                return "small"
            if memory_gb >= 8 and self._registry.has("base"):
                return "base"

        if self._registry.has("tiny"):
            return "tiny"

        return self._registry.default_model()

    def get_recommendation_context(self) -> Dict[str, float]:
        """获取用于模型推荐的系统上下文信息。

        Returns:
            包含系统资源信息的字典。
        """
        memory_gb = round(psutil.virtual_memory().total / (1024**3), 1)
        cpu_count = psutil.cpu_count(logical=False) or psutil.cpu_count()
        disk_usage = psutil.disk_usage(str(self._models_dir))
        free_disk_gb = round(disk_usage.free / (1024**3), 1)

        devices = GPUDetector.detect_available_devices()

        return {
            "memory_gb": memory_gb,
            "cpu_count": cpu_count or 0,
            "disk_free_gb": free_disk_gb,
            "has_gpu": bool(devices.get("cuda")),
            "has_coreml": bool(devices.get("coreml")),
        }

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _ensure_cache(self) -> None:
        if self._dirty:
            self._refresh_cache()

    def _refresh_cache(self) -> None:
        with self._lock:
            base_models = self._registry.list_models()
            usage_stats = {
                stat.model_name: stat for stat in ModelUsageStats.get_all(self._database)
            }

            self._model_cache.clear()
            self._model_order = []

            for model in base_models:
                model.ensure_local_state(self._models_dir)
                if model.name in self._invalid_models:
                    model.is_downloaded = False
                    model.local_path = None
                    model.download_date = None

                stats = usage_stats.get(model.name)
                if stats:
                    model.usage_count = stats.usage_count
                    model.last_used = self._parse_datetime(stats.last_used)
                else:
                    model.usage_count = 0
                    model.last_used = None

                self._model_cache[model.name] = model
                self._model_order.append(model.name)

            self._dirty = False

    def _mark_dirty(self) -> None:
        with self._lock:
            self._dirty = True

    def _is_configured_active_model(self, name: str) -> bool:
        default_engine = str(self._config.get("transcription.default_engine", "faster-whisper"))
        if default_engine.strip().lower() != "faster-whisper":
            return False
        configured_model = self._config.get("transcription.faster_whisper.model_size")
        return configured_model == name

    def _validate_models(self) -> None:
        logger.info("Validating downloaded models")
        updated = False
        for model in self.get_all_models():
            if not model.is_downloaded or not model.local_path:
                continue

            local_path = Path(model.local_path)
            missing = self._collect_missing_files(local_path, model)
            if missing:
                message = f"Missing files: {', '.join(missing)}"
                logger.warning(f"Model {model.name} validation failed: {message}")
                self.model_validation_failed.emit(model.name, message)

                with self._lock:
                    self._invalid_models.add(model.name)

                try:
                    if local_path.exists():
                        import shutil

                        shutil.rmtree(local_path)
                except Exception as exc:
                    logger.error("Failed to remove invalid model directory %s: %s", local_path, exc)

                with self._lock:
                    cached = self._model_cache.get(model.name)
                    if cached:
                        cached.is_downloaded = False
                        cached.local_path = None
                        cached.download_date = None
                        updated = True

        if updated:
            self.models_updated.emit()

    def _collect_missing_files(self, base_path: Path, model: ModelInfo) -> List[str]:
        missing: List[str] = []
        for required in model.required_files:
            if not (base_path / required).exists():
                missing.append(required)
        return missing

    @staticmethod
    def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            logger.warning(f"Invalid datetime format: {value}")
            return None

    @staticmethod
    def _accuracy_rank(value: str) -> int:
        order = {"low": 0, "medium": 1, "high": 2}
        return order.get(value, 0)

    def _on_download_completed(self, name: str) -> None:
        logger.info(f"Download completed: {name}")
        with self._lock:
            self._invalid_models.discard(name)
        self._mark_dirty()
        self._refresh_cache()
        self.models_updated.emit()

    def _on_download_failed(self, name: str, error: str) -> None:
        logger.error(f"Download failed for {name}: {error}")
        self._mark_dirty()
        self._refresh_cache()
