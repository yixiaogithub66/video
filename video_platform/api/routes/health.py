from __future__ import annotations

from fastapi import APIRouter, Response, status

from video_platform.core.schemas import DependencyHealth, HealthResponse, ReadyResponse
from video_platform.services.health_checks import check_db, check_minio, check_qdrant
from video_platform.utils.time import now_utc
from video_platform.worker.temporal_client import get_client

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health_endpoint():
    return HealthResponse(status="ok", now=now_utc())


@router.get("/health/ready", response_model=ReadyResponse)
async def readiness_endpoint(response: Response):
    dependencies: list[DependencyHealth] = []

    db_ok, db_detail = check_db()
    dependencies.append(DependencyHealth(name="database", ok=db_ok, detail=db_detail))

    q_ok, q_detail = check_qdrant()
    dependencies.append(DependencyHealth(name="qdrant", ok=q_ok, detail=q_detail))

    m_ok, m_detail = check_minio()
    dependencies.append(DependencyHealth(name="minio", ok=m_ok, detail=m_detail))

    t_client = await get_client()
    t_ok = t_client is not None
    dependencies.append(
        DependencyHealth(
            name="temporal",
            ok=t_ok,
            detail=None if t_ok else "temporal client unavailable",
        )
    )

    overall = all(dep.ok for dep in dependencies)
    if not overall:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return ReadyResponse(
        status="ok" if overall else "degraded",
        dependencies=dependencies,
        now=now_utc(),
    )
