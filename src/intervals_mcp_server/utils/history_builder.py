"""Historical snapshot generation logic for Section 11 data mirror format."""

import statistics
from datetime import datetime, timedelta
from typing import Any

from intervals_mcp_server.api.client import make_intervals_request
from intervals_mcp_server.analytics.phase_detection import detect_training_phase
from intervals_mcp_server.analytics.load import calculate_monotony
from intervals_mcp_server.analytics.zones import (
    aggregate_zone_times,
    calculate_3zone_distribution,
)


async def build_history_snapshot(
    athlete_id: str,
    api_key: str | None = None,
    max_lookback_days: int = 1095,
) -> dict[str, Any]:
    """Build complete historical snapshot with tiered granularity.

    Args:
        athlete_id: Intervals.icu athlete ID
        api_key: API key for authentication
        max_lookback_days: Maximum history to fetch (default: 1095 = 3 years)

    Returns:
        Dictionary with historical data in Section 11 format
    """
    today = datetime.now()
    start_date = (today - timedelta(days=max_lookback_days)).strftime("%Y-%m-%d")
    end_date = today.strftime("%Y-%m-%d")

    # Fetch all historical data
    activities_result = await make_intervals_request(
        url=f"/athlete/{athlete_id}/activities",
        api_key=api_key,
        params={"oldest": start_date, "newest": end_date},
    )

    wellness_result = await make_intervals_request(
        url=f"/athlete/{athlete_id}/wellness",
        api_key=api_key,
        params={"oldest": start_date, "newest": end_date},
    )

    # Handle errors
    if isinstance(activities_result, dict) and "error" in activities_result:
        return {"error": True, "message": f"Error fetching activities: {activities_result.get('message')}"}
    if isinstance(wellness_result, dict) and "error" in wellness_result:
        # Wellness might be empty dict, not an error
        if "message" in wellness_result:
            return {"error": True, "message": f"Error fetching wellness: {wellness_result.get('message')}"}

    # Convert wellness dict to list if needed
    wellness_data = []
    if isinstance(wellness_result, dict):
        wellness_data = [{**v, "id": k} for k, v in wellness_result.items()]
    elif isinstance(wellness_result, list):
        wellness_data = wellness_result

    # Convert activities to list if needed
    activities = activities_result if isinstance(activities_result, list) else []

    # Sort by date
    activities.sort(key=lambda x: x.get("start_date_local", ""))
    wellness_data.sort(key=lambda x: x.get("id", ""))

    # Build tiered aggregations
    tier_90d = build_daily_tier(activities, wellness_data, days=90)
    tier_180d = build_weekly_tier(activities, wellness_data, days=180)
    tier_1y = build_monthly_tier(activities, wellness_data, days=365)
    tier_2y = build_monthly_tier(activities, wellness_data, days=730)
    tier_3y = build_monthly_tier(activities, wellness_data, days=1095)

    # Extract timelines
    ftp_timeline = extract_ftp_timeline(activities, wellness_data)
    weight_progression = extract_weight_progression(wellness_data)

    # Detect patterns
    data_gaps = detect_data_gaps(activities, start_date, end_date)
    phase_markers = detect_phase_markers(wellness_data, activities)

    # Generate summary
    summary = generate_historical_summary(
        activities, wellness_data,
        ftp_timeline, weight_progression
    )

    return {
        "READ_THIS_FIRST": {
            "description": "Section 11 Training History",
            "purpose": "Longitudinal data for trend analysis and periodization planning",
            "timestamp": datetime.now().isoformat(),
            "version": "3.4.1"
        },
        "metadata": {
            "athlete_id": athlete_id,
            "snapshot_date": end_date,
            "lookback_days": max_lookback_days,
            "data_points": {
                "tier_90d": len(tier_90d),
                "tier_180d": len(tier_180d),
                "tier_1y": len(tier_1y),
                "tier_2y": len(tier_2y),
                "tier_3y": len(tier_3y),
                "ftp_changes": len(ftp_timeline),
                "weight_entries": len(weight_progression["entries"]) if weight_progression else 0
            }
        },
        "tier_90d": tier_90d,
        "tier_180d": tier_180d,
        "tier_1y": tier_1y,
        "tier_2y": tier_2y,
        "tier_3y": tier_3y,
        "ftp_timeline": ftp_timeline,
        "weight_progression": weight_progression,
        "data_gaps": data_gaps,
        "phase_markers": phase_markers,
        "summary": summary
    }


