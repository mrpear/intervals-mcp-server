"""Baseline and rolling window calculations."""

import statistics
from typing import Any


def calculate_rolling_average(
    data: list[dict[str, Any]],
    field: str,
    window_days: int = 7
) -> float:
    """Calculate rolling average for a field over window_days.

    Args:
        data: List of data points with 'id' (date) field
        field: Field name to average
        window_days: Number of days to include in window

    Returns:
        Rolling average value
    """
    if not data:
        return 0.0

    # Sort by date descending (most recent first)
    sorted_data = sorted(
        data,
        key=lambda x: x.get('id', ''),
        reverse=True
    )

    # Take most recent window_days entries
    window_data = sorted_data[:window_days]

    # Extract values, filter out None
    values = [
        item[field]
        for item in window_data
        if field in item and item[field] is not None
    ]

    if not values:
        return 0.0

    return sum(values) / len(values)


def filter_outliers(values: list[float], threshold: float = 3.0) -> list[float]:
    """Remove outliers using Median Absolute Deviation (MAD).

    MAD is more robust to outliers than standard deviation.

    Args:
        values: List of numeric values
        threshold: MAD threshold multiplier (default: 3.0)

    Returns:
        List with outliers removed
    """
    if len(values) < 3:
        return values

    median = statistics.median(values)

    # Calculate Median Absolute Deviation (MAD)
    abs_deviations = [abs(v - median) for v in values]
    mad = statistics.median(abs_deviations)

    # If MAD is 0, use a simple threshold based on median
    if mad == 0:
        # Fall back to filtering values more than 3x the median away
        return [v for v in values if abs(v - median) <= threshold * median]

    # Modified Z-score using MAD (more robust than standard deviation)
    # Scaling factor 1.4826 makes MAD consistent with standard deviation for normal distribution
    mad_scaled = mad * 1.4826

    return [v for v in values if abs(v - median) / mad_scaled <= threshold]


def calculate_baseline(
    data: list[dict[str, Any]],
    field: str,
    baseline_days: int = 7,
    end_date: str | None = None,
    filter_outliers_enabled: bool = True,
) -> float:
    """Calculate baseline (average) for a field over baseline_days.

    Args:
        data: List of data points with 'id' (date) field
        field: Field name to baseline
        baseline_days: Number of days for baseline period
        end_date: End date for baseline calculation (default: most recent)
        filter_outliers_enabled: If True, remove outliers before averaging (default: True)

    Returns:
        Baseline average value (with outliers filtered if enabled)
    """
    if not data:
        return 0.0

    # If end_date specified, filter data up to that date (exclude end_date itself)
    if end_date:
        data = [
            item for item in data
            if item.get('id', '') < end_date  # Changed from <= to < to exclude today
        ]

    # Sort by date descending (most recent first)
    sorted_data = sorted(
        data,
        key=lambda x: x.get('id', ''),
        reverse=True
    )

    # Take most recent baseline_days entries
    window_data = sorted_data[:baseline_days]

    # Extract values, filter out None
    values = [
        float(item[field])
        for item in window_data
        if field in item and item[field] is not None
    ]

    if not values:
        return 0.0

    # Filter outliers if enabled
    if filter_outliers_enabled and len(values) >= 3:
        values = filter_outliers(values, threshold=3.0)

    if not values:
        return 0.0

    return sum(values) / len(values)