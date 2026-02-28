"""
Activity-related MCP tools for Intervals.icu.

This module contains tools for retrieving and managing athlete activities.
"""

from datetime import datetime, timedelta
from typing import Any

from intervals_mcp_server.api.client import make_intervals_request
from intervals_mcp_server.config import get_config
from intervals_mcp_server.utils.formatting import format_activity_summary, format_intervals
from intervals_mcp_server.utils.validation import resolve_athlete_id, resolve_date_params
from intervals_mcp_server.utils.types import CoachTick

# Import mcp instance from shared module for tool registration
from intervals_mcp_server.mcp_instance import mcp  # noqa: F401

config = get_config()


def _parse_activities_from_result(result: Any) -> list[dict[str, Any]]:
    """Extract a list of activity dictionaries from the API result."""
    activities: list[dict[str, Any]] = []

    if isinstance(result, list):
        activities = [item for item in result if isinstance(item, dict)]
    elif isinstance(result, dict):
        # Result is a single activity or a container
        for _key, value in result.items():
            if isinstance(value, list):
                activities = [item for item in value if isinstance(item, dict)]
                break
        # If no list was found but the dict has typical activity fields, treat it as a single activity
        if not activities and any(key in result for key in ["name", "startTime", "distance"]):
            activities = [result]

    return activities


