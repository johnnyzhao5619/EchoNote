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

from core.qt_imports import QDate, QDateTime, QLocale, QTime, Qt

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
            # QDateTime.toPython() returns a naive datetime if the QDateTime is local,
            # or an aware datetime if the QDateTime is UTC.
            # We can simplify the logic by letting astimezone(timezone.utc) handle it.
            dt = value.toPython()
    else:
        logger.warning("Unsupported type for to_utc_iso: %s", type(value))
        return str(value)

    if dt:
        # Simplify: astimezone(timezone.utc) handles naive (as local) and aware correctly
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

    return dt.astimezone()


def format_localized_datetime(
    value: Any,
    format_type: QLocale.FormatType = QLocale.FormatType.ShortFormat,
    include_date: bool = True,
    include_time: bool = True,
    i18n_manager: Optional[Any] = None,
) -> str:
    """
    Format a datetime-like value into a localized string.

    Args:
        value: datetime, QDateTime, or ISO string.
        format_type: QLocale format type (ShortFormat, LongFormat, etc.)
        include_date: Whether to include the date.
        include_time: Whether to include the time.
        i18n_manager: Optional I18nManager to use its current language.

    Returns:
        Localized string.
    """
    try:
        dt_local = to_local_datetime(value)
        qdt = QDateTime(dt_local)

        # Use i18n_manager to determine the locale, fallback to system locale
        if i18n_manager and hasattr(i18n_manager, "current_language"):
            locale = QLocale(i18n_manager.current_language)
        else:
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
