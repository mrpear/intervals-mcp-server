"""
Unit tests for baseline calculation and outlier filtering.
"""

import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
os.environ.setdefault("API_KEY", "test")
os.environ.setdefault("ATHLETE_ID", "i1")

from intervals_mcp_server.analytics.baselines import (  # pylint: disable=wrong-import-position
    calculate_baseline,
    filter_outliers,
)


def test_filter_outliers_removes_extreme_values():
    """Test outlier detection removes extreme values."""
    # HRV values with one extreme outlier
    values = [40.0, 42.0, 38.0, 255.0, 45.0, 47.0, 40.0]
    filtered = filter_outliers(values, threshold=3.0)

    # 255 should be removed as it's >3 SD from median
    assert 255.0 not in filtered
    assert len(filtered) == 6
    assert all(v < 100 for v in filtered)


def test_filter_outliers_preserves_normal_variation():
    """Test outlier detection preserves normal variation."""
    # Normal HRV variation without outliers
    values = [40.0, 42.0, 38.0, 45.0, 47.0, 40.0, 43.0]
    filtered = filter_outliers(values, threshold=3.0)

    # All values should be preserved
    assert len(filtered) == len(values)
    assert set(filtered) == set(values)


def test_filter_outliers_handles_small_sample():
    """Test outlier filtering with small sample (<3 values)."""
    values = [40.0, 255.0]  # Only 2 values
    filtered = filter_outliers(values, threshold=3.0)

    # Should return all values unchanged when sample is too small
    assert len(filtered) == 2
    assert filtered == values


def test_calculate_baseline_excludes_today():
    """Test 7-day baseline excludes today."""
    wellness_data = [
        {"id": "2026-02-14", "hrv": 47.0, "restingHR": 52.0},
        {"id": "2026-02-15", "hrv": 38.0, "restingHR": 58.0},
        {"id": "2026-02-16", "hrv": 42.0, "restingHR": 58.0},
        {"id": "2026-02-17", "hrv": 42.0, "restingHR": 55.0},
        {"id": "2026-02-18", "hrv": 40.0, "restingHR": 62.0},
        {"id": "2026-02-19", "hrv": 255.0, "restingHR": 63.0},  # Outlier
        {"id": "2026-02-20", "hrv": 45.0, "restingHR": 53.0},
        {"id": "2026-02-21", "hrv": 40.0, "restingHR": 62.0},  # Today
    ]

    # Calculate baseline excluding today (2026-02-21)
    hrv_baseline = calculate_baseline(
        wellness_data,
        "hrv",
        baseline_days=7,
        end_date="2026-02-21",
        filter_outliers_enabled=True
    )
    rhr_baseline = calculate_baseline(
        wellness_data,
        "restingHR",
        baseline_days=7,
        end_date="2026-02-21",
        filter_outliers_enabled=True
    )

    # Should exclude today (40) and outlier (255)
    # HRV: (47 + 38 + 42 + 42 + 40 + 45) / 6 = 42.33 (255 filtered as outlier)
    assert abs(hrv_baseline - 42.33) < 0.1

    # RHR: (52 + 58 + 58 + 55 + 62 + 63 + 53) / 7 = 57.29 (no outliers)
    assert abs(rhr_baseline - 57.29) < 0.1


def test_calculate_baseline_without_outlier_filtering():
    """Test baseline calculation with outlier filtering disabled."""
    wellness_data = [
        {"id": "2026-02-19", "hrv": 255.0},
        {"id": "2026-02-20", "hrv": 45.0},
        {"id": "2026-02-21", "hrv": 40.0},  # Today
    ]

    # Calculate baseline excluding today but WITHOUT outlier filtering
    hrv_baseline = calculate_baseline(
        wellness_data,
        "hrv",
        baseline_days=7,
        end_date="2026-02-21",
        filter_outliers_enabled=False
    )

    # Should include outlier: (255 + 45) / 2 = 150.0
    assert abs(hrv_baseline - 150.0) < 0.1


def test_calculate_baseline_with_empty_data():
    """Test baseline calculation with empty data."""
    baseline = calculate_baseline([], "hrv", baseline_days=7)
    assert baseline == 0.0


def test_calculate_baseline_with_missing_field():
    """Test baseline calculation when field is missing from some entries."""
    wellness_data = [
        {"id": "2026-02-19", "hrv": 45.0},
        {"id": "2026-02-20"},  # Missing hrv field
        {"id": "2026-02-21", "hrv": 40.0},
    ]

    baseline = calculate_baseline(
        wellness_data,
        "hrv",
        baseline_days=7,
        end_date="2026-02-21"
    )

    # Should only use entry with hrv: 45.0 / 1 = 45.0
    assert abs(baseline - 45.0) < 0.1


def test_calculate_baseline_with_none_values():
    """Test baseline calculation filters out None values."""
    wellness_data = [
        {"id": "2026-02-19", "hrv": 45.0},
        {"id": "2026-02-20", "hrv": None},
        {"id": "2026-02-21", "hrv": 40.0},
    ]

    baseline = calculate_baseline(
        wellness_data,
        "hrv",
        baseline_days=7,
        end_date="2026-02-21"
    )

    # Should only use non-None value: 45.0
    assert abs(baseline - 45.0) < 0.1


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-v"]))
