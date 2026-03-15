# SPDX-License-Identifier: Apache-2.0
"""Unit tests for text AI model registry."""

from core.models.text_ai_registry import TextAIModelRegistry


def test_text_ai_registry_covers_all_runtime_families():
    registry = TextAIModelRegistry()

    runtimes = {model.runtime for model in registry.get_all()}

    assert {"extractive", "onnx", "gguf"}.issubset(runtimes)


def test_text_ai_registry_includes_builtin_extractive_model():
    registry = TextAIModelRegistry()

    model = registry.get_by_id("extractive-default")

    assert model is not None
    assert model.provider == "builtin"
