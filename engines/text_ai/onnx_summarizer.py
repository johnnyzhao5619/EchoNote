# SPDX-License-Identifier: Apache-2.0
"""ONNX-based summarizer runtime."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from engines.text_ai.base import TextAIEngine, TextAIRequest
from engines.text_ai.extractive_engine import ExtractiveEngine


class OnnxSummarizer(TextAIEngine):
    """Wrapper for ONNX summarization models with deterministic fallback."""

    def __init__(self, model_id: str, model_path: Optional[Path] = None) -> None:
        super().__init__(model_id, model_path)
        self._fallback = ExtractiveEngine()

    def generate(self, request: TextAIRequest) -> str:
        if not self.is_available():
            return self._fallback.generate(request)

        raise RuntimeError(
            "ONNX summarizer runtime requires exported seq2seq assets; "
            "install the model files before enabling abstractive summaries."
        )

    def is_available(self) -> bool:
        if self.model_path is None:
            return False
        try:
            import onnxruntime  # noqa: F401
        except ImportError:
            return False
        return (self.model_path / "model.onnx").exists()
