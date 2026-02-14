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


def _calculate_total_duration(steps: list[dict[str, Any]]) -> int:
    """Calculate total duration in seconds from workout steps.

    Handles nested steps (reps) recursively.
    """
    total = 0
    for step in steps:
        if "reps" in step and "steps" in step:
            # Nested steps - multiply by reps
            nested_duration = _calculate_total_duration(step["steps"])
            total += nested_duration * step["reps"]
        elif "duration" in step:
            # Single step with duration
            total += step["duration"]
    return total


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

    # Return concise summary instead of full JSON
    plan_id = result.get("id")
    plan_name = result.get("name")
    return f"✓ Created training plan '{plan_name}' (ID: {plan_id})"


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
        "folder_id": plan_id,
        "day": day,
        "type": workout_type,
    }

    # Handle workout_doc: send BOTH text description AND JSON workout_doc
    # Intervals.icu needs both for proper display
    if workout_doc is not None:
        from intervals_mcp_server.utils.types import WorkoutDoc as WorkoutDocType

        # Convert to WorkoutDoc object if it's a dict
        if isinstance(workout_doc, dict):
            workout_doc_obj = WorkoutDocType.from_dict(workout_doc)
            workout_doc_dict = workout_doc
        else:
            # Already a WorkoutDoc instance
            workout_doc_obj = workout_doc
            workout_doc_dict = workout_doc.to_dict()

        # Set description as text format (for display in some views)
        workout_data["description"] = str(workout_doc_obj)

        # Calculate total duration from steps
        total_duration = 0
        if "steps" in workout_doc_dict:
            total_duration = _calculate_total_duration(workout_doc_dict["steps"])

        # Add workout_doc as JSON (for structured data)
        workout_data["workout_doc"] = {
            "duration": total_duration,
            "distance": 0,
            "steps": workout_doc_dict.get("steps", [])
        }

        # Add moving_time (shows duration badge in plan view)
        workout_data["moving_time"] = total_duration
    else:
        # No workout_doc, use the provided description
        workout_data["description"] = description

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

    # Return concise summary
    workout_id = result.get("id")
    workout_name = result.get("name")
    duration_mins = result.get("moving_time", 0) // 60
    return f"✓ Added workout '{workout_name}' (ID: {workout_id}, Duration: {duration_mins}min) to plan on day {day}"


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

    # Process each workout: send BOTH text description AND JSON workout_doc
    from intervals_mcp_server.utils.types import WorkoutDoc as WorkoutDocType
    processed_workouts = []
    for workout in workouts:
        workout_copy = workout.copy()

        # If workout has workout_doc, process it
        if "workout_doc" in workout_copy and workout_copy["workout_doc"] is not None:
            workout_doc = workout_copy["workout_doc"]

            # Convert to WorkoutDoc object if needed
            if isinstance(workout_doc, dict):
                workout_doc_obj = WorkoutDocType.from_dict(workout_doc)
                workout_doc_dict = workout_doc
            else:
                workout_doc_obj = workout_doc
                workout_doc_dict = workout_doc.to_dict()

            # Set description as text format
            workout_copy["description"] = str(workout_doc_obj)

            # Calculate total duration from steps
            total_duration = 0
            if "steps" in workout_doc_dict:
                total_duration = _calculate_total_duration(workout_doc_dict["steps"])

            # Replace workout_doc with structured version
            workout_copy["workout_doc"] = {
                "duration": total_duration,
                "distance": 0,
                "steps": workout_doc_dict.get("steps", [])
            }

            # Add moving_time for duration badge in plan view
            workout_copy["moving_time"] = total_duration

        processed_workouts.append(workout_copy)

    # Make API request
    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/workouts/bulk",
        api_key=api_key,
        method="POST",
        data=processed_workouts,
    )

    # Handle errors
    if isinstance(result, dict) and "error" in result:
        error_message = result.get("message", "Unknown error")
        return f"Error adding workouts in bulk: {error_message}"

    # Return concise summary
    if isinstance(result, list):
        count = len(result)
        total_duration_mins = sum(w.get("moving_time", 0) for w in result) // 60
        return f"✓ Added {count} workouts in bulk (Total duration: {total_duration_mins}min)"
    return f"✓ Added workouts in bulk"


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

    # Return concise summary of plans
    if isinstance(result, list):
        plans = [f for f in result if f.get("type") == "PLAN"]
        if not plans:
            return "No training plans found"

        summary = f"Found {len(plans)} training plan(s):\n\n"
        for plan in plans:
            plan_id = plan.get("id")
            plan_name = plan.get("name")
            num_workouts = len(plan.get("children", []))
            start_date = plan.get("start_date_local", "Not set")
            summary += f"• {plan_name} (ID: {plan_id})\n"
            summary += f"  - Workouts: {num_workouts}\n"
            summary += f"  - Start date: {start_date}\n\n"
        return summary
    return "No training plans found"


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
