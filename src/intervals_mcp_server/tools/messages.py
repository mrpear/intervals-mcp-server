"""Message tools for Intervals.icu activities."""

import json

from intervals_mcp_server.api.client import make_intervals_request
from intervals_mcp_server.mcp_instance import mcp


@mcp.tool()
async def get_activity_messages(
    activity_id: str,
    api_key: str | None = None,
) -> str:
    """Get all messages (comments) for an activity.

    Lists all messages/comments posted on an activity, including the author,
    timestamp, and message content.

    Args:
        activity_id: The activity ID (e.g., "i127117496")
        api_key: The Intervals.icu API key (optional, will use API_KEY from .env if not provided)

    Returns:
        JSON string with list of messages or error message
    """
    result = await make_intervals_request(
        url=f"/activity/{activity_id}/messages",
        api_key=api_key,
    )

    if isinstance(result, dict) and "error" in result:
        return f"Error fetching messages: {result.get('message')}"

    if not result:
        return f"No messages found for activity {activity_id}"

    # Format messages
    if isinstance(result, list):
        return json.dumps(result, indent=2)

    return str(result)


@mcp.tool()
async def add_activity_message(
    activity_id: str,
    content: str,
    api_key: str | None = None,
) -> str:
    """Add a message (comment) to an activity.

    Posts a plain text message/comment on an activity. This is useful for coaches
    to provide feedback or for athletes to add notes about their performance.

    Note: Messages support plain text only (no markdown formatting).

    Args:
        activity_id: The activity ID (e.g., "i127117496")
        content: The message content (plain text)
        api_key: The Intervals.icu API key (optional, will use API_KEY from .env if not provided)

    Returns:
        Success message with message ID or error message
    """
    if not content or not content.strip():
        return "Error: Message content cannot be empty"

    result = await make_intervals_request(
        url=f"/activity/{activity_id}/messages",
        api_key=api_key,
        method="POST",
        data={"content": content.strip()}
    )

    if isinstance(result, dict) and "error" in result:
        return f"Error posting message: {result.get('message')}"

    # Extract message ID from response
    msg_id = result.get("id") if isinstance(result, dict) else None
    if msg_id:
        return f"Message posted successfully (ID: {msg_id})"

    return "Message posted successfully"


@mcp.tool()
async def delete_activity_message(
    activity_id: str,
    message_id: int,
    api_key: str | None = None,
) -> str:
    """Delete a message (comment) from an activity.

    Removes a message/comment that was previously posted on an activity.
    You can only delete messages that you posted.

    Note: This uses the activity's chat ID to delete the message via the
    chats endpoint, as there is no direct DELETE on activity messages.

    Args:
        activity_id: The activity ID (e.g., "i127117496")
        message_id: The message ID to delete (e.g., 3775912)
        api_key: The Intervals.icu API key (optional, will use API_KEY from .env if not provided)

    Returns:
        Success message or error message
    """
    # First, get the activity to retrieve its chat ID
    activity_result = await make_intervals_request(
        url=f"/activity/{activity_id}",
        api_key=api_key,
    )

    if isinstance(activity_result, dict) and "error" in activity_result:
        return f"Error fetching activity: {activity_result.get('message')}"

    # Extract chat ID from activity
    chat_id = activity_result.get("icu_chat_id") if isinstance(activity_result, dict) else None
    if not chat_id:
        return f"Error: Could not find chat ID for activity {activity_id}"

    # Delete the message using the chat endpoint
    result = await make_intervals_request(
        url=f"/chats/{chat_id}/messages/{message_id}",
        api_key=api_key,
        method="DELETE",
    )

    if isinstance(result, dict) and "error" in result:
        return f"Error deleting message: {result.get('message')}"

    return f"Message {message_id} deleted successfully"