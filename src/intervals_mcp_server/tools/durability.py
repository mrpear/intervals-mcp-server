"""Aerobic durability and efficiency analysis tools."""

from intervals_mcp_server.api.client import make_intervals_request
from intervals_mcp_server.config import get_config
from intervals_mcp_server.utils.validation import resolve_athlete_id
from intervals_mcp_server.analytics.durability import (
    calculate_efficiency_factor,
    interpret_efficiency_factor,
    calculate_decoupling,
    interpret_decoupling,
    calculate_variability_index,
    interpret_variability_index,
)
from intervals_mcp_server.mcp_instance import mcp

config = get_config()


@mcp.tool()
async def get_durability_metrics(
    activity_id: str,
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """Get aerobic durability and efficiency metrics for a specific activity.

    Calculates:
    - Efficiency Factor (EF): NP / Avg HR - measures aerobic efficiency
    - Pw:HR Decoupling: drift in power/HR ratio - assesses aerobic durability (target <5%)
    - Variability Index (VI): NP / Avg Power - measures effort steadiness (target <1.05)

    Best for steady-state rides >60 minutes. Decoupling requires minimum 60min duration.

    Args:
        activity_id: The Intervals.icu activity ID (required)
        athlete_id: The Intervals.icu athlete ID (optional, will use ATHLETE_ID from .env if not provided)
        api_key: The Intervals.icu API key (optional, will use API_KEY from .env if not provided)
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg

    # Fetch activity details
    activity_result = await make_intervals_request(
        url=f"/activity/{activity_id}",
        api_key=api_key
    )

    if isinstance(activity_result, dict) and "error" in activity_result:
        return f"Error fetching activity: {activity_result.get('message')}"

    if not isinstance(activity_result, dict):
        return "Invalid activity data"

    # Extract key metrics
    activity_name = activity_result.get("name", "Unnamed")
    activity_type = activity_result.get("type", "Unknown")
    moving_time = activity_result.get("moving_time", 0)
    normalized_power = activity_result.get("icu_weighted_avg_watts")
    average_power = activity_result.get("average_watts")
    average_hr = activity_result.get("average_heartrate")

    # Check if we have required data
    if not normalized_power or not average_hr:
        return f"Activity '{activity_name}' missing power or HR data"

    # Calculate Efficiency Factor
    ef = calculate_efficiency_factor(normalized_power, average_hr)
    ef_interpretation = interpret_efficiency_factor(ef)

    # Calculate Variability Index
    if average_power:
        vi = calculate_variability_index(normalized_power, average_power)
        vi_interpretation = interpret_variability_index(vi)
    else:
        vi = 0.0
        vi_interpretation = "No average power data"

    # Format output
    output = [f"Durability Metrics for '{activity_name}':\n"]

    output.append("Activity Info:")
    output.append(f"  Type: {activity_type}")
    output.append(f"  Duration: {moving_time // 60} min")
    output.append(f"  NP: {normalized_power:.0f}w")
    if average_power:
        output.append(f"  Avg Power: {average_power:.0f}w")
    output.append(f"  Avg HR: {average_hr:.0f} bpm")

    output.append("\nEfficiency Metrics:")
    output.append(f"  Efficiency Factor (EF): {ef:.2f}")
    output.append(f"    Interpretation: {ef_interpretation}")

    if vi > 0:
        output.append(f"  Variability Index (VI): {vi:.2f}")
        output.append(f"    Interpretation: {vi_interpretation}")

    # Calculate Pw:HR Decoupling (requires streams)
    if moving_time >= 3600:  # Only for rides >= 60 minutes
        output.append("\nAerobic Durability:")

        # Fetch streams
        streams_result = await make_intervals_request(
            url=f"/activity/{activity_id}/streams",
            api_key=api_key,
            params={"types": "watts,heartrate"}
        )

        if isinstance(streams_result, list):
            # Extract power and HR streams
            power_stream = None
            hr_stream = None

            for stream in streams_result:
                if stream.get("type") == "watts":
                    power_stream = stream.get("data", [])
                elif stream.get("type") == "heartrate":
                    hr_stream = stream.get("data", [])

            if power_stream and hr_stream:
                decoupling_pct, first_half_ratio, second_half_ratio = calculate_decoupling(
                    power_stream, hr_stream
                )

                if first_half_ratio > 0:
                    decoupling_interpretation = interpret_decoupling(decoupling_pct)

                    output.append(f"  Pw:HR Decoupling: {abs(decoupling_pct):.1f}%")
                    output.append(f"    First half ratio: {first_half_ratio:.2f} w/bpm")
                    output.append(f"    Second half ratio: {second_half_ratio:.2f} w/bpm")
                    output.append(f"    Change: {decoupling_pct:+.1f}% (negative = HR drift)")
                    output.append(f"    Interpretation: {decoupling_interpretation}")

                    # Add status indicator
                    if abs(decoupling_pct) < 5:
                        output.append("    Status: ✅ Excellent aerobic durability")
                    elif abs(decoupling_pct) < 10:
                        output.append("    Status: ⚠️ Moderate fatigue drift")
                    else:
                        output.append("    Status: ⛔ Significant fatigue - build aerobic base")
                else:
                    output.append("  Pw:HR Decoupling: Unable to calculate (insufficient data)")
            else:
                output.append("  Pw:HR Decoupling: Stream data not available")
        else:
            output.append("  Pw:HR Decoupling: Unable to fetch stream data")
    else:
        output.append("\nAerobic Durability:")
        output.append(f"  Pw:HR Decoupling: Not calculated (minimum 60 min required, ride was {moving_time // 60} min)")

    return "\n".join(output)
