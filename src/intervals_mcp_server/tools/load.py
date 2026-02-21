"""Training load analysis tools."""

from datetime import datetime, timedelta
import statistics
from collections import defaultdict

from intervals_mcp_server.api.client import make_intervals_request
from intervals_mcp_server.config import get_config
from intervals_mcp_server.utils.validation import resolve_athlete_id
from intervals_mcp_server.analytics.load import (
    calculate_monotony,
    calculate_strain,
    interpret_monotony,
    interpret_strain,
)
from intervals_mcp_server.mcp_instance import mcp

config = get_config()


@mcp.tool()
async def get_load_metrics(
    athlete_id: str | None = None,
    api_key: str | None = None,
    end_date: str | None = None,
    window_days: int = 7,
) -> str:
    """Get training load metrics for an athlete.

    Calculates Monotony, Strain, and load distribution over a rolling window.

    Monotony measures training variety (target: <2.5)
    Strain combines load and monotony (alarm: >3500)
    Load-Recovery Ratio ensures load is appropriate for recovery state

    Args:
        athlete_id: The Intervals.icu athlete ID (optional, will use ATHLETE_ID from .env if not provided)
        api_key: The Intervals.icu API key (optional, will use API_KEY from .env if not provided)
        end_date: End date for analysis (YYYY-MM-DD, default: today)
        window_days: Number of days to analyze (default: 7)
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg

    # Default to today
    if not end_date:
        end_date = datetime.now().strftime("%Y-%m-%d")

    # Calculate start date
    end_date_obj = datetime.fromisoformat(end_date)
    start_date = (end_date_obj - timedelta(days=window_days - 1)).strftime("%Y-%m-%d")

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

    # Group activities by date and calculate daily loads
    daily_loads_dict: dict[str, float] = defaultdict(float)

    for activity in result:
        if isinstance(activity, dict):
            date = activity.get('start_date_local', '')[:10]  # Extract YYYY-MM-DD
            load = activity.get('icu_training_load') or activity.get('training_load') or 0
            if date and load:
                daily_loads_dict[date] += load

    # Create ordered list of daily loads for the window (including zero days)
    daily_loads = []
    current_date = datetime.fromisoformat(start_date)

    for _ in range(window_days):
        date_str = current_date.strftime("%Y-%m-%d")
        daily_loads.append(daily_loads_dict.get(date_str, 0.0))
        current_date += timedelta(days=1)

    # Calculate metrics
    if not daily_loads or all(load == 0 for load in daily_loads):
        return f"No training data available for {window_days}-day window ({start_date} to {end_date})"

    # Filter non-zero days for mean calculation
    non_zero_loads = [load for load in daily_loads if load > 0]

    if not non_zero_loads:
        return f"No training sessions found in {window_days}-day window"

    mean_load = statistics.mean(non_zero_loads)
    weekly_load = sum(daily_loads)

    monotony = calculate_monotony(daily_loads)
    strain = calculate_strain(monotony, mean_load)

    monotony_interp = interpret_monotony(monotony)
    strain_interp = interpret_strain(strain)

    # Count training days
    training_days = len(non_zero_loads)
    rest_days = window_days - training_days

    # Format output
    output = [f"Load Metrics ({window_days}-day window: {start_date} to {end_date}):\n"]

    output.append("Training Summary:")
    output.append(f"  Training days: {training_days}/{window_days}")
    output.append(f"  Rest days: {rest_days}")
    output.append(f"  Total load: {weekly_load:.1f} TSS")
    output.append(f"  Mean load (training days): {mean_load:.1f} TSS")

    output.append("\nLoad Variability:")
    output.append(f"  Monotony: {monotony:.2f} - {monotony_interp}")

    # Add status indicator
    if monotony < 2.3:
        output.append("    Status: Good training variety")
    elif monotony < 2.5:
        output.append("    Status: ⚠️ Approaching monotony limit")
    else:
        output.append("    Status: ⛔ Reduce monotony - add variety")

    output.append(f"  Strain: {strain:.1f} - {strain_interp}")

    if strain < 3500:
        output.append("    Status: Load is manageable")
    else:
        output.append("    Status: ⛔ High injury risk - reduce load")

    # Daily loads breakdown
    output.append("\nDaily Loads:")
    for i, load in enumerate(daily_loads):
        date = (datetime.fromisoformat(start_date) + timedelta(days=i)).strftime("%Y-%m-%d")
        if load > 0:
            output.append(f"  {date}: {load:.0f} TSS")
        else:
            output.append(f"  {date}: Rest day")

    return "\n".join(output)
