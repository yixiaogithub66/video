from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from video_platform.config import settings
from video_platform.core.schemas import EditPlan

logger = logging.getLogger("video_platform.remote_inference")


def _endpoint(base_url: str) -> str:
    return f"{base_url.rstrip('/')}/v1/video/edit"


def _headers() -> dict[str, str]:
    token = settings.model_api_key or ""
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def call_remote_video_edit(
    job_id: str,
    iteration: int,
    input_uri: str,
    instruction: str,
    plan: EditPlan,
) -> tuple[bool, dict[str, Any], str | None]:
    base_url = settings.model_api_base_url
    if not base_url:
        return False, {}, "MODEL_API_BASE_URL is not configured"

    payload = {
        "job_id": job_id,
        "iteration": iteration,
        "input_uri": input_uri,
        "instruction": instruction,
        "capability": plan.capability.value,
        "tool_chain": plan.tool_chain,
        "constraints": plan.constraints,
        "model_bundle": plan.model_bundle,
    }

    attempts = max(1, settings.remote_model_max_retries + 1)
    last_error = ""

    for i in range(1, attempts + 1):
        try:
            with httpx.Client(timeout=settings.remote_model_timeout_seconds) as client:
                resp = client.post(_endpoint(base_url), headers=_headers(), json=payload)

            if 200 <= resp.status_code < 300:
                data = resp.json() if resp.content else {}
                return True, data, None

            last_error = f"status={resp.status_code} body={resp.text[:500]}"
        except Exception as exc:
            last_error = str(exc)

        if i < attempts:
            time.sleep(min(1.2 * i, 3.0))

    logger.warning("remote inference failed job_id=%s iteration=%s error=%s", job_id, iteration, last_error)
    return False, {}, last_error
