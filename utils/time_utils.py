# SPDX-License-Identifier: Apache-2.0
#
# Copyright (c) 2024-2025 EchoNote Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Time utilities for EchoNote."""

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from PySide6.QtCore import QDateTime, QLocale, Qt

logger = logging.getLogger("echonote.utils.time_utils")


def now_utc() -> datetime:
    """Get current datetime with UTC timezone."""
    return datetime.now(timezone.utc)


def now_local() -> datetime:
    """Get current datetime in system local timezone (aware)."""
    return now_utc().astimezone()


def current_iso_timestamp() -> str:
    """Get current UTC timestamp as ISO 8601 string with 'Z' suffix."""
    return now_utc().isoformat().replace("+00:00", "Z")


def to_utc_iso(value: Any) -> str:
    """
    Convert various datetime-like inputs to UTC ISO 8601 string with 'Z' suffix.

    Args:
        value: datetime, QDateTime, or ISO string.

    Returns:
        ISO 8601 formatted string in UTC.
    """
    if not value:
        return ""

    dt: Optional[datetime] = None

    if isinstance(value, str):
        try:
            # Handle 'Z' suffix which python's fromisoformat might not like in older versions
            text = value.replace("Z", "+00:00")
            dt = datetime.fromisoformat(text)
        except ValueError:
            logger.warning("Failed to parse ISO string: %s", value)
            return value
    elif isinstance(value, datetime):
        dt = value
    elif isinstance(value, QDateTime):
        # Convert QDateTime to Python datetime
        to_python = getattr(value, "toPython", None)
        if callable(to_python):
            dt = to_python()
        else:
            # Fallback for some environments
            qd = value.date()
            qt = value.time()
            dt = datetime(qd.year(), qd.month(), qd.day(), qt.hour(), qt.minute(), qt.second())
            if value.timeSpec() == Qt.TimeSpec.UTC:
                dt = dt.replace(tzinfo=timezone.utc)
    else:
        logger.warning("Unsupported type for to_utc_iso: %s", type(value))
        return str(value)

    if dt:
        if dt.tzinfo is None:
            # Assume naive is local time unless it's explicitly UTC
            dt = dt.astimezone(timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        return dt.isoformat().replace("+00:00", "Z")

    return str(value)


def to_local_datetime(value: Any) -> datetime:
    """
    Convert various datetime-like inputs to a Python datetime in system local timezone.

    Args:
        value: datetime, QDateTime, or ISO string.

    Returns:
        Aware datetime object in local time.
    """
    if isinstance(value, str):
        text = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(text)
    elif isinstance(value, QDateTime):
        to_python = getattr(value, "toPython", None)
        dt = to_python() if callable(to_python) else datetime.now()  # Fallback
    elif isinstance(value, datetime):
        dt = value
    else:
        return datetime.now()

    if dt.tzinfo is None:
        # Naive: assume it's already local or make it local
        return dt.astimezone()

    return dt.astimezone()


def format_localized_datetime(
    value: Any,
    format_type: QLocale.FormatType = QLocale.FormatType.ShortFormat,
    include_date: bool = True,
    include_time: bool = True,
) -> str:
    """
    Format a datetime-like value into a localized string using system locale.

    Args:
        value: datetime, QDateTime, or ISO string.
        format_type: QLocale format type (ShortFormat, LongFormat, etc.)
        include_date: Whether to include the date.
        include_time: Whether to include the time.

    Returns:
        Localized string.
    """
    try:
        dt_local = to_local_datetime(value)
        qdt = QDateTime(dt_local)
        locale = QLocale.system()

        if include_date and include_time:
            return locale.toString(qdt, format_type)
        elif include_date:
            return locale.toString(qdt.date(), format_type)
        elif include_time:
            return locale.toString(qdt.time(), format_type)
        return ""
    except Exception as exc:
        logger.warning("Failed to format localized datetime %s: %s", value, exc)
        return str(value)
