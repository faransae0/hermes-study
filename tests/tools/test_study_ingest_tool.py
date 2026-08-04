"""Tests for tools.study_ingest_tool — per-source-type extraction + summarization."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from tools.study_ingest_tool import extract_from_pdf, extract_from_url


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


@pytest.mark.asyncio
async def test_extract_from_pdf_missing_file():
    result = await extract_from_pdf("/no/such/file.pdf")
    assert result["success"] is False
    assert "not found" in result["error"].lower()


@pytest.mark.asyncio
async def test_extract_from_pdf_success(tmp_path):
    fake_pdf = tmp_path / "notes.pdf"
    fake_pdf.write_bytes(b"%PDF-1.4 fake")  # content is irrelevant; pdfplumber.open is mocked

    class FakePage:
        def extract_text(self):
            return "Page one text."

    class FakePdf:
        pages = [FakePage()]

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    with patch("tools.lazy_deps.ensure"), patch("pdfplumber.open", return_value=FakePdf()):
        result = await extract_from_pdf(str(fake_pdf))

    assert result == {"success": True, "text": "Page one text.", "title": "notes.pdf", "error": ""}


@pytest.mark.asyncio
async def test_extract_from_pdf_no_extractable_text(tmp_path):
    fake_pdf = tmp_path / "scanned.pdf"
    fake_pdf.write_bytes(b"%PDF-1.4 fake")

    class FakePage:
        def extract_text(self):
            return None

    class FakePdf:
        pages = [FakePage()]

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    with patch("tools.lazy_deps.ensure"), patch("pdfplumber.open", return_value=FakePdf()):
        result = await extract_from_pdf(str(fake_pdf))

    assert result["success"] is False
    assert "No extractable text" in result["error"]


@pytest.mark.asyncio
async def test_extract_from_pdf_lazy_install_unavailable(tmp_path):
    from tools.lazy_deps import FeatureUnavailable

    fake_pdf = tmp_path / "notes.pdf"
    fake_pdf.write_bytes(b"%PDF-1.4 fake")

    with patch(
        "tools.lazy_deps.ensure",
        side_effect=FeatureUnavailable("study.pdf", ("pdfplumber",), "lazy installs disabled"),
    ):
        result = await extract_from_pdf(str(fake_pdf))

    assert result["success"] is False
    assert "lazy installs disabled" in result["error"]
