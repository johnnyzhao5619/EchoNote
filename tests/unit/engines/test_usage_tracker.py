# SPDX-License-Identifier: Apache-2.0
"""
Unit tests for UsageTracker.

Tests API usage tracking, cost calculation, and statistics retrieval.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, Mock

import pytest

from engines.speech.usage_tracker import UsageTracker


class MockCursor:
    """Mock database cursor."""

    def __init__(self):
        self.execute_calls = []
        self.fetchall_results = []
        self.fetchall_index = 0

    def execute(self, query, params=None):
        """Mock execute method."""
        self.execute_calls.append({"query": query, "params": params})

    def fetchall(self):
        """Mock fetchall method."""
        if self.fetchall_index < len(self.fetchall_results):
            result = self.fetchall_results[self.fetchall_index]
            self.fetchall_index += 1
            return result
        return []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


class MockDBConnection:
    """Mock database connection."""

    def __init__(self):
        self.cursor = MockCursor()
        self.commit_called = False

    def get_cursor(self, commit=False):
        """Mock get_cursor method."""
        self.commit_called = commit
        return self.cursor


@pytest.fixture
def mock_db():
    """Create mock database connection."""
    return MockDBConnection()


@pytest.fixture
def usage_tracker(mock_db):
    """Create UsageTracker instance."""
    return UsageTracker(mock_db)


class TestUsageTrackerInitialization:
    """Test UsageTracker initialization."""

    def test_init(self, usage_tracker, mock_db):
        """Test basic initialization."""
        assert usage_tracker.db == mock_db
        assert "openai" in UsageTracker.PRICING
        assert "google" in UsageTracker.PRICING
        assert "azure" in UsageTracker.PRICING


class TestCostCalculation:
    """Test cost calculation methods."""

    def test_calculate_cost_openai(self, usage_tracker):
        """Test cost calculation for OpenAI."""
        # 60 seconds = 1 minute = $0.006
        cost = usage_tracker.calculate_cost("openai", 60)
        assert cost == pytest.approx(0.006, rel=1e-4)

    def test_calculate_cost_google(self, usage_tracker):
        """Test cost calculation for Google."""
        # 120 seconds = 2 minutes = $0.012
        cost = usage_tracker.calculate_cost("google", 120)
        assert cost == pytest.approx(0.012, rel=1e-4)

    def test_calculate_cost_azure(self, usage_tracker):
        """Test cost calculation for Azure."""
        # 60 seconds = 1 minute = $0.0167
        cost = usage_tracker.calculate_cost("azure", 60)
        assert cost == pytest.approx(0.0167, rel=1e-4)

    def test_calculate_cost_fractional_seconds(self, usage_tracker):
        """Test cost calculation with fractional seconds."""
        # 30 seconds = 0.5 minutes = $0.003
        cost = usage_tracker.calculate_cost("openai", 30)
        assert cost == pytest.approx(0.003, rel=1e-4)

    def test_calculate_cost_unknown_engine(self, usage_tracker):
        """Test cost calculation for unknown engine uses default pricing."""
        # Should use default pricing of $0.006 per minute
        cost = usage_tracker.calculate_cost("unknown", 60)
        assert cost == pytest.approx(0.006, rel=1e-4)

    def test_calculate_cost_zero_duration(self, usage_tracker):
        """Test cost calculation with zero duration."""
        cost = usage_tracker.calculate_cost("openai", 0)
        assert cost == 0.0

    def test_estimate_cost(self, usage_tracker):
        """Test estimate_cost method."""
        # Should be same as calculate_cost
        cost = usage_tracker.estimate_cost("openai", 60)
        assert cost == pytest.approx(0.006, rel=1e-4)


class TestRecordUsage:
    """Test usage recording."""

    def test_record_usage_basic(self, usage_tracker, mock_db):
        """Test basic usage recording."""
        record_id = usage_tracker.record_usage("openai", 60.0)

        # Should return a UUID
        assert isinstance(record_id, str)
        assert len(record_id) == 36  # UUID format

        # Should execute INSERT query
        assert len(mock_db.cursor.execute_calls) == 1
        call = mock_db.cursor.execute_calls[0]
        assert "INSERT INTO api_usage" in call["query"]
        assert call["params"][1] == "openai"
        assert call["params"][2] == 60.0

        # Should commit
        assert mock_db.commit_called

    def test_record_usage_with_timestamp(self, usage_tracker, mock_db):
        """Test usage recording with custom timestamp."""
        timestamp = datetime(2025, 10, 30, 12, 0, 0)
        record_id = usage_tracker.record_usage("google", 120.0, timestamp)

        assert isinstance(record_id, str)
        call = mock_db.cursor.execute_calls[0]
        assert call["params"][4] == timestamp

    def test_record_usage_calculates_cost(self, usage_tracker, mock_db):
        """Test that record_usage calculates cost correctly."""
        usage_tracker.record_usage("openai", 60.0)

        call = mock_db.cursor.execute_calls[0]
        cost = call["params"][3]
        assert cost == pytest.approx(0.006, rel=1e-4)

    def test_record_usage_error_handling(self, usage_tracker, mock_db):
        """Test error handling in record_usage."""

        # Make cursor raise error
        def raise_error(*args, **kwargs):
            raise RuntimeError("Database error")

        mock_db.cursor.execute = raise_error

        with pytest.raises(RuntimeError, match="Database error"):
            usage_tracker.record_usage("openai", 60.0)


class TestMonthlyUsage:
    """Test monthly usage statistics."""

    def test_get_monthly_usage_single_engine(self, usage_tracker, mock_db):
        """Test getting monthly usage for single engine."""
        # Mock database result
        mock_db.cursor.fetchall_results = [
            [("openai", 3600.0, 0.36, 10)]  # 1 hour, $0.36, 10 calls
        ]

        result = usage_tracker.get_monthly_usage("openai", 2025, 10)

        assert result["engine"] == "openai"
        assert result["total_duration_seconds"] == 3600.0
        assert result["total_duration_minutes"] == 60.0
        assert result["total_cost"] == 0.36
        assert result["usage_count"] == 10
        assert result["period"]["year"] == 2025
        assert result["period"]["month"] == 10

    def test_get_monthly_usage_no_data(self, usage_tracker, mock_db):
        """Test getting monthly usage when no data exists."""
        mock_db.cursor.fetchall_results = [[]]

        result = usage_tracker.get_monthly_usage("openai", 2025, 10)

        assert result["engine"] == "openai"
        assert result["total_duration_seconds"] == 0.0
        assert result["total_cost"] == 0.0
        assert result["usage_count"] == 0

    def test_get_monthly_usage_all_engines(self, usage_tracker, mock_db):
        """Test getting monthly usage for all engines."""
        mock_db.cursor.fetchall_results = [
            [
                ("openai", 3600.0, 0.36, 10),
                ("google", 1800.0, 0.18, 5),
                ("azure", 900.0, 0.15, 3),
            ]
        ]

        result = usage_tracker.get_monthly_usage(None, 2025, 10)

        assert "engines" in result
        assert len(result["engines"]) == 3
        assert result["engines"]["openai"]["total_duration_seconds"] == 3600.0
        assert result["engines"]["google"]["total_duration_seconds"] == 1800.0
        assert result["engines"]["azure"]["total_duration_seconds"] == 900.0
        assert result["total_duration_seconds"] == 6300.0
        assert result["total_cost"] == pytest.approx(0.69, rel=1e-2)
        assert result["total_usage_count"] == 18

    def test_get_monthly_usage_default_period(self, usage_tracker, mock_db):
        """Test getting monthly usage with default period (current month)."""
        mock_db.cursor.fetchall_results = [[]]

        now = datetime.now()
        result = usage_tracker.get_monthly_usage("openai")

        assert result["period"]["year"] == now.year
        assert result["period"]["month"] == now.month

    def test_get_monthly_usage_december(self, usage_tracker, mock_db):
        """Test getting monthly usage for December (edge case)."""
        mock_db.cursor.fetchall_results = [[]]

        result = usage_tracker.get_monthly_usage("openai", 2025, 12)

        # Should query from Dec 1 to Jan 1 of next year
        call = mock_db.cursor.execute_calls[0]
        assert call["params"][1] == datetime(2025, 12, 1)
        assert call["params"][2] == datetime(2026, 1, 1)


class TestUsageHistory:
    """Test usage history retrieval."""

    def test_get_usage_history_basic(self, usage_tracker, mock_db):
        """Test getting usage history."""
        now = datetime.now()
        mock_db.cursor.fetchall_results = [
            [
                ("id1", "openai", 60.0, 0.006, now),
                ("id2", "google", 120.0, 0.012, now - timedelta(hours=1)),
            ]
        ]

        history = usage_tracker.get_usage_history()

        assert len(history) == 2
        assert history[0]["id"] == "id1"
        assert history[0]["engine"] == "openai"
        assert history[0]["duration_seconds"] == 60.0
        assert history[0]["duration_minutes"] == 1.0
        assert history[0]["cost"] == 0.006

    def test_get_usage_history_filtered_by_engine(self, usage_tracker, mock_db):
        """Test getting usage history filtered by engine."""
        now = datetime.now()
        mock_db.cursor.fetchall_results = [[("id1", "openai", 60.0, 0.006, now)]]

        history = usage_tracker.get_usage_history("openai")

        assert len(history) == 1
        assert history[0]["engine"] == "openai"

        # Check query parameters
        call = mock_db.cursor.execute_calls[0]
        assert call["params"][0] == "openai"

    def test_get_usage_history_custom_days(self, usage_tracker, mock_db):
        """Test getting usage history with custom days parameter."""
        mock_db.cursor.fetchall_results = [[]]

        usage_tracker.get_usage_history(days=7)

        # Should query last 7 days
        call = mock_db.cursor.execute_calls[0]
        start_date = call["params"][0] if len(call["params"]) > 1 else call["params"][0]
        expected_start = datetime.now() - timedelta(days=7)
        # Allow 1 second tolerance
        assert abs((start_date - expected_start).total_seconds()) < 1

    def test_get_usage_history_custom_limit(self, usage_tracker, mock_db):
        """Test getting usage history with custom limit."""
        mock_db.cursor.fetchall_results = [[]]

        usage_tracker.get_usage_history(limit=50)

        call = mock_db.cursor.execute_calls[0]
        # Limit should be last parameter
        assert call["params"][-1] == 50

    def test_get_usage_history_empty(self, usage_tracker, mock_db):
        """Test getting usage history when no records exist."""
        mock_db.cursor.fetchall_results = [[]]

        history = usage_tracker.get_usage_history()

        assert history == []


class TestInternalMethods:
    """Test internal calculation methods."""

    def test_calculate_cost_internal(self, usage_tracker):
        """Test internal cost calculation method."""
        cost = usage_tracker._calculate_cost_internal("openai", Decimal("1.0"))
        assert cost == Decimal("0.0060")

    def test_calculate_cost_internal_precision(self, usage_tracker):
        """Test that internal calculation maintains precision."""
        # Test with value that would have floating point issues
        cost = usage_tracker._calculate_cost_internal("openai", Decimal("1.5"))
        assert cost == Decimal("0.0090")

    def test_calculate_cost_internal_rounding(self, usage_tracker):
        """Test that cost is rounded to 4 decimal places."""
        # 1/3 minute should round properly
        cost = usage_tracker._calculate_cost_internal("openai", Decimal("0.333333"))
        assert cost == Decimal("0.0020")


class TestPricingConstants:
    """Test pricing constants."""

    def test_pricing_values(self):
        """Test that pricing values are correct."""
        assert UsageTracker.PRICING["openai"] == Decimal("0.006")
        assert UsageTracker.PRICING["google"] == Decimal("0.006")
        assert UsageTracker.PRICING["azure"] == Decimal("0.0167")

    def test_pricing_all_engines(self):
        """Test that all expected engines have pricing."""
        expected_engines = ["openai", "google", "azure"]
        for engine in expected_engines:
            assert engine in UsageTracker.PRICING
            assert isinstance(UsageTracker.PRICING[engine], Decimal)