def build_daily_tier(
    activities: list[dict[str, Any]],
    wellness: list[dict[str, Any]],
    days: int = 90
) -> list[dict[str, Any]]:
    """Build 90-day daily resolution tier.

    Args:
        activities: List of activity dictionaries
        wellness: List of wellness dictionaries
        days: Number of days to include

    Returns:
        List of daily entries with metrics
    """
    daily_data = []
    end_date = datetime.now()

    for i in range(days):
        date = end_date - timedelta(days=days - i - 1)
        date_str = date.strftime("%Y-%m-%d")

        # Get data for this day
        day_wellness = next((w for w in wellness if w.get("id") == date_str), {})
        day_activities = [a for a in activities if a.get("start_date_local", "")[:10] == date_str]

        # Calculate daily TSS
        daily_tss = sum(a.get("training_load") or a.get("icu_training_load") or 0 for a in day_activities)

        # Detect phase from wellness data
        phase = None
        if day_wellness.get("ctl") and day_wellness.get("atl") and day_wellness.get("tsb"):
            phase = detect_training_phase(
                ctl=day_wellness["ctl"],
                atl=day_wellness["atl"],
                tsb=day_wellness["tsb"]
            )

        daily_entry = {
            "date": date_str,
            "ctl": round(float(day_wellness["ctl"]), 1) if day_wellness.get("ctl") is not None else None,
            "atl": round(float(day_wellness["atl"]), 1) if day_wellness.get("atl") is not None else None,
            "tsb": (
                round(float(day_wellness["ctl"]) - float(day_wellness["atl"]), 1)
                if day_wellness.get("ctl") is not None and day_wellness.get("atl") is not None
                else None
            ),
            "ramp_rate": round(float(day_wellness["rampRate"]), 2) if day_wellness.get("rampRate") is not None else None,
            "tss": daily_tss if daily_tss > 0 else 0,
            "activities_count": len(day_activities),
            "hrv": day_wellness.get("hrv") or day_wellness.get("hrvRMSSD"),
            "rhr": day_wellness.get("restingHR"),
            "weight": day_wellness.get("weight"),
            "sleep_hours": round(day_wellness.get("sleepSecs", 0) / 3600, 1) if day_wellness.get("sleepSecs") else None,
            "phase": phase
        }

        daily_data.append(daily_entry)

    return daily_data


def build_weekly_tier(
    activities: list[dict[str, Any]],
    wellness: list[dict[str, Any]],
    days: int = 180
) -> list[dict[str, Any]]:
    """Build 180-day weekly aggregates tier.

    Args:
        activities: List of activity dictionaries
        wellness: List of wellness dictionaries
        days: Number of days to include

    Returns:
        List of weekly aggregate entries
    """
    weekly_data = []
    end_date = datetime.now()
    weeks = days // 7

    for i in range(weeks):
        week_end = end_date - timedelta(days=(weeks - i - 1) * 7)
        week_start = week_end - timedelta(days=6)
        week_start_str = week_start.strftime("%Y-%m-%d")
        week_end_str = week_end.strftime("%Y-%m-%d")

        # Get data for this week
        week_activities = [
            a for a in activities
            if week_start_str <= a.get("start_date_local", "")[:10] <= week_end_str
        ]
        week_wellness = [
            w for w in wellness
            if week_start_str <= w.get("id", "") <= week_end_str
        ]

        # Calculate weekly aggregates (filter out None values)
        ctl_values = [float(w["ctl"]) for w in week_wellness if w.get("ctl") is not None]
        atl_values = [float(w["atl"]) for w in week_wellness if w.get("atl") is not None]
        tsb_values = [
            float(w["ctl"]) - float(w["atl"]) for w in week_wellness
            if w.get("ctl") is not None and w.get("atl") is not None
        ]

        weekly_tss = sum(a.get("training_load") or a.get("icu_training_load") or 0 for a in week_activities)
        weekly_hours = sum(a.get("moving_time", 0) for a in week_activities) / 3600

        # Calculate durability for week (activities >60 min)
        durability_values = []
        for activity in week_activities:
            if activity.get("moving_time", 0) >= 3600:  # 60+ minutes
                decoupling = activity.get("decoupling") or activity.get("pw_hr_decoupling")
                if decoupling is not None:
                    durability_values.append(abs(decoupling))

        # Calculate monotony for week
        daily_loads = [w.get("ctlLoad") or 0 for w in week_wellness]
        monotony = calculate_monotony(daily_loads) if daily_loads else 0.0

        # Calculate zone distribution
        zone_times = aggregate_zone_times(week_activities, "power")
        seiler_tid = calculate_3zone_distribution(zone_times) if zone_times else {"Z1": 0.0, "Z2": 0.0, "Z3": 0.0}

        # Detect phase for week (use end-of-week wellness)
        phase = None
        if week_wellness:
            last_day = week_wellness[-1]
            if last_day.get("ctl") and last_day.get("atl") and last_day.get("tsb"):
                phase = detect_training_phase(
                    ctl=last_day["ctl"],
                    atl=last_day["atl"],
                    tsb=last_day["tsb"]
                )

        weekly_entry = {
            "week_start": week_start_str,
            "week_end": week_end_str,
            "ctl_avg": round(statistics.mean(ctl_values), 1) if ctl_values else None,
            "ctl_min": round(min(ctl_values), 1) if ctl_values else None,
            "ctl_max": round(max(ctl_values), 1) if ctl_values else None,
            "atl_avg": round(statistics.mean(atl_values), 1) if atl_values else None,
            "tsb_avg": round(statistics.mean(tsb_values), 1) if tsb_values else None,
            "weekly_tss": weekly_tss if weekly_tss > 0 else 0,
            "activities_count": len(week_activities),
            "hours": round(weekly_hours, 1),
            "durability_avg": round(statistics.mean(durability_values), 1) if durability_values else None,
            "monotony": round(monotony, 2) if monotony > 0 else None,
            "seiler_tid": {k: round(v, 1) for k, v in seiler_tid.items()} if any(seiler_tid.values()) else None,
            "phase": phase
        }

        weekly_data.append(weekly_entry)

    return weekly_data


