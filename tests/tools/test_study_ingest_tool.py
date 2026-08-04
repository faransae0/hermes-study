"""Tests for tools.study_ingest_tool — per-source-type extraction + summarization."""

import json
from unittest.mock import AsyncMock, patch

import pytest

from tools.study_ingest_tool import extract_from_url


@pytest.mark.asyncio
async def test_extract_from_url_success():
    fake_response = json.dumps(
        {"results": [{"url": "https://example.com", "title": "Example Page", "content": "Hello world", "error": ""}]}
    )
    with patch("tools.web_tools.web_extract_tool", new=AsyncMock(return_value=fake_response)):
        result = await extract_from_url("https://example.com")

    assert result == {"success": True, "text": "Hello world", "title": "Example Page", "error": ""}


@pytest.mark.asyncio
async def test_extract_from_url_per_page_error():
    fake_response = json.dumps(
        {"results": [{"url": "https://example.com", "title": "", "content": "", "error": "404 Not Found"}]}
    )
    with patch("tools.web_tools.web_extract_tool", new=AsyncMock(return_value=fake_response)):
        result = await extract_from_url("https://example.com")

    assert result["success"] is False
    assert result["error"] == "404 Not Found"


@pytest.mark.asyncio
async def test_extract_from_url_blocked_before_results():
    fake_response = json.dumps({"success": False, "error": "Blocked: URL contains what appears to be an API key"})
    with patch("tools.web_tools.web_extract_tool", new=AsyncMock(return_value=fake_response)):
        result = await extract_from_url("https://example.com?token=sk-1234")

    assert result["success"] is False
    assert "Blocked" in result["error"]


@pytest.mark.asyncio
async def test_extract_from_url_non_json_response():
    with patch("tools.web_tools.web_extract_tool", new=AsyncMock(return_value="not json")):
        result = await extract_from_url("https://example.com")

    assert result["success"] is False
    assert "non-JSON" in result["error"]
