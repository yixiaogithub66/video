from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from video_platform.api.deps import get_db, require_token
from video_platform.core.enums import JobStatus
from video_platform.core.schemas import (
    ReviewDecisionRequest,
    ReviewDecisionResponse,
)
from video_platform.services.callbacks import callback_url_from_metadata, send_callback
from video_platform.services.orchestrator import start_orchestration
from video_platform.services.repository import create_review_action, get_job, log_job_event, set_job_status

router = APIRouter(prefix="/api/v1/reviews", tags=["reviews"], dependencies=[Depends(require_token)])


def _ensure_reviewable_status(job, decision: str) -> None:
    if decision in {"approve", "reject"} and job.status != JobStatus.human_review.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"job status must be human_review for {decision}",
        )
    if decision == "rerun" and job.status not in {JobStatus.human_review.value, JobStatus.failed.value}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="job status must be human_review or failed for rerun",
        )


@router.post("/{job_id}/decision", response_model=ReviewDecisionResponse)
async def review_decision_endpoint(job_id: str, payload: ReviewDecisionRequest, db: Session = Depends(get_db)):
    job = get_job(db, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job not found")
    _ensure_reviewable_status(job, payload.decision.value)

    create_review_action(
        session=db,
        job_id=job_id,
        decision=payload.decision.value,
        reviewer=payload.reviewer,
        reason=payload.reason,
    )

    if payload.decision.value == "approve":
        set_job_status(db, job_id, JobStatus.succeeded)
    elif payload.decision.value == "reject":
        set_job_status(db, job_id, JobStatus.failed)
    else:
        job.current_iteration = 0
        job.output_uri = None
        job.latest_qa_score = None
        set_job_status(db, job_id, JobStatus.queued)
        db.flush()
        db.commit()
        try:
            await start_orchestration(job_id)
        except RuntimeError as exc:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))

    if payload.decision.value in {"approve", "reject"}:
        callback_url = callback_url_from_metadata(job.metadata_json)
        if callback_url:
            callback_ok, callback_detail = send_callback(
                callback_url,
                {
                    "job_id": job.id,
                    "status": job.status,
                    "source": "manual_review",
                    "instruction": job.instruction,
                    "output_uri": job.output_uri,
                    "latest_qa_score": job.latest_qa_score,
                },
            )
            log_job_event(
                session=db,
                job_id=job.id,
                stage="callback_delivery",
                message="Callback delivered" if callback_ok else "Callback delivery failed",
                payload={"callback_url": callback_url, "detail": callback_detail, "status": job.status},
                level="info" if callback_ok else "warning",
            )

    db.flush()

    return ReviewDecisionResponse(
        job_id=job_id,
        decision=payload.decision,
        resulting_status=JobStatus(job.status),
    )
