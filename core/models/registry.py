"""可用模型注册表定义。"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple


@dataclass
class ModelInfo:
    """记录单个语音模型的元数据与状态。"""

    name: str
    full_name: str
    description: str
    size_mb: int
    speed: str
    accuracy: str
    languages: Tuple[str, ...]
    repo_id: str
    revision: str = "main"
    required_files: Tuple[str, ...] = (
        "config.json",
        "model.bin",
        "tokenizer.json",
    )
    optional_files: Tuple[str, ...] = field(default_factory=tuple)
    local_path: Optional[str] = None
    download_date: Optional[datetime] = None
    usage_count: int = 0
    last_used: Optional[datetime] = None
    is_downloaded: bool = False

    def clone(self) -> "ModelInfo":
        """返回该模型的独立副本。"""

        return replace(self)

    def ensure_local_state(self, models_dir: Path) -> None:
        """根据文件系统刷新本地状态。"""

        candidate = models_dir / self.name
        if candidate.exists() and candidate.is_dir():
            try:
                has_content = any(candidate.iterdir())
            except OSError:
                has_content = False
            if has_content:
                self.local_path = str(candidate)
                try:
                    self.download_date = datetime.fromtimestamp(
                        candidate.stat().st_mtime
                    )
                except OSError:
                    self.download_date = None
                self.is_downloaded = True
                return

        # 若目录不存在或为空，则标记为未下载
        self.local_path = None
        self.download_date = None
        self.is_downloaded = False


class ModelRegistry:
    """维护应用内置的可用模型列表。"""

    def __init__(self) -> None:
        self._models: Dict[str, ModelInfo] = {
            info.name: info
            for info in self._build_default_models()
        }
        self._order: List[str] = list(self._models.keys())

    def _build_default_models(self) -> Iterable[ModelInfo]:
        """构建默认模型集合。"""

        base_description = (
            "Faster-Whisper 官方模型，提供本地离线语音识别能力。"
        )

        return [
            ModelInfo(
                name="tiny",
                full_name="Faster Whisper Tiny",
                description=base_description,
                size_mb=75,
                speed="fastest",
                accuracy="low",
                languages=("multi",),
                repo_id="Systran/faster-whisper-tiny",
            ),
            ModelInfo(
                name="tiny.en",
                full_name="Faster Whisper Tiny (English)",
                description=base_description,
                size_mb=75,
                speed="fastest",
                accuracy="low",
                languages=("en",),
                repo_id="Systran/faster-whisper-tiny.en",
            ),
            ModelInfo(
                name="base",
                full_name="Faster Whisper Base",
                description=base_description,
                size_mb=142,
                speed="fast",
                accuracy="medium",
                languages=("multi",),
                repo_id="Systran/faster-whisper-base",
            ),
            ModelInfo(
                name="base.en",
                full_name="Faster Whisper Base (English)",
                description=base_description,
                size_mb=142,
                speed="fast",
                accuracy="medium",
                languages=("en",),
                repo_id="Systran/faster-whisper-base.en",
            ),
            ModelInfo(
                name="small",
                full_name="Faster Whisper Small",
                description=base_description,
                size_mb=462,
                speed="medium",
                accuracy="high",
                languages=("multi",),
                repo_id="Systran/faster-whisper-small",
            ),
            ModelInfo(
                name="small.en",
                full_name="Faster Whisper Small (English)",
                description=base_description,
                size_mb=462,
                speed="medium",
                accuracy="high",
                languages=("en",),
                repo_id="Systran/faster-whisper-small.en",
            ),
            ModelInfo(
                name="medium",
                full_name="Faster Whisper Medium",
                description=base_description,
                size_mb=1460,
                speed="slow",
                accuracy="high",
                languages=("multi",),
                repo_id="Systran/faster-whisper-medium",
            ),
            ModelInfo(
                name="medium.en",
                full_name="Faster Whisper Medium (English)",
                description=base_description,
                size_mb=1460,
                speed="slow",
                accuracy="high",
                languages=("en",),
                repo_id="Systran/faster-whisper-medium.en",
            ),
            ModelInfo(
                name="large-v2",
                full_name="Faster Whisper Large v2",
                description=base_description,
                size_mb=2900,
                speed="slow",
                accuracy="high",
                languages=("multi",),
                repo_id="Systran/faster-whisper-large-v2",
            ),
            ModelInfo(
                name="large-v3",
                full_name="Faster Whisper Large v3",
                description=base_description,
                size_mb=3100,
                speed="slow",
                accuracy="high",
                languages=("multi",),
                repo_id="Systran/faster-whisper-large-v3",
            ),
        ]

    def list_models(self) -> List[ModelInfo]:
        """返回所有模型的副本列表。"""

        return [self._models[name].clone() for name in self._order]

    def get(self, name: str) -> Optional[ModelInfo]:
        """根据名称获取模型信息。"""

        model = self._models.get(name)
        if model is None:
            return None
        return model.clone()

    def has(self, name: str) -> bool:
        """判断模型是否存在。"""

        return name in self._models

    def default_model(self) -> str:
        """返回默认模型名称。"""

        return self._order[0]
