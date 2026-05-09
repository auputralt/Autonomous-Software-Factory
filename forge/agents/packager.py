"""Packager node — finalises the build into a downloadable ZIP."""

from __future__ import annotations

import logging

from forge.agents.state import BuildState
from forge.utils.packaging import create_zip, store_zip
from forge.utils.progress import publish_progress

logger = logging.getLogger(__name__)


async def packager_node(state: BuildState) -> dict:
    request_id = state["request_id"]
    publish_progress(request_id, "packaging", "Forging final artifact…")

    # Create artifact
    zip_bytes = create_zip(state["source_files"], state["test_files"])
    download_url = store_zip(request_id, zip_bytes)

    publish_progress(request_id, "packaging", f"Success! Artifact stored ({len(zip_bytes)} bytes).")

    return {
        "status": "success",
        "download_url": download_url,
    }
