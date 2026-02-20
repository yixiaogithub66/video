from __future__ import annotations

import asyncio
import logging

from temporalio.worker import Worker

from video_platform.config import settings
from video_platform.db import init_db
from video_platform.services.knowledge import ensure_collection
from video_platform.worker.activities import (
    execute_iteration,
    finalize_blocked,
    finalize_human_review,
    finalize_success,
    plan_iteration,
    qa_iteration,
    safety_precheck,
)
from video_platform.worker.temporal_client import wait_for_temporal
from video_platform.worker.workflows import VideoEditWorkflow

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main() -> None:
    init_db()
    ensure_collection()

    client = await wait_for_temporal()
    worker = Worker(
        client,
        task_queue=settings.temporal_task_queue,
        workflows=[VideoEditWorkflow],
        activities=[
            safety_precheck,
            plan_iteration,
            execute_iteration,
            qa_iteration,
            finalize_blocked,
            finalize_success,
            finalize_human_review,
        ],
    )

    logger.info("Temporal worker started on queue=%s", settings.temporal_task_queue)
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
