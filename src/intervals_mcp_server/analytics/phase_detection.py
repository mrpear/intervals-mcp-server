"""Training phase detection logic."""

from typing import Any


def detect_training_phase(
    ctl: float,
    atl: float,
    tsb: float,
    ctl_7d_ago: float | None = None,
    recent_load_trend: str | None = None,
) -> str:
    """Detect current training phase based on CTL, ATL, TSB metrics.

    Phases:
    - Base: Low-moderate CTL, building aerobic base
    - Build: Rising CTL, moderate TSB
    - Peak: High CTL, moderate-high ATL
    - Taper: Declining ATL, rising TSB
    - Recovery: Very low load, high TSB

    Args:
        ctl: Current Chronic Training Load (28-42 day)
        atl: Current Acute Training Load (7-day)
        tsb: Current Training Stress Balance (CTL - ATL)
        ctl_7d_ago: CTL from 7 days ago (optional, for trend detection)
        recent_load_trend: Trend in recent load ("increasing", "stable", "decreasing")

    Returns:
        Detected training phase
    """
    # Calculate ACWR for phase context
    acwr = atl / ctl if ctl > 0 else 0.0

    # Calculate CTL trend if we have historical data
    ctl_trend = None
    if ctl_7d_ago is not None and ctl_7d_ago > 0:
        ctl_change_pct = ((ctl - ctl_7d_ago) / ctl_7d_ago) * 100
        if ctl_change_pct > 5:
            ctl_trend = "increasing"
        elif ctl_change_pct < -5:
            ctl_trend = "decreasing"
        else:
            ctl_trend = "stable"

    # Recovery phase: Very high TSB, low recent load
    if tsb > 15 and acwr < 0.7:
        return "Recovery"

    # Taper phase: Declining ATL, rising TSB, stable/decreasing CTL
    if tsb > 5 and acwr < 0.8 and (ctl_trend == "decreasing" or ctl_trend == "stable"):
        return "Taper"

    # Peak phase: High CTL, high ATL, moderate TSB
    if ctl > 80 and acwr > 0.9 and -10 < tsb < 5:
        return "Peak"

    # Build phase: Rising CTL, moderate ACWR, low-moderate TSB
    if ctl_trend == "increasing" and 0.8 <= acwr <= 1.2:
        return "Build"

    # Base phase: Low-moderate CTL, building foundation
    if ctl < 60:
        return "Base"

    # Default to Build if we can't clearly identify
    return "Build"


def interpret_training_phase(phase: str) -> str:
    """Interpret training phase and provide guidance.

    Args:
        phase: Training phase name

    Returns:
        Interpretation string with guidance
    """
    interpretations = {
        "Base": "Building aerobic foundation - focus on volume at low intensity",
        "Build": "Building fitness - structured intervals and progressive overload",
        "Peak": "Peak fitness - maintain intensity, manage fatigue carefully",
        "Taper": "Pre-event taper - reducing load while maintaining intensity",
        "Recovery": "Recovery period - prioritize rest and adaptation",
    }
    return interpretations.get(phase, "Unknown phase")


def calculate_phase_progression(
    current_phase: str,
    weeks_in_phase: int,
) -> dict[str, Any]:
    """Calculate progression through current training phase.

    Args:
        current_phase: Current training phase
        weeks_in_phase: Number of weeks in current phase

    Returns:
        Dictionary with phase progression details
    """
    # Typical phase durations (in weeks)
    phase_durations = {
        "Base": (4, 12),  # (min, max)
        "Build": (4, 8),
        "Peak": (1, 3),
        "Taper": (1, 2),
        "Recovery": (1, 2),
    }

    min_weeks, max_weeks = phase_durations.get(current_phase, (4, 8))

    # Calculate progression percentage
    if weeks_in_phase < min_weeks:
        progress_pct = (weeks_in_phase / min_weeks) * 50  # 0-50% during minimum period
        status = "Early"
    elif weeks_in_phase <= max_weeks:
        # 50-100% during min to max period
        progress_in_range = weeks_in_phase - min_weeks
        range_size = max_weeks - min_weeks
        progress_pct = 50 + (progress_in_range / range_size) * 50 if range_size > 0 else 75
        status = "Mid"
    else:
        progress_pct = 100
        status = "Extended"

    return {
        "phase": current_phase,
        "weeks_in_phase": weeks_in_phase,
        "progress_pct": round(progress_pct, 1),
        "status": status,
        "min_duration_weeks": min_weeks,
        "max_duration_weeks": max_weeks,
    }