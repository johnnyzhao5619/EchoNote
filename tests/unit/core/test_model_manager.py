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
        if key == "transcription.faster_whisper.model_dir":
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
def test_validation_removes_invalid_model_and_keeps_cache_consistent(
    _mock_usage, _mock_trans, tmp_path
):

    models_dir = tmp_path / "models"
    base_dir = models_dir / "base"
    base_dir.mkdir(parents=True, exist_ok=True)
    (base_dir / "config.json").write_text("{}", encoding="utf-8")

    manager = ModelManager(_build_config(models_dir), Mock())
    assert manager.get_model("base").is_downloaded

    manager.start_validation(deferred=False)
    assert not base_dir.exists()
    assert not manager.get_model("base").is_downloaded

    manager._refresh_cache()
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
