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
"""Helsinki-NLP/Opus-MT（MarianMT）本地翻译引擎。

特性：
- 懒加载：首次调用 translate 时才加载模型和分词器（避免启动耗时）
- 分块处理：输入超过 512 token 时自动分块翻译后拼接
- 异步执行：模型推理通过 asyncio.to_thread 在线程池中执行，不阻塞事件循环
- 内存管理：提供 close() 显式释放模型资源
"""

import asyncio
import logging
from pathlib import Path
from typing import List, Optional

from engines.translation.base import TranslationEngine

logger = logging.getLogger(__name__)

# MarianMT 分词器最大序列长度（token 数）
_MAX_TOKENS = 512
# 分块时每块最大字符数估算（1 token ≈ 4 chars，留余量）
_CHUNK_CHAR_LIMIT = 1500


class OpusMTEngine(TranslationEngine):
    """Helsinki-NLP/Opus-MT（MarianMT）本地翻译引擎。

    本地模型已通过 ModelManager 预先下载至 model_dir。
    """

    def __init__(
        self,
        model_dir: Path,
        source_lang: str = "auto",
        target_lang: str = "en",
    ) -> None:
        self._model_dir = Path(model_dir)
        self._source_lang = source_lang
        self._target_lang = target_lang
        self._model = None  # MarianMTModel（懒加载）
        self._tokenizer = None  # MarianTokenizer（懒加载）
        self._load_lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # TranslationEngine 接口实现
    # ------------------------------------------------------------------

    def get_name(self) -> str:
        return "opus-mt"

    def get_supported_languages(self) -> List[str]:
        """返回当前模型支持的语言列表（源语言 + 目标语言 + auto）。"""
        return ["auto", self._source_lang, self._target_lang]

    async def translate(self, text: str, source_lang: str = "auto", target_lang: str = "en") -> str:
        """翻译文本。

        Args:
            text: 待翻译文本（可超过 512 token，内部自动分块）
            source_lang: 源语言代码（opus-mt 模型固定语言对，此参数仅记录日志）
            target_lang: 目标语言代码（同上）

        Returns:
            翻译后的文本。
        """
        if not text.strip():
            return ""

        await self._ensure_loaded()

        # 分块翻译（文本过长时）
        chunks = self._split_text(text)
        if len(chunks) == 1:
            translated = await asyncio.to_thread(self._translate_chunk, chunks[0])
        else:
            parts = await asyncio.gather(
                *[asyncio.to_thread(self._translate_chunk, chunk) for chunk in chunks]
            )
            translated = " ".join(parts)

        logger.debug(
            "Translated %d chars (%s→%s via opus-mt)",
            len(text),
            source_lang,
            target_lang,
        )
        return translated

    async def is_available(self) -> bool:
        """检查模型文件是否存在（不加载模型）。"""
        core_configs = ["config.json", "tokenizer_config.json"]
        if not self._model_dir.exists() or not all(
            (self._model_dir / f).exists() for f in core_configs
        ):
            return False

        # 权重文件检查（支持 bin 或 safetensors）
        return (self._model_dir / "model.safetensors").exists() or (
            self._model_dir / "pytorch_model.bin"
        ).exists()

    def close(self) -> None:
        """释放模型和分词器资源。"""
        self._model = None
        self._tokenizer = None
        logger.debug("OpusMTEngine resources released")

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    async def _ensure_loaded(self) -> None:
        """确保模型和分词器已加载（线程安全的懒加载）。"""
        if self._model is not None:
            return

        async with self._load_lock:
            if self._model is not None:
                return

            if not await self.is_available():
                raise RuntimeError(
                    f"Opus-MT model not found at {self._model_dir}. "
                    "Please download the model from Settings → Model Management."
                )

            logger.info("Loading Opus-MT model from %s", self._model_dir)
            await asyncio.to_thread(self._load_model_sync)
            logger.info("Opus-MT model loaded successfully")

    def _load_model_sync(self) -> None:
        """在线程中同步加载模型（由 asyncio.to_thread 调用）。"""
        try:
            from transformers import MarianMTModel, MarianTokenizer
        except ImportError as exc:
            raise ImportError(
                "transformers package is required for Opus-MT translation. "
                "Install it with: pip install transformers sentencepiece"
            ) from exc

        self._tokenizer = MarianTokenizer.from_pretrained(str(self._model_dir))
        self._model = MarianMTModel.from_pretrained(str(self._model_dir))
        # 设为评估模式，节省内存并提升推理速度
        self._model.eval()

    def _translate_chunk(self, text: str) -> str:
        """同步翻译单块文本（在线程池中执行）。"""
        inputs = self._tokenizer(
            [text],
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=_MAX_TOKENS,
        )
        import torch

        with torch.no_grad():
            translated_ids = self._model.generate(**inputs)
        result = self._tokenizer.decode(translated_ids[0], skip_special_tokens=True)
        return result

    @staticmethod
    def _split_text(text: str) -> List[str]:
        """按句子边界分块，使每块不超过字符限制。"""
        if len(text) <= _CHUNK_CHAR_LIMIT:
            return [text]

        # 按句子结束符分割
        import re

        sentences = re.split(r"(?<=[.!?。！？\n])\s*", text)
        chunks: List[str] = []
        current = ""
        for sentence in sentences:
            if not sentence:
                continue
            if len(current) + len(sentence) + 1 > _CHUNK_CHAR_LIMIT and current:
                chunks.append(current.strip())
                current = sentence
            else:
                current = (current + " " + sentence).strip()
        if current:
            chunks.append(current)
        return chunks or [text]


