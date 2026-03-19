# SPDX-License-Identifier: Apache-2.0
"""Unit tests for ModelManager model lifecycle behavior."""

from pathlib import Path
from threading import Event
from unittest.mock import Mock, patch

from core.models.manager import ModelManager


def _build_config(
    models_dir: Path, default_engine: str = "faster-whisper", model_size: str = "base"
):
    config = Mock()

    def _get(key, default=None):
        if key == "models.root_dir":
            return str(models_dir)
        if key == "transcription.default_engine":
            return default_engine
        if key == "transcription.faster_whisper.model_size":
            return model_size
        return default

    config.get.side_effect = _get
    return config


@patch("core.models.manager.TranslationModelRecord.get_all", return_value=[])
@patch("core.models.manager.ModelUsageStats.get_all", return_value=[])
def test_model_manager_treats_incomplete_speech_model_as_not_downloaded(
    _mock_usage, _mock_trans, tmp_path
):

    models_dir = tmp_path / "models"
    base_dir = models_dir / "speech" / "base"
    base_dir.mkdir(parents=True, exist_ok=True)
    (base_dir / "config.json").write_text("{}", encoding="utf-8")

    manager = ModelManager(_build_config(models_dir), Mock())
    assert not manager.get_model("base").is_downloaded


@patch("core.models.manager.TranslationModelRecord.get_all", return_value=[])
@patch("core.models.manager.ModelUsageStats.get_all", return_value=[])
def test_recommend_model_no_longer_reads_legacy_default_model(_mock_usage, _mock_trans, tmp_path):

    models_dir = tmp_path / "models"
    config = _build_config(models_dir)

    registry = Mock()
    registry.list_models.return_value = []
    registry.has.return_value = False
    registry.default_model.return_value = "base"

    manager = ModelManager(config, Mock(), registry=registry)

    def _guard_get(key, default=None):
        if key == "transcription.faster_whisper.default_model":
            raise AssertionError("legacy key must not be read")
        return _build_config(models_dir).get(key, default)

    config.get.side_effect = _guard_get
    assert manager.recommend_model() == "base"


@patch("core.models.manager.TranslationModelRecord.get_all", return_value=[])
@patch("core.models.manager.ModelUsageStats.get_all", return_value=[])
def test_has_active_downloads_reflects_downloader_state(_mock_usage, _mock_trans, tmp_path):

    manager = ModelManager(_build_config(tmp_path / "models"), Mock())
    assert manager.has_active_downloads() is False

    with manager.downloader._lock:
        manager.downloader._active_flags["base"] = Event()
    assert manager.has_active_downloads() is True


@patch("core.models.manager.TranslationModelRecord.get_all", return_value=[])
@patch("core.models.manager.ModelUsageStats.get_all", return_value=[])
def test_get_best_translation_model_auto_detect_prefers_source_hint(
    _mock_usage, _mock_trans, tmp_path
):
    manager = ModelManager(_build_config(tmp_path / "models"), Mock())

    model = manager.get_best_translation_model("zh", "en", auto_detect=True)

    assert model is not None
    assert model.model_id == "opus-mt-zh-en"


@patch("core.models.manager.TranslationModelRecord.get_all", return_value=[])
@patch("core.models.manager.ModelUsageStats.get_all", return_value=[])
def test_get_best_translation_model_auto_detect_falls_back_to_downloaded_target_match(
    _mock_usage, _mock_trans, tmp_path
):
    manager = ModelManager(_build_config(tmp_path / "models"), Mock())
    manager.get_downloaded_translation_models = Mock(return_value=["opus-mt-ja-en"])

    model = manager.get_best_translation_model("auto", "en", auto_detect=True)

    assert model is not None
    assert model.model_id == "opus-mt-ja-en"


@patch("core.models.manager.TranslationModelRecord.get_all", return_value=[])
@patch("core.models.manager.ModelUsageStats.get_all", return_value=[])
def test_model_manager_lists_text_ai_models(_mock_usage, _mock_trans, tmp_path):
    manager = ModelManager(_build_config(tmp_path / "models"), Mock())

    models = manager.get_all_text_ai_models()

    assert any(model.model_id == "flan-t5-small-int8" for model in models)


@patch("core.models.manager.TranslationModelRecord.get_all", return_value=[])
@patch("core.models.manager.ModelUsageStats.get_all", return_value=[])
def test_model_manager_uses_unified_model_root_with_fixed_subdirectories(
    _mock_usage, _mock_trans, tmp_path
):
    models_root = tmp_path / "managed-models"

    manager = ModelManager(_build_config(models_root), Mock())

    assert manager._models_root_dir == models_root
    assert manager._models_dir == models_root / "speech"
    assert manager._translation_models_dir == models_root / "translation"
    assert manager._text_ai_models_dir == models_root / "text_ai"


def test_model_manager_tracks_text_ai_model_usage(tmp_path):
    from data.database.connection import DatabaseConnection

    db = DatabaseConnection(str(tmp_path / "models.db"))
    db.initialize_schema()
    manager = ModelManager(_build_config(tmp_path / "models"), db)

    manager.mark_text_ai_model_used("extractive-default")

    model = manager.get_text_ai_model("extractive-default")
    assert model is not None
    assert model.use_count == 1
    assert model.last_used is not None
