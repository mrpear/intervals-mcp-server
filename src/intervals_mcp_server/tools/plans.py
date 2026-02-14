"""
Training plan-related MCP tools for Intervals.icu.

This module contains tools for creating, managing, and deleting training plans.
"""

import json
from typing import Any

from intervals_mcp_server.api.client import make_intervals_request
from intervals_mcp_server.config import get_config
from intervals_mcp_server.utils.validation import resolve_athlete_id
from intervals_mcp_server.utils.types import WorkoutDoc

# Import mcp instance from shared module for tool registration
from intervals_mcp_server.mcp_instance import mcp

config = get_config()


@mcp.tool()
async def create_training_plan(
    name: str,
    description: str,
    duration_weeks: int,
    start_date: str | None = None,
    hours_per_week_min: int = 4,
    hours_per_week_max: int = 12,
    auto_rollout_day: int = 1,
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """Create a training plan folder in Intervals.icu

    Args:
        name: Plan name
        description: Plan description
        duration_weeks: Number of weeks in the plan
        start_date: Start date in YYYY-MM-DD format (optional)
        hours_per_week_min: Minimum weekly hours (default: 4)
        hours_per_week_max: Maximum weekly hours (default: 12)
        auto_rollout_day: Day to auto-rollout (0=Sunday, 1=Monday, etc., default: 1)
        athlete_id: The Intervals.icu athlete ID (optional, will use ATHLETE_ID from .env if not provided)
        api_key: The Intervals.icu API key (optional, will use API_KEY from .env if not provided)
    """
    # Resolve athlete ID
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg

    # Build request body
    plan_data = {
        "type": "PLAN",
        "name": name,
        "description": description,
        "duration_weeks": duration_weeks,
        "hours_per_week_min": hours_per_week_min,
        "hours_per_week_max": hours_per_week_max,
        "auto_rollout_day": auto_rollout_day,
        "workout_targets": ["POWER"],
        "activity_types": ["Ride"],
    }

    if start_date:
        plan_data["start_date_local"] = start_date

    # Make API request
    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/folders",
        api_key=api_key,
        method="POST",
        data=plan_data,
    )

    # Handle errors
    if isinstance(result, dict) and "error" in result:
        error_message = result.get("message", "Unknown error")
        return f"Error creating training plan: {error_message}"

    # Return success
    return json.dumps(result, indent=2)


@mcp.tool()
async def add_workout_to_plan(
    plan_id: int,
    name: str,
    description: str,
    day: int,
    workout_doc: WorkoutDoc | None = None,
    workout_type: str = "Ride",
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """Add a single workout template to a training plan

    Args:
        plan_id: ID of the training plan folder
        name: Workout name
        description: Workout description
        day: Absolute day from plan start (0=first day, 7=start of week 2, etc.)
        workout_doc: Workout document structure with steps (optional)
        workout_type: Type of workout (default: "Ride")
        athlete_id: The Intervals.icu athlete ID (optional, will use ATHLETE_ID from .env if not provided)
        api_key: The Intervals.icu API key (optional, will use API_KEY from .env if not provided)
    """
    # Resolve athlete ID
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg

    # Build request body
    workout_data: dict[str, Any] = {
        "name": name,
        "description": description,
        "folder_id": plan_id,
        "day": day,
        "type": workout_type,
    }

    # Add workout_doc if provided
    if workout_doc is not None:
        # Convert WorkoutDoc instance to dict if needed
        if hasattr(workout_doc, 'to_dict'):
            workout_data["workout_doc"] = workout_doc.to_dict()
        else:
            workout_data["workout_doc"] = workout_doc

    # Make API request
    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/workouts",
        api_key=api_key,
        method="POST",
        data=workout_data,
    )

    # Handle errors
    if isinstance(result, dict) and "error" in result:
        error_message = result.get("message", "Unknown error")
        return f"Error adding workout to plan: {error_message}"

    # Return success
    return json.dumps(result, indent=2)


@mcp.tool()
async def add_workouts_bulk(
    workouts: list[dict[str, Any]],
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """Add multiple workout templates to a plan in a single request

    Args:
        workouts: List of workout objects, each containing:
            - name: Workout name
            - description: Workout description
            - folder_id: Plan ID
            - day: Absolute day from plan start
            - type: Workout type (e.g., "Ride")
            - workout_doc: Workout structure (optional)
        athlete_id: The Intervals.icu athlete ID (optional, will use ATHLETE_ID from .env if not provided)
        api_key: The Intervals.icu API key (optional, will use API_KEY from .env if not provided)
    """
    # Resolve athlete ID
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg

    # Make API request
    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/workouts/bulk",
        api_key=api_key,
        method="POST",
        data=workouts,
    )

    # Handle errors
    if isinstance(result, dict) and "error" in result:
        error_message = result.get("message", "Unknown error")
        return f"Error adding workouts in bulk: {error_message}"

    # Return success
    return json.dumps(result, indent=2)


@mcp.tool()
async def get_training_plans(
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """Get all training plan folders for the athlete

    Args:
        athlete_id: The Intervals.icu athlete ID (optional, will use ATHLETE_ID from .env if not provided)
        api_key: The Intervals.icu API key (optional, will use API_KEY from .env if not provided)
    """
    # Resolve athlete ID
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg

    # Make API request
    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/folders",
        api_key=api_key,
        method="GET",
    )

    # Handle errors
    if isinstance(result, dict) and "error" in result:
        error_message = result.get("message", "Unknown error")
        return f"Error fetching training plans: {error_message}"

    # Return success
    return json.dumps(result, indent=2)


@mcp.tool()
async def delete_training_plan(
    plan_id: int,
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """Delete a training plan folder (and all its workouts)

    Args:
        plan_id: ID of the training plan folder to delete
        athlete_id: The Intervals.icu athlete ID (optional, will use ATHLETE_ID from .env if not provided)
        api_key: The Intervals.icu API key (optional, will use API_KEY from .env if not provided)
    """
    # Resolve athlete ID
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg

    # Make API request
    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/folders/{plan_id}",
        api_key=api_key,
        method="DELETE",
    )

    # Handle errors
    if isinstance(result, dict) and "error" in result:
        error_message = result.get("message", "Unknown error")
        return f"Error deleting training plan: {error_message}"

    # Return success message
    return f"Successfully deleted training plan {plan_id}"
