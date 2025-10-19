import json
import sys
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from config import app_config
from config.app_config import APP_DIR_NAME, ConfigManager


def test_config_manager_merges_defaults(tmp_path, monkeypatch):
    monkeypatch.setattr(app_config.Path, "home", lambda: tmp_path)

    legacy_config_path = (
        Path(app_config.__file__).parent / "default_config.json"
    )
    legacy_config = json.loads(legacy_config_path.read_text(encoding="utf-8"))
    legacy_config.pop("timeline")
    legacy_config["transcription"]["faster_whisper"].pop("default_model")

    user_config_dir = tmp_path / APP_DIR_NAME
    user_config_dir.mkdir()
    user_config_file = user_config_dir / "app_config.json"
    user_config_file.write_text(
        json.dumps(legacy_config, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    manager = ConfigManager()

    merged = manager.get_all()
    assert merged["timeline"]["future_days"] == 30
    assert merged["timeline"]["page_size"] == 50
    assert (
        merged["transcription"]["faster_whisper"]["default_model"]
        == "base"
    )
    assert manager.get("timeline.page_size") == 50

    defaults = manager.get_defaults()
    assert (
        defaults["transcription"]["faster_whisper"]["default_model"]
        == "base"
    )
    with pytest.raises(TypeError):
        defaults["timeline"]["page_size"] = 10

    manager.save()

    saved_config = json.loads(user_config_file.read_text(encoding="utf-8"))
    assert saved_config["timeline"]["page_size"] == 50
    assert (
        saved_config["transcription"]["faster_whisper"]["default_model"]
        == "base"
    )


def test_config_manager_set_does_not_mutate_defaults(tmp_path, monkeypatch):
    monkeypatch.setattr(app_config.Path, "home", lambda: tmp_path)

    manager = ConfigManager()

    defaults = manager.get_defaults()
    original_page_size = defaults["timeline"]["page_size"]
    original_local_color = defaults["calendar"]["colors"]["local"]

    manager.set("timeline.page_size", original_page_size + 5)
    manager.set("calendar.colors.local", "#000000")

    assert manager.get("timeline.page_size") == original_page_size + 5

    defaults_after = manager.get_defaults()
    assert defaults_after["timeline"]["page_size"] == original_page_size
    assert defaults_after["calendar"]["colors"]["local"] == original_local_color