def build_monthly_tier(
    activities: list[dict[str, Any]],
    wellness: list[dict[str, Any]],
    days: int
) -> list[dict[str, Any]]:
    """Build monthly aggregates tier (1y/2y/3y).

    Args:
        activities: List of activity dictionaries
        wellness: List of wellness dictionaries
        days: Number of days to include

    Returns:
        List of monthly aggregate entries
    """
    monthly_data = []
    end_date = datetime.now()

    # Calculate number of months
    months = days // 30

    for i in range(months):
        month_end = end_date - timedelta(days=(months - i - 1) * 30)
        month_start = month_end - timedelta(days=29)
        month_start_str = month_start.strftime("%Y-%m-%d")
        month_end_str = month_end.strftime("%Y-%m-%d")

        # Get data for this month
        month_activities = [
            a for a in activities
            if month_start_str <= a.get("start_date_local", "")[:10] <= month_end_str
        ]
        month_wellness = [
            w for w in wellness
            if month_start_str <= w.get("id", "") <= month_end_str
        ]

        # Calculate monthly aggregates (filter out None values)
        ctl_values = [float(w["ctl"]) for w in month_wellness if w.get("ctl") is not None]
        monthly_tss = sum(a.get("training_load") or a.get("icu_training_load") or 0 for a in month_activities)
        monthly_hours = sum(a.get("moving_time", 0) for a in month_activities) / 3600

        # Calculate durability for month
        durability_values = []
        for activity in month_activities:
            if activity.get("moving_time", 0) >= 3600:
                decoupling = activity.get("decoupling") or activity.get("pw_hr_decoupling")
                if decoupling is not None:
                    durability_values.append(abs(decoupling))

        # Calculate zone distribution (only for 1y tier to reduce size)
        zone_times = None
        seiler_tid = None
        if days <= 365:
            zone_times = aggregate_zone_times(month_activities, "power")
            if zone_times:
                seiler_tid = calculate_3zone_distribution(zone_times)

        # Detect phase for month (use end-of-month wellness)
        phase = None
        if month_wellness:
            last_day = month_wellness[-1]
            if last_day.get("ctl") and last_day.get("atl"):
                tsb = last_day["ctl"] - last_day["atl"]
                phase = detect_training_phase(
                    ctl=last_day["ctl"],
                    atl=last_day["atl"],
                    tsb=tsb
                )

        monthly_entry = {
            "month": month_start.strftime("%Y-%m"),
            "ctl_avg": round(statistics.mean(ctl_values), 1) if ctl_values else None,
            "ctl_end": round(ctl_values[-1], 1) if ctl_values else None,
            "monthly_tss": monthly_tss if monthly_tss > 0 else 0,
            "activities_count": len(month_activities),
            "hours": round(monthly_hours, 1),
            "durability_avg": round(statistics.mean(durability_values), 1) if durability_values else None,
            "seiler_tid": {k: round(v, 1) for k, v in seiler_tid.items()} if seiler_tid and any(seiler_tid.values()) else None,
            "phase": phase
        }

        monthly_data.append(monthly_entry)

    return monthly_data


