"""Baseline and rolling window calculations."""

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


def calculate_baseline(
    data: list[dict[str, Any]],
    field: str,
    baseline_days: int = 7,
    end_date: str | None = None
) -> float:
    """Calculate baseline (average) for a field over baseline_days.

    Args:
        data: List of data points with 'id' (date) field
        field: Field name to baseline
        baseline_days: Number of days for baseline period
        end_date: End date for baseline calculation (default: most recent)

    Returns:
        Baseline average value
    """
    if not data:
        return 0.0

    # If end_date specified, filter data up to that date
    if end_date:
        data = [
            item for item in data
            if item.get('id', '') <= end_date
        ]

    return calculate_rolling_average(data, field, baseline_days)