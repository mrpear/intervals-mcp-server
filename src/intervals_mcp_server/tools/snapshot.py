"""Snapshot generation tools for Section 11 data mirror."""

from intervals_mcp_server.config import get_config
from intervals_mcp_server.utils.validation import resolve_athlete_id
from intervals_mcp_server.utils.snapshot_builder import (
    build_latest_snapshot,
    format_snapshot_as_json,
)
from intervals_mcp_server.utils.history_builder import (
    build_history_snapshot,
    format_history_as_json,
)
from intervals_mcp_server.mcp_instance import mcp

config = get_config()


@mcp.tool()
async def get_latest_snapshot(
    athlete_id: str | None = None,
    api_key: str | None = None,
    days: int = 7,
    extended_days: int = 28,
) -> str:
    """Get pre-calculated Section 11 metrics snapshot.

    Returns comprehensive training snapshot with derived metrics:
    - CTL, ATL, TSB, Ramp Rate
    - ACWR, Monotony, Strain, Recovery Index
    - Zone Distribution, Seiler TID (7d and 28d)
    - Aggregate Durability (7d/28d mean decoupling)
    - Phase Detection (Base/Build/Peak/Taper/Recovery)
    - Graduated Alerts Array
    - Recent Activities, Wellness Data, Planned Workouts

    This tool provides a complete snapshot in Section 11 format, equivalent
    to the latest.json file from the data mirror. It combines data from
    multiple endpoints and pre-calculates all derived metrics in a single call.

    Args:
        athlete_id: Intervals.icu athlete ID (optional, will use ATHLETE_ID from .env if not provided)
        api_key: Intervals.icu API key (optional, will use API_KEY from .env if not provided)
        days: Primary snapshot window (default: 7 days)
        extended_days: Extended window for ACWR/baselines (default: 28 days)

    Returns:
        JSON string with complete snapshot data
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg

    # Build snapshot
    snapshot = await build_latest_snapshot(
        athlete_id=athlete_id_to_use,
        api_key=api_key,
        days=days,
        extended_days=extended_days,
    )

    # Handle errors
    if isinstance(snapshot, dict) and "error" in snapshot:
        return f"Error building snapshot: {snapshot.get('message')}"

    # Format as JSON
    return format_snapshot_as_json(snapshot)


@mcp.tool()
async def get_history_snapshot(
    athlete_id: str | None = None,
    api_key: str | None = None,
    max_lookback_days: int = 1095,
) -> str:
    """Get longitudinal training history with tiered granularity.

    Returns historical data structured for trend analysis:
    - 90-day tier: Daily resolution (fine-grained recent trends)
    - 180-day tier: Weekly aggregates (medium-term patterns)
    - 1/2/3-year tiers: Monthly aggregates (long-term progression)
    - FTP timeline: All FTP changes with dates
    - Weight progression: All weight entries with trend line
    - Data gaps: Flagged periods with missing data
    - Phase markers: Base/Build/Peak/Taper/Race transitions

    This tool provides complete historical context for periodization planning,
    performance progression analysis, and long-term trend identification.

    Args:
        athlete_id: Intervals.icu athlete ID (optional, will use ATHLETE_ID from .env if not provided)
        api_key: Intervals.icu API key (optional, will use API_KEY from .env if not provided)
        max_lookback_days: Maximum history to fetch (default: 1095 = 3 years)

    Returns:
        JSON string with historical data
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg

    # Build history snapshot
    snapshot = await build_history_snapshot(
        athlete_id=athlete_id_to_use,
        api_key=api_key,
        max_lookback_days=max_lookback_days,
    )

    # Handle errors
    if isinstance(snapshot, dict) and "error" in snapshot:
        return f"Error building history snapshot: {snapshot.get('message')}"

    # Format as JSON
    return format_history_as_json(snapshot)
