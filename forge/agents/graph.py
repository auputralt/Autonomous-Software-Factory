"""LangGraph workflow orchestration — the 'Brain' of Forge."""

from __future__ import annotations

import logging

from langgraph.graph import END, StateGraph

from forge.agents.developer import developer_node
from forge.agents.executor import executor_node
from forge.agents.manager import manager_node
from forge.agents.packager import packager_node
from forge.agents.state import BuildState
from forge.agents.tester import tester_node
from forge.utils.progress import publish_result, publish_progress

logger = logging.getLogger(__name__)


def should_continue(state: BuildState) -> str:
    """Conditional router determining the next step in the loop."""
    if state["status"] == "success":
        return "package"

    if state["attempt"] >= state["max_attempts"]:
        return "fail"

    return "retry"


def build_graph():
    """Compiles the agent nodes into a cyclical workflow."""
    workflow = StateGraph(BuildState)

    # Add Nodes
    workflow.add_node("manager", manager_node)
    workflow.add_node("developer", developer_node)
    workflow.add_node("tester", tester_node)
    workflow.add_node("executor", executor_node)
    workflow.add_node("packager", packager_node)

    # Define Linear Path
    workflow.set_entry_point("manager")
    workflow.add_edge("manager", "developer")
    workflow.add_edge("developer", "tester")
    workflow.add_edge("tester", "executor")

    # Define Conditional Loop (Self-Correction)
    workflow.add_conditional_edges(
        "executor",
        should_continue,
        {
            "retry": "developer",
            "package": "packager",
            "fail": END,
        },
    )

    workflow.add_edge("packaging", END)

    return workflow.compile()


async def run_build(request_id: str, user_prompt: str, max_attempts: int = 5) -> BuildState:
    """Entry point to execute a full build pipeline."""
    graph = build_graph()

    initial_state: BuildState = {
        "request_id": request_id,
        "user_prompt": user_prompt,
        "blueprint": None,
        "source_files": None,
        "test_files": None,
        "execution_report": None,
        "attempt": 0,
        "max_attempts": max_attempts,
        "error_feedback": None,
        "status": "starting",
        "download_url": None,
    }

    try:
        # Run the graph
        result = await graph.ainvoke(initial_state)
    except Exception as exc:
        logger.exception("Pipeline Crash: Request %s", request_id)
        publish_progress(request_id, "error", f"Pipeline encountered a fatal error: {exc}")
        publish_result(request_id, "failed", {"error": str(exc)})
        raise

    # Final Outcome Handling
    if result.get("status") == "success":
        publish_result(request_id, "success", {
            "download_url": result.get("download_url", ""),
            "attempts": result.get("attempt", 0),
        })
    else:
        publish_result(request_id, "failed", {
            "error": "Failed to pass tests after maximum retries.",
            "attempts": result.get("attempt", 0),
        })

    return result