def _filter_named_activities(activities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Filter out unnamed activities from the list."""
    return [
        activity
        for activity in activities
        if activity.get("name") and activity.get("name") != "Unnamed"
    ]


async def _fetch_more_activities(
    athlete_id: str,
    start_date: str,
    api_key: str | None,
    api_limit: int,
) -> list[dict[str, Any]]:
    """Fetch additional activities from an earlier date range."""
    oldest_date = datetime.fromisoformat(start_date)
    older_start_date = (oldest_date - timedelta(days=60)).strftime("%Y-%m-%d")
    older_end_date = (oldest_date - timedelta(days=1)).strftime("%Y-%m-%d")

    if older_start_date >= older_end_date:
        return []

    more_params = {
        "oldest": older_start_date,
        "newest": older_end_date,
        "limit": api_limit,
    }
    more_result = await make_intervals_request(
        url=f"/athlete/{athlete_id}/activities",
        api_key=api_key,
        params=more_params,
    )

    if isinstance(more_result, list):
        return _filter_named_activities(more_result)
    return []


def _format_activities_response(
    activities: list[dict[str, Any]],
    athlete_id: str,
    include_unnamed: bool,
) -> str:
    """Format the activities response based on the results."""
    if not activities:
        if include_unnamed:
            return (
                f"No valid activities found for athlete {athlete_id} in the specified date range."
            )
        return f"No named activities found for athlete {athlete_id} in the specified date range. Try with include_unnamed=True to see all activities."

    # Format the output
    activities_summary = "Activities:\n\n"
    for activity in activities:
        if isinstance(activity, dict):
            activities_summary += format_activity_summary(activity) + "\n"
        else:
            activities_summary += f"Invalid activity format: {activity}\n\n"

    return activities_summary


@mcp.tool()
async def get_activities(  # pylint: disable=too-many-arguments,too-many-return-statements,too-many-branches,too-many-positional-arguments
    athlete_id: str | None = None,
    api_key: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int = 10,
    include_unnamed: bool = False,
    fields: str | None = None,
) -> str:
    """Get a list of activities for an athlete from Intervals.icu

    Args:
        athlete_id: The Intervals.icu athlete ID (optional, will use ATHLETE_ID from .env if not provided)
        api_key: The Intervals.icu API key (optional, will use API_KEY from .env if not provided)
        start_date: Start date in YYYY-MM-DD format (optional, defaults to 30 days ago)
        end_date: End date in YYYY-MM-DD format (optional, defaults to today)
        limit: Maximum number of activities to return (optional, defaults to 10)
        include_unnamed: Whether to include unnamed activities (optional, defaults to False)
        fields: Comma-separated list of fields to include in the response, e.g. "id,name,start_date_local,type,distance"
                (optional, defaults to all fields)
    """
    # Resolve athlete ID and date parameters
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg

    start_date, end_date = resolve_date_params(start_date, end_date)

    # Fetch more activities if we need to filter out unnamed ones
    api_limit = limit * 3 if not include_unnamed else limit

    # Call the Intervals.icu API
    params: dict[str, Any] = {"oldest": start_date, "newest": end_date, "limit": api_limit}
    if fields:
        params["fields"] = fields
    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/activities", api_key=api_key, params=params
    )

    # Check for error
    if isinstance(result, dict) and "error" in result:
        error_message = result.get("message", "Unknown error")
        return f"Error fetching activities: {error_message}"

    if not result:
        return f"No activities found for athlete {athlete_id_to_use} in the specified date range."

    # Parse activities from result
    activities = _parse_activities_from_result(result)

    if not activities:
        return f"No valid activities found for athlete {athlete_id_to_use} in the specified date range."

    # Filter and fetch more if needed
    if not include_unnamed:
        activities = _filter_named_activities(activities)

        # If we don't have enough named activities, try to fetch more
        if len(activities) < limit:
            more_activities = await _fetch_more_activities(
                athlete_id_to_use, start_date, api_key, api_limit
            )
            activities.extend(more_activities)

    # Limit to requested count
    activities = activities[:limit]

    return _format_activities_response(activities, athlete_id_to_use, include_unnamed)


@mcp.tool()
async def get_activity_details(activity_id: str, api_key: str | None = None) -> str:
    """Get detailed information for a specific activity from Intervals.icu

    Args:
        activity_id: The Intervals.icu activity ID
        api_key: The Intervals.icu API key (optional, will use API_KEY from .env if not provided)
    """
    # Call the Intervals.icu API
    result = await make_intervals_request(url=f"/activity/{activity_id}", api_key=api_key)

    if isinstance(result, dict) and "error" in result:
        error_message = result.get("message", "Unknown error")
        return f"Error fetching activity details: {error_message}"

    # Format the response
    if not result:
        return f"No details found for activity {activity_id}."

    # If result is a list, use the first item if available
    activity_data = result[0] if isinstance(result, list) and result else result
    if not isinstance(activity_data, dict):
        return f"Invalid activity format for activity {activity_id}."

    # Return a more detailed view of the activity
    detailed_view = format_activity_summary(activity_data)

    # Add additional details if available
    if "zones" in activity_data:
        zones = activity_data["zones"]
        detailed_view += "\nPower Zones:\n"
        for zone in zones.get("power", []):
            detailed_view += f"Zone {zone.get('number')}: {zone.get('secondsInZone')} seconds\n"

        detailed_view += "\nHeart Rate Zones:\n"
        for zone in zones.get("hr", []):
            detailed_view += f"Zone {zone.get('number')}: {zone.get('secondsInZone')} seconds\n"

    return detailed_view


@mcp.tool()
async def get_activity_intervals(activity_id: str, api_key: str | None = None) -> str:
    """Get interval data for a specific activity from Intervals.icu

    This endpoint returns detailed metrics for each interval in an activity, including power, heart rate,
    cadence, speed, and environmental data. It also includes grouped intervals if applicable.

    Args:
        activity_id: The Intervals.icu activity ID
        api_key: The Intervals.icu API key (optional, will use API_KEY from .env if not provided)
    """
    # Call the Intervals.icu API
    result = await make_intervals_request(url=f"/activity/{activity_id}/intervals", api_key=api_key)

    if isinstance(result, dict) and "error" in result:
        error_message = result.get("message", "Unknown error")
        return f"Error fetching intervals: {error_message}"

    # Format the response
    if not result:
        return f"No interval data found for activity {activity_id}."

    # If the result is empty or doesn't contain expected fields
    if not isinstance(result, dict) or not any(
        key in result for key in ["icu_intervals", "icu_groups"]
    ):
        return f"No interval data or unrecognized format for activity {activity_id}."

    # Format the intervals data
    return format_intervals(result)


@mcp.tool()
async def get_activity_streams(
    activity_id: str,
    api_key: str | None = None,
    stream_types: str | None = None,
) -> str:
    """Get stream data for a specific activity from Intervals.icu

    This endpoint returns time-series data for an activity, including metrics like power, heart rate,
    cadence, altitude, distance, temperature, and velocity data.

    Args:
        activity_id: The Intervals.icu activity ID
        api_key: The Intervals.icu API key (optional, will use API_KEY from .env if not provided)
        stream_types: Comma-separated list of stream types to retrieve (optional, defaults to all available types)
                     Available types: time, watts, heartrate, cadence, altitude, distance,
                     core_temperature, skin_temperature, velocity_smooth
    """
    # Build query parameters
    params = {}
    if stream_types:
        params["types"] = stream_types
    else:
        # Default to common stream types if none specified
        params["types"] = "time,watts,heartrate,cadence,altitude,distance,velocity_smooth"

    # Call the Intervals.icu API
    result = await make_intervals_request(
        url=f"/activity/{activity_id}/streams",
        api_key=api_key,
        params=params,
    )

    if isinstance(result, dict) and "error" in result:
        error_message = result.get("message", "Unknown error")
        return f"Error fetching activity streams: {error_message}"

    # Format the response
    if not result:
        return f"No stream data found for activity {activity_id}."

    # Ensure result is a list
    streams = result if isinstance(result, list) else []

    if not streams:
        return f"No stream data found for activity {activity_id}."

    # Format the streams data
    streams_summary = f"Activity Streams for {activity_id}:\n\n"

    for stream in streams:
        if not isinstance(stream, dict):
            continue

        stream_type = stream.get("type", "unknown")
        stream_name = stream.get("name", stream_type)
        data = stream.get("data", [])
        value_type = stream.get("valueType", "")

        streams_summary += f"Stream: {stream_name} ({stream_type})\n"
        streams_summary += f"  Value Type: {value_type}\n"
        streams_summary += f"  Data Points: {len(data)}\n"

        # Show first few and last few data points for preview
        if data:
            if len(data) <= 10:
                streams_summary += f"  Values: {data}\n"
            else:
                preview_start = data[:5]
                preview_end = data[-5:]
                streams_summary += f"  First 5 values: {preview_start}\n"
                streams_summary += f"  Last 5 values: {preview_end}\n"

        streams_summary += "\n"

    return streams_summary


@mcp.tool()
async def search_activities(
    query: str,
    athlete_id: str | None = None,
    api_key: str | None = None,
    limit: int = 50,
) -> str:
    """Search for activities by name or tag across all time (no date range constraint).

    Args:
        query: Search query. Case-insensitive name search, or exact tag search if it starts with #
               (e.g., "morning ride" or "#race")
        athlete_id: The Intervals.icu athlete ID (optional, will use ATHLETE_ID from .env if not provided)
        api_key: The Intervals.icu API key (optional, will use API_KEY from .env if not provided)
        limit: Maximum number of activities to return (optional, defaults to 50)
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg

    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/activities/search",
        api_key=api_key,
        params={"q": query, "limit": limit},
    )

    if isinstance(result, dict) and "error" in result:
        return f"Error searching activities: {result.get('message', 'Unknown error')}"

    if not result or not isinstance(result, list):
        return f"No activities found matching '{query}'."

    lines = [f"Activities matching '{query}' ({len(result)} results):\n"]
    for activity in result:
        if not isinstance(activity, dict):
            continue
        date = activity.get("start_date_local", "Unknown")
        name = activity.get("name", "Unnamed")
        activity_id = activity.get("id", "")
        activity_type = activity.get("type", "")
        distance = activity.get("distance")
        moving_time = activity.get("moving_time")
        tags = activity.get("tags") or []
        description = activity.get("description", "")

        line = f"- [{date}] {name} (ID: {activity_id})"
        if activity_type:
            line += f" | {activity_type}"
        if distance:
            line += f" | {distance:.0f}m"
        if moving_time:
            minutes, seconds = divmod(moving_time, 60)
            hours, minutes = divmod(minutes, 60)
            if hours:
                line += f" | {hours}h{minutes:02d}m"
            else:
                line += f" | {minutes}m{seconds:02d}s"
        if tags:
            line += f" | tags: {', '.join(tags)}"
        lines.append(line)
        if description:
            lines.append(f"  {description}")

    return "\n".join(lines)


