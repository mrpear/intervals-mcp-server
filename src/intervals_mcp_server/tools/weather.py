"""
Weather-related MCP tools for Intervals.icu.

This module contains tools for retrieving weather forecast information.
"""

from intervals_mcp_server.api.client import make_intervals_request
from intervals_mcp_server.config import get_config
from intervals_mcp_server.utils.validation import resolve_athlete_id

# Import mcp instance from shared module for tool registration
from intervals_mcp_server.mcp_instance import mcp  # noqa: F401

config = get_config()


@mcp.tool()
async def get_weather_forecast(
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """Get weather forecast information for an athlete from Intervals.icu

    Returns configured weather forecasts including location, coordinates, and provider.

    Args:
        athlete_id: The Intervals.icu athlete ID (optional, will use ATHLETE_ID from .env if not provided)
        api_key: The Intervals.icu API key (optional, will use API_KEY from .env if not provided)
    """
    # Resolve athlete ID
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg

    # Call the Intervals.icu API
    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/weather-forecast", api_key=api_key
    )

    if isinstance(result, dict) and "error" in result:
        return f"Error fetching weather forecast: {result.get('message')}"

    # Format the response
    if not result:
        return f"No weather forecast data found for athlete {athlete_id_to_use}."

    # Extract forecasts array
    forecasts = result.get("forecasts", [])
    if not forecasts:
        return f"No weather forecasts configured for athlete {athlete_id_to_use}."

    weather_summary = "Weather Forecasts:\n\n"

    for forecast in forecasts:
        location = forecast.get("location", "Unknown")
        label = forecast.get("label", "")
        lat = forecast.get("lat", 0.0)
        lon = forecast.get("lon", 0.0)
        provider = forecast.get("provider", "Unknown")
        enabled = forecast.get("enabled", False)
        status = "Enabled" if enabled else "Disabled"

        weather_summary += f"📍 {location}"
        if label:
            weather_summary += f" ({label})"
        weather_summary += f"\n"
        weather_summary += f"   Coordinates: {lat:.4f}, {lon:.4f}\n"
        weather_summary += f"   Provider: {provider}\n"
        weather_summary += f"   Status: {status}\n\n"

    return weather_summary