def extract_ftp_timeline(
    activities: list[dict[str, Any]],
    wellness: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Extract all FTP changes from activities and wellness data.

    Args:
        activities: List of activity dictionaries
        wellness: List of wellness dictionaries

    Returns:
        List of FTP change entries with dates and values
    """
    ftp_changes = []

    # Track FTP changes from wellness data (eFTP changes)
    prev_ftp = None
    for entry in wellness:
        sport_info = entry.get("sportInfo", {})
        if isinstance(sport_info, dict):
            ride_info = sport_info.get("ride", {})
            if isinstance(ride_info, dict):
                ftp = ride_info.get("icu_ftp_watts") or ride_info.get("ftp")
                weight = entry.get("weight")

                # Only record if FTP changed
                if ftp and ftp != prev_ftp:
                    ftp_changes.append({
                        "date": entry.get("id"),
                        "ftp": ftp,
                        "weight": weight,
                        "w_kg": round(ftp / weight, 2) if weight and weight > 0 else None,
                        "test_type": "Auto-calculated",
                        "source": "wellness"
                    })
                    prev_ftp = ftp

    # Sort by date
    ftp_changes.sort(key=lambda x: x["date"])

    return ftp_changes


def extract_weight_progression(
    wellness: list[dict[str, Any]]
) -> dict[str, Any] | None:
    """Extract weight progression with trend line.

    Args:
        wellness: List of wellness dictionaries

    Returns:
        Dictionary with weight entries and trend line, or None if no data
    """
    entries = []

    for entry in wellness:
        weight = entry.get("weight")
        if weight:
            entries.append({
                "date": entry.get("id"),
                "weight": round(weight, 1)
            })

    if not entries:
        return None

    # Sort by date
    entries.sort(key=lambda x: x["date"])

    # Calculate trend line
    if len(entries) >= 2:
        start_weight = entries[0]["weight"]
        end_weight = entries[-1]["weight"]
        change_kg = end_weight - start_weight
        change_pct = (change_kg / start_weight) * 100

        # Calculate months between first and last entry
        start_date = datetime.fromisoformat(entries[0]["date"])
        end_date = datetime.fromisoformat(entries[-1]["date"])
        months = (end_date - start_date).days / 30.44
        avg_monthly_change = change_kg / months if months > 0 else 0

        trend_line = {
            "start_weight": start_weight,
            "end_weight": end_weight,
            "change_kg": round(change_kg, 1),
            "change_pct": round(change_pct, 1),
            "avg_monthly_change": round(avg_monthly_change, 2)
        }
    else:
        trend_line = None

    return {
        "entries": entries,
        "trend_line": trend_line
    }


def detect_data_gaps(
    activities: list[dict[str, Any]],
    start_date: str,
    end_date: str
) -> list[dict[str, Any]]:
    """Detect periods with no training data.

    Args:
        activities: List of activity dictionaries
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format

    Returns:
        List of data gap entries
    """
    gaps: list[dict[str, Any]] = []

    if not activities:
        return gaps

    # Sort activities by date
    sorted_activities = sorted(activities, key=lambda x: x.get("start_date_local", ""))

    # Check for gaps between activities
    current_date = datetime.fromisoformat(start_date)
    for activity in sorted_activities:
        activity_date_str = activity.get("start_date_local", "")[:10]
        if not activity_date_str:
            continue

        activity_date = datetime.fromisoformat(activity_date_str)

        # If gap is >7 days, flag it
        gap_days = (activity_date - current_date).days
        if gap_days > 7:
            gaps.append({
                "start_date": current_date.strftime("%Y-%m-%d"),
                "end_date": activity_date.strftime("%Y-%m-%d"),
                "days": gap_days,
                "reason": "no_activities"
            })

        current_date = activity_date

    # Check for gap at end
    end_date_obj = datetime.fromisoformat(end_date)
    gap_days = (end_date_obj - current_date).days
    if gap_days > 7:
        gaps.append({
            "start_date": current_date.strftime("%Y-%m-%d"),
            "end_date": end_date,
            "days": gap_days,
            "reason": "no_activities"
        })

    return gaps


def detect_phase_markers(
    wellness: list[dict[str, Any]],
    activities: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Detect training phase transitions (Base/Build/Peak/Taper/Recovery).

    Args:
        wellness: List of wellness dictionaries
        activities: List of activity dictionaries

    Returns:
        List of phase marker entries
    """
    # Simplified implementation - detect phase changes in CTL trends
    phase_markers: list[dict[str, Any]] = []

    if not wellness:
        return phase_markers

    current_phase = None
    phase_start = None

    for entry in wellness:
        if entry.get("ctl") and entry.get("atl"):
            tsb = entry["ctl"] - entry["atl"]
            phase = detect_training_phase(
                ctl=entry["ctl"],
                atl=entry["atl"],
                tsb=tsb
            )

            # Detect phase change
            if phase != current_phase:
                # Save previous phase if it existed
                if current_phase and phase_start:
                    phase_markers.append({
                        "start_date": phase_start,
                        "end_date": entry.get("id"),
                        "phase": current_phase
                    })

                # Start new phase
                current_phase = phase
                phase_start = entry.get("id")

    # Add final phase
    if current_phase and phase_start and wellness:
        phase_markers.append({
            "start_date": phase_start,
            "end_date": wellness[-1].get("id"),
            "phase": current_phase
        })

    return phase_markers


def generate_historical_summary(
    activities: list[dict[str, Any]],
    wellness: list[dict[str, Any]],
    ftp_timeline: list[dict[str, Any]],
    weight_progression: dict[str, Any] | None
) -> dict[str, Any]:
    """Generate overall historical summary statistics.

    Args:
        activities: List of activity dictionaries
        wellness: List of wellness dictionaries
        ftp_timeline: List of FTP change entries
        weight_progression: Weight progression dictionary

    Returns:
        Summary statistics dictionary
    """
    # Activity dates
    activity_dates = set(a.get("start_date_local", "")[:10] for a in activities if a.get("start_date_local"))

    total_activities = len(activities)
    total_hours = sum(a.get("moving_time", 0) for a in activities) / 3600
    total_tss = sum(a.get("training_load") or a.get("icu_training_load") or 0 for a in activities)

    # Calculate consistency (days with activities / total days)
    if activity_dates:
        min_date = min(activity_dates)
        max_date = max(activity_dates)
        total_days = (datetime.fromisoformat(max_date) - datetime.fromisoformat(min_date)).days + 1
        consistency_pct = (len(activity_dates) / total_days * 100) if total_days > 0 else 0
    else:
        total_days = 0
        consistency_pct = 0

    # FTP progression
    if len(ftp_timeline) >= 2:
        ftp_start = ftp_timeline[0]["ftp"]
        ftp_end = ftp_timeline[-1]["ftp"]
        ftp_gain = ftp_end - ftp_start
        ftp_gain_pct = (ftp_gain / ftp_start) * 100
    else:
        ftp_start = ftp_end = ftp_gain = ftp_gain_pct = None

    # Weight change
    if weight_progression and weight_progression.get("entries"):
        weight_entries = weight_progression["entries"]
        if len(weight_entries) >= 2:
            weight_start = weight_entries[0]["weight"]
            weight_end = weight_entries[-1]["weight"]
            weight_change = weight_end - weight_start
            weight_change_pct = (weight_change / weight_start) * 100
        else:
            weight_start = weight_end = weight_change = weight_change_pct = None
    else:
        weight_start = weight_end = weight_change = weight_change_pct = None

    return {
        "total_days_with_data": len(activity_dates),
        "total_activities": total_activities,
        "total_hours": round(total_hours, 1),
        "total_tss": int(total_tss),
        "avg_hours_per_week": round(total_hours / (total_days / 7), 1) if total_days > 0 else 0,
        "consistency_pct": round(consistency_pct, 1),
        "ftp_progression": {
            "start": ftp_start,
            "end": ftp_end,
            "gain": ftp_gain,
            "gain_pct": round(ftp_gain_pct, 1) if ftp_gain_pct is not None else None
        },
        "weight_change": {
            "start": weight_start,
            "end": weight_end,
            "change": round(weight_change, 1) if weight_change is not None else None,
            "change_pct": round(weight_change_pct, 1) if weight_change_pct is not None else None
        }
    }


def format_history_as_json(snapshot: dict[str, Any]) -> str:
    """Format history snapshot as JSON string.

    Args:
        snapshot: History snapshot dictionary

    Returns:
        JSON string
    """
    import json
    return json.dumps(snapshot, indent=2, default=str)
