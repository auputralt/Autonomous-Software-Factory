"""Real-time progress streaming via Redis Pub/Sub."""

from __future__ import annotations

import json
import time

import redis.asyncio as aioredis

from forge.config import settings

_redis = aioredis.from_url(settings.REDIS_URL)


async def publish_progress(
    request_id: str, phase: str, message: str, data: dict | None = None
) -> None:
    """Stream a live update to the build's websocket channel."""
    payload = {
        "type": "progress",
        "phase": phase,
        "message": message,
        "timestamp": time.time(),
        "data": data or {},
    }
    await _redis.publish(f"forge:progress:{request_id}", json.dumps(payload))


async def publish_result(
    request_id: str, status: str, data: dict | None = None
) -> None:
    """Signal final build completion and update request cache."""
    payload = {
        "type": "complete",
        "status": status,
        "timestamp": time.time(),
        "data": data or {},
    }

    # Store in hash for polling-based persistence
    update = {"status": status}
    if data:
        if "download_url" in data:
            update["download_url"] = data["download_url"]
        if "attempts" in data:
            update["attempts"] = str(data["attempts"])
        if "error" in data:
            update["error"] = data["error"]

    async with _redis.pipeline() as pipe:
        pipe.publish(f"forge:progress:{request_id}", json.dumps(payload))
        pipe.hset(f"forge:request:{request_id}", mapping=update)
        await pipe.execute()
