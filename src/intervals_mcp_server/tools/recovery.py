"""Recovery and readiness analysis tools."""

from datetime import datetime, timedelta

from intervals_mcp_server.api.client import make_intervals_request
from intervals_mcp_server.config import get_config
from intervals_mcp_server.utils.validation import resolve_athlete_id
from intervals_mcp_server.analytics.baselines import calculate_baseline
from intervals_mcp_server.analytics.recovery import (
    calculate_recovery_index,
    interpret_recovery_index,
    calculate_acwr,
    interpret_acwr,
)
from intervals_mcp_server.mcp_instance import mcp

config = get_config()


@mcp.tool()
async def get_recovery_metrics(
    athlete_id: str | None = None,
    api_key: str | None = None,
    date: str | None = None,
) -> str:
    """Get recovery and readiness metrics for an athlete.

    Calculates Recovery Index (RI) and ACWR based on wellness and fitness data.

    Recovery Index combines HRV and RHR to assess readiness:
    - ≥ 0.8: Good readiness for training
    - 0.6-0.79: Moderate fatigue, reduce intensity
    - < 0.6: Deload required

    ACWR (Acute:Chronic Workload Ratio) assesses injury risk:
    - 0.8-1.3: Optimal training load
    - < 0.8: Under-training
    - > 1.3: Over-reaching risk

    Args:
        athlete_id: The Intervals.icu athlete ID (optional, will use ATHLETE_ID from .env if not provided)
        api_key: The Intervals.icu API key (optional, will use API_KEY from .env if not provided)
        date: Date to analyze (YYYY-MM-DD, default: today)
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg

    # Default to today if no date provided
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")

    # Calculate date ranges
    date_obj = datetime.fromisoformat(date)
    start_date_wellness = (date_obj - timedelta(days=14)).strftime("%Y-%m-%d")
    start_date_fitness = (date_obj - timedelta(days=42)).strftime("%Y-%m-%d")

    # Fetch wellness data (includes both wellness and fitness metrics: CTL, ATL, TSB)
    # Note: We use the longer date range to ensure we have fitness data
    wellness_params = {
        "oldest": start_date_fitness,  # Use longer range for fitness calculation
        "newest": date
    }
    wellness_result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/wellness",
        api_key=api_key,
        params=wellness_params
    )

    if isinstance(wellness_result, dict) and "error" in wellness_result:
        return f"Error fetching wellness data: {wellness_result.get('message')}"

    # Convert wellness dict to list if needed
    wellness_data = []
    if isinstance(wellness_result, dict):
        wellness_data = [
            {"id": k, **v} for k, v in wellness_result.items()
        ]
    elif isinstance(wellness_result, list):
        wellness_data = wellness_result

    # Get today's wellness values
    today_wellness = next(
        (item for item in wellness_data if item.get('id') == date),
        None
    )

    if not today_wellness:
        return f"No wellness data found for {date}"

    # Calculate baselines (7-day average excluding today)
    baseline_data = [
        item for item in wellness_data
        if item.get('id', '') < date
    ]

    # Note: API may return 'hrv', 'hrvRMSSD', or 'hrvSDNN' - check all three
    # Priority: hrv > hrvRMSSD > hrvSDNN
    hrv_field = None
    for field in ['hrv', 'hrvRMSSD', 'hrvSDNN']:
        if today_wellness.get(field) is not None:
            hrv_field = field
            break

    if not hrv_field:
        return f"No HRV data found for {date}"

    hrv_baseline = calculate_baseline(baseline_data, hrv_field, baseline_days=7)
    rhr_baseline = calculate_baseline(baseline_data, 'restingHR', baseline_days=7)

    # Get today's values
    hrv_today = today_wellness.get(hrv_field)
    rhr_today = today_wellness.get('restingHR')

    if hrv_today is None or rhr_today is None:
        return f"Incomplete wellness data for {date} (HRV: {hrv_today}, RHR: {rhr_today})"

    # Calculate Recovery Index
    ri = calculate_recovery_index(hrv_today, hrv_baseline, rhr_today, rhr_baseline)
    ri_interpretation = interpret_recovery_index(ri)

    # Note: Fitness values (CTL, ATL, TSB) are already in today_wellness
    # No need for separate fitness API call

    # Format output
    output = [f"Recovery Metrics for {date}:\n"]

    # Recovery Index section
    output.append("Recovery Index (RI):")
    output.append(f"  HRV today: {hrv_today:.1f} ms (baseline: {hrv_baseline:.1f} ms)")
    output.append(f"  RHR today: {rhr_today:.0f} bpm (baseline: {rhr_baseline:.0f} bpm)")
    output.append(f"  RI: {ri:.2f} - {ri_interpretation}")

    # Add emoji indicators
    if ri >= 0.8:
        output.append("  Status: Ready for training")
    elif ri >= 0.6:
        output.append("  Status: Reduce intensity or volume")
    else:
        output.append("  Status: Deload/rest day recommended")

    # ACWR section - fitness data is in today_wellness
    if today_wellness and ('atl' in today_wellness or 'ctl' in today_wellness):
        atl = today_wellness.get('atl', 0)
        ctl = today_wellness.get('ctl', 0)
        tsb = today_wellness.get('tsb', 0)

        acwr = calculate_acwr(atl, ctl)
        acwr_interpretation = interpret_acwr(acwr)

        output.append("\nLoad Metrics:")
        output.append(f"  ATL (Acute): {atl:.1f}")
        output.append(f"  CTL (Chronic): {ctl:.1f}")
        output.append(f"  TSB (Form): {tsb:.1f}")
        output.append(f"  ACWR: {acwr:.2f} - {acwr_interpretation}")

        # Add status based on ACWR
        if 0.8 <= acwr <= 1.3:
            output.append("  Status: Load is in optimal range")
        elif acwr < 0.8:
            output.append("  Status: Consider increasing training load")
        else:
            output.append("  Status: High injury risk - reduce load")
    else:
        output.append("\nLoad Metrics: No fitness data available")

    # Sleep data
    sleep_secs = today_wellness.get('sleepSecs', 0)
    sleep_hours = sleep_secs / 3600 if sleep_secs else 0
    sleep_score = today_wellness.get('sleepScore', 0)

    output.append("\nSleep:")
    output.append(f"  Duration: {sleep_hours:.1f} hours")
    output.append(f"  Score: {sleep_score}/100" if sleep_score else "  Score: N/A")

    # Sleep quality interpretation (1-4 scale: 1=Great, 2=Good, 3=Average, 4=Poor)
    sleep_quality = today_wellness.get('sleepQuality', 0)
    if sleep_quality:
        quality_map = {1: "Great", 2: "Good", 3: "Average", 4: "Poor"}
        quality_text = quality_map.get(sleep_quality, f"Unknown ({sleep_quality})")
        output.append(f"  Quality: {quality_text}")

    # Subjective metrics
    feel = today_wellness.get('feel', 0)
    fatigue = today_wellness.get('fatigue', 0)
    stress = today_wellness.get('stress', 0)

    if feel or fatigue or stress:
        output.append("\nSubjective Metrics:")
        if feel:
            output.append(f"  Feel: {feel}/5")
        if fatigue:
            output.append(f"  Fatigue: {fatigue}/5")
        if stress:
            output.append(f"  Stress: {stress}/5")

    return "\n".join(output)