@mcp.tool()
async def update_activity(
    activity_id: str,
    coach_tick: int | None = None,
    description: str | None = None,
    name: str | None = None,
    feel: int | None = None,
    perceived_exertion: int | None = None,
    api_key: str | None = None,
) -> str:
    """Update activity fields.

    Updates one or more fields on an activity. Common uses:
    - Set coach's tick (1-5 rating, or -1 to unset)
    - Update description/notes
    - Change activity name
    - Set feel or perceived exertion

    Coach's tick scale:
    - 5: Amazing
    - 4: Great
    - 3: Good
    - 2: Needs improvement
    - 1: Concerning
    - -1: Remove/unset the tick

    Args:
        activity_id: The activity ID (e.g., "i127117496")
        coach_tick: Coach's rating (1-5 to set, -1 to unset, optional)
        description: Activity description/notes (optional, supports markdown)
        name: Activity name (optional)
        feel: How the athlete felt (1-5, optional)
        perceived_exertion: RPE rating (1-10, optional)
        api_key: The Intervals.icu API key (optional, will use API_KEY from .env if not provided)

    Returns:
        Success message or error message
    """
    # Build update payload with only provided fields
    update_data: dict[str, Any] = {}

    if coach_tick is not None:
        if coach_tick == -1:
            # -1 means unset the coach tick
            update_data["coach_tick"] = -1
        elif coach_tick < 1 or coach_tick > 5:
            return "Error: coach_tick must be between 1 and 5, or -1 to unset"
        else:
            update_data["coach_tick"] = coach_tick

    if description is not None:
        update_data["description"] = description

    if name is not None:
        update_data["name"] = name

    if feel is not None:
        if feel < 1 or feel > 5:
            return "Error: feel must be between 1 and 5"
        update_data["feel"] = feel

    if perceived_exertion is not None:
        if perceived_exertion < 1 or perceived_exertion > 10:
            return "Error: perceived_exertion must be between 1 and 10"
        update_data["perceived_exertion"] = perceived_exertion

    if not update_data:
        return "Error: No fields provided to update"

    result = await make_intervals_request(
        url=f"/activity/{activity_id}",
        api_key=api_key,
        method="PUT",
        data=update_data
    )

    if isinstance(result, dict) and "error" in result:
        return f"Error updating activity: {result.get('message')}"

    # Build success message
    updated_fields = []
    if coach_tick is not None:
        if coach_tick == -1:
            updated_fields.append("coach_tick: removed")
        else:
            tick_enum = CoachTick(coach_tick)
            updated_fields.append(f"coach_tick: {coach_tick} ({tick_enum.label})")
    if description is not None:
        updated_fields.append("description")
    if name is not None:
        updated_fields.append(f"name: {name}")
    if feel is not None:
        updated_fields.append(f"feel: {feel}")
    if perceived_exertion is not None:
        updated_fields.append(f"perceived_exertion: {perceived_exertion}")

    return f"Activity {activity_id} updated: {', '.join(updated_fields)}"
