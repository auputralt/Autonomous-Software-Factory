"""Tester agent — generates pytest-compatible test files."""

from __future__ import annotations

import json
import logging

from forge.agents.llm import call_gemini
from forge.agents.prompts import TESTER_SYSTEM_INSTRUCTION
from forge.agents.state import BuildState
from forge.config import settings
from forge.utils.json_extract import extract_json
from forge.utils.progress import publish_progress

logger = logging.getLogger(__name__)


async def tester_node(state: BuildState) -> dict:
    request_id = state["request_id"]
    publish_progress(request_id, "testing", "Writing test suite…")

    prompt = (
        f"BLUEPRINT:\n{json.dumps(state['blueprint'], indent=2)}\n\n"
        f"SOURCE CODE:\n{json.dumps(state['source_files'], indent=2)}\n\n"
        "OUTPUT FORMAT: Return a JSON object mapping test filenames to source code strings."
    )

    raw = await call_gemini(
        prompt=prompt,
        system_instruction=TESTER_SYSTEM_INSTRUCTION,
        model_name=settings.TESTER_MODEL,
        temperature=0.2,
    )

    try:
        test_files = extract_json(raw)
    except Exception as exc:
        logger.error("Tester failed to output valid JSON: %s", exc)
        raise ValueError("Tester agent returned invalid JSON.") from exc

    publish_progress(
        request_id,
        "testing",
        f"Generated {len(test_files)} test file(s).",
    )

    return {
        "test_files": test_files,
        "status": "tests_complete",
    }
