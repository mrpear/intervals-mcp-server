"""Training zone distribution analysis tools."""

from datetime import datetime, timedelta

from intervals_mcp_server.api.client import make_intervals_request
from intervals_mcp_server.config import get_config
from intervals_mcp_server.utils.validation import resolve_athlete_id
from intervals_mcp_server.analytics.zones import (
    aggregate_zone_times,
    calculate_polarization_index,
    interpret_polarization_index,
    calculate_zone_percentages,
    calculate_3zone_distribution,
    interpret_zone_distribution,
)
from intervals_mcp_server.mcp_instance import mcp

config = get_config()


@mcp.tool()
async def get_zone_distribution(
    athlete_id: str | None = None,
    api_key: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    zone_type: str = "power",
) -> str:
    """Get training zone distribution analysis for an athlete.

    Analyzes time spent in different training zones and calculates polarization index.

    Polarization Index (PI) measures training intensity distribution:
    - PI > 2.0: Polarized training (80/20 model - optimal)
    - PI 1.0-2.0: Pyramidal distribution
    - PI < 1.0: Threshold-heavy training

    3-Zone Model:
    - Z1 (Easy): Zones 1-2 (recovery/endurance <75% FTP)
    - Z2 (Threshold): Zones 3-4 (tempo/threshold 75-95% FTP)
    - Z3 (High): Zones 5-7 (VO2max/anaerobic >95% FTP)

    Args:
        athlete_id: The Intervals.icu athlete ID (optional, will use ATHLETE_ID from .env if not provided)
        api_key: The Intervals.icu API key (optional, will use API_KEY from .env if not provided)
        start_date: Start date in YYYY-MM-DD format (optional, defaults to 30 days ago)
        end_date: End date in YYYY-MM-DD format (optional, defaults to today)
        zone_type: "power" or "hr" zones to analyze (default: "power")
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg

    # Default date range: last 30 days
    if not end_date:
        end_date = datetime.now().strftime("%Y-%m-%d")
    if not start_date:
        start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

    # Validate zone_type
    if zone_type not in ["power", "hr"]:
        return f"Invalid zone_type: {zone_type}. Must be 'power' or 'hr'."

    # Fetch activities
    params = {
        "oldest": start_date,
        "newest": end_date
    }

    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/activities",
        api_key=api_key,
        params=params
    )

    if isinstance(result, dict) and "error" in result:
        return f"Error fetching activities: {result.get('message')}"

    if not isinstance(result, list):
        return "No activity data available"

    # Filter activities that have zone data
    if zone_type == "power":
        activities_with_zones = [
            act for act in result
            if isinstance(act, dict) and act.get("icu_zone_times")
        ]
    else:  # hr
        activities_with_zones = [
            act for act in result
            if isinstance(act, dict) and act.get("icu_hr_zone_times")
        ]

    if not activities_with_zones:
        return f"No activities with {zone_type} zone data found in period {start_date} to {end_date}"

    # Aggregate zone times
    zone_times = aggregate_zone_times(activities_with_zones, zone_type)

    if not zone_times:
        return f"No {zone_type} zone data available"

    # Calculate metrics
    zone_percentages = calculate_zone_percentages(zone_times)
    three_zone_dist = calculate_3zone_distribution(zone_times)
    pi = calculate_polarization_index(zone_times)
    pi_interpretation = interpret_polarization_index(pi)
    dist_interpretation = interpret_zone_distribution(three_zone_dist)

    # Calculate total time
    total_seconds = sum(zone_times.values())
    total_hours = total_seconds / 3600

    # Format output
    output = [f"Zone Distribution Analysis ({start_date} to {end_date}):\n"]

    output.append("Training Summary:")
    output.append(f"  Activities analyzed: {len(activities_with_zones)}")
    output.append(f"  Total time: {total_hours:.1f} hours")
    output.append(f"  Zone type: {zone_type.upper()}")

    # 3-Zone model
    output.append("\n3-Zone Polarization Model:")
    output.append(f"  Z1 (Easy, zones 1-2):      {three_zone_dist['Z1']:.1f}%")
    output.append(f"  Z2 (Threshold, zones 3-4): {three_zone_dist['Z2']:.1f}%")
    output.append(f"  Z3 (High, zones 5-7):      {three_zone_dist['Z3']:.1f}%")

    output.append(f"\n  Polarization Index: {pi:.2f} - {pi_interpretation}")
    output.append(f"  Distribution Pattern: {dist_interpretation}")

    # Add status indicator
    if pi >= 2.0:
        output.append("  Status: ✅ Optimal polarized training")
    elif pi >= 1.0:
        output.append("  Status: ⚠️ Consider increasing Z1/Z3 ratio")
    else:
        output.append("  Status: ⛔ Too much threshold work - polarize training")

    # Detailed zone breakdown
    output.append("\nDetailed Zone Breakdown:")
    for zone in sorted(zone_percentages.keys()):
        pct = zone_percentages[zone]
        hours = zone_times[zone] / 3600
        output.append(f"  Zone {zone}: {pct:5.1f}% ({hours:.1f} hours)")

    return "\n".join(output)
