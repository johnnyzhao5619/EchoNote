import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

def _ensure_psutil_stub():
    if "psutil" in sys.modules:
        return

    psutil_module = ModuleType("psutil")

    class _VirtualMemory:
        available = 1024 * 1024 * 1024
        total = 4 * 1024 * 1024 * 1024
        percent = 0.0

    def _virtual_memory():
        return _VirtualMemory()

    def _cpu_percent(interval=None):  # noqa: ARG001
        return 0.0

    psutil_module.virtual_memory = _virtual_memory  # type: ignore[attr-defined]
    psutil_module.cpu_percent = _cpu_percent  # type: ignore[attr-defined]
    psutil_module.cpu_count = lambda *args, **kwargs: 1  # type: ignore[attr-defined, E731]

    sys.modules["psutil"] = psutil_module


_ensure_psutil_stub()


def _ensure_registry_stub():
    if "core.models.registry" in sys.modules:
        return

    core_module = sys.modules.setdefault("core", ModuleType("core"))
    models_module = ModuleType("core.models")
    models_module.__path__ = []  # type: ignore[attr-defined]
    sys.modules["core.models"] = models_module
    setattr(core_module, "models", models_module)

    registry_module = ModuleType("core.models.registry")
    registry_module.get_default_model_names = lambda: ("base",)  # type: ignore[attr-defined]
    sys.modules["core.models.registry"] = registry_module


_ensure_registry_stub()

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

    timeline_page_size = manager.get("timeline.page_size")
    database_path = manager.get("database.path")
    calendar_local_color = manager.get("calendar.colors.local")
    ui_theme = manager.get("ui.theme")

    merged["timeline"]["page_size"] = timeline_page_size + 10
    merged["database"]["path"] = "modified-path"
    merged["calendar"]["colors"]["local"] = "#FFFFFF"
    merged["ui"]["theme"] = "invalid-theme"

    assert manager.get("timeline.page_size") == timeline_page_size
    assert manager.get("database.path") == database_path
    assert manager.get("calendar.colors.local") == calendar_local_color
    assert manager.get("ui.theme") == ui_theme

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


@pytest.mark.parametrize(
    ("field", "value", "expected_exception"),
    [
        ("low_memory_mb", 10, ValueError),
        ("low_memory_mb", True, TypeError),
        ("high_cpu_percent", 120, ValueError),
        ("high_cpu_percent", "high", TypeError),
    ],
)
def test_config_manager_validates_resource_monitor_thresholds(
    tmp_path, monkeypatch, field, value, expected_exception
):
    monkeypatch.setattr(app_config.Path, "home", lambda: tmp_path)

    default_config_path = Path(app_config.__file__).parent / "default_config.json"
    base_config = json.loads(default_config_path.read_text(encoding="utf-8"))
    base_config["resource_monitor"][field] = value

    user_config_dir = tmp_path / APP_DIR_NAME
    user_config_dir.mkdir()
    (user_config_dir / "app_config.json").write_text(
        json.dumps(base_config, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    with pytest.raises(expected_exception):
        ConfigManager()


def test_config_manager_accepts_resource_monitor_overrides(tmp_path, monkeypatch):
    monkeypatch.setattr(app_config.Path, "home", lambda: tmp_path)

    default_config_path = Path(app_config.__file__).parent / "default_config.json"
    base_config = json.loads(default_config_path.read_text(encoding="utf-8"))
    base_config["resource_monitor"]["low_memory_mb"] = 768
    base_config["resource_monitor"]["high_cpu_percent"] = 75

    user_config_dir = tmp_path / APP_DIR_NAME
    user_config_dir.mkdir()
    (user_config_dir / "app_config.json").write_text(
        json.dumps(base_config, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    manager = ConfigManager()

    assert manager.get("resource_monitor.low_memory_mb") == 768
    assert manager.get("resource_monitor.high_cpu_percent") == 75
