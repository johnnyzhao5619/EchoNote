# SPDX-License-Identifier: Apache-2.0
"""ONNX-based summarizer runtime."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import numpy as np

from engines.text_ai.base import TextAIEngine, TextAIRequest
from engines.text_ai.extractive_engine import ExtractiveEngine


class OnnxSummarizer(TextAIEngine):
    """Wrapper for ONNX summarization models with deterministic fallback."""

    def __init__(self, model_id: str, model_path: Optional[Path] = None) -> None:
        super().__init__(model_id, model_path)
        self._fallback = ExtractiveEngine()
        self._config = None
        self._session = None
        self._tokenizer = None

    def generate(self, request: TextAIRequest) -> str:
        if not self.is_available():
            return self._fallback.generate(request)

        try:
            return self._generate_with_onnx(request)
        except Exception:
            return self._fallback.generate(request)

    def is_available(self) -> bool:
        if self.model_path is None:
            return False
        try:
            import onnxruntime  # noqa: F401
            from transformers import AutoTokenizer  # noqa: F401
        except ImportError:
            return False
        return (self.model_path / "model.onnx").exists()

    def _generate_with_onnx(self, request: TextAIRequest) -> str:
        tokenizer = self._get_tokenizer()
        session = self._get_session()
        config = self._get_config()

        source_text = (request.prompt or request.text or "").strip()
        encoded = tokenizer(
            source_text,
            return_tensors="np",
            truncation=True,
            max_length=512,
        )
        input_ids = np.asarray(encoded["input_ids"], dtype=np.int64)
        attention_mask = np.asarray(
            encoded.get("attention_mask", np.ones_like(input_ids)),
            dtype=np.int64,
        )

        decoder_start_token_id = self._resolve_decoder_start_token_id(tokenizer, config)
        eos_token_id = self._resolve_eos_token_id(tokenizer, config)
        decoder_input_ids = np.array([[decoder_start_token_id]], dtype=np.int64)

        for _ in range(max(1, min(int(request.max_output_tokens or 256), 256))):
            ort_inputs = self._build_ort_inputs(
                session,
                input_ids=input_ids,
                attention_mask=attention_mask,
                decoder_input_ids=decoder_input_ids,
            )
            outputs = session.run(None, ort_inputs)
            if not outputs:
                break
            logits = np.asarray(outputs[0])
            next_token_id = int(np.argmax(logits[0, -1, :]))
            decoder_input_ids = np.concatenate(
                [decoder_input_ids, np.array([[next_token_id]], dtype=np.int64)],
                axis=1,
            )
            if eos_token_id is not None and next_token_id == eos_token_id:
                break

        generated_ids = decoder_input_ids[0, 1:]
        if eos_token_id is not None and generated_ids.size and generated_ids[-1] == eos_token_id:
            generated_ids = generated_ids[:-1]

        summary = tokenizer.decode(generated_ids.tolist(), skip_special_tokens=True).strip()
        return summary or self._fallback.generate(request)

    def _get_session(self):
        if self._session is None:
            import onnxruntime

            self._session = onnxruntime.InferenceSession(
                str(self.model_path / "model.onnx"),
                providers=["CPUExecutionProvider"],
            )
        return self._session

    def _get_tokenizer(self):
        if self._tokenizer is None:
            from transformers import AutoTokenizer

            self._tokenizer = AutoTokenizer.from_pretrained(
                str(self.model_path),
                local_files_only=True,
            )
        return self._tokenizer

    def _get_config(self) -> dict:
        if self._config is None:
            self._config = json.loads((self.model_path / "config.json").read_text(encoding="utf-8"))
        return self._config

    def _build_ort_inputs(
        self,
        session,
        *,
        input_ids: np.ndarray,
        attention_mask: np.ndarray,
        decoder_input_ids: np.ndarray,
    ) -> dict:
        ort_inputs = {}
        input_names = {node.name for node in session.get_inputs()}

        if "input_ids" in input_names:
            ort_inputs["input_ids"] = input_ids
        if "attention_mask" in input_names:
            ort_inputs["attention_mask"] = attention_mask
        if "decoder_input_ids" in input_names:
            ort_inputs["decoder_input_ids"] = decoder_input_ids
        if "decoder_attention_mask" in input_names:
            ort_inputs["decoder_attention_mask"] = np.ones_like(decoder_input_ids, dtype=np.int64)

        if "input_ids" not in ort_inputs or "decoder_input_ids" not in ort_inputs:
            raise RuntimeError("ONNX summarizer is missing required seq2seq inputs")

        return ort_inputs

    def _resolve_decoder_start_token_id(self, tokenizer, config: dict) -> int:
        token_id = config.get("decoder_start_token_id")
        if token_id is not None:
            return int(token_id)
        if getattr(tokenizer, "cls_token_id", None) is not None:
            return int(tokenizer.cls_token_id)
        if getattr(tokenizer, "bos_token_id", None) is not None:
            return int(tokenizer.bos_token_id)
        if getattr(tokenizer, "pad_token_id", None) is not None:
            return int(tokenizer.pad_token_id)
        raise RuntimeError("Unable to resolve decoder start token id for ONNX summarizer")

    def _resolve_eos_token_id(self, tokenizer, config: dict) -> Optional[int]:
        token_id = config.get("eos_token_id")
        if token_id is not None:
            return int(token_id)
        if getattr(tokenizer, "eos_token_id", None) is not None:
            return int(tokenizer.eos_token_id)
        return None
