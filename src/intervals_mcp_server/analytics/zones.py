"""Training zone distribution analysis metrics."""

from typing import Any


def aggregate_zone_times(activities: list[dict[str, Any]], zone_type: str = "power") -> dict[int, int]:
    """Aggregate time in zones across multiple activities.

    Handles both Intervals.icu zone formats:
    - Power: icu_zone_times array with {"id": "Z1", "secs": 123}
    - HR: icu_hr_zone_times array [secs_z1, secs_z2, ...]

    Args:
        activities: List of activity objects with zone data
        zone_type: "power" or "hr" zones to analyze

    Returns:
        Dictionary mapping zone number to total seconds
    """
    zone_totals: dict[int, int] = {}

    for activity in activities:
        if zone_type == "power":
            # Power zones: icu_zone_times array
            zone_times = activity.get("icu_zone_times", [])
            for zone in zone_times:
                if isinstance(zone, dict):
                    zone_id = zone.get("id", "")
                    seconds = zone.get("secs", 0)
                    # Extract zone number from "Z1", "Z2", etc.
                    if zone_id.startswith("Z") and seconds > 0:
                        try:
                            zone_num = int(zone_id[1:])
                            zone_totals[zone_num] = zone_totals.get(zone_num, 0) + seconds
                        except (ValueError, IndexError):
                            pass
        elif zone_type == "hr":
            # HR zones: icu_hr_zone_times simple array [z1, z2, z3, ...]
            zone_times = activity.get("icu_hr_zone_times", [])
            if isinstance(zone_times, list):
                for zone_num, seconds in enumerate(zone_times, start=1):
                    if seconds > 0:
                        zone_totals[zone_num] = zone_totals.get(zone_num, 0) + seconds

    return zone_totals


def calculate_polarization_index(zone_times: dict[int, int]) -> float:
    """Calculate Polarization Index using 3-zone model.

    PI = (Z1_time + Z3_time) / Z2_time

    3-Zone Model:
    - Z1 (Easy): Zones 1-2 (recovery/endurance)
    - Z2 (Threshold): Zones 3-4 (tempo/threshold)
    - Z3 (High): Zones 5-7 (VO2max/anaerobic)

    Target: > 2.0 (polarized training)

    Args:
        zone_times: Dictionary mapping zone number to seconds

    Returns:
        Polarization index value
    """
    # Aggregate into 3-zone model
    z1_time = zone_times.get(1, 0) + zone_times.get(2, 0)
    z2_time = zone_times.get(3, 0) + zone_times.get(4, 0)
    z3_time = zone_times.get(5, 0) + zone_times.get(6, 0) + zone_times.get(7, 0)

    if z2_time == 0:
        return 0.0

    return (z1_time + z3_time) / z2_time


def interpret_polarization_index(pi: float) -> str:
    """Interpret Polarization Index value.

    Args:
        pi: Polarization index value

    Returns:
        Interpretation string
    """
    if pi >= 3.0:
        return "Highly polarized"
    elif pi >= 2.0:
        return "Polarized (optimal)"
    elif pi >= 1.0:
        return "Pyramidal"
    else:
        return "Threshold-heavy"


def calculate_zone_percentages(zone_times: dict[int, int]) -> dict[int, float]:
    """Calculate percentage of time in each zone.

    Args:
        zone_times: Dictionary mapping zone number to seconds

    Returns:
        Dictionary mapping zone number to percentage (0-100)
    """
    total_time = sum(zone_times.values())

    if total_time == 0:
        return {}

    return {
        zone: (seconds / total_time) * 100
        for zone, seconds in zone_times.items()
    }


def calculate_3zone_distribution(zone_times: dict[int, int]) -> dict[str, float]:
    """Calculate distribution in 3-zone polarization model.

    Args:
        zone_times: Dictionary mapping zone number to seconds

    Returns:
        Dictionary with Z1, Z2, Z3 percentages
    """
    z1_time = zone_times.get(1, 0) + zone_times.get(2, 0)
    z2_time = zone_times.get(3, 0) + zone_times.get(4, 0)
    z3_time = zone_times.get(5, 0) + zone_times.get(6, 0) + zone_times.get(7, 0)

    total_time = z1_time + z2_time + z3_time

    if total_time == 0:
        return {"Z1": 0.0, "Z2": 0.0, "Z3": 0.0}

    return {
        "Z1": (z1_time / total_time) * 100,
        "Z2": (z2_time / total_time) * 100,
        "Z3": (z3_time / total_time) * 100,
    }


def interpret_zone_distribution(dist: dict[str, float]) -> str:
    """Interpret zone distribution pattern.

    Args:
        dist: Distribution with Z1, Z2, Z3 percentages

    Returns:
        Interpretation string
    """
    z1 = dist.get("Z1", 0)
    z2 = dist.get("Z2", 0)
    z3 = dist.get("Z3", 0)

    # Polarized: ~80% Z1, ~5% Z2, ~15% Z3
    if z1 >= 70 and z3 >= 10 and z2 <= 20:
        return "Polarized (80/20 model)"
    # Pyramidal: Z1 > Z2 > Z3
    elif z1 > z2 > z3:
        return "Pyramidal (traditional)"
    # Threshold: High Z2
    elif z2 >= 30:
        return "Threshold-focused"
    else:
        return "Mixed distribution"