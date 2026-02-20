from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from video_platform.core.enums import JobStatus
from video_platform.db import CaseRecord, Job, JobEvent, JobIteration, QAReport, ReviewAction, SafetyEvent
from video_platform.services.knowledge import simple_embedding, upsert_case_embedding
from video_platform.utils.time import now_utc

ALLOWED_STATUS_TRANSITIONS: dict[str, set[str]] = {
    JobStatus.queued.value: {JobStatus.planning.value, JobStatus.blocked.value, JobStatus.failed.value},
    JobStatus.planning.value: {JobStatus.editing.value, JobStatus.failed.value},
    JobStatus.editing.value: {JobStatus.qa.value, JobStatus.failed.value},
    JobStatus.qa.value: {
        JobStatus.planning.value,
        JobStatus.succeeded.value,
        JobStatus.human_review.value,
        JobStatus.failed.value,
    },
    JobStatus.human_review.value: {JobStatus.succeeded.value, JobStatus.failed.value, JobStatus.queued.value},
    JobStatus.failed.value: {JobStatus.queued.value},
    JobStatus.succeeded.value: set(),
    JobStatus.blocked.value: set(),
}


def create_job(
    session,
    instruction: str,
    input_uri: str,
    metadata: dict,
    max_iterations: int,
    idempotency_key: str | None = None,
):
    if idempotency_key:
        existing = session.execute(select(Job).where(Job.idempotency_key == idempotency_key)).scalar_one_or_none()
        if existing:
            return existing, False

    job = Job(
        id=str(uuid.uuid4()),
        idempotency_key=idempotency_key,
        status=JobStatus.queued.value,
        instruction=instruction,
        input_uri=input_uri,
        metadata_json=metadata,
        current_iteration=0,
        max_iterations=max_iterations,
    )
    session.add(job)

    try:
        session.flush()
    except IntegrityError:
        session.rollback()
        if idempotency_key:
            existing = session.execute(select(Job).where(Job.idempotency_key == idempotency_key)).scalar_one_or_none()
            if existing:
                return existing, False
        raise

    log_job_event(
        session=session,
        job_id=job.id,
        stage="job_created",
        message="Job accepted",
        payload={"instruction": instruction, "input_uri": input_uri},
    )
    return job, True


def get_job(session, job_id: str) -> Job | None:
    return session.get(Job, job_id)


def list_jobs(session, limit: int = 50) -> list[Job]:
    return session.execute(select(Job).order_by(Job.created_at.desc()).limit(limit)).scalars().all()


def set_job_status(session, job_id: str, status: JobStatus, *, enforce: bool = True) -> Job:
    job = session.get(Job, job_id)
    if job is None:
        raise ValueError(f"job {job_id} not found")
    current = job.status
    target = status.value
    if current == target:
        return job
    if enforce:
        allowed = ALLOWED_STATUS_TRANSITIONS.get(current, set())
        if target not in allowed:
            raise ValueError(f"invalid status transition {current} -> {target}")
    job.status = target
    job.updated_at = now_utc()
    session.flush()
    log_job_event(
        session=session,
        job_id=job_id,
        stage="status_transition",
        message=f"Status changed from {current} to {target}",
        payload={"from": current, "to": target},
    )
    return job


def update_job_iteration(session, job_id: str, iteration: int, edit_plan: dict, execution_log: dict, output_uri: str) -> JobIteration:
    row = JobIteration(
        job_id=job_id,
        iteration=iteration,
        edit_plan=edit_plan,
        execution_log=execution_log,
        output_uri=output_uri,
    )
    session.add(row)

    job = session.get(Job, job_id)
    if job is None:
        raise ValueError("job missing")
    job.current_iteration = iteration
    job.output_uri = output_uri
    job.updated_at = now_utc()
    session.flush()
    log_job_event(
        session=session,
        job_id=job_id,
        stage="iteration_completed",
        message=f"Iteration {iteration} execution completed",
        payload={"output_uri": output_uri},
    )
    return row


def create_qa_report(session, job_id: str, iteration: int, report: dict) -> QAReport:
    qa = QAReport(
        id=str(uuid.uuid4()),
        job_id=job_id,
        iteration=iteration,
        overall_score=report["overall_score"],
        dimension_scores=report["dimension_scores"],
        issues=report["issues"],
        hard_fail_flags=report["hard_fail_flags"],
        recommendations=report["recommendations"],
        raw_report=report,
    )
    session.add(qa)

    job = session.get(Job, job_id)
    if job is None:
        raise ValueError("job missing")
    job.latest_qa_score = qa.overall_score
    job.updated_at = now_utc()
    session.flush()
    log_job_event(
        session=session,
        job_id=job_id,
        stage="qa_completed",
        message=f"QA report written for iteration {iteration}",
        payload={"overall_score": qa.overall_score, "hard_fail_flags": qa.hard_fail_flags},
    )
    return qa


