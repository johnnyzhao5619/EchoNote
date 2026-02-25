# SPDX-License-Identifier: Apache-2.0
"""Tests for translation model registry mappings."""

from core.models.translation_registry import TranslationModelRegistry


def test_en_to_ja_repo_id_points_to_public_helsinki_repo():
    registry = TranslationModelRegistry()
    model = registry.get_by_langs("en", "ja")

    assert model is not None
    assert model.model_id == "opus-mt-en-ja"
    assert model.repo_id == "Helsinki-NLP/opus-mt-en-jap"
