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

import asyncio
import logging
import threading
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set

import psutil
from core.qt_imports import QCoreApplication, QObject, QTimer, Signal

from config.app_config import ConfigManager, get_app_dir
from core.models.downloader import ModelDownloader
from core.models.registry import ModelInfo, ModelRegistry
from core.models.translation_registry import (
    TranslationModelInfo,
    TranslationModelRegistry,
)
from data.database.connection import DatabaseConnection
from data.database.models import ModelUsageStats, TranslationModelRecord
from utils.gpu_detector import GPUDetector
from utils.time_utils import current_iso_timestamp

logger = logging.getLogger(__name__)


class ModelManager(QObject):
    """管理可用模型及其生命周期。"""

    models_updated = Signal()
    model_validation_failed = Signal(str, str)
    translation_models_updated = Signal()

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

        # ---------- 翻译模型（独立目录和下载器，不与语音模型混用） ----------
        self._translation_registry = TranslationModelRegistry()
        self._translation_models_dir = Path(
            self._config.get(
                "translation.models_dir",
                str(Path.home() / ".echonote" / "translation_models"),
            )
        ).expanduser()
        self._translation_models_dir.mkdir(parents=True, exist_ok=True)
        # 独立的 ModelDownloader 实例：目录不同，信号不同，互不干扰
        self.translation_downloader = ModelDownloader(self._translation_models_dir, self)
        self.translation_downloader.download_completed.connect(
            self._on_translation_download_completed
        )
        self.translation_downloader.download_failed.connect(self._on_translation_download_failed)
        # 刷新翻译模型本地状态
        self._refresh_translation_states()

        self._lock = threading.RLock()
        self._model_cache: Dict[str, ModelInfo] = {}
        self._model_order: List[str] = []
        self._invalid_models: Set[str] = set()
        self._dirty = True

        self._refresh_cache()

        # 下载任务缓存（用于重入保护）
        self._active_downloads: Dict[str, asyncio.Task] = {}
        self._async_lock_instance: Optional[asyncio.Lock] = None

    @property
    def _async_lock(self) -> asyncio.Lock:
        """懒加载异步锁，确保在当前线程的事件循环中创建。"""
        if self._async_lock_instance is None:
            self._async_lock_instance = asyncio.Lock()
        return self._async_lock_instance

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
        """下载指定的 Whisper 模型。"""
        model = self.get_model(name)
        if not model:
            raise ValueError(f"Unknown model: {name}")

        return await self._execute_download(name, model, self.downloader)

    async def _execute_download(
        self,
        task_id: str,
        model_info,
        downloader: ModelDownloader,
        pre_download_cb: Optional[Callable[[], None]] = None,
        post_download_cb: Optional[Callable[[Path], None]] = None,
    ) -> Path:
        """通用的下载执行逻辑（含重入保护）。"""
        if model_info.is_downloaded:
            logger.info(f"Model {task_id} already downloaded")
            return Path(model_info.local_path)

        async with self._async_lock:
            if task_id in self._active_downloads:
                logger.info(f"Model {task_id} is already downloading, waiting...")
                return await self._active_downloads[task_id]

            if pre_download_cb:
                pre_download_cb()

            async def _do_download():
                try:
                    path = await downloader.download(model_info)
                    if post_download_cb:
                        post_download_cb(path)
                    return path
                finally:
                    self._active_downloads.pop(task_id, None)

            download_task = asyncio.create_task(_do_download())
            self._active_downloads[task_id] = download_task

        logger.info(f"Starting download for: {task_id}")
        return await download_task

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
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
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

    # ------------------------------------------------------------------
    # 翻译模型管理
    # ------------------------------------------------------------------

    def _refresh_translation_states(self) -> None:
        """刷新所有翻译模型的本地下载状态及使用统计。"""
        # 从数据库获取统计信息
        translation_stats = {
            rec.model_id: rec for rec in TranslationModelRecord.get_all(self._database)
        }

        for model in self._translation_registry.get_all():
            model.ensure_local_state(self._translation_models_dir)

            # 填充统计信息
            stats = translation_stats.get(model.model_id)
            if stats:
                model.use_count = stats.use_count
                model.last_used = self._parse_datetime(stats.last_used)
                model.download_date = self._parse_datetime(stats.downloaded_at)

            # 同步更新注册表内部对象
            registered = self._translation_registry._models.get(model.model_id)
            if registered:
                registered.local_path = model.local_path
                registered.is_downloaded = model.is_downloaded
                if stats:
                    registered.use_count = model.use_count
                    registered.last_used = model.last_used
                    registered.download_date = model.download_date

    def get_all_translation_models(self) -> List[TranslationModelInfo]:
        """返回所有翻译模型信息（含本地状态）。"""
        self._refresh_translation_states()
        return self._translation_registry.get_all()

    def get_translation_model(self, model_id: str) -> Optional[TranslationModelInfo]:
        """按 model_id 获取翻译模型信息。"""
        model = self._translation_registry.get_by_id(model_id)
        if model:
            model.ensure_local_state(self._translation_models_dir)
        return model

    def is_translation_model_downloaded(self, model_id: str) -> bool:
        """检查翻译模型是否已下载。"""
        model = self._translation_registry.get_by_id(model_id)
        if not model:
            return False
        model.ensure_local_state(self._translation_models_dir)
        return model.is_downloaded

    def get_translation_model_path(self, model_id: str) -> Optional[Path]:
        """获取已下载翻译模型的本地路径。"""
        model = self.get_translation_model(model_id)
        if model and model.is_downloaded and model.local_path:
            return Path(model.local_path)
        return None

    def get_downloaded_translation_models(self) -> List[str]:
        """返回已下载翻译模型的 model_id 列表。"""
        return [m.model_id for m in self.get_all_translation_models() if m.is_downloaded]

    def get_best_translation_model(
        self, source_lang: str, target_lang: str, auto_detect: bool = False
    ) -> Optional[TranslationModelInfo]:
        """寻找最匹配的翻译模型。

        Args:
            source_lang: 源语言代码（如果 auto_detect 为 True，则此参数为候选项或被忽略）。
            target_lang: 目标语言代码。
            auto_detect: 是否尝试根据已下载的模型自动匹配源语言。
        """
        if auto_detect:
            normalized_source = (source_lang or "").strip().lower()
            if normalized_source and normalized_source != "auto":
                hinted = self._translation_registry.get_by_langs(normalized_source, target_lang)
                if hinted:
                    logger.info(
                        "Auto-detect translation model with source hint %s->%s: %s",
                        normalized_source,
                        target_lang,
                        hinted.model_id,
                    )
                    return hinted

            # 搜索已下载的、目标语言匹配的所有模型
            downloaded = self.get_downloaded_translation_models()
            for mid in downloaded:
                model = self._translation_registry.get_by_id(mid)
                if model and model.target_lang == target_lang:
                    logger.info(
                        "Auto-matched translation model for target '%s': %s", target_lang, mid
                    )
                    return model

            # 如果没找到已下载的，尝试在注册表中找一个默认的
            for model in self._translation_registry.get_all():
                if model.target_lang == target_lang:
                    return model
        else:
            # 精确匹配
            model_id = f"opus-mt-{source_lang}-{target_lang}"
            return self.get_translation_model(model_id)

        return None

    async def download_translation_model(self, model_id: str) -> Path:
        """下载指定翻译模型，返回本地路径。"""
        model = self._translation_registry.get_by_id(model_id)
        if not model:
            raise ValueError(f"Unknown translation model: {model_id}")

        record = TranslationModelRecord.get_by_model_id(
            self._database, model_id
        ) or TranslationModelRecord(
            model_id=model_id,
            source_lang=model.source_lang,
            target_lang=model.target_lang,
        )

        def pre_cb():
            record.update_status(self._database, "downloading")

        def post_cb(path: Path):
            model.ensure_local_state(self._translation_models_dir)
            record.update_status(
                self._database,
                "downloaded",
                download_path=str(path),
                size_bytes=int(model.size_mb * 1024 * 1024),
                downloaded_at=current_iso_timestamp(),
            )
            self._refresh_translation_states()
            self.translation_models_updated.emit()

        try:
            return await self._execute_download(
                model_id,
                model,
                self.translation_downloader,
                pre_download_cb=pre_cb,
                post_download_cb=post_cb,
            )
        except Exception:
            record.update_status(self._database, "failed")
            raise

    def delete_translation_model(self, model_id: str) -> bool:
        """删除已下载的翻译模型文件并更新记录。"""
        import shutil

        model = self.get_translation_model(model_id)
        if not model or not model.is_downloaded or not model.local_path:
            logger.warning("Translation model not downloaded: %s", model_id)
            return False

        try:
            path = Path(model.local_path)
            if path.exists():
                shutil.rmtree(path, ignore_errors=True)

            record = TranslationModelRecord.get_by_model_id(self._database, model_id)
            if record:
                record.update_status(
                    self._database,
                    "not_downloaded",
                    download_path=None,
                    size_bytes=None,
                    downloaded_at=None,
                )

            self._refresh_translation_states()
            self.translation_models_updated.emit()
            return True
        except Exception as exc:
            logger.error("Failed to delete translation model %s: %s", model_id, exc)
            return False

    def _on_translation_download_completed(self, name: str) -> None:
        logger.info("Translation model download completed: %s", name)
        self._refresh_translation_states()
        self.translation_models_updated.emit()

    def _on_translation_download_failed(self, name: str, error: str) -> None:
        logger.error("Translation model download failed for %s: %s", name, error)
        # 更新数据库状态为 failed
        record = TranslationModelRecord.get_by_model_id(self._database, name)
        if record:
            record.update_status(self._database, "failed")
        self.translation_models_updated.emit()
