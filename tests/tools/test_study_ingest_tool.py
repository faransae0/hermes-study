"""Tests for tools.study_ingest_tool — per-source-type extraction + summarization."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from tools.study_ingest_tool import _parse_vtt, extract_from_pdf, extract_from_url, extract_from_youtube, summarize_source


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
    pytest.importorskip("pdfplumber")  # optional dep; lazy-installed
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
    pytest.importorskip("pdfplumber")  # optional dep; lazy-installed
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


def test_parse_vtt_dedupes_rolling_captions(tmp_path):
    vtt_path = tmp_path / "captions.vtt"
    vtt_path.write_text(
        "WEBVTT\n\n"
        "00:00:00.000 --> 00:00:02.000\n"
        "Hello there\n\n"
        "00:00:02.000 --> 00:00:04.000\n"
        "Hello there\n\n"
        "00:00:04.000 --> 00:00:06.000\n"
        "Hello there general\n\n",
        encoding="utf-8",
    )

    text = _parse_vtt(str(vtt_path))
    assert text == "Hello there general"


@pytest.mark.asyncio
async def test_extract_from_youtube_uses_captions_when_available(tmp_path):
    pytest.importorskip("yt_dlp")  # optional dep; lazy-installed

    def fake_extract_info(self, url, download=True):
        # Simulate yt-dlp writing a caption file into the configured outtmpl dir.
        out_dir = Path(self.params["outtmpl"]["default"]).parent
        (out_dir / "video.en.vtt").write_text(
            "WEBVTT\n\n00:00:00.000 --> 00:00:02.000\nCaptioned content\n\n", encoding="utf-8"
        )
        return {"title": "My Video"}

    with patch("tools.lazy_deps.ensure"), patch("yt_dlp.YoutubeDL.extract_info", new=fake_extract_info):
        result = await extract_from_youtube("https://youtube.com/watch?v=abc123")

    assert result == {"success": True, "text": "Captioned content", "title": "My Video", "error": ""}


@pytest.mark.asyncio
async def test_extract_from_youtube_falls_back_to_audio_transcription(tmp_path):
    pytest.importorskip("yt_dlp")  # optional dep; lazy-installed
    call_count = {"n": 0}

    def fake_extract_info(self, url, download=True):
        call_count["n"] += 1
        out_dir = Path(self.params["outtmpl"]["default"]).parent
        if call_count["n"] == 2:
            # Second call is the audio-only download pass.
            (out_dir / "audio.m4a").write_bytes(b"fake audio bytes")
        return {"title": "No Captions Video"}

    fake_transcribe_result = {"success": True, "transcript": "Transcribed speech.", "error": ""}

    with (
        patch("tools.lazy_deps.ensure"),
        patch("yt_dlp.YoutubeDL.extract_info", new=fake_extract_info),
        patch("tools.transcription_tools.transcribe_audio", return_value=fake_transcribe_result),
    ):
        result = await extract_from_youtube("https://youtube.com/watch?v=noCaptions")

    assert result == {"success": True, "text": "Transcribed speech.", "title": "No Captions Video", "error": ""}


@pytest.mark.asyncio
async def test_extract_from_youtube_lazy_install_unavailable():
    from tools.lazy_deps import FeatureUnavailable

    with patch(
        "tools.lazy_deps.ensure",
        side_effect=FeatureUnavailable("study.youtube", ("yt-dlp",), "lazy installs disabled"),
    ):
        result = await extract_from_youtube("https://youtube.com/watch?v=abc123")

    assert result["success"] is False
    assert "lazy installs disabled" in result["error"]


@pytest.mark.asyncio
async def test_summarize_source_success():
    fake_llm_json = json.dumps(
        {
            "one_line_summary": "Newton's laws describe motion.",
            "key_concepts": ["inertia", "force", "momentum"],
            "detailed_markdown": "## Overview\n\nNewton's three laws...",
        }
    )

    fake_message = type("Msg", (), {"content": fake_llm_json})
    fake_choice = type("Choice", (), {"message": fake_message})
    fake_response = type("Response", (), {"choices": [fake_choice]})

    fake_client = AsyncMock()
    fake_client.chat.completions.create = AsyncMock(return_value=fake_response)

    with (
        patch("tools.openrouter_client.check_api_key", return_value=True),
        patch("tools.openrouter_client.get_async_client", return_value=fake_client),
    ):
        result = await summarize_source("Newton's laws of motion...", "Physics 101")

    assert result["success"] is True
    assert "Newton's laws describe motion." in result["summary_md"]
    assert "## Overview" in result["summary_md"]
    assert result["key_concepts"] == ["inertia", "force", "momentum"]


@pytest.mark.asyncio
async def test_summarize_source_no_api_key():
    with patch("tools.openrouter_client.check_api_key", return_value=False):
        result = await summarize_source("some text", "Some Title")

    assert result["success"] is False
    assert "OPENROUTER_API_KEY" in result["error"]


@pytest.mark.asyncio
async def test_summarize_source_empty_text():
    result = await summarize_source("", "Some Title")
    assert result["success"] is False
    assert "No text" in result["error"]


@pytest.mark.asyncio
async def test_summarize_source_llm_non_json_response():
    fake_message = type("Msg", (), {"content": "not json"})
    fake_choice = type("Choice", (), {"message": fake_message})
    fake_response = type("Response", (), {"choices": [fake_choice]})

    fake_client = AsyncMock()
    fake_client.chat.completions.create = AsyncMock(return_value=fake_response)

    with (
        patch("tools.openrouter_client.check_api_key", return_value=True),
        patch("tools.openrouter_client.get_async_client", return_value=fake_client),
    ):
        result = await summarize_source("some text", "Some Title")

    assert result["success"] is False
    assert "non-JSON" in result["error"]


from pathlib import Path as _Path

import study_state as state
from tools.study_ingest_tool import ingest_source


@pytest.fixture
def ingest_db_path(tmp_path):
    return tmp_path / "study.db"


@pytest.mark.asyncio
async def test_ingest_source_end_to_end_success(ingest_db_path, tmp_path, monkeypatch):
    subject_id = state.create_subject("Astronomy", db_path=ingest_db_path)

    monkeypatch.setattr(
        "tools.study_ingest_tool.extract_from_url",
        AsyncMock(return_value={"success": True, "text": "Stars are big.", "title": "Stars 101", "error": ""}),
    )
    monkeypatch.setattr(
        "tools.study_ingest_tool.summarize_source",
        AsyncMock(
            return_value={
                "success": True,
                "summary_md": "**Stars are big.**\n\nDetails.",
                "key_concepts": ["stars", "fusion"],
                "error": "",
            }
        ),
    )
    # Route the raw-text cache into tmp_path instead of the real hermes home.
    monkeypatch.setattr("hermes_constants.get_hermes_home", lambda: tmp_path)

    result = await ingest_source(subject_id, "url", "https://example.com/stars", db_path=ingest_db_path)

    assert result == {"success": True, "source_id": result["source_id"], "error": ""}

    source = state.get_source(result["source_id"], db_path=ingest_db_path)
    assert source["status"] == "ready"
    assert source["raw_text_path"] is not None
    assert _Path(source["raw_text_path"]).read_text(encoding="utf-8") == "Stars are big."

    note = state.get_note_for_source(result["source_id"], db_path=ingest_db_path)
    assert note["summary_md"] == "**Stars are big.**\n\nDetails."
    assert note["key_concepts"] == ["stars", "fusion"]


@pytest.mark.asyncio
async def test_ingest_source_extraction_failure_marks_source_error(ingest_db_path):
    subject_id = state.create_subject("Astronomy", db_path=ingest_db_path)

    with patch(
        "tools.study_ingest_tool.extract_from_url",
        new=AsyncMock(return_value={"success": False, "text": "", "title": "", "error": "404 Not Found"}),
    ):
        result = await ingest_source(subject_id, "url", "https://example.com/broken", db_path=ingest_db_path)

    assert result == {"success": False, "source_id": result["source_id"], "error": "404 Not Found"}
    source = state.get_source(result["source_id"], db_path=ingest_db_path)
    assert source["status"] == "error"
    assert source["error_message"] == "404 Not Found"
    assert state.get_note_for_source(result["source_id"], db_path=ingest_db_path) is None


@pytest.mark.asyncio
async def test_ingest_source_summarization_failure_preserves_extracted_text(ingest_db_path, tmp_path, monkeypatch):
    subject_id = state.create_subject("Astronomy", db_path=ingest_db_path)

    monkeypatch.setattr(
        "tools.study_ingest_tool.extract_from_url",
        AsyncMock(return_value={"success": True, "text": "Stars are big.", "title": "Stars 101", "error": ""}),
    )
    monkeypatch.setattr(
        "tools.study_ingest_tool.summarize_source",
        AsyncMock(return_value={"success": False, "summary_md": "", "key_concepts": [], "error": "LLM call failed"}),
    )
    monkeypatch.setattr("hermes_constants.get_hermes_home", lambda: tmp_path)

    result = await ingest_source(subject_id, "url", "https://example.com/stars", db_path=ingest_db_path)

    assert result["success"] is False
    assert result["error"] == "LLM call failed"
    source = state.get_source(result["source_id"], db_path=ingest_db_path)
    assert source["status"] == "error"
    # Extraction had already succeeded — raw text must still be cached, per the
    # "extraction succeeded, only retry summary" error-handling rule in the spec.
    assert source["raw_text_path"] is not None
    assert _Path(source["raw_text_path"]).read_text(encoding="utf-8") == "Stars are big."


@pytest.mark.asyncio
async def test_ingest_source_unknown_type_rejected(ingest_db_path):
    subject_id = state.create_subject("Astronomy", db_path=ingest_db_path)

    result = await ingest_source(subject_id, "carrier-pigeon", "n/a", db_path=ingest_db_path)

    assert result == {"success": False, "source_id": "", "error": "Unknown source type: carrier-pigeon"}


@pytest.mark.asyncio
async def test_ingest_source_unexpected_extractor_exception_marks_source_error(ingest_db_path):
    subject_id = state.create_subject("Astronomy", db_path=ingest_db_path)

    with patch(
        "tools.study_ingest_tool.extract_from_url",
        new=AsyncMock(side_effect=RuntimeError("kaboom")),
    ):
        result = await ingest_source(subject_id, "url", "https://example.com/broken", db_path=ingest_db_path)

    assert result["success"] is False
    assert "kaboom" in result["error"]

    source = state.get_source(result["source_id"], db_path=ingest_db_path)
    # Must land on "error", not be stranded at the last successfully-set
    # status ("extracting") from before the exception was raised.
    assert source["status"] == "error"
    assert "kaboom" in source["error_message"]


@pytest.mark.asyncio
async def test_ingest_source_nonexistent_subject_id_returns_clean_failure(ingest_db_path):
    result = await ingest_source("does-not-exist", "url", "https://example.com", db_path=ingest_db_path)

    assert result["success"] is False
    assert result["source_id"] == ""
    assert "Failed to create source" in result["error"]


@pytest.mark.asyncio
async def test_ingest_source_caches_raw_text_under_db_path_not_hermes_home(ingest_db_path, tmp_path, monkeypatch):
    subject_id = state.create_subject("Astronomy", db_path=ingest_db_path)

    # Decoy: get_hermes_home() points somewhere entirely different from
    # ingest_db_path's parent, so the assertion below actually discriminates
    # between "used db_path" and "fell back to get_hermes_home()".
    decoy_home = tmp_path / "decoy-hermes-home"
    monkeypatch.setattr("hermes_constants.get_hermes_home", lambda: decoy_home)

    monkeypatch.setattr(
        "tools.study_ingest_tool.extract_from_url",
        AsyncMock(return_value={"success": True, "text": "Stars are big.", "title": "Stars 101", "error": ""}),
    )
    monkeypatch.setattr(
        "tools.study_ingest_tool.summarize_source",
        AsyncMock(
            return_value={
                "success": True,
                "summary_md": "**Stars are big.**\n\nDetails.",
                "key_concepts": ["stars", "fusion"],
                "error": "",
            }
        ),
    )

    result = await ingest_source(subject_id, "url", "https://example.com/stars", db_path=ingest_db_path)

    assert result["success"] is True
    source = state.get_source(result["source_id"], db_path=ingest_db_path)
    raw_text_path = _Path(source["raw_text_path"])

    assert raw_text_path.is_relative_to(ingest_db_path.parent)
    assert not raw_text_path.is_relative_to(decoy_home)
