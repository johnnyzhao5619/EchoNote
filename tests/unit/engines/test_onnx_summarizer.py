# SPDX-License-Identifier: Apache-2.0
"""Tests for ONNX summarizer runtime."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

from engines.text_ai.base import TextAIRequest
from engines.text_ai.onnx_summarizer import OnnxSummarizer


class _FakeTokenizer:
    eos_token_id = 2
    pad_token_id = 0

    def __call__(self, text, return_tensors="np", truncation=True, max_length=512):
        return {
            "input_ids": np.array([[11, 12]], dtype=np.int64),
            "attention_mask": np.array([[1, 1]], dtype=np.int64),
        }

    def decode(self, token_ids, skip_special_tokens=True):
        if token_ids == [5]:
            return "short summary"
        return ""


class _FakeSession:
    def __init__(self):
        self._step = 0

    def get_inputs(self):
        return [
            SimpleNamespace(name="input_ids"),
            SimpleNamespace(name="attention_mask"),
            SimpleNamespace(name="decoder_input_ids"),
            SimpleNamespace(name="decoder_attention_mask"),
        ]

    def run(self, _outputs, _inputs):
        next_token = 5 if self._step == 0 else 2
        logits = np.zeros((1, 1, 8), dtype=np.float32)
        logits[0, -1, next_token] = 1.0
        self._step += 1
        return [logits]


def test_onnx_summarizer_generates_text_with_seq2seq_assets(tmp_path):
    model_dir = tmp_path / "onnx-model"
    model_dir.mkdir(parents=True)
    (model_dir / "model.onnx").write_bytes(b"onnx")
    (model_dir / "config.json").write_text(
        '{"decoder_start_token_id": 0, "eos_token_id": 2}',
        encoding="utf-8",
    )

    fake_session = _FakeSession()
    fake_tokenizer = _FakeTokenizer()
    fake_onnxruntime = SimpleNamespace(
        InferenceSession=lambda *_args, **_kwargs: fake_session
    )
    fake_transformers = SimpleNamespace(
        AutoTokenizer=SimpleNamespace(
            from_pretrained=lambda *_args, **_kwargs: fake_tokenizer
        )
    )

    with patch.dict(
        "sys.modules",
        {
            "onnxruntime": fake_onnxruntime,
            "transformers": fake_transformers,
        },
    ):
        summarizer = OnnxSummarizer("flan-t5-small-int8", model_dir)
        summary = summarizer.generate(TextAIRequest(text="meeting transcript", max_output_tokens=8))

    assert summary == "short summary"
