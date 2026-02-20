# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2025 EchoNote Contributors

"""
Utility functions for shared UI logic in EchoNote.
"""

import math
from typing import Any, Tuple

from core.qt_imports import QDate


def normalize_day_span(value: Any) -> int:
    """Return a non-negative integer day span derived from value."""
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return 0

    normalized = math.floor(numeric)
    return max(normalized, 0)


def calculate_date_range_defaults(past_days: int, future_days: int) -> Tuple[QDate, QDate]:
    """Compute default start/end dates derived from day spans."""
    current_date = QDate.currentDate()
    
    normalized_past = normalize_day_span(past_days)
    normalized_future = normalize_day_span(future_days)

    start_date = current_date.addDays(-normalized_past) if normalized_past else current_date
    end_date = current_date.addDays(normalized_future) if normalized_future else current_date
    return start_date, end_date
