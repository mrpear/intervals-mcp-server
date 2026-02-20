"""
Fitness-related MCP tools for Intervals.icu.

This module contains tools for retrieving athlete fitness data (CTL, ATL, TSB).
"""

from intervals_mcp_server.api.client import make_intervals_request
from intervals_mcp_server.config import get_config
from intervals_mcp_server.utils.validation import resolve_athlete_id, resolve_date_params

# Import mcp instance from shared module for tool registration
from intervals_mcp_server.mcp_instance import mcp  # noqa: F401

config = get_config()


@mcp.tool()
async def get_fitness_data(
    athlete_id: str | None = None,
    api_key: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> str:
    """Get fitness data for an athlete from Intervals.icu

    Returns CTL (Chronic Training Load), ATL (Acute Training Load),
    and TSB (Training Stress Balance) for the specified date range.

    CTL represents long-term fitness (42-day exponentially weighted average).
    ATL represents short-term fatigue (7-day exponentially weighted average).
    TSB represents form/freshness (CTL - ATL).

    Args:
        athlete_id: The Intervals.icu athlete ID (optional, will use ATHLETE_ID from .env if not provided)
        api_key: The Intervals.icu API key (optional, will use API_KEY from .env if not provided)
        start_date: Start date in YYYY-MM-DD format (optional, defaults to 42 days ago for ACWR)
        end_date: End date in YYYY-MM-DD format (optional, defaults to today)
    """
    # Resolve athlete ID
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg

    # For fitness data, we want a longer default window (42 days for ACWR calculation)
    start_date, end_date = resolve_date_params(start_date, end_date, default_start_days_ago=42)

    # Call the Intervals.icu API
    # Note: Fitness data (CTL, ATL, TSB) is included in the wellness endpoint
    params = {"oldest": start_date, "newest": end_date}

    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/wellness", api_key=api_key, params=params
    )

    if isinstance(result, dict) and "error" in result:
        return f"Error fetching fitness data: {result.get('message')}"

    # Format the response
    if not result:
        return f"No fitness data found for athlete {athlete_id_to_use} in the specified date range."

    fitness_summary = "Fitness Data:\n\n"

    # Handle list response (most common)
    if isinstance(result, list):
        # Show most recent entries first
        sorted_result = sorted(result, key=lambda x: x.get('id', ''), reverse=True)

        for entry in sorted_result[:10]:  # Show last 10 days
            if isinstance(entry, dict):
                date = entry.get('id', 'Unknown')
                ctl = entry.get('ctl', 0)
                atl = entry.get('atl', 0)
                tsb = entry.get('tsb', 0)
                ramp_rate = entry.get('rampRate', 0)

                fitness_summary += f"Date: {date}\n"
                fitness_summary += f"  CTL (Fitness):   {ctl:.1f}\n"
                fitness_summary += f"  ATL (Fatigue):   {atl:.1f}\n"
                fitness_summary += f"  TSB (Form):      {tsb:+.1f}\n"
                fitness_summary += f"  Ramp Rate:       {ramp_rate:.2f}\n"

                # Interpret TSB
                if tsb > 25:
                    form_status = "(Fresh - consider intensity)"
                elif tsb > 5:
                    form_status = "(Rested - good for racing)"
                elif tsb > -10:
                    form_status = "(Optimal training zone)"
                elif tsb > -30:
                    form_status = "(Fatigued - absorbing training)"
                else:
                    form_status = "(High fatigue - recovery needed)"

                fitness_summary += f"  Form Status:     {form_status}\n\n"

        if len(sorted_result) > 10:
            fitness_summary += f"... and {len(sorted_result) - 10} more days\n"

    return fitness_summary