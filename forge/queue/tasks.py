"""The core background task driving the factory pipeline."""

import asyncio
import logging

from forge.queue.celery_app import celery_app
from forge.config import settings
from forge.utils.progress import publish_progress, publish_result

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=0)
def process_build(self, request_id: str, user_prompt: str) -> None:
    """Async wrapper to run the build pipeline inside the Celery worker."""
    from forge.agents.graph import run_build  # Local import to prevent circularity

    async def _execute():
        logger.info("Starting Build Task: %s", request_id)
        await publish_progress(request_id, "queued", "Your build has entered the factory.")

        try:
            await run_build(
                request_id=request_id,
                user_prompt=user_prompt,
                max_attempts=settings.MAX_BUILD_ATTEMPTS,
            )
        except Exception as exc:
            logger.exception("Build %s failed with exception.", request_id)
            await publish_result(request_id, "failed", {"error": str(exc)})

    # Execute the async pipeline in the sync Celery environment
    asyncio.run(_execute())
