"""WebSocket handler for real-time build streaming."""

import json

import redis.asyncio as aioredis
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from forge.config import settings

ws_router = APIRouter()


@ws_router.websocket("/ws/build/{request_id}")
async def websocket_endpoint(websocket: WebSocket, request_id: str):
    await websocket.accept()

    r = aioredis.from_url(settings.REDIS_URL)
    pubsub = r.pubsub()
    await pubsub.subscribe(f"forge:progress:{request_id}")

    try:
        async for message in pubsub.listen():
            if message["type"] != "message":
                continue

            data = message["data"].decode("utf-8")
            await websocket.send_text(data)

            # Auto-close if build is finalized
            if '"type": "complete"' in data:
                break

    except WebSocketDisconnect:
        pass
    finally:
        await pubsub.unsubscribe(f"forge:progress:{request_id}")
        await r.close()
