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
