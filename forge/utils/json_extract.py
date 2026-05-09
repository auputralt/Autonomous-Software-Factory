"""Robust JSON extraction from noisy LLM outputs."""

from __future__ import annotations

import json
import re
from typing import Any


def extract_json(text: str) -> Any:
    """Finds and parses the first valid JSON object or array in a string."""
    # Attempt 1: Direct Parse
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass

    # Attempt 2: Code Fences
    fence_pattern = r"```(?:json)?\s*([\s\S]*?)\s*```"
    match = re.search(fence_pattern, text)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Attempt 3: Greedy Brace Matching (Deep Search)
    for open_char, close_char in [("{", "}"), ("[", "]")]:
        start = text.find(open_char)
        if start == -1:
            continue

        # Scan from end to start to find the widest possible match
        end = text.rfind(close_char)
        while end > start:
            try:
                snippet = text[start : end + 1]
                return json.loads(snippet)
            except json.JSONDecodeError:
                end = text.rfind(close_char, start, end)

    raise ValueError("LLM response contained no valid JSON structure.")
