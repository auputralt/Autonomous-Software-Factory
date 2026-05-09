"""Developer agent — generates source code from a blueprint."""

from __future__ import annotations

import json
import logging

from forge.agents.llm import call_gemini
from forge.agents.prompts import DEVELOPER_SYSTEM_INSTRUCTION
from forge.agents.state import BuildState
from forge.config import settings
from forge.utils.json_extract import extract_json
from forge.utils.progress import publish_progress

logger = logging.getLogger(__name__)


async def developer_node(state: BuildState) -> dict:
    request_id = state["request_id"]
    attempt = state.get("attempt", 0)

    if attempt == 0:
        publish_progress(request_id, "generating", "Writing source code…")
    else:
        publish_progress(
            request_id,
            "generating",
            f"Re-writing source code (attempt {attempt + 1})…",
        )

    # Build error feedback block if retrying
    feedback_block = ""
    if state.get("error_feedback"):
        feedback_block = (
            "\n\nPREVIOUS ATTEMPT FAILED. Fix the issues below:\n"
            f"{state['error_feedback']}\n"
        )

    prompt = (
        f"BLUEPRINT:\n{json.dumps(state['blueprint'], indent=2)}\n"
        f"{feedback_block}\n\n"
        "OUTPUT FORMAT: Return a JSON object mapping filenames to source code strings."
    )

    raw = await call_gemini(
        prompt=prompt,
        system_instruction=DEVELOPER_SYSTEM_INSTRUCTION,
        model_name=settings.DEVELOPER_MODEL,
        temperature=0.2,
    )

    try:
        source_files = extract_json(raw)
    except Exception as exc:
        logger.error("Developer failed to output valid JSON: %s", exc)
        raise ValueError("Developer agent returned invalid JSON.") from exc

    publish_progress(
        request_id,
        "generating",
        f"Generated {len(source_files)} source file(s).",
    )

    return {
        "source_files": source_files,
        "status": "code_complete",
        "error_feedback": None,  # Clear after consumption
    }
