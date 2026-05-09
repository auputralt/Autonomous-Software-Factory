"""LangGraph state definition for the build pipeline."""

from typing import Any, Optional
from typing_extensions import TypedDict


class BuildState(TypedDict, total=False):
    # Immutable inputs
    request_id: str
    user_prompt: str

    # Produced by agents (None until created)
    blueprint: Optional[dict[str, Any]]
    source_files: Optional[dict[str, str]]
    test_files: Optional[dict[str, str]]
    execution_report: Optional[dict[str, Any]]

    # Loop control
    attempt: int
    max_attempts: int

    # Error feedback for retry loop
    error_feedback: Optional[str]

    # Pipeline status
    status: str  # starting | planning | generating | testing | executing | success | failed

    # Final output
    download_url: Optional[str]
