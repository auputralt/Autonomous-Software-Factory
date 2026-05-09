"""FastAPI REST endpoints for Build management."""

from __future__ import annotations

import os
import time

import redis.asyncio as aioredis
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from forge.config import settings
from forge.logging_config import generate_request_id
from forge.queue.tasks import process_build

router = APIRouter()
_redis = aioredis.from_url(settings.REDIS_URL)


class BuildRequest(BaseModel):
    prompt: str = Field(..., min_length=10, max_length=5000)


class BuildStatus(BaseModel):
    request_id: str
    status: str
    download_url: str | None = None
    attempts: int = 0


@router.post("/build", response_model=BuildStatus)
async def create_build(req: BuildRequest):
    blocked = ["ignore previous", "system prompt", "os.environ", "eval("]
    if any(p in req.prompt.lower() for p in blocked):
        raise HTTPException(
            status_code=400, detail="Security violation: Blocked pattern detected."
        )

    request_id = generate_request_id()

    await _redis.hset(
        f"forge:request:{request_id}",
        mapping={
            "status": "queued",
            "created_at": str(time.time()),
            "attempts": "0",
        },
    )
    await _redis.expire(f"forge:request:{request_id}", 86400)

    process_build.delay(request_id, req.prompt)

    return BuildStatus(request_id=request_id, status="queued")


@router.get("/status/{request_id}", response_model=BuildStatus)
async def get_status(request_id: str):
    data = await _redis.hgetall(f"forge:request:{request_id}")
    if not data:
        raise HTTPException(status_code=404, detail="Build request not found.")

    return BuildStatus(
        request_id=request_id,
        status=data.get(b"status", b"unknown").decode(),
        download_url=data.get(b"download_url", b"").decode() or None,
        attempts=int(data.get(b"attempts", b"0").decode()),
    )


@router.get("/download/{request_id}")
async def download_artifact(request_id: str):
    path = os.path.join(settings.DOWNLOAD_DIR, f"{request_id}.zip")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Artifact expired or not found.")
    return FileResponse(
        path, media_type="application/zip", filename=f"forge_{request_id}.zip"
    )
