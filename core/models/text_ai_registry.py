# SPDX-License-Identifier: Apache-2.0
"""Text AI model registry for workspace summarization and meeting cleanup."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple


@dataclass
class TextAIModelInfo:
    """Metadata for locally managed Text AI models."""

    model_id: str
    display_name: str
    runtime: str  # extractive / onnx / gguf
    provider: str  # builtin / onnxruntime / llama_cpp
    description: str
    family: str  # summary / meeting
    size_mb: int
    repo_id: str = ""
    revision: str = "main"
    required_files: Tuple[str, ...] = field(default_factory=tuple)
    download_files: Tuple[Tuple[str, str], ...] = field(default_factory=tuple)
    optional_files: Tuple[str, ...] = field(default_factory=tuple)
    local_path: Optional[str] = None
    is_downloaded: bool = False
    download_date: Optional[datetime] = None
    use_count: int = 0
    last_used: Optional[datetime] = None
    name: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", self.model_id)

    def clone(self) -> "TextAIModelInfo":
        clone = replace(self)
        object.__setattr__(clone, "name", self.model_id)
        return clone

    def ensure_local_state(self, models_dir: Path) -> None:
        """Refresh download state from disk."""
        if self.runtime == "extractive":
            self.local_path = "builtin://extractive-default"
            self.is_downloaded = True
            return

        candidate = models_dir / self.model_id
        if candidate.exists() and candidate.is_dir():
            has_required = all((candidate / file_name).exists() for file_name in self.required_files)
            if has_required:
                self.local_path = str(candidate)
                self.is_downloaded = True
                try:
                    self.download_date = datetime.fromtimestamp(candidate.stat().st_mtime)
                except OSError:
                    self.download_date = None
                return

        self.local_path = None
        self.is_downloaded = False
        self.download_date = None


class TextAIModelRegistry:
    """Registry of built-in Text AI model definitions."""

    def __init__(self) -> None:
        self._models: Dict[str, TextAIModelInfo] = {
            info.model_id: info for info in self._build_default_models()
        }

    def _build_default_models(self) -> List[TextAIModelInfo]:
        return [
            TextAIModelInfo(
                model_id="extractive-default",
                display_name="Extractive Summary",
                runtime="extractive",
                provider="builtin",
                description="Deterministic sentence-ranking summarizer for offline fallback.",
                family="summary",
                size_mb=0,
            ),
            TextAIModelInfo(
                model_id="flan-t5-small-int8",
                display_name="Flan-T5 Small ONNX",
                runtime="onnx",
                provider="onnxruntime",
                description="Lightweight local abstractive summarizer for short meeting notes.",
                family="summary",
                size_mb=380,
                repo_id="dmmagdal/flan-t5-small-onnx",
                required_files=(
                    "encoder_model.onnx",
                    "decoder_model.onnx",
                    "config.json",
                    "generation_config.json",
                    "tokenizer_config.json",
                    "tokenizer.json",
                    "special_tokens_map.json",
                    "spiece.model",
                ),
                download_files=(
                    ("encoder_model.onnx", "encoder_model.onnx"),
                    ("decoder_model.onnx", "decoder_model.onnx"),
                    ("config.json", "config.json"),
                    ("generation_config.json", "generation_config.json"),
                    ("tokenizer_config.json", "tokenizer_config.json"),
                    ("tokenizer.json", "tokenizer.json"),
                    ("special_tokens_map.json", "special_tokens_map.json"),
                    ("spiece.model", "spiece.model"),
                ),
            ),
            TextAIModelInfo(
                model_id="gemma-3-1b-it-gguf",
                display_name="Gemma 3 1B Instruct",
                runtime="gguf",
                provider="llama_cpp",
                description="Fast local meeting cleanup model for concise structured outputs.",
                family="meeting",
                size_mb=770,
                repo_id="ggml-org/gemma-3-1b-it-GGUF",
                required_files=("model.gguf",),
                download_files=(("gemma-3-1b-it-Q4_K_M.gguf", "model.gguf"),),
            ),
            TextAIModelInfo(
                model_id="gemma-3-4b-it-gguf",
                display_name="Gemma 3 4B Instruct",
                runtime="gguf",
                provider="llama_cpp",
                description="Balanced local meeting model with better reasoning on action items.",
                family="meeting",
                size_mb=2375,
                repo_id="ggml-org/gemma-3-4b-it-GGUF",
                required_files=("model.gguf",),
                download_files=(("gemma-3-4b-it-Q4_K_M.gguf", "model.gguf"),),
            ),
            TextAIModelInfo(
                model_id="apertus-8b-instruct-gguf",
                display_name="Apertus 8B Instruct",
                runtime="gguf",
                provider="llama_cpp",
                description="Higher-quality local meeting summarization model for structured briefs.",
                family="meeting",
                size_mb=4825,
                repo_id="MaziyarPanahi/Apertus-8B-Instruct-2509-GGUF",
                required_files=("model.gguf",),
                download_files=(("Apertus-8B-Instruct-2509.Q4_K_M.gguf", "model.gguf"),),
            ),
        ]

    def get_all(self) -> List[TextAIModelInfo]:
        return [model.clone() for model in self._models.values()]

    def get_by_id(self, model_id: str) -> Optional[TextAIModelInfo]:
        model = self._models.get(model_id)
        return model.clone() if model else None
