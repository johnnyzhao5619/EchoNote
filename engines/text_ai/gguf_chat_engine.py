# SPDX-License-Identifier: Apache-2.0
"""GGUF chat runtime abstraction backed by llama.cpp-style subprocess execution."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional, Sequence

from engines.text_ai.base import TextAIEngine, TextAIRequest


class GGUFChatEngine(TextAIEngine):
    """Execute local GGUF models through a single runtime abstraction."""

    def __init__(
        self,
        model_id: str,
        model_path: Optional[Path],
        *,
        runtime_command: Optional[Sequence[str]] = None,
        timeout_seconds: int = 120,
    ) -> None:
        super().__init__(model_id, model_path)
        self.runtime_command = list(runtime_command or [])
        self.timeout_seconds = timeout_seconds

    def generate(self, request: TextAIRequest) -> str:
        if self.model_path is None:
            raise RuntimeError("GGUF model path is not configured")
        if not self.runtime_command:
            raise RuntimeError("GGUF runtime command is not configured")

        prompt = request.prompt or request.text
        command = list(self.runtime_command)
        command.extend(
            [
                "-m",
                str(self.model_path / "model.gguf"),
                "-p",
                prompt,
                "-n",
                str(request.max_output_tokens),
                "--temp",
                str(request.temperature),
            ]
        )
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=self.timeout_seconds,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "GGUF runtime execution failed")
        return result.stdout.strip()
