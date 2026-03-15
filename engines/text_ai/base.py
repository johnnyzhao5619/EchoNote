# SPDX-License-Identifier: Apache-2.0
"""Base abstractions for local Text AI engines."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class TextAIRequest:
    """Normalized generation request."""

    text: str
    prompt: Optional[str] = None
    max_output_tokens: int = 256
    temperature: float = 0.2


class TextAIEngine(ABC):
    """Base class for local text generation and summarization engines."""

    def __init__(self, model_id: str, model_path: Optional[Path] = None) -> None:
        self.model_id = model_id
        self.model_path = model_path

    @abstractmethod
    def generate(self, request: TextAIRequest) -> str:
        """Generate output for the given request."""
