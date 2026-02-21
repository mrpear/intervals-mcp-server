"""Training Intensity Distribution (TID) drift detection."""

from typing import Any


def detect_tid_drift(
    tid_7d: dict[str, float],
    tid_28d: dict[str, float],
    threshold_pct: float = 15.0,
) -> str:
    """Detect drift in Training Intensity Distribution.

    Compares 7-day TID with 28-day TID to identify acute changes
    in training intensity distribution.

    Classifications:
    - "consistent": 7d TID matches 28d pattern (within threshold)
    - "shifting": Moderate drift detected
    - "acute_depolarization": Significant increase in Z2 intensity

    Args:
        tid_7d: 7-day TID percentages {Z1: %, Z2: %, Z3: %}
        tid_28d: 28-day TID percentages {Z1: %, Z2: %, Z3: %}
        threshold_pct: Percentage threshold for detecting drift (default: 15%)

    Returns:
        Drift classification string
    """
    if not tid_7d or not tid_28d:
        return "insufficient_data"

    # Calculate absolute differences
    z1_diff = abs(tid_7d.get("Z1", 0) - tid_28d.get("Z1", 0))
    z2_diff = tid_7d.get("Z2", 0) - tid_28d.get("Z2", 0)  # Signed for depolarization check
    z3_diff = abs(tid_7d.get("Z3", 0) - tid_28d.get("Z3", 0))

    # Check for acute depolarization (Z2 significantly higher in 7d)
    if z2_diff > threshold_pct:
        return "acute_depolarization"

    # Check for general drift (any zone differs significantly)
    max_diff = max(z1_diff, abs(z2_diff), z3_diff)
    if max_diff > threshold_pct:
        return "shifting"

    return "consistent"


def interpret_tid_drift(drift_classification: str) -> str:
    """Interpret TID drift classification.

    Args:
        drift_classification: Drift classification string

    Returns:
        Interpretation string
    """
    interpretations = {
        "consistent": "Training intensity distribution is consistent with recent trends",
        "shifting": "Training intensity distribution is shifting - monitor pattern",
        "acute_depolarization": "Recent week shows increased threshold work - ensure adequate recovery",
        "insufficient_data": "Not enough data to assess TID drift",
    }
    return interpretations.get(drift_classification, "Unknown drift pattern")


def calculate_tid_comparison(
    tid_7d: dict[str, float],
    tid_28d: dict[str, float],
) -> dict[str, Any]:
    """Calculate detailed TID comparison metrics.

    Args:
        tid_7d: 7-day TID percentages
        tid_28d: 28-day TID percentages

    Returns:
        Dictionary with comparison details
    """
    if not tid_7d or not tid_28d:
        return {
            "drift_classification": "insufficient_data",
            "interpretation": "Not enough data to assess TID drift",
            "zone_differences": {},
        }

    # Calculate differences for each zone
    zone_diffs = {
        "Z1": tid_7d.get("Z1", 0) - tid_28d.get("Z1", 0),
        "Z2": tid_7d.get("Z2", 0) - tid_28d.get("Z2", 0),
        "Z3": tid_7d.get("Z3", 0) - tid_28d.get("Z3", 0),
    }

    # Detect drift
    drift_classification = detect_tid_drift(tid_7d, tid_28d)
    interpretation = interpret_tid_drift(drift_classification)

    return {
        "drift_classification": drift_classification,
        "interpretation": interpretation,
        "zone_differences": zone_diffs,
        "tid_7d": tid_7d,
        "tid_28d": tid_28d,
    }
