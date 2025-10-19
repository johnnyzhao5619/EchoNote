import sys
import types
from pathlib import Path

import pytest

if "PyQt6" not in sys.modules:
    qtcore_module = types.ModuleType("PyQt6.QtCore")

    class _QObject:  # pragma: no cover - simple stub for tests
        def __init__(self, *_, **__):
            pass

    class _Signal:  # pragma: no cover - simple stub for tests
        def __init__(self, *_, **__):
            pass

        def emit(self, *_, **__):
            pass

    def _pyqt_signal(*_, **__):  # pragma: no cover - simple stub for tests
        return _Signal()

    qtcore_module.QObject = _QObject
    qtcore_module.pyqtSignal = _pyqt_signal

    pyqt6_module = types.ModuleType("PyQt6")
    pyqt6_module.QtCore = qtcore_module

    sys.modules["PyQt6"] = pyqt6_module
    sys.modules["PyQt6.QtCore"] = qtcore_module

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from config import app_config
from config.app_config import ConfigManager
from core.settings.manager import SettingsManager


@pytest.fixture()
def settings_manager(tmp_path, monkeypatch):
    monkeypatch.setattr(app_config.Path, "home", lambda: tmp_path)
    config_manager = ConfigManager()
    return SettingsManager(config_manager)


def test_reset_to_default_restores_nested_structure(settings_manager):
    config_manager = settings_manager.config_manager

    default_colors_mapping = config_manager.get_defaults()["calendar"]["colors"]
    default_colors = {
        key: default_colors_mapping[key]
        for key in default_colors_mapping
    }

    settings_manager.set_setting("calendar.colors.local", "#000000")
    settings_manager.set_setting("calendar.colors.google", "#000001")
    settings_manager.set_setting("calendar.colors.outlook", "#000002")

    assert settings_manager.get_setting("calendar.colors.local") == "#000000"

    settings_manager.reset_to_default("calendar.colors")
    assert settings_manager.get_setting("calendar.colors") == default_colors

    settings_manager.set_setting("calendar.colors.local", "#123456")
    settings_manager.reset_to_default("calendar.colors")
    assert settings_manager.get_setting("calendar.colors") == default_colors


def test_new_settings_manager_resets_to_original_defaults(tmp_path, monkeypatch):
    monkeypatch.setattr(app_config.Path, "home", lambda: tmp_path)
    config_manager = ConfigManager()

    defaults = config_manager.get_defaults()
    default_colors_mapping = defaults["calendar"]["colors"]
    default_colors = {key: default_colors_mapping[key] for key in default_colors_mapping}
    default_page_size = defaults["timeline"]["page_size"]

    config_manager.set("calendar.colors.local", "#000111")
    config_manager.set("timeline.page_size", default_page_size + 10)

    settings_manager = SettingsManager(config_manager)

    assert settings_manager.get_setting("calendar.colors.local") == "#000111"
    assert settings_manager.reset_to_default("calendar.colors")
    assert settings_manager.get_setting("calendar.colors") == default_colors

    assert settings_manager.get_setting("timeline.page_size") == default_page_size + 10
    assert settings_manager.reset_to_default("timeline.page_size")
    assert settings_manager.get_setting("timeline.page_size") == default_page_size
