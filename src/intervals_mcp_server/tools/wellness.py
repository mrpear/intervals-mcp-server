"""
Wellness-related MCP tools for Intervals.icu.

This module contains tools for retrieving athlete wellness data.
"""

from intervals_mcp_server.api.client import make_intervals_request
from intervals_mcp_server.config import get_config
from intervals_mcp_server.utils.formatting import format_wellness_entry
from intervals_mcp_server.utils.validation import resolve_athlete_id, resolve_date_params

# Import mcp instance from shared module for tool registration
from intervals_mcp_server.mcp_instance import mcp  # noqa: F401

config = get_config()


@mcp.tool()
async def get_wellness_data(
    athlete_id: str | None = None,
    api_key: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> str:
    """Get wellness data for an athlete from Intervals.icu

    Args:
        athlete_id: The Intervals.icu athlete ID (optional, will use ATHLETE_ID from .env if not provided)
        api_key: The Intervals.icu API key (optional, will use API_KEY from .env if not provided)
        start_date: Start date in YYYY-MM-DD format (optional, defaults to 30 days ago)
        end_date: End date in YYYY-MM-DD format (optional, defaults to today)
    """
    # Resolve athlete ID and date parameters
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg

    start_date, end_date = resolve_date_params(start_date, end_date)

    # Call the Intervals.icu API
    params = {"oldest": start_date, "newest": end_date}

    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/wellness", api_key=api_key, params=params
    )

    if isinstance(result, dict) and "error" in result:
        return f"Error fetching wellness data: {result.get('message')}"

    # Format the response
    if not result:
        return (
            f"No wellness data found for athlete {athlete_id_to_use} in the specified date range."
        )

    wellness_summary = "Wellness Data:\n\n"

    # Handle both list and dictionary responses
    if isinstance(result, dict):
        for date_str, data in result.items():
            # Add the date to the data dictionary if it's not already present
            if isinstance(data, dict) and "date" not in data:
                data["date"] = date_str
            wellness_summary += format_wellness_entry(data) + "\n\n"
    elif isinstance(result, list):
        for entry in result:
            if isinstance(entry, dict):
                wellness_summary += format_wellness_entry(entry) + "\n\n"

    return wellness_summary


@mcp.tool()
async def update_wellness_data(
    date: str,
    athlete_id: str | None = None,
    api_key: str | None = None,
    weight: float | None = None,
    resting_hr: int | None = None,
    hrv: float | None = None,
    hrv_sdnn: float | None = None,
    avg_sleeping_hr: int | None = None,
    spo2: float | None = None,
    systolic: int | None = None,
    diastolic: int | None = None,
    respiration: float | None = None,
    blood_glucose: float | None = None,
    lactate: float | None = None,
    vo2max: float | None = None,
    body_fat: float | None = None,
    abdomen: float | None = None,
    baevsky_si: float | None = None,
    sleep_secs: int | None = None,
    sleep_quality: int | None = None,
    sleep_score: int | None = None,
    readiness: int | None = None,
    menstrual_phase: str | None = None,
    menstrual_phase_predicted: str | None = None,
    soreness: int | None = None,
    fatigue: int | None = None,
    stress: int | None = None,
    mood: int | None = None,
    motivation: int | None = None,
    injury: int | None = None,
    kcal_consumed: int | None = None,
    hydration_volume: float | None = None,
    hydration: int | None = None,
    steps: int | None = None,
    comments: str | None = None,
) -> str:
    """Update wellness data for a specific date.

    Updates wellness record for the specified date. Only provided fields will be updated.

    Args:
        date: Date in YYYY-MM-DD format (required)
        athlete_id: The Intervals.icu athlete ID (optional, will use ATHLETE_ID from .env if not provided)
        api_key: The Intervals.icu API key (optional, will use API_KEY from .env if not provided)
        weight: Weight in kg
        resting_hr: Resting heart rate in bpm
        hrv: Heart rate variability
        hrv_sdnn: HRV SDNN
        avg_sleeping_hr: Average sleeping heart rate in bpm
        spo2: Blood oxygen saturation percentage
        systolic: Systolic blood pressure
        diastolic: Diastolic blood pressure
        respiration: Respiration rate in breaths/min
        blood_glucose: Blood glucose in mmol/L
        lactate: Lactate in mmol/L
        vo2max: VO2 max in ml/kg/min
        body_fat: Body fat percentage
        abdomen: Abdomen measurement in cm
        baevsky_si: Baevsky Stress Index
        sleep_secs: Sleep duration in seconds
        sleep_quality: Sleep quality (1=Great, 2=Good, 3=Average, 4=Poor)
        sleep_score: Device sleep score (0-100)
        readiness: Readiness score (0-10)
        menstrual_phase: Menstrual phase
        menstrual_phase_predicted: Predicted menstrual phase
        soreness: Soreness level (1-5)
        fatigue: Fatigue level (1-5)
        stress: Stress level (1-5)
        mood: Mood level (1-5)
        motivation: Motivation level (1-5)
        injury: Injury status (1-5)
        kcal_consumed: Calories consumed
        hydration_volume: Hydration volume in ml
        hydration: Hydration score (0-10)
        steps: Daily step count
        comments: Free-text comments
    """
    # Resolve athlete ID
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg

    # Build request body with only non-None fields
    # Map Python parameter names to Intervals.icu API field names
    field_mapping = {
        "weight": weight,
        "restingHR": resting_hr,
        "hrv": hrv,
        "hrvSDNN": hrv_sdnn,
        "avgSleepingHR": avg_sleeping_hr,
        "spO2": spo2,
        "systolic": systolic,
        "diastolic": diastolic,
        "respiration": respiration,
        "bloodGlucose": blood_glucose,
        "lactate": lactate,
        "vo2max": vo2max,
        "bodyFat": body_fat,
        "abdomen": abdomen,
        "baevskySI": baevsky_si,
        "sleepSecs": sleep_secs,
        "sleepQuality": sleep_quality,
        "sleepScore": sleep_score,
        "readiness": readiness,
        "menstrualPhase": menstrual_phase,
        "menstrualPhasePredicted": menstrual_phase_predicted,
        "soreness": soreness,
        "fatigue": fatigue,
        "stress": stress,
        "mood": mood,
        "motivation": motivation,
        "injury": injury,
        "kcalConsumed": kcal_consumed,
        "hydrationVolume": hydration_volume,
        "hydration": hydration,
        "steps": steps,
        "comments": comments,
    }

    # Filter out None values
    data = {k: v for k, v in field_mapping.items() if v is not None}

    if not data:
        return "Error: No wellness fields provided to update"

    # Call the Intervals.icu API with PUT method
    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/wellness/{date}",
        api_key=api_key,
        method="PUT",
        data=data,
    )

    if isinstance(result, dict) and "error" in result:
        return f"Error updating wellness data: {result.get('message')}"

    # Format success response
    updated_fields = ", ".join(data.keys())
    return f"Successfully updated wellness data for {date}:\nUpdated fields: {updated_fields}\n\n{format_wellness_entry(result if isinstance(result, dict) else {})}"