class MultiModelOpusMTEngine(TranslationEngine):
    """支持多语言对切换的 Opus-MT 引擎包装器。

    根据 source_lang 和 target_lang 动态加载和缓存对应的 OpusMTEngine。
    """

    def __init__(self, model_manager, target_lang: str = "en") -> None:
        self.model_manager = model_manager
        self.target_lang = target_lang
        self._engines: dict[str, OpusMTEngine] = {}
        self._lock = asyncio.Lock()

    def get_name(self) -> str:
        return "opus-mt-multi"

    def get_supported_languages(self) -> List[str]:
        # 从 ModelManager 获取所有支持的语言
        return ["auto"] + self.model_manager.get_available_translation_languages()

    async def translate(self, text: str, source_lang: str = "auto", target_lang: str = "en") -> str:
        if not text.strip():
            return ""

        if source_lang == "auto":
            # 如果是 auto，且没有传入具体的 detected_lang，则尝试找一个默认模型
            # 这种情况通常发生在还没检测到语言时。
            # 注意：RealtimeRecorder 现在会传具体的 detected_lang
            pass

        # 查找或创建具体的引擎实例
        engine = await self._get_engine(source_lang, target_lang)
        if not engine:
            logger.warning("No Opus-MT model available for %s -> %s", source_lang, target_lang)
            return text  # 返回原文作为 fallback

        return await engine.translate(text, source_lang, target_lang)

    async def _get_engine(self, source_lang: str, target_lang: str) -> Optional[OpusMTEngine]:
        """寻找并加载最匹配的翻译引擎。"""
        # 寻找模型元数据
        model_info = self.model_manager.get_best_translation_model(
            source_lang, target_lang, auto_detect=(source_lang == "auto")
        )

        if not model_info or not model_info.is_downloaded:
            return None

        model_id = model_info.model_id
        async with self._lock:
            if model_id not in self._engines:
                # 限制缓存数量，避免内存溢出（可选，此处先简单缓存）
                if len(self._engines) >= 3:
                    # 简单策略：清空旧缓存
                    old_id, old_engine = self._engines.popitem()
                    old_engine.close()
                    logger.debug("Evicted old translation engine from cache: %s", old_id)

                engine = OpusMTEngine(
                    Path(model_info.local_path), model_info.source_lang, model_info.target_lang
                )
                self._engines[model_id] = engine

            return self._engines[model_id]

    def close(self) -> None:
        for engine in self._engines.values():
            engine.close()
        self._engines.clear()
