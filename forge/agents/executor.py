"""Executor node — runs the sandbox and evaluates results."""

from __future__ import annotations

import logging

from forge.agents.state import BuildState
from forge.config import settings
from forge.sandbox.runner import run_sandbox
from forge.utils.progress import publish_progress

logger = logging.getLogger(__name__)


def _format_error_feedback(report: dict) -> str:
    """Build a precise error summary for the Developer agent to use for fixes."""
    lines: list[str] = []

    if report.get("timed_out"):
        return "EXECUTION TIMED OUT — Possible infinite loop or inefficient logic detected."

    tests = report.get("tests", [])
    failed_tests = [t for t in tests if t["status"] in ("failed", "error")]

    if not failed_tests and report.get("exit_code", 0) != 0:
        # System-level crash outside of pytest
        stderr = report.get("stderr", "")
        lines.append("SYSTEM CRASH DETECTED:")
        lines.append(stderr[-1000:])  # Last 1k chars of stderr
    else:
        for t in failed_tests:
            lines.append(f"FAILED: {t['name']}")
            if t.get("message"):
                lines.append(f"ERROR DETAIL: {t['message']}")
            lines.append("-" * 20)

    return "\n".join(lines) if lines else "Unknown failure in execution."


async def executor_node(state: BuildState) -> dict:
    request_id = state["request_id"]
    publish_progress(request_id, "executing", "Running code in isolated sandbox…")

    # The runner (from Part 4) chooses Rust sandbox or Python fallback
    report = run_sandbox(
        state["source_files"],
        state["test_files"],
        timeout_secs=settings.SANDBOX_TIMEOUT_SECS,
        max_memory_mb=settings.SANDBOX_MAX_MEMORY_MB,
    )

    tests = report.get("tests", [])
    total = len(tests)
    passed = sum(1 for t in tests if t["status"] == "passed")
    new_attempt = state.get("attempt", 0) + 1

    if total > 0 and all(t["status"] == "passed" for t in tests):
        publish_progress(
            request_id,
            "executing",
            f"Build Validated: {passed}/{total} tests passed on attempt {new_attempt}.",
        )
        return {
            "execution_report": report,
            "attempt": new_attempt,
            "status": "success",
            "error_feedback": None,
        }

    # If we get here, tests failed
    feedback = _format_error_feedback(report)
    publish_progress(
        request_id,
        "executing",
        f"Validation Failed: {passed}/{total} passed. Retrying (Attempt {new_attempt}/{state['max_attempts']})…",
    )

    return {
        "execution_report": report,
        "attempt": new_attempt,
        "error_feedback": feedback,
        "status": "tests_failed",
    }
