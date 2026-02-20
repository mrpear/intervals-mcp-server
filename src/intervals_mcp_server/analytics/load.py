"""Training load analysis metrics."""

import statistics
from typing import Any


def calculate_monotony(daily_loads: list[float]) -> float:
    """Calculate training monotony.

    Monotony = Mean(daily_load) / StdDev(daily_load)

    Target: < 2.5
      Flag at: 2.3
      Alarm at: 2.5

    Args:
        daily_loads: List of daily training load values (TSS)

    Returns:
        Monotony value
    """
    if len(daily_loads) < 2:
        return 0.0

    # Filter out zero/None values
    loads = [load for load in daily_loads if load and load > 0]

    if len(loads) < 2:
        return 0.0

    mean_load = statistics.mean(loads)
    std_dev = statistics.stdev(loads)

    if std_dev == 0:
        return 0.0

    return mean_load / std_dev


def calculate_strain(monotony: float, mean_load: float) -> float:
    """Calculate training strain.

    Strain = Monotony × Mean(daily_load)

    Alarm threshold: > 3500

    Args:
        monotony: Monotony value
        mean_load: Mean daily load

    Returns:
        Strain value
    """
    return monotony * mean_load


def interpret_monotony(monotony: float) -> str:
    """Interpret monotony value.

    Args:
        monotony: Monotony value

    Returns:
        Interpretation string
    """
    if monotony < 2.3:
        return "Good variety"
    elif monotony < 2.5:
        return "Approaching limit"
    else:
        return "Excessive monotony"


def interpret_strain(strain: float) -> str:
    """Interpret strain value.

    Args:
        strain: Strain value

    Returns:
        Interpretation string
    """
    if strain < 3500:
        return "Manageable load"
    else:
        return "High strain risk"


def calculate_load_recovery_ratio(
    weekly_load: float,
    recovery_index: float
) -> float:
    """Calculate Load-Recovery Ratio.

    Ratio = Weekly_load / Recovery_Index

    Target: < 2.5

    Args:
        weekly_load: 7-day total load (TSS)
        recovery_index: Current RI value

    Returns:
        Load-Recovery ratio
    """
    if recovery_index == 0:
        return 0.0

    return weekly_load / recovery_index


def interpret_load_recovery_ratio(ratio: float) -> str:
    """Interpret Load-Recovery ratio.

    Args:
        ratio: Load-Recovery ratio value

    Returns:
        Interpretation string
    """
    if ratio < 2.5:
        return "Load appropriate for recovery"
    else:
        return "Load too high for recovery state"


def calculate_consistency_index(
    sessions_completed: int,
    sessions_planned: int
) -> float:
    """Calculate Consistency Index.

    Index = Sessions_completed / Sessions_planned

    Target: ≥ 0.9

    Args:
        sessions_completed: Number of completed sessions
        sessions_planned: Number of planned sessions

    Returns:
        Consistency index (0-1)
    """
    if sessions_planned == 0:
        return 0.0

    return sessions_completed / sessions_planned


def interpret_consistency_index(index: float) -> str:
    """Interpret Consistency Index.

    Args:
        index: Consistency index value

    Returns:
        Interpretation string
    """
    if index >= 0.9:
        return "Excellent adherence"
    elif index >= 0.75:
        return "Good adherence"
    elif index >= 0.5:
        return "Moderate adherence"
    else:
        return "Poor adherence"