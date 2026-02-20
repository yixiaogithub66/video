from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from video_platform.config import settings

logger = logging.getLogger("video_platform.callback")


def _request_headers() -> dict[str, str]:
    return {
        "Content-Type": "application/json",
    }


def send_callback(callback_url: str, payload: dict[str, Any]) -> tuple[bool, str]:
    attempts = max(1, settings.callback_max_retries + 1)
    last_error = ""

    for i in range(1, attempts + 1):
        try:
            with httpx.Client(timeout=settings.callback_timeout_seconds) as client:
                response = client.post(callback_url, json=payload, headers=_request_headers())
            if 200 <= response.status_code < 300:
                return True, f"status={response.status_code}"
            last_error = f"status={response.status_code} body={response.text[:200]}"
        except Exception as exc:
            last_error = str(exc)

        if i < attempts:
            time.sleep(min(1.5 * i, 3.0))

    logger.warning("callback delivery failed url=%s error=%s", callback_url, last_error)
    return False, last_error


def callback_url_from_metadata(metadata: dict[str, Any] | None) -> str | None:
    if not metadata:
        return None
    callback = metadata.get("callback_url")
    if callback and isinstance(callback, str):
        return callback.strip() or None
    return None
