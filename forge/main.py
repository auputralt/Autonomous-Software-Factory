"""FastAPI Entry Point — The Forge Gateway."""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from forge.api.rate_limit import RateLimitMiddleware
from forge.api.routes import router as api_router
from forge.api.ws import ws_router
from forge.logging_config import generate_request_id, request_id_ctx, setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    setup_logging()
    logger = logging.getLogger("forge.main")
    logger.info("FORGE: Initializing Autonomous Factory...")
    yield
    # Shutdown
    logger.info("FORGE: Shutting down factory services.")


app = FastAPI(
    title="FORGE",
    version="3.0.0",
    lifespan=lifespan,
)

# Middleware Stack
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RateLimitMiddleware)


@app.middleware("http")
async def context_id_middleware(request: Request, call_next):
    """Ensures every request has a tracking ID for logs."""
    request_id = request.headers.get("X-Request-ID") or generate_request_id()
    token = request_id_ctx.set(request_id)
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
    finally:
        request_id_ctx.reset(token)


# Route Mounting
app.include_router(api_router, prefix="/api")
app.include_router(ws_router)


@app.get("/health")
async def health():
    return {"status": "operational", "timestamp": time.time()}
