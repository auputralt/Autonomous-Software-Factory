"""Gemini API wrapper with retry, rate-limiting, and modern GenAI SDK."""

from __future__ import annotations

import asyncio
import logging
import time

from google import genai
from google.genai import types
import redis.asyncio as aioredis

from forge.config import settings

logger = logging.getLogger(__name__)

# Initialize the async client using the modern SDK
_client = genai.Client(api_key=settings.GEMINI_API_KEY.get_secret_value()).aio
_redis = aioredis.from_url(settings.REDIS_URL)


async def _check_daily_quota() -> bool:
    """Return True if we still have quota remaining today."""
    key = f"forge:daily_count:{time.strftime('%Y-%m-%d')}"
    count = int(await _redis.get(key) or 0)
    return count < settings.DAILY_REQUEST_LIMIT


async def _increment_daily_quota() -> None:
    """Safely increment the daily quota counter."""
    key = f"forge:daily_count:{time.strftime('%Y-%m-%d')}"
    async with _redis.pipeline() as pipe:
        pipe.incr(key)
        pipe.expire(key, 86400)
        await pipe.execute()


async def call_gemini(
    prompt: str,
    system_instruction: str,
    *,
    model_name: str = settings.MANAGER_MODEL,
    temperature: float = 0.2,
    max_output_tokens: int = 8192,
    max_retries: int = 3,
) -> str:
    """Call Gemini using the modern Google GenAI SDK with robust retries."""
    if not await _check_daily_quota():
        raise RuntimeError(
            f"Daily request limit ({settings.DAILY_REQUEST_LIMIT}) reached. "
            "Try again tomorrow."
        )

    config = types.GenerateContentConfig(
        system_instruction=system_instruction,
        temperature=temperature,
        max_output_tokens=max_output_tokens,
    )

    last_err: Exception | None = None
    for attempt in range(max_retries):
        try:
            response = await _client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=config,
            )

            text = response.text
            if not text:
                raise RuntimeError("Empty response from Gemini")

            await _increment_daily_quota()
            return text

        except Exception as exc:
            last_err = exc
            logger.warning("Gemini call attempt %d failed: %s", attempt + 1, exc)
            if attempt < max_retries - 1:
                # Exponential backoff: 1s, 2s, 4s...
                await asyncio.sleep(2 ** attempt)

    raise RuntimeError(f"Gemini call failed after {max_retries} attempts: {last_err}")
