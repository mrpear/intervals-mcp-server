"""Recovery and readiness metrics."""


def calculate_recovery_index(
    hrv_today: float,
    hrv_baseline: float,
    rhr_today: float,
    rhr_baseline: float
) -> float:
    """Calculate Recovery Index (RI).

    RI = (HRV_today / HRV_baseline) / (RHR_today / RHR_baseline)

    Interpretation:
      ≥ 0.8    = Good readiness
      0.6-0.79 = Moderate fatigue
      < 0.6    = Deload required

    Args:
        hrv_today: Today's HRV value (ms)
        hrv_baseline: 7-day baseline HRV (ms)
        rhr_today: Today's resting HR (bpm)
        rhr_baseline: 7-day baseline RHR (bpm)

    Returns:
        Recovery Index value
    """
    if hrv_baseline == 0 or rhr_baseline == 0:
        return 0.0

    hrv_ratio = hrv_today / hrv_baseline
    rhr_ratio = rhr_today / rhr_baseline

    if rhr_ratio == 0:
        return 0.0

    return hrv_ratio / rhr_ratio


def interpret_recovery_index(ri: float) -> str:
    """Interpret Recovery Index value.

    Args:
        ri: Recovery Index value

    Returns:
        Interpretation string
    """
    if ri >= 0.8:
        return "Good readiness"
    elif ri >= 0.6:
        return "Moderate fatigue"
    else:
        return "Deload required"


def calculate_acwr(atl: float, ctl: float) -> float:
    """Calculate Acute:Chronic Workload Ratio.

    ACWR = ATL / CTL

    Target: 0.8-1.3
      Flag at: 0.8 / 1.3 edges
      Alarm: outside range

    Args:
        atl: Acute Training Load (7-day)
        ctl: Chronic Training Load (28-42 day)

    Returns:
        ACWR value
    """
    if ctl == 0:
        return 0.0

    return atl / ctl


def interpret_acwr(acwr: float) -> str:
    """Interpret ACWR value.

    Args:
        acwr: ACWR value

    Returns:
        Interpretation string
    """
    if acwr < 0.8:
        return "Under-training"
    elif acwr <= 1.3:
        return "Optimal range"
    else:
        return "Over-reaching risk"
