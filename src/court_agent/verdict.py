"""Verdict aggregation + juror-response parsing.

Pure-Python module — no framework imports — so the logic can be unit-tested
without spinning up FastAPI / anet / Anthropic clients.
"""

from __future__ import annotations

import json
from collections import Counter
from typing import Iterable

VALID_VERDICTS = frozenset({"PLAINTIFF", "DEFENDANT", "ABSTAIN"})


def majority_vote(votes: Iterable[str]) -> str:
    """Return the majority verdict.

    Rules:
      - Anything outside VALID_VERDICTS is normalized to ABSTAIN.
      - ABSTAIN votes are excluded from the count.
      - Tie among non-abstain → DEFENDANT (in dubio pro reo).
      - All ABSTAIN (or no votes) → ABSTAIN.
    """
    sanitized = [v if v in VALID_VERDICTS else "ABSTAIN" for v in votes]
    non_abstain = [v for v in sanitized if v != "ABSTAIN"]

    if not non_abstain:
        return "ABSTAIN"

    counts = Counter(non_abstain).most_common()
    if len(counts) > 1 and counts[0][1] == counts[1][1]:
        return "DEFENDANT"
    return counts[0][0]


def parse_juror_response(text: str) -> tuple[str, str]:
    """Robust JSON extraction for juror /vote responses.

    Handles three real failure modes Claude exhibits:
      1. Plain JSON object — happy path
      2. Fenced ```json ... ``` block — strip fences before parsing
      3. JSON embedded in surrounding prose — locate {...} substring

    Returns (verdict, reasoning). Anything that fails to parse → ABSTAIN.
    """
    cleaned = text.strip()

    # Strip ``` / ```json fences
    if cleaned.startswith("```"):
        if cleaned.count("```") >= 2:
            cleaned = cleaned.split("```", 2)[1]
        else:
            cleaned = cleaned[3:]
        if cleaned.lstrip().lower().startswith("json"):
            cleaned = cleaned.lstrip()[4:]
        cleaned = cleaned.strip()

    parsed: dict | None = None
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start != -1 and end > start:
            try:
                parsed = json.loads(cleaned[start : end + 1])
            except json.JSONDecodeError:
                parsed = None

    if not isinstance(parsed, dict):
        return "ABSTAIN", f"could not parse model output: {text[:200]}"

    verdict = str(parsed.get("verdict", "ABSTAIN")).upper()
    if verdict not in VALID_VERDICTS:
        verdict = "ABSTAIN"
    reasoning = str(parsed.get("reasoning", "(no reasoning)"))
    return verdict, reasoning
