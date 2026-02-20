from __future__ import annotations

from fastapi import Header, HTTPException, status

from video_platform.config import settings
from video_platform.db import SessionLocal


def get_db():
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _extract_bearer(authorization: str | None) -> str | None:
    if not authorization:
        return None
    parts = authorization.strip().split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1]
    return None


def require_token(
    x_api_token: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
) -> None:
    tokens = settings.api_tokens()
    if not tokens:
        return

    bearer = _extract_bearer(authorization)
    candidate = x_api_token or bearer
    if candidate not in tokens:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid api token")
