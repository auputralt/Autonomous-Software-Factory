"""Project Manager agent — translates user prompt into a JSON blueprint."""

from __future__ import annotations

import logging

from forge.agents.llm import call_gemini
from forge.agents.prompts import MANAGER_SYSTEM_INSTRUCTION
from forge.agents.state import BuildState
from forge.config import settings
from forge.utils.json_extract import extract_json
from forge.utils.progress import publish_progress

logger = logging.getLogger(__name__)


async def manager_node(state: BuildState) -> dict:
    request_id = state["request_id"]
    publish_progress(request_id, "planning", "Analysing your requirements…")

    prompt = f"USER REQUEST:\n{state['user_prompt']}"

    raw = await call_gemini(
        prompt=prompt,
        system_instruction=MANAGER_SYSTEM_INSTRUCTION,
        model_name=settings.MANAGER_MODEL,
        temperature=0.3,
    )

    try:
        blueprint = extract_json(raw)
    except Exception as exc:
        logger.error("Manager failed to parse blueprint: %s\nRaw: %s", exc, raw[:500])
        raise ValueError("Manager agent returned invalid JSON.") from exc

    project_name = blueprint.get("project_name", "project")
    file_count = len(blueprint.get("files", []))
    publish_progress(
        request_id,
        "planning",
        f"Blueprint ready: {project_name} ({file_count} files)",
    )

    return {
        "blueprint": blueprint,
        "status": "planning_complete",
    }
