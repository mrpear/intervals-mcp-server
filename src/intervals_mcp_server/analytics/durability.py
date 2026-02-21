"""Aerobic durability and efficiency analysis metrics."""

from typing import Any


def calculate_efficiency_factor(
    normalized_power: float,
    average_hr: float
) -> float:
    """Calculate Efficiency Factor (EF).

    EF = Normalized Power / Average HR

    Higher is better. Tracks aerobic efficiency trends.

    Args:
        normalized_power: Normalized Power (NP) in watts
        average_hr: Average heart rate in bpm

    Returns:
        Efficiency Factor value
    """
    if average_hr == 0:
        return 0.0

    return normalized_power / average_hr


def interpret_efficiency_factor(ef: float, previous_ef: float | None = None) -> str:
    """Interpret Efficiency Factor value.

    Args:
        ef: Current EF value
        previous_ef: Previous EF for comparison (optional)

    Returns:
        Interpretation string
    """
    if previous_ef is not None and previous_ef > 0:
        change_pct = ((ef - previous_ef) / previous_ef) * 100
        if change_pct >= 5:
            return f"Improved (+{change_pct:.1f}%)"
        elif change_pct <= -5:
            return f"Declined ({change_pct:.1f}%)"
        else:
            return f"Stable ({change_pct:+.1f}%)"
    else:
        # Rough guidelines (very athlete-specific)
        if ef >= 2.0:
            return "Strong aerobic efficiency"
        elif ef >= 1.5:
            return "Good aerobic efficiency"
        else:
            return "Building aerobic base"


def calculate_decoupling(
    power_stream: list[float],
    hr_stream: list[float]
) -> tuple[float, float, float]:
    """Calculate Pw:HR decoupling for aerobic durability assessment.

    Decoupling = ((Second_half_ratio - First_half_ratio) / First_half_ratio) × 100

    Target: < 5% (good aerobic durability)

    Args:
        power_stream: Time-series power data in watts
        hr_stream: Time-series heart rate data in bpm

    Returns:
        Tuple of (decoupling_pct, first_half_ratio, second_half_ratio)
    """
    if not power_stream or not hr_stream:
        return 0.0, 0.0, 0.0

    if len(power_stream) != len(hr_stream):
        return 0.0, 0.0, 0.0

    # Minimum duration: 60 minutes (3600 samples at 1Hz)
    if len(power_stream) < 3600:
        return 0.0, 0.0, 0.0

    # Split into halves
    midpoint = len(power_stream) // 2
    first_half_power = power_stream[:midpoint]
    first_half_hr = hr_stream[:midpoint]
    second_half_power = power_stream[midpoint:]
    second_half_hr = hr_stream[midpoint:]

    # Calculate average Pw:HR ratios (filter out zeros)
    first_half_ratio = _calculate_average_pw_hr_ratio(first_half_power, first_half_hr)
    second_half_ratio = _calculate_average_pw_hr_ratio(second_half_power, second_half_hr)

    if first_half_ratio == 0:
        return 0.0, 0.0, 0.0

    # Calculate decoupling percentage
    decoupling_pct = ((second_half_ratio - first_half_ratio) / first_half_ratio) * 100

    return decoupling_pct, first_half_ratio, second_half_ratio


def _calculate_average_pw_hr_ratio(power_data: list[float], hr_data: list[float]) -> float:
    """Calculate average Pw:HR ratio from stream data.

    Args:
        power_data: Power values
        hr_data: HR values

    Returns:
        Average Pw:HR ratio
    """
    ratios = []
    for power, hr in zip(power_data, hr_data, strict=False):
        if power > 0 and hr > 0:
            ratios.append(power / hr)

    if not ratios:
        return 0.0

    return sum(ratios) / len(ratios)


def interpret_decoupling(decoupling_pct: float) -> str:
    """Interpret Pw:HR decoupling percentage.

    Note: Negative decoupling means Pw:HR ratio decreased (HR drifted up).
    This is normal fatigue. We report absolute value for clarity.

    Args:
        decoupling_pct: Decoupling percentage

    Returns:
        Interpretation string
    """
    # Use absolute value - negative just means ratio decreased (normal fatigue)
    abs_decoupling = abs(decoupling_pct)

    if abs_decoupling < 5:
        return "Excellent aerobic durability"
    elif abs_decoupling < 10:
        return "Good aerobic durability"
    else:
        return "Poor aerobic durability - build aerobic base"


def calculate_variability_index(
    normalized_power: float,
    average_power: float
) -> float:
    """Calculate Variability Index (VI).

    VI = NP / Average Power

    Target: < 1.05 for steady-state rides

    Args:
        normalized_power: Normalized Power in watts
        average_power: Average power in watts

    Returns:
        Variability Index value
    """
    if average_power == 0:
        return 0.0

    return normalized_power / average_power


def interpret_variability_index(vi: float) -> str:
    """Interpret Variability Index value.

    Args:
        vi: Variability Index value

    Returns:
        Interpretation string
    """
    if vi < 1.05:
        return "Very steady effort"
    elif vi < 1.10:
        return "Moderately steady effort"
    else:
        return "Variable effort"


def calculate_aggregate_durability(
    activities: list[dict[str, Any]],
    min_duration_minutes: int = 60,
) -> dict[str, Any]:
    """Calculate aggregate durability metrics across multiple activities.

    Aggregates decoupling data from activities that meet minimum duration
    requirements to assess overall aerobic durability.

    Args:
        activities: List of activity dictionaries with decoupling data
        min_duration_minutes: Minimum activity duration to include (default: 60 min)

    Returns:
        Dictionary with aggregate durability metrics:
        - mean_decoupling: Average decoupling across qualifying activities
        - activities_analyzed: Number of activities included
        - interpretation: Overall durability assessment
    """
    decoupling_values = []

    for activity in activities:
        # Check if activity has required data
        moving_time = activity.get("moving_time", 0)
        duration_minutes = moving_time / 60 if moving_time else 0

        # Skip activities that are too short
        if duration_minutes < min_duration_minutes:
            continue

        # Check if decoupling data exists (Intervals.icu uses 'decoupling' field)
        decoupling = activity.get("decoupling") or activity.get("pw_hr_decoupling")
        if decoupling is not None:
            decoupling_values.append(abs(decoupling))  # Use absolute value

    if not decoupling_values:
        return {
            "mean_decoupling": None,
            "activities_analyzed": 0,
            "interpretation": "Insufficient data for durability assessment",
        }

    mean_decoupling = sum(decoupling_values) / len(decoupling_values)

    # Interpret aggregate durability
    if mean_decoupling < 5:
        interpretation = "Excellent aerobic durability"
    elif mean_decoupling < 10:
        interpretation = "Good aerobic durability"
    else:
        interpretation = "Poor aerobic durability - focus on base building"

    return {
        "mean_decoupling": round(mean_decoupling, 1),
        "activities_analyzed": len(decoupling_values),
        "interpretation": interpretation,
    }
