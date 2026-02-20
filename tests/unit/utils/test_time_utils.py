# SPDX-License-Identifier: Apache-2.0
"""
Unit tests for time utilities.
"""

from datetime import datetime, timedelta, timezone

import pytest
from PySide6.QtCore import QDateTime, QLocale

from utils.time_utils import (
    current_iso_timestamp,
    format_localized_datetime,
    now_utc,
    to_local_datetime,
    to_utc_iso,
)


def test_now_utc():
    """Test now_utc returns aware UTC datetime."""
    dt = now_utc()
    assert dt.tzinfo == timezone.utc
    # Should be close to current time
    assert abs((datetime.now(timezone.utc) - dt).total_seconds()) < 5


def test_to_utc_iso_from_datetime():
    """Test conversion from datetime object to UTC ISO string."""
    # Aware datetime
    dt = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone(timedelta(hours=8)))
    iso = to_utc_iso(dt)
    assert iso == "2024-01-01T04:00:00Z"

    # Naive datetime (treated as local)
    # This behavior depends on the system timezone, but we can verify it has Z
    dt_naive = datetime(2024, 1, 1, 12, 0, 0)
    iso_naive = to_utc_iso(dt_naive)
    assert iso_naive.endswith("Z")


def test_to_utc_iso_from_string():
    """Test conversion from string to UTC ISO string."""
    # UTC string
    assert to_utc_iso("2024-01-01T12:00:00Z") == "2024-01-01T12:00:00Z"
    # Offset string
    assert to_utc_iso("2024-01-01T12:00:00+08:00") == "2024-01-01T04:00:00Z"


def test_to_utc_iso_from_qdatetime():
    """Test conversion from QDateTime to UTC ISO string."""
    qdt = QDateTime.fromString("2024-01-01T12:00:00", "yyyy-MM-ddTHH:mm:ss")
    # QDateTime without spec is usually local
    iso = to_utc_iso(qdt)
    assert iso.endswith("Z")


def test_to_local_datetime_from_utc_iso():
    """Test conversion from UTC ISO string to local aware datetime."""
    iso = "2024-01-01T12:00:00Z"
    dt = to_local_datetime(iso)
    assert dt.tzinfo is not None
    # Convert back to UTC to verify
    assert dt.astimezone(timezone.utc) == datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


def test_format_localized_datetime(qapp):
    """Test localized formatting."""
    iso = "2024-01-01T12:00:00Z"
    # Just verify it doesn't crash and returns a string
    formatted = format_localized_datetime(iso)
    assert isinstance(formatted, str)
    assert len(formatted) > 0


def test_current_iso_timestamp():
    """Test current_iso_timestamp returns UTC Z string."""
    ts = current_iso_timestamp()
    assert ts.endswith("Z")
    assert "T" in ts
