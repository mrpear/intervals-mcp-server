"""Snapshot generation logic for Section 11 data mirror format."""

import json
from datetime import datetime, timedelta
from typing import Any

from intervals_mcp_server.api.client import make_intervals_request
from intervals_mcp_server.analytics.recovery import (
    calculate_recovery_index,
    calculate_acwr,
)
from intervals_mcp_server.analytics.load import (
    calculate_monotony,
    calculate_strain,
)
from intervals_mcp_server.analytics.zones import (
    aggregate_zone_times,
    calculate_polarization_index,
    calculate_3zone_distribution,
)
from intervals_mcp_server.analytics.durability import (
    calculate_aggregate_durability,
)
from intervals_mcp_server.analytics.phase_detection import (
    detect_training_phase,
    interpret_training_phase,
)
from intervals_mcp_server.analytics.alerts import generate_alerts
from intervals_mcp_server.analytics.tid_drift import calculate_tid_comparison
from intervals_mcp_server.analytics.baselines import calculate_baseline


async def build_latest_snapshot(
    athlete_id: str,
    api_key: str | None = None,
    days: int = 7,
    extended_days: int = 28,
) -> dict[str, Any]:
    """Build latest snapshot with Section 11 metrics.

    Fetches data from Intervals.icu API and calculates derived metrics
    matching the Section 11 data mirror format.

    Args:
        athlete_id: Intervals.icu athlete ID
        api_key: API key for authentication
        days: Primary snapshot window (default: 7)
        extended_days: Extended window for ACWR/baselines (default: 28)

    Returns:
        Dictionary with complete snapshot data
    """
    today = datetime.now()
    date_str = today.strftime("%Y-%m-%d")
    start_date = (today - timedelta(days=extended_days)).strftime("%Y-%m-%d")
    start_date_7d = (today - timedelta(days=days)).strftime("%Y-%m-%d")

    # Fetch all required data in parallel
    activities_result = await make_intervals_request(
        url=f"/athlete/{athlete_id}/activities",
        api_key=api_key,
        params={"oldest": start_date, "newest": date_str},
    )

    wellness_result = await make_intervals_request(
        url=f"/athlete/{athlete_id}/wellness",
        api_key=api_key,
        params={"oldest": start_date, "newest": date_str},
    )

    events_result = await make_intervals_request(
        url=f"/athlete/{athlete_id}/events",
        api_key=api_key,
        params={"oldest": date_str, "newest": (today + timedelta(days=7)).strftime("%Y-%m-%d")},
    )

    # Handle errors
    if isinstance(activities_result, dict) and "error" in activities_result:
        return {"error": True, "message": f"Error fetching activities: {activities_result.get('message')}"}
    if isinstance(wellness_result, dict) and "error" in wellness_result:
        return {"error": True, "message": f"Error fetching wellness: {wellness_result.get('message')}"}

    # Convert wellness dict to list if needed
    wellness_data = []
    if isinstance(wellness_result, dict):
        wellness_data = [{"id": k, **v} for k, v in wellness_result.items()]
    elif isinstance(wellness_result, list):
        wellness_data = wellness_result

    # Convert activities to list if needed
    activities = activities_result if isinstance(activities_result, list) else []

    # Convert events to list if needed
    events = events_result if isinstance(events_result, list) else []

    # Filter activities for different windows
    activities_7d = [a for a in activities if a.get("start_date_local", "")[:10] >= start_date_7d]
    activities_28d = activities  # All activities from extended window

    # Get today's wellness data
    today_wellness = next(
        (item for item in wellness_data if item.get("id") == date_str),
        {}
    )

    # Calculate baseline data (7-day average excluding today)
    baseline_data = [item for item in wellness_data if item.get("id", "") < date_str]

    # Detect HRV field
    hrv_field = None
    for field in ["hrv", "hrvRMSSD", "hrvSDNN"]:
        if today_wellness.get(field) is not None:
            hrv_field = field
            break

    # Calculate derived metrics
    derived_metrics: dict[str, Any] = {}

    # Recovery Index
    if hrv_field and today_wellness.get(hrv_field) and today_wellness.get("restingHR"):
        # Calculate baselines excluding today
        hrv_baseline = calculate_baseline(wellness_data, hrv_field, baseline_days=7, end_date=date_str)
        rhr_baseline = calculate_baseline(wellness_data, "restingHR", baseline_days=7, end_date=date_str)

        # Only calculate RI if we have valid baselines (non-zero)
        if hrv_baseline and hrv_baseline > 0 and rhr_baseline and rhr_baseline > 0:
            try:
                ri = calculate_recovery_index(
                    today_wellness.get(hrv_field, 0),
                    hrv_baseline,
                    today_wellness.get("restingHR", 0),
                    rhr_baseline,
                )
                derived_metrics["recovery_index"] = round(ri, 2)
                derived_metrics["hrv_baseline"] = round(hrv_baseline, 1)
                derived_metrics["rhr_baseline"] = round(rhr_baseline, 1)
            except (ZeroDivisionError, TypeError) as e:
                # Log error but continue with snapshot generation
                derived_metrics["recovery_index"] = None
                derived_metrics["recovery_index_error"] = f"Calculation error: {str(e)}"

    # ACWR
    try:
        if today_wellness.get("atl") and today_wellness.get("ctl"):
            acwr = calculate_acwr(today_wellness["atl"], today_wellness["ctl"])
            derived_metrics["acwr"] = round(acwr, 2)
    except (ZeroDivisionError, TypeError) as e:
        derived_metrics["acwr"] = None
        derived_metrics["acwr_error"] = f"Calculation error: {str(e)}"

    # Monotony and Strain (7-day window)
    try:
        # Use 'or 0' to handle None values from wellness data
        daily_loads = [w.get("loadToday") or 0 for w in wellness_data if w.get("id", "") >= start_date_7d and w.get("id", "") <= date_str]
        if daily_loads:
            monotony = calculate_monotony(daily_loads)
            # Fix division by zero: check if there are any loads > 0 before dividing
            loads_above_zero = [l for l in daily_loads if l > 0]
            mean_load = sum(loads_above_zero) / len(loads_above_zero) if loads_above_zero else 0
            strain = calculate_strain(monotony, mean_load)
            derived_metrics["monotony"] = round(monotony, 2)
            derived_metrics["strain"] = round(strain, 1)
    except (ZeroDivisionError, TypeError) as e:
        derived_metrics["monotony"] = None
        derived_metrics["strain"] = None
        derived_metrics["load_metrics_error"] = f"Calculation error: {str(e)}"

    # Zone Distribution (7d and 28d)
    try:
        zone_times_7d = aggregate_zone_times(activities_7d, "power")
        zone_times_28d = aggregate_zone_times(activities_28d, "power")

        if zone_times_7d:
            pi_7d = calculate_polarization_index(zone_times_7d)
            tid_7d = calculate_3zone_distribution(zone_times_7d)
            derived_metrics["polarization_index_7d"] = round(pi_7d, 2)
            derived_metrics["seiler_tid_7d"] = {k: round(v, 1) for k, v in tid_7d.items()}

        if zone_times_28d:
            pi_28d = calculate_polarization_index(zone_times_28d)
            tid_28d = calculate_3zone_distribution(zone_times_28d)
            derived_metrics["polarization_index_28d"] = round(pi_28d, 2)
            derived_metrics["seiler_tid_28d"] = {k: round(v, 1) for k, v in tid_28d.items()}
    except (ZeroDivisionError, TypeError) as e:
        derived_metrics["zone_distribution_error"] = f"Calculation error: {str(e)}"

    # TID Drift
    try:
        if "seiler_tid_7d" in derived_metrics and "seiler_tid_28d" in derived_metrics:
            tid_comparison = calculate_tid_comparison(
                derived_metrics["seiler_tid_7d"],
                derived_metrics["seiler_tid_28d"],
            )
            derived_metrics["tid_drift"] = tid_comparison["drift_classification"]
            derived_metrics["tid_comparison"] = tid_comparison
    except (ZeroDivisionError, TypeError) as e:
        derived_metrics["tid_drift_error"] = f"Calculation error: {str(e)}"

    # Aggregate Durability
    try:
        durability_7d = calculate_aggregate_durability(activities_7d, min_duration_minutes=60)
        durability_28d = calculate_aggregate_durability(activities_28d, min_duration_minutes=60)

        derived_metrics["durability_7d"] = durability_7d
        derived_metrics["durability_28d"] = durability_28d
    except (ZeroDivisionError, TypeError) as e:
        derived_metrics["durability_error"] = f"Calculation error: {str(e)}"

    # Phase Detection
    try:
        if today_wellness.get("ctl") and today_wellness.get("atl") and today_wellness.get("tsb"):
            phase = detect_training_phase(
                ctl=today_wellness["ctl"],
                atl=today_wellness["atl"],
                tsb=today_wellness["tsb"],
            )
            derived_metrics["phase_detected"] = phase
            derived_metrics["phase_interpretation"] = interpret_training_phase(phase)
    except (ZeroDivisionError, TypeError) as e:
        derived_metrics["phase_detection_error"] = f"Calculation error: {str(e)}"

    # Generate Alerts
    alerts = generate_alerts(derived_metrics)

    # Build snapshot structure
    snapshot = {
        "READ_THIS_FIRST": {
            "description": "Section 11 Training Snapshot",
            "purpose": "Pre-calculated metrics for coaching decisions",
            "timestamp": datetime.now().isoformat(),
        },
        "metadata": {
            "athlete_id": athlete_id,
            "snapshot_date": date_str,
            "window_days": days,
            "extended_window_days": extended_days,
            "activities_count_7d": len(activities_7d),
            "activities_count_28d": len(activities_28d),
        },
        "alerts": alerts,
        "current_status": {
            "fitness": {
                "ctl": round(today_wellness.get("ctl", 0), 1),
                "atl": round(today_wellness.get("atl", 0), 1),
                "tsb": round(today_wellness.get("tsb", 0), 1),
            },
            "wellness": {
                "hrv": round(today_wellness.get(hrv_field, 0), 1) if hrv_field else None,
                "resting_hr": round(today_wellness.get("restingHR", 0), 0),
                "sleep_hours": round(today_wellness.get("sleepSecs", 0) / 3600, 1),
                "sleep_score": today_wellness.get("sleepScore", 0),
            },
        },
        "derived_metrics": derived_metrics,
        "recent_activities": [
            {
                "id": a.get("id"),
                "name": a.get("name"),
                "type": a.get("type"),
                "start_date": a.get("start_date_local"),
                "distance": a.get("distance"),
                "moving_time": a.get("moving_time"),
                "training_load": a.get("training_load"),
            }
            for a in activities_7d[:10]  # Last 10 activities
        ],
        "wellness_data": [
            {
                "date": w.get("id"),
                "ctl": w.get("ctl"),
                "atl": w.get("atl"),
                # Calculate TSB from CTL - ATL if not present
                "tsb": (
                    w.get("tsb") if w.get("tsb") is not None
                    else (w["ctl"] - w["atl"] if "ctl" in w and "atl" in w and w["ctl"] is not None and w["atl"] is not None else None)
                ),
                "hrv": w.get(hrv_field) if hrv_field else None,
                "resting_hr": w.get("restingHR"),
            }
            for w in wellness_data[-7:]  # Last 7 days
        ],
        "planned_workouts": [
            {
                "id": e.get("id"),
                "name": e.get("name"),
                "type": e.get("type"),
                "start_date": e.get("start_date_local"),
            }
            for e in events if e.get("category") == "WORKOUT"
        ][:5],  # Next 5 planned workouts
    }

    return snapshot


def format_snapshot_as_json(snapshot: dict[str, Any]) -> str:
    """Format snapshot as JSON string.

    Args:
        snapshot: Snapshot dictionary

    Returns:
        JSON string
    """
    return json.dumps(snapshot, indent=2, default=str)
