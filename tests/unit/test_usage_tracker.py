from decimal import Decimal
from pathlib import Path
import sys

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from engines.speech.usage_tracker import UsageTracker


class _DummyDB:
    """用于隔离数据库依赖的简易占位符。"""

    def get_cursor(self, commit: bool = False):  # pragma: no cover - 不会在测试中调用
        raise AssertionError("测试不应访问数据库")


@pytest.fixture()
def usage_tracker():
    return UsageTracker(_DummyDB())


def _to_decimal(value: float) -> Decimal:
    """将浮点值转换为量化到 4 位小数的 Decimal。"""

    return Decimal(str(value)).quantize(Decimal('0.0001'))


def test_calculate_cost_azure_one_minute(usage_tracker):
    cost = usage_tracker.calculate_cost('azure', 60)
    assert _to_decimal(cost) == Decimal('0.0167')


@pytest.mark.parametrize(
    "engine,duration_seconds,expected",
    [
        ("openai", 90, Decimal('0.0090')),
        ("google", 30, Decimal('0.0030')),
        ("azure", 45, Decimal('0.0125')),
        ("unknown", 60, Decimal('0.0060')),
    ],
)
def test_calculate_cost_various_engines(usage_tracker, engine, duration_seconds, expected):
    cost = usage_tracker.calculate_cost(engine, duration_seconds)
    assert _to_decimal(cost) == expected
