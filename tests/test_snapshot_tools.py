"""
Unit tests for snapshot tools.

These tests verify that the get_latest_snapshot tool works correctly
and returns properly formatted Section 11 snapshot data.
"""

import asyncio
import json
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
os.environ.setdefault("API_KEY", "test")
os.environ.setdefault("ATHLETE_ID", "i1")

from intervals_mcp_server.server import get_latest_snapshot  # pylint: disable=wrong-import-position
from intervals_mcp_server import server  # pylint: disable=wrong-import-position


def test_get_latest_snapshot_structure(monkeypatch):
    """
    Test get_latest_snapshot returns a valid JSON structure with expected keys.
    """
    # Mock API responses
    async def mock_request(url, api_key=None, params=None):
        if "/activities" in url:
            return []
        if "/wellness" in url:
            return {
                "2024-01-01": {
                    "ctl": 100.0,
                    "atl": 90.0,
                    "tsb": 10.0,
                    "hrv": 50.0,
                    "restingHR": 60.0,
                    "sleepSecs": 28800,
                    "sleepScore": 85,
                    "loadToday": 150,
                }
            }
        if "/events" in url:
            return []
        return {}

    monkeypatch.setattr(server, "httpx_client", None)
    monkeypatch.setattr(
        "intervals_mcp_server.api.client.make_intervals_request",
        mock_request,
    )
    monkeypatch.setattr(
        "intervals_mcp_server.utils.snapshot_builder.make_intervals_request",
        mock_request,
    )

    result = asyncio.run(get_latest_snapshot())

    # Parse JSON result
    data = json.loads(result)

    # Verify top-level keys exist
    assert "READ_THIS_FIRST" in data
    assert "metadata" in data
    assert "alerts" in data
    assert "current_status" in data
    assert "derived_metrics" in data
    assert "recent_activities" in data
    assert "wellness_data" in data
    assert "planned_workouts" in data

    # Verify metadata structure
    assert "athlete_id" in data["metadata"]
    assert "snapshot_date" in data["metadata"]
    assert "window_days" in data["metadata"]

    # Verify current_status structure
    assert "fitness" in data["current_status"]
    assert "wellness" in data["current_status"]


def test_get_latest_snapshot_with_error(monkeypatch):
    """
    Test get_latest_snapshot handles API errors gracefully.
    """
    async def mock_request_error(url, api_key=None, params=None):
        return {"error": True, "message": "API error"}

    monkeypatch.setattr(server, "httpx_client", None)
    monkeypatch.setattr(
        "intervals_mcp_server.api.client.make_intervals_request",
        mock_request_error,
    )
    monkeypatch.setattr(
        "intervals_mcp_server.utils.snapshot_builder.make_intervals_request",
        mock_request_error,
    )

    result = asyncio.run(get_latest_snapshot())

    # Should return error message string
    assert "Error" in result


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-v"]))
