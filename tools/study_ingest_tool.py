"""Source-type extraction + summarization for study-desktop.

Each extractor normalizes its underlying tool's return shape into a common
{"success": bool, "text": str, "title": str, "error": str} dict. All
extractors are `async def` for interface parity with web_extract_tool, even
where the underlying work is synchronous (pdfplumber, yt-dlp,
transcribe_audio) — see the Global Constraints note in this plan for why
that's acceptable in Phase 1.
"""

from __future__ import annotations

import json
import logging
import re
import tempfile
from typing import Any, Dict

logger = logging.getLogger(__name__)


async def extract_from_url(url: str, *, char_limit: int = 15000) -> Dict[str, Any]:
    """Extract clean page text from a single URL via the shared web_extract_tool."""
    from tools.web_tools import web_extract_tool

    raw = await web_extract_tool([url], format="markdown", char_limit=char_limit)

    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError) as exc:
        return {"success": False, "text": "", "title": "", "error": f"web_extract_tool returned non-JSON: {exc}"}

    if "results" not in parsed:
        # Blocked before any per-URL result was produced (secret in URL, SSRF, etc.)
        return {
            "success": False,
            "text": "",
            "title": "",
            "error": parsed.get("error") or "web_extract_tool blocked the request",
        }

    results = parsed.get("results") or []
    if not results:
        return {"success": False, "text": "", "title": "", "error": "web_extract_tool returned no results"}

    entry = results[0]
    if entry.get("error"):
        return {"success": False, "text": "", "title": entry.get("title", ""), "error": entry["error"]}

    return {"success": True, "text": entry.get("content", ""), "title": entry.get("title", ""), "error": ""}


async def extract_from_pdf(file_path: str) -> Dict[str, Any]:
    """Extract text from a local PDF file via pdfplumber (lazy-installed)."""
    from pathlib import Path

    from tools import lazy_deps

    path = Path(file_path)
    if not path.is_file():
        return {"success": False, "text": "", "title": path.name, "error": f"File not found: {file_path}"}

    try:
        lazy_deps.ensure("study.pdf", prompt=False)
    except lazy_deps.FeatureUnavailable as exc:
        return {"success": False, "text": "", "title": path.name, "error": str(exc)}

    import pdfplumber

    try:
        pages = []
        with pdfplumber.open(str(path)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                if page_text.strip():
                    pages.append(page_text)
    except Exception as exc:
        return {"success": False, "text": "", "title": path.name, "error": f"PDF extraction failed: {exc}"}

    text = "\n\n".join(pages).strip()
    if not text:
        return {
            "success": False,
            "text": "",
            "title": path.name,
            "error": "No extractable text found (possibly a scanned/image-only PDF; OCR not supported yet)",
        }

    return {"success": True, "text": text, "title": path.name, "error": ""}


_VTT_TS_RE = re.compile(
    r"(\d{2}):(\d{2}):(\d{2})[.,](\d{3})\s+-->\s+(\d{2}):(\d{2}):(\d{2})[.,](\d{3})"
)
_VTT_TAG_RE = re.compile(r"<[^>]+>")


def _parse_vtt(vtt_path: str) -> str:
    """Parse a WebVTT subtitle file into deduplicated plain text.

    YouTube auto-captions emit rolling-duplicate cues (each line appears
    2-3 times as it scrolls); consecutive identical/prefix cues are
    merged. Adapted from the /watch Claude Code skill's transcribe.py
    dedupe logic.
    """
    from pathlib import Path

    lines = Path(vtt_path).read_text(encoding="utf-8", errors="ignore").splitlines()
    cues: list[str] = []
    i = 0
    while i < len(lines):
        if not _VTT_TS_RE.match(lines[i]):
            i += 1
            continue
        i += 1
        cue_lines = []
        while i < len(lines) and lines[i].strip():
            cleaned = _VTT_TAG_RE.sub("", lines[i]).strip()
            if cleaned:
                cue_lines.append(cleaned)
            i += 1
        cue_text = " ".join(cue_lines).strip()
        if cue_text:
            if cues and cue_text == cues[-1]:
                pass
            elif cues and cue_text.startswith(cues[-1] + " "):
                cues[-1] = cue_text
            else:
                cues.append(cue_text)
        i += 1
    return "\n".join(cues)


async def extract_from_youtube(url: str) -> Dict[str, Any]:
    """Extract a transcript from a YouTube/video URL: captions first, audio+STT fallback."""
    from pathlib import Path

    from tools import lazy_deps

    try:
        lazy_deps.ensure("study.youtube", prompt=False)
    except lazy_deps.FeatureUnavailable as exc:
        return {"success": False, "text": "", "title": "", "error": str(exc)}

    import yt_dlp

    with tempfile.TemporaryDirectory(prefix="hermes-study-yt-") as tmpdir:
        tmp_path = Path(tmpdir)
        title = ""

        caption_opts = {
            "skip_download": True,
            "writesubtitles": True,
            "writeautomaticsub": True,
            "subtitleslangs": ["en"],
            "subtitlesformat": "vtt",
            "outtmpl": str(tmp_path / "video.%(ext)s"),
            "quiet": True,
            "no_warnings": True,
        }
        try:
            with yt_dlp.YoutubeDL(caption_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                title = (info or {}).get("title", "")
        except Exception as exc:
            return {"success": False, "text": "", "title": "", "error": f"yt-dlp caption fetch failed: {exc}"}

        vtt_files = sorted(tmp_path.glob("*.vtt"))
        if vtt_files:
            text = _parse_vtt(str(vtt_files[0]))
            if text.strip():
                return {"success": True, "text": text, "title": title, "error": ""}

        # No usable captions — fall back to downloading audio and transcribing it.
        audio_opts = {
            "format": "bestaudio/best",
            "outtmpl": str(tmp_path / "audio.%(ext)s"),
            "quiet": True,
            "no_warnings": True,
        }
        try:
            with yt_dlp.YoutubeDL(audio_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                title = title or (info or {}).get("title", "")
        except Exception as exc:
            return {"success": False, "text": "", "title": title, "error": f"yt-dlp audio download failed: {exc}"}

        audio_files = list(tmp_path.glob("audio.*"))
        if not audio_files:
            return {
                "success": False,
                "text": "",
                "title": title,
                "error": "No captions available and audio download produced no file",
            }

        from tools.transcription_tools import transcribe_audio

        transcription = transcribe_audio(str(audio_files[0]))
        if not transcription.get("success"):
            return {
                "success": False,
                "text": "",
                "title": title,
                "error": transcription.get("error") or "Transcription failed",
            }

        return {"success": True, "text": transcription.get("transcript", ""), "title": title, "error": ""}
