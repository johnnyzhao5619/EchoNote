# SPDX-License-Identifier: Apache-2.0
"""Unit tests for application configuration hygiene."""

import json

from config.app_config import ConfigManager


def test_config_manager_prunes_legacy_model_path_keys_from_user_config(tmp_path, monkeypatch):
    app_dir = tmp_path / ".echonote"
    app_dir.mkdir(parents=True, exist_ok=True)
    user_config_path = app_dir / "app_config.json"
    user_config_path.write_text(
        json.dumps(
            {
                "version": "2.1.3",
                "models": {"root_dir": "~/.echonote/models"},
                "transcription": {
                    "default_engine": "faster-whisper",
                    "default_output_format": "txt",
                    "max_concurrent_tasks": 2,
                    "faster_whisper": {
                        "model_size": "tiny",
                        "device": "auto",
                        "compute_type": "int8",
                        "model_dir": "~/.echonote/models",
                    },
                },
                "translation": {
                    "translation_engine": "none",
                    "translation_source_lang": "auto",
                    "translation_target_lang": "en",
                    "models_dir": "~/.echonote/translation_models",
                },
                "text_ai": {
                    "models_dir": "~/.echonote/text_ai_models",
                },
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr("config.app_config.get_app_dir", lambda: app_dir)

    manager = ConfigManager()

    assert manager.get("models.root_dir") == "~/.echonote/models"
    assert manager.get("transcription.faster_whisper.model_dir") is None
    assert manager.get("translation.models_dir") is None
    assert manager.get("text_ai.models_dir") is None

    persisted = json.loads(user_config_path.read_text(encoding="utf-8"))
    assert persisted["transcription"]["faster_whisper"]["model_dir"] == "~/.echonote/models"
    assert persisted["translation"]["models_dir"] == "~/.echonote/translation_models"
    assert persisted["text_ai"]["models_dir"] == "~/.echonote/text_ai_models"


def test_config_manager_save_prunes_legacy_model_path_keys_before_writing(tmp_path, monkeypatch):
    app_dir = tmp_path / ".echonote"
    app_dir.mkdir(parents=True, exist_ok=True)
    user_config_path = app_dir / "app_config.json"

    monkeypatch.setattr("config.app_config.get_app_dir", lambda: app_dir)

    manager = ConfigManager()
    manager._config["transcription"]["faster_whisper"]["model_dir"] = "~/.echonote/models"
    manager._config["translation"]["models_dir"] = "~/.echonote/translation_models"
    manager._config["text_ai"]["models_dir"] = "~/.echonote/text_ai_models"

    manager.save()

    persisted = json.loads(user_config_path.read_text(encoding="utf-8"))
    assert "model_dir" not in persisted["transcription"]["faster_whisper"]
    assert "models_dir" not in persisted["translation"]
    assert "models_dir" not in persisted["text_ai"]


def test_config_manager_rejects_legacy_model_path_keys(tmp_path, monkeypatch):
    app_dir = tmp_path / ".echonote"
    app_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("config.app_config.get_app_dir", lambda: app_dir)

    manager = ConfigManager()

    assert manager.validate_setting("transcription.faster_whisper.model_dir", "~/.echonote/models") is False
    assert manager.validate_setting("translation.models_dir", "~/.echonote/translation_models") is False
    assert manager.validate_setting("text_ai.models_dir", "~/.echonote/text_ai_models") is False
