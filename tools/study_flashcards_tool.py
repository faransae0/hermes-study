"""LLM-backed flashcard generation for study-desktop.

Given a study note's full content, generates question/answer flashcard
pairs via the study_flashcards auxiliary LLM task — the same call_llm()
mechanism tools/study_ingest_tool.py's summarize_source() uses, never a raw
provider client.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


FLASHCARDS_SYSTEM_PROMPT = """You are a study-flashcards assistant. Given a study note's content, produce 3-7 flashcards that test genuine understanding of the material, not just term recall.

Each flashcard is a question/answer pair: a specific, answerable question on the front, and a concise, correct answer on the back.

Respond as JSON: {"cards": [{"front": str, "back": str}, ...]}. Output ONLY the JSON object, no other text."""


async def generate_flashcards(text: str, title: str) -> Dict[str, Any]:
    """Generate flashcards from a study note's content via the study_flashcards auxiliary task."""
    if not text.strip():
        return {"success": False, "cards": [], "error": "No text to generate flashcards from"}

    try:
        from agent.auxiliary_client import call_llm, extract_content_or_reasoning

        response = call_llm(
            task="study_flashcards",
            messages=[
                {"role": "system", "content": FLASHCARDS_SYSTEM_PROMPT},
                {"role": "user", "content": f"# {title}\n\n{text[:60000]}"},
            ],
            timeout=120,
        )
        raw = extract_content_or_reasoning(response)
    except Exception as exc:
        return {"success": False, "cards": [], "error": f"LLM call failed: {exc}"}

    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError) as exc:
        return {"success": False, "cards": [], "error": f"LLM returned non-JSON: {exc}"}

    cards = parsed.get("cards", [])
    if not isinstance(cards, list) or not cards:
        return {"success": False, "cards": [], "error": "LLM returned no flashcards"}

    valid_cards = [
        {"front": c["front"], "back": c["back"]}
        for c in cards
        if isinstance(c, dict) and c.get("front") and c.get("back")
    ]
    if not valid_cards:
        return {"success": False, "cards": [], "error": "LLM returned no valid flashcards"}

    return {"success": True, "cards": valid_cards, "error": ""}
