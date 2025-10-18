"""ModelManager 功能测试。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import pytest
try:
    from PyQt6.QtCore import QCoreApplication
except ModuleNotFoundError:  # pragma: no cover - 测试环境缺少 PyQt6 时跳过
    pytest.skip("PyQt6 is required for ModelManager tests", allow_module_level=True)

from core.models.manager import ModelManager
from data.database.connection import DatabaseConnection


class _StubConfig:
    """最小化配置实现，满足 ModelManager 接口需求。"""

    def __init__(self, overrides: Dict[str, Any]):
        import json

        # 默认配置文件位于项目根目录下的 config/default_config.json，
        # 这里通过测试文件相对于项目根路径的层级关系推导出真实路径。
        default_path = Path(__file__).resolve().parents[2] / "config" / "default_config.json"
        with open(default_path, "r", encoding="utf-8") as fh:
            self._defaults = json.load(fh)
        self._overrides = overrides

    def get(self, key: str, default: Any = None) -> Any:
        if key in self._overrides:
            return self._overrides[key]

        parts = key.split(".")
        current = self._defaults
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return default
        return current


@pytest.fixture(scope="module")
def qt_app():
    app = QCoreApplication.instance()
    if app is None:
        app = QCoreApplication([])
    return app


@pytest.fixture()
def database(tmp_path: Path) -> DatabaseConnection:
    db_path = tmp_path / "test.db"
    connection = DatabaseConnection(str(db_path))
    connection.initialize_schema()
    yield connection
    connection.close_all()


@pytest.fixture()
def models_dir(tmp_path: Path) -> Path:
    path = tmp_path / "models"
    path.mkdir(parents=True, exist_ok=True)
    return path


@pytest.fixture()
def manager(models_dir: Path, database: DatabaseConnection) -> ModelManager:
    overrides = {"transcription.faster_whisper.model_dir": str(models_dir)}
    config = _StubConfig(overrides)
    return ModelManager(config, database)


def _prepare_model_dir(models_dir: Path, name: str) -> Path:
    path = models_dir / name
    path.mkdir(parents=True, exist_ok=True)
    for filename in ("config.json", "model.bin", "tokenizer.json"):
        file_path = path / filename
        file_path.write_bytes(b"test")
    return path


def test_manager_initializes_without_models(qt_app, manager: ModelManager):
    assert manager.get_downloaded_models() == []
    assert not manager.is_model_downloaded("base")


def test_mark_model_used_updates_stats(manager: ModelManager, models_dir: Path):
    _prepare_model_dir(models_dir, "base")

    manager.start_validation()
    assert manager.is_model_downloaded("base")

    manager.mark_model_used("base")
    model = manager.get_model("base")
    assert model is not None
    assert model.usage_count == 1
    assert model.last_used is not None


def test_recommend_model_returns_known_value(manager: ModelManager):
    recommended = manager.recommend_model()
    assert recommended in {m.name for m in manager.get_all_models()}
