from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from video_platform.api.deps import get_db, require_token
from video_platform.config import settings
from video_platform.core.enums import Capability, JobStatus
from video_platform.core.schemas import (
    ArtifactManifestResponse,
    JobCreateRequest,
    JobEventResponse,
    JobListResponse,
    JobResponse,
    QAReportResponse,
)
from video_platform.db import JobIteration
from video_platform.services.model_manager import get_runtime_mode
from video_platform.services.orchestrator import start_orchestration
from video_platform.services.repository import (
    create_job,
    get_job,
    latest_qa_report,
    list_job_events,
    list_jobs,
)
from video_platform.services.safety import classify_risk

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"], dependencies=[Depends(require_token)])


def _to_job_response(job) -> JobResponse:
    capability = Capability(job.capability) if job.capability else None
    return JobResponse(
        job_id=job.id,
        status=JobStatus(job.status),
        instruction=job.instruction,
        input_uri=job.input_uri,
        output_uri=job.output_uri,
        capability=capability,
        model_bundle=job.model_bundle,
        risk_level=job.risk_level,
        current_iteration=job.current_iteration,
        max_iterations=job.max_iterations,
        latest_qa_score=job.latest_qa_score,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


def _default_bundle_name() -> str:
    return "api_remote_bundle" if get_runtime_mode() == "api" else "balanced_12g_bundle"


def _apply_admin_override(
    payload: JobCreateRequest,
    metadata: dict,
    x_admin_token: str | None,
) -> None:
    if not payload.safety_override:
        return

    configured = settings.safety_admin_token
    if not configured or x_admin_token != configured:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="admin token required for safety override",
        )

    reason = (payload.override_reason or "").strip()
    if len(reason) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="override_reason must be provided and at least 6 characters",
        )

    metadata["admin_override"] = True
    metadata["override_reason"] = reason


@router.post("", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def create_job_endpoint(
    payload: JobCreateRequest,
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
):
    metadata = dict(payload.metadata)
    if payload.callback_url:
        metadata["callback_url"] = payload.callback_url
    _apply_admin_override(payload, metadata, x_admin_token)

    job, created = create_job(
        session=db,
        instruction=payload.instruction,
        input_uri=payload.input_uri,
        metadata=metadata,
        max_iterations=settings.max_iterations,
        idempotency_key=idempotency_key,
    )

    if payload.force_capability is not None:
        job.capability = payload.force_capability.value

    if not job.model_bundle:
        job.model_bundle = _default_bundle_name()
    if not job.risk_level:
        job.risk_level = classify_risk(payload.instruction)

    db.flush()
    db.commit()
    db.refresh(job)

    if created:
        try:
            await start_orchestration(job.id)
        except RuntimeError as exc:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))

    return _to_job_response(job)


@router.get("", response_model=JobListResponse)
def list_jobs_endpoint(limit: int = 50, db: Session = Depends(get_db)):
    rows = list_jobs(db, limit=min(max(limit, 1), 100))
    return JobListResponse(items=[_to_job_response(row) for row in rows])


@router.get("/{job_id}", response_model=JobResponse)
def get_job_endpoint(job_id: str, db: Session = Depends(get_db)):
    job = get_job(db, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job not found")
    return _to_job_response(job)


@router.get("/{job_id}/events", response_model=list[JobEventResponse])
def get_job_events_endpoint(job_id: str, limit: int = 200, db: Session = Depends(get_db)):
    job = get_job(db, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job not found")

    events = list_job_events(db, job_id=job_id, limit=min(max(limit, 1), 1000))
    return [
        JobEventResponse(
            event_id=event.id,
            job_id=event.job_id,
            stage=event.stage,
            level=event.level,
            message=event.message,
            payload=event.payload,
            created_at=event.created_at,
        )
        for event in events
    ]


@router.get("/{job_id}/artifacts", response_model=ArtifactManifestResponse)
def get_artifacts_endpoint(job_id: str, db: Session = Depends(get_db)):
    job = get_job(db, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job not found")

    iterations = (
        db.query(JobIteration)
        .filter(JobIteration.job_id == job_id)
        .order_by(JobIteration.iteration.asc())
        .all()
    )

    intermediate = [f"minio://intermediate/{job_id}/iter_{it.iteration}/trace.json" for it in iterations]
    output = [it.output_uri for it in iterations if it.output_uri]
    if job.output_uri and job.output_uri not in output:
        output.append(job.output_uri)

    return ArtifactManifestResponse(
        job_id=job_id,
        raw=[job.input_uri],
        intermediate=intermediate,
        output=output,
        audit=[f"minio://audit/{job_id}/events.json"],
        retention_days={
            "raw": settings.raw_retention_days,
            "intermediate": settings.intermediate_retention_days,
            "output": settings.output_retention_days,
            "audit": 3650,
        },
    )


@router.get("/{job_id}/qa-report", response_model=QAReportResponse)
def get_qa_report_endpoint(job_id: str, db: Session = Depends(get_db)):
    job = get_job(db, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job not found")

    report = latest_qa_report(db, job_id)
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="qa report not found")

    return QAReportResponse(
        job_id=job_id,
        iteration=report.iteration,
        overall_score=report.overall_score,
        dimension_scores=report.dimension_scores,
        issues=report.issues,
        hard_fail_flags=report.hard_fail_flags,
        recommendations=report.recommendations,
        created_at=report.created_at,
    )
