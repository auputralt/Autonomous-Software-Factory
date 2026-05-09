"""Structured logging with request-ID correlation."""

from __future__ import annotations

import logging
import sys
import uuid
from contextvars import ContextVar

# Context variable to hold the request ID across async tasks
request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")


class RequestIDFilter(logging.Filter):
    """Injects the current request_id into every log record automatically."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_ctx.get("-")
        return True


def setup_logging(level: str = "INFO") -> None:
    """Configures the root logger with a structured, readable format."""
    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(RequestIDFilter())

    # Format: Time | RequestID | Logger Name | Level | Message
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(request_id)-12s | %(name)-24s | %(levelname)-7s | %(message)s",
        datefmt="%H:%M:%S",
    )
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(getattr(logging, level.upper()))

    # Suppress noise from third-party libraries
    for lib in ["httpx", "httpcore", "google", "urllib3"]:
        logging.getLogger(lib).setLevel(logging.WARNING)


def generate_request_id() -> str:
    """Generates a short, readable unique identifier for a build request."""
    return uuid.uuid4().hex[:12]
