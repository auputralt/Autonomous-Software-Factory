"""High-performance IP-based rate limiting middleware."""

from __future__ import annotations

import time
from collections import defaultdict

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Sliding window rate limiter.
    Protects API endpoints from abuse while allowing burst traffic for WebSockets.
    """

    def __init__(self, app, max_requests: int = 10, window_seconds: int = 60):
        super().__init__(app)
        self.max_requests = max_requests
        self.window = window_seconds
        self._hits: dict[str, list[float]] = defaultdict(list)

    def _get_ip(self, request: Request) -> str:
        forwarded = request.headers.get("x-forwarded-for")
        return (
            forwarded.split(",")[0].strip()
            if forwarded
            else (request.client.host if request.client else "unknown")
        )

    async def dispatch(self, request: Request, call_next) -> Response:
        # Only rate-limit the build submission endpoint
        if not request.url.path.endswith("/api/build"):
            return await call_next(request)

        ip = self._get_ip(request)
        now = time.time()

        # Clean up old hits
        self._hits[ip] = [t for t in self._hits[ip] if t > now - self.window]

        if len(self._hits[ip]) >= self.max_requests:
            retry_after = int(self._hits[ip][0] + self.window - now) + 1
            return JSONResponse(
                status_code=429,
                content={"detail": f"Rate limit exceeded. Try again in {retry_after}s."},
                headers={"Retry-After": str(retry_after)},
            )

        self._hits[ip].append(now)
        return await call_next(request)
