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
"""
Helsinki-NLP/Opus-MT 翻译模型注册表。

TranslationModelInfo 字段有意对齐 ModelInfo（repo_id / revision /
required_files / is_downloaded / ensure_local_state），以便直接传入
ModelDownloader.download() 实现鸭子类型复用，无需修改下载器。
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class TranslationModelInfo:
    """Opus-MT 语言对模型元数据。

    字段命名与 ModelInfo 保持一致，以便直接传入 ModelDownloader.download()。
    仅保留与翻译模型相关的属性，去掉语音模型专属的 speed / accuracy 字段。
    """

    model_id: str = ""  # "opus-mt-zh-en"
    source_lang: str = ""  # "zh"
    target_lang: str = ""  # "en"
    display_name: str = ""  # "中文 → English"

    # ---- ModelDownloader 需要读取的字段（与 ModelInfo 同名同义） ----
    # name 用于下载目录命名（ModelDownloader 使用 model.name 创建子目录）
    name: str = field(init=False, repr=False)
    repo_id: str = ""  # "Helsinki-NLP/opus-mt-zh-en"
    revision: str = "main"
    # 核心配置文件，权重文件（bin/safetensors）在 ensure_local_state 中动态检查
    required_files: Tuple[str, ...] = (
        "config.json",
        "tokenizer_config.json",
        "vocab.json",
        "source.spm",
        "target.spm",
    )
    optional_files: Tuple[str, ...] = field(default_factory=tuple)

    # ---- 本地状态（由 ensure_local_state 填充） ----
    local_path: Optional[str] = None
    is_downloaded: bool = False
    size_mb: int = 0  # 下载后显示实际大小，下载前显示预计大小

    # ---- 统计信息（由 ModelManager 填充） ----
    use_count: int = 0
    last_used: Optional[datetime] = None
    download_date: Optional[datetime] = None

    def __post_init__(self) -> None:
        # ModelDownloader 使用 model.name 命名本地目录
        object.__setattr__(self, "name", self.model_id)

    def ensure_local_state(self, models_dir: Path) -> None:
        """根据文件系统刷新下载状态（与 ModelInfo.ensure_local_state 同构）。"""
        candidate = models_dir / self.model_id
        if candidate.exists() and candidate.is_dir():
            try:
                # 检查核心配置
                has_config = all((candidate / f).exists() for f in self.required_files)
                # 检查权重文件（支持 bin 或 safetensors）
                has_weights = (candidate / "model.safetensors").exists() or (
                    candidate / "pytorch_model.bin"
                ).exists()

                if has_config and has_weights:
                    self.local_path = str(candidate)
                    self.is_downloaded = True
                    # 更新实际大小
                    total_size = sum(f.stat().st_size for f in candidate.rglob("*") if f.is_file())
                    self.size_mb = max(1, total_size // (1024 * 1024))
                    return
            except Exception:
                pass

        self.local_path = None
        self.is_downloaded = False

    def clone(self) -> "TranslationModelInfo":
        from dataclasses import replace

        cloned = replace(self)
        cloned.name = self.model_id  # 重新设置 post_init 属性
        return cloned


# ---------------------------------------------------------------------------
# 预置语言对注册表
# ---------------------------------------------------------------------------

# 每条记录：(model_id, source_lang, target_lang, display_name, repo_id, estimated_size_mb)
_PRESET_MODELS: List[Tuple[str, str, str, str, str, int]] = [
    ("opus-mt-zh-en", "zh", "en", "中文 → English", "Helsinki-NLP/opus-mt-zh-en", 312),
    ("opus-mt-en-zh", "en", "zh", "English → 中文", "Helsinki-NLP/opus-mt-en-zh", 312),
    ("opus-mt-ja-en", "ja", "en", "日本語 → English", "Helsinki-NLP/opus-mt-ja-en", 312),
    ("opus-mt-en-ja", "en", "ja", "English → 日本語", "Helsinki-NLP/opus-mt-en-ja", 312),
    ("opus-mt-ko-en", "ko", "en", "한국어 → English", "Helsinki-NLP/opus-mt-ko-en", 312),
    ("opus-mt-en-ko", "en", "ko", "English → 한국어", "Helsinki-NLP/opus-mt-en-ko", 312),
    ("opus-mt-fr-en", "fr", "en", "Français → English", "Helsinki-NLP/opus-mt-fr-en", 300),
    ("opus-mt-en-fr", "en", "fr", "English → Français", "Helsinki-NLP/opus-mt-en-fr", 300),
    ("opus-mt-de-en", "de", "en", "Deutsch → English", "Helsinki-NLP/opus-mt-de-en", 298),
    ("opus-mt-en-de", "en", "de", "English → Deutsch", "Helsinki-NLP/opus-mt-en-de", 298),
    ("opus-mt-es-en", "es", "en", "Español → English", "Helsinki-NLP/opus-mt-es-en", 310),
    ("opus-mt-en-es", "en", "es", "English → Español", "Helsinki-NLP/opus-mt-en-es", 310),
]


class TranslationModelRegistry:
    """Opus-MT 翻译模型注册表（内存中，无需数据库）。"""

    def __init__(self) -> None:
        self._models: Dict[str, TranslationModelInfo] = {}
        for model_id, src, tgt, display, repo, estimated_size in _PRESET_MODELS:
            info = TranslationModelInfo(
                model_id=model_id,
                source_lang=src,
                target_lang=tgt,
                display_name=display,
                repo_id=repo,
                size_mb=estimated_size,
            )
            self._models[model_id] = info

    def get_all(self) -> List[TranslationModelInfo]:
        """返回所有已注册模型（副本列表）。"""
        return [m.clone() for m in self._models.values()]

    def get_by_id(self, model_id: str) -> Optional[TranslationModelInfo]:
        """按 model_id 查询，返回副本；不存在时返回 None。"""
        m = self._models.get(model_id)
        return m.clone() if m else None

    def get_by_langs(self, source_lang: str, target_lang: str) -> Optional[TranslationModelInfo]:
        """按源/目标语言查询（精确匹配）。"""
        for m in self._models.values():
            if m.source_lang == source_lang and m.target_lang == target_lang:
                return m.clone()
        return None

    def get_available_sources(self) -> List[str]:
        """返回所有可用的源语言代码（去重）。"""
        return sorted({m.source_lang for m in self._models.values()})

    def get_available_targets(self, source_lang: Optional[str] = None) -> List[str]:
        """返回给定源语言下可用的目标语言代码；source_lang 为 None 时返回全部。"""
        if source_lang is None:
            return sorted({m.target_lang for m in self._models.values()})
        return sorted(
            {m.target_lang for m in self._models.values() if m.source_lang == source_lang}
        )


# 全局单例（lazy import 友好）
_registry: Optional[TranslationModelRegistry] = None


def get_translation_registry() -> TranslationModelRegistry:
    """获取全局翻译模型注册表单例。"""
    global _registry
    if _registry is None:
        _registry = TranslationModelRegistry()
    return _registry
