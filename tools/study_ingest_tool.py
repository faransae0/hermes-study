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
