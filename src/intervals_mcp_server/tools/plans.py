"""
Training plan-related MCP tools for Intervals.icu.

This module contains tools for creating, managing, and deleting training plans.
"""

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
        description: Plan description (not sent to API, kept for compatibility)
        duration_weeks: Number of weeks in the plan (not sent to API, kept for compatibility)
        start_date: Start date in YYYY-MM-DD format (optional)
        hours_per_week_min: Minimum weekly hours (not sent to API, kept for compatibility)
        hours_per_week_max: Maximum weekly hours (not sent to API, kept for compatibility)
        auto_rollout_day: Day to auto-rollout (0=Sunday, 1=Monday, etc., default: 1)
        athlete_id: The Intervals.icu athlete ID (optional, will use ATHLETE_ID from .env if not provided)
        api_key: The Intervals.icu API key (optional, will use API_KEY from .env if not provided)
    """
    # Resolve athlete ID
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg

    # Build request body - MATCH WEB UI EXACTLY
    plan_data = {
        "name": name,
        "rollout_weeks": 0,  # Web UI uses rollout_weeks, not duration_weeks
        "auto_rollout_day": auto_rollout_day,
        "starting_ctl": -1,  # Web UI sends these
        "starting_atl": -1,
        "type": "PLAN",
    }

    if start_date:
        # Web UI uses ISO timestamp format
        plan_data["start_date_local"] = f"{start_date}T00:00:00"

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
        description: Workout description or notes. If both description and workout_doc
            are provided, they will be combined with description first, then workout structure.
        day: Absolute day from plan start (0=first day, 7=start of week 2, etc.)
        workout_doc: Workout document structure with steps (optional). Will be converted to text
            format and combined with description if both provided.
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
        "targets": ["POWER"],  # Required for TSS/training load calculation
    }

    # Handle workout_doc
    # CRITICAL: Do NOT send workout_doc JSON - it prevents TSS calculation!
    # Instead, convert to text description and let API parse it with targets set
    if workout_doc is not None:
        from intervals_mcp_server.utils.types import WorkoutDoc as WorkoutDocType

        # Convert to WorkoutDoc object if it's a dict
        workout_doc_dict: dict[str, Any]
        if isinstance(workout_doc, dict):
            workout_doc_obj = WorkoutDocType.from_dict(workout_doc)
            workout_doc_dict = workout_doc
        else:
            # Already a WorkoutDoc instance
            workout_doc_obj = workout_doc
            workout_doc_dict = workout_doc.to_dict()

        # Convert workout_doc to text format
        workout_text = str(workout_doc_obj)

        # If both workout_doc and description provided, combine them
        if description:
            workout_data["description"] = f"{description}\n\n{workout_text}"
        else:
            workout_data["description"] = workout_text

        # Calculate total duration from steps
        total_duration = 0
        if "steps" in workout_doc_dict:
            total_duration = _calculate_total_duration(workout_doc_dict["steps"])

        # Add moving_time - this is all we need besides description + targets
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

    # Process each workout: convert to text description
    # NOTE: Do NOT send workout_doc JSON - it breaks TSS calculation!
    from intervals_mcp_server.utils.types import WorkoutDoc as WorkoutDocType
    processed_workouts = []
    for workout in workouts:
        # Add targets if not present (required for TSS/training load calculation)
        if "targets" not in workout:
            workout["targets"] = ["POWER"]

        # If workout has workout_doc, convert to text description
        if "workout_doc" in workout and workout["workout_doc"] is not None:
            workout_doc = workout["workout_doc"]

            # Convert to WorkoutDoc object if needed
            if isinstance(workout_doc, dict):
                workout_doc_obj = WorkoutDocType.from_dict(workout_doc)
                workout_doc_dict = workout_doc
            else:
                workout_doc_obj = workout_doc
                workout_doc_dict = workout_doc.to_dict()

            # Convert workout_doc to text format
            workout_text = str(workout_doc_obj)

            # If both workout_doc and description provided, combine them
            existing_description = workout.get("description", "")
            if existing_description:
                workout["description"] = f"{existing_description}\n\n{workout_text}"
            else:
                workout["description"] = workout_text

            # Calculate total duration from steps
            total_duration = 0
            if "steps" in workout_doc_dict:
                total_duration = _calculate_total_duration(workout_doc_dict["steps"])

            # Add moving_time - this is all we need besides description + targets
            workout["moving_time"] = total_duration

            # Remove workout_doc from payload - prevents TSS calculation
            del workout["workout_doc"]

        processed_workouts.append(workout)

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
    return "✓ Added workouts in bulk"


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
async def get_plan_workouts(
    plan_id: int,
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """Get all workout templates from a specific training plan

    Args:
        plan_id: ID of the training plan folder
        athlete_id: The Intervals.icu athlete ID (optional, will use ATHLETE_ID from .env if not provided)
        api_key: The Intervals.icu API key (optional, will use API_KEY from .env if not provided)
    """
    # Resolve athlete ID
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg

    # Make API request to get all folders
    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/folders",
        api_key=api_key,
        method="GET",
    )

    # Handle errors
    if isinstance(result, dict) and "error" in result:
        error_message = result.get("message", "Unknown error")
        return f"Error fetching plan workouts: {error_message}"

    # Find the specific plan
    if isinstance(result, list):
        plan = next((f for f in result if f.get("id") == plan_id), None)
        if not plan:
            return f"Training plan with ID {plan_id} not found"

        plan_name = plan.get("name", "Unknown")
        workouts = plan.get("children", [])

        if not workouts:
            return f"No workouts found in plan '{plan_name}' (ID: {plan_id})"

        # Format workout details
        summary = f"Training Plan: {plan_name} (ID: {plan_id})\n"
        summary += f"Total Workouts: {len(workouts)}\n\n"

        for workout in workouts:
            workout_id = workout.get("id")
            workout_name = workout.get("name", "Unnamed")
            day = workout.get("day", 0)
            workout_type = workout.get("type", "Unknown")
            moving_time = workout.get("moving_time", 0)
            duration_mins = moving_time // 60 if moving_time else 0
            description = workout.get("description", "")

            summary += f"Day {day}: {workout_name}\n"
            summary += f"  ID: {workout_id}\n"
            summary += f"  Type: {workout_type}\n"
            summary += f"  Duration: {duration_mins}min\n"
            if description:
                # Truncate long descriptions
                desc_preview = description[:100] + "..." if len(description) > 100 else description
                summary += f"  Description: {desc_preview}\n"
            summary += "\n"

        return summary

    return f"Error: Unexpected response format when fetching plan {plan_id}"


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
