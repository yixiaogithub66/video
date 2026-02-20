from __future__ import annotations

import asyncio
import logging

from video_platform.config import settings

logger = logging.getLogger(__name__)

try:
    from temporalio.client import Client
except Exception:  # pragma: no cover - optional local dependency during tests
    Client = None


async def get_client() -> Client | None:
    if Client is None:
        return None
    try:
        return await Client.connect(settings.temporal_address, namespace=settings.temporal_namespace)
    except Exception as exc:
        logger.warning("Temporal connection unavailable: %s", exc)
        return None


async def wait_for_temporal(max_attempts: int = 30, delay_seconds: float = 2.0) -> Client:
    attempt = 0
    while attempt < max_attempts:
        attempt += 1
        client = await get_client()
        if client is not None:
            return client
        await asyncio.sleep(delay_seconds)
    raise RuntimeError("Unable to connect to Temporal after retries")