def latest_qa_report(session, job_id: str) -> QAReport | None:
    return (
        session.execute(
            select(QAReport)
            .where(QAReport.job_id == job_id)
            .order_by(QAReport.created_at.desc())
            .limit(1)
        )
        .scalars()
        .first()
    )


def list_job_events(session, job_id: str, limit: int = 200) -> list[JobEvent]:
    return (
        session.execute(
            select(JobEvent)
            .where(JobEvent.job_id == job_id)
            .order_by(JobEvent.created_at.asc())
            .limit(limit)
        )
        .scalars()
        .all()
    )


def log_job_event(session, job_id: str | None, stage: str, message: str, payload: dict | None = None, level: str = "info") -> JobEvent:
    event = JobEvent(
        id=str(uuid.uuid4()),
        job_id=job_id,
        stage=stage,
        level=level,
        message=message,
        payload=payload or {},
    )
    session.add(event)
    session.flush()
    return event


def log_safety_event(
    session,
    job_id: str | None,
    blocked: bool,
    rule_ids: list[str],
    reason: str,
    payload: dict,
    *,
    risk_level: str | None = None,
    override_applied: bool = False,
):
    event = SafetyEvent(
        id=str(uuid.uuid4()),
        job_id=job_id,
        blocked=blocked,
        rule_ids=rule_ids,
        reason=reason,
        payload=payload,
    )
    session.add(event)
    session.flush()

    log_job_event(
        session=session,
        job_id=job_id,
        stage="safety_precheck",
        message="Safety precheck blocked request" if blocked else "Safety precheck passed",
        payload={
            "blocked": blocked,
            "rule_ids": rule_ids,
            "reason": reason,
            "risk_level": risk_level,
            "override_applied": override_applied,
        },
        level="warning" if blocked else "info",
    )
    return event


def create_review_action(session, job_id: str, decision: str, reviewer: str, reason: str):
    action = ReviewAction(
        id=str(uuid.uuid4()),
        job_id=job_id,
        decision=decision,
        reviewer=reviewer,
        reason=reason,
    )
    session.add(action)
    session.flush()
    log_job_event(
        session=session,
        job_id=job_id,
        stage="manual_review_decision",
        message=f"Manual review decision: {decision}",
        payload={"reviewer": reviewer, "reason": reason},
    )
    return action


def create_case_record(
    session,
    job_id: str,
    task_summary: str,
    tags: list[str],
    failure_reason: str | None,
    fix_strategy: str | None,
    final_metrics: dict,
) -> CaseRecord:
    case = CaseRecord(
        id=str(uuid.uuid4()),
        job_id=job_id,
        task_summary=task_summary,
        tags=tags,
        failure_reason=failure_reason,
        fix_strategy=fix_strategy,
        final_metrics=final_metrics,
        embedding=simple_embedding(task_summary),
    )
    session.add(case)
    session.flush()
    upsert_case_embedding(case)

    log_job_event(
        session=session,
        job_id=job_id,
        stage="case_archived",
        message="Case archived into knowledge base",
        payload={"case_id": case.id, "tags": tags},
    )
    return case


def get_case(session, case_id: str) -> CaseRecord | None:
    return session.get(CaseRecord, case_id)


def seed_model_bundles(session, bundles: list[dict]) -> None:
    from video_platform.db import ModelBundle

    for bundle in bundles:
        existing = session.get(ModelBundle, bundle["name"])
        payload = {
            "min_vram_gb": bundle["min_vram_gb"],
            "estimated_time_minutes": bundle["estimated_time_minutes"],
            "download_size_gb": bundle["download_size_gb"],
            "quality_tier": bundle["quality_tier"],
            "metadata_json": {
                "enabled_modules": bundle["enabled_modules"],
            },
        }
        if existing is None:
            session.add(ModelBundle(name=bundle["name"], **payload))
        else:
            existing.min_vram_gb = payload["min_vram_gb"]
            existing.estimated_time_minutes = payload["estimated_time_minutes"]
            existing.download_size_gb = payload["download_size_gb"]
            existing.quality_tier = payload["quality_tier"]
            existing.metadata_json = payload["metadata_json"]
